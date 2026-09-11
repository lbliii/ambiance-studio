"""Canonical creative intent. Runtime, fulfillment and observations live elsewhere."""
import difflib
import hashlib
import json
import math
from pathlib import Path
import re

import studio
from .errors import CommandError
from .project import project_lock

PATH = 'plans/production-plan.json'
FORMAT = 'ambiance-production-plan'
STAGES = ['layout', 'assets', 'animation', 'export']
DIMENSIONS = {
    'kind': ['environment', 'structure', 'character', 'prop', 'effect'],
    'depth_band': ['far-background', 'background', 'midground', 'foreground', 'near-foreground'],
    'motion_role': ['primary', 'supporting', 'ambient', 'stable'],
    'cadence': ['continuous', 'recurring', 'occasional', 'still'],
}
METHODS = ['baked', 'cutout', 'rig', 'mask', 'painted-effect']
CHECKS = {'view': 'structural', 'independent-control': 'structural', 'art': 'structural',
          'relation': 'structural', 'raster': 'measured', 'movie': 'measured',
          'activity': 'measured', 'readability': 'observed', 'composition': 'observed',
          'lighting': 'observed'}


def obj(value, required, optional=(), label='object'):
    if not isinstance(value, dict):
        raise ValueError(f'{label}: expected object')
    missing, extra = set(required)-value.keys(), value.keys()-set(required)-set(optional)
    if missing or extra:
        raise ValueError(f'{label}: missing fields {sorted(missing)}; unknown fields {sorted(extra)}')


