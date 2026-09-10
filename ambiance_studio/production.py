"""Inspectable, restartable local iteration runs over the existing media tools."""
from datetime import datetime, timezone
from pathlib import Path
import os
import time

import studio
from . import deliveries, revisions


def add_parsers(sub):
    group = sub.add_parser('delivery', help='Register movie sets and select the current review').add_subparsers(dest='action', required=True)
    q = group.add_parser('import'); q.add_argument('file', type=Path); q.add_argument('--dry-run', action='store_true')
    group.add_parser('list')
    q = group.add_parser('inspect'); q.add_argument('id')
    q = group.add_parser('handoff'); q.add_argument('id'); q.add_argument('--out', type=Path, required=True)
    q = group.add_parser('present'); q.add_argument('id'); q.add_argument('--by', required=True)
    q.add_argument('--note', default=''); q.add_argument('--channel', choices=['review', 'release'], default='review'); q.add_argument('--expect-selection')
    group = sub.add_parser('iteration', help='Produce and present a recorded local iteration').add_subparsers(dest='action', required=True)
    q = group.add_parser('run'); q.add_argument('file', type=Path); q.add_argument('--by', required=True)
    group.add_parser('list')
    q = group.add_parser('inspect'); q.add_argument('id')
    group = sub.add_parser('feedback', help='Keep observations tied to exact movie versions').add_subparsers(dest='action', required=True)
    q = group.add_parser('add'); q.add_argument('delivery'); q.add_argument('--role', choices=list(deliveries.ROLES), required=True)
    q.add_argument('--time', type=float, required=True); q.add_argument('--note', required=True); q.add_argument('--by', required=True)
    q = group.add_parser('list'); q.add_argument('delivery')


def run_file(project, id):
    return studio.inside(project, f'runs/{revisions.identifier(id)}/run.json')


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


def overview(project, alias, base_url, fingerprints=None):
    selected = deliveries.latest(project, fingerprints=fingerprints)
    history = deliveries.listing(project, fingerprints)
    def link(data):
        if not data:
            return data
        data['watch_url'] = f'{base_url}/projects/{alias}/deliveries/{data["id"]}'
        for role, entry in data.get('editions', {}).items():
            entry['watch_url'] = data['watch_url']+'?role='+role
            entry['media_url'] = f'{base_url}/media/{alias}/{data["id"]}/{role}'
        return data
    selected['delivery'] = link(selected.get('delivery'))
    for entry in history:
        link(entry)
    errors = []; checks = []; gates = None; working = {}
    current_data = selected.get('delivery')
    try:
        conf = studio.read(project/'ambiance-project.json')
        for kind in ['scene', 'catalog']:
            path = studio.inside(project, conf[kind])
            digest = fingerprints.digest(path) if fingerprints else studio.digest(path)
            captured = (current_data or {}).get('working_inputs', {}).get(kind)
            working[kind] = {'sha256': digest, 'matches_selected': digest == captured['sha256'] if captured else None}
    except (OSError, ValueError, KeyError, TypeError) as error:
        errors.append('Working scene unavailable: '+str(error))
    try:
        context = None
        if current_data:
            edition = current_data['editions'][current_data['default_role']]
            if edition['revision']:
                context = revisions.review_context(project, edition['revision'], edition['edition'])
        gates = studio.gate_status(project, context)
        review_dir = context['review_dir'] if context else project/'reviews'
        for gate, state in gates['gates'].items():
            if state['state'] == 'passed':
                continue
            path = review_dir/f'{gate}.json'
            receipt = studio.read(path) if path.exists() else {}
            unfinished = [{'id': check['id'], 'result': check['result'], 'note': check.get('note', '')}
                          for check in receipt.get('checks', []) if check.get('result') != 'pass']
            checks.append({'gate': gate, 'state': state['state'], 'reasons': state['reasons'], 'criteria': unfinished})
    except (OSError, ValueError, KeyError, TypeError) as error:
        errors.append('Review status unavailable: '+str(error))
    from . import planning
    try:
        inventory = planning.inspect(project)
        ready = [{'id': item['id'], 'action': item['next_action']} for item in inventory['items']
                 if not item['complete_for_scope'] and not item['blocked_by']][:5] if inventory['ok'] else []
        inventory_errors = inventory['errors']
    except (OSError, ValueError, KeyError, TypeError) as error:
        ready = []; inventory_errors = [str(error)]
    return {'ok': True, 'project': alias, 'current_url': f'{base_url}/projects/{alias}',
            'current': selected, 'release': deliveries.latest(project, 'release', fingerprints),
            'history': history, 'working': working, 'open_checks': checks, 'ready_work': ready,
            'inventory_errors': inventory_errors, 'errors': errors, 'runs': runs(project)[:10],
            'release_ready': gates['release_ready'] if gates else False,
            'check_subject': gates['subject'] if gates else None}


