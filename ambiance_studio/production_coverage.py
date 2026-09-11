"""One stage-aware intent/evidence evaluator for CLI, overview and production.

Reports describe structural, measured and observed requirements separately. They
never infer an artistic pass from counters, filenames or untyped evidence.
"""
from pathlib import Path
import hashlib
import json

import studio
from . import production_plan as spec, revisions, scene_runtime
from .project import locations, project_lock
from .errors import CommandError

EVIDENCE = 'ambiance-plan-evidence'


def context(project, revision=None):
    project = Path(project).resolve(); result = spec.load_context(project, revision)
    if revision:
        captured = revisions.render_context(project, revision)
        scene_path, catalog_path = captured['scene'], captured['catalog']
        result['revision_sha256'] = captured['manifest_sha256']
        result['inventory_path'] = studio.inside(project, revisions.load(project, revision)['controls']['inventory'])
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
    return revisions.relative(Path(project).resolve(), path)


def pinned(project, path):
    path = Path(path).resolve()
    return {'path': relative_file(project, path), 'sha256': studio.digest(path)}


def same_picture(receipt, ctx):
    for key in ['scene_sha256', 'catalog_sha256']:
        if receipt.get(key) != ctx[key]: raise ValueError('Evidence belongs to different '+key)
    revision = receipt.get('revision')
    if isinstance(revision, dict): revision = revision.get('revision_id')
    if revision != ctx['revision']: raise ValueError('Evidence belongs to a different revision')


def raster_receipt(project, path, ctx, view):
    """Validate actual existing renderer outputs without treating them as observation."""
    from PIL import Image
    from . import preview
    receipt = spec.read(path)
    if not isinstance(receipt, dict): raise ValueError('Raster evidence must be a typed object receipt')
    if receipt.get('mode') not in ['frame', 'views-proof'] or receipt.get('ok') is not True:
        raise ValueError('Raster evidence requires a successful render frame or synchronized views-proof receipt')
    same_picture(receipt, ctx)
    for key in ['scene', 'catalog']:
        snapshot = path.parent/(key+'.snapshot.json')
        if not snapshot.is_file() or studio.digest(snapshot) != ctx[key+'_sha256']:
            raise ValueError('Raster evidence needs exact '+key+' snapshot')
    refs = [pinned(project, path), *ctx['asset_references'],
            pinned(project, path.parent/'scene.snapshot.json'), pinned(project, path.parent/'catalog.snapshot.json')]
    def image(file, digest, size):
        name = relative_file(project, file); target = studio.inside(Path(project).resolve(), name)
        if studio.digest(target) != digest: raise ValueError('Raster artifact changed: '+name)
        with Image.open(target) as decoded:
            decoded.load()
            if decoded.format != 'PNG' or decoded.size != (size['width'], size['height']):
                raise ValueError('Raster artifact dimensions/format differ from receipt')
        refs.append({'path': name, 'sha256': digest})
    expected = ctx['views'][view]
    if receipt['mode'] == 'views-proof':
        preview.views_proof_routes(path.parent)
        rows = receipt.get('views', {})
        if not isinstance(rows, dict): raise ValueError('Raster receipt requires typed view rows')
        row = rows.get(view)
        output = next((r for r in receipt.get('outputs', []) if r.get('id') == view), None)
        if not output or not row or type(receipt.get('frames')) is not int or receipt['frames'] < 1:
            raise ValueError('Raster receipt has no frames for expected view')
        if row['view'] != expected['view'] or row['view_sha256'] != expected['view_sha256']:
            raise ValueError('Raster receipt has wrong view identity')
        for name, digest in zip(output['files'], output['hashes']):
            file = (path.parent/name).resolve()
            if not file.is_relative_to(path.parent): raise ValueError('Raster artifact escapes directory')
            image(file, digest, output['output'])
        refs.append(pinned(project, path.parent/'index.html'))
        size = output['output']
    else:
        row = receipt.get('view')
        if not row or row['view'] != expected['view'] or row['view_sha256'] != expected['view_sha256']:
            raise ValueError('Raster receipt needs explicit matching --view')
        size = row['output']; image(Path(receipt['output']), receipt['output_sha256'], size)
    output = expected['output']
    if size['width']*output['height'] != size['height']*output['width']:
        raise ValueError('Raster dimensions do not match view aspect')
    return {'kind': 'raster', 'references': refs, 'output': size}