def string(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{label}: expected nonempty string')


def ident(value, label='id'):
    if not isinstance(value, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}', value):
        raise ValueError(f'{label}: expected stable ID (1–100 letters, digits, dot, underscore, hyphen)')


def enum(value, choices, label):
    if value not in choices:
        raise ValueError(f'{label}: expected one of {choices}')


def level(value):
    if type(value) is not int or not 0 <= value <= 4:
        raise ValueError('readability_target: expected integer 0–4')


def array(value, label):
    if not isinstance(value, list):
        raise ValueError(f'{label}: expected array')
    return value


def ids(value, label):
    for item in array(value, label):
        ident(item, label)
    if len(set(value)) != len(value):
        raise ValueError(f'{label}: duplicate IDs')
    return value


def rows(value, label, key='id'):
    result = {}
    for item in array(value, label):
        if not isinstance(item, dict):
            raise ValueError(f'{label}: expected object entries')
        ident(item.get(key), label+'.'+key)
        if item[key] in result:
            raise ValueError(f'{label}: duplicate {key} {item[key]}')
        result[item[key]] = item
    return result


def sha(value, label='sha256'):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
        raise ValueError(f'{label}: expected lowercase SHA-256')


def file_ref(project, value, *, verify=True, extra=()):
    obj(value, ['path', 'sha256'], extra, 'file reference')
    sha(value['sha256'])
    path = studio.inside(Path(project).resolve(), value['path'])
    if verify and (not path.is_file() or studio.digest(path) != value['sha256']):
        raise ValueError(f'Missing or changed source: {value["path"]}')
    return path


def part_ref(value):
    obj(value, ['item_id', 'part_id'], label='inventory part')
    ident(value['item_id']); ident(value['part_id'])


def read(path):
    def pairs(entries):
        data = {}
        for key, value in entries:
            if key in data:
                raise ValueError(f'Duplicate JSON field: {key}')
            data[key] = value
        return data
    def constant(value):
        raise ValueError(f'Nonfinite JSON value: {value}')
    return json.loads(Path(path).read_bytes(), object_pairs_hook=pairs, parse_constant=constant)


def validate(project, plan, *, verify_sources=True):
    obj(plan, ['format', 'schema_version', 'story', 'sources', 'elements', 'actions', 'outputs',
               'relations', 'expectations', 'change'], ['migration'], 'production plan')
    if plan['format'] != FORMAT or type(plan['schema_version']) is not int or plan['schema_version'] != 1:
        raise ValueError('Expected ambiance-production-plan schema_version 1')
    obj(plan['story'], ['premise', 'direction'], label='story')
    for value in plan['story'].values(): string(value, 'story')
    obj(plan['change'], ['reason', 'supersedes_sha256'], label='change')
    string(plan['change']['reason'], 'change.reason')
    if plan['change']['supersedes_sha256'] is not None: sha(plan['change']['supersedes_sha256'])
    sources = rows(plan['sources'], 'sources')
    for source in sources.values(): file_ref(project, source, verify=verify_sources, extra=['id'])
    elements = rows(plan['elements'], 'elements'); actions = rows(plan['actions'], 'actions')
    outputs = rows(plan['outputs'], 'outputs', 'view_id'); relations = rows(plan['relations'], 'relations')
    expectations = rows(plan['expectations'], 'expectations')
    def references(values, known, label):
        ids(values, label)
        unknown = set(values)-set(known)
        if unknown: raise ValueError(f'{label}: unknown IDs {sorted(unknown)}')
    for output in outputs.values():
        obj(output, ['view_id', 'roles'], label='output')
        ids(output['roles'], 'output.roles')
        if not output['roles'] or set(output['roles'])-{'score', 'effects', 'silent'}:
            raise ValueError('output.roles: select score, effects and/or silent')
    for element in elements.values():
        obj(element, ['id', *DIMENSIONS, 'readability_target', 'origin', 'purpose', 'source_ids',
                      'action_ids', 'realization', 'required_art'], label='element')
        for name, choices in DIMENSIONS.items(): enum(element[name], choices, name)
        level(element['readability_target']); enum(element['origin'], ['observed', 'proposed', 'user-directed'], 'origin')
        string(element['purpose'], 'purpose')
        references(element['source_ids'], sources, 'source_ids'); references(element['action_ids'], actions, 'action_ids')
        realization = element['realization']
        obj(realization, ['method', 'inventory_parts', 'layer_ids'], label='realization')
        enum(realization['method'], METHODS, 'realization.method'); ids(realization['layer_ids'], 'layer_ids')
        for part in array(realization['inventory_parts'], 'inventory_parts'): part_ref(part)
        for art in rows(element['required_art'], 'required_art').values():
            obj(art, ['id', 'role', 'purpose', 'inventory_part'], label='required_art')
            enum(art['role'], ['source', 'cutout', 'backing', 'occluder', 'mask', 'painted-effect'], 'art.role')
            string(art['purpose'], 'art.purpose'); part_ref(art['inventory_part'])
    for action in actions.values():
        obj(action, ['id', 'element_id', 'description', 'method', 'targets'], ['timing', 'layer_ids'], 'action')
        references([action['element_id']], elements, 'action.element_id')
        if action['id'] not in elements[action['element_id']]['action_ids']:
            raise ValueError(f'action {action["id"]}: element.action_ids must reference its action')
        string(action['description'], 'description'); string(action['method'], 'action.method')
        if 'layer_ids' in action:
            references(action['layer_ids'], elements[action['element_id']]['realization']['layer_ids'], 'action.layer_ids')
        for target in rows(action['targets'], 'targets', 'view_id').values():
            obj(target, ['view_id', 'readability_target'], label='action target')
            references([target['view_id']], outputs, 'target.view_id'); level(target['readability_target'])
        if 'timing' in action:
            obj(action['timing'], [], ['onset_max_seconds', 'duration_min_seconds', 'rest_max_seconds'], 'timing target')
            for value in action['timing'].values():
                if type(value) not in [int, float] or not math.isfinite(value) or value < 0:
                    raise ValueError('timing targets: expected finite nonnegative seconds')
    for element in elements.values():
        if any(actions[id]['element_id'] != element['id'] for id in element['action_ids']):
            raise ValueError('element.action_ids must refer only to its own actions')
    for relation in relations.values():
        obj(relation, ['id', 'kind', 'source_element', 'target_element', 'scene_ref', 'dependencies'], label='relation')
        enum(relation['kind'], ['attachment', 'occlusion', 'light-source', 'receiver', 'driver'], 'relation.kind')
        references([relation['source_element']], elements, 'source_element')
        references([relation['target_element']], elements, 'target_element')
        if relation['scene_ref'] is not None: string(relation['scene_ref'], 'scene_ref')
        for dep in array(relation['dependencies'], 'dependencies'): file_ref(project, dep, verify=verify_sources)
    for exp in expectations.values():
        obj(exp, ['id', 'rationale', 'direction', 'stage', 'view_ids', 'element_ids', 'action_ids', 'relation_ids', 'requirement'], label='expectation')
        string(exp['rationale'], 'rationale'); string(exp['direction'], 'direction'); enum(exp['stage'], STAGES, 'stage')
        for key, known in [('view_ids', outputs), ('element_ids', elements), ('action_ids', actions), ('relation_ids', relations)]:
            references(exp[key], known, key)
        req = exp['requirement']; obj(req, ['type', 'check'], ['metric', 'minimum', 'maximum'], 'requirement')
        enum(req['check'], list(CHECKS), 'requirement.check')
        if req['type'] != CHECKS[req['check']]: raise ValueError('requirement type does not match check')
        if any(k in req for k in ['metric', 'minimum', 'maximum']):
            if req['check'] != 'activity' or not isinstance(req.get('metric'), str) or not any(k in req for k in ['minimum', 'maximum']):
                raise ValueError('Only activity requirements accept a named metric with minimum/maximum')
            for key in ['minimum', 'maximum']:
                if key in req and (type(req[key]) not in [int, float] or not math.isfinite(req[key])):
                    raise ValueError('metric bounds must be finite numbers')
            if req.get('minimum', -math.inf) > req.get('maximum', math.inf): raise ValueError('metric minimum exceeds maximum')
    if 'migration' in plan:
        obj(plan['migration'], ['version', 'originals', 'unresolved'], label='migration')
        if type(plan['migration']['version']) is not int or plan['migration']['version'] != 1: raise ValueError('migration version must be 1')
        for ref in array(plan['migration']['originals'], 'migration.originals'): file_ref(project, ref, verify=verify_sources)
        for note in array(plan['migration']['unresolved'], 'migration.unresolved'): string(note, 'migration.unresolved')
    return plan


def identity(plan):
    return {'plan_content_sha256': studio.encoded_hash(plan),
            'expectations': {e['id']: studio.encoded_hash(e) for e in plan['expectations']}}


def load(project):
    return validate(project, read(studio.inside(Path(project).resolve(), PATH)))


def load_context(project, revision=None):
    project = Path(project).resolve()
    if revision:
        from . import revisions
        manifest = revisions.load(project, revision)
        if not revisions.check(project, revision)['ok']: raise ValueError('Captured revision dependencies changed')
        name = manifest['controls'].get('production_plan')
        if not name: raise ValueError('Revision has no captured production plan; legacy records are unchanged')
        path = studio.inside(project, name)
    else:
        path = studio.inside(project, PATH)
    raw = path.read_bytes(); plan = validate(project, read(path))
    if raw != path.read_bytes(): raise ValueError('Plan changed during inspection')
    return {'plan': plan, 'path': str(path), 'plan_sha256': hashlib.sha256(raw).hexdigest(),
            'expectation_sha256': identity(plan)['expectations'], 'revision': revision}


def validate_binding(project, binding, plan=None):
    obj(binding, ['element_id', 'inventory_part'], label='production binding')
    part_ref(binding['inventory_part'])
    plan = load(project) if plan is None else plan
    element = next((e for e in plan['elements'] if e['id'] == binding['element_id']), None)
    if element is None: raise ValueError('Unknown production element: '+str(binding['element_id']))
    declared = element['realization']['inventory_parts'] + [a['inventory_part'] for a in element['required_art']]
    if binding['inventory_part'] not in declared: raise ValueError('Inventory part is not declared for this production element')
    inventory = studio.read(studio.inside(Path(project).resolve(), 'plans/asset-inventory.json'))
    ref = binding['inventory_part']
    item = next((i for i in inventory['items'] if i['id'] == ref['item_id']), {})
    if not any(isinstance(p, dict) and p.get('id') == ref['part_id'] for p in item.get('required_parts', [])):
        raise ValueError('Unknown inventory part: '+ref['item_id']+'/'+ref['part_id'])
    return binding


def contradictions(project, plan):
    path = studio.inside(Path(project).resolve(), 'plans/asset-inventory.json')
    if not path.is_file(): return []
    inventory = studio.read(path); items = {i['id']: i for i in inventory.get('items', [])}
    required_elements = {id for e in plan['expectations'] for id in e['element_ids']}
    required_actions = {id for e in plan['expectations'] for id in e['action_ids']}
    required_elements |= {a['element_id'] for a in plan['actions'] if a['id'] in required_actions}
    required_relations = {id for e in plan['expectations'] for id in e['relation_ids']}
    required_elements |= {r[k] for r in plan['relations'] if r['id'] in required_relations for k in ['source_element', 'target_element']}
    result = []
    covered = set()
    for element in plan['elements']:
        parts = list(element['realization']['inventory_parts']) + [a['inventory_part'] for a in element['required_art']]
        for ref in parts:
            if element['id'] in required_elements: covered.add((ref['item_id'], ref['part_id']))
            item = items.get(ref['item_id'], {})
            part = next((p for p in item.get('required_parts', []) if isinstance(p, dict) and p.get('id') == ref['part_id']), {})
            if element['id'] in required_elements and (item.get('required') is False or part.get('required') is False or item.get('state') == 'static-deferred'):
                result.append({'id': f'plan.required-contradiction.{element["id"]}.{ref["item_id"]}.{ref["part_id"]}',
                               'element_id': element['id'], 'inventory_part': ref,
                               'action': 'Reconcile the explicit plan requirement with the retained legacy optional/deferred flag.'})
    for item in items.values():
        parts = [p for p in item.get('required_parts', []) if isinstance(p, dict)]
        if item.get('required') is True and not any(i == item['id'] for i, _ in covered):
            result.append({'id': 'plan.required-unmapped.'+item['id'],
                           'action': 'Map the legacy required inventory item to an explicit plan expectation.'})
        for part in parts:
            if part.get('required') is True and (item['id'], part['id']) not in covered:
                result.append({'id': 'plan.required-unmapped.'+item['id']+'.'+part['id'],
                               'action': 'Map the legacy required inventory part to an explicit plan expectation.'})
    return result


def complexity(plan):
    def counts(key):
        return {value: sum(e[key] == value for e in plan['elements']) for value in DIMENSIONS[key]}
    return {'elements': len(plan['elements']), 'dimensions': {key: counts(key) for key in DIMENSIONS},
            'actions': len(plan['actions']), 'output_pairs': sum(len(o['roles']) for o in plan['outputs']),
            'relations': len(plan['relations']), 'required_art': len([a for e in plan['elements'] for a in e['required_art']]),
            'realized_layer_refs': len({l for e in plan['elements'] for l in e['realization']['layer_ids']}),
            'inventory_part_refs': len({(p['item_id'], p['part_id']) for e in plan['elements'] for p in e['realization']['inventory_parts']}),
            'expectations_by_stage': {stage: sum(e['stage'] == stage for e in plan['expectations']) for stage in STAGES},
            'meaning': 'Workload and coverage dimensions; no artistic score or minimum layer quota.'}


def inspect(project, details=False):
    plan = load(project); conflicts = contradictions(project, plan)
    result = {'ok': not conflicts, 'path': str(Path(project).resolve()/PATH), 'sha256': studio.digest(Path(project)/PATH),
              'identity': identity(plan), 'complexity': complexity(plan), 'contradictions': conflicts}
    if details: result['plan'] = plan
    return result


def apply(project, source, *, dry_run=False, expected=None):
    project = Path(project).resolve(); source = Path(source).resolve(); path = studio.inside(project, PATH)
    with project_lock(project):
        raw = source.read_bytes(); candidate = validate(project, read(source))
        old = path.read_bytes() if path.exists() else None
        previous = hashlib.sha256(old).hexdigest() if old is not None else None
        if expected is not None and expected != (previous or 'absent'):
            raise CommandError('Plan changed since expected SHA-256; inspect and rebase the edit.', 'stale_input', 2)
        if candidate['change']['supersedes_sha256'] != previous:
            raise CommandError('change.supersedes_sha256 must identify the current plan (null for first creation).', 'stale_input', 2)
        conflicts = contradictions(project, candidate)
        after = json.dumps(candidate, indent=2)+'\n'
        diff = ''.join(difflib.unified_diff((old.decode() if old else '').splitlines(True), after.splitlines(True), fromfile=PATH, tofile='candidate'))
        result = {'ok': not conflicts, 'dry_run': dry_run, 'previous_sha256': previous, 'identity': identity(candidate),
                  'path': str(path), 'contradictions': conflicts, 'diff': diff}
        if conflicts or dry_run: return result
        if source.read_bytes() != raw or (path.read_bytes() if path.exists() else None) != old:
            raise CommandError('Plan inputs changed during validation; no edit saved.', 'stale_input', 2)
        validate(project, candidate)
        if old is not None:
            history = studio.inside(project, f'.ambiance/plan-history/{previous}.json'); history.parent.mkdir(parents=True, exist_ok=True)
            if history.exists() and history.read_bytes() != old: raise ValueError('Plan history changed')
            if not history.exists(): history.write_bytes(old)
            result['restore_source'] = str(history)
        studio.write(path, candidate); result['sha256'] = studio.digest(path)
        result.pop('diff')
        return result


def migrate(project, proposal, originals, out):
    """Explicit authored mapping; preserve notes without guessing semantics from prose."""
    project = Path(project).resolve(); out = Path(out).resolve()
    if out.exists(): raise ValueError('Migration artifact directory must be fresh')
    candidate = read(proposal)
    if 'migration' in candidate: raise ValueError('Proposal already has a migration record')
    records = []
    for name in originals:
        path = studio.inside(project, name)
        if not path.is_file(): raise ValueError(f'Missing migration original: {name}')
        records.append({'path': name, 'sha256': studio.digest(path)})
    if not records: raise ValueError('At least one original census/inventory/note is required')
    candidate['migration'] = {'version': 1, 'originals': records, 'unresolved': []}
    validate(project, candidate)
    conflicts = contradictions(project, candidate)
    out.mkdir(parents=True)
    for index, ref in enumerate(records):
        target = out/'originals'/f'{index}-{Path(ref["path"]).name}'; target.parent.mkdir(exist_ok=True)
        source = studio.inside(project, ref['path']); raw = source.read_bytes()
        if hashlib.sha256(raw).hexdigest() != ref['sha256']: raise ValueError('Migration source changed')
        target.write_bytes(raw)
    studio.write(out/'candidate.json', candidate)
    result = apply(project, out/'candidate.json', dry_run=True)
    result.update(artifact=str(out), candidate=str(out/'candidate.json'), originals=records,
                  migration_version=1, instructions='Review the mapping/diff, reconcile contradictions, then plan spec apply candidate.json.')
    studio.write(out/'report.json', result)
    return {k: v for k, v in result.items() if k != 'diff'} | {'report': str(out/'report.json')}
