"""Recipe contracts, readiness and complete view/audio job preflight."""
import hashlib
from types import SimpleNamespace

import studio
from . import deliveries, revisions
from .errors import CommandError


def production_readiness(project, **kwargs):
    from .production_coverage import evaluate
    return evaluate(project, **kwargs)

def iteration_preflight(project, recipe, stage=None):
    validate_recipe(recipe)
    scope = recipe.get('scope', 'review')
    revision = recipe['revision'] if revisions.manifest_path(project, recipe['revision']).exists() else None
    outputs = [{'view_id': v, 'roles': [e['role'] for e in recipe['editions']]}
               for v in recipe.get('views', ['authored'])]
    readiness = production_readiness(project, stage=stage or ('export' if scope == 'final' else 'animation'),
                                      revision=revision, outputs=outputs, phase='preflight')
    return {'ok': readiness['ready'], 'scope': scope, 'may_render': scope != 'final' or readiness['ready'],
            'readiness': readiness, 'output_pairs': outputs}

def record_iteration_scope(project, recipe, declaration):
    from . import production_coverage as coverage, production_plan
    manifest = revisions.load(project, recipe['revision'])
    if 'production_plan' not in manifest['controls']:
        return coverage.evaluate(project, 'export', revision=recipe['revision'])
    ctx = production_plan.load_context(project, recipe['revision']); registration_gaps = []
    for entry in declaration.get('entries', declaration.get('editions', [])):
        view = entry.get('view', 'authored')
        for exp in ctx['plan']['expectations']:
            if exp['requirement']['check'] != 'movie' or view not in exp['view_ids']: continue
            try:
                coverage.register_evidence(project, exp['id'], view,
                    revisions.relative(project, revisions.edition_path(project, entry['revision'], entry['edition'])),
                    entry['revision'], entry['role'])
            except (OSError, ValueError, KeyError, TypeError, CommandError) as error:
                if recipe.get('scope') == 'final': raise
                registration_gaps.append({'expectation_id': exp['id'], 'view_id': view,
                                          'role': entry['role'], 'reason': str(error)})
    result = coverage.evaluate(project, 'export', revision=recipe['revision'])
    if registration_gaps: result['evidence_registration_gaps'] = registration_gaps
    return result

def validate_recipe(recipe):
    revisions.fields(recipe, {'format', 'schema_version', 'id', 'title', 'notes', 'revision',
                              'capture_selection', 'width', 'long_edge', 'supersample', 'editions', 'default_role', 'views', 'default', 'scope'}, 'iteration')
    if recipe.get('format') != 'ambiance-iteration' or recipe.get('schema_version') not in [1,2]:
        raise ValueError('Expected ambiance-iteration schema_version 1 or 2')
    id = revisions.identifier(recipe['id']); revisions.identifier(recipe['revision'])
    if recipe.get('scope', 'review') not in ['proof', 'review', 'final']: raise ValueError('Iteration scope must be proof, review or final')
    if not isinstance(recipe.get('title',id),str) or not recipe.get('title',id).strip() or not isinstance(recipe.get('notes',''),str):
        raise ValueError('Iteration title and notes must be text, with a nonempty title')
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
        if entry.get('audio_run') and entry.get('audio_provenance'):
            raise ValueError('Choose one audio provenance source')
        if role != 'silent' and not entry.get('audio'):
            raise ValueError('Sound editions require an explicit PCM source')
        if role == 'silent' and (entry.get('audio') or entry.get('repeats', 1) != 1):
            raise ValueError('Silent edition uses one picture loop')
        if not isinstance(entry.get('repeats', 1), int) or isinstance(entry.get('repeats', 1), bool) or entry.get('repeats', 1) < 1:
            raise ValueError('Repeats must be a positive integer')
    if type(recipe.get('supersample',1)) is not int or recipe.get('supersample',1) not in [1,2,4]:
        raise ValueError('Supersample must be 1, 2, or 4')
    if recipe['schema_version']==1:
        if any(key in recipe for key in ['views','default','long_edge']):raise ValueError('Version 1 recipes use one authored picture')
        if recipe.get('default_role', entries[0]['role']) not in roles:raise ValueError('Default soundtrack must be produced')
    else:
        if any(key in recipe for key in ['width','default_role']):raise ValueError('Version 2 recipes use long_edge and a default view/role pair')
        views=recipe.get('views')
        if not isinstance(views,list) or not views or any(not isinstance(view,str) for view in views) or len(set(views))!=len(views):
            raise ValueError('Iteration requires unique view IDs')
        default=recipe.get('default');revisions.fields(default,{'view','role'},'iteration default')
        if set(default)!={'view','role'} or default['view'] not in views or default['role'] not in roles:raise ValueError('Default pair must be produced')
        if 'long_edge' in recipe and (type(recipe['long_edge']) is not int or recipe['long_edge']<1):raise ValueError('long_edge must be a positive integer')

def view_job_plan(project, recipe, directory, state):
    """Preflight every view, PCM master and destination before starting any encoder."""
    from . import rendering, scene_runtime
    context=revisions.render_context(project,recipe['revision']);data=revisions.load(project,recipe['revision'])
    scene=scene_runtime.load_scene_json(context['scene'].read_bytes());catalog=scene_runtime.load_scene_json(context['catalog'].read_bytes())
    options={'supersample':recipe.get('supersample',1)}
    if 'long_edge' in recipe:options['long_edge']=recipe['long_edge']
    raster=scene_runtime.scene_bridge('view-plan',scene,catalog,{'requests':[{'id':view} for view in recipe['views']], 'options':options})
    sound=[]
    for entry in recipe['editions']:
        if entry['role']=='silent':continue
        args=SimpleNamespace(**{**entry,'audio':studio.inside(project,entry['audio'])})
        collector,master=revisions.collect_edition_audio(project,data,args)
        rendering._pcm_bytes(args.audio,scene['canvas']['loop_seconds']*entry.get('repeats',1))
        sound.extend(collector.refs+collector.origins)
    jobs=[]
    for resolved in raster['views']:
        view=resolved['view'];size=resolved['output']
        if any(size[key]%2 for key in ['width','height']):raise ValueError('Native H.264 view dimensions must be even; choose another long_edge')
        for stage,role in [('picture','silent')]+[('compose',entry['role']) for entry in recipe['editions'] if entry['role']!='silent']:
            name=f'{view["id"]}.{stage}.{role}'
            suffix=hashlib.sha256(name.encode()).hexdigest()[:16]
            edition=recipe['id']+'-'+suffix
            next_out=directory/f'{name}-{state["attempts"].get(name,0)+1}'
            if next_out.exists():raise ValueError('Next attempt directory exists; inspect the saved run before resuming')
            receipt=revisions.edition_path(project,recipe['revision'],edition)
            if receipt.exists():
                bound=revisions.load_edition(project,recipe['revision'],edition)
                if studio.inside(project,bound['output']['path']).parent.parent!=directory:raise ValueError('Planned edition belongs to another run')
            jobs.append({'key':name,'view':view['id'],'stage':stage,'role':role,'edition':edition,'output':size})
    return {'raster':raster,'jobs':jobs,'audio_inputs':revisions.unique(sound),'encoder_workers':1}
