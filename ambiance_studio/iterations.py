"""Restartable iteration execution over typed media jobs and saved receipts."""
import os
from pathlib import Path

import studio
from . import deliveries, project_references, revision_capture
from .errors import CommandError
from .iteration_plan import (
    iteration_preflight, production_readiness, record_iteration_scope,
    validate_recipe, view_job_plan,
)
from .media_operations import ComposeRequest, MediaExecutor, PictureRequest, execute_job
from .iteration_steps import IterationProgress, run_file


def _composition(project, recipe, entry, picture, edition, view=None):
    return ComposeRequest(
        revision=recipe['revision'], edition=edition, view=view,
        picture=Path(picture['output']), picture_receipt=project_references.relative(project, picture['report']),
        audio=studio.inside(project, entry['audio']), repeats=entry.get('repeats', 1),
        audio_run=entry.get('audio_run'), audio_provenance=entry.get('audio_provenance'),
    )


def _produce_delivery(project, recipe, progress):
    """Both recipe versions share picture reuse, composition and registration."""
    paired = recipe['schema_version'] == 2
    id = recipe['id']
    if paired:
        progress.save('preflight')
        plan = view_job_plan(project, recipe, progress.directory, progress.state)
        if progress.state.get('plan') and progress.state['plan'] != plan:
            raise ValueError('Captured job inputs or raster plan changed; choose a new iteration ID')
        progress.state['plan'] = plan
        progress.save('preflight')
    else:
        jobs = [{'key': 'picture', 'stage': 'picture', 'role': 'silent', 'edition': id+'-silent',
                 'view': None, 'output': {'width': recipe.get('width'), 'height': None}}]
        jobs += [{'key': e['role'], 'stage': 'compose', 'role': e['role'], 'edition': id+'-'+e['role'], 'view': None}
                 for e in recipe['editions'] if e['role'] != 'silent']
        plan = {'jobs': jobs, 'audio_inputs': []}
    editions = {entry['role']: entry for entry in recipe['editions']}
    pictures = {}
    selected = []
    for job in plan['jobs']:
        if project_references.changed(project, plan['audio_inputs']):
            raise ValueError('Audio inputs changed after job preflight')
        view, role = job['view'], job['role']
        if job['stage'] == 'picture':
            request = PictureRequest(revision=recipe['revision'], edition=job['edition'], view=view,
                                     width=job['output']['width'], height=job['output']['height'],
                                     supersample=recipe.get('supersample', 1))
            result = progress.step(job['key'], request)
            pictures[view] = result
            if 'silent' not in editions:
                continue
        else:
            request = _composition(project, recipe, editions[role], pictures[view], job['edition'], view)
            result = progress.step(job['key'], request)
        entry = {'role': role, 'revision': recipe['revision'], 'edition': result['edition']['id']}
        if paired:
            entry['view'] = view
        selected.append(entry)
    progress.save('register')
    declaration = {'format': deliveries.SELECTION, 'schema_version': recipe['schema_version'], 'id': id,
                   'title': recipe.get('title', id), 'notes': recipe.get('notes', '')}
    if paired:
        declaration.update(entries=selected, default=recipe['default'])
    else:
        # Legacy selection order determines the default role when it is omitted.
        selected.sort(key=lambda entry: list(editions).index(entry['role']))
        declaration.update(editions=selected, default_role=recipe.get('default_role', selected[0]['role']))
    picture = next(iter(pictures.values()))
    picture_dir = Path(picture['report']).parent
    for kind in ['scene', 'catalog']:
        declaration[kind+'_snapshot'] = project_references.relative(project, picture_dir/(kind+'.snapshot.json'))
    if not paired:
        contacts = Path(picture['verification']['report']).parent/'contacts/decoded-0000.png'
        if contacts.exists():
            declaration['poster'] = project_references.relative(project, contacts)
    deliveries.register(project, declaration)
    return declaration


