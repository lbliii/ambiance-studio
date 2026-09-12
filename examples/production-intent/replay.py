"""Public CLI replay using local synthetic art, never a completed artistic pilot."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2)+'\n')


def replay(destination, native=False):
    project = destination.resolve(); transcript = []
    def command(*args, expected=0):
        proc = subprocess.run([sys.executable, str(ROOT/'ambiance'), *map(str, args)], capture_output=True, text=True)
        result = json.loads(proc.stdout)
        transcript.append({'args': list(map(str, args)), 'exit_code': proc.returncode, 'result': result})
        if proc.returncode != expected: raise RuntimeError(json.dumps(result))
        return result.get('data', result)
    def run(*args, **kwargs): return command('--project', project, *args, **kwargs)
    command('project', 'init', project, '--title', 'Synthetic production-intent replay')
    image = Image.new('RGB', (160,160), '#2e4052'); draw = ImageDraw.Draw(image)
    draw.rectangle((22,45,136,115), fill='#cfac73'); draw.ellipse((54,54,104,104), fill='#6f8a88')
    path = project/'assets/source.png'; image.save(path); source_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    write(project/'assets/catalog.json', {'version':1,'assets':[{'id':'paint','kind':'plate','file':'assets/source.png','width':160,'height':160,'sha256':source_hash}]})
    # Fixture setup supplies a small authored clock. Production mutations below
    # use the ordinary transaction and plan APIs.
    scene = json.loads((project/'scene/scene.json').read_text()); scene['canvas'].update(width=160,height=160,fps=6,loop_seconds=1)
    write(project/'scene/scene.json', scene)
    write(project/'plans/framing.json', {'version':1,'views':{
        'portrait':{'rect_scene_px':[35,0,90,160],'output':{'width':90,'height':160}},
        'landscape':{'rect_scene_px':[0,35,160,90],'output':{'width':160,'height':90}}}})
    run('view','apply',project/'plans/framing.json'); run('scene','add','paint','--id','plate','--width','1')
    write(project/'plans/asset-inventory.json', {'version':1,'items':[{'id':'room','required':True,'state':'complete','required_parts':[{'id':'plate','stage':'placed','asset_id':'paint','layer_ids':['plate'],'files':[{'file':'assets/source.png','sha256':source_hash}]}]}]})
    plan = json.loads((ROOT/'examples/production-plan.json').read_text())
    plan['story']={'premise':'Two flat shapes demonstrate exact production scope.', 'direction':'Synthetic nearly-still fixture. No film or artistic approval claim.'}
    plan['sources']=[{'id':'paint','path':'assets/source.png','sha256':source_hash}]
    plan['elements'][0]['source_ids']=['paint'];plan['elements'][0]['realization']['layer_ids']=['plate']
    plan['outputs']=[{'view_id':id,'roles':['silent']} for id in ['portrait','landscape']]
    for exp in plan['expectations']:exp['view_ids']=['portrait','landscape']
    pixels={'id':'pixels','rationale':'Actual view raster evidence','direction':'Synthetic executable fixture','stage':'animation',
            'view_ids':['portrait','landscape'],'element_ids':['room'],'action_ids':[],'relation_ids':[],
            'requirement':{'type':'measured','check':'raster'}}
    plan['expectations'].append(pixels);write(project/'plans/proposal.json',plan)
    run('plan','spec','apply',project/'plans/proposal.json','--expect-sha256','absent')
    recipe={'format':'ambiance-iteration','schema_version':2,'id':'paired','revision':'v1','scope':'review',
            'views':['portrait','landscape'],'editions':[{'role':'silent'}],'default':{'view':'portrait','role':'silent'}}
    write(project/'plans/iteration.json',recipe)
    before=run('plan','coverage',expected=1)
    overview=run('project','overview','--details')['production_readiness']
    preflight=run('iteration','preflight',project/'plans/iteration.json',expected=1)['readiness']
    ids=lambda r:[row['id'] for row in r['blocked']]
    if not ids(before)==ids(overview)==ids(preflight):raise AssertionError('Readiness consumers disagree')
    write(project/'plans/selection.json',{'format':'ambiance-revision-selection','schema_version':1,'scene':'scene/scene.json','catalog':'assets/catalog.json'})
    capture=run('revision','capture','v1','--selection',project/'plans/selection.json')
    proof=run('render','views-proof','--view','portrait','--view','landscape','--revision','v1','--seconds','1','--long-edge','160','--out',project/'render/paired')
    evidence=[]
    for view in ['portrait','landscape']:
        evidence.append(run('plan','evidence','pixels','--view',view,'--revision','v1','--receipt','render/paired/render-report.json'))
    after=run('plan','coverage','--revision','v1')
    overview=run('project','overview','--details','--revision','v1')['production_readiness']
    preflight=run('iteration','preflight',project/'plans/iteration.json')['readiness']
    if not after['ready'] or not ids(after)==ids(overview)==ids(preflight):raise AssertionError('Captured readiness consumers disagree')
    export=run('plan','coverage','--stage','export','--revision','v1',expected=1)
    write(project/'reports/fake.json',{'ok':True,'claim':'nonempty arbitrary report'})
    spoof=run('plan','evidence','pixels','--view','portrait','--revision','v1','--receipt','reports/fake.json',expected=2)
    reduced={**recipe,'scope':'final','views':['portrait']};write(project/'plans/reduced.json',reduced)
    reduced_result=run('iteration','preflight',project/'plans/reduced.json',expected=1)
    delivery=None
    if native:
        recipe['scope']='final';write(project/'plans/iteration.json',recipe)
        delivery=run('iteration','run',project/'plans/iteration.json','--by','Synthetic CLI replay')
    report={'format':'ambiance-production-intent-replay','schema_version':1,'ok':True,
            'scope':'Synthetic structure/raster/native validation only; no completed film or artistic observation.',
            'project':str(project),'capture':capture,'raster':proof,'evidence':evidence,
            'before':before,'after':after,'export_before_encoding':export,'spoof_rejected':spoof,
            'reduced_scope':reduced_result,'delivery':delivery,'transcript':str(project/'reports/replay-transcript.json')}
    write(project/'reports/replay-transcript.json',transcript);write(project/'reports/production-intent-replay.json',report)
    print(json.dumps({'ok':True,'report':str(project/'reports/production-intent-replay.json'),'raster':proof['output'],'native':native},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('destination',type=Path);parser.add_argument('--native',action='store_true')
    args=parser.parse_args();replay(args.destination,args.native)