def validate_recipe(recipe):
    revisions.fields(recipe, {'format', 'schema_version', 'id', 'title', 'notes', 'revision',
                              'capture_selection', 'width', 'supersample', 'editions', 'default_role'}, 'iteration')
    if recipe.get('format') != 'ambiance-iteration' or recipe.get('schema_version') != 1:
        raise ValueError('Expected ambiance-iteration schema_version 1')
    id = revisions.identifier(recipe['id']); revisions.identifier(recipe['revision'])
    if len(id) > 80:
        raise ValueError('Iteration ID must be at most 80 characters')
    entries = recipe.get('editions')
    if not isinstance(entries, list) or not entries:
        raise ValueError('Iteration requires editions')
    roles = set()
    for entry in entries:
        revisions.fields(entry, {'role', 'audio', 'audio_run', 'audio_provenance', 'repeats'}, 'iteration edition')
        role = entry.get('role')
        if role not in deliveries.ROLES or role in roles:
            raise ValueError('Iteration soundtrack roles must be unique')
        roles.add(role)
        if role != 'silent' and not entry.get('audio'):
            raise ValueError('Sound editions require an explicit PCM source')
        if role == 'silent' and (entry.get('audio') or entry.get('repeats', 1) != 1):
            raise ValueError('Silent edition uses one picture loop')
        if not isinstance(entry.get('repeats', 1), int) or isinstance(entry.get('repeats', 1), bool) or entry.get('repeats', 1) < 1:
            raise ValueError('Repeats must be a positive integer')
    if recipe.get('default_role', entries[0]['role']) not in roles:
        raise ValueError('Default soundtrack must be produced')


