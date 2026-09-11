"""Typed finishing dependencies and explicit, reusable look transactions.

The JavaScript engine owns grading/projection semantics. This adapter validates
file identities and remaps declared IDs; it never guesses a rig or copies art.
"""
import copy
import hashlib
import json
from pathlib import Path
import re
import tempfile

import studio
from .scene_authoring import file_dependency

LOOK = 'ambiance-look'
PACKAGE = 'ambiance-finishing-package'
BINDINGS = 'ambiance-finishing-bindings'


def add_parsers(sub):
    group = sub.add_parser('look', help='Inspect and reuse authored finishing').add_subparsers(dest='action', required=True)
    for action in ['inspect', 'check']:
        q = group.add_parser(action); q.add_argument('--time', type=float, default=0); q.add_argument('--out', type=Path)
    q = group.add_parser('apply'); q.add_argument('file', type=Path)
    q.add_argument('--dry-run', action='store_true'); q.add_argument('--expect-sha256')
    q = group.add_parser('export'); q.add_argument('--out', type=Path, required=True); q.add_argument('--include-rig', action='store_true')
    q = group.add_parser('import'); q.add_argument('package', type=Path); q.add_argument('--bindings', type=Path, required=True)
    q.add_argument('--dry-run', action='store_true'); q.add_argument('--expect-sha256'); q.add_argument('--include-rig', action='store_true')


def fields(value, allowed, label):
    if not isinstance(value, dict) or set(value)-set(allowed):
        raise ValueError(f'Invalid {label} fields')


def dependency_roles(scene):
    """Only executable schema fields form closure; arbitrary strings do not."""
    result = {}
    def add(aid, role):
        if not isinstance(aid, str) or not aid: raise ValueError(f'Invalid finishing asset reference ({role})')
        result.setdefault(aid, set()).add(role)
    for layer in scene.get('layers', []): add(layer['asset'], 'layer-image')
    finish = scene.get('finishing') or {}
    by_layer = {layer['id']: layer for layer in scene.get('layers', []) if 'id' in layer}
    for effect in finish.get('illuminations', []):
        for key, role in [('layer', 'paint'), ('receiver', 'base')]:
            if effect[key] in by_layer: add(by_layer[effect[key]]['asset'], 'finishing-illumination-'+role)
    for aid in finish.get('assets', {}): add(aid, 'finishing-grade-target')
    grades = [('global', finish.get('grade', {}))]
    for scope in ['assets', 'groups', 'layers']:
        grades += [(scope, grade) for grade in finish.get(scope, {}).values()]
    for scope, grade in grades:
        if grade.get('mask_asset') is not None: add(grade['mask_asset'], f'finishing-{scope}-grade-mask')
    for scope in ['lights', 'shadows', 'reflections', 'illuminations']:
        for effect in finish.get(scope, []):
            if effect.get('mask_asset') is not None: add(effect['mask_asset'], f'finishing-{scope}-mask')
    return {aid: sorted(roles) for aid, roles in sorted(result.items())}


def used_asset_ids(scene):
    return set(dependency_roles(scene))


def finishing_asset_ids(scene):
    return set(dependency_roles({'finishing': scene.get('finishing')}))


def relationship_ids(finish, scene_bindings=None):
    layers = set(finish.get('layers', {})); groups = set(finish.get('groups', {}))
    for signal in finish.get('signals', []):
        if signal.get('layer') is not None: layers.add(signal['layer'])
    for light in finish.get('lights', []):
        layers.update(light.get('receivers', []))
        if light.get('anchor_layer') is not None: layers.add(light['anchor_layer'])
    for scope in ['shadows', 'reflections']:
        for effect in finish.get(scope, []):
            layers.update([effect['caster'], effect['receiver']])
            if effect.get('elevation') is not None: layers.add(effect['elevation']['layer'])
    for effect in finish.get('illuminations', []):
        layers.update([effect['layer'], effect['receiver']])
    for link in (scene_bindings or {}).get('links', []):
        layers.add(link['target']['layer'])
        if link['source'].get('layer') is not None: layers.add(link['source']['layer'])
    return {'layers': sorted(layers), 'groups': sorted(groups)}


