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
    data = revisions.read_sealed(record_path(project, id), FORMAT, versions=(1,2))
    if data['id'] != id:
        raise ValueError('Delivery identity mismatch')
    if data['schema_version']==2:
        if not isinstance(data.get('entries'),dict) or not data['entries']:raise ValueError('Delivery entries are missing')
        for key,entry in data['entries'].items():
            if key!=entry_key(entry['view'],entry['role']) or entry['id']!=key:raise ValueError('Delivery entry identity mismatch')
        resolve_entry(data)
    return data


def entry_key(view, role):
    if role not in ROLES:raise ValueError('Unknown soundtrack role')
    return revisions.identifier(f'{view}.{role}')


def entries(data):
    if data.get('schema_version',1)==2:return data['entries']
    return {role:{**entry,'id':role,'view':'authored','poster':data.get('poster')} for role,entry in data['editions'].items()}


def resolve_entry(data, view=None, role=None, entry_id=None, unambiguous=False):
    available=entries(data)
    if entry_id is not None:
        if entry_id not in available:raise ValueError('Delivery entry is unavailable')
        selected=available[entry_id]
        if view is not None and view!=selected['view'] or role is not None and role!=selected['role']:raise ValueError('Entry differs from the requested view or soundtrack')
        return entry_id,selected
    if unambiguous and view is None and role is not None:
        matches=[(key,value) for key,value in available.items() if value['role']==role]
        if len(matches)!=1:raise ValueError('Choose an explicit view for this soundtrack')
        return matches[0]
    if data.get('schema_version',1)==2:
        default=data['default'];key=entry_key(view if view is not None else default['view'],role if role is not None else default['role'])
    else:
        if view not in [None,'authored']:raise ValueError('View is unavailable in this legacy delivery')
        key=role if role is not None else data['default_role']
    if key not in available:raise ValueError('Requested view and soundtrack are unavailable')
    return key,available[key]


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


def _prepare_legacy(project, declaration, allow_named=False):
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
            if bound['schema_version']==2 and not allow_named:raise ValueError('Named-view editions require delivery selection schema_version 2')
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


def prepare(project, declaration):
    if declaration.get('schema_version')!=2:return _prepare_legacy(project,declaration)
    allowed={'format','schema_version','id','title','notes','default','entries','provenance','scene_snapshot','catalog_snapshot'}
    revisions.fields(declaration,allowed,'view delivery selection')
    if declaration.get('format')!=SELECTION:raise ValueError('Expected ambiance-delivery-selection schema_version 2')
    id=revisions.identifier(declaration['id']);selected=declaration.get('entries')
    if not isinstance(selected,list) or not selected:raise ValueError('Delivery requires view entries')
    result_entries={};dependencies=[];working={}
    for entry in selected:
        revisions.fields(entry,{'view','role','revision','edition','poster'},'view delivery entry')
        if not entry.get('revision') or not entry.get('edition'):raise ValueError('View deliveries require captured edition receipts')
        bound=revisions.load_edition(project,entry['revision'],entry['edition']);view=revisions.edition_view(project,bound)
        if entry.get('view')!=view['id']:raise ValueError('Delivery view differs from its edition')
        key=entry_key(view['id'],entry.get('role'))
        if key in result_entries:raise ValueError('Each view and soundtrack pair must be unique')
        poster=entry.get('poster')
        if poster is None:
            contact=studio.inside(project,bound['verification']['path']).parent/'contacts/decoded-0000.png'
            if contact.is_file():poster=revisions.relative(project,contact)
        one={k:v for k,v in declaration.items() if k in {'id','title','notes','provenance','scene_snapshot','catalog_snapshot'}}
        one.update(format=SELECTION,schema_version=1,editions=[{k:entry[k] for k in ['role','revision','edition']}],default_role=entry['role'])
        if poster:one['poster']=poster
        if not poster:raise ValueError('Each view entry requires its own poster')
        parsed=_prepare_legacy(project,one,allow_named=True)
        from PIL import Image
        with Image.open(studio.inside(project,poster)) as image:
            facts=parsed['editions'][entry['role']]
            if image.size!=(facts['width'],facts['height']):raise ValueError('Entry poster dimensions differ from its movie')
        item=parsed['editions'][entry['role']]
        receipt=reference(project,revisions.relative(project,revisions.edition_path(project,entry['revision'],entry['edition'])))
        result_entries[key]={**item,'id':key,'view':view['id'],'view_sha256':view['sha256'],'poster':parsed['poster'],'edition_receipt':receipt}
        dependencies.extend(parsed['dependencies']);working=parsed['working_inputs']
    default=declaration.get('default')
    revisions.fields(default,{'view','role'},'default delivery pair')
    if set(default)!={'view','role'} or entry_key(default['view'],default['role']) not in result_entries:raise ValueError('Default view and soundtrack must exist')
    default_entry=result_entries[entry_key(default['view'],default['role'])]
    return {'format':FORMAT,'schema_version':2,'id':id,'title':parsed['title'],'notes':parsed['notes'],'created_utc':now(),
            'default':default,'entries':result_entries,'poster':default_entry['poster'],'working_inputs':working,
            'dependencies':list({item['path']:item for item in dependencies}.values()),
            'selection_sha256':studio.encoded_hash(declaration),'selection':declaration,
            'review':'Each view and soundtrack has its own exact edition; human review remains separate.'}


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
                ('entries' if candidate['schema_version']==2 else 'editions'): list(entries(candidate))}


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


