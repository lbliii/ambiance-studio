"""Contained scene instances and explicit, conservative mc/1 version adoption.

Immutable packages supply authored state. Ordinary generated scene layers are
derived output with drift checks, not another editable model definition.
"""
import copy
import json
from pathlib import Path
import re

import studio
from . import model_package, scene_authoring
from .errors import CommandError
from .file_identity import digest
from .project import locations
from .record_contracts import fields, identifier
from .scene_runtime import scene_bridge
from .scene_transactions import scene_transaction

FORMAT = 'ambiance-model-instances'
RECIPE = 'ambiance-model-instance-operations'
REST = {'schema_version': 1, 'pose_id': 'rest', 'controls': [], 'variants': []}


def runtime_numbers(value):
    """Persist JSON numbers as the scene bridge will return them on reopen.

    This is scene-data normalization, not another cross-language hash. Seals
    and fingerprints continue to use studio.encoded_hash unchanged.
    """
    if isinstance(value, dict): return {k: runtime_numbers(v) for k, v in value.items()}
    if isinstance(value, list): return [runtime_numbers(v) for v in value]
    if isinstance(value, float) and value.is_integer(): return int(value)
    return value


def sha(value):
    if not isinstance(value, str) or not re.fullmatch('[a-f0-9]{64}', value):
        raise ValueError('Expected exact SHA-256')
    return value


def records(scene):
    container = scene.get('model_instances', {'format': FORMAT, 'schema_version': 1, 'instances': []})
    fields(container, ['format', 'schema_version', 'instances'], 'model instances')
    if container.get('format') != FORMAT or container.get('schema_version') != 1 or not isinstance(container.get('instances'), list):
        raise ValueError('Unsupported scene model instance contract')
    ids = [identifier(r['instance_id']) for r in container['instances']]
    if len(set(ids)) != len(ids): raise ValueError('Duplicate scene instance IDs')
    return container['instances']


def managed_subject(scene, catalog, record):
    """Selected leaves, exact art, local writers and external contacts only."""
    owned = {r['layer_id'] for r in record['mapping']}
    selected = [l for l in scene['layers'] if l['id'] in owned]
    if [l['id'] for l in selected] != [r['layer_id'] for r in record['mapping']]:
        raise ValueError('Managed layers missing, duplicated or reordered')
    positions = [i for i, l in enumerate(scene['layers']) if l['id'] in owned]
    if positions != list(range(min(positions), min(positions)+len(positions))):
        raise ValueError('Managed instance paint block was split')
    assets = {l['asset'] for l in selected}
    finishing = scene.get('finishing', {})
    signals = [s for s in finishing.get('signals', []) if s.get('layer') in owned or s['id'] in record['relationships']['signals']]
    signal_ids = {s['id'] for s in signals}
    bindings = [b for b in scene.get('bindings', {}).get('links', []) if b['source'].get('signal') in signal_ids or b['target'].get('layer') in owned or b['id'] in record['relationships']['bindings']]
    contacts = record['relationships']['receivers']
    contact_layers = {r[k] for r in contacts for k in ['layer', 'receiver']}
    if record['mount']: contact_layers.add(record['mount']['layer'])
    return {'instance': {k: v for k, v in record.items() if k != 'managed_sha256'},
            'layers': selected, 'assets': sorted([a for a in catalog['assets'] if a['id'] in assets], key=lambda a: a['id']),
            'signals': signals, 'bindings': bindings,
            'illuminations': [i for i in finishing.get('illuminations', []) if i['layer'] in owned or i['id'] in {r['illumination'] for r in contacts}],
            'contacts': [l for l in scene['layers'] if l['id'] in contact_layers or l.get('attach', {}).get('layer') in owned and l['id'] not in owned]}


def fingerprint(scene, catalog, record):
    # Use the studio's existing canonical record hash, never a JS JSON hash.
    return studio.encoded_hash(managed_subject(scene, catalog, record))


