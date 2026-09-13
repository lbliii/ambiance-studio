"""Local immutable audio versions, explicit listening records and CLI operations."""
import json
from pathlib import Path
import shutil
import tempfile
import wave

from . import audio, audio_sources
from .audio_library_records import (VERSION, CONFIG, LIBRARY, AUDITION, EVENT, KINDS, LIMITS,
    now, shape, text, timestamp, reference, checked_ref, metadata, validate_version)
from .command_output import Output, add_output
from .file_identity import digest
from .project import project_lock
from .record_contracts import read_sealed, seal


def absolute(path, label):
    path = Path(path)
    if not path.is_absolute(): raise ValueError(label+' must be an explicit absolute path')
    return path.resolve()


def stable_root(path):
    root = absolute(path, 'media root')
    for parent in [root, *root.parents]:
        if (parent/'.git').exists() or (parent/'ambiance-project.json').exists():
            raise ValueError('Audio media root must be independent of a Git checkout or film project')
    return root


def configure(config, media_root, library_id):
    config = absolute(config, 'config'); root = stable_root(media_root)
    audio.identifier(library_id, 'library id')
    if config.exists(): raise ValueError('Config already exists; choose a fresh explicit config')
    if config.is_relative_to(root): raise ValueError('Config must live outside the managed media root')
    if root.exists(): raise ValueError('Media root already exists; initialization requires a fresh directory')
    header = seal({'format': LIBRARY, 'schema_version': 1, 'id': library_id, 'created_utc': now()})
    settings = {'format': CONFIG, 'schema_version': 1, 'media_root': str(root), 'library_id': library_id,
                'library_sha256': None}
    # Stage under the destination filesystem, then publish only complete resources.
    root.parent.mkdir(parents=True, exist_ok=True); config.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.audio-library-', dir=root.parent) as temporary:
        stage = Path(temporary)/'root'; stage.mkdir(); (stage/'versions').mkdir()
        audio.write_json(stage/'library.json', header)
        settings['library_sha256'] = digest(stage/'library.json')
        with config.open('x') as stream:
            try:
                stream.write(json.dumps(settings, indent=2)+'\n'); stream.flush()
                if root.exists(): raise ValueError('Media root appeared before publication')
                stage.rename(root)
            except BaseException:
                config.unlink(missing_ok=True)
                raise
    return {'ok': True, 'config': str(config), 'library_id': library_id, 'media_root': str(root), 'limits': LIMITS}


def load_config(config):
    config = absolute(config, 'config'); data = audio.read_json(config)
    shape(data, ['format','schema_version','media_root','library_id','library_sha256'], label='audio library config')
    if data['format'] != CONFIG or type(data['schema_version']) is not int or data['schema_version'] != 1:
        raise ValueError('Unsupported audio library config')
    root = stable_root(data['media_root']); audio.identifier(data['library_id']); audio_sources._sha(data['library_sha256'])
    header = read_sealed(audio.inside(root, 'library.json'), LIBRARY)
    shape(header, ['format','schema_version','id','created_utc','payload_sha256'], label='library header')
    if header['id'] != data['library_id'] or digest(root/'library.json') != data['library_sha256']:
        raise ValueError('Configured library identity changed')
    return root, header


def version_folder(root, asset_id, version):
    audio.identifier(asset_id, 'asset id'); audio.identifier(version, 'version')
    return audio.inside(root, f'versions/{asset_id}/{version}')


def load_version(root, header, asset_id, version, seen=None):
    folder = version_folder(root, asset_id, version); value = validate_version(folder)
    if (value['library_id'], value['asset_id'], value['version']) != (header['id'], asset_id, version):
        raise ValueError('Version location/identity mismatch (duplicate ID or broken reference)')
    seen = set() if seen is None else seen
    if version in seen: raise ValueError('Cyclic parent version reference')
    parent = value['parent']
    if parent:
        prior, prior_folder = load_version(root, header, asset_id, parent['version'], seen | {version})
        if digest(prior_folder/'version.json') != parent['sha256']: raise ValueError('Stale parent version reference')
        if prior['files']['original']['sha256'] != value['files']['original']['sha256']:
            raise ValueError('Parent version must preserve the same original; use a new asset ID')
    return value, folder