def iteration(project, recipe, actor, *, present=True, executor: MediaExecutor = execute_job):
    from .project import project_lock
    from . import run_control
    import uuid
    validate_recipe(recipe)
    if not isinstance(actor,str) or not actor.strip():raise ValueError('Identify who runs this iteration with --by')
    id = recipe['id']; path = run_file(project, id); directory = path.parent
    with project_lock(project):
        if path.exists():
            state = studio.read(path)
            if state.get('present', True) != present: raise ValueError('Run presentation mode changed; use a new iteration ID')
            if state['recipe'] != recipe:
                raise ValueError('Run recipe changed; choose a new iteration ID')
            if state['state'] == 'complete':
                for step_record in state['steps'].values():
                    if any(not deliveries.intact(project, item)['ok'] for item in step_record['outputs']):
                        raise ValueError('Completed run output changed; use a new iteration ID')
                if not deliveries.inspect(project, id)['ok']:
                    raise ValueError('Completed delivery dependencies changed; inspect the saved delivery')
                readiness = production_readiness(project, stage='export', revision=recipe['revision'])
                return {'ok': recipe.get('scope') != 'final' or readiness['ready'], 'run': state, 'reused': True, 'production_readiness': readiness}
            if (directory/'active.lock').exists():
                if run_control.live_children(project, state): raise ValueError('Owned children remain; cancel/reconcile this run before resume')
                if run_control.owner_state(state) != 'absent':
                    raise ValueError('Run owner is present or unverified; inspect before resuming')
                lock = directory/'active.lock'
                if lock.read_text().strip() and studio.read(lock).get('run_uuid') != state.get('run_uuid'):
                    raise ValueError('Run lock identity differs')
                lock.unlink()

        else:
            directory.mkdir(parents=True, exist_ok=False)
            state = {'id': id, 'recipe': recipe, 'started_utc': deliveries.now(),
                     'expected_selection': deliveries.selection_token(project), 'steps': {}, 'attempts': {}}
        fd = os.open(directory/'active.lock', os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        state.update(state='running', present=present, run_uuid=uuid.uuid4().hex, owner=run_control.identity(os.getpid()), pid=os.getpid(), updated_utc=deliveries.now(), error=None)
        studio.write(directory/'active.lock', {'run_uuid': state['run_uuid'], 'owner': state['owner']})
        studio.write(path, state)
    tracker = run_control.Tracker(project, state)
    try: tracker.__enter__()
    except BaseException as error:
        state.update(state='failed', error=str(error)); studio.write(path, state)
        lock = directory/'active.lock'
        if lock.exists() and studio.read(lock).get('run_uuid') == state['run_uuid']: lock.unlink()
        raise
    progress = IterationProgress(project, state, tracker, executor)
    save = progress.save
    try:
        if recipe.get('capture_selection'):
            save('capture')
            selection = studio.inside(project, recipe['capture_selection'])
            if not revision_capture.manifest_path(project, recipe['revision']).exists():
                revision_capture.capture(project, recipe['revision'], selection)
            elif revision_capture.load(project, recipe['revision'])['selection'] != studio.read(selection):
                raise ValueError('Existing revision selection differs from the iteration recipe')
        revision_capture.render_context(project, recipe['revision'])
        preflight = iteration_preflight(project, recipe)
        state['production_preflight'] = preflight; save('production-preflight')
        if not preflight['may_render']:
            raise CommandError('Full production scope is not ready; inspect '+preflight['readiness']['report'], 'production_not_ready', 1)
        declaration = _produce_delivery(project, recipe, progress)
        state['production_readiness'] = record_iteration_scope(project, recipe, declaration)
        save('present')
        selected = deliveries.present(project, id, actor, recipe.get('notes', ''), expected=state['expected_selection']) if present else {'selection': None}
        state.update(state='complete', selection=selected['selection'], finished_utc=deliveries.now())
        save('complete')
        complete = recipe.get('scope') != 'final' or state['production_readiness']['ready']
        return {'ok': complete, 'run': state, 'delivery': id, 'production_readiness': state['production_readiness']}
    except BaseException as error:
        state.update(state='interrupted' if isinstance(error, KeyboardInterrupt) else 'failed', error=str(error),
                     recovery='Rerun the unchanged recipe to reuse completed steps. For stale_selection, inspect and present the saved delivery explicitly.')
        save(state['state'])
        raise
    finally:
        tracker.__exit__(None, None, None)
        lock = directory/'active.lock'
        if lock.exists() and studio.read(lock).get('run_uuid') == state['run_uuid']: lock.unlink()
