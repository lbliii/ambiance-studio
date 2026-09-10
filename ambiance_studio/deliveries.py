"""Immutable, playable delivery sets and explicit presentation selections.

This index references existing edition/decode evidence. It never invents a
captured revision, copies a review verdict, or chooses a movie by filename.
"""
from datetime import datetime, timezone
import math
from pathlib import Path
import threading
import uuid

import studio
from . import revisions

FORMAT = 'ambiance-delivery'
SELECTION = 'ambiance-delivery-selection'
PRESENTATION = 'ambiance-presentation'
ROLES = {'score': 'Score', 'effects': 'Effects only', 'silent': 'Silent picture'}


def now():
    return datetime.now(timezone.utc).isoformat()


class Fingerprints:
    """Reuse a hash only while file identity and change timestamps are unchanged."""
    def __init__(self):
        self.values = {}
        self.lock = threading.Lock()

    def digest(self, path):
        with self.lock:
            before = path.stat()
            key = (str(path), before.st_dev, before.st_ino, before.st_size,
                   before.st_mtime_ns, before.st_ctime_ns)
            if key in self.values:
                return self.values[key]
            value = studio.digest(path)
            after = path.stat()
            if before != after:
                raise ValueError(f'File changed while checking: {path.name}')
            if len(self.values) > 2048:
                self.values.clear()
            self.values[key] = value
            return value


def reference(project, name):
    path = studio.inside(project, name)
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f'Missing or empty delivery input: {name}')
    return {'path': name, 'sha256': studio.digest(path), 'bytes': path.stat().st_size}


def intact(project, item, fingerprints=None):
    try:
        path = studio.inside(project, item['path'])
        digest = fingerprints.digest(path) if fingerprints else studio.digest(path)
        if digest != item['sha256'] or path.stat().st_size != item['bytes']:
            return {'ok': False, 'path': item['path'], 'error': 'File changed'}
        return {'ok': True, 'path': item['path']}
    except (OSError, ValueError, KeyError) as error:
        return {'ok': False, 'path': item.get('path'), 'error': str(error)}


def record_path(project, id):
    return studio.inside(project, f'deliveries/{revisions.identifier(id)}.json')


def load(project, id):
    data = revisions.read_sealed(record_path(project, id), FORMAT)
    if data['id'] != id:
        raise ValueError('Delivery identity mismatch')
    return data


def metadata(report):
    keys = {'duration_seconds': 'duration_seconds', 'width': 'width', 'height': 'height',
            'fps': 'fps', 'frames': 'decoded_frames'}
    result = {key: report.get(source) for key, source in keys.items()}
    for key, value in result.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f'Media verification lacks valid {key}')
    tracks = report.get('audio', {}).get('tracks')
    if tracks not in [0, 1]:
        raise ValueError('Media verification lacks its audio track count')
    result['audio_tracks'] = tracks
    return result


