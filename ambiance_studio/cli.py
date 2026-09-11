"""A local, JSON-first interface to the studio's tested production tools."""
import argparse
import importlib.util
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile

from . import __version__
from . import planning, assets, revisions, views
from .errors import CommandError
from .project import locations, project_lock
from .scene_runtime import require_node, scene_bridge

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import studio

class Parser(argparse.ArgumentParser):
    def error(self,message):raise CommandError(message)

def emit(command,data,ok=True):
    print(json.dumps({'ok':ok,'schema_version':1,'command':command,'data':data},indent=2,allow_nan=False))

def asset_tool():
    if importlib.util.find_spec('PIL') is None:raise CommandError('Install requirements-assets.txt with this Python to prepare assets.','missing_dependency',3)
    from tools import asset_tool as module
    return module

def project_path(value, registry_file=None):
    if value:
        p=Path(value).resolve()
        if not (p/'ambiance-project.json').is_file():
            if len(Path(value).parts)==1 and not Path(value).is_absolute():
                from . import registry
                return registry.resolve(ROOT, registry.registry_path(registry_file), str(value))
            raise CommandError(f'No ambiance-project.json in {p}')
        return p
    for p in [Path.cwd(),*Path.cwd().parents]:
        if (p/'ambiance-project.json').is_file():return p.resolve()
    raise CommandError('Choose --project PATH, or run inside an initialized project.')

def optional_project_path(value, registry_file=None):
    if value:return project_path(value,registry_file)
    for p in [Path.cwd(),*Path.cwd().parents]:
        if (p/'ambiance-project.json').is_file():return p.resolve()
    return None

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

