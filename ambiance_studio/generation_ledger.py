"""Durable local request/result bookkeeping. Never submits a provider request."""
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import re

import studio
from . import asset_prep as p
from .project import project_lock

FORMAT = 'ambiance-generation-request'
STATES = ('pending', 'submitted', 'uncertain', 'retrieved', 'selected')
NEXT = {'pending': 'Record an authorized submission or an existing tool result; this CLI never submits.',
        'submitted': 'Retrieve the existing request result; preserve its provider identity.',
        'uncertain': 'Reconcile the existing request/history or tool result before any new charged request.',
        'retrieved': 'Inspect saved outputs, then explicitly select their SHA-256.',
        'selected': 'Use the selected local source; retain request and preparation provenance.'}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def identifier(value, label):
    if not isinstance(value, str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_-]{0,79}', value):
        raise ValueError(f'{label} must be 1–80 letters, digits, underscores or hyphens')
    return value


def digest(value):
    if not isinstance(value, str) or not re.fullmatch('[a-f0-9]{64}', value):
        raise ValueError('Expected an actual SHA-256')
    return value


def nullable_text(value, label):
    if value is not None and (not isinstance(value, str) or not value or len(value) > 32000):
        raise ValueError(f'{label} must be nonempty text or null for unknown')


def cost(value, label):
    if value is not None and (type(value) not in (int, float) or not __import__('math').isfinite(value) or value < 0):
        raise ValueError(f'{label} must be a nonnegative finite number or null for unknown')


def checked_ref(project, ref):
    p.fields(ref, ['file', 'sha256'], 'source identity')
    digest(ref.get('sha256'))
    path = p.project_file(project, ref.get('file'))
    if not path.is_file() or p.sha(path.read_bytes()) != ref['sha256']:
        raise ValueError(f'Source identity changed or missing: {ref.get("file")}')
    return path


def request_spec(project, value):
    allowed = ['format', 'version', 'local_request_id', 'provider', 'capability', 'requested_model',
               'prompt', 'references', 'settings', 'intended_asset_id', 'authorized_scope', 'estimated_cost']
    p.fields(value, allowed, 'generation request')
    if value.get('format') != FORMAT or type(value.get('version')) is not int or value['version'] != 1:
        raise ValueError(f'Expected {FORMAT} version 1')
    identifier(value.get('local_request_id'), 'local_request_id')
    spec = copy.deepcopy(value)
    for key in ['provider', 'capability', 'requested_model', 'prompt', 'intended_asset_id']:
        nullable_text(spec.setdefault(key, None), key)
    if not isinstance(spec.get('references'), list) or len(spec['references']) > 64:
        raise ValueError('references must explicitly list at most 64 local source identities')
    for ref in spec['references']: checked_ref(project, ref)
    if not isinstance(spec.get('settings'), dict): raise ValueError('settings must be an explicit object')
    authority = spec.get('authorized_scope')
    p.fields(authority, ['source', 'cost_limit', 'currency'], 'authorized_scope')
    for key in ['source', 'currency']: nullable_text(authority.setdefault(key, None), key)
    cost(authority.setdefault('cost_limit', None), 'cost_limit')
    cost(spec.setdefault('estimated_cost', None), 'estimated_cost')
    if len(canonical(spec)) > 131072: raise ValueError('Request exceeds 128 KiB')
    return spec


def ledger_path(project): return project/'plans/generation-ledger.json'


def load(project):
    path = ledger_path(project)
    value = p.load(path) if path.exists() else {'version': 1, 'requests': []}
    if value.get('version') != 1 or not isinstance(value.get('requests'), list):
        raise ValueError('Unsupported generation ledger; preserve it and repair its schema explicitly')
    return value


def find(ledger, id):
    rows = [r for r in ledger['requests'] if r.get('local_request_id') == id]
    if len(rows) != 1 or rows[0].get('format') != FORMAT:
        raise ValueError('Request is absent, duplicated, or legacy; use an explicit version-1 request without overwriting history')
    return rows[0]