def verify_managed(scene, catalog, record):
    if fingerprint(scene, catalog, record) != record.get('managed_sha256'):
        raise ValueError('Unmanaged model layer, metadata, art or contact drift: '+record['instance_id'])


def open_pin(project, pin):
    fields(pin, ['package', 'sha256', 'definition'], 'instance pin')
    path = studio.inside(project, pin['package'])
    if path.name != 'model-package.json' or digest(path) != sha(pin['sha256']): raise ValueError('Changed exact instance package pin')
    package, manifest, closure, root = model_package.open_package(path.parent)
    if manifest['definition'] != pin['definition']: raise ValueError('Changed exact instance definition pin')
    return package, manifest, closure, root


def interface(closure, root):
    """This adoption slice allows metadata/default revisions, not interface edits."""
    def clean(value):
        if isinstance(value, list): return [clean(v) for v in value]
        if isinstance(value, dict): return {k: clean(v) for k, v in value.items() if not k.startswith('_')}
        return value
    def definition(file):
        model = closure.models[file]
        result = {k: clean(model[k]) for k in ['model_id', 'kind', 'local_frame', 'root_part_id', 'drawings', 'parts', 'paint_order']}
        for key in ['sockets', 'variant_sets']: result[key] = clean(model.get(key, []))
        result['controls'] = [{k: clean(v) for k, v in c.items() if k != 'default'} for c in model.get('controls', [])]
        return result
    return definition(root)


def adoption_preview(old, new_interface, operation):
    conflicts = []
    for key in sorted(set(old['interface']) | set(new_interface)):
        if old['interface'].get(key) != new_interface.get(key):
            conflicts.append({'field': key, 'reason': 'Changed model interface; explicit remapping is outside this adoption subset'})
    state = copy.deepcopy(old['state']); reset = []; retained = []
    for group, identity_keys in [('controls', ['model_path', 'control_id']), ('variants', ['model_path', 'variant_set_id'])]:
        requested = operation.get('reset_'+group, [])
        if not isinstance(requested, list): raise ValueError('Reset selections must be arrays')
        for row in requested: fields(row, identity_keys, 'reset identity')
        identities = [tuple(json.dumps(row[k], separators=(',', ':')) for k in identity_keys) for row in requested]
        if len(set(identities)) != len(identities): raise ValueError('Duplicate reset identity')
        present = {tuple(json.dumps(row[k], separators=(',', ':')) for k in identity_keys) for row in state[group]}
        if set(identities)-present: raise ValueError('Reset must identify an existing explicit override')
        kept = []
        for row in state[group]:
            key = tuple(json.dumps(row[k], separators=(',', ':')) for k in identity_keys)
            (reset if key in identities else retained).append({'kind': group, **row})
            if key not in identities: kept.append(row)
        state[group] = kept
    return state, {'retained': retained, 'reset': reset, 'conflicts': conflicts,
                   'contacts': {'retained': old['relationships']['receivers'], 'mount': old['mount']},
                   'remapped': [], 'applicable': not conflicts}


def dependencies(package, manifest):
    result = [scene_authoring.file_dependency(package/'model-package.json', 'model-package')]
    for name, expected in manifest['files'].items():
        row = scene_authoring.file_dependency(package/'source'/name, 'model-source')
        if row['sha256'] != expected: raise ValueError('Model package changed during resolution')
        result.append(row)
    return result


def inspect(project, instance_id=None):
    scene_path, catalog_path = locations(project)
    inputs = [scene_authoring.file_dependency(p, 'model-inspect') for p in [Path(project)/'ambiance-project.json', scene_path, catalog_path]]
    scene, catalog = studio.read(scene_path), studio.read(catalog_path)
    found = records(scene)
    if instance_id is not None:
        found = [r for r in found if r['instance_id'] == instance_id]
        if not found: raise ValueError('Unknown model instance: '+instance_id)
    from .model_evidence import model_references
    model_references(project, scene, catalog)
    scene_authoring.verify_dependencies(project, inputs)
    return {'scene_sha256': inputs[1]['sha256'], 'instances': found, 'acceptance': 'not established'}