def all_versions(root, header):
    base = audio.inside(root, 'versions')
    if not base.is_dir(): raise ValueError('Missing library version directory')
    for asset in sorted(base.iterdir()):
        if asset.name.startswith('.'): continue
        if not asset.is_dir(): raise ValueError('Unexpected file in versions directory')
        for version in sorted(asset.iterdir()):
            if version.name.startswith('.'): continue
            if not version.is_dir(): raise ValueError('Unexpected file in asset versions')
            yield load_version(root, header, asset.name, version.name)


def version_pin(folder, value):
    return {'library_id': value['library_id'], 'asset_id': value['asset_id'], 'version': value['version'],
            'sha256': digest(folder/'version.json')}


def validate_audition(folder, value, audition_id, expected=None):
    audio.identifier(audition_id, 'audition id')
    directory = audio.inside(folder, 'auditions/'+audition_id); path = audio.inside(directory, 'receipt.json')
    record = read_sealed(path, AUDITION)
    shape(record, ['format','schema_version','id','version_pin','source','start_frame','frames','sample_rate',
                   'channels','bits','excerpt','created_utc','listening','payload_sha256'], label='audition receipt')
    if expected is not None and digest(path) != expected: raise ValueError('Stale audition receipt')
    if record['id'] != audition_id or record['version_pin'] != version_pin(folder, value): raise ValueError('Audition version identity changed')
    if record['source'] != value['files'].get('working'): raise ValueError('Audition source changed')
    checked_ref(folder, record['source']); excerpt = checked_ref(directory, record['excerpt'])
    info = audio.wav_info(excerpt); working = value['working_format']
    start = audio.integer(record['start_frame'], 'audition start'); frames = audio.integer(record['frames'], 'audition frames', 1)
    if start+frames > working['frames']: raise ValueError('Audition exceeds source')
    for key in ['sample_rate','channels','bits']:
        if record[key] != working[key] or info[key] != working[key]: raise ValueError('Audition format changed')
    if frames != info['frames'] or record['listening'] != 'not performed': raise ValueError('Invalid audition state or duration')
    # Exact payload comparison avoids treating a different excerpt as this region.
    with wave.open(str(checked_ref(folder, record['source'])), 'rb') as source, wave.open(str(excerpt), 'rb') as output:
        source.setpos(start)
        remaining = frames
        while remaining:
            count = min(65536, remaining)
            if source.readframes(count) != output.readframes(count): raise ValueError('Audition samples differ from selected source region')
            remaining -= count
    return record, path


def validate_observation(folder, value, observation):
    shape(observation, ['version_sha256','source_sha256','listened','observer','observed_utc','device',
                        'playback_path','start_frame','frames','heard','suitability'], ['audition'], 'listening observation')
    if observation['version_sha256'] != digest(folder/'version.json'): raise ValueError('Stale observation version identity')
    if 'working' not in value['files'] or observation['source_sha256'] != value['files']['working']['sha256']:
        raise ValueError('Observation must identify this prepared source')
    if observation['listened'] is not True: raise ValueError('Observation must record actual listening')
    for key in ['observer','device','playback_path','heard']: text(observation[key], key)
    timestamp(observation['observed_utc'])
    if observation['suitability'] not in ['suitable','unsuitable','revise','unknown']: raise ValueError('Unsupported observation suitability')
    start = audio.integer(observation['start_frame'], 'listening start'); frames = audio.integer(observation['frames'], 'listening frames', 1)
    if start+frames > value['working_format']['frames']: raise ValueError('Observation exceeds prepared source')
    if observation.get('audition') is not None:
        item = observation['audition']; shape(item, ['id','sha256'], label='observed audition'); audio_sources._sha(item['sha256'])
        audition, _ = validate_audition(folder, value, item['id'], item['sha256'])
        if (start, frames) != (audition['start_frame'], audition['frames']): raise ValueError('Observation region differs from audition')
    return observation


