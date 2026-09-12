"""Validated recipe bundles, without capture, rendering or presentation side effects."""
import tempfile
from pathlib import Path
import studio
from . import production, revisions, scene_runtime
from .project import locations, project_lock
from .rendering import _pcm_bytes


def build(project, request, destination):
    from . import recipe_config
    resolution = recipe_config.resolve(project, request) if request.get('format') == recipe_config.FORMAT else None
    if resolution: request = resolution['request']
    revisions.fields(request, {'format', 'schema_version', 'id', 'revision', 'title', 'notes', 'views', 'default', 'scope',
                              'long_edge', 'supersample', 'editions', 'documents', 'audio_selection'}, 'iteration request')
    if request.get('format') != 'ambiance-iteration-request' or request.get('schema_version') != 1:
        raise ValueError('Expected ambiance-iteration-request schema_version 1')
    destination = Path(destination).resolve(); project = project.resolve()
    if not destination.is_relative_to(project): raise ValueError('Recipe bundle must stay inside its project')
    scene_path, catalog_path = locations(project); scene = studio.read(scene_path); catalog = studio.read(catalog_path)
    recipe = {k: request[k] for k in ['id', 'revision', 'title', 'notes', 'views', 'default', 'scope', 'long_edge', 'supersample', 'editions'] if k in request}
    recipe.update(format='ambiance-iteration', schema_version=2, capture_selection=str((destination/'capture-selection.json').relative_to(project)))
    production.validate_recipe(recipe)
    if revisions.manifest_path(project, recipe['revision']).exists(): raise ValueError('Initializer needs a fresh revision ID; existing recipes can still resume captured work')
    audio = dict(request.get('audio_selection', {})); masters = list(audio.get('masters', []))
    for edition in recipe['editions']:
        if edition['role'] != 'silent':
            _pcm_bytes(studio.inside(project, edition['audio']), scene['canvas']['loop_seconds']*edition.get('repeats', 1))
            if edition['audio'] not in masters: masters.append(edition['audio'])
    if masters: audio['masters'] = masters
    selection = dict(format=revisions.SELECTION, schema_version=1, scene=str(scene_path.relative_to(project)), catalog=str(catalog_path.relative_to(project)),
                     documents=request.get('documents', {}), audio=audio)
    collector = revisions.collect(project, selection)
    plan = scene_runtime.scene_bridge('view-plan', scene, catalog, {'requests': [{'id': v} for v in recipe['views']],
        'options': {k: recipe[k] for k in ['long_edge', 'supersample'] if k in recipe}})
    if any(any(view['output'][axis] % 2 for axis in ['width', 'height']) for view in plan['views']):
        raise ValueError('Movie dimensions must be even')
    inputs = revisions.unique(collector.refs+collector.origins+(resolution['inputs'] if resolution else []))
    return {'recipe': recipe, 'selection': selection, 'plan': plan, 'inputs': inputs, 'resolution': resolution}


def initialize(project, request, out, *, complete_bundle=None):
    out = Path(out).resolve()
    with project_lock(project):
        if out.exists(): raise ValueError('Recipe destination already exists')
        built = build(project, request, out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.iteration-init-', dir=out.parent) as temporary:
            bundle = Path(temporary)/'bundle'; bundle.mkdir()
            studio.write(bundle/'iteration.json', built['recipe']); studio.write(bundle/'capture-selection.json', built['selection'])
            studio.write(bundle/'inputs.json', built['inputs']); studio.write(bundle/'job-plan.json', built['plan'])
            if built['resolution']: studio.write(bundle/'config-resolution.json', built['resolution'])
            if complete_bundle is not None: complete_bundle(bundle, built)
            if revisions.changed(project, built['inputs']): raise ValueError('Recipe inputs changed during initialization')
            if out.exists(): raise ValueError('Recipe destination appeared during initialization')
            bundle.rename(out)
    return {'ok': True, 'recipe': str(out/'iteration.json'), 'selection': str(out/'capture-selection.json'),
            'inputs': str(out/'inputs.json'), 'job_plan': str(out/'job-plan.json'), 'views': built['recipe']['views'],
            'roles': [e['role'] for e in built['recipe']['editions']], 'meaning': 'Initialized only; no revision captured, media produced or review selected.'}
