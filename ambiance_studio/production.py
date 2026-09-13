"""Production command adapters, project overview and delivery handoffs."""
from .command_output import Output, add_output
from pathlib import Path
import os

import studio
from . import deliveries, revision_reviews
from .errors import CommandError
# Compatibility exports for existing operators; implementation has one owner.
from .iteration_plan import (
    iteration_preflight, production_readiness, record_iteration_scope,
    validate_recipe, view_job_plan,
)
from .iterations import iteration
from .iteration_steps import run_file


def add_parsers(sub):
    group = sub.add_parser('delivery', help='Register movie sets and select the current review').add_subparsers(dest='action', required=True)
    q = group.add_parser('import'); q.add_argument('file', type=Path); q.add_argument('--dry-run', action='store_true')
    group.add_parser('list')
    q = group.add_parser('inspect'); q.add_argument('id')
    q = group.add_parser('handoff'); q.add_argument('id'); add_output(q, Output.ARTIFACT, type=Path, required=True)
    q = group.add_parser('present'); q.add_argument('id'); q.add_argument('--by', required=True)
    q.add_argument('--note', default=''); q.add_argument('--channel', choices=['review', 'release'], default='review'); q.add_argument('--expect-selection')
    group = sub.add_parser('iteration', help='Produce and present a recorded local iteration').add_subparsers(dest='action', required=True)
    q = group.add_parser('init'); q.add_argument('file', type=Path); add_output(q, Output.ARTIFACT, type=Path, required=True)
    q = group.add_parser('resolve'); q.add_argument('file', type=Path)
    q = group.add_parser('run'); q.add_argument('file', type=Path); q.add_argument('--by', required=True)
    q = group.add_parser('preflight'); q.add_argument('file', type=Path); q.add_argument('--stage', choices=['layout', 'assets', 'animation', 'export']); add_output(q, Output.REPORT, type=Path)
    q = group.add_parser('list'); q.add_argument('--details', action='store_true'); q.add_argument('--limit', type=int, default=20); q.add_argument('--offset', type=int, default=0)
    q = group.add_parser('inspect'); q.add_argument('id')
    q = group.add_parser('cancel'); q.add_argument('id'); q.add_argument('--expect-run', required=True)
    q = group.add_parser('reconcile'); q.add_argument('id')
    from . import feedback
    feedback.add_parsers(sub.add_parser('feedback', help='Version-bound reports and dispositions').add_subparsers(dest='action', required=True))


def runs(project):
    rows = []
    for path in (project/'runs').glob('*/run.json'):
        try:
            row = studio.read(path)
            row['process_state'] = 'finished'
            if row['state'] == 'running':
                try:
                    os.kill(row['pid'], 0)
                    row['process_state'] = 'present'
                except (ProcessLookupError, PermissionError):
                    row['process_state'] = 'unknown-or-interrupted'
            rows.append(row)
        except (OSError, ValueError, KeyError, TypeError) as error:
            rows.append({'id': path.parent.name, 'state': 'unreadable', 'error': str(error), 'started_utc': ''})
    return sorted(rows, key=lambda row: row['started_utc'], reverse=True)


def link_delivery(data, alias, base_url):
    if not data:return data
    data['watch_url']=f'{base_url}/projects/{alias}/deliveries/{data["id"]}'
    for key,entry in data.get('entries',{}).items():
        suffix=f'?view={entry["view"]}&role={entry["role"]}' if data['schema_version']==2 else '?role='+entry['role']
        entry['watch_url']=data['watch_url']+suffix
        entry['current_url']=f'{base_url}/projects/{alias}'+suffix
        entry['media_url']=f'{base_url}/media/{alias}/{data["id"]}/{key}'
    return data