def _rig_fragment(scene, finish, scene_bindings=None):
    """Capture declared roots and attachment ancestors, never nearby objects."""
    required = relationship_ids(finish, scene_bindings); by_layer = {row['id']: row for row in scene['layers']}
    chosen = set(); visiting = set()
    def include(lid):
        if lid in visiting: raise ValueError('Rig attachment cycle')
        if lid in chosen: return
        if lid not in by_layer: raise ValueError(f'Missing rig attachment ancestor: {lid}')
        visiting.add(lid); layer = by_layer[lid]
        if layer.get('attach'): include(layer['attach']['layer'])
        visiting.remove(lid); chosen.add(lid)
    for lid in required['layers']: include(lid)
    groups = set(required['groups']) | {by_layer[lid]['group'] for lid in chosen if by_layer[lid].get('group')}
    if groups-{g['id'] for g in scene['groups']}: raise ValueError('Missing rig group definition')
    return {'version': 1, 'canvas': {key: scene['canvas'][key] for key in ['width', 'height', 'fps', 'loop_seconds']},
            'layers': [copy.deepcopy(layer) for layer in scene['layers'] if layer['id'] in chosen],
            'groups': [copy.deepcopy(group) for group in scene['groups'] if group['id'] in groups]}


def _requirements(finish, rig=None, scene_bindings=None):
    required = relationship_ids(finish, scene_bindings); roles = dependency_roles({'finishing': finish})
    if rig is not None:
        required = {'layers': sorted(layer['id'] for layer in rig['layers']), 'groups': sorted(group['id'] for group in rig['groups'])}
        for layer in rig['layers']: roles[layer['asset']] = sorted(set(roles.get(layer['asset'], [])) | {'rig-image'})
    return required, dict(sorted(roles.items()))


def _validate_rig(rig, finish, scene_bindings=None):
    fields(rig, ['version', 'canvas', 'layers', 'groups'], 'rig package')
    if rig.get('version') != 1: raise ValueError('Unsupported rig package version')
    fields(rig.get('canvas'), ['width', 'height', 'fps', 'loop_seconds'], 'rig canvas')
    for scope in ['layers', 'groups']:
        rows = rig.get(scope)
        if not isinstance(rows, list) or any(not isinstance(row, dict) or not isinstance(row.get('id'), str) for row in rows) or len({row['id'] for row in rows}) != len(rows):
            raise ValueError(f'Invalid or duplicate rig {scope}')
    selected = _rig_fragment(rig, finish, scene_bindings)
    if selected != rig: raise ValueError('Rig must contain exactly finishing roots, their attachment ancestors and required groups')


def apply_batch(doc):
    fields(doc, ['kind', 'version', 'finishing'], 'look document')
    if doc.get('kind') != LOOK or doc.get('version') != 1 or 'finishing' not in doc:
        raise ValueError('Expected ambiance-look version 1 with finishing')
    if doc['finishing'] is not None and not isinstance(doc['finishing'], dict): raise ValueError('Finishing must be an object or null')
    return {'version': 1, 'operations': [{'op': 'finishing', 'value': doc['finishing']}]}


def inspect(project, scene, catalog, time=0):
    from .scene_runtime import scene_bridge
    from .scene_authoring import resolve_batch
    diagnostics = scene_bridge('finishing-check', scene, catalog, {'time': time})
    _, dependencies = resolve_batch(project, scene, catalog,
        {'version': 1, 'operations': [{'op': 'finishing', 'value': scene.get('finishing')}]})
    return {'ok': True, 'finishing': copy.deepcopy(scene.get('finishing')), 'diagnostics': diagnostics,
            'asset_roles': dependency_roles(scene), 'dependencies': dependencies,
            'limits': ['Technical validation and file identity are not visual finishing approval.']}


def _registration_identity(asset):
    mapping = asset.get('registration_mapping')
    if mapping is None: return None
    return {key: copy.deepcopy(mapping.get(key)) for key in ['cell_size', 'reference', 'cels']}


def _asset_identity(asset, roles):
    return {**{key: copy.deepcopy(asset[key]) for key in ['id', 'sha256', 'width', 'height']},
            **({'atlas': copy.deepcopy(asset['atlas'])} if asset.get('atlas') else {}), 'roles': roles,
            **({'registration': _registration_identity(asset)} if asset.get('registration_mapping') else {}),
            **({'rig_metadata': {'pivot': copy.deepcopy(asset.get('pivot')), 'sockets': copy.deepcopy(asset.get('sockets', {}))}} if 'rig-image' in roles else {})}


def _seal(doc):
    return {**doc, 'payload_sha256': studio.encoded_hash(doc)}


def _package_path(path):
    path = Path(path).resolve()
    return path/'look.json' if path.is_dir() else path