def iteration(project, recipe, actor):
    from .cli import parser, run
    from .project import project_lock
    validate_recipe(recipe)
    id = recipe['id']; path = run_file(project, id); directory = path.parent
    with project_lock(project):
        if path.exists():
            state = studio.read(path)
            if state['recipe'] != recipe:
                raise ValueError('Run recipe changed; choose a new iteration ID')
            if state['state'] == 'complete':
                for step_record in state['steps'].values():
                    if any(not deliveries.intact(project, item)['ok'] for item in step_record['outputs']):
                        raise ValueError('Completed run output changed; use a new iteration ID')
                if not deliveries.inspect(project, id)['ok']:
                    raise ValueError('Completed delivery dependencies changed; inspect the saved delivery')
                return {'ok': True, 'run': state, 'reused': True}
            if (directory/'active.lock').exists():
                raise ValueError('Run is active or interrupted with a lock; verify its process before removing active.lock')
        else:
            directory.mkdir(parents=True, exist_ok=False)
            state = {'id': id, 'recipe': recipe, 'started_utc': deliveries.now(),
                     'expected_selection': deliveries.selection_token(project), 'steps': {}, 'attempts': {}}
        fd = os.open(directory/'active.lock', os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        state.update(state='running', pid=os.getpid(), updated_utc=deliveries.now(), error=None)
        studio.write(path, state)
    start = time.monotonic()
    def save(stage):
        state.update(stage=stage, updated_utc=deliveries.now(), elapsed_seconds=time.monotonic()-start)
        studio.write(path, state)
    def step(name, arguments):
        save(name)
        completed = state['steps'].get(name)
        if completed:
            for item in completed['outputs']:
                if not deliveries.intact(project, item)['ok']:
                    raise ValueError(f'Completed {name} output changed; use a new iteration ID')
            return completed['result']
        # Reconcile an edition recorded just before an interrupted run-state save.
        edition_id = recipe['id']+('-silent' if name == 'picture' else '-'+name)
        receipt_path = revisions.edition_path(project, recipe['revision'], edition_id)
        if receipt_path.exists():
            receipt = revisions.load_edition(project, recipe['revision'], edition_id)
            output_dir = studio.inside(project, receipt['output']['path']).parent
            if output_dir.parent != directory:
                raise ValueError('Existing edition belongs to a different production run')
            report = output_dir/('render-report.json' if name == 'picture' else 'compose-report.json')
            result = studio.read(report)
            result.update(report=str(report), edition={'id': edition_id, 'revision': recipe['revision'], 'receipt': str(receipt_path)})
            if not result.get('ok'):
                raise ValueError('Recorded edition has no completed production report')
            files = [result['output'], report, result['verification']['report'], receipt_path]
            outputs = [deliveries.reference(project, revisions.relative(project, file)) for file in files]
            for item in receipt['dependencies']:
                if not deliveries.intact(project, item)['ok']:
                    raise ValueError('Recorded edition changed while the run was interrupted')
            state['steps'][name] = {'result': result, 'outputs': outputs}; save(name)
            return result
        attempt = state['attempts'].get(name, 0)+1
        state['attempts'][name] = attempt
        out = directory/f'{name}-{attempt}'
        arguments = ['--project', str(project), *arguments, '--out', str(out)]
        state['active_command'] = arguments; save(name)
        result = run(parser().parse_args(arguments))
        if not result.get('ok', True):
            raise ValueError(f'{name} failed; inspect {out}')
        files = [result['output'], result['report'], result['verification']['report']]
        if result.get('edition'):
            files.append(result['edition']['receipt'])
        outputs = [deliveries.reference(project, revisions.relative(project, file)) for file in files]
        state['steps'][name] = {'result': result, 'outputs': outputs}; save(name)
        return result
    try:
        if recipe.get('capture_selection'):
            save('capture')
            selection = studio.inside(project, recipe['capture_selection'])
            if not revisions.manifest_path(project, recipe['revision']).exists():
                revisions.capture(project, recipe['revision'], selection)
            elif revisions.load(project, recipe['revision'])['selection'] != studio.read(selection):
                raise ValueError('Existing revision selection differs from the iteration recipe')
        revisions.render_context(project, recipe['revision'])
        args = ['render', 'video', '--revision', recipe['revision'], '--edition', id+'-silent']
        for key in ['width', 'supersample']:
            if key in recipe:
                args += ['--'+key, str(recipe[key])]
        picture = step('picture', args)
        entries = []
        for entry in recipe['editions']:
            role = entry['role']
            if role == 'silent':
                result = picture
            else:
                args = ['media', 'compose', picture['output'], '--revision', recipe['revision'],
                        '--edition', id+'-'+role, '--picture-receipt', revisions.relative(project, picture['report']),
                        '--audio', str(studio.inside(project, entry['audio'])), '--repeats', str(entry.get('repeats', 1))]
                for key in ['audio_run', 'audio_provenance']:
                    if entry.get(key):
                        args += ['--'+key.replace('_', '-'), entry[key]]
                result = step(role, args)
            entries.append({'role': role, 'revision': recipe['revision'], 'edition': result['edition']['id']})
        save('register')
        declaration = {'format': deliveries.SELECTION, 'schema_version': 1, 'id': id,
                       'title': recipe.get('title', id), 'notes': recipe.get('notes', ''), 'editions': entries,
                       'default_role': recipe.get('default_role', entries[0]['role'])}
        picture_dir = Path(picture['report']).parent
        for kind in ['scene', 'catalog']:
            declaration[kind+'_snapshot'] = revisions.relative(project, picture_dir/(kind+'.snapshot.json'))
        contacts = Path(picture['verification']['report']).parent/'contacts/decoded-0000.png'
        if contacts.exists():
            declaration['poster'] = revisions.relative(project, contacts)
        deliveries.register(project, declaration)
        save('present')
        selected = deliveries.present(project, id, actor, recipe.get('notes', ''), expected=state['expected_selection'])
        state.update(state='complete', selection=selected['selection'], finished_utc=deliveries.now())
        save('complete')
        return {'ok': True, 'run': state, 'delivery': id}
    except BaseException as error:
        state.update(state='interrupted' if isinstance(error, KeyboardInterrupt) else 'failed', error=str(error),
                     recovery='Rerun the unchanged recipe to reuse completed steps. For stale_selection, inspect and present the saved delivery explicitly.')
        save(state['state'])
        raise
    finally:
        (directory/'active.lock').unlink(missing_ok=True)


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
        if args.action == 'run':
            return iteration(project, studio.read(args.file), args.by)
        if args.action == 'inspect':
            return {'ok': True, 'run': studio.read(run_file(project, args.id))}
        return {'ok': True, 'runs': runs(project)}
    if args.action == 'add':
        return deliveries.feedback(project, args.delivery, args.role, args.time, args.note, args.by)
    return {'ok': True, 'feedback': deliveries.feedback_list(project, args.delivery)}


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
    for role, entry in selected['editions'].items():
        lines.append(f'- [{entry["label"]}]({exact_url}?role={role}): {entry["duration_seconds"]} seconds; `{entry["movie"]["path"]}`; SHA-256 `{entry["movie"]["sha256"]}`.')
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
        studio.write(stage/'handoff.json', {'delivery': selected, 'overview': data, 'watch_url': exact_url})
        (stage/'handoff.md').write_text('\n'.join(lines))
        stage.rename(out)
    return {'ok': selected['ok'], 'id': id, 'directory': str(out), 'watch_url': exact_url}
