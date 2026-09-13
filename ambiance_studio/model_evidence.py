"""Typed model edges around existing scene raster and revision authorities."""
from pathlib import Path

import studio
from . import assets, model_instances, model_package
from .coverage_context import pinned
from .record_contracts import read_sealed, seal

FORMAT = 'ambiance-model-scene-evidence'


def implementation():
    return {**model_package.implementation(), **{name: studio.digest(model_package.ROOT/name) for name in [
        'ambiance_studio/model_instances.py', 'ambiance_studio/model_evidence.py',
        'ambiance_studio/scene_runtime.py', 'tools/scene-command.mjs']}}


def model_references(project, scene, catalog):
    """Re-lower the exact pin/state before admitting any compiler ID alias."""
    from .scene_runtime import scene_bridge
    references = {}; aliases = {}
    for record in model_instances.records(scene):
        model_instances.verify_managed(scene, catalog, record)
        package, manifest, closure, root = model_instances.open_pin(project, record['pin'])
        resolved = model_package.bridge(closure, root, state=record['state'])
        expected = scene_bridge('model-instance', scene, catalog, {'instance_id': record['instance_id'], 'resolved': resolved,
            'pin': record['pin'], 'package_source': str(Path(record['pin']['package']).parent/'source'),
            'pivot': closure.models[root]['local_frame']['pivot'], 'placement': record['placement'], 'mount': record['mount'],
            'receivers': record['receivers'], 'sockets': resolved['exported_sockets'], 'previous': record})
        for key in ['mapping', 'sockets', 'root_layer', 'relationships']:
            if expected[key] != record[key]: raise ValueError('Model '+key+' differs from exact package lowering')
        if model_instances.interface(closure, root) != record['interface']:
            raise ValueError('Model interface differs from pinned definition')
        for key in ['effective_controls', 'selected_variants', 'clock']:
            if record[key] != resolved[key]: raise ValueError('Model resolved '+key+' changed')
        if model_instances.managed_subject(scene, catalog, record) != model_instances.managed_subject(expected['scene'], expected['catalog'], record):
            raise ValueError('Managed layers, signals or bindings differ from exact package/state lowering')
        for row in record['mapping']:
            asset = next(a for a in expected['catalog']['assets'] if a['id'] == row['asset_id'])
            recipe = studio.inside(project, asset['provenance']['recipe'])
            compiler_asset = recipe.parent/'asset.json'
            aliases[row['asset_id']] = {'compiler_id': studio.read(compiler_asset)['id'],
                'recipe': asset['provenance']['recipe'], 'compiler_asset': pinned(project, compiler_asset),
                'file': asset['file'], 'sha256': asset['sha256']}
        path = package/'model-package.json'
        references[str(path)] = {**pinned(project, path), 'section': 'assets', 'role': 'model_package'}
        for name, expected in manifest['files'].items():
            path = package/'source'/name
            role = 'model_definition' if name in closure.models else 'model_source'
            row = {**pinned(project, path), 'section': 'assets', 'role': role}
            if row['sha256'] != expected: raise ValueError('Changed model evidence dependency')
            references[str(path)] = row
    return list(references.values()), aliases


def model_dependencies(project, scene, catalog):
    return model_references(project, scene, catalog)[0]


def _raster_inputs(project, receipt_path):
    receipt = studio.read(receipt_path)
    if receipt.get('mode') not in ['frame', 'views-proof'] or receipt.get('ok') is not True:
        raise ValueError('Model evidence requires an existing successful frame or views-proof receipt')
    scene_path, catalog_path = receipt_path.parent/'scene.snapshot.json', receipt_path.parent/'catalog.snapshot.json'
    scene, catalog = studio.read(scene_path), studio.read(catalog_path)
    if studio.digest(scene_path) != receipt['scene_sha256'] or studio.digest(catalog_path) != receipt['catalog_sha256']:
        raise ValueError('Model raster snapshots differ from receipt')
    return receipt, scene, catalog


def bind(project, receipt_path, instance_ids, out):
    """Bind selected instances to real renderer output; this is not observation."""
    from .coverage_evidence import raster_receipt
    project = Path(project).resolve(); receipt_path = Path(receipt_path).resolve()
    pinned(project, receipt_path)
    receipt, scene, catalog = _raster_inputs(project, receipt_path)
    rows = model_instances.records(scene)
    if not instance_ids or len(set(instance_ids)) != len(instance_ids): raise ValueError('Select unique instance IDs')
    selected = [r for r in rows if r['instance_id'] in instance_ids]
    if len(selected) != len(instance_ids): raise ValueError('Model raster lacks a selected instance')
    dependencies = model_dependencies(project, scene, catalog)
    asset_refs = []
    for item in catalog['assets']:
        assets.read_asset(item, project)
        asset_refs.append(pinned(project, studio.inside(project, item['file'])))
    if receipt['mode'] == 'frame' and not receipt.get('view'): raise ValueError('Model raster evidence requires an explicit --view')
    views = receipt.get('views') if receipt['mode'] == 'views-proof' else {receipt['view']['view']['id']: receipt['view']}
    context = {'scene_sha256': receipt['scene_sha256'], 'catalog_sha256': receipt['catalog_sha256'],
               'revision': receipt.get('revision'), 'views': views, 'asset_references': asset_refs}
    if isinstance(context['revision'], dict): context['revision'] = context['revision'].get('revision_id')
    evidence_refs = []
    for view in views: evidence_refs.extend(raster_receipt(project, receipt_path, context, view)['references'])
    record = seal({'format': FORMAT, 'schema_version': 1, 'raster': pinned(project, receipt_path),
        'scene_sha256': receipt['scene_sha256'], 'catalog_sha256': receipt['catalog_sha256'],
        'revision': context['revision'], 'instances': selected, 'views': views,
        'dependencies': dependencies, 'artifacts': evidence_refs,
        'implementation': implementation(), 'acceptance': 'not established',
        'limitations': ['Static instance/pose and actual rendered output; no motion, whole-scene or artistic acceptance.']})
    out = Path(out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('x') as stream:
        import json
        stream.write(json.dumps(record, indent=2)+'\n')
    return {'report': str(out), 'sha256': studio.digest(out), 'instances': instance_ids, 'acceptance': 'not established'}


def verify(project, path, ctx, view):
    from .coverage_evidence import raster_receipt, same_picture
    project = Path(project).resolve(); path = Path(path).resolve()
    report = read_sealed(path, FORMAT)
    same_picture(report, ctx)
    if report['implementation'] != implementation(): raise ValueError('Model evidence implementation changed')
    for ref in [report['raster'], *report['dependencies'], *report['artifacts']]:
        if pinned(project, studio.inside(project, ref['path']))['sha256'] != ref['sha256']: raise ValueError('Model evidence dependency/artifact changed')
    raster_path = studio.inside(project, report['raster']['path'])
    _, scene, catalog = _raster_inputs(project, raster_path)
    records = model_instances.records(scene)
    if not report['instances'] or any(r not in records for r in report['instances']): raise ValueError('Model evidence instance subject changed')
    if model_dependencies(project, scene, catalog) != report['dependencies']: raise ValueError('Model evidence closure changed')
    if view not in report['views']: raise ValueError('Model evidence has no requested view')
    evidence = raster_receipt(project, raster_path, ctx, view)
    return {**evidence, 'kind': 'model-raster', 'references': [pinned(project, path), *evidence['references'],
            *[{'path': r['path'], 'sha256': r['sha256']} for r in report['dependencies']]]}
