"""One stage-aware intent/evidence evaluator for CLI, overview and production.

Reports describe structural, measured and observed requirements separately. They
never infer an artistic pass from counters, filenames or untyped evidence.
"""
from pathlib import Path
import hashlib
import json

import studio
from . import production_plan as spec, scene_runtime
from .errors import CommandError
from .coverage_context import context, subject, expectation, relative_file, pinned
from .coverage_evidence import (
    EvidenceVerifier, same_picture, raster_receipt, movie_receipt, activity_receipt, observed_receipt,
    observation_media, verify_provider,
)
from .coverage_records import (
    EVIDENCE, observation_drafts, normalize_observations, register_evidence, evidence_for,
    acquire_evidence, save_report,
)

# Existing imports above remain available to studio reviews and external callers.
# Provider verification and registration live in their dedicated owners.


def relation_issues(scene, elements, relation):
    """Check declared endpoint membership; the shared engine validates execution."""
    ref = relation['scene_ref'] or ':'; kind, _, id = ref.partition(':')
    groups = {'layer': scene['layers'], 'binding': scene.get('bindings', {}).get('links', []),
              'illumination': scene.get('finishing', {}).get('illuminations', []),
              'signal': scene.get('finishing', {}).get('signals', [])}
    row = next((r for r in groups.get(kind, []) if r['id'] == id), None)
    if row is None: return [relation['id']+': missing runtime relationship '+ref]
    source = elements[relation['source_element']]['realization']['layer_ids']
    target = elements[relation['target_element']]['realization']['layer_ids']
    if not source or not target: return [relation['id']+': source/receiver elements lack runtime layer references']
    if kind == 'binding':
        source_id = row['source'].get('layer')
        if row['source'].get('signal'):
            signal = next((s for s in groups['signal'] if s['id'] == row['source']['signal']), {})
            source_id = signal.get('layer')
        if source_id not in source or row['target'].get('layer') not in target:
            return [relation['id']+': binding endpoints differ from the declared source/target elements']
    elif kind == 'illumination' and row.get('receiver') not in target:
        return [relation['id']+': illumination receiver differs from the declared target element']
    elif kind == 'signal' and row.get('layer') not in source:
        return [relation['id']+': signal source differs from the declared source element']
    elif kind == 'layer':
        if row['id'] not in source: return [relation['id']+': layer reference differs from the declared source element']
        if relation['kind'] == 'attachment' and row.get('attach', {}).get('layer') not in target:
            return [relation['id']+': attachment parent differs from the declared target element']
        if relation['kind'] == 'occlusion':
            order = {l['id']: i for i, l in enumerate(scene['layers'])}
            if any(order.get(t, len(order)) >= order[row['id']] for t in target):
                return [relation['id']+': declared occluder is not after its target in painter order']
    return []


def expectation_has_subjects(exp):
    """One applicability rule shared by evidence selection and readiness policy."""
    check = exp['requirement']['check']
    return not (check in ['independent-control', 'art'] and not exp['element_ids']
                or check == 'relation' and not exp['relation_ids']
                or check in ['activity', 'readability'] and not exp['action_ids'])


