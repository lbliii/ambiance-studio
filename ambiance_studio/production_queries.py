"""Bounded operational projections; existing evaluators retain readiness authority."""
import os
from . import feedback


def excerpt(value, maximum=160):
    value = str(value)
    return value if len(value) <= maximum else value[:maximum-1]+'…'


def saved_step_result(result):
    """Keep resumable handles; sample arrays already live in hashed output reports."""
    compact = {k: result[k] for k in ['ok', 'output', 'report', 'output_sha256', 'output_expectations', 'edition'] if k in result}
    compact['verification'] = {k: result.get('verification', {})[k] for k in ['ok', 'report'] if k in result.get('verification', {})}
    compact['detail_storage'] = 'The report and verification paths contain full results; outputs pin their exact bytes.'
    return compact


def run_summary(row, project=None):
    from .run_control import effective
    health = effective(row, project)
    result = {k: row[k] for k in ['id', 'state', 'run_uuid', 'stage', 'started_utc', 'updated_utc', 'elapsed_seconds'] if k in row}
    result.update(health)
    if row.get('error'): result['error'] = excerpt(row['error'])
    if project is not None:
        result['path'] = str(project/'runs'/row['id']/'run.json')
    return result


def delivery_summary(data, entry_limit=6):
    if not data: return data
    result = {k: data[k] for k in ['id', 'schema_version', 'title', 'default', 'default_role', 'watch_url', 'created_utc'] if k in data}
    if 'notes' in data: result['notes'] = excerpt(data['notes'])
    key = 'entries' if data.get('schema_version') == 2 else 'editions'
    rows = data.get(key, {})
    result[key] = {id: {k: e[k] for k in ['id', 'view', 'role', 'duration_seconds', 'width', 'height', 'fps', 'available',
                                      'technical_evidence_current', 'watch_url'] if k in e} for id, e in list(rows.items())[:entry_limit]}
    for id, e in list(rows.items())[:entry_limit]:
        if e.get('movie'): result[key][id]['movie'] = {k: e['movie'][k] for k in ['path', 'sha256', 'bytes'] if k in e['movie']}
    result['entry_count'] = len(rows); result['entries_omitted'] = max(0, len(rows)-entry_limit)
    if data.get('error'): result['error'] = excerpt(data['error'])
    return result


def selection_summary(data):
    result = {k: data[k] for k in ['ok', 'error', 'channel'] if k in data}
    result['selection'] = {k: data['selection'][k] for k in ['delivery', 'payload_sha256', 'channel'] if k in data['selection']} if data.get('selection') else None
    result['delivery'] = delivery_summary(data.get('delivery'))
    if data.get('release'): result['release'] = {'approved': data['release'].get('approved', False)}
    return result