def state(folder, value):
    current = 'prepared' if 'working' in value['files'] else 'candidate'
    previous = digest(folder/'version.json'); events = []; ids = set(); last_observation = None
    event_dir = audio.inside(folder, 'events')
    for path in sorted(event_dir.glob('*.json')) if event_dir.exists() else []:
        path = audio.inside(folder, str(path.relative_to(folder)))
        event = read_sealed(path, EVENT)
        shape(event, ['format','schema_version','id','sequence','version_pin','previous_sha256','type','body','created_utc','payload_sha256'], label='library event')
        audio.identifier(event['id']); sequence = len(events)+1
        if event['id'] in ids or path.name != f'{sequence:08d}-{event["id"]}.json' or event['sequence'] != sequence:
            raise ValueError('Duplicate event ID or broken event sequence')
        ids.add(event['id'])
        if event['version_pin'] != version_pin(folder, value) or event['previous_sha256'] != previous:
            raise ValueError('Stale event/version chain')
        if event['type'] == 'observation':
            validate_observation(folder, value, event['body']); current = 'auditioned'; last_observation = event
        elif event['type'] == 'decision':
            body = event['body']; shape(body, ['decision','by','note','observation_sha256'], label='promotion decision')
            text(body['by'], 'decision by'); text(body['note'], 'decision note')
            if body['decision'] not in ['accepted','rejected','revise']: raise ValueError('Unsupported decision')
            if body['decision'] == 'accepted':
                if current != 'auditioned' or not last_observation or body['observation_sha256'] != previous:
                    raise ValueError('Acceptance requires the current listening observation')
                obs = last_observation['body']
                if obs['suitability'] != 'suitable' or obs['start_frame'] != 0 or obs['frames'] != value['working_format']['frames']:
                    raise ValueError('Acceptance requires suitable full-source listening evidence')
            elif body['observation_sha256'] is not None:
                raise ValueError('Rejection/revision decisions do not transfer audition approval')
            current = body['decision']
        else: raise ValueError('Unsupported library event type')
        previous = digest(path); events.append((event, path))
    return {'state': current, 'state_sha256': previous, 'events': events}


def summary(value, folder):
    review = state(folder, value)
    return {**version_pin(folder, value), 'state': review['state'], 'state_sha256': review['state_sha256'],
            'kind': value['kind'], 'metadata': value['metadata'], 'source_format': value['source_format'],
            'working_format': value['working_format'], 'original_sha256': value['files']['original']['sha256'],
            'version_path': str(folder/'version.json')}


def search(config, query='', kind=None, status=None):
    root, header = load_config(config); matches = []
    for value, folder in all_versions(root, header):
        item = summary(value, folder)
        if kind and item['kind'] != kind: continue
        if status and item['state'] != status: continue
        if query.casefold() not in json.dumps([value['asset_id'],value['version'],value['metadata']], sort_keys=True).casefold(): continue
        matches.append(item)
    return {'ok': True, 'library_id': header['id'], 'matches': matches, 'limits': LIMITS}


def inspect(config, asset_id, version):
    root, header = load_config(config); value, folder = load_version(root, header, asset_id, version)
    auditions = audio.inside(folder, 'auditions'); previews = []
    if auditions.exists():
        for directory in sorted(auditions.iterdir()):
            record, path = validate_audition(folder, value, directory.name)
            previews.append({'id': record['id'], 'receipt': str(path), 'sha256': digest(path), 'audio': str(directory/record['excerpt']['path'])})
    review = state(folder, value)
    return {'ok': True, **summary(value, folder), 'record': value, 'auditions': previews,
            'events': [{'path': str(path), 'sha256': digest(path), 'record': event} for event, path in review['events']], 'limits': LIMITS}