def review_states(project, data):
    result={}
    for key,entry in entries(data).items():
        try:
            context=revisions.review_context(project,entry['revision'],entry['edition']) if entry['revision'] else None
            state=studio.gate_status(project,context)
            review_dir=context['review_dir'] if context else project/'reviews'
            checks=[]
            for gate,value in state['gates'].items():
                if value['state']=='passed':continue
                path=review_dir/f'{gate}.json';receipt=studio.read(path) if path.exists() else {}
                checks.append({'gate':gate, 'state':value['state'], 'reasons':value['reasons'],
                               'criteria':[{'id':check['id'],'result':check['result'],'note':check.get('note','')} for check in receipt.get('checks',[]) if check['result']!='pass']})
            result[key]={'view':entry['view'],'role':entry['role'],'subject':state['subject'],
                         'release_ready':bool(entry['revision']) and state['release_ready'],'open_checks':checks}
        except (OSError,ValueError,KeyError,TypeError) as error:
            result[key]={'view':entry['view'],'role':entry['role'],'release_ready':False,'open_checks':[],'error':str(error)}
    return result


def release_state(project, data):
    reasons = []
    for role, edition in entries(data).items():
        if not edition['revision']:
            reasons.append(f'{role}: legacy export has no edition-bound release review')
            continue
        try:
            state = revisions.status(project, edition['revision'], edition['edition'])
            if not state['release_ready']:
                reasons.append(f'{role}: release review is {state["gates"]["release"]["state"]}')
        except (OSError, ValueError, KeyError, TypeError) as error:
            reasons.append(f'{role}: {error}')
    scope = production_scope(project, data)
    if scope['enforced'] and not scope['ready']:
        reasons += ['Production scope: '+r['action'] for r in scope['blocked']]
    return {'approved': not reasons, 'reasons': reasons, 'production_scope': scope}