def prepare(project, declaration):
    allowed = {'format', 'schema_version', 'id', 'title', 'notes', 'default_role', 'editions',
               'poster', 'provenance', 'scene_snapshot', 'catalog_snapshot'}
    revisions.fields(declaration, allowed, 'delivery selection')
    if declaration.get('format') != SELECTION or declaration.get('schema_version') != 1:
        raise ValueError('Expected ambiance-delivery-selection schema_version 1')
    id = revisions.identifier(declaration['id'])
    title = declaration.get('title', id)
    notes = declaration.get('notes', '')
    if not isinstance(title, str) or not title.strip() or not isinstance(notes, str):
        raise ValueError('Delivery title and notes must be text')
    entries = declaration.get('editions')
    if not isinstance(entries, list) or not entries:
        raise ValueError('A delivery needs at least one verified movie')
    editions = {}; dependencies = []
    for entry in entries:
        revisions.fields(entry, {'role', 'file', 'verification', 'revision', 'edition'}, 'delivery edition')
        role = entry.get('role')
        if role not in ROLES or role in editions:
            raise ValueError('Use each of score, effects, silent at most once per delivery')
        bound = None
        if entry.get('revision') or entry.get('edition'):
            bound = revisions.load_edition(project, entry['revision'], entry['edition'])
            if entry.get('file', bound['output']['path']) != bound['output']['path']:
                raise ValueError('Selected movie differs from captured edition output')
            file = bound['output']['path']; verification = bound['verification']['path']
            receipt = reference(project, revisions.relative(project, revisions.edition_path(project, entry['revision'], entry['edition'])))
            dependencies.append(receipt)
        else:
            file = entry['file']; verification = entry['verification']
        movie = reference(project, file)
        if Path(file).suffix.lower() != '.mp4':
            raise ValueError('Delivery playback currently supports MP4 movies')
        report_ref = reference(project, verification)
        report = studio.read(studio.inside(project, verification))
        if report.get('ok') is not True or report.get('fully_decoded') is not True or report.get('input_unchanged') is not True:
            raise ValueError('Delivery needs successful full-decode evidence of an unchanged movie')
        if report.get('input_sha256') != movie['sha256'] or report.get('input_sha256_after') != movie['sha256']:
            raise ValueError('Verification does not identify the selected movie bytes')
        if bound and (bound['output']['sha256'] != movie['sha256'] or bound['verification']['sha256'] != report_ref['sha256']):
            raise ValueError('Captured edition output or verification changed')
        facts = metadata(report)
        if (role == 'silent') != (facts['audio_tracks'] == 0):
            raise ValueError('Soundtrack role disagrees with decoded audio tracks')
        editions[role] = {'role': role, 'label': ROLES[role], 'movie': movie,
                          'verification': report_ref, **facts,
                          'revision': entry.get('revision'), 'edition': entry.get('edition'),
                          'provenance_kind': 'captured-edition' if bound else 'legacy-verified-export'}
        dependencies += [movie, report_ref]
    default = declaration.get('default_role', next(iter(editions)))
    if default not in editions:
        raise ValueError('The default soundtrack must exist in this delivery')
    poster = reference(project, declaration['poster']) if declaration.get('poster') else None
    if poster and Path(poster['path']).suffix.lower() not in ['.png', '.jpg', '.jpeg', '.webp']:
        raise ValueError('Cover must be a PNG, JPEG or WebP image')
    if poster:
        dependencies.append(poster)
    for name in declaration.get('provenance', []):
        dependencies.append(reference(project, name))
    working = {}
    for kind in ['scene', 'catalog']:
        name = declaration.get(kind+'_snapshot')
        if name:
            working[kind] = reference(project, name)
            dependencies.append(working[kind])
    return {'format': FORMAT, 'schema_version': 1, 'id': id, 'title': title.strip(), 'notes': notes,
            'created_utc': now(), 'default_role': default, 'editions': editions, 'poster': poster,
            'working_inputs': working, 'dependencies': list({d['path']: d for d in dependencies}.values()),
            'selection_sha256': studio.encoded_hash(declaration), 'selection': declaration,
            'review': 'Human review is separate; registration does not grant release approval.'}


def register(project, declaration, dry_run=False):
    from .project import project_lock
    with project_lock(project):
        candidate = prepare(project, declaration)
        path = record_path(project, candidate['id'])
        if path.exists():
            existing = load(project, candidate['id'])
            if existing['selection_sha256'] == candidate['selection_sha256'] and existing['dependencies'] == candidate['dependencies']:
                return {'ok': True, 'id': candidate['id'], 'reused': True, 'record': str(path)}
            raise ValueError('Delivery ID exists with different inputs; choose a new ID')
        for item in candidate['dependencies']:
            if not intact(project, item)['ok']:
                raise ValueError('Delivery input changed during registration')
        if not dry_run:
            studio.write(path, revisions.seal(candidate))
        return {'ok': True, 'id': candidate['id'], 'dry_run': dry_run, 'record': str(path),
                'editions': list(candidate['editions'])}


def current(project, channel='review'):
    if channel not in ['review', 'release']:
        raise ValueError('Presentation channel must be review or release')
    paths = sorted((project/'presentations'/channel).glob('*.json'))
    if not paths:
        return None
    result = revisions.read_sealed(paths[-1], PRESENTATION)
    if result['channel'] != channel or paths[-1].stem != f'{result["sequence"]:08d}':
        raise ValueError('Presentation identity mismatch')
    return result


def selection_token(project, channel='review'):
    selected = current(project, channel)
    return selected['payload_sha256'] if selected else 'none'


def release_state(project, data):
    reasons = []
    for role, edition in data['editions'].items():
        if not edition['revision']:
            reasons.append(f'{role}: legacy export has no edition-bound release review')
            continue
        try:
            state = revisions.status(project, edition['revision'], edition['edition'])
            if not state['release_ready']:
                reasons.append(f'{role}: release review is {state["gates"]["release"]["state"]}')
        except (OSError, ValueError, KeyError, TypeError) as error:
            reasons.append(f'{role}: {error}')
    return {'approved': not reasons, 'reasons': reasons}


