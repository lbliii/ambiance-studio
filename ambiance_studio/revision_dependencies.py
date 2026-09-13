"""Collect explicit revision inputs and their source/provenance identities.

Control documents retain their captured bytes; binary dependencies remain at
versioned project paths. This collector does not publish records or grant reviews.
"""
import hashlib
import json
from pathlib import Path
import re

import studio
from . import assets, audio
from .record_contracts import fields
from .project_references import ref, unique

SELECTION = 'ambiance-revision-selection'
PREPARATION = 'ambiance-external-preparation'
DOCUMENTS = {
    'production_plan': 'layout',
    'brief': 'intent', 'layer_plan': 'layout', 'layout_notes': 'layout',
    'inventory': 'layout', 'generation_ledger': 'assets',
    'sound_plan': 'sound-design', 'source_ledger': 'sound-design',
}


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
        declaration = audio.read_json(path)
        if isinstance(declaration, dict) and declaration.get('format') == 'ambiance-audio-materialization':
            from .audio_materialization import validate_materialization
            materialized = validate_materialization(self.project, path)
            self.document(f'preparation-{index}.json', path, 'sound-design', 'audio_materialization')
            for item in materialized['dependencies']:
                self.pin(studio.inside(self.project, item['path']), item['section'], item['role'], item['sha256'])
            self.notes.append('Contained library audio and exact review history are pinned; source use is not a complete master or film approval.')
            return
        if isinstance(declaration, dict) and declaration.get('format') == 'ambiance-audio-preparation':
            from .audio_sources import validate_preparation
            prepared = validate_preparation(self.project, path)
            self.document(f'preparation-{index}.json', path, 'sound-design', 'audio_preparation')
            for item in prepared['dependencies']:
                self.pin(studio.inside(self.project, item['path']), item['section'], item['role'], item['sha256'])
            self.notes.append('Prepared audio source dependencies are pinned; preparation is not a complete master or an audition.')
            return
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
        for key in ['registration_source', 'source_mapping', 'edge_preparation', 'motion_preparation', 'preparation_receipt', 'cel_trim', 'region_receipt']:
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
        for key in ['registration_source', 'source_mapping', 'edge_preparation', 'motion_preparation', 'preparation_receipt', 'cel_trim', 'region_receipt']:
            source = packed.get('provenance', {}).get(key)
            if source:
                source_path = (pack/source['file']).resolve()
                self.pin(source_path, 'assets', key, source['sha256'])
                if key == 'cel_trim':
                    from .cel_trim import validate as validate_trim
                    trimmed=validate_trim(source_path,source['sha256'],[(pack/name).resolve() for name in paths],recipe)
                    for dep in trimmed['dependencies']:self.pin(dep['path'],'assets',dep['role'],dep['sha256'])
                if key == 'source_mapping': self.source_mapping(source_path)
                if key == 'region_receipt':
                    from .art_regions import validate_region_receipt
                    region=validate_region_receipt(source_path,source['sha256'],[(pack/name).resolve() for name in paths],recipe)
                    for dep in region['dependencies']: self.pin(dep['path'],'assets',dep['role'],dep['sha256'])
                if key == 'preparation_receipt':
                    from .compound_preparation import validate_preparation_receipt
                    prepared=validate_preparation_receipt(source_path,source['sha256'],[(pack/name).resolve() for name in paths],recipe)
                    for dep in prepared['dependencies']: self.pin(dep['path'],'assets',dep['role'],dep['sha256'])
                if key == 'motion_preparation':
                    from .asset_motion import validate_preparation, compiler_settings
                    motion=validate_preparation(source_path,source['sha256'],[(pack/name).resolve() for name in paths])
                    compiler_settings(motion,recipe)
                    for dep in motion['dependencies']: self.pin(dep['path'],'assets',dep['role'],dep['sha256'])
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
    docs = dict(docs)
    from . import production_plan
    canonical_plan = studio.inside(project, production_plan.PATH)
    if canonical_plan.exists() or docs.get('production_plan'):
        if docs.get('production_plan', production_plan.PATH) != production_plan.PATH:
            raise ValueError('Capture must select the canonical production plan; apply a scope revision before capture')
        plan = production_plan.load(project)
        docs['production_plan'] = production_plan.PATH
        if docs.get('inventory', 'plans/asset-inventory.json') != 'plans/asset-inventory.json':
            raise ValueError('Canonical production intent uses plans/asset-inventory.json')
        docs['inventory'] = 'plans/asset-inventory.json'
        for source in plan['sources']: c.pin(studio.inside(project, source['path']), 'layout', 'production_source', source['sha256'])
        for source in plan.get('migration', {}).get('originals', []):
            c.pin(studio.inside(project, source['path']), 'layout', 'production_source', source['sha256'])
        for relation in plan['relations']:
            for dep in relation['dependencies']: c.pin(studio.inside(project, dep['path']), 'animation', 'production_driver', dep['sha256'])
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
