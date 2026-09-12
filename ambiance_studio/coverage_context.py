"""Exact production inputs and evidence subject identities.

These helpers retain the production plan, revision and project path authorities;
no readiness decisions or evidence writes belong here.
"""
from pathlib import Path
import hashlib

import studio
from . import production_plan as spec, project_references, revision_capture, scene_runtime
from .project import locations


def context(project, revision=None):
    project = Path(project).resolve(); result = spec.load_context(project, revision)
    if revision:
        captured = revision_capture.render_context(project, revision)
        scene_path, catalog_path = captured['scene'], captured['catalog']
        result['revision_sha256'] = captured['manifest_sha256']
        result['inventory_path'] = studio.inside(project, revision_capture.load(project, revision)['controls']['inventory'])
    else:
        scene_path, catalog_path = locations(project)
        result['revision_sha256'] = None
        result['inventory_path'] = project/'plans/asset-inventory.json'
    scene_bytes, catalog_bytes = scene_path.read_bytes(), catalog_path.read_bytes()
    result.update(scene_path=scene_path, catalog_path=catalog_path,
                  scene=scene_runtime.load_scene_json(scene_bytes), catalog=scene_runtime.load_scene_json(catalog_bytes),
                  scene_sha256=hashlib.sha256(scene_bytes).hexdigest(), catalog_sha256=hashlib.sha256(catalog_bytes).hexdigest())
    info = scene_runtime.scene_bridge('view-inspect', result['scene'], result['catalog'], {})
    result['views'] = {id: {'view': {k: v for k, v in row.items() if k not in ['projection', 'view_sha256']},
                            'output': row['output'], 'view_sha256': row['view_sha256']}
                       for id, row in info['views'].items()}
    from .assets import read_asset
    result['asset_references'] = []
    for asset in result['catalog']['assets']:
        read_asset(asset, project)
        result['asset_references'].append({'path': asset['file'], 'sha256': asset['sha256']})
    return result


def subject(ctx, expectation, view):
    row = ctx['views'].get(view)
    if row is None: raise ValueError('Expected view is absent from scene: '+str(view))
    return {key: ctx[key] for key in ['plan_sha256', 'scene_sha256', 'catalog_sha256', 'revision', 'revision_sha256']} | {
        'expectation_id': expectation['id'], 'expectation_sha256': ctx['expectation_sha256'][expectation['id']],
        'view_id': view, 'view_sha256': row['view_sha256'],
        'dependencies': ctx['plan']['sources'] + [d for r in ctx['plan']['relations'] for d in r['dependencies']]}


def expectation(ctx, id):
    value = next((e for e in ctx['plan']['expectations'] if e['id'] == id), None)
    if value is None: raise ValueError('Unknown expectation: '+str(id))
    return value


def relative_file(project, path):
    return project_references.relative(Path(project).resolve(), path)


def pinned(project, path):
    path = Path(path).resolve()
    return {'path': relative_file(project, path), 'sha256': studio.digest(path)}
