"""One stage-aware intent/evidence evaluator for CLI, overview and production.

Reports describe structural, measured and observed requirements separately. They
never infer an artistic pass from counters, filenames or untyped evidence.
"""
from pathlib import Path

import studio
from . import production_plan as spec, scene_runtime, revision_capture
from .errors import CommandError
from .coverage_context import (
    AssessmentInputs, AssessmentUnavailable, context, subject, expectation, relative_file, pinned,
)
from .coverage_evidence import (
    EvidenceVerifier, same_picture, raster_receipt, movie_receipt, activity_receipt, observed_receipt,
    observation_media, verify_provider,
)
from .coverage_records import (
    EVIDENCE, observation_drafts, normalize_observations, register_evidence, evidence_for,
    acquire_evidence, save_report, format_report,
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


def _compute(project, stage='animation', view=None, revision=None, *, outputs=None, phase='current',
             verifier: EvidenceVerifier | None = None, assessment=None, read_only=True):
    """Shared coverage policy; persistence belongs to the explicit wrapper."""
    project = Path(project).resolve(); spec.enum(stage, spec.STAGES, 'coverage stage')
    spec.enum(phase, ['current', 'preflight'], 'coverage phase')
    issues = []; fulfilled = []; rows = []; deferred = []
    def gap(id, action, **detail): issues.append({'id': id, 'action': action, **detail})
    assessment = assessment or AssessmentInputs(project, revision)
    if assessment.project != project or assessment.revision != revision:
        raise ValueError('Assessment inputs belong to a different project/revision')
    ctx = None; inputs = {}; used = {'plan'}
    def component(name):
        used.add(name)
        return assessment.get(name)
    def unknown(names):
        return [name for name in names if assessment.components.get(name, {}).get('state') != 'available']
    def file_hash(name):
        try:
            return assessment.track(assessment.path(name), name)['sha256']
        except (OSError, ValueError, KeyError, TypeError, CommandError):
            return None
    try:
        plan = component('plan')
        if plan is None: raise AssessmentUnavailable('; '.join(assessment.components['plan']['diagnostics']))
        scene, catalog = component('scene'), component('catalog')
        views = component('views')
        assets = component('asset_dependencies')
        component('plan_dependencies')
        if revision: component('revision_dependencies')
        inventory = component('evidence_index')
        fulfillment = component('inventory')
        # Preserve the exact legacy subject/hash contract for evidence adapters.
        ctx = dict(plan=plan, plan_sha256=file_hash('plan'), expectation_sha256=spec.identity(plan)['expectations'],
                   path=str(assessment.path('plan')), revision=revision,
                   revision_sha256=studio.digest(revision_capture.manifest_path(project, revision)) if revision else None,
                   scene=scene, catalog=catalog, views=views or {}, asset_references=assets or [],
                   scene_sha256=file_hash('scene'), catalog_sha256=file_hash('catalog'),
                   scene_path=assessment.path('scene') if scene is not None else None,
                   catalog_path=assessment.path('catalog') if catalog is not None else None,
                   inventory_path=assessment.path('inventory') if fulfillment is not None else None,
                   _read_only=read_only, _assessment=assessment)
        for name in sorted(used - {'plan'}):
            if unknown([name]):
                gap('plan.component-unavailable.'+name, 'Inspect the unavailable assessment input.',
                    component=name, state='unknown', reasons=assessment.components[name]['diagnostics'])
        inputs = {key: ctx[key] for key in ['scene_sha256', 'catalog_sha256', 'revision_sha256']}
        inputs['asset_dependencies_sha256'] = studio.encoded_hash(ctx['asset_references']) if assets is not None else None
        inputs['view_sha256'] = {id: row['view_sha256'] for id, row in ctx['views'].items()}
        plan = ctx['plan']; elements = {e['id']: e for e in plan['elements']}; layers = {l['id']: l for l in (scene or {}).get('layers', [])}
        intended = {o['view_id']: o['roles'] for o in plan['outputs']}
        selected = [view] if view is not None else list(intended)
        if view is not None and view not in intended: gap('plan.view-unplanned.'+view, 'Select an intended view or explicitly revise production scope.')
        if not elements: gap('plan.elements-unplanned', 'Author the scene census with plan spec apply.')
        if not intended: gap('plan.outputs-unplanned', 'Declare intended output views and soundtrack roles.')
        if not plan['expectations']: gap('plan.expectations-unplanned', 'Author explicit expectations before claiming scope completion.')
        if plan.get('migration', {}).get('unresolved'): gap('plan.migration-unresolved', 'Resolve the authored migration questions.')
        if inventory is not None:
            try:
                for conflict in spec.contradictions(project, plan): issues.append(conflict)
            except (OSError, ValueError, KeyError, TypeError) as error:
                gap('plan.inventory-unavailable', 'Inspect inventory scope accounting.', state='unknown', reasons=[str(error)])
        for id in selected:
            if views is not None and id not in views: gap('plan.view-missing.'+id, 'Create the intended saved view through view apply.')
        inventory_path = project/'plans/asset-inventory.json'
        inputs['evidence_index_sha256'] = assessment.track(inventory_path, 'evidence_index')['sha256']
        inputs['fulfillment_inventory_sha256'] = file_hash('inventory')
        refs = (inventory or {}).get('expectation_evidence', [])
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
        evidence_inputs = ['views', 'asset_dependencies', 'plan_dependencies', 'evidence_index'] + (['revision_dependencies'] if revision else [])
        evidence = acquire_evidence(project, ctx, needs, refs, verifier=verifier) if not unknown(evidence_inputs) else {}
        inventory_report = None
        for exp in applicable:
            check = exp['requirement']['check']; exp_views = [v for v in exp['view_ids'] if v in selected]
            if not exp['view_ids']: gap('plan.expectation-unplanned.'+exp['id'], 'Give this expectation explicit applicable views.')
            if not expectation_has_subjects(exp):
                gap('plan.expectation-unplanned.'+exp['id'], 'Declare the required elements, actions or relations for this expectation.')
                continue
            for v in exp_views:
                prefix = f'plan.expectation.{exp["id"]}.{v}'
                required = ['views', 'plan_dependencies'] + (['revision_dependencies'] if revision else [])
                if check == 'art': required += ['inventory', 'asset_dependencies']
                elif exp['requirement']['type'] != 'structural': required += ['asset_dependencies', 'evidence_index']
                unavailable = unknown(required)
                if unavailable:
                    gap(prefix, 'Restore the inputs needed to assess this expectation.', expectation_id=exp['id'],
                        view_id=v, state='unknown', reasons=['Unavailable component: '+name for name in unavailable])
                    rows.append({'id': exp['id'], 'view_id': v, 'type': exp['requirement']['type'], 'ready': None})
                    continue
                if v not in ctx['views']:
                    rows.append({'id': exp['id'], 'view_id': v, 'type': exp['requirement']['type'], 'ready': None})
                    continue
                if phase == 'preflight' and check == 'movie':
                    deferred.append(prefix)
                    continue
                reasons = []; uncertain = False
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
                        try:
                            assessment.track_references(fulfillment, 'inventory')
                            inventory_report = planning.evaluate(project, fulfillment, catalog, scene, ctx['inventory_path'],
                                {str(path.relative_to(project)): assessment.track(path, 'inventory')['sha256']
                                 for path in [ctx['inventory_path'], ctx['scene_path'], ctx['catalog_path']]})
                            for path in inventory_report['evidence_bindings']:
                                assessment.track(studio.inside(project, path), 'inventory')
                        except (OSError, ValueError, KeyError, TypeError, CommandError) as error:
                            inventory_report = {'ok': False, 'errors': [str(error)], 'items': [], 'unknown': True}
                    uncertain = inventory_report.get('unknown', False)
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
                        if ok is None: uncertain = True
                        if not ok: reasons.append((role+': ' if role else '')+reason)
                if reasons: gap(prefix, 'Fulfill the expectation and record its exact evidence.', expectation_id=exp['id'], view_id=v, reasons=reasons, **({'state': 'unknown'} if uncertain else {}))
                else: fulfilled.append(prefix)
                rows.append({'id': exp['id'], 'view_id': v, 'type': exp['requirement']['type'], 'ready': None if uncertain else not reasons})
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
    except (OSError, ValueError, KeyError, TypeError, CommandError) as error:
        gap('plan.unavailable', 'Inspect or explicitly create/migrate the production plan.', reasons=[str(error)])
    snapshot = assessment.finish(used)
    if snapshot['changed_inputs']:
        gap('plan.inputs-changed', 'Inputs changed during coverage; rerun against one stable revision or working snapshot.')
        fulfilled.clear()
        for row in rows: row['ready'] = None
    issues = list({r['id']: r for r in issues}.values())
    result = {'ok': not issues, 'ready': not issues, 'stage': stage, 'view': view, 'revision': revision, 'phase': phase,
              'full_scope': view is None, 'plan_sha256': ctx['plan_sha256'] if ctx else None, 'inputs': inputs,
              'blocked': issues, 'fulfilled': fulfilled, 'future_outputs': deferred, 'counts': {'blocked': len(issues), 'fulfilled': len(fulfilled), 'future_outputs': len(deferred)},
              'limits': ['Readiness is scoped to the requested stage and views.', 'Draft renders and review presentations remain available.', 'Structural/measured evidence does not imply an artistic observation.']}
    return result, rows, snapshot


def evaluate(project, stage='animation', view=None, revision=None, *, details=False, outputs=None, phase='current',
             verifier: EvidenceVerifier | None = None):
    """Explicit compatible coverage/preflight report, including evidence acquisition."""
    result, rows, _ = _compute(project, stage, view, revision, outputs=outputs, phase=phase,
                                verifier=verifier, read_only=False)
    return save_report(Path(project).resolve(), result, rows, details=details)


def assess(project, stage='animation', view=None, revision=None, *, details=False, outputs=None, phase='current',
           verifier: EvidenceVerifier | None = None, assessment=None):
    """Pure shared assessment; no report/cache write or writer lock.

    Reusable AssessmentInputs may pre-load independent components. Only the
    coverage inputs participate in its result and freshness identity.
    """
    result, rows, snapshot = _compute(project, stage, view, revision, outputs=outputs, phase=phase,
                                       verifier=verifier, assessment=assessment)
    snapshot['subject'] = {'mode': 'revision' if revision else 'working', 'revision': revision,
                           'plan_sha256': result['plan_sha256'], **result['inputs']}
    snapshot['unknown_expectations'] = sum(row['ready'] is None for row in rows)
    snapshot['complete'] = snapshot['complete'] and snapshot['unknown_expectations'] == 0
    snapshot['diagnostics'] = [row for row in result['blocked'] if row.get('state') == 'unknown']
    snapshot['assessment_sha256'] = studio.encoded_hash({'version': 1, 'result': result, 'inputs': snapshot})
    return {**format_report(result, rows, details=details), 'assessment': snapshot}