def next_work(project, data, limit=8, kind=None, offset=0):
    if type(limit) is not int or not 1 <= limit <= 1000 or type(offset) is not int or offset < 0:
        raise ValueError('Next-work limit must be 1–1000 with a nonnegative offset')
    if kind not in (None, 'input', 'run', 'feedback', 'production', 'coverage', 'observation'):
        raise ValueError('Unknown next-work kind')
    items = []; seen = set()
    def add(id, kind, subject, reason, command=None, decision=None, dependencies=None):
        if id in seen: return
        seen.add(id)
        row = dict(id=id, kind=kind, subject=subject, reason=excerpt(reason), dependencies=dependencies or [])
        if command: row['argv'] = ['./ambiance', '--project', str(project), *command]
        if decision: row['decision'] = decision
        items.append(row)
    for index, error in enumerate(data.get('errors', [])+data.get('inventory_errors', [])):
        add('input:'+str(index), 'input', 'working', error, ['project', 'check'])
    for aid in data.get('active_unmapped_asset_ids', []):
        add('input:unmapped:'+aid, 'input', aid, 'Active scene asset has no authored inventory accounting.', ['plan', 'inspect'])
    for run in data.get('runs', []):
        effective = run_summary(run, project)
        if effective['effective_state'] in ['interrupted', 'unknown', 'unreadable', 'failed']:
            add('run:'+run['id'], 'run', run['id'], effective.get('state_reason') or effective['effective_state'], ['iteration', 'inspect', run['id']])
    try:
        feedback_offset = 0
        while True:
            page = feedback.listing(project, state='open', limit=1000, offset=feedback_offset)
            for row in page['feedback']:
                add('feedback:'+row['id'], 'feedback', {'delivery': row['delivery'], 'feedback': row['id']}, row['note'], ['feedback', 'inspect', row['id']], 'Choose a revision or disposition for this report.')
            if page['next_offset'] is None: break
            feedback_offset = page['next_offset']
    except (OSError, ValueError, KeyError, TypeError) as error:
        add('input:feedback', 'input', 'feedback', str(error), ['feedback', 'list'])
    for row in data.get('ready_work', []):
        add('inventory:'+row['id'], 'production', row['id'], row['action'], ['plan', 'next'])
    readiness = data.get('production_readiness', {})
    for row in readiness.get('blocked', []):
        add('coverage:'+row['id'], 'coverage', row.get('subject', row['id']), row.get('action', row.get('reason', row['id'])), ['plan', 'coverage', '--stage', readiness.get('stage', 'animation')])
    for row in data.get('open_checks', []):
        add('observation:'+row['gate'], 'observation', data.get('check_subject'), '; '.join(row.get('reasons', [])) or row['state'],
            decision='Inspect the exact subject and record only observations actually made.')
    selected = [row for row in items if kind is None or row['kind'] == kind]
    return {'ok': True, 'items': selected[offset:offset+limit], 'total': len(selected), 'omitted': max(0, len(selected)-offset-limit),
            'next_offset': offset+limit if offset+limit < len(selected) else None}


def summarize(project, data):
    def checks(rows):
        return [dict(gate=row['gate'], state=row['state'], reasons=[excerpt(r) for r in row.get('reasons', [])[:2]],
                     criteria=[{k: excerpt(c[k]) for k in ['id', 'result', 'note'] if k in c} for c in row.get('criteria', [])[:2]]) for row in rows[:8]]
    result = {k: data[k] for k in ['ok', 'project', 'current_url', 'working', 'release_ready']}
    result.update(format='ambiance-project-overview', schema_version=2, current=selection_summary(data['current']), release=selection_summary(data['release']),
                  history=[delivery_summary(d, 0) for d in data['history'][:5]], history_total=len(data['history']),
                  history_omitted=max(0, len(data['history'])-5), runs=[run_summary(r, project) for r in data['runs'][:5]],
                  runs_total=data.get('runs_total', len(data['runs'])), runs_omitted=max(0, data.get('runs_total', len(data['runs']))-5),
                  open_checks=checks(data['open_checks']), open_checks_total=len(data['open_checks']),
                  ready_work=data['ready_work'][:8], errors=[excerpt(e) for e in data['errors'][:8]],
                  inventory_errors=[excerpt(e) for e in data['inventory_errors'][:8]],
                  next_work=next_work(project, data), details_argv=['./ambiance', '--project', str(project), 'project', 'overview', '--details'])
    readiness = data.get('production_readiness', {})
    result['production_readiness'] = {k: readiness[k] for k in ['ready', 'stage', 'enforced', 'phase'] if k in readiness}
    result['production_readiness']['blocked_count'] = len(readiness.get('blocked', []))
    result['framing'] = {k: data.get('framing', {}).get(k) for k in ['ok', 'intended_views']}
    result['asset_accounting'] = {'active_unmapped_count': len(data.get('active_unmapped_asset_ids', [])),
                                 'retained_unused_count': len(data.get('retained_unmapped_asset_ids', [])),
                                 'details_argv': ['./ambiance', '--project', str(project), 'plan', 'inspect']}
    return result
