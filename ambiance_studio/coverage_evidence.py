"""Typed provider adapters; acquire and verify evidence, never decide readiness.

Movie acquisition may populate the existing exact-input decode cache. Provider
results keep their serialized dictionary contract for sealed evidence records.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, NotRequired, Protocol, TypedDict
import math

import studio
from . import production_plan as spec, editions, project_references, record_contracts, revision_reviews
from .coverage_context import AssessmentUnavailable, pinned, relative_file
from .timebase import scene_frame_count


class FileReference(TypedDict):
    path: str
    sha256: str


class ProviderEvidence(TypedDict):
    kind: Literal['raster', 'model-raster', 'movie', 'activity', 'observation']
    references: list[FileReference]
    output: NotRequired[dict[str, int]]
    role: NotRequired[str]
    edition: NotRequired[str]


@dataclass(frozen=True)
class EvidenceRequest:
    project: Path
    receipt: Path
    context: dict[str, Any]
    expectation: dict[str, Any]
    view: str
    role: str | None = None


class EvidenceVerifier(Protocol):
    def verify(self, request: EvidenceRequest) -> ProviderEvidence:
        """Verify exact provider artifacts or raise a contract/runtime error."""
        ...


def same_picture(receipt, ctx):
    for key in ['scene_sha256', 'catalog_sha256']:
        if receipt.get(key) != ctx[key]: raise ValueError('Evidence belongs to different '+key)
    revision = receipt.get('revision')
    if isinstance(revision, dict): revision = revision.get('revision_id')
    if revision != ctx['revision']: raise ValueError('Evidence belongs to a different revision')


def raster_receipt(project, path, ctx, view) -> ProviderEvidence:
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


def movie_receipt(project, path, ctx, view, role=None) -> ProviderEvidence:
    from . import deliveries
    receipt = record_contracts.read_sealed(path, editions.EDITION, versions=(1, 2))
    if receipt['revision'] != ctx['revision'] or receipt['revision_sha256'] != ctx['revision_sha256']:
        raise ValueError('Movie evidence belongs to a different captured revision')
    exact = editions.edition_path(project, receipt['revision'], receipt['id'])
    if path != exact: raise ValueError('Movie evidence must select its canonical edition receipt')
    receipt = editions.load_edition(project, receipt['revision'], receipt['id'])
    bound_view = editions.edition_view(project, receipt)
    if bound_view['id'] != view or bound_view['sha256'] != ctx['views'][view]['view_sha256']:
        raise ValueError('Movie evidence belongs to a different view')
    if project_references.changed(project, receipt['dependencies']): raise ValueError('Movie edition dependencies changed')
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
    if verification.get('loop_frames') != scene_frame_count(ctx['scene']):
        raise ValueError('Movie evidence does not cover the full captured picture loop')
    from . import media_verification, native_media
    # Run the existing decoder once per exact movie/expectations. Warm readiness
    # uses the hashed result and never repeats encoding or full media decoding.
    key = studio.encoded_hash({'movie': receipt['output'], 'facts': facts, 'loop_frames': verification['loop_frames']})
    cache = Path(project)/'.ambiance/evidence-decode'/key
    report_path = cache/'media-report.json'
    assessment = ctx.get('_assessment')
    if assessment:
        for ref in receipt['dependencies']:
            assessment.track(studio.inside(project, ref['path']), 'evidence_index')
        if ctx.get('_read_only') or report_path.exists(): assessment.track(report_path, 'evidence_index')
    if not report_path.exists():
        if ctx.get('_read_only'):
            raise AssessmentUnavailable('Exact movie decode evidence is unavailable; run explicit plan evidence or plan coverage to acquire it: '+str(report_path))
        media_verification.verify_media(native_media.native_binary(project), movie, cache,
                          int(facts['width']), int(facts['height']), int(facts['fps']), int(facts['frames']),
                          facts['audio_tracks'], int(verification['loop_frames']))
    decoded = studio.read(report_path)
    if decoded.get('ok') is not True or decoded.get('fully_decoded') is not True or decoded.get('input_sha256') != receipt['output']['sha256']:
        raise ValueError('Movie failed actual decoder verification; inspect '+str(report_path))
    return {'kind': 'movie', 'role': role, 'edition': receipt['id'],
            'references': [pinned(project, path), pinned(project, report_path), *[{'path': r['path'], 'sha256': r['sha256']} for r in receipt['dependencies']]]}


def activity_receipt(project, path, ctx, exp, view) -> ProviderEvidence:
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
    if ctx['scene'].get('clock', {}).get('mode') == 'finite':
        raise ValueError('Finite activity remains diagnostic; finite-shot requirement evidence is not implemented')
    if clock['start_frame'] != 0 or clock['frames'] != scene_frame_count(ctx['scene']) or clock['stride'] != 1:
        raise ValueError('Required activity evidence needs the full picture loop at every output frame; reduced sampling remains diagnostic')
    actions = {r['id']: r for r in summary.get('actions', [])}
    planned_actions = {r['id']: r for r in activity.actions_from_plan(ctx['plan'])}
    reported_actions = {r['id']: r for r in receipt['actions']}
    for id in exp['action_ids']:
        if reported_actions.get(id) != planned_actions.get(id): raise ValueError('Activity action realization/targets differ from the captured plan: '+id)
        if not actions.get(id, {}).get('applicable'): raise ValueError('Activity is missing required action '+id)
        diagnostics = actions[id].get('timing_target_diagnostics')
        if not isinstance(diagnostics, list): raise ValueError('Activity receipt lacks authored timing target diagnostics')
        if diagnostics: raise ValueError('Activity violates authored timing targets: '+id+': '+', '.join(diagnostics))
        req = exp['requirement']; metric = req.get('metric')
        if metric:
            value = actions[id].get(metric)
            if type(value) not in [int, float] or not math.isfinite(value): raise ValueError('Activity metric unavailable/nonfinite: '+metric)
            if 'minimum' in req and value < req['minimum'] or 'maximum' in req and value > req['maximum']:
                raise ValueError('Activity metric outside authored bounds: '+id+'/'+metric)
    return {'kind': 'activity', 'references': [pinned(project, path)]}


def observed_receipt(project, path, ctx, exp, view) -> ProviderEvidence:
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
        planned = next((r for r in activity.actions_from_plan(ctx['plan']) if r['id'] == observation['action_id']), None)
        reported = next((r for r in receipt['actions'] if r['id'] == observation['action_id']), None)
        if planned is None or reported != planned: raise ValueError('Observed action realization/targets differ from the captured plan')
        if observation['status'] != 'meets-direction' or observation.get('criterion', 'readability') != exp['requirement']['check']:
            raise ValueError('Activity observation does not meet this observed requirement')
        if exp['requirement']['check'] == 'readability' and observation.get('observed_level') is None:
            raise ValueError('Readability observation needs its actual observed level')
        return {'kind': 'observation', 'references': [pinned(project, path), pinned(project, validated['receipt_path'])]}
    if data.get('version') != 2 or not ctx['revision']:
        raise ValueError('Observed evidence requires a captured revision review')
    subject_data = data.get('subject', {})
    context = revision_reviews.review_context(project, ctx['revision'], subject_data.get('edition'), view)
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


class ProviderVerifier:
    """Explicit adapters for supported receipt kinds; no plugin registry."""

    def verify(self, request: EvidenceRequest) -> ProviderEvidence:
        project, path = request.project, request.receipt
        ctx, exp, view, role = request.context, request.expectation, request.view, request.role
        check = exp['requirement']['check']
        if check == 'raster':
            receipt = studio.read(path)
            if isinstance(receipt, dict) and receipt.get('format') == 'ambiance-model-scene-evidence':
                from .model_evidence import verify
                return verify(project, path, ctx, view)
            return raster_receipt(project, path, ctx, view)
        if check == 'movie': return movie_receipt(project, path, ctx, view, role)
        if check == 'activity': return activity_receipt(project, path, ctx, exp, view)
        if exp['requirement']['type'] == 'observed': return observed_receipt(project, path, ctx, exp, view)
        raise ValueError('Structural expectations use current structural checks, not report files')


def verify_provider(project, path, ctx, exp, view, role=None):
    """Compatibility entry point for callers verifying one provider receipt."""
    return ProviderVerifier().verify(EvidenceRequest(project, path, ctx, exp, view, role))
