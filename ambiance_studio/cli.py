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
    group=sub.add_parser('scene').add_subparsers(dest='action',required=True)
    group.add_parser('inspect');q=group.add_parser('sample');q.add_argument('--time',type=float,required=True)
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
    q=group.add_parser('record');q.add_argument('file',type=Path)
    q=sub.add_parser('preview',help='Serve this project read-only on localhost');q.add_argument('--port',type=int,default=8783)
    q=sub.add_parser('test',help='Run local regression checks without paid providers');q.add_argument('--out',type=Path)
    return p

def run(args):
    command=args.command;action=getattr(args,'action',None)
    if command=='doctor':
        pillow=importlib.util.find_spec('PIL') is not None
        return {'version':__version__,'root':str(ROOT),'python':platform.python_version(),'python_executable':sys.executable,
            'node':shutil.which('node'),'pillow':pillow,'ffmpeg':shutil.which('ffmpeg'),'ffprobe':shutil.which('ffprobe'),
            'capabilities':{'project_and_reviews':True,'asset_preparation':pillow,'scene_operations':bool(shutil.which('node')),'preview':bool(shutil.which('node')),'final_video_export':False,'audio_arrangement':False},
            'note':'Optional dependency availability does not imply a renderer or provider adapter is implemented.'}
    if command=='test':
        require_node();asset_tool()
        commands=[[sys.executable,'-m','unittest','discover','-s','tests','-p','test_*.py'],['node','editor/verify-engine.mjs'],['node','tests/test-rig.mjs'],[sys.executable,'tools/package_audit.py']]
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
        pack=args.pack.resolve();report=studio.read(pack/'report.json')
        unchanged=all(studio.inside(pack,f).is_file() and studio.digest(studio.inside(pack,f))==h for f,h in report['outputs'].items())
        return {'ok':unchanged,'asset':studio.read(pack/'asset.json'),'build':report}
    project=project_path(args.project)
    if command=='project' and action=='status':return studio.gate_status(project)
    if command in ['project','scene'] and action=='check':return check_project(project)
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
            draft=studio.review_template(project,args.gate)
            if args.out.exists():raise CommandError('Review draft already exists.')
            studio.write(args.out,draft);return {'draft':str(args.out.resolve()),'review':draft}
        with project_lock(project):return studio.record_review(project,args.file)
    if command=='scene':
        if action in ['inspect','sample']:return scene_bridge(action,studio.read(scene_path),studio.read(catalog_path),{'time':getattr(args,'time',None)})
        if action=='history':
            return {'snapshots':[{'sha256':p.stem,'path':str(p)} for p in sorted((project/'.ambiance/scene-history').glob('*.json'))]}
        with project_lock(project):
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
        if getattr(args,'out',None) and args.command!='asset' and not(args.command=='review' and args.action=='draft'):
            studio.write(args.out,payload)
        emit(command,result,ok)
        return 0 if ok else 1
    except CommandError as e:
        print(json.dumps({'ok':False,'schema_version':1,'error':{'code':e.code,'message':str(e)}},indent=2));return e.exit_code
    except (OSError,ValueError,TypeError,KeyError) as e:
        print(json.dumps({'ok':False,'schema_version':1,'error':{'code':'invalid_input','message':str(e)}},indent=2));return 2
    except KeyboardInterrupt:return 130
