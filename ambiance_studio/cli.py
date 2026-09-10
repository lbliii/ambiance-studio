"""A local, JSON-first interface to the studio's tested production tools."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import shlex
import subprocess
import sys
import tempfile

from . import __version__
from . import planning, assets, revisions

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import studio

class CommandError(Exception):
    def __init__(self,message,code='invalid_input',exit_code=2):
        super().__init__(message);self.code=code;self.exit_code=exit_code

class Parser(argparse.ArgumentParser):
    def error(self,message):raise CommandError(message)

def emit(command,data,ok=True):
    print(json.dumps({'ok':ok,'schema_version':1,'command':command,'data':data},indent=2,allow_nan=False))

def require_node():
    node=shutil.which('node')
    if not node:raise CommandError('Node is required for scene operations. Run ambiance doctor.','missing_dependency',3)
    return node

def asset_tool():
    if importlib.util.find_spec('PIL') is None:raise CommandError('Install requirements-assets.txt with this Python to prepare assets.','missing_dependency',3)
    from tools import asset_tool as module
    return module

def project_path(value):
    if value:
        p=Path(value).resolve()
        if not (p/'ambiance-project.json').is_file():raise CommandError(f'No ambiance-project.json in {p}')
        return p
    for p in [Path.cwd(),*Path.cwd().parents]:
        if (p/'ambiance-project.json').is_file():return p.resolve()
    raise CommandError('Choose --project PATH, or run inside an initialized project.')

def optional_project_path(value):
    if value:return project_path(value)
    for p in [Path.cwd(),*Path.cwd().parents]:
        if (p/'ambiance-project.json').is_file():return p.resolve()
    return None

def locations(project):
    conf=studio.read(project/'ambiance-project.json')
    if conf.get('version')!=1:raise CommandError('Unsupported project configuration version')
    return studio.inside(project,conf['scene']),studio.inside(project,conf['catalog'])

@contextmanager
def project_lock(project):
    directory=project/'.ambiance';directory.mkdir(exist_ok=True)
    lock=directory/'write.lock'
    try:fd=os.open(lock,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except FileExistsError:raise CommandError(f'Project is locked: {lock}. Check for an active writer before removing a stale lock.','project_locked',2)
    try:
        with os.fdopen(fd,'w') as f:f.write(str(os.getpid()))
        yield
    finally:lock.unlink(missing_ok=True)

def scene_bridge(action,scene,catalog,args):
    p=subprocess.run([require_node(),str(ROOT/'tools/scene-command.mjs')],input=json.dumps({'action':action,'scene':scene,'catalog':catalog,'args':args},allow_nan=False),text=True,capture_output=True)
    try:result=json.loads(p.stdout)
    except ValueError:raise CommandError('Scene evaluator failed: '+p.stderr.strip(),'runtime_error',3)
    if p.returncode or not result['ok']:raise CommandError(result.get('error','Scene operation failed'))
    return result['data']

def save_scene(project,path,next_scene,operation):
    history=project/'.ambiance/scene-history';history.mkdir(parents=True,exist_ok=True)
    previous=studio.digest(path);backup=history/f'{previous}.json'
    if not backup.exists():shutil.copy2(path,backup)
    studio.write(path,next_scene)
    return {'scene':str(path),'operation':operation,'previous_sha256':previous,'sha256':studio.digest(path),'restore_command':shlex.join(['ambiance','--project',str(project),'scene','restore',previous])}

def init_project(destination,reference,title,template):
    destination=Path(destination).resolve()
    if destination.exists():raise CommandError('Project already exists; choose a new directory.')
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

def check_project(project):
    scene_path,catalog_path=locations(project)
    from kit import validate
    integrity=validate(scene_path,catalog_path)
    scene=studio.read(scene_path)
    if not scene['layers']:
        integrity['ok']=False;integrity['errors'].append('Scene has no layers. Import prepared assets and add a layer before preview.')
    p=subprocess.run([require_node(),str(ROOT/'tools/check-scene.mjs'),str(scene_path),'--catalog',str(catalog_path)],capture_output=True,text=True)
    try:state=json.loads(p.stdout)
    except ValueError:raise CommandError('Scene audit failed: '+p.stderr,'runtime_error',3)
    return {'ok':integrity['ok'] and state['ok'],'integrity':integrity,'state':state,
            'limits':['This is a technical check, not artistic approval, browser pixel inspection, or encoded-video validation.']}

def parser():
    p=Parser(prog='ambiance',description='Ambiance Studio — local projects, assets, rigs, checks and reviews. Commands emit JSON.')
    p.add_argument('--version',action='version',version=f'Ambiance Studio {__version__}')
    p.add_argument('--project',type=Path,help='Project directory; otherwise discover it from the working directory')
    sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('doctor',help='Inspect runtimes and implemented capabilities')
    group=sub.add_parser('project').add_subparsers(dest='action',required=True)
    q=group.add_parser('init');q.add_argument('destination',type=Path);q.add_argument('--reference',type=Path);q.add_argument('--title');q.add_argument('--template',choices=['blank','last-lantern'],default='blank')
    q=group.add_parser('list');q.add_argument('--directory',type=Path,default=ROOT/'projects')
    group.add_parser('status');q=group.add_parser('check');q.add_argument('--out',type=Path)
    group=sub.add_parser('asset').add_subparsers(dest='action',required=True)
    group.add_parser('list')
    q=group.add_parser('build');q.add_argument('recipe',type=Path);q.add_argument('--out',type=Path,required=True)
    q=group.add_parser('admit');q.add_argument('pack',type=Path)
    q=group.add_parser('inspect');q.add_argument('pack',type=Path)
    q=group.add_parser('proof');q.add_argument('asset');q.add_argument('--out',type=Path,required=True);q.add_argument('--catalog',type=Path)
    q.add_argument('--fps',type=float,default=6);q.add_argument('--width',type=int,default=180);q.add_argument('--landmark',default='anchor')
    assets.add_preparation_parsers(group)
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
    q.add_argument('--revision');q.add_argument('--edition')
    q=group.add_parser('record');q.add_argument('file',type=Path)
    q=sub.add_parser('preview',help='Serve this project or saved look read-only on localhost');q.add_argument('--port',type=int,default=8783);q.add_argument('--look',type=Path,help='Serve a verified look-proof artifact without requiring a project')
    q=sub.add_parser('test',help='Run local regression checks without paid providers');q.add_argument('--out',type=Path)
    planning.add_parsers(sub);assets.add_library_parsers(sub);revisions.add_parsers(sub)
    from . import rendering, audio, finishing
    rendering.add_parsers(sub);audio.add_parsers(sub);finishing.add_parsers(sub)
    return p

def run(args):
    command=args.command;action=getattr(args,'action',None)
    if command=='doctor':
        from . import rendering, audio
        render_caps=rendering.capabilities();audio_caps=audio.capabilities()
        pillow=importlib.util.find_spec('PIL') is not None
        return {'version':__version__,'root':str(ROOT),'python':platform.python_version(),'python_executable':sys.executable,
            'node':shutil.which('node'),'pillow':pillow,'ffmpeg':shutil.which('ffmpeg'),'ffprobe':shutil.which('ffprobe'),
            'capabilities':{'project_and_reviews':True,'revision_binding':True,'production_inventory':True,'asset_preparation':pillow,'asset_preflight_and_crop_return':pillow,'edge_inspection_and_repair':pillow,'finishing_and_look_packages':render_caps['frame_render'],'asset_proofs':pillow,'scene_operations':bool(shutil.which('node')),'scene_tracks':bool(shutil.which('node')),'source_placement_and_reparent':bool(shutil.which('node')),'scene_timing':bool(shutil.which('node')),'preview':bool(shutil.which('node')),'final_video_export':render_caps['final_video_export'],'audio_arrangement':audio_caps['audio_arrangement'],'rendering':render_caps,'audio':audio_caps},
            'note':'Optional dependency availability does not imply a renderer or provider adapter is implemented.'}
    if command=='test':
        require_node();asset_tool()
        commands=[[sys.executable,'-m','unittest','discover','-s','tests','-p','test_*.py'],['node','editor/verify-engine.mjs'],['node','tests/test-rig.mjs'],['node','tests/test-tracks.mjs'],['node','tests/test-source-placement.mjs'],['node','tests/test-finishing.mjs'],[sys.executable,'tools/package_audit.py']]
        results=[]
        for c in commands:
            p=subprocess.run(c,cwd=ROOT,capture_output=True,text=True)
            results.append({'command':c,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
        return {'ok':all(r['exit_code']==0 for r in results),'checks':results}
    if command=='project' and action=='init':return init_project(args.destination,args.reference,args.title,args.template)
    if command=='project' and action=='list':
        return {'projects':[{'path':str(p.parent.resolve()),'title':studio.read(p.parent/'project.json')['title']} for p in sorted(args.directory.glob('*/ambiance-project.json'))]}
    if command=='asset' and action=='build':return asset_tool().build(args.recipe,args.out)
    if command=='asset' and action=='inspect':
        asset_tool();return assets.inspect_pack(args.pack)
    if command=='library':
        selected=optional_project_path(args.project)
        return assets.library(args,selected)
    if command=='asset' and action=='proof':
        asset_tool()
        selected=optional_project_path(args.project)
        return assets.proof(args.asset,args.out,selected,args.catalog,args.fps,args.width,args.landmark)
    if command=='preview' and args.look is not None:
        from .preview import serve_look
        serve_look(args.look,args.port);return None
    project=project_path(args.project)
    if command=='asset' and action in ['preflight','crop','return','edges','edge-repair']:return assets.run_preparation(args,project)
    if command=='revision':return revisions.run(args,project)
    if command=='plan':return planning.run(args,project)
    if command in ['render','media']:
        from . import rendering
        prepared=revisions.prepare_edition(project,args)
        result=rendering.run(args,project)
        return revisions.record_edition(project,prepared,result,args)
    if command=='audio':
        from . import audio
        return audio.run(args,project)
    if command=='project' and action=='status':return revisions.project_status(project)
    if command in ['project','scene'] and action=='check':return check_project(project)
    scene_path,catalog_path=locations(project)
    if command=='look':
        from . import finishing, scene_authoring
        with project_lock(project):
            previous=studio.digest(scene_path);catalog_hash=studio.digest(catalog_path);config_hash=studio.digest(project/'ambiance-project.json')
            scene=studio.read(scene_path);catalog=studio.read(catalog_path)
            if action in ['inspect','check']:return finishing.inspect(project,scene,catalog,args.time)
            if action=='export':return finishing.export_package(project,scene,catalog,args.out,include_rig=getattr(args,'include_rig',False))
            if args.expect_sha256 and args.expect_sha256!=previous:raise CommandError('Scene changed since expected SHA-256.','stale_input',2)
            extra=[];detail={}
            if action=='apply':
                extra=[finishing.file_dependency(args.file,'look-input')];batch=finishing.load_apply(args.file)
            else:batch,extra,detail=finishing.import_batch(project,scene,catalog,args.package,args.bindings,include_rig=getattr(args,'include_rig',False))
            batch,dependencies=scene_authoring.resolve_batch(project,scene,catalog,batch);dependencies+=extra
            candidate=scene_bridge('apply',scene,catalog,{'batch':batch,'report':True})['scene']
            if studio.digest(scene_path)!=previous or studio.digest(catalog_path)!=catalog_hash or studio.digest(project/'ambiance-project.json')!=config_hash:raise CommandError('Project changed during look validation; nothing saved.','stale_input',2)
            scene_authoring.verify_dependencies(project,dependencies)
            if args.dry_run:return {'dry_run':True,'previous_sha256':previous,'scene':candidate,'dependencies':dependencies,'import':detail}
            return {**save_scene(project,scene_path,candidate,'look-'+action),'dependencies':dependencies,'import':detail}
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
            context=revisions.review_context(project,args.revision,args.edition) if args.revision else None
            draft=studio.review_template(project,args.gate,context)
            if args.out.exists():raise CommandError('Review draft already exists.')
            studio.write(args.out,draft);return {'draft':str(args.out.resolve()),'review':draft}
        with project_lock(project):
            source=studio.read(args.file);subject=source.get('subject',{})
            context=revisions.review_context(project,subject['revision'],subject.get('edition')) if source.get('version')==2 else None
            return studio.record_review(project,args.file,context)
    if command=='scene':
        if action in ['inspect','sample','timing']:return scene_bridge(action,studio.read(scene_path),studio.read(catalog_path),{'time':getattr(args,'time',None),'full':getattr(args,'full',False),'layer':getattr(args,'layer',None)})
        if action=='history':
            return {'snapshots':[{'sha256':p.stem,'path':str(p)} for p in sorted((project/'.ambiance/scene-history').glob('*.json'))]}
        with project_lock(project):
            if action in ['apply','track','place','reparent']:
                from . import scene_authoring
                previous=studio.digest(scene_path)
                catalog_hash=studio.digest(catalog_path);config_hash=studio.digest(project/'ambiance-project.json')
                scene=studio.read(scene_path);catalog=studio.read(catalog_path)
                if args.expect_sha256 and args.expect_sha256!=previous:raise CommandError('Scene changed since the expected SHA-256; inspect and rebase the edit.','stale_input',2)
                if action=='reparent':batch={'version':1,'operations':[{'op':'reparent','layer':args.layer,'to':args.to,'socket':args.socket,'preserve':'world_at_time','at_seconds':args.at}]}
                else:batch=studio.read(args.file)
                if action=='place':batch=scene_authoring.placement_batch(batch)
                if action=='track':
                    if batch.get('version')!=1 or not isinstance(batch.get('tracks'),dict) or set(batch)-{'version','tracks','track_loop'}:raise CommandError('Track file needs version 1, tracks and optional track_loop.')
                    values={'tracks':batch['tracks'],'track_loop':batch.get('track_loop','closed')}
                    batch={'version':1,'operations':[{'op':'set','layer':args.layer,'values':values}]}
                batch,dependencies=scene_authoring.resolve_batch(project,scene,catalog,batch)
                reported=scene_bridge('apply',scene,catalog,{'batch':batch,'report':True})
                candidate=reported['scene'];diagnostics=reported['operations']
                if studio.digest(scene_path)!=previous:raise CommandError('Scene changed during validation; no edit was saved.','stale_input',2)
                if studio.digest(catalog_path)!=catalog_hash or studio.digest(project/'ambiance-project.json')!=config_hash:raise CommandError('Catalog or project configuration changed during validation; no edit was saved.','stale_input',2)
                scene_authoring.verify_dependencies(project,dependencies)
                if args.dry_run:return {'dry_run':True,'previous_sha256':previous,'scene':candidate,'operations':len(batch['operations']),'diagnostics':diagnostics,'dependencies':dependencies}
                return {**save_scene(project,scene_path,candidate,action),'diagnostics':diagnostics,'dependencies':dependencies}
            operation_args=vars(args).copy()
            # Only primitive scene arguments cross the JSON bridge.
            operation_args.pop('project',None)
            if action=='restore':
                import re
                if not re.fullmatch('[0-9a-f]{64}',args.sha256):raise CommandError('Provide a SHA-256 returned by scene history.')
                operation_args['snapshot']=studio.read(project/'.ambiance/scene-history'/f'{args.sha256}.json')
            next_scene=scene_bridge(action,studio.read(scene_path),studio.read(catalog_path),operation_args)
            return save_scene(project,scene_path,next_scene,action)
    raise CommandError('Unsupported command')

def main(argv=None):
    try:
        args=parser().parse_args(argv)
        result=run(args)
        if result is None:return 0
        command=' '.join(filter(None,[args.command,getattr(args,'action',None)]))
        ok=result.get('ok',True) if isinstance(result,dict) else True
        payload={'ok':ok,'schema_version':1,'command':command,'data':result}
        if getattr(args,'out',None) and args.command not in ['asset','render','media'] and not(args.command=='look' and args.action=='export') and not(args.command=='review' and args.action=='draft') and not(args.command=='revision' and args.action=='handoff'):
            studio.write(args.out,payload)
        emit(command,result,ok)
        return 0 if ok else 1
    except CommandError as e:
        print(json.dumps({'ok':False,'schema_version':1,'error':{'code':e.code,'message':str(e)}},indent=2));return e.exit_code
    except (OSError,ValueError,TypeError,KeyError) as e:
        print(json.dumps({'ok':False,'schema_version':1,'error':{'code':'invalid_input','message':str(e)}},indent=2));return 2
    except KeyboardInterrupt:return 130