def export_package(project, scene, catalog, out, include_rig=False):
    from .scene_authoring import verify_dependencies
    project = Path(project).resolve(); out = Path(out).resolve()
    if out.exists(): raise ValueError('Look export destination exists; choose a fresh directory')
    inspection = inspect(project, scene, catalog)
    finish = copy.deepcopy(scene.get('finishing'))
    if finish is None: raise ValueError('Scene has no finishing configuration to export')
    scene_bindings = copy.deepcopy(scene.get('bindings'))
    rig = _rig_fragment(scene, finish, scene_bindings) if include_rig else None
    requirements, roles = _requirements(finish, rig, scene_bindings); by_id = {a['id']: a for a in catalog['assets']}
    requirements['assets'] = [_asset_identity(by_id[aid], asset_roles) for aid, asset_roles in roles.items()]
    by_layer = {layer['id']: layer for layer in scene['layers']}
    source = {'scene_sha256': studio.encoded_hash(scene), 'catalog_sha256': studio.encoded_hash(catalog),
              'picture_seconds': scene['canvas']['loop_seconds'],
              'layer_art': [{'layer': lid, **_asset_identity(by_id[by_layer[lid]['asset']], ['source-layer-art'])} for lid in requirements['layers']]}
    doc = _seal({'kind': PACKAGE, 'version': 1, 'finishing': finish, 'requires': requirements, 'source': source,
                 **({'rig': rig} if rig is not None else {}), **({'scene_bindings': scene_bindings} if scene_bindings is not None else {})})
    bindings = {'kind': BINDINGS, 'version': 1, 'layers': {key: None for key in requirements['layers']},
                'groups': {key: None for key in requirements['groups']}, 'assets': {row['id']: None for row in requirements['assets']}}
    # Pin current scene/config/catalog as well as prepared dependencies. A caller
    # passing old parsed data cannot label it as the current project's export.
    conf_file = project/'ambiance-project.json'; conf = studio.read(conf_file)
    controls = [(conf_file, 'look-export-project'), (studio.inside(project, conf['scene']), 'look-export-scene'),
                (studio.inside(project, conf['catalog']), 'look-export-catalog')]
    dependencies = inspection['dependencies']+[file_dependency(path, role) for path, role in controls]
    if studio.read(controls[1][0]) != scene or studio.read(controls[2][0]) != catalog: raise ValueError('Scene/catalog changed before look export')
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.look-', dir=out.parent) as temp:
        stage = Path(temp)/'package'; stage.mkdir()
        studio.write(stage/'look.json', doc); studio.write(stage/'bindings-template.json', bindings)
        report = {'kind': 'ambiance-look-export', 'version': 1, 'package_sha256': studio.digest(stage/'look.json'),
                  'dependencies': dependencies, 'source': source, 'copied_art': False, 'includes_rig': include_rig,
                  'limits': ['Look-only layer and grade-target bindings may select different art. Masks and included rig images require exact version identities.',
                             'Included rigs restore source normalized placement, clock and relative painter order among explicit bound targets; target camera remains unchanged.']}
        studio.write(stage/'report.json', report)
        verify_dependencies(project, dependencies)
        # Share the tested no-replace publication primitive; a reservation plus
        # replace could overwrite another actor's concurrently swapped directory.
        from .edge_quality import promote_exclusive
        promote_exclusive(stage,out)
    return {'ok': True, 'directory': str(out), 'package': str(out/'look.json'), 'bindings_template': str(out/'bindings-template.json'),
            'resolved_path': str(out), 'path_base': 'absolute', 'package_sha256': studio.digest(out/'look.json'), 'dependencies': dependencies, 'includes_rig': include_rig}


