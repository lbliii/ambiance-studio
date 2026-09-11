"""Identity-bound activity evidence; sampled state, raster and observation stay separate."""
import hashlib
import json
import math
from pathlib import Path
import re

from .errors import CommandError
from .project import locations
from .scene_runtime import ROOT, require_node, scene_bridge
from .rendering import _json_command


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fields(value, allowed, label):
    if not isinstance(value, dict) or set(value) - set(allowed):
        raise ValueError(f'Invalid or unknown {label} fields')


def add_parsers(group):
    p = group.add_parser('activity', help='Measure per-view state and optional bounded raster contribution')
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--view', action='append', default=[])
    p.add_argument('--layer', action='append', default=[])
    p.add_argument('--action-id', action='append', default=[])
    p.add_argument('--revision')
    p.add_argument('--start-frame', type=int, default=0)
    p.add_argument('--frames', type=int)
    p.add_argument('--stride', type=int, default=1)
    p.add_argument('--long-edge', type=int, default=320)
    p.add_argument('--raster', action='store_true')
    p.add_argument('--compare', type=Path)
    p.add_argument('--resume', action='store_true')
    p = group.add_parser('activity-review', help='Record an actual observation of an exact normal-speed proof')
    p.add_argument('file', type=Path)
    p.add_argument('--out', type=Path, required=True)


def actions_from_plan(plan):
    elements = {e['id']: e for e in plan.get('elements', [])}
    result = []
    for action in plan.get('actions', []):
        element = elements[action['element_id']]
        result.append({'id': action['id'], 'element_id': element['id'], 'description': action['description'],
                       'layers': action.get('layer_ids', element.get('realization', {}).get('layer_ids', [])),
                       'views': [t['view_id'] for t in action['targets']], 'targets': action['targets'],
                       'kind': element.get('kind'), 'motion_role': element.get('motion_role'),
                       'cadence': element.get('cadence'), 'method': action['method'], 'timing': action.get('timing')})
    return result


def load_actions(project, revision=None):
    # The plan owner validates the sole semantic source. An absent optional plan
    # is different from a malformed plan, which must not be silently ignored.
    if not revision and not (Path(project)/'plans/production-plan.json').exists():
        return [], None
    from . import production_plan
    context = production_plan.load_context(project, revision=revision)
    if not context or context.get('plan') is None:
        return [], None
    return actions_from_plan(context['plan']), {k: str(v) if isinstance(v, Path) else v
                                               for k, v in context.items() if k != 'plan'}


def variants_from_recipe(path, scene, catalog):
    recipe = json.loads(Path(path).read_text())
    fields(recipe, ['version', 'strength', 'cadence'], 'activity comparison')
    if recipe.get('version') != 1:
        raise ValueError('Activity comparison requires version 1')
    variants = []
    for experiment in ['strength', 'cadence']:
        rows = recipe.get(experiment, [])
        if not isinstance(rows, list) or len(rows) not in [0, 2]:
            raise ValueError(f'{experiment} requires exactly two explicit comparison batches')
        for row in rows:
            fields(row, ['id', 'batch'], 'comparison variant')
            identifier = row.get('id', '')
            if not re.fullmatch(r'[a-z][a-z0-9_-]{0,31}', identifier) or identifier == 'target' or any(v['id'] == identifier for v in variants):
                raise ValueError('Comparison IDs must be unique safe IDs distinct from target')
            batch = row['batch']
            if experiment == 'cadence':
                for op in batch.get('operations', []):
                    values = op.get('values', {})
                    if op.get('op') != 'set' or op.get('unset') or set(values) - {'cycle_seconds', 'phase_frames', 'motion', 'tracks'}:
                        raise ValueError('Cadence comparisons may change clocks, phase and track key times only')
                    original = next((l for l in scene['layers'] if l['id'] == op.get('layer')), {})
                    if 'motion' in values and any(values['motion'].get(k, 0) != original.get('motion', {}).get(k, 0) for k in ['x_amplitude', 'y_amplitude', 'rotation_amplitude']):
                        raise ValueError('Cadence comparisons must preserve motion amplitudes')
                    if 'tracks' in values:
                        if set(values['tracks']) != set(original.get('tracks', {})):
                            raise ValueError('Cadence comparisons must preserve track channels')
                        for channel, track in values['tracks'].items():
                            prior = original['tracks'][channel]
                            if track.get('interpolation') != prior['interpolation'] or {json.dumps(k[1]) for k in track['keys']} != {json.dumps(k[1]) for k in prior['keys']}:
                                raise ValueError('Cadence comparisons must preserve track values/interpolation')
            if experiment == 'strength':
                # Amplitude/size-only experiments cannot silently alter cadence.
                for op in batch.get('operations', []):
                    if op.get('op') != 'set' or op.get('unset') or set(op.get('values', {})) - {'motion', 'width', 'height', 'scale'}:
                        raise ValueError('Strength comparisons may set motion amplitudes, width, height or scale only')
                    if 'motion' in op.get('values', {}):
                        original = next((l for l in scene['layers'] if l['id'] == op.get('layer')), {}).get('motion', {})
                        candidate = op['values']['motion']
                        if not isinstance(candidate, dict) or candidate.get('cycles') != original.get('cycles') or candidate.get('phase') != original.get('phase'):
                            raise ValueError('Strength comparisons must preserve motion cycles and phase')
            candidate = scene_bridge('apply', scene, catalog, {'batch': batch})
            if candidate['canvas'] != scene['canvas'] or candidate.get('framing') != scene.get('framing'):
                raise ValueError('Comparisons must preserve picture clock and exact view identity')
            variants.append({'id': identifier, 'experiment': experiment, 'scene': candidate})
    return variants