def present(project, id, actor, note='', channel='review', expected=None):
    from .project import project_lock
    from .errors import CommandError
    if not isinstance(actor, str) or not actor.strip():
        raise ValueError('Identify who selected this presentation with --by')
    with project_lock(project):
        previous = current(project, channel)
        token = previous['payload_sha256'] if previous else 'none'
        if expected is not None and expected != token:
            raise CommandError('Current selection changed; the completed delivery is saved but was not presented.', 'stale_selection', 2)
        data = load(project, id)
        issues = [check for item in data['dependencies'] if not (check := intact(project, item))['ok']]
        if issues:
            raise ValueError('Cannot present changed or missing delivery inputs: '+str(issues))
        if channel == 'release' and not release_state(project, data)['approved']:
            raise ValueError('Release selection needs current edition-bound release evidence for every edition')
        sequence = previous['sequence']+1 if previous else 1
        selected = revisions.seal({'format': PRESENTATION, 'schema_version': 1, 'channel': channel,
            'sequence': sequence, 'delivery': id, 'delivery_sha256': studio.digest(record_path(project, id)),
            'selected_utc': now(), 'selected_by': actor.strip(), 'note': note, 'previous': token})
        studio.write(project/'presentations'/channel/f'{sequence:08d}.json', selected)
    return {'ok': True, 'selection': selected}


def inspect(project, id, fingerprints=None):
    data = load(project, id)
    checks = {item['path']: intact(project, item, fingerprints) for item in data['dependencies']}
    result = {key: data[key] for key in ['id', 'title', 'notes', 'created_utc', 'default_role', 'poster', 'working_inputs']}
    result['editions'] = {role: {**entry, 'available': checks[entry['movie']['path']]['ok'],
                         'technical_evidence_current': checks[entry['verification']['path']]['ok'],
                         'error': checks[entry['movie']['path']].get('error')}
                         for role, entry in data['editions'].items()}
    result['issues'] = [check for check in checks.values() if not check['ok']]
    result['ok'] = not result['issues']
    if data['poster'] and not checks[data['poster']['path']]['ok']:
        result['poster'] = None
    result['checked_utc'] = now()
    result['record_sha256'] = studio.digest(record_path(project, id))
    return result


def listing(project, fingerprints=None):
    results = []
    for path in sorted((project/'deliveries').glob('*.json')):
        try:
            results.append(inspect(project, path.stem, fingerprints))
        except (OSError, ValueError, KeyError, TypeError) as error:
            results.append({'id': path.stem, 'title': path.stem, 'ok': False, 'error': str(error), 'created_utc': ''})
    return sorted(results, key=lambda item: (item['created_utc'], item['id']), reverse=True)


def latest(project, channel='review', fingerprints=None):
    selected = current(project, channel)
    if not selected:
        return {'ok': True, 'selection': None, 'delivery': None}
    try:
        data = inspect(project, selected['delivery'], fingerprints)
        if data['record_sha256'] != selected['delivery_sha256']:
            raise ValueError('Selected delivery record changed')
        release = release_state(project, load(project, selected['delivery'])) if channel == 'release' else None
        return {'ok': data['ok'] and (release is None or release['approved']),
                'selection': selected, 'delivery': data, 'release': release}
    except (OSError, ValueError, KeyError, TypeError) as error:
        return {'ok': False, 'selection': selected, 'delivery': None, 'error': str(error)}


def feedback(project, id, role, seconds, note, observer):
    from .project import project_lock
    data = load(project, id)
    if role not in data['editions']:
        raise ValueError('Soundtrack is unavailable for this delivery')
    edition = data['editions'][role]
    if isinstance(seconds, bool) or not isinstance(seconds, (float, int)) or not math.isfinite(seconds) or not 0 <= seconds < edition['duration_seconds']:
        raise ValueError('Feedback time must fall inside the selected movie')
    if not isinstance(note, str) or not note.strip() or len(note) > 10000:
        raise ValueError('Feedback needs 1–10000 characters')
    if not isinstance(observer, str) or not observer.strip() or len(observer) > 200:
        raise ValueError('Identify the observer')
    if not intact(project, edition['movie'])['ok']:
        raise ValueError('Movie changed; cannot attach feedback to these bytes')
    record = {'format': 'ambiance-movie-feedback', 'schema_version': 1, 'id': uuid.uuid4().hex,
              'created_utc': now(), 'delivery': id, 'role': role, 'seconds': seconds,
              'movie': edition['movie'], 'observer': observer.strip(), 'note': note.strip(),
              'state': 'open', 'meaning': 'An observation, not an automatic gate pass.'}
    with project_lock(project):
        path = project/'feedback/movies'/f'{record["id"]}.json'
        studio.write(path, revisions.seal(record))
    return {'ok': True, 'feedback': record, 'path': str(path)}


def feedback_list(project, id):
    results = []
    for path in (project/'feedback/movies').glob('*.json'):
        data = revisions.read_sealed(path, 'ambiance-movie-feedback')
        if data['delivery'] == id:
            results.append(data)
    return sorted(results, key=lambda row: row['created_utc'], reverse=True)