def overview(project, alias, base_url, fingerprints=None, readiness_options=None, details=False):
    fingerprints = fingerprints or deliveries.Fingerprints()
    errors = []
    try:
        selected = deliveries.latest(project, fingerprints=fingerprints)
    except (OSError, ValueError, KeyError, TypeError, CommandError) as error:
        selected = {'ok': False, 'selection': None, 'delivery': None, 'error': str(error)}
        errors.append('Selected movie unavailable: '+str(error))
    history = deliveries.listing(project, fingerprints)
    selected['delivery'] = link_delivery(selected.get('delivery'),alias,base_url)
    for entry in history:
        link_delivery(entry,alias,base_url)
    checks = []; gates = None; working = {}; entry_checks = {}
    current_data = selected.get('delivery')
    try:
        conf = studio.read(project/'ambiance-project.json')
        for kind in ['scene', 'catalog']:
            path = studio.inside(project, conf[kind])
            digest = fingerprints.digest(path) if fingerprints else studio.digest(path)
            captured = (current_data or {}).get('working_inputs', {}).get(kind)
            working[kind] = {'sha256': digest, 'matches_selected': digest == captured['sha256'] if captured else None}
    except (OSError, ValueError, KeyError, TypeError, CommandError) as error:
        errors.append('Working scene unavailable: '+str(error))
    try:
        context = None
        if current_data:
            _, edition = deliveries.resolve_entry(current_data)
            if edition['revision']:
                context = revision_reviews.review_context(project, edition['revision'], edition['edition'])
        gates = studio.gate_status(project, context)
        if current_data:entry_checks=deliveries.review_states(project,current_data)
        review_dir = context['review_dir'] if context else project/'reviews'
        for gate, state in gates['gates'].items():
            if state['state'] == 'passed':
                continue
            path = review_dir/f'{gate}.json'
            receipt = studio.read(path) if path.exists() else {}
            unfinished = [{'id': check['id'], 'result': check['result'], 'note': check.get('note', '')}
                          for check in receipt.get('checks', []) if check.get('result') != 'pass']
            checks.append({'gate': gate, 'state': state['state'], 'reasons': state['reasons'], 'criteria': unfinished})
    except (OSError, ValueError, KeyError, TypeError, CommandError) as error:
        errors.append('Review status unavailable: '+str(error))
    from . import planning
    inventory = {}
    try:
        inventory = planning.inspect(project)
        ready = [{'id': item['id'], 'action': item['next_action']} for item in planning.ready_work(inventory)['ready']]
        inventory_errors = inventory['errors']
    except (OSError, ValueError, KeyError, TypeError) as error:
        ready = []; inventory_errors = [str(error)]
    from . import views
    try:
        framing = views.project_summary(project)
    except (OSError, ValueError, KeyError, TypeError, CommandError) as error:
        framing = {'ok': False, 'errors': [str(error)]}
    run_rows = runs(project)
    try:
        release = deliveries.latest(project, 'release', fingerprints)
    except (OSError, ValueError, KeyError, TypeError, CommandError) as error:
        release = {'ok': False, 'selection': None, 'delivery': None, 'error': str(error)}
        errors.append('Selected release unavailable: '+str(error))
    subjects = {'working': {'mode': 'working', **{key+'_sha256': row['sha256'] for key, row in working.items()}},
                'selected_movie': None}
    if current_data:
        subjects['selected_movie'] = {
            'mode': 'delivery', 'delivery': current_data['id'],
            'selection_sha256': selected['selection']['payload_sha256'],
            'delivery_sha256': current_data['record_sha256'],
            'entries': {key: {field: entry.get(field) for field in ['revision', 'edition', 'view', 'role', 'movie']}
                        for key, entry in current_data['entries'].items()},
        }
    result = {'ok': True, 'project': alias, 'current_url': f'{base_url}/projects/{alias}',
            'current': selected, 'release': release, 'subjects': subjects,
            'history': history, 'working': working, 'open_checks': checks, 'ready_work': ready,
            'inventory_errors': inventory_errors, 'errors': errors, 'runs': run_rows, 'runs_total': len(run_rows),
            'active_unmapped_asset_ids': inventory.get('active_unmapped_asset_ids', []),
            'retained_unmapped_asset_ids': inventory.get('retained_unmapped_asset_ids', []),
            'entry_checks':entry_checks,
            'release_ready': bool(entry_checks) and all(item['release_ready'] for item in entry_checks.values()) and
                             (not current_data.get('production_scope', {}).get('enforced') or current_data['production_scope']['ready']) if current_data else gates['release_ready'] if gates else False,
            'check_subject': gates['subject'] if gates else None, 'framing': framing,
            'production_readiness': production_readiness(project, persist=False, **(readiness_options or {}))}
    from .production_plan import PATH as plan_path
    if not current_data and (project/plan_path).exists() and not result['production_readiness']['assessment']['complete']:
        result['release_ready'] = False
    if details: return result
    from .production_queries import summarize
    return summarize(project, result)