def movie_receipt(project, path, ctx, view, role=None):
    from . import deliveries
    receipt = revisions.read_sealed(path, revisions.EDITION, versions=(1, 2))
    if receipt['revision'] != ctx['revision'] or receipt['revision_sha256'] != ctx['revision_sha256']:
        raise ValueError('Movie evidence belongs to a different captured revision')
    exact = revisions.edition_path(project, receipt['revision'], receipt['id'])
    if path != exact: raise ValueError('Movie evidence must select its canonical edition receipt')
    receipt = revisions.load_edition(project, receipt['revision'], receipt['id'])
    bound_view = revisions.edition_view(project, receipt)
    if bound_view['id'] != view or bound_view['sha256'] != ctx['views'][view]['view_sha256']:
        raise ValueError('Movie evidence belongs to a different view')
    if revisions.changed(project, receipt['dependencies']): raise ValueError('Movie edition dependencies changed')
    verification = studio.read(studio.inside(project, receipt['verification']['path']))
    movie = studio.inside(project, receipt['output']['path'])
    # The existing edition checker validates technical expectations; ensure real
    # container bytes too, rather than admitting a prose-only synthetic receipt.
    with movie.open('rb') as stream: header = stream.read(32)
    if len(header) < 12 or header[4:8] != b'ftyp': raise ValueError('Movie evidence is not an encoded MP4 container')
    if not verification.get('fully_decoded') or not verification.get('input_unchanged') or verification.get('input_sha256') != studio.digest(movie):
        raise ValueError('Movie requires exact complete decode evidence')
    tracks = verification.get('audio', {}).get('tracks')
    if role == 'silent' and tracks != 0 or role in ['score', 'effects'] and tracks != 1:
        raise ValueError('Movie soundtrack differs from the required role')
    if role is None: raise ValueError('Movie evidence needs an explicit soundtrack role')
    if not deliveries.intact(project, receipt['output'])['ok']: raise ValueError('Movie changed')
    facts = deliveries.metadata(verification)
    expected = ctx['views'][view]['output']
    if facts['width'] != expected['width'] or facts['height'] != expected['height'] or facts['fps'] != ctx['scene']['canvas']['fps']:
        raise ValueError('Movie decode dimensions/clock differ from expected view')
    if verification.get('loop_frames') != ctx['scene']['canvas']['fps']*ctx['scene']['canvas']['loop_seconds']:
        raise ValueError('Movie evidence does not cover the full captured picture loop')
    from . import rendering
    # Run the existing decoder once per exact movie/expectations. Warm readiness
    # uses the hashed result and never repeats encoding or full media decoding.
    key = studio.encoded_hash({'movie': receipt['output'], 'facts': facts, 'loop_frames': verification['loop_frames']})
    cache = Path(project)/'.ambiance/evidence-decode'/key
    report_path = cache/'media-report.json'
    if not report_path.exists():
        rendering._verify(project, rendering._native_binary(project), movie, cache,
                          int(facts['width']), int(facts['height']), int(facts['fps']), int(facts['frames']),
                          facts['audio_tracks'], int(verification['loop_frames']))
    decoded = studio.read(report_path)
    if decoded.get('ok') is not True or decoded.get('fully_decoded') is not True or decoded.get('input_sha256') != receipt['output']['sha256']:
        raise ValueError('Movie failed actual decoder verification; inspect '+str(report_path))
    return {'kind': 'movie', 'role': role, 'edition': receipt['id'],
            'references': [pinned(project, path), pinned(project, report_path), *[{'path': r['path'], 'sha256': r['sha256']} for r in receipt['dependencies']]]}


