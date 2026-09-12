"""Project command adapters and atomic initialization over studio services."""
from .command_output import Output, add_output
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import studio
from . import __version__, views
from .errors import CommandError
from .project import locations
from .scene_runtime import require_node, scene_bridge

ROOT = Path(__file__).resolve().parents[1]

def init_project(destination,reference,title,template,output_format=None):
    destination=Path(destination).resolve()
    if destination.exists():raise CommandError('Project already exists; choose a new directory.')
    if output_format not in [None,'dual']:raise CommandError('Unsupported project output format')
    if output_format=='dual' and template!='blank':raise CommandError('Dual format requires the blank template; adapt existing artwork explicitly.')
    if output_format=='dual':require_node()
    if template=='last-lantern':require_node()
    destination.parent.mkdir(parents=True,exist_ok=True)
    # Build out of sight; a failure cannot leave a half-initialized destination.
    with tempfile.TemporaryDirectory(prefix='.ambiance-init-',dir=destination.parent) as temp:
        candidate=Path(temp)/destination.name
        studio.new_project(candidate,reference,title)
        settings=studio.read(candidate/'project.json');settings['studio_version']=__version__;studio.write(candidate/'project.json',settings)
        if template=='last-lantern':
            shutil.copytree(ROOT/'assets',candidate/'assets',dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__'))
            scene=studio.read(ROOT/'scenes/last-lantern-rigged.json')
            scene['id']=destination.name;scene['title']=title or settings['title']
        else:
            studio.write(candidate/'assets/catalog.json',{'version':1,'assets':[]})
            scene={'version':1,'id':destination.name,'title':settings['title'],
                'canvas':{'width':1080,'height':1920,'fps':30,'loop_seconds':16,'background':'#1a1733'},
                'camera':{'overscan':1.08,'x_amplitude':0,'y_amplitude':0,'zoom_amplitude':0},'groups':[],'layers':[]}
        if output_format=='dual':
            scene['canvas'].update(width=1920,height=1920)
            scene['framing']=scene_bridge('view-defaults',scene,studio.read(candidate/'assets/catalog.json'),{})
            settings['intended_views']=['portrait','landscape']
            studio.write(candidate/'project.json',settings)
        studio.write(candidate/'scene/scene.json',scene)
        studio.write(candidate/'ambiance-project.json',{'version':1,'scene':'scene/scene.json','catalog':'assets/catalog.json','template':template})
        studio.write(candidate/'plans/asset-inventory.json',{'version':1,'purpose':'Author visible objects, intended actions and required parts; reconcile with plan check.','items':[]})
        # Track the whole project library in asset/animation gates, including imported atlases.
        pipeline=studio.read(candidate/'pipeline.json')
        for gate in pipeline['gates']:
            if gate['id'] in ['assets','animation'] and 'assets/' not in gate['watch']:gate['watch'].append('assets/')
        studio.write(candidate/'pipeline.json',pipeline)
        if destination.exists():raise CommandError('Destination appeared during initialization; refusing to replace it.')
        candidate.rename(destination)
    return {'project':str(destination),'template':template,'scene':'scene/scene.json','catalog':'assets/catalog.json','next':'Inspect the reference and brief; no gate is pre-approved.'}

def check_project(project,include_views=True):
    scene_path,catalog_path=locations(project)
    from kit import validate
    integrity=validate(scene_path,catalog_path)
    scene=studio.read(scene_path)
    if not scene['layers']:
        integrity['ok']=False;integrity['errors'].append('Scene has no layers. Import prepared assets and add a layer before preview.')
    p=subprocess.run([require_node(),str(ROOT/'tools/check-scene.mjs'),str(scene_path),'--catalog',str(catalog_path)],capture_output=True,text=True)
    try:state=json.loads(p.stdout)
    except ValueError:raise CommandError('Scene audit failed: '+p.stderr,'runtime_error',3)
    result={'ok':integrity['ok'] and state['ok'],'integrity':integrity,'state':state,
            'limits':['This is a technical check, not artistic approval, browser pixel inspection, or encoded-video validation.']}
    if include_views and (scene.get('framing') or studio.read(project/'project.json').get('intended_views') is not None):
        summary=views.project_summary(project)
        result['framing']=summary
        result['view_checks']=views.inspect(project,check=True,selected=summary['intended_views']) if summary['ok'] else None
        result['ok']=result['ok'] and summary['ok'] and bool(result['view_checks'] and result['view_checks']['ok'])
    return result

def add_parsers(sub):
    group=sub.add_parser('project').add_subparsers(dest='action',required=True)
    q=group.add_parser('init');q.add_argument('destination',type=Path);q.add_argument('--reference',type=Path);q.add_argument('--title');q.add_argument('--template',choices=['blank','last-lantern'],default='blank')
    q.add_argument('--format',dest='output_format',choices=['dual'],help='Blank square stage with saved portrait and landscape framing')
    q=group.add_parser('list');q.add_argument('--directory',type=Path)
    group.add_parser('status');q=group.add_parser('check');add_output(q, Output.REPORT, type=Path)
    q=group.add_parser('latest');q.add_argument('--channel',choices=['review','release'],default='review')
    q=group.add_parser('overview');add_output(q, Output.REPORT, type=Path);q.add_argument('--details',action='store_true')
    q.add_argument('--stage',choices=['layout','assets','animation','export'],default='animation');q.add_argument('--view');q.add_argument('--revision')
    q=group.add_parser('next');q.add_argument('--limit',type=int,default=8);q.add_argument('--offset',type=int,default=0);q.add_argument('--kind')
    from . import project_storage
    project_storage.add_parsers(group)


def run(args, project, root, registry_file):
    from . import deliveries, registry, revisions
    if args.action == 'init':
        return init_project(args.destination, args.reference, args.title, args.template, args.output_format)
    if args.action == 'list':
        return {'projects': registry.projects(root, registry_file, args.directory), 'registry': str(registry_file)}
    if args.action in ['storage', 'cleanup']:
        from . import project_storage
        return project_storage.run(args, project)
    if args.action in ['latest', 'overview', 'next']:
        from . import production_commands
        return production_commands.run(args, project, root, registry_file)
    if args.action == 'status':
        result = revisions.project_status(project)
        result['current_delivery'] = deliveries.latest(project)
        return result
    if args.action == 'check':
        return check_project(project)
    raise CommandError('Unsupported command')
