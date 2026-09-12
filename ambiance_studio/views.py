"""Saved framing commands over the shared evaluator and scene transactions."""
import hashlib
from pathlib import Path

import studio
from . import scene_runtime, revision_capture
from .project import locations
from .scene_commands import apply_batch
from .scene_transactions import scene_transaction


def add_parsers(sub):
    group = sub.add_parser('view', help='Inspect, author and check saved output framing').add_subparsers(dest='action', required=True)
    q = group.add_parser('inspect'); q.add_argument('id', nargs='?'); q.add_argument('--revision')
    q = group.add_parser('check'); q.add_argument('--view', action='append', dest='views'); q.add_argument('--revision'); q.add_argument('--out', type=Path)
    q = group.add_parser('apply'); q.add_argument('file', type=Path); q.add_argument('--dry-run', action='store_true'); q.add_argument('--expect-sha256')


def inspect(project, id=None, revision=None, check=False, selected=None):
    if revision:
        context = revision_capture.render_context(project, revision)
        scene_path, catalog_path = context['scene'], context['catalog']
    else:
        scene_path, catalog_path = locations(project)
    scene_bytes, catalog_bytes = scene_path.read_bytes(), catalog_path.read_bytes()
    scene = scene_runtime.load_scene_json(scene_bytes)
    catalog = scene_runtime.load_scene_json(catalog_bytes)
    result = scene_runtime.scene_bridge('view-check' if check else 'view-inspect', scene, catalog,
                                        {'id': id, 'views': selected})
    result['inputs'] = {'scene_sha256': hashlib.sha256(scene_bytes).hexdigest(),
                        'catalog_sha256': hashlib.sha256(catalog_bytes).hexdigest(),
                        'views_module_sha256': studio.digest(scene_runtime.ROOT/'editor/views.mjs'),
                        'engine_sha256': studio.digest(scene_runtime.ROOT/'editor/engine.mjs'),
                        'audit_sha256': studio.digest(scene_runtime.ROOT/'editor/audit.mjs')}
    result['revision'] = revision
    if scene_path.read_bytes() != scene_bytes or catalog_path.read_bytes() != catalog_bytes:
        raise ValueError('Scene or catalog changed during view inspection; rerun the check')
    if revision:
        revision_capture.render_context(project, revision)
    return result


def project_summary(project):
    info = inspect(project)
    settings = studio.read(project/'project.json')
    intended = settings.get('intended_views')
    from . import production_plan
    canonical = (project/production_plan.PATH).exists()
    if canonical: intended = [o['view_id'] for o in production_plan.load(project)['outputs']]
    if intended is None:
        intended = [id for id in info['views'] if id != 'authored'] or ['authored']
    errors = []
    if not isinstance(intended, list) or not intended or any(not isinstance(id, str) for id in intended) or len(set(intended)) != len(intended):
        errors.append('intended_views must list unique view IDs')
        intended = []
    errors += [f'Intended view is missing from the scene: {id}' for id in intended if id not in info['views']]
    primary = settings.get('output', {})
    if canonical and intended and intended[0] in info['views']: primary = info['views'][intended[0]]['output']
    if intended and intended[0] in info['views']:
        expected = info['views'][intended[0]]['output']
        if any(primary.get(key) != expected[key] for key in ['width', 'height']):
            errors.append('Primary output summary differs from the first intended view; update the project scope explicitly')
    return {'ok': not errors, 'authored_canvas': info['authored_canvas'], 'intended_views': intended,
            'primary_output': primary, 'views': info['views'], 'errors': errors,
            'intent_source': production_plan.PATH if canonical else 'project.json (legacy)'}


def run(args, project):
    if args.action != 'apply':
        return inspect(project, getattr(args, 'id', None), args.revision,
                       args.action == 'check', getattr(args, 'views', None))
    with scene_transaction(project, args.expect_sha256) as transaction:
        framing = transaction.read_json(args.file, 'framing-input')
        return apply_batch(transaction, {'version': 1, 'operations': [{'op': 'framing', 'value': framing}]},
                           'view-apply', dry_run=args.dry_run)