def import_batch(project, scene, catalog, package, bindings, include_rig=False):
    from .scene_runtime import scene_bridge
    from .scene_authoring import verify_dependencies
    package_path = _package_path(package); bindings_path = Path(bindings).resolve()
    extra = [file_dependency(package_path, 'look-package'), file_dependency(bindings_path, 'look-bindings')]
    doc = studio.read(package_path); fields(doc, ['kind', 'version', 'finishing', 'requires', 'source', 'payload_sha256', 'rig', 'scene_bindings'], 'look package')
    if doc.get('kind') != PACKAGE or doc.get('version') != 1 or not isinstance(doc.get('finishing'), dict): raise ValueError('Expected ambiance-finishing-package version 1')
    if doc.get('payload_sha256') != studio.encoded_hash({key: value for key, value in doc.items() if key != 'payload_sha256'}): raise ValueError('Look package integrity changed')
    rig = doc.get('rig'); scene_bindings = doc.get('scene_bindings')
    if 'rig' in doc:
        if not include_rig: raise ValueError('Package includes geometry/cadence; import requires explicit --include-rig')
        _validate_rig(rig, doc['finishing'], scene_bindings)
        if rig['canvas'] != {key: scene['canvas'][key] for key in ['width', 'height', 'fps', 'loop_seconds']}: raise ValueError('Rig import requires identical canvas dimensions, fps and picture loop')
    elif include_rig: raise ValueError('Package contains no rig; omit --include-rig or export a rig package')
    expected, roles = _requirements(doc['finishing'], rig, scene_bindings)
    requirements = doc['requires']; fields(requirements, ['layers', 'groups', 'assets'], 'package requirements')
    if any(requirements.get(key) != value for key, value in expected.items()): raise ValueError('Package relationship requirements differ from finishing')
    asset_records = requirements.get('assets')
    if not isinstance(asset_records, list) or any(not isinstance(row, dict) or not isinstance(row.get('id'), str) for row in asset_records) or len({row.get('id') for row in asset_records}) != len(asset_records) or {row.get('id') for row in asset_records} != set(roles): raise ValueError('Package asset requirements differ from finishing')
    for record in asset_records:
        fields(record, ['id', 'sha256', 'width', 'height', 'atlas', 'roles', 'rig_metadata', 'registration'], 'package asset identity')
        if record.get('roles') != roles[record['id']] or not re.fullmatch('[a-f0-9]{64}', record.get('sha256', '')) or any(type(record.get(k)) is not int or record[k] <= 0 for k in ['width', 'height']): raise ValueError('Invalid package asset identity/roles')
        if 'rig-image' in record['roles']:
            fields(record.get('rig_metadata'), ['pivot', 'sockets'], 'rig asset metadata')
            if set(record['rig_metadata']) != {'pivot', 'sockets'}: raise ValueError('Rig asset metadata requires pivot and sockets')
        elif 'rig_metadata' in record: raise ValueError('Rig metadata is only valid for rig image dependencies')
    binding = studio.read(bindings_path); fields(binding, ['kind', 'version', 'layers', 'groups', 'assets'], 'look bindings')
    if binding.get('kind') != BINDINGS or binding.get('version') != 1: raise ValueError('Expected ambiance-finishing-bindings version 1')
    targets = {'layers': {layer['id'] for layer in scene['layers']}, 'groups': {group['id'] for group in scene['groups']}, 'assets': {a['id'] for a in catalog['assets']}}
    keys = {**expected, 'assets': sorted(roles)}
    for scope, names in keys.items():
        remap = binding.get(scope)
        if not isinstance(remap, dict) or set(remap) != set(names) or any(not isinstance(v, str) or v not in targets[scope] for v in remap.values()): raise ValueError(f'Complete explicit {scope} bindings to existing targets are required')
        if len(set(remap.values())) != len(remap): raise ValueError(f'Colliding {scope} bindings are not supported')
    by_asset = {a['id']: a for a in catalog['assets']}; substitutions = []
    for record in asset_records:
        target = by_asset[binding['assets'][record['id']]]
        mask = any(role.endswith('-mask') for role in record['roles'])
        identical = all(record.get(key) == target.get(key) for key in ['sha256', 'width', 'height', 'atlas'])
        if mask and (not identical or ('registration' in record and record['registration'] != _registration_identity(target))): raise ValueError(f'Mask version differs for binding {record["id"]} -> {target["id"]}')
        if 'rig-image' in record['roles'] and (not identical or ('registration' in record and record['registration'] != _registration_identity(target)) or record['rig_metadata'] != {'pivot': target.get('pivot'), 'sockets': target.get('sockets', {})}): raise ValueError(f'Rig image version/cell layout/socket metadata differs for binding {record["id"]} -> {target["id"]}')
        if not identical: substitutions.append({'source_asset': record['id'], 'target_asset': target['id'], 'role': 'grade-target', 'source_sha256': record['sha256'], 'target_sha256': target['sha256']})
    art = {row['layer']: row for row in doc['source']['layer_art']}
    target_layers = {row['id']: row for row in scene['layers']}
    rig_sources = {row['id']: row for row in rig['layers']} if rig is not None else {}
    for effect in doc['finishing'].get('illuminations', []):
        for name in [effect['layer'], effect['receiver']]:
            target = by_asset[binding['assets'][rig_sources[name]['asset']]] if rig is not None else by_asset[target_layers[binding['layers'][name]]['asset']]
            if name not in art or any(art[name].get(key) != target.get(key) for key in ['sha256', 'width', 'height', 'atlas']) or ('registration' in art[name] and art[name]['registration'] != _registration_identity(target)):
                raise ValueError(f'Painted illumination base/contribution version differs: {name}')
    result = copy.deepcopy(doc['finishing'])
    for scope in ['assets', 'layers', 'groups']:
        if scope in result: result[scope] = {binding[scope][key]: value for key, value in result[scope].items()}
    grades = [result.get('grade', {})]+[grade for scope in ['assets', 'groups', 'layers'] for grade in result.get(scope, {}).values()]
    for grade in grades:
        if grade.get('mask_asset') is not None: grade['mask_asset'] = binding['assets'][grade['mask_asset']]
    for signal in result.get('signals', []):
        if signal.get('layer') is not None: signal['layer'] = binding['layers'][signal['layer']]
    for light in result.get('lights', []):
        light['receivers'] = [binding['layers'][key] for key in light['receivers']]
        if light.get('anchor_layer') is not None: light['anchor_layer'] = binding['layers'][light['anchor_layer']]
    for scope in ['shadows', 'reflections']:
        for effect in result.get(scope, []):
            for key in ['caster', 'receiver']: effect[key] = binding['layers'][effect[key]]
            if effect.get('elevation') is not None: effect['elevation']['layer'] = binding['layers'][effect['elevation']['layer']]
    for scope in ['lights', 'shadows', 'reflections', 'illuminations']:
        for effect in result.get(scope, []):
            if effect.get('mask_asset') is not None: effect['mask_asset'] = binding['assets'][effect['mask_asset']]
    for effect in result.get('illuminations', []):
        effect['layer'] = binding['layers'][effect['layer']]
        effect['receiver'] = binding['layers'][effect['receiver']]
    rebound = copy.deepcopy(scene_bindings)
    if rebound is not None:
        for link in rebound['links']:
            link['target']['layer'] = binding['layers'][link['target']['layer']]
            if link['source'].get('layer') is not None: link['source']['layer'] = binding['layers'][link['source']['layer']]
    operations = []; rig_report = None
    if rig is not None:
        for source_group in rig['groups']:
            group = copy.deepcopy(source_group); gid = binding['groups'][group.pop('id')]
            operations.append({'op': 'group', 'id': gid, 'value': group})
        for source_layer in rig['layers']:
            layer = copy.deepcopy(source_layer); layer['id'] = binding['layers'][layer['id']]; layer['asset'] = binding['assets'][layer['asset']]
            if layer.get('group'): layer['group'] = binding['groups'][layer['group']]
            if layer.get('attach'): layer['attach']['layer'] = binding['layers'][layer['attach']['layer']]
            operations.append({'op': 'replace', 'layer': layer['id'], 'value': layer})
        before_order = [layer['id'] for layer in scene['layers']]; bound = set(binding['layers'].values())
        source_order = [binding['layers'][layer['id']] for layer in rig['layers']]; ordered = iter(source_order)
        after_order = [next(ordered) if lid in bound else lid for lid in before_order]
        operations.append({'op': 'order', 'layers': after_order})
        rig_report = {'restores_source_normalized_placement': True, 'restores_source_motion_and_cel_timing': True,
                      'target_camera_unchanged': True, 'replaced_layers': source_order,
                      'replaced_groups': list(binding['groups'].values()), 'paint_order_before': before_order, 'paint_order_after': after_order,
                      'unbound_layers_with_replaced_group': [layer['id'] for layer in scene['layers'] if layer['id'] not in bound and layer.get('group') in set(binding['groups'].values())]}
    operations.append({'op': 'finishing', 'value': result})
    if rebound is not None: operations.append({'op': 'bindings', 'value': rebound})
    batch = {'version': 1, 'operations': operations}
    candidate = scene_bridge('apply', scene, catalog, {'batch': batch})
    diagnostics = scene_bridge('finishing-check', candidate, catalog, {'time': 0})
    verify_dependencies(project, extra)
    return (batch, extra,
            {'source_package': str(package_path), 'package_sha256': extra[0]['sha256'], 'bindings': binding,
             'asset_substitutions': substitutions, 'diagnostics': diagnostics,
             'replaces_finishing': True, 'copied_art': False, 'rig': rig_report})
