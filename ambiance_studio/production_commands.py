"""Production CLI presentation over the shared iteration and delivery services."""
import studio
from . import registry, studio_server

def run(args, project, root, registry_file):
    command, action = args.command, args.action
    from . import production, deliveries
    matches=[item['id'] for item in registry.projects(root,registry_file) if item['path']==str(project)]
    alias=matches[0] if matches else studio.read(project/'project.json')['id']
    base=studio_server.base_url(registry_file)
    if command=='project' and action=='overview':return production.overview(project,alias,base,readiness_options={'stage':args.stage,'view':args.view,'revision':args.revision},details=args.details)
    if command=='project' and action=='next':
        from .production_queries import next_work
        return next_work(project,production.overview(project,alias,base,details=True),args.limit,args.kind,args.offset)
    if command=='project' and action=='latest':
        data=deliveries.latest(project,args.channel)
        data['current_url']=f'{base}/projects/{alias}'
        if data.get('delivery'):
            production.link_delivery(data['delivery'],alias,base)
            _,entry=deliveries.resolve_entry(data['delivery'])
            data['watch_url']=entry['watch_url'] if data['delivery']['schema_version']==2 else data['delivery']['watch_url']
            data['file']=str(project/entry['movie']['path'])
        return data
    result=production.handoff(project,args.id,args.out,alias,base) if command=='delivery' and action=='handoff' else production.run_command(args,project)
    id = None
    if command=='iteration' and action=='run':id=result['run']['id']
    elif command=='delivery':
        selection = result.get('selection')
        id=result.get('id') or (selection.get('delivery') if isinstance(selection,dict) else None)
    if id:result.update(watch_url=f'{base}/projects/{alias}/deliveries/{id}',current_url=f'{base}/projects/{alias}')
    return result