def parser():
    p=Parser(prog='ambiance',description='Ambiance Studio — local projects, assets, rigs, checks and reviews. Commands emit JSON.')
    p.add_argument('--version',action='version',version=f'Ambiance Studio {__version__}')
    p.add_argument('--project',type=Path,help='Project directory; otherwise discover it from the working directory')
    p.add_argument('--registry',type=Path,help='Shared local registry; defaults to AMBIANCE_REGISTRY or ~/.ambiance-studio/registry.json')
    sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('doctor',help='Inspect runtimes and implemented capabilities')
    group=sub.add_parser('project').add_subparsers(dest='action',required=True)
    q=group.add_parser('init');q.add_argument('destination',type=Path);q.add_argument('--reference',type=Path);q.add_argument('--title');q.add_argument('--template',choices=['blank','last-lantern'],default='blank')
    q.add_argument('--format',dest='output_format',choices=['dual'],help='Blank square stage with saved portrait and landscape framing')
    q=group.add_parser('list');q.add_argument('--directory',type=Path)
    group.add_parser('status');q=group.add_parser('check');q.add_argument('--out',type=Path)
    q=group.add_parser('latest');q.add_argument('--channel',choices=['review','release'],default='review')
    q=group.add_parser('overview');q.add_argument('--out',type=Path)
    group=sub.add_parser('studio',help='Open the shared local film library').add_subparsers(dest='action',required=True)
    q=group.add_parser('register');q.add_argument('path',type=Path);q.add_argument('--id');q.add_argument('--relocate',action='store_true')
    q=group.add_parser('open');q.add_argument('--port',type=int,default=8783);q.add_argument('--no-browser',action='store_true')
    q=group.add_parser('serve');q.add_argument('--port',type=int,default=8783)
    group.add_parser('status');group.add_parser('stop')
    group=sub.add_parser('asset').add_subparsers(dest='action',required=True)
    group.add_parser('list')
    q=group.add_parser('build');q.add_argument('recipe',type=Path);q.add_argument('--out',type=Path,required=True)
    q=group.add_parser('admit');q.add_argument('pack',type=Path)
    q=group.add_parser('inspect');q.add_argument('pack',type=Path)
    q=group.add_parser('proof');q.add_argument('asset');q.add_argument('--out',type=Path,required=True);q.add_argument('--catalog',type=Path)
    q.add_argument('--fps',type=float,default=6);q.add_argument('--width',type=int,default=180);q.add_argument('--landmark',default='anchor')
    assets.add_preparation_parsers(group)
    from . import asset_motion
    asset_motion.add_parsers(group)
    group=sub.add_parser('scene').add_subparsers(dest='action',required=True)
    q=group.add_parser('inspect');q.add_argument('--full',action='store_true');q=group.add_parser('sample');q.add_argument('--time',type=float,required=True)
    q=group.add_parser('apply');q.add_argument('file',type=Path);q.add_argument('--dry-run',action='store_true');q.add_argument('--expect-sha256')
    q=group.add_parser('track');q.add_argument('layer');q.add_argument('file',type=Path);q.add_argument('--dry-run',action='store_true');q.add_argument('--expect-sha256')
    q=group.add_parser('timing');q.add_argument('--layer');q.add_argument('--out',type=Path)
    q=group.add_parser('place');q.add_argument('file',type=Path);q.add_argument('--dry-run',action='store_true');q.add_argument('--expect-sha256')
    q=group.add_parser('reparent');q.add_argument('layer');q.add_argument('--to',required=True);q.add_argument('--socket',required=True)
    q.add_argument('--keep-world',action='store_true',required=True);q.add_argument('--at',type=float,required=True)
    q.add_argument('--dry-run',action='store_true');q.add_argument('--expect-sha256')
    q=group.add_parser('check');q.add_argument('--out',type=Path)
    q=group.add_parser('set');q.add_argument('layer')
    for name in ['x','y','scale','rotation-deg','opacity','depth','cycle-seconds']:q.add_argument('--'+name,type=float)
    q.add_argument('--phase-frames',type=int)
    q=group.add_parser('socket');q.add_argument('layer');q.add_argument('name');q.add_argument('--u',type=float,required=True);q.add_argument('--v',type=float,required=True)
    q=group.add_parser('attach');q.add_argument('layer');q.add_argument('--to',required=True);q.add_argument('--socket',required=True);q.add_argument('--offset-x',type=float,default=0);q.add_argument('--offset-y',type=float,default=0)
    q=group.add_parser('add');q.add_argument('asset');q.add_argument('--id',required=True);q.add_argument('--name')
    for name in ['x','y','width','depth']:q.add_argument('--'+name,type=float)
    group.add_parser('history');q=group.add_parser('restore');q.add_argument('sha256')
    group=sub.add_parser('review').add_subparsers(dest='action',required=True)
    q=group.add_parser('draft');q.add_argument('gate');q.add_argument('--out',type=Path,required=True)
    q.add_argument('--revision');q.add_argument('--edition');q.add_argument('--view')
    q=group.add_parser('record');q.add_argument('file',type=Path)
    q=sub.add_parser('preview',help='Serve a project, saved look or preparation workspace on localhost');q.add_argument('--port',type=int,default=8783)
    preview_kind=q.add_mutually_exclusive_group()
    preview_kind.add_argument('--look',type=Path,help='Serve a verified look-proof artifact without requiring a project')
    preview_kind.add_argument('--views-proof',type=Path,help='Serve a saved synchronized view proof with verified frame hashes')
    preview_kind.add_argument('--motion',type=Path,help='Inspect a motion proof and evaluate in-memory drafts')
    preview_kind.add_argument('--prepare',type=Path,help='Inspect and edit a verified preparation draft without writing project files')
    q=sub.add_parser('test',help='Run local regression checks without paid providers');q.add_argument('--out',type=Path)
    planning.add_parsers(sub);assets.add_library_parsers(sub);revisions.add_parsers(sub);views.add_parsers(sub)
    from . import rendering, audio, finishing, production
    rendering.add_parsers(sub);audio.add_parsers(sub);finishing.add_parsers(sub)
    production.add_parsers(sub)
    return p