def activity_receipt(project, path, ctx, exp, view):
    try:
        from . import activity
    except ImportError:
        raise ValueError('Activity evidence provider is unavailable; produce its typed receipt after integration') from None
    receipt = activity.verify_receipt(path)
    same_picture(receipt, ctx)
    plan = receipt.get('plan', {})
    if plan.get('plan_sha256') != ctx['plan_sha256'] or plan.get('expectation_sha256', {}).get(exp['id']) != ctx['expectation_sha256'][exp['id']]:
        raise ValueError('Activity receipt has stale plan/expectation identity')
    row = next((r for r in receipt['views'] if r['view']['id'] == view), None)
    if not row or row['view_sha256'] != ctx['views'][view]['view_sha256']:
        raise ValueError('Activity receipt has wrong view identity')
    summary = next((r for r in receipt['summary'] if r['view'] == view), {})
    clock = receipt['clock']
    if clock['start_frame'] != 0 or clock['frames'] != clock['fps']*clock['picture_seconds'] or clock['stride'] != 1:
        raise ValueError('Required activity evidence needs the full picture loop at every output frame; reduced sampling remains diagnostic')
    actions = {r['id']: r for r in summary.get('actions', [])}
    for id in exp['action_ids']:
        if not actions.get(id, {}).get('applicable'): raise ValueError('Activity is missing required action '+id)
        req = exp['requirement']; metric = req.get('metric')
        if metric:
            value = actions[id].get(metric)
            if type(value) not in [int, float]: raise ValueError('Activity metric unavailable: '+metric)
            if 'minimum' in req and value < req['minimum'] or 'maximum' in req and value > req['maximum']:
                raise ValueError('Activity metric outside authored bounds: '+id+'/'+metric)
    return {'kind': 'activity', 'references': [pinned(project, path)]}


def observed_receipt(project, path, ctx, exp, view):
    """Consume actual existing gate reviews with explicit expectation mappings."""
    data = studio.read(path)
    if not isinstance(data, dict): raise ValueError('Observed evidence must be a typed object receipt')
    if data.get('kind') == 'ambiance-activity-observation':
        try:
            from . import activity
        except ImportError:
            raise ValueError('Activity observation provider is unavailable; integrate it before registering this receipt') from None
        validated = activity.verify_observation(path)
        observation = validated['observation']; receipt = validated['receipt']
        same_picture(receipt, ctx)
        recorded_plan = receipt.get('plan', {})
        if recorded_plan.get('plan_sha256') != ctx['plan_sha256'] or recorded_plan.get('expectation_sha256', {}).get(exp['id']) != ctx['expectation_sha256'][exp['id']]:
            raise ValueError('Activity observation has wrong plan/expectation identity')
        if observation['view_id'] != view or observation['action_id'] not in exp['action_ids'] or len(exp['action_ids']) != 1:
            raise ValueError('Activity observation must identify the sole required action/view')
        if observation['status'] != 'meets-direction' or observation.get('criterion', 'readability') != exp['requirement']['check']:
            raise ValueError('Activity observation does not meet this observed requirement')
        if exp['requirement']['check'] == 'readability' and observation.get('observed_level') is None:
            raise ValueError('Readability observation needs its actual observed level')
        return {'kind': 'observation', 'references': [pinned(project, path), pinned(project, validated['receipt_path'])]}
    if data.get('version') != 2 or not ctx['revision']:
        raise ValueError('Observed evidence requires a captured revision review')
    subject_data = data.get('subject', {})
    context = revisions.review_context(project, ctx['revision'], subject_data.get('edition'), view)
    if subject_data != context['subject']: raise ValueError('Observation has wrong revision/view/plan subject')
    if path != context['review_dir']/(data.get('gate', '')+'.json'):
        raise ValueError('Observation must name its canonical recorded review')
    checks = [c for c in data.get('expectations', []) if c.get('id') == exp['id'] and c.get('view_id') == view]
    if len(checks) != 1 or checks[0].get('status') != 'meets-direction':
        raise ValueError('Expectation is unreviewed or needs revision')
    state = studio.gate_status(project, context)['gates'].get(data['gate'], {})
    if state.get('state') == 'stale': raise ValueError('Observation evidence is stale')
    check = checks[0]
    if check.get('expectation_sha256') != ctx['expectation_sha256'][exp['id']]: raise ValueError('Observation expectation changed')
    observer = check.get('observed_by', {})
    if observer.get('kind') not in ['agent', 'human'] or not observer.get('name') or not check.get('note'):
        raise ValueError('Observation needs a named human/agent and actual note')
    if check.get('normal_speed') is not True: raise ValueError('Observed direction requires normal-speed review')
    if not check.get('evidence'): raise ValueError('Observation needs actual picture evidence')
    for ref in check['evidence']:
        spec.file_ref(project, {'path': ref['path'], 'sha256': ref['sha256']})
        observation_media(project, ref, ctx, view)
    if exp['requirement']['check'] == 'readability':
        spec.level(check.get('observed_level'))
        target = max((t['readability_target'] for a in ctx['plan']['actions'] if a['id'] in exp['action_ids'] for t in a['targets'] if t['view_id'] == view), default=None)
        if target is None or check['observed_level'] < target: raise ValueError('Observed readability does not meet the selected target')
    return {'kind': 'observation', 'references': [pinned(project, path)]}


