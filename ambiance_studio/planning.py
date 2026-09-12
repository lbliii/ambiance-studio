"""Reconcile authored production intentions with current project evidence."""
from .command_output import Output, add_output
from pathlib import Path
import json
import studio

STATES = {'keep','implemented-subtle','partial-light-only','not-produced','static-deferred','static-support','planned','in-progress','complete'}
STAGES = ['planned','source','prepared','compiled','placed']
PRIORITIES = ['next','prepare-with-flame','exploration','preserve','retain-or-tune','retain','retain-or-disable','optional']


def add_parsers(sub):
    group=sub.add_parser('plan',help='Reconcile production intentions with current evidence').add_subparsers(dest='action',required=True)
    from . import plan_commands
    plan_commands.add_parsers(group)
    q=group.add_parser('fulfill');q.add_argument('file',type=Path);q.add_argument('--dry-run',action='store_true');q.add_argument('--expect-sha256',required=True)
    for action in ['inspect','check','next']:
        q=group.add_parser(action);q.add_argument('--inventory',default='plans/asset-inventory.json');add_output(q, Output.REPORT, type=Path)
        if action=='next':q.add_argument('--limit',type=int,default=5)
        if action=='check':q.add_argument('--require-complete',action='store_true',help='Fail when declared production scope is empty or unfinished; does not certify aesthetics')


def inspect(project, inventory='plans/asset-inventory.json', *, scene_path=None, catalog_path=None):
    project=Path(project).resolve();path=studio.inside(project,inventory)
    plan=studio.read(path)
    conf=studio.read(project/'ambiance-project.json')
    catalog_path=catalog_path or studio.inside(project,conf['catalog']);scene_path=scene_path or studio.inside(project,conf['scene'])
    catalog=studio.read(catalog_path);scene=studio.read(scene_path)
    return evaluate(project,plan,catalog,scene,path,{str(f.relative_to(project)):studio.digest(f) for f in [path,catalog_path,scene_path]})