def run(args):
    command=args.command;action=getattr(args,'action',None)
    from . import registry, studio_server
    registry_file=registry.registry_path(getattr(args,'registry',None))
    if command=='studio':
        if action=='register':return registry.register(registry_file,args.path,args.id,args.relocate)
        if action=='open':return studio_server.open_studio(ROOT,registry_file,args.port,not args.no_browser)
        if action=='serve':return studio_server.serve(ROOT,registry_file,args.port)
        if action=='status':return studio_server.status(registry_file)
        if action=='stop':return studio_server.stop(registry_file)
    if command=='doctor':
        from . import rendering, audio
        render_caps=rendering.capabilities();audio_caps=audio.capabilities()
        render_caps['preparation_workbench']=importlib.util.find_spec('PIL') is not None and bool(shutil.which('node'))
        pillow=importlib.util.find_spec('PIL') is not None
        return {'version':__version__,'root':str(ROOT),'python':platform.python_version(),'python_executable':sys.executable,
            'node':shutil.which('node'),'pillow':pillow,'ffmpeg':shutil.which('ffmpeg'),'ffprobe':shutil.which('ffprobe'),
            'capabilities':{'project_and_reviews':True,'revision_binding':True,'production_inventory':True,'asset_preparation':pillow,'asset_preflight_and_crop_return':pillow,'edge_inspection_and_repair':pillow,'finishing_and_look_packages':render_caps['frame_render'],'cel_motion':{'manual':pillow,'tracking':'pillow-patch-ncc' if pillow else None,'version':'1.0.0'},'asset_proofs':pillow,'scene_operations':bool(shutil.which('node')),'scene_tracks':bool(shutil.which('node')),'saved_views':bool(shutil.which('node')),'source_placement_and_reparent':bool(shutil.which('node')),'scene_timing':bool(shutil.which('node')),'preview':bool(shutil.which('node')),'final_video_export':render_caps['final_video_export'],'audio_arrangement':audio_caps['audio_arrangement'],'rendering':render_caps,'audio':audio_caps},
            'note':'Optional dependency availability does not imply a renderer or provider adapter is implemented.'}
    if command=='test':
        require_node();asset_tool()
        commands=[[sys.executable,'-m','unittest','discover','-s','tests','-p','test_*.py'],['node','editor/verify-engine.mjs'],['node','tests/test-rig.mjs'],['node','tests/test-views.mjs'],['node','tests/test-view-raster.mjs'],['node','tests/test-tracks.mjs'],['node','tests/test-source-placement.mjs'],['node','tests/test-finishing.mjs'],[sys.executable,'tools/package_audit.py']]
        results=[]
        for c in commands:
            p=subprocess.run(c,cwd=ROOT,capture_output=True,text=True)
            results.append({'command':c,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
        return {'ok':all(r['exit_code']==0 for r in results),'checks':results}
    if command=='project' and action=='init':return init_project(args.destination,args.reference,args.title,args.template,args.output_format)
    if command=='project' and action=='list':
        return {'projects':registry.projects(ROOT,registry_file,args.directory),'registry':str(registry_file)}
    if command=='asset' and action=='build':return asset_tool().build(args.recipe,args.out)
    if command=='asset' and action=='inspect':
        asset_tool();return assets.inspect_pack(args.pack)
    if command=='library':
        selected=optional_project_path(args.project,args.registry)
        return assets.library(args,selected)
    if command=='asset' and action=='proof':
        asset_tool()
        selected=optional_project_path(args.project,args.registry)
        return assets.proof(args.asset,args.out,selected,args.catalog,args.fps,args.width,args.landmark)
    if command=='preview' and args.motion is not None:
        asset_tool()
        from .motion_server import serve
        serve(args.motion,args.port);return None
    if command=='preview' and args.look is not None:
        from .preview import serve_look
        serve_look(args.look,args.port);return None
    if command=='preview' and args.views_proof is not None:
        from .preview import serve_look
        serve_look(args.views_proof,args.port,kind='views-proof');return None
    if command=='preview' and args.prepare is not None:
        from .preparation_server import serve
        serve(args.prepare,args.port);return None
    project=project_path(args.project,args.registry)
    if command=='asset' and action=='motion':
        asset_tool()
        from . import asset_motion
        return asset_motion.run(args,project)
    if command in ['delivery','iteration','feedback'] or (command=='project' and action in ['latest','overview']):
        from . import production, deliveries
        matches=[item['id'] for item in registry.projects(ROOT,registry_file) if item['path']==str(project)]
        alias=matches[0] if matches else studio.read(project/'project.json')['id']
        base=studio_server.base_url(registry_file)
        if command=='project' and action=='overview':return production.overview(project,alias,base)
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
        if command=='iteration' and action=='run':id=result['run']['id']
        else:id=result.get('id') or result.get('selection',{}).get('delivery')
        if id:result.update(watch_url=f'{base}/projects/{alias}/deliveries/{id}',current_url=f'{base}/projects/{alias}')
        return result
    if command=='asset' and action in ['prepare','preflight','crop','return','edges','edge-repair']:return assets.run_preparation(args,project)
    if command=='revision':return revisions.run(args,project)
    if command=='view':return views.run(args,project)
    if command=='plan':return planning.run(args,project)
    if command in ['render','media']:
        from . import rendering
        prepared=revisions.prepare_edition(project,args)
        result=rendering.run(args,project)
        return revisions.record_edition(project,prepared,result,args)
    if command=='audio':
        from . import audio
        return audio.run(args,project)
    if command=='project' and action=='status':
        from . import deliveries
        result=revisions.project_status(project)
        result['current_delivery']=deliveries.latest(project)
        return result
    if command in ['project','scene'] and action=='check':return check_project(project,include_views=command=='project')
    if command in ['look','scene']:
        from . import scene_commands
        return scene_commands.run_look(args,project) if command=='look' else scene_commands.run_scene(args,project)
    scene_path,catalog_path=locations(project)
    if command=='preview':
        checked=check_project(project)
        if not checked['ok']:raise CommandError('Project checks failed. Run project check for details.','check_failed',1)
        from .preview import serve
        serve(ROOT,project,args.port);return None
    if command=='asset':
        if action=='list':return studio.read(catalog_path)
        with project_lock(project):return asset_tool().admit(args.pack,catalog_path)
    if command=='review':
        if action=='draft':
            if args.edition and not args.revision:raise CommandError('--edition requires --revision')
            if args.view and not args.revision:raise CommandError('--view requires --revision')
            context=revisions.review_context(project,args.revision,args.edition,args.view) if args.revision else None
            draft=studio.review_template(project,args.gate,context)
            if args.out.exists():raise CommandError('Review draft already exists.')
            studio.write(args.out,draft);return {'draft':str(args.out.resolve()),'review':draft}
        with project_lock(project):
            source=studio.read(args.file);subject=source.get('subject',{})
            context=revisions.review_context(project,subject['revision'],subject.get('edition'),subject.get('view')) if source.get('version')==2 else None
            return studio.record_review(project,args.file,context)
    raise CommandError('Unsupported command')

def main(argv=None):
    try:
        args=parser().parse_args(argv)
        result=run(args)
        if result is None:return 0
        command=' '.join(filter(None,[args.command,getattr(args,'action',None),getattr(args,'motion_action',None)]))
        ok=result.get('ok',True) if isinstance(result,dict) else True
        payload={'ok':ok,'schema_version':1,'command':command,'data':result}
        if getattr(args,'out',None) and args.command not in ['asset','render','media'] and not(args.command=='look' and args.action=='export') and not(args.command=='review' and args.action=='draft') and not(args.command in ['revision','delivery'] and args.action=='handoff') and not(args.command=='plan' and getattr(args,'spec_action',None)=='migrate'):
            studio.write(args.out,payload)
        emit(command,result,ok)
        return 0 if ok else 1
    except CommandError as e:
        print(json.dumps({'ok':False,'schema_version':1,'error':{'code':e.code,'message':str(e)}},indent=2));return e.exit_code
    except (OSError,ValueError,TypeError,KeyError) as e:
        print(json.dumps({'ok':False,'schema_version':1,'error':{'code':'invalid_input','message':str(e)}},indent=2));return 2
    except KeyboardInterrupt:return 130