def summary(project, row):
    stale = []
    for ref in row['references']:
        try: checked_ref(project, ref)
        except (ValueError, OSError): stale.append(ref['file'])
    for output in row['outputs']:
        try: checked_ref(project, output['saved'])
        except (ValueError, OSError): stale.append(output['saved']['file'])
    return {'ok': not stale, 'local_request_id': row['local_request_id'], 'status': row['status'],
            'request_fingerprint': row['request_fingerprint'], 'outputs': row['outputs'],
            'selected_output': row['selected_output'], 'stale_files': stale,
            'unknowns': [key for key in ['provider', 'requested_model', 'provider_request_id', 'actual_model_returned',
                                         'estimated_cost', 'reported_cost'] if row.get(key) is None],
            'authorized_scope': row['authorized_scope'], 'next_action': NEXT[row['status']] if not stale else 'Restore the recorded bytes or explicitly review changed sources; selection is blocked.',
            'ledger': str(ledger_path(project)), 'event_count': len(row['attempts']),
            'submits_requests': False}


def record(project, file):
    project = Path(project).resolve(); raw = Path(file).read_bytes()
    with project_lock(project):
        spec = request_spec(project, json.loads(raw)); ledger = load(project)
        # Authority and local labels do not make an otherwise identical request a new remote job.
        fingerprint = p.sha(canonical({k: v for k, v in spec.items() if k not in ['local_request_id', 'authorized_scope', 'estimated_cost']}))
        for existing in ledger['requests']:
            if existing.get('local_request_id') == spec['local_request_id']:
                if existing.get('format') != FORMAT or existing.get('request_spec_sha256') != p.sha(canonical(spec)):
                    raise ValueError('Request identity already exists with different content; reconcile the original request')
                return {**summary(project, existing), 'cached': True}
            if existing.get('request_fingerprint') == fingerprint:
                raise ValueError(f'Existing request {existing.get("local_request_id")} has this fingerprint; reconcile it before recording another charged request')
        row = {**spec, 'request_fingerprint': fingerprint, 'request_spec_sha256': p.sha(canonical(spec)),
               'status': 'pending', 'provider_request_id': None, 'actual_model_returned': None,
               'reported_cost': None, 'outputs': [], 'selected_output': None, 'attempts': []}
        if Path(file).read_bytes() != raw: raise ValueError('Request changed during recording')
        ledger['requests'].append(row); studio.write(ledger_path(project), ledger)
        return summary(project, row)


