"""Compact prepare commands, resumable proofs and source-mapped scene adoption."""
import copy
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys

import studio
from . import asset_prep as ap, compound_preparation as cp, preparation
from .generation_ledger import canonical, identifier
from .project import project_lock

ROOT = Path(__file__).resolve().parents[1]
ACTIONS = ('init', 'inspect', 'check', 'edit', 'build', 'proof', 'place')


def cli(project, *args):
    process = subprocess.run([sys.executable, str(ROOT/'ambiance'), '--project', str(project), *map(str,args)], capture_output=True, text=True)
    if process.returncode: raise ValueError(process.stdout.strip() or process.stderr.strip())
    return json.loads(process.stdout)['data']


def proof(project, directory, out, long_edge=640, resume=False):
    directory,out=Path(directory).resolve(),Path(out).resolve();ap.relative(Path(project).resolve(),out)
    recipe,receipt=cp.artifact(directory)
    integer = __import__('ambiance_studio.edge_quality',fromlist=['integer']).integer
    integer(long_edge,'proof long edge',32,2048)
    views=list(receipt['views']) or ['authored']
    if len(views)>8: raise ValueError('Preparation proof supports at most 8 selected views')
    identity={'preparation_receipt_sha256':ap.sha((directory/'preparation-receipt.json').read_bytes()),
              'artifact_sha256':ap.sha((directory/'artifact.json').read_bytes()),'long_edge':long_edge,'views':views,
              'renderer_sha256':ap.sha((ROOT/'tools/render-scene.mjs').read_bytes()),
              'engine_sha256':ap.sha((ROOT/'editor/engine.mjs').read_bytes())}
    with project_lock(project):
        if out.exists():
            if not resume: raise ValueError('Proof directory exists; use --resume for its exact preparation and options')
            run=ap.load(out/'proof-run.json')
            if run['identity']!=identity: raise ValueError('Preparation/options/runtime changed; use a fresh proof directory')
        else:
            out.mkdir(parents=True);run={'format':'ambiance-preparation-proof','version':1,'identity':identity,'steps':{},'status':'running','observations':[]}
            studio.write(out/'proof-run.json',run)
        variants={'normal':[], 'subjects-hidden':[p['id'] for p in recipe['parts'] if p['kind']=='cutout'],
                  'foreground-hidden':[p['id'] for p in recipe['parts'] if p['kind']=='occluder']}
        for name,hidden in variants.items():
            result_dir=Path(run['steps'][name]['files_base']) if name in run['steps'] else out/name
            if name in run['steps']:
                for relative,digest in run['steps'][name]['files'].items():
                    if ap.sha(ap.project_file(result_dir,relative).read_bytes())!=digest: raise ValueError(f'Completed proof step changed: {name}/{relative}')
                continue
            # Interrupted attempts remain for diagnosis; retry into a distinct local attempt.
            attempt=1
            while (out/f'{name}-attempt-{attempt}').exists(): attempt+=1
            attempt_dir=out/f'{name}-attempt-{attempt}';attempt_dir.mkdir()
            preview=attempt_dir/'project';shutil.copytree(directory/'preview-project',preview)
            scene=ap.load(preview/'scene.json')
            for layer in scene['layers']:
                if layer['id'] in hidden: layer['visible']=False
            ap.write(preview/'scene.json',scene)
            result=cli(preview,'render','views-proof','--out',attempt_dir/'render','--seconds',recipe['seconds'],
                       '--long-edge',long_edge,*[arg for id in views for arg in ['--view',id]])
            # Capture rest/extreme from the same view-aware renderer; no alternate Pillow motion model.
            for pose,t in [('rest',0),('extreme',recipe['seconds']/2)]:
                for view in views:
                    info=receipt['views'].get(view)
                    if info:
                        width,height=info['output']['width'],info['output']['height']
                    else: width,height=scene['canvas']['width'],scene['canvas']['height']
                    divisor=math.gcd(width,height);unitw,unith=width//divisor,height//divisor;n=long_edge//max(unitw,unith)
                    if n<1: raise ValueError('Proof long edge cannot fit the saved integer aspect ratio')
                    cli(preview,'render','frame','--time',t,'--view',view,'--width',unitw*n,'--out',attempt_dir/f'{pose}-{view}')
            # Keep paths stable: record the actual attempt, do not move files whose render receipts use absolute paths.
            run['steps'][name]={'directory':str(attempt_dir),'render':result,'files':{str(p.relative_to(attempt_dir)):ap.sha(p.read_bytes()) for p in attempt_dir.rglob('*') if p.is_file() and '.ambiance' not in p.parts}}
            # Result-directory alias is never a symlink; resume resolves the recorded attempt explicitly.
            run['steps'][name]['files_base']=str(attempt_dir)
            cp.artifact(directory)
            studio.write(out/'proof-run.json',run)
        run['status']='complete';run['review_status']='unreviewed'
        run['review_needed']=['Inspect hidden/rest/extreme in every view for duplicate old paint, attached foreground fragments and missing reconstruction.',
                              'Watch the exact normal-speed artifact in each view; record observer, display size, timestamps and observations separately.']
        links=[]
        import html
        for name,step in run['steps'].items():
            render_dir=Path(step['directory'])/'render'
            links.append(f'<li>{html.escape(name)}: <a href="{html.escape(str((render_dir/"index.html").relative_to(out)))}">synchronized views and normal-speed playback</a></li>')
        (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Compound preparation proof</title><h1>Compound preparation proof</h1><p>Unreviewed raster evidence. Hidden/rest/extreme and ordinary playback require observations.</p><ul>'+''.join(links)+'</ul>')
        studio.write(out/'proof-run.json',run)
    return {'ok':True,'report':str(out/'proof-run.json'),'html':str(out/'index.html'),'status':'complete','views':views,'steps':{k:v['directory'] for k,v in run['steps'].items()},'review_status':'unreviewed'}


def place(project, directory, base, prefix=None, expected=None, dry_run=False):
    from .scene_transactions import scene_transaction
    from .scene_commands import apply_batch
    from . import assets, scene_authoring
    directory=Path(directory).resolve();recipe,receipt=cp.artifact(directory)
    if not base: raise ValueError('prepare place requires --base naming the existing source plane')
    prefix=identifier(prefix or directory.name,'placement prefix')
    # Compiler/admission are immutable and idempotent checkpoints. A failure preserves complete packs.
    pack_dir=directory.parent/(directory.name+'-packs')
    for id in receipt['outputs']:
        cli(project,'asset','build',directory/'compiler'/f'{id}.json','--out',pack_dir/id)
        cli(project,'asset','admit',pack_dir/id)
    with scene_transaction(project,expected) as transaction:
        cp.artifact(directory)
        dependencies=[]
        verified=cp.validate_preparation_receipt(directory/'preparation-receipt.json',ap.sha((directory/'preparation-receipt.json').read_bytes()),
                                               [ap.project_file(project,receipt['outputs']['backing']['image']['file'])])
        for dep in verified['dependencies']: dependencies.append(scene_authoring.file_dependency(dep['path'],dep['role']))
        dependencies.append(scene_authoring.file_dependency(directory/'preparation-receipt.json','preparation receipt'))
        byid={a['id']:a for a in transaction.catalog['assets']};layer=next((l for l in transaction.scene['layers'] if l['id']==base),None)
        if not layer: raise ValueError('Preparation placement base is absent')
        old=byid[layer['asset']];new=byid[ap.load(directory/'compiler/backing.json')['id']]
        def mapping(asset):
            data=asset.get('registration_mapping',{})
            if data.get('reference')!=recipe['source'] or len(data.get('cels',[]))!=1: raise ValueError('Base must have a one-cel compiler source map identifying the preparation reference')
            matrix=data['cels'][0]['reference_to_cell']
            if matrix[1]!=0 or matrix[2]!=0 or matrix[0]<=0 or matrix[3]<=0: raise ValueError('Base cell mapping must have positive aligned source axes')
            return matrix,data['cell_size']
        before,bs=mapping(old);after,ns=mapping(new);convert=ap.multiply(after,ap.inverse(before))
        value=copy.deepcopy(layer);value['asset']=new['id']
        anchor=layer.get('anchor',old.get('pivot',[.5,.5]));px,py=anchor[0]*bs[0],anchor[1]*bs[1]
        value['anchor']=[(convert[0]*px+convert[4])/ns[0],(convert[3]*py+convert[5])/ns[1]]
        value['width']=layer['width']/bs[0]*before[0]/after[0]*ns[0];value['height']=layer['height']/bs[1]*before[3]/after[3]*ns[1]
        sockets={**old.get('sockets',{}),**layer.get('sockets',{})}
        for socket,uv in sockets.items():
            if not isinstance(uv,list) or len(uv)!=2: raise ValueError('Dynamic base sockets need explicit migration before preparation placement')
            sockets[socket]=[(convert[0]*uv[0]*bs[0]+convert[4])/ns[0],(convert[3]*uv[1]*bs[1]+convert[5])/ns[1]]
        if sockets: value['sockets']=sockets
        batch={'version':1,'operations':[{'op':'replace','layer':base,'value':value}]}
        for part in sorted(recipe['parts'],key=lambda p:p['kind']=='occluder'):
            id=part['id'];asset=byid[ap.load(directory/'compiler'/f'{id}.json')['id']]
            matrix,cs=mapping(asset);px,py=part['pivot'];anchor=[(matrix[0]*px+matrix[4])/cs[0],(matrix[3]*py+matrix[5])/cs[1]]
            if any(v<0 or v>1 for v in anchor): raise ValueError('Prepared anchor falls outside padded cell')
            batch['operations'].append({'op':'place_from_source','id':prefix+'-'+id,'asset':asset['id'],'base':base,
                                        'mode':'native','reference':recipe['source'],'anchor':anchor})
        return apply_batch(transaction,batch,'prepare-place',dry_run=dry_run,dependencies=dependencies,
                           details={'preparation_receipt':str(directory/'preparation-receipt.json'),'proof_motion_adopted':False,
                                    'companions':'Compiled and admitted with owner metadata; bind their receiving surface explicitly.'})


def run(args, project):
    action=str(args.source) if args.source is not None else None
    if action not in ACTIONS:
        if args.target is not None: raise ValueError('Unexpected second source argument')
        if args.out is None: raise ValueError('asset prepare requires --out')
        if args.recipe and ap.load(args.recipe).get('format')==cp.FORMAT: return cp.build(project,args.recipe,args.out)
        return preparation.build(project,args.out,args.recipe,args.source,args.backing,args.backing_to_source)
    if args.target is None: raise ValueError(f'prepare {action} requires a recipe/artifact path')
    if action in ['inspect','check']: return cp.inspect(project,args.target,check=action=='check')
    if action=='place': return place(project,args.target,args.base,args.prefix,args.expect_sha256,args.dry_run)
    if args.out is None: raise ValueError(f'prepare {action} requires --out')
    if action=='init': return cp.initialize(project,args.target,args.out,args.context)
    if action=='build': return cp.build(project,args.target,args.out)
    if action=='edit':
        if args.batch is None: raise ValueError('prepare edit requires --batch')
        return cp.edit(project,args.target,args.batch,args.out,args.expect_sha256)
    return proof(project,args.target,args.out,args.long_edge,args.resume)