def import_version(config, project, asset_id, version, kind, expected, *, source=None, preparation=None,
                   backend=None, raw=None, provenance=None, meta=None, parent=None):
    root, header = load_config(config); project = Path(project).resolve()
    audio_sources._sha(expected)
    if kind not in KINDS: raise ValueError('Unsupported audio kind')
    destination = version_folder(root, asset_id, version)
    if destination.exists(): raise ValueError('Version ID already exists')
    if bool(source) == bool(preparation): raise ValueError('Select exactly one original source or preparation receipt')
    path = audio.inside(project, str(source or preparation))
    if digest(path) != expected: raise ValueError('Selected import hash changed')
    if preparation:
        audio_sources.validate_preparation(project, path)
        prior = read_sealed(path, audio_sources.FORMAT)
        source_paths = {key: audio.inside(project, prior[key]['path']) for key in ['original','working','recipe']}
        source_paths['source_receipt'] = path
        info = prior['source_format']; working = prior['working_format']; provenance = prior['provenance']
        if backend or raw: raise ValueError('Prepared imports retain their recorded backend and raw declaration')
    else:
        if not backend: raise ValueError('Candidate import requires an explicit inspection backend')
        inspection = audio_sources.inspect_source(project, str(source), backend, raw)
        source_paths = {'original': path}; info = inspection['format']; working = None
        provenance = audio_sources._provenance(provenance)
    meta = metadata(meta, (working or info)['frames'])
    if parent:
        shape(parent, ['version','sha256'], label='parent version'); audio_sources._sha(parent['sha256'])
    with tempfile.TemporaryDirectory(prefix='ambiance-audio-import-') as temporary:
        stage = Path(temporary); files = {}
        names = {'original':'original.source','working':'working.wav','recipe':'recipe.json','source_receipt':'source-receipt.json'}
        for key, selected in source_paths.items():
            before = reference(project, selected); target = stage/names[key]; shutil.copyfile(selected, target)
            files[key] = reference(stage, target)
            if files[key]['sha256'] != before['sha256'] or reference(project, selected) != before:
                raise ValueError('Import dependency changed during preservation')
        if not preparation:
            audio.write_json(stage/'inspection.json', inspection); files['inspection'] = reference(stage, stage/'inspection.json')
        value = seal({'format': VERSION, 'schema_version': 1, 'library_id': header['id'], 'asset_id': asset_id, 'version': version,
                      'kind': kind, 'created_utc': now(), 'parent': parent, 'files': files, 'source_format': info,
                      'working_format': working, 'provenance': provenance, 'metadata': meta, 'limits': LIMITS})
        audio.write_json(stage/'version.json', value); validate_version(stage)
        with project_lock(root):
            if destination.exists(): raise ValueError('Version ID already exists')
            existing_asset = destination.parent.exists() and any(p.is_dir() and not p.name.startswith('.') for p in destination.parent.iterdir())
            if existing_asset and parent is None: raise ValueError('Existing asset needs an explicit pinned parent version')
            if parent:
                previous, previous_folder = load_version(root, header, asset_id, parent['version'])
                if digest(previous_folder/'version.json') != parent['sha256']: raise ValueError('Stale parent version reference')
                if previous['files']['original']['sha256'] != files['original']['sha256']: raise ValueError('Parent original differs')
            fingerprint = lambda v: tuple(v['files'].get(k, {}).get('sha256') for k in ['original','working','recipe'])
            for existing, folder in all_versions(root, header):
                if fingerprint(existing) == fingerprint(value):
                    raise ValueError('Duplicate audio content already imported: '+str(folder/'version.json'))
            if digest(path) != expected: raise ValueError('Selected import changed before publication')
            destination.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix='.import-', dir=destination.parent) as publication:
                copied = Path(publication)/'version'; shutil.copytree(stage, copied); validate_version(copied)
                copied.rename(destination)
    return {'ok': True, **summary(value, destination), 'limits': LIMITS}