def verify_receipt(path):
    path = Path(path).resolve()
    if path.is_dir(): path /= 'activity-report.json'
    report = json.loads(path.read_text())
    if report.get('kind') != 'ambiance-scene-activity' or report.get('schema_version') != 1 or report.get('ok') is not True:
        raise ValueError('Expected a completed ambiance-scene-activity schema_version 1 receipt')
    paths = set()
    for artifact in report['artifacts']:
        relative = artifact['path']
        file = (path.parent / relative).resolve()
        if not file.is_relative_to(path.parent) or Path(relative).is_absolute() or relative in paths:
            raise ValueError('Invalid or duplicate activity artifact path')
        paths.add(relative)
        if not file.is_file() or file.stat().st_size != artifact['bytes'] or digest(file) != artifact['sha256']:
            raise ValueError(f'Activity artifact changed or missing: {relative}')
    required = {'scene.snapshot.json', 'catalog.snapshot.json', 'state.json', 'raster.json', 'request.json'}
    if not required <= paths or report['raster_performed'] and 'index.html' not in paths:
        raise ValueError('Activity receipt is missing required artifacts')
    if digest(path.parent/'scene.snapshot.json') != report['scene_sha256'] or digest(path.parent/'catalog.snapshot.json') != report['catalog_sha256']:
        raise ValueError('Activity snapshot identity does not match receipt')
    return report


def record_observation(source, out):
    doc = json.loads(Path(source).read_text())
    fields(doc, ['kind', 'schema_version', 'receipt', 'receipt_sha256', 'action_id', 'view_id', 'status', 'observer',
                 'observed_level', 'note', 'playback_rate', 'display_width', 'display_height', 'watched_start_seconds', 'watched_end_seconds'], 'activity observation')
    if doc.get('kind') != 'ambiance-activity-observation' or doc.get('schema_version') != 1:
        raise ValueError('Expected ambiance-activity-observation schema_version 1')
    receipt_path = Path(doc['receipt']).resolve()
    report = verify_receipt(receipt_path)
    if digest(receipt_path) != doc['receipt_sha256'] or not report['raster_performed']:
        raise ValueError('Observation requires the exact completed raster receipt')
    view = next((v for v in report['views'] if v['view']['id'] == doc['view_id']), None)
    action = next((a for a in report['actions'] if a['id'] == doc['action_id']), None)
    if not view or not action or action.get('views') and doc['view_id'] not in action['views']:
        raise ValueError('Observation action/view is not covered by this proof')
    if doc.get('status') not in ['unreviewed', 'revise', 'meets-direction']:
        raise ValueError('Observation status must be unreviewed, revise or meets-direction')
    level = doc.get('observed_level')
    if level is not None and (type(level) is not int or not 0 <= level <= 4):
        raise ValueError('Observed level must be null or an authored 0–4 judgment')
    if doc['status'] != 'unreviewed':
        if not isinstance(doc.get('observer'), str) or not doc['observer'].strip() or not isinstance(doc.get('note'), str) or not doc['note'].strip():
            raise ValueError('An actual observation requires a named observer and concrete note')
        if doc.get('playback_rate') != 1 or doc.get('display_width') != view['output']['width'] or doc.get('display_height') != view['output']['height']:
            raise ValueError('Observe at normal speed and the exact proof display resolution')
        clock = report['clock']; start = clock['start_frame']/clock['fps']; end = start + clock['frames']/clock['fps']
        for key in ['watched_start_seconds', 'watched_end_seconds']:
            if type(doc.get(key)) not in [int, float] or not math.isfinite(doc[key]): raise ValueError('Watched bounds must be finite seconds')
        if not start <= doc['watched_start_seconds'] < doc['watched_end_seconds'] <= end:
            raise ValueError('Watched bounds must lie inside the exact saved proof segment')
    elif level is not None:
        raise ValueError('Unreviewed observations cannot contain an observed level')
    out = Path(out).resolve()
    if out.exists(): raise ValueError('Observation output exists; choose a fresh file')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, allow_nan=False)+'\n')
    return {'ok': True, 'observation': str(out), 'sha256': digest(out), 'status': doc['status'],
            'scope': 'Recorded observer statement; no automated artistic certification'}


