"""Expectation evidence registration, history and exact record lookup.

Registration retains the project lock, concurrent-input checks and byte-for-byte
inventory snapshots. Lookup delegates provider acquisition to one verifier.
"""
from pathlib import Path
import hashlib

import studio
from . import production_plan as spec, record_contracts
from .coverage_context import context, expectation, pinned, subject
from .coverage_evidence import EvidenceRequest, EvidenceVerifier, ProviderVerifier, observation_media
from .project import project_lock
from .errors import CommandError

EVIDENCE = 'ambiance-plan-evidence'


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


def register_evidence(project, id, view, receipt, revision=None, role=None, *, verifier: EvidenceVerifier | None = None):
    project = Path(project).resolve(); path = studio.inside(project, receipt)
    with project_lock(project):
        ctx = context(project, revision); exp = expectation(ctx, id)
        if view not in exp['view_ids']: raise ValueError('View is not applicable to this expectation')
        provider = (ProviderVerifier() if verifier is None else verifier).verify(EvidenceRequest(project, path, ctx, exp, view, role))
        record = record_contracts.seal({'format': EVIDENCE, 'schema_version': 1, 'subject': subject(ctx, exp, view),
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


def evidence_for(project, ctx, exp, view, refs, role=None, *, verifier: EvidenceVerifier | None = None):
    reasons = []
    for ref in refs:
        try:
            path = spec.file_ref(project, ref)
            record = record_contracts.read_sealed(path, EVIDENCE)
            spec.obj(record, ['format', 'schema_version', 'payload_sha256', 'subject', 'receipt', 'provider'], label='plan evidence')
            selected = record['subject']
            if not isinstance(selected, dict) or not isinstance(record['provider'], dict): raise ValueError('Plan evidence subject/provider must be typed objects')
            if selected.get('expectation_id') != exp['id'] or selected.get('view_id') != view: continue
            if role and record['provider'].get('role') != role: continue
            if selected != subject(ctx, exp, view): raise ValueError('Stale plan/expectation/scene/catalog/view/revision identity')
            receipt = spec.file_ref(project, record['receipt'])
            provider = (ProviderVerifier() if verifier is None else verifier).verify(EvidenceRequest(project, receipt, ctx, exp, view, role))
            if provider != record['provider']: raise ValueError('Evidence artifact identity changed')
            return True, str(path)
        except (OSError, ValueError, KeyError, TypeError, CommandError) as error: reasons.append(str(error))
    unique = list(dict.fromkeys(reasons))
    return False, ('; '.join(unique[:3]) + (f'; {len(unique)-3} further invalid records' if len(unique)>3 else '')) or 'No matching typed evidence is recorded'


def acquire_evidence(project, ctx, needs, refs, *, verifier: EvidenceVerifier | None = None):
    """Acquire all requested matches before readiness consumes their results.

    Scope/stage policy supplies the needs. This operation only resolves sealed
    records and exact artifacts, including cold movie-cache verification.
    """
    verifier = ProviderVerifier() if verifier is None else verifier
    return {(exp['id'], view, role): evidence_for(project, ctx, exp, view, refs, role, verifier=verifier)
            for exp, view, role in needs}


def save_report(project, result, rows, *, details):
    """Persist an immutable report with the existing bytes/hash/compact contract."""
    issues = result['blocked']; fulfilled = result['fulfilled']
    report = project/'.ambiance/coverage'/f'{studio.encoded_hash(result)}.json'
    full = {**result, 'expectations': rows, 'report': str(report)}
    if not report.exists(): studio.write(report, full)
    elif studio.read(report) != full: raise ValueError('Saved coverage report changed')
    if details: return full
    compact = [{**r, **({'reasons': r['reasons'][:3]} if 'reasons' in r else {})} for r in issues[:8]]
    return {**result, 'blocked': compact, 'fulfilled': len(fulfilled), 'report': str(report),
            'details_truncated': len(issues)>8 or any(len(r.get('reasons', []))>3 for r in issues)}