def audition(config, asset_id, version, expected, audition_id, start=0, frames=None):
    root, header = load_config(config)
    with project_lock(root):
        value, folder = load_version(root, header, asset_id, version); audio_sources._sha(expected)
        if digest(folder/'version.json') != expected: raise ValueError('Stale selected version')
        if 'working' not in value['files']: raise ValueError('Prepare the candidate before creating an audition')
        audio.identifier(audition_id); start = audio.integer(start, 'audition start')
        info = value['working_format']; frames = min(info['frames']-start, 30*info['sample_rate']) if frames is None else frames
        audio.integer(frames, 'audition frames', 1)
        if frames > 60*info['sample_rate'] or start+frames > info['frames']: raise ValueError('Audition exceeds source or 60-second excerpt limit')
        final = audio.inside(folder, 'auditions/'+audition_id)
        if final.exists(): raise ValueError('Audition ID already exists')
        with tempfile.TemporaryDirectory(prefix='ambiance-audition-') as temporary:
            stage = Path(temporary); excerpt = stage/'excerpt.wav'
            with wave.open(str(checked_ref(folder, value['files']['working'])), 'rb') as source, wave.open(str(excerpt), 'wb') as output:
                output.setparams(source.getparams()); source.setpos(start)
                remaining = frames
                while remaining:
                    count = min(65536, remaining); output.writeframesraw(source.readframes(count)); remaining -= count
            record = seal({'format': AUDITION, 'schema_version': 1, 'id': audition_id, 'version_pin': version_pin(folder, value),
                           'source': value['files']['working'], 'start_frame': start, 'frames': frames, 'sample_rate': info['sample_rate'],
                           'channels': info['channels'], 'bits': info['bits'], 'excerpt': reference(stage, excerpt), 'created_utc': now(),
                           'listening': 'not performed'})
            audio.write_json(stage/'receipt.json', record)
            final.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix='.audition-', dir=folder) as publication:
                copied = Path(publication)/'audition'; shutil.copytree(stage, copied)
                if digest(copied/'excerpt.wav') != record['excerpt']['sha256']: raise ValueError('Staged audition changed')
                copied.rename(final)
        validate_audition(folder, value, audition_id)
    return {'ok': True, 'audition': str(final/'receipt.json'), 'audition_sha256': digest(final/'receipt.json'),
            'audio': str(final/'excerpt.wav'), **summary(value, folder), 'limits': LIMITS}


def append_event(config, asset_id, version, expected_state, event_id, event_type, body):
    root, header = load_config(config); audio.identifier(event_id); audio_sources._sha(expected_state)
    with project_lock(root):
        value, folder = load_version(root, header, asset_id, version); review = state(folder, value)
        if review['state_sha256'] != expected_state: raise ValueError('Stale promotion/review state; inspect the current exact version')
        if event_id in [event['id'] for event, _ in review['events']]: raise ValueError('Event ID already exists')
        if event_type == 'observation': validate_observation(folder, value, body)
        elif event_type == 'decision':
            shape(body, ['decision','by','note','observation_sha256'], label='decision')
            text(body['by'], 'by'); text(body['note'], 'note')
            if body['decision'] not in ['accepted','rejected','revise']: raise ValueError('Unsupported decision')
            if body['decision'] == 'accepted':
                if review['state'] != 'auditioned' or not review['events']: raise ValueError('Acceptance requires actual recorded listening')
                observation = review['events'][-1][0]['body']
                if body['observation_sha256'] != expected_state or observation['suitability'] != 'suitable' or observation['start_frame'] != 0 or observation['frames'] != value['working_format']['frames']:
                    raise ValueError('Acceptance requires current suitable full-source listening evidence')
            elif body['observation_sha256'] is not None: raise ValueError('Rejection/revision cannot copy an approval')
        else: raise ValueError('Unsupported event type')
        sequence = len(review['events'])+1
        event = seal({'format': EVENT, 'schema_version': 1, 'id': event_id, 'sequence': sequence,
                      'version_pin': version_pin(folder, value), 'previous_sha256': expected_state,
                      'type': event_type, 'body': body, 'created_utc': now()})
        parent = audio.inside(folder, 'events'); parent.mkdir(exist_ok=True)
        final = parent/f'{sequence:08d}-{event_id}.json'
        with tempfile.TemporaryDirectory(prefix='.event-', dir=folder) as temporary:
            staged = Path(temporary)/'event.json'; audio.write_json(staged, event)
            staged.rename(final)
    return {'ok': True, **summary(value, folder), 'event': str(final), 'event_sha256': digest(final), 'limits': LIMITS}


