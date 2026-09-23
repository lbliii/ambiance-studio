"""Project command adapters and atomic initialization over studio services."""
from .command_output import Output, add_output
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unicodedata

import studio
from . import __version__, views
from .errors import CommandError
from .project import locations
from .scene_runtime import require_node, scene_bridge

ROOT = Path(__file__).resolve().parents[1]

def default_project_slug(title):
    """Make a stable directory ID from a title for default-root projects."""
    if not isinstance(title, str) or not title.strip():
        raise CommandError('Omitting the destination requires a non-empty --title.')
    ascii_title=unicodedata.normalize('NFKD',title.strip()).encode('ascii','ignore').decode('ascii')
    slug=re.sub(r'[^a-z0-9]+','-',ascii_title.lower()).strip('-')[:100].rstrip('-')
    if not slug:
        raise CommandError('Title must contain ASCII letters or numbers to derive a project slug; provide an explicit destination instead.')
    return slug


def init_project(destination,reference,title,template,output_format=None,registry_file=None,root=ROOT):
    from . import registry
    defaulted=destination is None
    if defaulted:
        slug=default_project_slug(title)
        destination=registry.projects_directory()/slug
        if destination.exists():
            raise CommandError(f'Default project path already exists: {destination}; choose a different title or an explicit destination.')
        collisions=[item for item in registry.projects(root,registry.registry_path(registry_file)) if item['id']==slug]
        if collisions:
            raise CommandError(f'Project ID {slug!r} is already registered or discoverable at {collisions[0]["path"]}; choose a different title or an explicit destination.')
        title=title.strip()
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
    integrity=validate(scene_path,catalog_path,project_root=project)
    scene=studio.read(scene_path)
    if not scene['layers']:
        integrity['ok']=False;integrity['errors'].append('Scene has no layers. Import prepared assets and add a layer before preview.')
    p=subprocess.run([require_node(),str(ROOT/'tools/check-scene.mjs'),str(scene_path),'--catalog',str(catalog_path),'--project-root',str(project)],capture_output=True,text=True)
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
    q=group.add_parser('init');q.add_argument('destination',nargs='?',type=Path,help='Project directory (default: AMBIANCE_PROJECTS_DIR or ~/Ambiance Projects, using the title slug)');q.add_argument('--reference',type=Path);q.add_argument('--title',help='Required when omitting DESTINATION; determines the default directory slug');q.add_argument('--template',choices=['blank','last-lantern'],default='blank')
    q.add_argument('--format',dest='output_format',choices=['dual'],help='Blank square stage with saved portrait and landscape framing')
    q=group.add_parser('list');q.add_argument('--directory',type=Path)
    group.add_parser('status');q=group.add_parser('check');add_output(q, Output.REPORT, type=Path)
    q=group.add_parser('latest');q.add_argument('--channel',choices=['review','release'],default='review')
    q=group.add_parser('overview');add_output(q, Output.REPORT, type=Path);q.add_argument('--details',action='store_true')
    q.add_argument('--stage',choices=['layout','assets','animation','export'],default='animation');q.add_argument('--view');q.add_argument('--revision')
    q=group.add_parser('next');q.add_argument('--limit',type=int,default=8);q.add_argument('--offset',type=int,default=0);q.add_argument('--kind')
    q.add_argument('--guided',action='store_true',help='Opt into exact-subject workflow action guidance')
    from .workflow_commands import add_selectors
    add_selectors(q);q.add_argument('--stage');q.add_argument('--details',action='store_true')
    q.add_argument('--subject-limit',type=int,default=6);q.add_argument('--subject-offset',type=int,default=0)
    from . import project_storage
    project_storage.add_parsers(group)


def run(args, project, root, registry_file):
    from . import deliveries, registry, revision_reviews
    if args.action == 'init':
        return init_project(args.destination, args.reference, args.title, args.template, args.output_format,
                            registry_file=registry_file, root=root)
    if args.action == 'list':
        return {'projects': registry.projects(root, registry_file, args.directory), 'registry': str(registry_file)}
    if args.action in ['storage', 'cleanup']:
        from . import project_storage
        return project_storage.run(args, project)
    if args.action == 'next':
        if args.guided:
            from .production_queries import guided_next
            return guided_next(project, args)
        if any(getattr(args,key,None) is not None for key in ['subject','revision','edition','view','stage']) or args.details or args.subject_limit!=6 or args.subject_offset!=0:
            raise CommandError('Workflow selectors require project next --guided')
    if args.action in ['latest', 'overview', 'next']:
        from . import production_commands
        return production_commands.run(args, project, root, registry_file)
    if args.action == 'status':
        result = revision_reviews.project_status(project)
        result['current_delivery'] = deliveries.latest(project)
        return result
    if args.action == 'check':
        return check_project(project)
    raise CommandError('Unsupported command')