def observation_media(project, ref, ctx, view):
    path = studio.inside(project, ref['path'])
    if ref['kind'] == 'raster': return raster_receipt(project, path, ctx, view)
    if ref['kind'] == 'movie': return movie_receipt(project, path, ctx, view, ref.get('role'))
    raise ValueError('Observation must cite actual raster or movie evidence')


def observation_drafts(ctx, gate, view):
    return [{'id': e['id'], 'view_id': view, 'expectation_sha256': ctx['expectation_sha256'][e['id']],
             'status': 'unreviewed', 'observed_by': {'kind': 'agent', 'name': ''}, 'note': '',
             'normal_speed': False, 'display': {'width': None, 'height': None}, 'evidence': []}
            for e in ctx['plan']['expectations'] if e['requirement']['type'] == 'observed' and e['stage'] == gate and view in e['view_ids']]


def normalize_observations(project, review, review_context):
    if not review_context or not review_context.get('plan_context'):
        if review.get('expectations'): raise ValueError('Expectation observations require a captured production plan')
        return []
    ctx = context(project, review_context['subject']['revision'])
    view = review_context['subject'].get('view', 'authored')
    expected = {r['id']: r for r in observation_drafts(ctx, review['gate'], view)}
    records = spec.rows(review.get('expectations', []), 'review expectations')
    if set(records) != set(expected): raise ValueError('Record exactly every applicable observed expectation; use unreviewed for unperformed checks')
    result = []
    for id, row in records.items():
        spec.obj(row, ['id', 'view_id', 'expectation_sha256', 'status', 'observed_by', 'note', 'normal_speed', 'display', 'evidence'], ['observed_level'], 'expectation observation')
        if row['view_id'] != view or row['expectation_sha256'] != expected[id]['expectation_sha256']:
            raise ValueError('Observation view or expectation identity differs from captured subject')
        spec.enum(row['status'], ['unreviewed', 'revise', 'meets-direction'], 'observation status')
        if review['verdict'] == 'pass' and row['status'] != 'meets-direction':
            raise ValueError('Passing review requires all applicable observed expectations to meet direction')
        normalized = dict(row)
        if row['status'] != 'unreviewed':
            spec.obj(row['observed_by'], ['kind', 'name'], label='observer')
            spec.enum(row['observed_by']['kind'], ['agent', 'human'], 'observer kind')
            spec.string(row['observed_by']['name'], 'observer name'); spec.string(row['note'], 'observation note')
            if row['normal_speed'] is not True: raise ValueError('Direction observations require actual normal-speed viewing')
            spec.obj(row['display'], ['width', 'height'], label='observation display')
            if any(type(v) is not int or v <= 0 for v in row['display'].values()): raise ValueError('Record actual positive display dimensions')
            refs = []
            if not row['evidence']: raise ValueError('Observation needs exact raster/movie evidence')
            for ref in spec.array(row['evidence'], 'observation evidence'):
                spec.obj(ref, ['path', 'kind'], ['role', 'sha256'], 'observation evidence')
                observation_media(project, ref, ctx, view)
                refs.append({**ref, **pinned(project, studio.inside(project, ref['path']))})
            normalized['evidence'] = refs
            exp = expectation(ctx, id)
            if exp['requirement']['check'] == 'readability':
                spec.level(row.get('observed_level'))
                targets = [t['readability_target'] for a in ctx['plan']['actions'] if a['id'] in exp['action_ids'] for t in a['targets'] if t['view_id'] == view]
                if row['status'] == 'meets-direction' and (not targets or row['observed_level'] < max(targets)):
                    raise ValueError('Observed readability is below the exact per-action/view target')
        result.append(normalized)
    return result


def verify_provider(project, path, ctx, exp, view, role=None):
    check = exp['requirement']['check']
    if check == 'raster': return raster_receipt(project, path, ctx, view)
    if check == 'movie': return movie_receipt(project, path, ctx, view, role)
    if check == 'activity': return activity_receipt(project, path, ctx, exp, view)
    if exp['requirement']['type'] == 'observed': return observed_receipt(project, path, ctx, exp, view)
    raise ValueError('Structural expectations use current structural checks, not report files')