def apply(project, recipe_file, *, dry_run=False):
    project = Path(project).resolve(); recipe_file = Path(recipe_file).resolve()
    # Read inside the lock and pin the exact recipe; expected scene is mandatory.
    with scene_transaction(project) as transaction:
        recipe = transaction.read_json(recipe_file, 'model-instance-recipe')
        fields(recipe, ['format', 'schema_version', 'expected_scene_sha256', 'operations'], 'model operation recipe')
        if recipe.get('format') != RECIPE or recipe.get('schema_version') != 1: raise ValueError('Expected model instance operations schema_version 1')
        if sha(recipe['expected_scene_sha256']) != transaction.previous_sha256:
            raise CommandError('Scene changed since expected SHA-256; no model operation was saved.', 'stale_input', 2)
        operations = recipe.get('operations')
        if not isinstance(operations, list) or not 1 <= len(operations) <= 64: raise ValueError('Model recipe needs 1–64 operations')
        ids = [identifier(op['instance_id']) for op in operations]
        if len(set(ids)) != len(ids): raise ValueError('Each instance may appear once per batch; duplicate operation rejected')
        scene, catalog = copy.deepcopy(transaction.scene), copy.deepcopy(transaction.catalog)
        current = records(scene)
        from .model_evidence import model_references
        model_references(project, scene, catalog)
        pinned = []
        for record in current:
            verify_managed(scene, catalog, record)
            package, manifest, _, _ = open_pin(project, record['pin'])
            pinned.extend(dependencies(package, manifest))
        generation = project/'.ambiance/model-generations'/transaction.dependencies[0]['sha256']
        packages = {}; previews = []
        for operation in operations:
            action = operation.get('op'); instance_id = operation['instance_id']
            common = ['op', 'instance_id']
            if action == 'place': allowed = common+['package', 'package_sha256', 'state', 'placement', 'mount', 'order', 'receivers']
            elif action == 'update': allowed = common+['expected_pin', 'expected_managed_sha256', 'state', 'placement', 'mount', 'order', 'receivers']
            elif action == 'adopt': allowed = common+['expected_pin', 'expected_managed_sha256', 'package', 'package_sha256', 'reset_controls', 'reset_variants']
            else: raise ValueError('Unknown model instance operation: '+str(action))
            fields(operation, allowed, 'model '+action)
            old = next((r for r in current if r['instance_id'] == instance_id), None)
            if action == 'place':
                if old: raise ValueError('Occupied instance ID; retry cannot duplicate: '+instance_id)
            else:
                if not old: raise ValueError('Unknown model instance: '+instance_id)
                if operation['expected_pin'] != old['pin'] or sha(operation['expected_managed_sha256']) != old['managed_sha256']:
                    raise ValueError('Previous exact pin or managed-layer fingerprint differs')
            if action == 'update':
                package, manifest, closure, root = open_pin(project, old['pin']); pin = old['pin']
            else:
                package = Path(operation['package'])
                if not package.is_absolute(): package = recipe_file.parent/package
                package, manifest, closure, root = model_package.open_package(package)
                package_hash = sha(operation['package_sha256'])
                if digest(package/'model-package.json') != package_hash: raise ValueError('Requested package pin differs')
                # Reuse an already contained exact package; otherwise stage once.
                reused = next((r['pin'] for r in current if r['pin']['sha256'] == package_hash), None)
                target = generation/'packages'/package_hash
                pin = reused or {'package': (target/'model-package.json').relative_to(project).as_posix(), 'sha256': package_hash, 'definition': manifest['definition']}
                if not reused: packages[package_hash] = (package, manifest)
            pinned.extend(dependencies(package, manifest))
            contract = interface(closure, root)
            preview = None
            if action == 'adopt':
                if old['pin']['definition']['model_id'] != manifest['definition']['model_id']: raise ValueError('Adoption requires the same model family')
                if old['pin']['definition']['version'] == manifest['definition']['version']:
                    raise ValueError('Adoption requires a new immutable version; never change bytes under an existing version')
                state, preview = adoption_preview(old, contract, operation)
                if preview['conflicts']:
                    if dry_run: return {'dry_run': True, 'applicable': False, 'previous_sha256': transaction.previous_sha256,
                                        'previews': [*previews, {'instance_id': instance_id, 'adoption': preview}], 'saved': False}
                    raise ValueError('Adoption interface conflicts: '+', '.join(r['field'] for r in preview['conflicts']))
            else: state = copy.deepcopy(operation.get('state', old['state'] if old else REST))
            resolved = model_package.bridge(closure, root, state=state)
            if preview is not None:
                preview['effective_controls'] = {'before': old['effective_controls'], 'after': resolved['effective_controls']}
                preview['selected_variants'] = {'before': old['selected_variants'], 'after': resolved['selected_variants']}
            placement = operation.get('placement', old['placement'] if old else None)
            if placement is None: raise ValueError('Place requires explicit host-pixel placement')
            mount = operation.get('mount', old['mount'] if old else None)
            receivers = operation.get('receivers', old['receivers'] if old else [])
            if not isinstance(receivers, list): raise ValueError('Receiver contacts must be an array')
            receiver_ids = [identifier(r['id']) for r in receivers]
            if len(set(receiver_ids)) != len(receiver_ids): raise ValueError('Duplicate receiver contact IDs')
            result = scene_bridge('model-instance', scene, catalog, {'instance_id': instance_id, 'resolved': resolved,
                'pin': pin, 'package_source': str(Path(pin['package']).parent/'source'), 'pivot': closure.models[root]['local_frame']['pivot'],
                'placement': placement, 'mount': mount, 'receivers': receivers, 'sockets': resolved['exported_sockets'],
                'previous': old, **({'order': operation['order']} if 'order' in operation else {})})
            scene, catalog = result['scene'], result['catalog']
            record = runtime_numbers({'instance_id': instance_id, 'pin': pin, 'state': state, 'placement': placement, 'mount': mount,
                      'receivers': receivers, 'interface': contract, 'mapping': result['mapping'], 'sockets': result['sockets'],
                      'root_layer': result['root_layer'], 'relationships': result['relationships'],
                      'effective_controls': resolved['effective_controls'], 'selected_variants': resolved['selected_variants'],
                      'clock': resolved['clock']})
            current = [record if r['instance_id'] == instance_id else r for r in current] if old else [*current, record]
            scene['model_instances'] = {'format': FORMAT, 'schema_version': 1, 'instances': current}
            record['managed_sha256'] = fingerprint(scene, catalog, record)
            previews.append({'instance_id': instance_id, 'op': action, 'pin': pin, 'managed_sha256': record['managed_sha256'],
                             'adoption': preview, 'mount': result['mount_proof'], 'selected_leaves': result['selected_leaves'],
                             'affected_receivers': result['relationships']['receivers']})
        # Changes to another instance's mount/contact must not silently rewrite
        # its fingerprint. Such a change requires a separate explicit revision.
        for record in current: verify_managed(scene, catalog, record)
        def materialize(stage):
            for package_hash, (package, manifest) in packages.items():
                target = stage/'packages'/package_hash
                model_package.copy_files(package/'source', target/'source', manifest['files'])
                target.joinpath('model-package.json').write_bytes(package.joinpath('model-package.json').read_bytes())
                if digest(target/'model-package.json') != package_hash: raise ValueError('Package changed while copying')
                model_package.open_package(target)
        return transaction.finish_bundle(scene, catalog, generation, materialize=materialize,
            dependencies=pinned, dry_run=dry_run, details={'applicable': True, 'previews': previews,
                'evidence_effect': 'Changed scene/catalog/instance subjects require new scene-context evidence; old captured revisions remain pinned.',
                'acceptance': 'not established'})