def run(args, project):
    if args.action == 'activity-review': return record_observation(args.file, args.out)
    from .rendering import _context
    context = _context(project, args.revision)
    scene_path, catalog_path = Path(context['scene']), Path(context['catalog'])
    scene, catalog = json.loads(scene_path.read_text()), json.loads(catalog_path.read_text())
    actions, plan = load_actions(project, args.revision)
    if args.action_id:
        if set(args.action_id) - {a['id'] for a in actions}: raise ValueError('Unknown semantic --action-id')
        actions = [a for a in actions if a['id'] in args.action_id]
    layers = {l['id'] for l in scene['layers']}
    if set(args.layer) - layers: raise ValueError('Unknown --layer in selected scene')
    for layer in args.layer:
        actions.append({'id': 'layer-'+layer, 'layers': [layer], 'views': [], 'targets': [], 'cadence': None, 'semantic': False})
    if len({a['id'] for a in actions}) != len(actions): raise ValueError('Duplicate action ID; remove repeated filters')
    if len(actions) > 64: raise ValueError('Activity summary is limited to 64 actions; select --action-id filters')
    for action in actions:
        if not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}', action['id']): raise ValueError('Activity action IDs require a safe lowercase identifier')
        if not set(action['layers']) <= layers: raise ValueError(f'Action {action["id"]} references unrealized layers')
    if args.compare and not args.raster: raise ValueError('--compare requires --raster')
    frames = args.frames if args.frames is not None else round(scene['canvas']['fps'] * scene['canvas']['loop_seconds'])
    request = {'project': str(Path(project).resolve()), 'out': str(args.out.resolve()), 'scene_path': str(scene_path), 'catalog_path': str(catalog_path),
               'scene_sha256': digest(scene_path), 'catalog_sha256': digest(catalog_path), 'plan': plan,
               'revision': {k:context[k] for k in ['revision_id', 'manifest_sha256'] if k in context} or None,
               'actions': actions, 'views': [{'id': v} for v in (args.view or ['authored'])], 'long_edge': args.long_edge,
               'start_frame': args.start_frame, 'frames': frames, 'stride': args.stride, 'raster': args.raster,
               'variants': variants_from_recipe(args.compare, scene, catalog) if args.compare else []}
    if args.out.exists():
        if not args.resume: raise ValueError('Activity output exists; use --resume for an unchanged completed run or a fresh directory')
        if not (args.out/'activity-report.json').exists():
            if not (args.out/'request.json').is_file() or json.loads((args.out/'request.json').read_text()) != request:
                raise ValueError('Partial activity request missing or changed; choose a fresh output directory')
            return _json_command([require_node(), ROOT/'tools/activity-scene.mjs'], {**request, 'resume': True})
        report = verify_receipt(args.out)
        if json.loads((args.out/'request.json').read_text()) != request:
            raise ValueError('Activity resume inputs/options changed; choose a fresh output directory')
        for asset in report['source_assets']:
            if digest(asset['path']) != asset['sha256']: raise ValueError('Activity source changed; cannot resume')
        return {'ok': True, 'resumed': True, 'report': str(args.out.resolve()/'activity-report.json'), 'summary': report['summary']}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    return _json_command([require_node(), ROOT/'tools/activity-scene.mjs'], request)