def register_evidence(project, id, view, receipt, revision=None, role=None):
    project = Path(project).resolve(); path = studio.inside(project, receipt)
    with project_lock(project):
        ctx = context(project, revision); exp = expectation(ctx, id)
        if view not in exp['view_ids']: raise ValueError('View is not applicable to this expectation')
        provider = verify_provider(project, path, ctx, exp, view, role)
        record = revisions.seal({'format': EVIDENCE, 'schema_version': 1, 'subject': subject(ctx, exp, view),
                                 'receipt': pinned(project, path), 'provider': provider})
        target = studio.inside(project, f'evidence/expectations/{record["payload_sha256"]}.json')
        inventory_path = project/'plans/asset-inventory.json'; inventory_raw = inventory_path.read_bytes()
        inventory = studio.read(inventory_path); refs = inventory.setdefault('expectation_evidence', [])
        if not isinstance(refs, list): raise ValueError('Inventory expectation_evidence must be an array')
        current = context(project, revision)
        if subject(current, expectation(current, id), view) != record['subject']: raise ValueError('Evidence inputs changed during registration')
        for ref in provider['references']: spec.file_ref(project, ref)
        if inventory_path.read_bytes() != inventory_raw: raise ValueError('Inventory changed during evidence registration')
        if target.exists() and studio.read(target) != record: raise ValueError('Evidence record changed')
        if not target.exists(): studio.write(target, record)
        ref = pinned(project, target)
        reused = ref in refs
        if not reused:
            history = project/'.ambiance/inventory-history'/f'{hashlib.sha256(inventory_raw).hexdigest()}.json'
            history.parent.mkdir(parents=True, exist_ok=True)
            if not history.exists(): history.write_bytes(inventory_raw)
            refs.append(ref); studio.write(inventory_path, inventory)
        return {'ok': True, 'record': str(target), 'subject': record['subject'], 'reused': reused}


def evidence_for(project, ctx, exp, view, refs, role=None):
    reasons = []
    for ref in refs:
        try:
            path = spec.file_ref(project, ref)
            record = revisions.read_sealed(path, EVIDENCE)
            spec.obj(record, ['format', 'schema_version', 'payload_sha256', 'subject', 'receipt', 'provider'], label='plan evidence')
            selected = record['subject']
            if not isinstance(selected, dict) or not isinstance(record['provider'], dict): raise ValueError('Plan evidence subject/provider must be typed objects')
            if selected.get('expectation_id') != exp['id'] or selected.get('view_id') != view: continue
            if role and record['provider'].get('role') != role: continue
            if selected != subject(ctx, exp, view): raise ValueError('Stale plan/expectation/scene/catalog/view/revision identity')
            receipt = spec.file_ref(project, record['receipt'])
            provider = verify_provider(project, receipt, ctx, exp, view, role)
            if provider != record['provider']: raise ValueError('Evidence artifact identity changed')
            return True, str(path)
        except (OSError, ValueError, KeyError, TypeError, CommandError) as error: reasons.append(str(error))
    unique = list(dict.fromkeys(reasons))
    return False, ('; '.join(unique[:3]) + (f'; {len(unique)-3} further invalid records' if len(unique)>3 else '')) or 'No matching typed evidence is recorded'


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


def evaluate(project, stage='animation', view=None, revision=None, *, details=False, outputs=None, phase='current'):
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
        inventory_report = None
        for exp in applicable:
            check = exp['requirement']['check']; exp_views = [v for v in exp['view_ids'] if v in selected]
            if not exp['view_ids']: gap('plan.expectation-unplanned.'+exp['id'], 'Give this expectation explicit applicable views.')
            if check in ['independent-control', 'art'] and not exp['element_ids'] or check == 'relation' and not exp['relation_ids'] or check in ['activity', 'readability'] and not exp['action_ids']:
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
                        ok, reason = evidence_for(project, ctx, exp, v, refs, role)
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
    report = project/'.ambiance/coverage'/f'{studio.encoded_hash(result)}.json'
    full = {**result, 'expectations': rows, 'report': str(report)}
    if not report.exists(): studio.write(report, full)
    elif studio.read(report) != full: raise ValueError('Saved coverage report changed')
    if details: return full
    compact = [{**r, **({'reasons': r['reasons'][:3]} if 'reasons' in r else {})} for r in issues[:8]]
    return {**result, 'blocked': compact, 'fulfilled': len(fulfilled), 'report': str(report),
            'details_truncated': len(issues)>8 or any(len(r.get('reasons', []))>3 for r in issues)}