def production_scope(project, data):
    from . import production_plan, production_coverage
    selected = list(entries(data).values()); revisions_used = sorted({e['revision'] for e in selected if e.get('revision')})
    enforced = (project/production_plan.PATH).exists()
    reports = []; blocked = []
    for revision in revisions_used:
        manifest = revisions.load(project, revision)
        if 'production_plan' not in manifest['controls'] and not enforced: continue
        enforced = True
        outputs = {}
        for entry in selected:
            if entry['revision'] == revision: outputs.setdefault(entry['view'], []).append(entry['role'])
        report = production_coverage.evaluate(project, 'export', revision=revision,
            outputs=[{'view_id': v, 'roles': roles} for v, roles in outputs.items()], details=True)
        reports.append(report['report']); blocked.extend(report['blocked'])
    if enforced and (not revisions_used or any(not e.get('revision') for e in selected)):
        blocked.append({'id': 'plan.delivery-legacy-subject', 'action': 'Capture the intended plan and produce view-bound editions before claiming full scope.'})
    return {'enforced': enforced, 'ready': enforced and not blocked, 'blocked': blocked[:8], 'reports': reports,
            'meaning': 'Captured production scope; earlier sealed records retain their original meaning.'}


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
    result = {key: data[key] for key in ['id', 'title', 'notes', 'created_utc', 'poster', 'working_inputs']}
    result['schema_version']=data['schema_version']
    result['entries'] = {role: {**entry, 'available': checks[entry['movie']['path']]['ok'],
                         'technical_evidence_current': checks[entry['verification']['path']]['ok'] and (not entry.get('edition_receipt') or checks[entry['edition_receipt']['path']]['ok']),
                         'poster':entry.get('poster') if not entry.get('poster') or checks[entry['poster']['path']]['ok'] else None,
                         'error': checks[entry['movie']['path']].get('error')}
                         for role, entry in entries(data).items()}
    if data['schema_version']==2:result['default']=data['default']
    else:
        result['default_role']=data['default_role'];result['editions']=result['entries']
    result['issues'] = [check for check in checks.values() if not check['ok']]
    result['ok'] = not result['issues']
    if data['poster'] and not checks[data['poster']['path']]['ok']:
        result['poster'] = None
    result['checked_utc'] = now()
    result['record_sha256'] = studio.digest(record_path(project, id))
    result['production_scope'] = production_scope(project, data)
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


def feedback(project, id, role, seconds, note, observer, view=None):
    from .project import project_lock
    data = load(project, id)
    selected_id,edition=resolve_entry(data,view,role,unambiguous=True)
    if isinstance(seconds, bool) or not isinstance(seconds, (float, int)) or not math.isfinite(seconds) or not 0 <= seconds < edition['duration_seconds']:
        raise ValueError('Feedback time must fall inside the selected movie')
    if not isinstance(note, str) or not note.strip() or len(note) > 10000:
        raise ValueError('Feedback needs 1–10000 characters')
    if not isinstance(observer, str) or not observer.strip() or len(observer) > 200:
        raise ValueError('Identify the observer')
    if not intact(project, edition['movie'])['ok']:
        raise ValueError('Movie changed; cannot attach feedback to these bytes')
    record = {'format': 'ambiance-movie-feedback', 'schema_version': data['schema_version'], 'id': uuid.uuid4().hex,
              'created_utc': now(), 'delivery': id, 'role': role, 'seconds': seconds,
              'movie': edition['movie'], 'observer': observer.strip(), 'note': note.strip(),
              'state': 'open', 'meaning': 'An observation, not an automatic gate pass.'}
    if data['schema_version']==2:record.update(entry=selected_id,view=edition['view'],view_sha256=edition['view_sha256'],revision=edition['revision'],edition=edition['edition'])
    with project_lock(project):
        path = project/'feedback/movies'/f'{record["id"]}.json'
        studio.write(path, revisions.seal(record))
    return {'ok': True, 'feedback': record, 'path': str(path)}


def feedback_list(project, id):
    results = []
    for path in (project/'feedback/movies').glob('*.json'):
        data = revisions.read_sealed(path, 'ambiance-movie-feedback', versions=(1,2))
        if data['delivery'] == id:
            results.append(data)
    return sorted(results, key=lambda row: row['created_utc'], reverse=True)