def evaluate(project,plan,catalog,scene,path,bindings):
    if plan.get('version')!=1 or not isinstance(plan.get('items'),list):raise ValueError('Expected inventory version 1 with items.')
    evidence_bindings={}
    assets={a['id']:a for a in catalog['assets']};layers={l['id']:l for l in scene['layers']}
    errors=[];warnings=[];ids=set();rows=[];asset_coverage=set()
    def evidence(ref,context):
        if not isinstance(ref,dict) or not isinstance(ref.get('file'),str) or not isinstance(ref.get('sha256'),str):
            errors.append(f'{context}: evidence needs file and sha256');return False
        try:
            target=studio.inside(project,ref['file'])
            if not target.is_file() or studio.digest(target)!=ref['sha256']:
                errors.append(f'{context}: missing or changed evidence {ref["file"]}');return False
        except ValueError as e:errors.append(f'{context}: {e}');return False
        evidence_bindings[ref['file']]=ref['sha256']
        return True
    if plan.get('reference'):
        ref=plan['reference'];evidence({'file':ref.get('file',ref.get('path')),'sha256':ref.get('sha256')},'reference')
    asset_integrity={aid:evidence({'file':a['file'],'sha256':a.get('sha256')},f'catalog {aid}') for aid,a in assets.items()}
    if not plan['items']:warnings.append('No objects have been inventoried yet; an empty list is not a completed visual inventory.')
    if len(assets)!=len(catalog['assets']):errors.append('Duplicate catalog asset IDs')
    for lid,layer in layers.items():
        if layer['asset'] not in assets:errors.append(f'Scene layer {lid}: unknown asset {layer["asset"]}')
    for item in plan['items']:
        if not isinstance(item,dict) or not isinstance(item.get('id'),str) or not item['id'] or item['id'] in ids:
            errors.append('Each inventory item needs a unique nonempty id');continue
        id=item['id'];ids.add(id);start_errors=len(errors)
        state=item.get('state','planned')
        if state not in STATES:errors.append(f'{id}: unknown state {state}')
        mandatory=item.get('required',False)
        if not isinstance(mandatory,bool):errors.append(f'{id}: required must be a boolean');mandatory=False
        if mandatory and state=='static-deferred':errors.append(f'{id}: required scope cannot be static-deferred; retain the work or explicitly revise the scope')
        dependencies=item.get('dependencies',[])
        if not isinstance(dependencies,list) or not all(isinstance(d,str) for d in dependencies):
            errors.append(f'{id}: dependencies must be IDs');dependencies=[]
        existing=item.get('existing_asset_ids',[])
        if not isinstance(existing,list) or not all(isinstance(a,str) for a in existing):
            errors.append(f'{id}: existing_asset_ids must be IDs');existing=[]
        for a in existing:
            if a not in assets:errors.append(f'{id}: unknown asset {a}')
            else:
                asset_coverage.add(a)
                if not asset_integrity[a]:errors.append(f'{id}: existing asset {a} failed integrity')
        required=item.get('required_parts',[])
        if not isinstance(required,list):errors.append(f'{id}: required_parts must be a list');required=[]
        if mandatory and not required:errors.append(f'{id}: required scope needs tracked required_parts')
        parts=[];part_ids=set()
        for n,part in enumerate(required):
            if isinstance(part,str):
                parts.append({'id':str(n+1),'description':part,'stage':'planned','complete':False});continue
            if not isinstance(part,dict):errors.append(f'{id}: invalid part');continue
            pid=part.get('id');stage=part.get('stage','planned');target=part.get('target_stage','placed');valid=True
            if not isinstance(pid,str) or not pid or pid in part_ids:errors.append(f'{id}: unique part IDs required');valid=False
            part_ids.add(str(pid))
            if stage not in STAGES or target not in STAGES or target=='planned':errors.append(f'{id}/{pid}: invalid stage/target_stage');valid=False
            refs=part.get('files',[])
            if not isinstance(refs,list):errors.append(f'{id}/{pid}: files must be a list');refs=[];valid=False
            for ref in refs:
                if not evidence(ref,f'{id}/{pid}'):valid=False
            if stage!='planned' and not refs:errors.append(f'{id}/{pid}: claimed stage needs hashed file evidence');valid=False
            aid=part.get('asset_id');used=part.get('layer_ids',[])
            if stage in ['compiled','placed'] and aid not in assets:errors.append(f'{id}/{pid}: compiled/placed stage needs catalog asset_id');valid=False
            if aid in assets:
                asset_coverage.add(aid)
                if not asset_integrity[aid]:errors.append(f'{id}/{pid}: asset {aid} failed integrity');valid=False
            if not isinstance(used,list) or not all(isinstance(l,str) for l in used):errors.append(f'{id}/{pid}: layer_ids must be IDs');used=[];valid=False
            if stage=='placed' and not used:errors.append(f'{id}/{pid}: placed stage needs layer_ids');valid=False
            for lid in used:
                if lid not in layers or layers[lid]['asset']!=aid:errors.append(f'{id}/{pid}: layer {lid} does not use {aid}');valid=False
            review=part.get('review',{'state':'pending'})
            if not isinstance(review,dict) or review.get('state') not in ['pending','accepted','needs-revision']:
                errors.append(f'{id}/{pid}: review must be pending, accepted or needs-revision');review={'state':'pending'};valid=False
            if review.get('state') in ['accepted','needs-revision']:
                review_refs=review.get('evidence',[])
                if not isinstance(review_refs,list) or not review_refs:errors.append(f'{id}/{pid}: recorded review needs hashed evidence');valid=False
                else:
                    for ref in review_refs:
                        if not evidence(ref,f'{id}/{pid} review'):valid=False
            produced=valid and stage in STAGES and target in STAGES and STAGES.index(stage)>=STAGES.index(target)
            done=produced and review.get('state')!='needs-revision'
            parts.append({'id':pid,'description':part.get('description',pid),'stage':stage,'target_stage':target,'production_complete':produced,'complete':done,'review':review})
        in_scene=sorted(lid for lid,l in layers.items() if l['asset'] in existing)
        retained=state in ['keep','implemented-subtle','static-support'] and bool(in_scene)
        deferred=state=='static-deferred'
        completed_parts=bool(parts) and all(x['complete'] for x in parts)
        complete=(completed_parts or (retained and not parts) or deferred) and len(errors)==start_errors
        if state=='complete' and not completed_parts:errors.append(f'{id}: complete claim lacks completed parts')
        rows.append({'id':id,'name':item.get('name',id),'location':item.get('location'),'declared_state':state,
            'required':mandatory,'priority':item.get('priority','next'),'method':item.get('method','unspecified'),'existing_asset_ids':existing,
            'scene_layer_ids':in_scene,'required_parts':parts,'dependencies':dependencies,'complete_for_scope':complete,
            'disposition':'deferred' if deferred else 'retained' if retained and not parts else 'produced' if completed_parts else 'missing-work',
            'next_action':item.get('next_action','Define the intended action and required parts.')})
    byid={r['id']:r for r in rows};visiting=set();visited=set()
    def visit(id):
        if id in visiting:errors.append(f'Dependency cycle at {id}');return
        if id in visited:return
        visiting.add(id)
        for dep in byid[id]['dependencies']:
            if dep not in byid:errors.append(f'{id}: unknown dependency {dep}')
            else:visit(dep)
        visiting.remove(id);visited.add(id)
    for id in byid:visit(id)
    computed=set()
    def completion(id,active):
        if id in computed:return byid[id]['complete_for_scope']
        if id in active:return False
        r=byid[id]
        r['blocked_by']=[d for d in r['dependencies'] if d not in byid or not completion(d,active|{id}) or byid[d]['disposition']=='deferred']
        if r['blocked_by']:r['complete_for_scope']=False
        computed.add(id);return r['complete_for_scope']
    for id in byid:completion(id,set())
    uncovered=sorted(set(assets)-asset_coverage)
    active_unmapped=sorted(set(uncovered)&{layer['asset'] for layer in layers.values()})
    retained_unmapped=sorted(set(uncovered)-set(active_unmapped))
    if active_unmapped:warnings.append('Active scene assets missing from the authored inventory: '+', '.join(active_unmapped))
    return {'ok':not errors,'inventory':str(path),'bindings':bindings,'evidence_bindings':evidence_bindings,
        'summary':{'items':len(rows),'catalog_assets':len(assets),'scene_layers':len(layers),'incomplete_items':sum(not r['complete_for_scope'] for r in rows),
                   'deferred_items':sum(r['disposition']=='deferred' for r in rows)},
        'items':rows,'unmapped_asset_ids':uncovered,'active_unmapped_asset_ids':active_unmapped,'retained_unmapped_asset_ids':retained_unmapped,'errors':errors,'warnings':warnings,
        'limits':['Production evidence is separate from artistic approval.','Object/method declarations are authored; this command does not infer every object from an image.','Planned work is normal incompleteness, not a failed integrity check.']}


