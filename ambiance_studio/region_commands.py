"""Agent-facing operations for saved art regions."""
from .command_output import Output, add_output
import copy
from pathlib import Path

from . import art_regions as ar


def add_parsers(group):
    sub=group.add_parser('region',help='Trace, frame, size and return artwork for a source region').add_subparsers(dest='region_action',required=True)
    q=sub.add_parser('init');q.add_argument('source',type=Path);q.add_argument('--id',required=True);add_output(q, Output.ARTIFACT, type=Path,required=True)
    q.add_argument('--rect',type=int,nargs=4,help='Half-open source pixel-edge rectangle')
    q.add_argument('--base',help='Bind sizing to this existing mapped source layer');q.add_argument('--view',action='append',dest='views')
    for name in ('inspect','check'):
        q=sub.add_parser(name);q.add_argument('directory',type=Path)
    q=sub.add_parser('edit');q.add_argument('directory',type=Path);q.add_argument('--batch',type=Path,required=True);q.add_argument('--expect-sha256');add_output(q, Output.ARTIFACT, type=Path,required=True)
    q=sub.add_parser('build');q.add_argument('directory',type=Path,help='Saved draft directory or authored recipe JSON');add_output(q, Output.ARTIFACT, type=Path,required=True)
    q=sub.add_parser('return');q.add_argument('directory',type=Path);q.add_argument('returned',type=Path);q.add_argument('--recipe',type=Path,required=True);add_output(q, Output.ARTIFACT, type=Path,required=True)


def edit_recipe(recipe,batch):
    ar.ap.fields(batch,['version','operations'],'region edit batch')
    if batch.get('version')!=1 or not isinstance(batch.get('operations'),list) or not 1<=len(batch['operations'])<=64: raise ValueError('Region edit needs version 1 and 1–64 operations')
    candidate=copy.deepcopy(recipe)
    keys={'set-visible-mask':'visible_mask','set-coverage':'paint_coverage','set-frame':'frame','set-sizing':'sizing','set-context':'context','set-intent':'intent'}
    for op in batch['operations']:
        ar.ap.fields(op,['op','value'],'region operation')
        if op.get('op')=='append-polygon': candidate['visible_mask']['polygons'].append(op['value'])
        elif op.get('op') in keys: candidate[keys[op['op']]]=op['value']
        else: raise ValueError('Unknown region edit operation')
    ar.validate(candidate)
    return candidate


def run(args,project):
    project=Path(project).resolve();action=args.region_action
    if action=='init':
        recipe=ar.initial(project,args.source,args.id)
        if args.rect:
            l,t,r,b=ar.rectangle(args.rect,'initial rectangle',recipe['source']['width'],recipe['source']['height'])
            recipe['visible_mask']['polygons']=[{'operation':'add','points':[[l,t],[r-1,t],[r-1,b-1],[l,b-1]]}]
        if args.base:
            from .project import locations
            from .views import project_summary
            from .production_plan import PATH
            scene,catalog=locations(project);scope=project/PATH if (project/PATH).is_file() else project/'project.json'
            recipe['context']={**{k:ar.file_ref(project,p) for k,p in [('scene',scene),('catalog',catalog),('scope',scope)]},
                               'base':args.base,'views':args.views or project_summary(project)['intended_views'],'start_frame':0,'frames':None}
            recipe['sizing']['mode']='scene'
        elif args.views: raise ValueError('--view requires --base')
        return ar.save_draft(project,recipe,args.out)
    if action=='inspect': return ar.inspect(project,args.directory)
    if action=='check':
        recipe,_,receipt=ar.verify(args.directory,project)
        if receipt['kind']=='return':
            info=ar.read(args.directory/'report.json')
        else:
            info,_,_=ar.geometry(recipe,ar.load_inputs(project,recipe))
        return {'ok':info['ready'],'directory':str(args.directory.resolve()),**info}
    if action=='edit':
        recipe,_,_=ar.verify(args.directory,project)
        if args.expect_sha256 and ar.ap.sha((args.directory/'recipe.json').read_bytes())!=args.expect_sha256: raise ValueError('Region recipe changed since inspection')
        batch_bytes=args.batch.read_bytes();batch=ar.load_scene_json(batch_bytes)
        candidate=edit_recipe(recipe,batch)
        if args.batch.read_bytes()!=batch_bytes: raise ValueError('Region edit changed while reading')
        return ar.save_draft(project,candidate,args.out,parent=recipe,batch=batch)
    if action=='build': return ar.build(project,args.directory,args.out)
    if action=='return': return ar.return_art(project,args.directory,args.returned,args.recipe,args.out)
    raise ValueError('Unknown region action')