def reconcile(project, id, file):
    project = Path(project).resolve(); raw = Path(file).read_bytes(); event = json.loads(raw)
    allowed = ['version', 'event_id', 'state', 'provider_request_id', 'actual_model_returned', 'reported_cost', 'outputs', 'selected_output_sha256', 'note']
    p.fields(event, allowed, 'generation event')
    if type(event.get('version')) is not int or event['version'] != 1: raise ValueError('Expected generation event version 1')
    identifier(event.get('event_id'), 'event_id')
    if event.get('state') not in STATES[1:]: raise ValueError('Event state must be submitted, uncertain, retrieved or selected')
    for key in ['provider_request_id', 'actual_model_returned', 'note']: nullable_text(event.get(key), key)
    cost(event.get('reported_cost'), 'reported_cost')
    outputs = event.get('outputs', [])
    if not isinstance(outputs, list) or len(outputs) > 32: raise ValueError('A receipt supports at most 32 existing outputs')
    if outputs and event['state'] != 'retrieved': raise ValueError('New outputs require a retrieved event')
    if event.get('selected_output_sha256') is not None and event['state'] != 'selected': raise ValueError('Output selection requires a selected event')
    event_hash = p.sha(canonical(event))
    with project_lock(project):
        ledger = load(project); row = find(ledger, id)
        for previous in row['attempts']:
            if previous['event_id'] == event['event_id']:
                if previous['sha256'] != event_hash: raise ValueError('Event ID already records different content')
                return {**summary(project, row), 'cached': True}
        permitted = {'pending': ['submitted', 'uncertain', 'retrieved'], 'submitted': ['uncertain', 'retrieved'],
                     'uncertain': ['uncertain', 'retrieved'], 'retrieved': ['retrieved', 'selected'], 'selected': ['retrieved', 'selected']}
        if event['state'] not in permitted[row['status']]: raise ValueError(f'Cannot change {row["status"]} to {event["state"]}; reconcile existing results instead of resubmitting')
        for ref in row['references']: checked_ref(project, ref)
        pinned = []
        for output in outputs:
            p.fields(output, ['file', 'sha256', 'provider_output_id'], 'returned output')
            nullable_text(output.get('provider_output_id'), 'provider_output_id')
            ref = {key: output.get(key) for key in ['file', 'sha256']}; source = checked_ref(project, ref)
            data = source.read_bytes()
            # Decode real pixels before accepting an image result. Audio/video use their separate import paths.
            _, info = p.decoded(source)
            if info['sha256'] != output['sha256']: raise ValueError('Returned image changed during decoding')
            saved = project/'assets/raw/generation'/identifier(id, 'request ID')/(output['sha256']+'.bin')
            pinned.append((source, data, saved))
            prior = next((x for x in row['outputs'] if x['sha256'] == output['sha256']), None)
            alias = {'returned': ref, 'provider_output_id': output.get('provider_output_id')}
            if prior:
                if alias not in prior['receipts']: prior['receipts'].append(alias)
            else:
                row['outputs'].append({'sha256': output['sha256'], 'saved': {'file': p.relative(project, saved), 'sha256': output['sha256']},
                                       'width': info['width'], 'height': info['height'], 'frames': info['frames'], 'format': info['format'], 'receipts': [alias]})
        if event['state'] == 'retrieved' and not row['outputs']: raise ValueError('Retrieved requires at least one verified local image output')
        if event['state'] == 'selected':
            digest(event.get('selected_output_sha256'))
            chosen = next((x for x in row['outputs'] if x['sha256'] == event['selected_output_sha256']), None)
            if not chosen: raise ValueError('Select an output SHA-256 already retrieved for this request')
            checked_ref(project, chosen['saved']); row['selected_output'] = chosen['saved']
        for key in ['provider_request_id', 'actual_model_returned', 'reported_cost']:
            if event.get(key) is not None:
                if row.get(key) is not None and row[key] != event[key]: raise ValueError(f'Conflicting recorded {key}; preserve the original request identity')
                row[key] = event[key]
        if Path(file).read_bytes() != raw: raise ValueError('Receipt changed during reconciliation')
        for source, data, saved in pinned:
            if source.read_bytes() != data: raise ValueError('Returned output changed during reconciliation')
            saved.parent.mkdir(parents=True, exist_ok=True)
            if saved.exists():
                if saved.read_bytes() != data: raise ValueError('Saved output snapshot changed')
            else:
                # A crash can leave an unreferenced content-addressed snapshot; a retry verifies and reuses it.
                with saved.open('xb') as handle: handle.write(data)
        row['status'] = event['state']
        row['attempts'].append({'event_id': event['event_id'], 'sha256': event_hash, 'at': datetime.now(timezone.utc).isoformat(), 'event': event})
        studio.write(ledger_path(project), ledger)
        return summary(project, row)


def add_parsers(group):
    sub = group.add_parser('request', help='Record and reconcile existing generation requests; never submit').add_subparsers(dest='request_action', required=True)
    q = sub.add_parser('record'); q.add_argument('file', type=Path)
    q = sub.add_parser('reconcile'); q.add_argument('id'); q.add_argument('--receipt', type=Path, required=True)
    q = sub.add_parser('inspect'); q.add_argument('id', nargs='?')


def run(args, project):
    if args.request_action == 'record': return record(project, args.file)
    if args.request_action == 'reconcile': return reconcile(project, args.id, args.receipt)
    ledger = load(project)
    if args.id: return summary(project, find(ledger, args.id))
    managed = [r for r in ledger['requests'] if r.get('format') == FORMAT]
    return {'requests': [{'id': r['local_request_id'], 'status': r['status'], 'outputs': len(r['outputs']), 'next_action': NEXT[r['status']]} for r in managed],
            'legacy_records': len(ledger['requests'])-len(managed), 'ledger': str(ledger_path(project)), 'submits_requests': False}