def run_command(args, project):
    if args.command == 'delivery':
        if args.action == 'import':
            return deliveries.register(project, studio.read(args.file), args.dry_run)
        if args.action == 'list':
            return {'ok': True, 'deliveries': deliveries.listing(project), 'current': deliveries.current(project)}
        if args.action == 'inspect':
            return deliveries.inspect(project, args.id)
        if args.action == 'handoff':
            return handoff(project, args.id, args.out)
        return deliveries.present(project, args.id, args.by, args.note, args.channel, args.expect_selection)
    if args.command == 'iteration':
        if args.action == 'resolve':
            from .recipe_config import read, resolve
            return resolve(project, read(args.file))
        if args.action in ['cancel', 'reconcile']:
            from . import run_control
            return run_control.cancel(project, args.id, args.expect_run) if args.action == 'cancel' else run_control.reconcile(project, args.id)
        if args.action == 'init':
            from .iteration_recipes import initialize
            from .recipe_config import read
            return initialize(project, read(args.file), args.out)
        if args.action == 'preflight': return iteration_preflight(project, studio.read(args.file), args.stage)
        if args.action == 'run':
            return iteration(project, studio.read(args.file), args.by)
        if args.action == 'inspect':
            from .run_control import effective
            row = studio.read(run_file(project, args.id))
            return {'ok': True, 'run': row, **effective(row, project)}
        from .production_queries import run_summary
        if not 1 <= args.limit <= 1000 or args.offset < 0: raise ValueError('Run list needs limit 1–1000 and a nonnegative offset')
        rows = runs(project); selected = rows[args.offset:args.offset+args.limit]
        return {'ok': True, 'runs': selected if args.details else [run_summary(row, project) for row in selected],
                'total': len(rows), 'omitted': max(0, len(rows)-args.offset-args.limit),
                'next_offset': args.offset+args.limit if args.offset+args.limit < len(rows) else None,
                'details': 'iteration inspect ID or iteration list --details'}
    from . import feedback
    return feedback.run(args, project)


def handoff(project, id, out, alias=None, base_url='http://127.0.0.1:8783'):
    import tempfile
    out = Path(out).resolve()
    if out.exists():
        raise ValueError('Handoff output already exists; choose a fresh directory')
    alias = alias or studio.read(project/'project.json')['id']
    data = overview(project, alias, base_url)
    selected = deliveries.inspect(project, id)
    exact_url = f'{base_url}/projects/{alias}/deliveries/{id}'
    lines = [f'# {selected["title"]}', '', f'[Watch this exact version]({exact_url})', '',
             f'[Current project review]({base_url}/projects/{alias})', '', selected['notes'], '',
             '## Movies', '']
    for key, entry in selected['entries'].items():
        pair=f'view={entry["view"]}&role={entry["role"]}' if selected['schema_version']==2 else 'role='+entry['role']
        lines.append(f'- [{entry["view"]} · {entry["label"]}]({exact_url}?{pair}): {entry["duration_seconds"]} seconds; `{entry["movie"]["path"]}`; SHA-256 `{entry["movie"]["sha256"]}`.')
    entry_checks=deliveries.review_states(project,selected)
    lines+=['','## Checks for each movie','']
    for key,state in entry_checks.items():
        lines.append(f'- {key}: '+ ('release ready' if state['release_ready'] else 'review pending') +'.')
        lines.extend(f'  - {item["gate"]}: {item["state"]}. '+ '; '.join(item['reasons']) for item in state['open_checks'])
        if state.get('error'):lines.append('  - '+state['error'])
    is_current = data['current'].get('selection', {}).get('delivery') == id if data['current'].get('selection') else False
    lines += ['', '## Project checks', '', 'These checks describe the current project review subject, not an inferred approval of the movie linked above.', '']
    if is_current:
        lines += [f'- {item["gate"]}: {item["state"]}. '+ '; '.join(item['reasons']+[c['id']+': '+c['result'] for c in item['criteria']]) for item in data['open_checks']]
    else:
        lines += ['This is an earlier delivery. Consult its exact edition review records; current working/project checks are retained separately in handoff.json.']
    lines += ['', 'This handoff does not infer a human review or permission to publish. Authored creative notes remain in the project handoff.', '']
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.delivery-handoff-', dir=out.parent) as temp:
        stage = Path(temp)/'handoff'; stage.mkdir()
        studio.write(stage/'handoff.json', {'delivery': selected, 'entry_checks':entry_checks, 'overview': data, 'watch_url': exact_url})
        (stage/'handoff.md').write_text('\n'.join(lines))
        stage.rename(out)
    return {'ok': selected['ok'], 'id': id, 'directory': str(out), 'watch_url': exact_url}
