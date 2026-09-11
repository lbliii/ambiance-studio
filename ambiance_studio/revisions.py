"""Explicit immutable control snapshots and typed production dependencies.

Binary dependencies remain in their versioned project locations and are checked
by identity. No folder scan, report prose, or pass verdict defines a release.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import tempfile

import studio
from . import assets, audio

FORMAT = 'ambiance-revision'
SELECTION = 'ambiance-revision-selection'
EDITION = 'ambiance-edition'
PREPARATION = 'ambiance-external-preparation'
DOCUMENTS = {
    'brief': 'intent', 'layer_plan': 'layout', 'layout_notes': 'layout',
    'inventory': 'layout', 'generation_ledger': 'assets',
    'sound_plan': 'sound-design', 'source_ledger': 'sound-design',
}


def add_parsers(sub):
    group = sub.add_parser('revision', help='Capture and verify explicit production revisions').add_subparsers(dest='action', required=True)
    q = group.add_parser('capture'); q.add_argument('id'); q.add_argument('--selection', type=Path, required=True)
    q.add_argument('--dry-run', action='store_true'); q.add_argument('--expect-selection-sha256')
    for action in ['inspect', 'check', 'compare', 'handoff']:
        q = group.add_parser(action); q.add_argument('id')
        if action in ['check', 'compare']: q.add_argument('--out', type=Path)
        if action == 'compare': q.add_argument('--working', action='store_true', required=True)
        if action == 'handoff': q.add_argument('--edition'); q.add_argument('--out', type=Path, required=True)


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}', value):
        raise ValueError('Revision/edition ID needs 1–100 letters, numbers, dots, underscores or hyphens')
    return value


def fields(value, allowed, label):
    if not isinstance(value, dict) or set(value) - set(allowed):
        raise ValueError(f'Unsupported {label} fields; expected {", ".join(allowed)}')


def relative(project, path):
    path = Path(path).resolve()
    if not path.is_relative_to(project.resolve()): raise ValueError(f'Path must stay inside the project: {path}')
    return path.relative_to(project.resolve()).as_posix()


def ref(project, path, section, role, expected=None):
    path = Path(path).resolve(); name = relative(project, path)
    if not path.is_file() or not path.stat().st_size: raise ValueError(f'Missing or empty {role}: {name}')
    result = {'path': name, 'sha256': studio.digest(path), 'bytes': path.stat().st_size,
              'section': section, 'role': role, 'path_base': 'project'}
    if expected is not None and result['sha256'] != expected: raise ValueError(f'Changed {role}: {name}')
    return result


def changed(project, refs):
    result = []
    for item in refs:
        path = studio.inside(project, item['path'])
        actual = studio.digest(path) if path.is_file() else None
        if actual != item['sha256'] or (path.is_file() and path.stat().st_size != item['bytes']):
            result.append({'path': item['path'], 'section': item['section'], 'role': item['role'],
                           'expected_sha256': item['sha256'], 'actual_sha256': actual})
    return result


def unique(refs):
    return list({(r['path'], r['section'], r['role']): r for r in refs}.values())


def seal(data):
    data = dict(data); data['payload_sha256'] = studio.encoded_hash(data); return data


def read_sealed(path, kind):
    data = studio.read(path)
    if data.get('format') != kind or data.get('schema_version') != 1: raise ValueError(f'Unsupported {kind} contract: {path}')
    if data.get('payload_sha256') != studio.encoded_hash({k: v for k, v in data.items() if k != 'payload_sha256'}):
        raise ValueError(f'Manifest integrity changed: {path}')
    return data


class Collector:
    def __init__(self, project):
        self.project = project; self.refs = []; self.documents = {}; self.origins = []; self.masters = []
        self.sound_complete = set(); self.notes = []

    def pin(self, path, section, role, expected=None):
        item = ref(self.project, path, section, role, expected)
        if any(r['path'] == item['path'] and r['sha256'] != item['sha256'] for r in self.refs+self.origins):
            raise ValueError(f'Input changed during collection: {item["path"]}')
        self.refs.append(item); return item

    def document(self, name, path, section, role, content=None):
        original = ref(self.project, path, section, role)
        if any(r['path'] == original['path'] and r['sha256'] != original['sha256'] for r in self.refs+self.origins):
            raise ValueError(f'Input changed during collection: {original["path"]}')
        raw = Path(path).read_bytes()
        if hashlib.sha256(raw).hexdigest() != original['sha256']: raise ValueError(f'Input changed while capturing {path}')
        self.origins.append(original)
        self.documents[name] = {'bytes': raw if content is None else (json.dumps(content, indent=2, allow_nan=False)+'\n').encode(),
                                'section': section, 'role': role, 'origin': original['path']}
        return self.documents[name]

    def session(self, path, name='audio-session.json'):
        doc = self.document(name, path, 'mix', 'audio_session')
        session, _ = audio.load_session(self.project, path, session_data=json.loads(doc['bytes']))
        used = {c['source'] for c in session['clips']}
        for source in session['sources']:
            if source['id'] in used:
                self.pin(studio.inside(self.project, source['path']), 'sound-design', 'audio_source', source['sha256'])
        if session.get('imported_from'):
            origin = session['imported_from']; source_path = Path(origin['path'])
            if not source_path.is_absolute(): source_path = self.project/source_path
            self.pin(source_path, 'mix', 'imported_session', origin['sha256'])
        return session

    def audio_run(self, path, index):
        self.pin(path/'report.json', 'mix', 'audio_run')
        self.pin(path/'session.json', 'mix', 'audio_run_session')
        checked = audio.check_audio(path)
        if not checked['ok']: raise ValueError('Audio run failed integrity checks: '+str(checked['errors']))
        report = audio.read_json(path/'report.json')
        self.pin(path/'report.json', 'mix', 'audio_run')
        self.session(path/'session.json', f'run-session-{index}.json')
        for name, variant in report['variants'].items():
            folder = path/name
            master = self.pin(audio.inside(folder, variant['master']['path']), 'mix', 'master', variant['master']['sha256'])
            self.masters.append(master); self.sound_complete.add(master['path'])
            for stem in variant['stems']:
                self.pin(audio.inside(folder, stem['path']), 'mix', 'stem', stem['sha256'])

    def preparation(self, path, index):
        doc = self.document(f'preparation-{index}.json', path, 'mix', 'external_preparation')
        data = json.loads(doc['bytes'])
        fields(data, ['format', 'schema_version', 'sources', 'recipes', 'outputs', 'notes'], 'external preparation')
        if data.get('format') != PREPARATION or data.get('schema_version') != 1: raise ValueError('Expected ambiance-external-preparation schema_version 1')
        if not data.get('sources') or not data.get('recipes') or not data.get('outputs'): raise ValueError('External preparation needs sources, recipes and outputs')
        for group, section, role in [('sources', 'sound-design', 'audio_source'), ('recipes', 'mix', 'external_recipe'), ('outputs', 'mix', 'master')]:
            for item in data[group]:
                fields(item, ['path', 'sha256'], 'preparation reference')
                if not re.fullmatch('[a-f0-9]{64}', item.get('sha256', '')): raise ValueError('Preparation references require SHA-256')
                r = self.pin(studio.inside(self.project, item['path']), section, role, item['sha256'])
                if group in ['sources', 'outputs']: audio.wav_info(studio.inside(self.project, item['path']))
                if group == 'outputs': self.masters.append(r); self.sound_complete.add(r['path'])
        self.notes.append('External sound preparation is identified by declared recipe/source/output hashes; this tool did not execute or certify its processing.')

    def asset(self, item):
        assets.read_asset(item, self.project)
        self.pin(studio.inside(self.project, item['file']), 'assets', 'image', item['sha256'])
        recipe_name = item.get('provenance', {}).get('recipe')
        if not recipe_name:
            self.notes.append(f'{item["id"]}: source rebuild recipe unavailable; rendered image identity is pinned.')
            return
        pack = studio.inside(self.project, recipe_name).parent
        for name in ['asset.json', 'recipe.json', 'report.json']: self.pin(pack/name, 'assets', 'pack_metadata')
        checked = assets.inspect_pack(pack)
        if not checked['ok']: raise ValueError(f'Prepared pack changed: {pack}')
        packed = checked['asset']
        for key in ['id', 'sha256', 'width', 'height', 'atlas', 'pivot', 'registration_mapping']:
            if item.get(key) != packed.get(key): raise ValueError(f'Catalog/pack {key} mismatch for {item["id"]}')
        if item.get('provenance', {}).get('sources') != packed.get('provenance', {}).get('sources'):
            raise ValueError('Catalog and pack source provenance differ')
        for key in ['registration_source', 'source_mapping', 'edge_preparation']:
            if item.get('provenance', {}).get(key) != packed.get('provenance', {}).get(key): raise ValueError(f'Catalog and pack {key} provenance differ')
        for name, hash_value in checked['build']['outputs'].items():
            self.pin(studio.inside(pack, name), 'assets', 'pack_output', hash_value)
        self.pin(pack/'report.json', 'assets', 'pack_report')
        recipe = studio.read(pack/'recipe.json'); spec = recipe['input']
        paths = [spec['sheet']] if 'sheet' in spec else spec['frames']
        sources = packed['provenance'].get('sources', [])
        if len(paths) != len(sources): raise ValueError('Recipe input/source provenance count differs')
        for name, source in zip(paths, sources):
            target = (pack/name).resolve()
            if target != (pack/source['file']).resolve(): raise ValueError('Recipe input/source path differs')
            self.pin(target, 'assets', 'asset_source', source['sha256'])
        for key in ['registration_source', 'source_mapping', 'edge_preparation']:
            source = packed.get('provenance', {}).get(key)
            if source:
                source_path = (pack/source['file']).resolve()
                self.pin(source_path, 'assets', key, source['sha256'])
                if key == 'source_mapping': self.source_mapping(source_path)
                if key == 'edge_preparation':
                    from .edge_quality import validate_edge_preparation
                    checked_edge = validate_edge_preparation(source_path, source['sha256'], [(pack/name).resolve() for name in paths])
                    for dependency in checked_edge['dependencies']:
                        self.pin(dependency['path'], 'assets', dependency['role'], dependency['sha256'])

    def source_mapping(self, path):
        self.pin(path, 'assets', 'source_mapping')
        data = studio.read(path)
        if data.get('format') != 'ambiance-asset-source-mapping' or data.get('version') != 1 or data.get('path_base') != 'project':
            raise ValueError('Unsupported asset source-mapping contract')
        def image_record(item, role):
            from .asset_prep import checked_image
            checked_image(self.project, item)
            self.pin(studio.inside(self.project, item['file']), 'assets', role, item['sha256'])
        for key in ['reference', 'image']: image_record(data[key], 'mapping_'+key)
        registration = data.get('registration')
        if isinstance(registration, dict):
            image_record(registration['edit'], 'returned_edit')
            for key in ['recipe', 'crop_manifest']:
                item = registration[key]; self.pin(studio.inside(self.project, item['file']), 'assets', key, item['sha256'])
            mask = registration['blend_mask']
            if mask.get('kind') != 'full': self.pin(studio.inside(self.project, mask['file']), 'assets', 'blend_mask', mask['sha256'])
            crop_path = studio.inside(self.project, registration['crop_manifest']['file']); crop = studio.read(crop_path)
            if crop.get('format') != 'ambiance-asset-crop' or crop.get('version') != 1: raise ValueError('Unsupported crop manifest')
            for key in ['source', 'crop']: image_record(crop[key], 'crop_'+key)
            self.pin(crop_path.parent/'recipe.json', 'assets', 'crop_recipe', crop['recipe_sha256'])


def collect(project, selection):
    fields(selection, ['format', 'schema_version', 'scene', 'catalog', 'documents', 'audio'], 'revision selection')
    if selection.get('format') != SELECTION or selection.get('schema_version') != 1: raise ValueError('Expected ambiance-revision-selection schema_version 1')
    c = Collector(project)
    settings = json.loads(c.document('project.json', project/'project.json', 'intent', 'settings')['bytes'])
    policy = json.loads(c.document('pipeline.json', project/'pipeline.json', 'policy', 'pipeline')['bytes'])
    studio.pipeline(project, {'pipeline': policy})
    if settings.get('reference'):
        source = settings['reference']; c.pin(studio.inside(project, source['path']), 'intent', 'reference', source['sha256'])
    docs = selection.get('documents', {}); fields(docs, DOCUMENTS, 'selected documents')
    for role, name in docs.items(): c.document(role+Path(name).suffix, studio.inside(project, name), DOCUMENTS[role], role)
    scene_path = studio.inside(project, selection['scene']); catalog_path = studio.inside(project, selection['catalog'])
    scene = json.loads(c.document('scene.json', scene_path, 'animation', 'scene')['bytes'])
    catalog = json.loads(c.document('catalog.json', catalog_path, 'assets', 'catalog')['bytes'])
    if scene.get('version') != 1 or catalog.get('version') != 1: raise ValueError('Unsupported scene/catalog version')
    from .scene_runtime import scene_bridge
    scene_bridge('inspect', scene, catalog, {'full': True})
    from .finishing import used_asset_ids, dependency_roles
    used = used_asset_ids(scene); roles = dependency_roles(scene)
    selected = [a for a in catalog['assets'] if a['id'] in used]
    if len({a['id'] for a in selected}) != len(selected) or {a['id'] for a in selected} != used: raise ValueError('Missing or duplicate selected catalog entries')
    c.documents['catalog.json']['bytes'] = (json.dumps({'version': 1, 'assets': selected}, indent=2, allow_nan=False)+'\n').encode()
    for item in selected:
        c.asset(item)
        for role in roles[item['id']]:
            if role.startswith('finishing-'): c.pin(studio.inside(project, item['file']), 'assets', role, item['sha256'])
    sound = selection.get('audio', {}); fields(sound, ['session', 'runs', 'masters', 'preparations'], 'selected audio')
    if sound.get('session'): c.session(studio.inside(project, sound['session']))
    for i, name in enumerate(sound.get('runs', [])): c.audio_run(studio.inside(project, name), i)
    for i, name in enumerate(sound.get('preparations', [])): c.preparation(studio.inside(project, name), i)
    for name in sound.get('masters', []):
        path = studio.inside(project, name); audio.wav_info(path)
        c.masters.append(c.pin(path, 'mix', 'master'))
    c.refs = unique(c.refs); c.origins = unique(c.origins); c.masters = unique(c.masters)
    return c


def capture(project, id, selection_path, dry_run=False, expected=None):
    from .project import project_lock
    identifier(id); selection_path = Path(selection_path).resolve(); destination = studio.inside(project, f'revisions/{id}')
    with project_lock(project):
        if destination.exists(): raise ValueError('Revision exists; choose a new ID')
        selection_bytes = selection_path.read_bytes(); selection = json.loads(selection_bytes)
        c = collect(project, selection)
        identities = unique(c.origins+c.refs)
        fingerprint = studio.encoded_hash({'selection': selection, 'inputs': identities})
        if expected and expected != fingerprint: raise ValueError('Selection inputs changed since dry run; capture was not saved')
        if changed(project, identities) or selection_path.read_bytes() != selection_bytes: raise ValueError('Inputs changed during revision capture')
        if dry_run: return {'ok': True, 'dry_run': True, 'id': id, 'selection_sha256': fingerprint, 'dependencies': identities,
                            'captured_documents': list(c.documents), 'destination': str(destination), 'path_base': 'project'}
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.capture-', dir=destination.parent) as temp:
            stage = Path(temp)/'revision'; (stage/'controls').mkdir(parents=True)
            refs = list(c.refs); controls = {}
            for name, doc in c.documents.items():
                target = stage/'controls'/name; target.write_bytes(doc['bytes'])
                name_in_project = relative(project, destination/'controls'/name)
                controls[doc['role']] = name_in_project
                refs.append({'path': name_in_project, 'sha256': studio.digest(target), 'bytes': target.stat().st_size,
                             'section': doc['section'], 'role': doc['role'], 'path_base': 'project'})
            manifest = seal({'format': FORMAT, 'schema_version': 1, 'id': id, 'created_utc': datetime.now(timezone.utc).isoformat(),
                'selection': selection, 'selection_sha256': fingerprint, 'origins': c.origins, 'controls': controls,
                'dependencies': unique(refs), 'masters': c.masters, 'sound_complete': sorted(c.sound_complete), 'notes': c.notes,
                'meaning': 'Captured inputs, not approval. Binary dependencies remain pinned to their project paths.'})
            studio.write(stage/'manifest.json', manifest)
            if changed(project, identities) or selection_path.read_bytes() != selection_bytes: raise ValueError('Inputs changed before revision publication')
            if destination.exists(): raise ValueError('Revision appeared during capture; no replacement')
            stage.rename(destination)
    return {'ok': True, 'id': id, 'manifest': str(destination/'manifest.json'), 'manifest_sha256': studio.digest(destination/'manifest.json'),
            'selection_sha256': fingerprint, 'dependencies': len(refs), 'review': 'not-recorded'}


def manifest_path(project, id):
    return studio.inside(project, f'revisions/{identifier(id)}/manifest.json')


def load(project, id):
    data = read_sealed(manifest_path(project, id), FORMAT)
    if data['id'] != id: raise ValueError('Revision ID does not match its directory')
    for item in data['dependencies']: studio.inside(project, item['path'])
    return data


def check(project, id):
    try:
        data = load(project, id); differences = changed(project, data['dependencies'])
        return {'ok': not differences, 'id': id, 'manifest_sha256': studio.digest(manifest_path(project, id)), 'changed': differences,
                'dependencies': len(data['dependencies']), 'notes': data['notes'], 'review_performed': False}
    except (OSError, ValueError, KeyError, TypeError) as error:
        return {'ok': False, 'id': id, 'errors': [str(error)], 'changed': []}


def compare(project, id):
    data = load(project, id)
    differences = changed(project, data['origins'])
    return {'ok': True, 'id': id, 'working_diverged': bool(differences), 'working_changes': differences, 'integrity': check(project, id),
            'meaning': 'Working divergence does not replace the captured revision or transfer its review.'}


def render_context(project, id):
    result = check(project, id)
    if not result['ok']: raise ValueError('Revision integrity failed: '+json.dumps(result.get('errors') or result['changed']))
    data = load(project, id)
    return {'scene': studio.inside(project, data['controls']['scene']), 'catalog': studio.inside(project, data['controls']['catalog']),
            'revision_id': id, 'manifest_sha256': result['manifest_sha256']}


def edition_path(project, revision, edition):
    return studio.inside(project, f'revisions/{identifier(revision)}/editions/{identifier(edition)}.json')


def load_edition(project, revision, edition):
    data = read_sealed(edition_path(project, revision, edition), EDITION)
    if data['revision'] != revision or data['id'] != edition: raise ValueError('Edition identity mismatch')
    if data['revision_sha256'] != studio.digest(manifest_path(project, revision)): raise ValueError('Edition refers to a different revision manifest')
    return data


def prepare_edition(project, args):
    """Freeze declared inputs before rendering; publication checks them again."""
    edition = getattr(args, 'edition', None)
    if not edition: return None
    if getattr(args, 'view', None) not in [None, 'authored']:
        raise ValueError('Named-view edition registration is not implemented yet; render without --edition and retain the view report.')
    id = getattr(args, 'revision', None)
    if not id: raise ValueError('--edition requires --revision')
    identifier(edition); context = render_context(project, id); data = load(project, id)
    if edition_path(project, id, edition).exists(): raise ValueError('Edition exists; choose a new ID')
    relative(project, args.out)
    c = Collector(project)
    if getattr(args, 'audio_session', None): c.session(studio.inside(project, str(args.audio_session)))
    if getattr(args, 'audio_run', None): c.audio_run(studio.inside(project, str(args.audio_run)), 'edition')
    if getattr(args, 'audio_provenance', None): c.preparation(studio.inside(project, str(args.audio_provenance)), 'edition')
    pcm = getattr(args, 'audio', None); master = None
    if pcm:
        path = Path(pcm).resolve(); audio.wav_info(path); master = c.pin(path, 'mix', 'master')
        declared = set(data['sound_complete']) | c.sound_complete
        if master['path'] not in declared:
            raise ValueError('Edition PCM needs a selected revision master with complete provenance, --audio-run, or --audio-provenance identifying this output')
        # Include frozen sound roots when using the revision's selected master.
        if master['path'] in data['sound_complete']:
            c.refs += [r for r in data['dependencies'] if r['section'] in ['sound-design', 'mix']]
        c.sound_complete.add(master['path'])
    picture = None
    if args.command == 'media' and args.action == 'compose':
        picture = c.pin(Path(args.picture).resolve(), 'export', 'picture_input')
        proof = getattr(args, 'picture_receipt', None); bound = False
        if proof:
            proof_path = studio.inside(project, str(proof)); pinned = c.pin(proof_path, 'export', 'picture_receipt')
            raw = proof_path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != pinned['sha256']: raise ValueError('Picture receipt changed while reading')
            report = json.loads(raw)
            if report.get('view', {}).get('view', {}).get('id', 'authored') != 'authored':
                raise ValueError('Named-view picture receipts need view-aware edition registration, which is not implemented yet.')
            if report.get('mode') != 'video' or not report.get('ok'):
                raise ValueError('Picture receipt must be a successful saved render video report')
            for key in ['scene', 'catalog']:
                if report.get(key+'_sha256') != studio.digest(context[key]): raise ValueError('Picture receipt belongs to a different captured '+key)
            if picture['sha256'] not in [report.get('picture_sha256'), report.get('output_sha256')]: raise ValueError('Picture bytes differ from the render receipt')
            bound = True
        else:
            for previous in sorted((manifest_path(project, id).parent/'editions').glob('*.json')):
                ed = load_edition(project, id, previous.stem)
                if picture['sha256'] in [ed['picture']['sha256'], ed['output']['sha256']]:
                    dependencies = [r for r in ed['dependencies'] if r['section'] == 'export']
                    if changed(project, dependencies): raise ValueError('Selected prior picture edition dependencies changed')
                    c.refs += dependencies; c.pin(previous, 'export', 'picture_edition'); bound = True; break
        if not bound: raise ValueError('Picture is not bound to this revision; supply --picture-receipt or reuse a recorded edition of this revision')
    return {'revision': id, 'id': edition, 'manifest_sha256': context['manifest_sha256'], 'collector': c, 'audio': master, 'picture': picture,
            'inputs': unique(c.refs+c.origins)}


def record_edition(project, prepared, result, args):
    """Register an actually verified render result, never a user-authored pass."""
    if prepared is None: return result
    from .project import project_lock
    if not result.get('ok', True): return result
    with project_lock(project):
        id = prepared['revision']; edition = prepared['id']; c = prepared['collector']
        if studio.digest(manifest_path(project, id)) != prepared['manifest_sha256'] or not check(project, id)['ok']:
            raise ValueError('Revision changed during media production; edition not registered')
        if changed(project, prepared['inputs']): raise ValueError('Selected media/audio inputs changed; edition not registered')
        path = edition_path(project, id, edition)
        if path.exists(): raise ValueError('Edition appeared during production; refusing replacement')
        verification = result.get('verification')
        if not isinstance(verification, dict) or not verification.get('ok'):
            raise ValueError('Edition requires successful actual media verification')
        output_path = Path(result['output']).resolve()
        output = ref(project, output_path, 'export', 'edition_output', result.get('output_sha256'))
        refs = list(c.refs)
        refs += [output, {**output, 'section': 'release'}]
        report_path = verification.get('report')
        if not report_path: raise ValueError('Media verification did not provide its saved report')
        refs.append(ref(project, Path(report_path), 'export', 'media_verification'))
        picture = prepared['picture']
        if picture is None:
            # The render run retains its original encoded picture separately.
            picture_path = Path(args.out).resolve()/'picture.mp4'
            picture = ref(project, picture_path, 'export', 'picture_input')
            refs.append(picture)
        out = Path(args.out).resolve()
        # Explicit named backend receipts, not an open-ended output-folder scan.
        for name in ['render-report.json', 'compose-report.json', 'composition-recipe.json', 'scene.snapshot.json', 'catalog.snapshot.json']:
            file = out/name
            if file.is_file(): refs.append(ref(project, file, 'export', 'production_record'))
        for name, source in [('selected-audio.wav', prepared['audio']), ('picture-input.mp4', prepared['picture'])]:
            if source and (out/name).is_file(): refs.append(ref(project, out/name, 'export', 'media_input_snapshot', source['sha256']))
        doc_dir = out/'edition-inputs'
        if doc_dir.exists(): raise ValueError('Edition input snapshot directory already exists')
        doc_dir.mkdir()
        for name, doc in c.documents.items():
            target = doc_dir/name; target.write_bytes(doc['bytes'])
            refs.append(ref(project, target, doc['section'], doc['role']))
        if changed(project, prepared['inputs']): raise ValueError('Inputs changed before edition publication')
        receipt = seal({'format': EDITION, 'schema_version': 1, 'id': edition, 'revision': id,
            'revision_sha256': prepared['manifest_sha256'], 'created_utc': datetime.now(timezone.utc).isoformat(),
            'picture': picture, 'audio': prepared['audio'], 'output': output, 'dependencies': unique(refs),
            'sound_complete': sorted(c.sound_complete), 'recipe': {'command': args.command, 'action': args.action,
            'repeats': getattr(args, 'repeats', 1)}, 'verification': {'path': relative(project, report_path), 'sha256': studio.digest(report_path)},
            'limits': ['Technical verification only. No creative verdict, listening, phone observation or publication is inferred.']})
        studio.write(path, receipt)
    return {**result, 'edition': {'id': edition, 'revision': id, 'receipt': str(path), 'sha256': studio.digest(path)}}


def review_context(project, id, edition=None):
    data = load(project, id)
    controls = data['controls']; refs = list(data['dependencies']); final_files = []
    subject = {'mode': 'revision', 'revision': id, 'revision_sha256': studio.digest(manifest_path(project, id)),
               'edition': edition, 'dependency_policy': 1}
    if edition:
        ed = load_edition(project, id, edition); refs += ed['dependencies']; final_files = [ed['output']['path']]
        subject['edition_sha256'] = studio.digest(edition_path(project, id, edition))
    gates = studio.read(studio.inside(project, controls['pipeline']))
    settings = studio.read(studio.inside(project, controls['settings']))
    all_roles = {r['role'] for r in refs}
    required = {'intent': {'reference', 'brief'}, 'layout': {'layer_plan'}, 'assets': {'image'}, 'animation': {'scene'},
                'sound-design': {'sound_plan', 'audio_source'}, 'mix': {'master'}, 'export': {'edition_output'}, 'release': {'edition_output'}}
    def relevant(gate): return unique([r for r in refs if r['section'] in [gate, 'policy']])
    def snapshot(gate):
        return {r['path']: studio.digest(studio.inside(project, r['path'])) if studio.inside(project, r['path']).is_file() else None for r in relevant(gate)}
    def issues(gate):
        errors = [f'Selected {r["role"]} changed: {r["path"]}' for r in changed(project, relevant(gate))]
        errors += [f'Selected revision lacks {role}' for role in sorted(required.get(gate, set())-all_roles)]
        if studio.digest(manifest_path(project, id)) != subject['revision_sha256']: errors.append('Revision manifest changed')
        if edition and studio.digest(edition_path(project, id, edition)) != subject['edition_sha256']: errors.append('Edition manifest changed')
        if gate == 'mix':
            complete = set(data['sound_complete']) | (set(ed.get('sound_complete', [])) if edition else set())
            chosen = ([ed['audio']['path']] if ed.get('audio') else []) if edition else [m['path'] for m in data['masters']]
            if not chosen or any(path not in complete for path in chosen): errors.append('Selected master lacks an explicit audio-run or external-preparation dependency record')
        return errors
    return {'settings': settings, 'pipeline': gates, 'subject': subject,
            'review_dir': studio.inside(project, f'reviews/revisions/{id}/'+(f'editions/{identifier(edition)}' if edition else 'picture')),
            'snapshot': snapshot, 'issues': issues, 'final_files': final_files}


def status(project, id, edition=None):
    return studio.gate_status(project, review_context(project, id, edition))


def project_status(project):
    result = studio.gate_status(project); result['revisions'] = []
    for path in sorted((project/'revisions').glob('*/manifest.json')):
        id = path.parent.name; item = {'id': id, 'integrity': check(project, id)}
        try:
            item['working'] = compare(project, id); item['reviews'] = status(project, id); item['editions'] = []
            for ed in sorted((path.parent/'editions').glob('*.json')):
                try: item['editions'].append({'id': ed.stem, 'reviews': status(project, id, ed.stem)})
                except (OSError, ValueError, KeyError, TypeError) as error: item['editions'].append({'id': ed.stem, 'ok': False, 'error': str(error)})
        except (OSError, ValueError, KeyError, TypeError) as error: item['error'] = str(error)
        result['revisions'].append(item)
    return result


def handoff(project, id, edition, out):
    out = Path(out).resolve()
    if out.exists(): raise ValueError('Handoff output exists; choose a fresh directory')
    data = load(project, id); review = status(project, id, edition)
    payload = {'revision': id, 'edition': edition, 'integrity': check(project, id), 'working': compare(project, id), 'reviews': review,
               'manifest': relative(project, manifest_path(project, id)), 'masters': data['masters'],
               'edition_record': load_edition(project, id, edition) if edition else None}
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.handoff-', dir=out.parent) as temp:
        stage = Path(temp)/'result'; stage.mkdir(); studio.write(stage/'handoff.json', payload)
        lines = [f'# Revision {id}', '', f'Edition: {edition or "none selected"}', f'Release ready: {review["release_ready"]}', '',
                 'Captured inputs and review evidence are distinct from current working changes.', '', '## Gate status', '']
        lines += [f'- {gate}: {state["state"]}'+(' — '+'; '.join(state['reasons']) if state['reasons'] else '') for gate, state in review['gates'].items()]
        lines += ['', 'Exact paths and hashes are in handoff.json. No publishing or new creative review was performed.']
        (stage/'handoff.md').write_text('\n'.join(lines)+'\n')
        if out.exists(): raise ValueError('Handoff destination appeared; refusing replacement')
        stage.rename(out)
    return {'ok': True, 'directory': str(out), 'handoff': str(out/'handoff.md'), 'release_ready': review['release_ready']}


def run(args, project):
    if args.action == 'capture': return capture(project, args.id, args.selection, args.dry_run, args.expect_selection_sha256)
    if args.action == 'inspect': return {'ok': True, 'manifest': load(project, args.id), 'integrity': check(project, args.id)}
    if args.action == 'check': return check(project, args.id)
    if args.action == 'compare': return compare(project, args.id)
    if args.action == 'handoff': return handoff(project, args.id, args.edition, args.out)
    raise ValueError('Unknown revision command')