def evaluate(project, stage='animation', view=None, revision=None, *, details=False, outputs=None, phase='current',
             verifier: EvidenceVerifier | None = None):
    """Return the same ready/blocked decision for every caller; drafts remain usable."""
    project = Path(project).resolve(); spec.enum(stage, spec.STAGES, 'coverage stage')
    spec.enum(phase, ['current', 'preflight'], 'coverage phase')
    issues = []; fulfilled = []; rows = []; deferred = []
    def gap(id, action, **detail): issues.append({'id': id, 'action': action, **detail})
    ctx = None; inputs = {}
    try:
        ctx = context(project, revision)
        inputs = {key: ctx[key] for key in ['scene_sha256', 'catalog_sha256', 'revision_sha256']}
        inputs['asset_dependencies_sha256'] = studio.encoded_hash(ctx['asset_references'])
        inputs['view_sha256'] = {id: row['view_sha256'] for id, row in ctx['views'].items()}
        plan = ctx['plan']; elements = {e['id']: e for e in plan['elements']}; layers = {l['id']: l for l in ctx['scene']['layers']}
        intended = {o['view_id']: o['roles'] for o in plan['outputs']}
        selected = [view] if view is not None else list(intended)
        if view is not None and view not in intended: gap('plan.view-unplanned.'+view, 'Select an intended view or explicitly revise production scope.')
        if not elements: gap('plan.elements-unplanned', 'Author the scene census with plan spec apply.')
        if not intended: gap('plan.outputs-unplanned', 'Declare intended output views and soundtrack roles.')
        if not plan['expectations']: gap('plan.expectations-unplanned', 'Author explicit expectations before claiming scope completion.')
        if plan.get('migration', {}).get('unresolved'): gap('plan.migration-unresolved', 'Resolve the authored migration questions.')
        for conflict in spec.contradictions(project, plan): issues.append(conflict)
        for id in selected:
            if id not in ctx['views']: gap('plan.view-missing.'+id, 'Create the intended saved view through view apply.')
        inventory_path = project/'plans/asset-inventory.json'; inventory_bytes = inventory_path.read_bytes(); inventory = json.loads(inventory_bytes)
        inputs['evidence_index_sha256'] = hashlib.sha256(inventory_bytes).hexdigest()
        inputs['fulfillment_inventory_sha256'] = studio.digest(ctx['inventory_path'])
        refs = inventory.get('expectation_evidence', [])
        if not isinstance(refs, list): raise ValueError('Inventory expectation_evidence must be an array')
        applicable = [e for e in plan['expectations'] if spec.STAGES.index(e['stage']) <= spec.STAGES.index(stage)]
        if not applicable: gap('plan.stage-unplanned.'+stage, 'Author applicable structural/measured/observed expectations for this stage.')
        if spec.STAGES.index(stage) >= spec.STAGES.index('assets'):
            for element in elements.values():
                if element['required_art'] and not any(e['requirement']['check'] == 'art' and element['id'] in e['element_ids'] for e in applicable):
                    gap('plan.art-unplanned.'+element['id'], 'Declare an applicable art expectation for the required art/backing/occluders.')
        if spec.STAGES.index(stage) >= spec.STAGES.index('animation'):
            for relation in plan['relations']:
                if not any(e['requirement']['check'] == 'relation' and relation['id'] in e['relation_ids'] for e in applicable):
                    gap('plan.relation-unplanned.'+relation['id'], 'Declare an applicable structural expectation for the intended relationship.')
        if outputs is not None:
            declared = {(o['view_id'], role) for o in outputs for role in o['roles']}
            wanted = {(v, r) for v in selected for r in intended.get(v, [])}
            for v, r in sorted(wanted-declared): gap(f'plan.output-missing.{v}.{r}', 'Include this intended view/soundtrack in the full-scope iteration or label it a draft.')
        # Acquisition can decode a cold movie cache. Complete it before the
        # policy loop consumes match results; no adapter decides stage readiness.
        needs = [(exp, v, role) for exp in applicable
                 if exp['requirement']['type'] != 'structural' and expectation_has_subjects(exp)
                 and not (phase == 'preflight' and exp['requirement']['check'] == 'movie')
                 for v in exp['view_ids'] if v in selected and v in ctx['views']
                 for role in (intended[v] if exp['requirement']['check'] == 'movie' else [None])]
        evidence = acquire_evidence(project, ctx, needs, refs, verifier=verifier)
        inventory_report = None
        for exp in applicable:
            check = exp['requirement']['check']; exp_views = [v for v in exp['view_ids'] if v in selected]
            if not exp['view_ids']: gap('plan.expectation-unplanned.'+exp['id'], 'Give this expectation explicit applicable views.')
            if not expectation_has_subjects(exp):
                gap('plan.expectation-unplanned.'+exp['id'], 'Declare the required elements, actions or relations for this expectation.')
                continue
            for v in exp_views:
                prefix = f'plan.expectation.{exp["id"]}.{v}'
                if v not in ctx['views']: continue
                if phase == 'preflight' and check == 'movie':
                    deferred.append(prefix)
                    continue
                reasons = []
                if check == 'view':
                    pass  # Shared view resolver validated the saved geometry.
                elif check == 'independent-control':
                    owned = {}
                    for eid in exp['element_ids']:
                        realization = elements[eid]['realization']; ids = realization['layer_ids']
                        if realization['method'] == 'baked' or not ids or any(l not in layers for l in ids): reasons.append(eid+': independent realization missing')
                        for lid in ids:
                            if lid in owned: reasons.append(lid+': shared layer cannot prove independent elements')
                            owned[lid] = eid
                elif check == 'art':
                    if inventory_report is None:
                        from . import planning
                        inventory_report = planning.inspect(project, relative_file(project, ctx['inventory_path']),
                                                            scene_path=ctx['scene_path'], catalog_path=ctx['catalog_path'])
                    if not inventory_report['ok']: reasons.extend(inventory_report['errors'])
                    items = {r['id']: r for r in inventory_report['items']}
                    for eid in exp['element_ids']:
                        element = elements[eid]
                        parts = element['realization']['inventory_parts'] + [a['inventory_part'] for a in element['required_art']]
                        if not parts: reasons.append(eid+': no declared art parts')
                        for ref in parts:
                            part = next((p for p in items.get(ref['item_id'], {}).get('required_parts', []) if p['id'] == ref['part_id']), {})
                            if part.get('stage') not in ['compiled', 'placed'] or part.get('review', {}).get('state') == 'needs-revision':
                                reasons.append(ref['item_id']+'/'+ref['part_id']+': compile/admit actual art and resolve revisions')
                elif check == 'relation':
                    for relation in plan['relations']:
                        if relation['id'] not in exp['relation_ids']: continue
                        reasons.extend(relation_issues(ctx['scene'], elements, relation))
                else:
                    roles = intended[v] if check == 'movie' else [None]
                    for role in roles:
                        ok, reason = evidence[(exp['id'], v, role)]
                        if not ok: reasons.append((role+': ' if role else '')+reason)
                if reasons: gap(prefix, 'Fulfill the expectation and record its exact evidence.', expectation_id=exp['id'], view_id=v, reasons=reasons)
                else: fulfilled.append(prefix)
                rows.append({'id': exp['id'], 'view_id': v, 'type': exp['requirement']['type'], 'ready': not reasons})
        if spec.STAGES.index(stage) >= spec.STAGES.index('animation'):
            for element in elements.values():
                if element['cadence'] != 'still' and not element['action_ids']:
                    gap('plan.action-unplanned.'+element['id'], 'Declare the selected action or explicitly author intentional stillness.')
            for action in plan['actions']:
                for v in selected:
                    targets = [t for t in action['targets'] if t['view_id'] == v]
                    if not targets: gap(f'plan.action-target-missing.{action["id"]}.{v}', 'Author this action’s per-view target, including explicit stillness where directed.')
                    for kind in ['activity', 'readability']:
                        if not any(e['requirement']['check'] == kind and action['id'] in e['action_ids'] and v in e['view_ids'] for e in applicable):
                            gap(f'plan.action-{kind}-unplanned.{action["id"]}.{v}', 'Declare the applicable '+kind+' expectation for this action/view.')
        if stage == 'export':
            for v in selected:
                if not any(e['requirement']['check'] == 'movie' and v in e['view_ids'] for e in applicable):
                    gap('plan.movie-unplanned.'+v, 'Declare an encoded-movie expectation for the intended output.')
        tracked = [(Path(ctx['path']), ctx['plan_sha256']), (ctx['scene_path'], ctx['scene_sha256']),
                   (ctx['catalog_path'], ctx['catalog_sha256']), (inventory_path, inputs['evidence_index_sha256']),
                   (ctx['inventory_path'], inputs['fulfillment_inventory_sha256'])]
        if any(not path.is_file() or studio.digest(path) != digest for path, digest in tracked):
            gap('plan.inputs-changed', 'Inputs changed during coverage; rerun against one stable revision or working snapshot.')
        for ref in ctx['asset_references']: spec.file_ref(project, ref)
        spec.validate(project, plan)
    except (OSError, ValueError, KeyError, TypeError, CommandError) as error:
        gap('plan.unavailable', 'Inspect or explicitly create/migrate the production plan.', reasons=[str(error)])
    issues = list({r['id']: r for r in issues}.values())
    result = {'ok': not issues, 'ready': not issues, 'stage': stage, 'view': view, 'revision': revision, 'phase': phase,
              'full_scope': view is None, 'plan_sha256': ctx['plan_sha256'] if ctx else None, 'inputs': inputs,
              'blocked': issues, 'fulfilled': fulfilled, 'future_outputs': deferred, 'counts': {'blocked': len(issues), 'fulfilled': len(fulfilled), 'future_outputs': len(deferred)},
              'limits': ['Readiness is scoped to the requested stage and views.', 'Draft renders and review presentations remain available.', 'Structural/measured evidence does not imply an artistic observation.']}
    return save_report(project, result, rows, details=details)