def add_parsers(group):
    sub = group.add_parser('library', help='Typed local audio versions and portable source use').add_subparsers(dest='library_action', required=True)
    p = sub.add_parser('configure'); p.add_argument('--config', type=Path, required=True)
    p.add_argument('--media-root', type=Path, required=True); p.add_argument('--library-id', required=True)
    p = sub.add_parser('search'); p.add_argument('--config', type=Path, required=True); p.add_argument('query', nargs='?', default='')
    p.add_argument('--kind', choices=KINDS); p.add_argument('--state', choices=['candidate','prepared','auditioned','accepted','rejected','revise'])
    add_output(p, Output.REPORT, type=Path)
    p = sub.add_parser('check'); p.add_argument('receipt', type=Path); add_output(p, Output.REPORT, type=Path)
    for action in ['inspect','import','audition','observe','promote','materialize']:
        p = sub.add_parser(action); p.add_argument('--config', type=Path, required=True)
        p.add_argument('asset_id'); p.add_argument('--version', required=True)
        if action == 'inspect': add_output(p, Output.REPORT, type=Path)
        if action == 'import':
            p.add_argument('--kind', choices=KINDS, required=True)
            select = p.add_mutually_exclusive_group(required=True); select.add_argument('--source', type=Path); select.add_argument('--preparation', type=Path)
            p.add_argument('--sha256', required=True); p.add_argument('--backend', choices=['pcm','macos-afconvert'])
            p.add_argument('--raw-format', choices=['u8','s16le','s24le','s32le']); p.add_argument('--raw-rate', type=int); p.add_argument('--raw-channels', type=int)
            p.add_argument('--provenance', type=Path); p.add_argument('--metadata', type=Path)
            p.add_argument('--parent-version'); p.add_argument('--parent-sha256')
        if action in ['audition','materialize']: p.add_argument('--expect-version', required=True)
        if action == 'audition':
            p.add_argument('--audition-id', required=True); p.add_argument('--start-frame', type=int, default=0); p.add_argument('--frames', type=int)
        if action in ['observe','promote']:
            p.add_argument('--expect-state', required=True); p.add_argument('--event-id', required=True)
        if action == 'observe': p.add_argument('--observation', type=Path, required=True)
        if action == 'promote':
            p.add_argument('--decision', choices=['accepted','rejected','revise'], required=True); p.add_argument('--by', required=True); p.add_argument('--note', required=True)
            p.add_argument('--observation-sha256')
        if action == 'materialize':
            p.add_argument('--materialization-id', required=True); p.add_argument('--allow-unaccepted', action='store_true')
            p.add_argument('--expect-state', required=True)


def _run(args, project):
    action = args.library_action
    if action == 'configure': return configure(args.config, args.media_root, args.library_id)
    if action == 'check':
        from .audio_materialization import validate_materialization
        return validate_materialization(project, args.receipt)
    if action == 'search': return search(args.config, args.query, args.kind, args.state)
    if action == 'inspect': return inspect(args.config, args.asset_id, args.version)
    if action == 'import':
        if bool(args.parent_version) != bool(args.parent_sha256): raise ValueError('Parent version and SHA-256 are required together')
        if args.preparation and args.provenance: raise ValueError('Prepared imports preserve recorded provenance')
        parent = {'version': args.parent_version, 'sha256': args.parent_sha256} if args.parent_version else None
        local_json = lambda path: audio.read_json(audio.inside(project, str(path))) if path else None
        return import_version(args.config, project, args.asset_id, args.version, args.kind, args.sha256,
            source=args.source, preparation=args.preparation, backend=args.backend, raw=audio_sources._raw(args),
            provenance=local_json(args.provenance), meta=local_json(args.metadata), parent=parent)
    if action == 'audition': return audition(args.config, args.asset_id, args.version, args.expect_version, args.audition_id, args.start_frame, args.frames)
    if action == 'observe':
        return append_event(args.config, args.asset_id, args.version, args.expect_state, args.event_id, 'observation', audio.read_json(args.observation))
    if action == 'promote':
        body = {'decision': args.decision, 'by': args.by, 'note': args.note, 'observation_sha256': args.observation_sha256}
        return append_event(args.config, args.asset_id, args.version, args.expect_state, args.event_id, 'decision', body)
    if action == 'materialize':
        from .audio_materialization import materialize
        return materialize(args.config, project, args.asset_id, args.version, args.expect_version,
                           args.expect_state, args.materialization_id, args.allow_unaccepted)
    raise ValueError('Unsupported audio library operation')


def run(args, project):
    result = _run(args, project)
    return {**result, 'operation': args.library_action}