def ready_work(result, limit=5):
    ready=[r for r in result['items'] if not r['complete_for_scope'] and not r['blocked_by']] if result['ok'] else []
    ready.sort(key=lambda r:(PRIORITIES.index(r['priority']) if r['priority'] in PRIORITIES else len(PRIORITIES),r['id']))
    return {'total_ready':len(ready), 'ready':ready[:limit]}


def run(args,project):
    if args.action=='fulfill':
        from .inventory_authoring import fulfill
        return fulfill(project,studio.read(args.file),args.expect_sha256,args.dry_run)
    if args.action in ['spec', 'complexity', 'coverage', 'evidence']:
        from . import plan_commands
        return plan_commands.run(args, project)
    result=inspect(project,args.inventory)
    if args.action=='check' and getattr(args,'require_complete',False):
        outstanding=[{'id':r['id'],'state':r['declared_state'],'blocked_by':r['blocked_by'],'next_action':r['next_action']}
                     for r in result['items'] if not r['complete_for_scope']]
        if not result['items']:result['errors'].append('Production scope is empty; author the reference census and required parts first.')
        if outstanding:result['errors'].append('Unfinished production scope: '+', '.join(r['id'] for r in outstanding))
        result['ok']=not result['errors']
        result['completion']={'required':True,'complete':result['ok'],'outstanding':outstanding,
            'meaning':'Declared production scope only; pending artistic reviews are not approvals, and omitted objects or deliverable formats cannot be inferred.'}
    if args.action=='next':
        if not 1<=args.limit<=1000:raise ValueError('Next-action limit must be 1–1000')
        result.update(ready_work(result,args.limit))
        result['blocked']=[{'id':r['id'],'dependencies':r['blocked_by']} for r in result['items'] if r['blocked_by']]
        result['reason']='Declared priorities and satisfied prerequisites; no paid or generation action is executed.'
        result.pop('items')
    return result
