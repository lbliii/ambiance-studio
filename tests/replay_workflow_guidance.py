"""WF-02/03 actual public CLI replay. Local synthetic art; no artistic verdicts."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from PIL import Image,ImageDraw
import studio
from ambiance_studio import preparation
from test_production_coverage import fixture


def snapshot(project):
    return {str(p.relative_to(project)):studio.digest(p) if p.is_file() else 'directory' for p in project.rglob('*')}


def replay(out):
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    records=[]
    def run(name,project,*args,code=0,pure=False,argv=None,bounded=False):
        argv=argv or [str(ROOT/'ambiance'),'--project',str(project),*map(str,args)]
        before=snapshot(project) if pure else None;started=time.monotonic()
        process=subprocess.run(argv,cwd=ROOT,text=True,capture_output=True)
        target=out/(name+'.json');target.write_text(process.stdout)
        if process.returncode!=code:raise AssertionError(f'{name}: expected {code}, got {process.returncode}: {process.stdout} {process.stderr}')
        if pure and before!=snapshot(project):raise AssertionError(name+': query changed project bytes')
        if bounded and target.stat().st_size>16384:raise AssertionError(name+': default envelope exceeds 16 KiB')
        records.append({'name':name,'argv':argv,'exit_code':process.returncode,'elapsed_seconds':round(time.monotonic()-started,3),
                        'project_unchanged':pure and before==snapshot(project),'output':{'path':str(target),'sha256':studio.digest(target),'bytes':target.stat().st_size}})
        value=json.loads(process.stdout)
        return value.get('data',value)
    blank=out/'blank'
    run('01-blank-init',blank,'project','init',blank)
    initial=run('02-blank-intent',blank,'workflow','inspect',pure=True,bounded=True)
    assert [r['operation'] for r in initial['items'][:2]]==['reference.inspect','intent.author']
    project=fixture(out)
    initial=run('03-inspect',project,'workflow','inspect',pure=True,bounded=True)
    guided=run('04-guided-next',project,'project','next','--guided',pure=True,bounded=True)
    first=next(r for r in initial['items'] if r['operation']=='asset.proof')
    explained=run('05-explain',project,'workflow','explain',first['id'],'--expect-assessment',initial['assessment']['sha256'],pure=True)
    run('06-suggested-asset-proof',project,argv=explained['action']['argv'])
    # Source separation begins from the actual single-recipe initializer contract.
    art=project/'assets';backing=Image.new('RGBA',(48,64),'#162034');backing.save(art/'backing.png')
    source=backing.copy();ImageDraw.Draw(source).rectangle((12,20,24,36),fill='#ddb84e');source.save(art/'separation.png')
    recipe=preparation.initial_recipe(project,art/'separation.png',art/'backing.png');recipe['motion']['seconds']=1
    poly={'operation':'add','points':[[12,20],[24,20],[24,36],[12,36]]}
    recipe['masks']['removal']['polygons']=[poly];recipe['masks']['cutout']['polygons']=[poly]
    native=project/'plans/separation.json';studio.write(native,recipe)
    run('07-prepare-native-help',project,'workflow','stage','assets','--details',pure=True)
    initialized=run('08-prepare-init',project,'asset','prepare','init',native,'--out',project/'preparation/initial')
    checked=run('09-prepare-check-unresolved',project,'asset','prepare','check',initialized['recipe'],code=1)
    batch=project/'plans/preparation-edit.json';studio.write(batch,{'version':1,'operations':[{'op':'remove-part','part':'foreground'}]})
    initialized=run('09a-native-correction',project,'asset','prepare','edit',initialized['recipe'],'--batch',batch,'--expect-sha256',initialized['sha256'],'--out',project/'preparation/corrected')
    run('09b-prepare-check-corrected',project,'asset','prepare','check',initialized['recipe'])
    inventory=studio.read(project/'plans/asset-inventory.json')
    inventory['items'].append({'id':'separation','required_parts':[{'id':'body','stage':'source','files':[{'file':str(Path(initialized['recipe']).relative_to(project)),'sha256':studio.digest(initialized['recipe'])}]}]})
    studio.write(project/'plans/asset-inventory.json',inventory)
    actions=run('10-separation-actions',project,'workflow','stage','assets','--limit','100',pure=True)
    candidate=next(r for r in actions['items'] if r['operation']=='prepare.build')
    assert candidate['state']=='ready',candidate
    prepared=run('11-suggested-prepare-build',project,argv=candidate['argv'])
    run('12-prepare-inspect',project,'asset','prepare','inspect',project/'reports/workflow'/Path(candidate['argv'][-1]).name,pure=True)
    # Already-isolated artwork goes to preflight/compiler, never source separation.
    isolated=Image.new('RGBA',(24,24));ImageDraw.Draw(isolated).ellipse((4,3,19,21),fill='#baa667');isolated.save(art/'isolated.png')
    compiler={'version':1,'id':'isolated','input':{'frames':['isolated.png']},'registration':{'mode':'fixed','point':[12,12],'target':[.5,.5]},'output':{'cell_size':[28,28],'columns':1,'padding':2}}
    compiler_path=art/'isolated-recipe.json';studio.write(compiler_path,compiler)
    inventory=studio.read(project/'plans/asset-inventory.json');inventory['items'].append({'id':'isolated','required_parts':[{'id':'cutout','stage':'prepared','files':[{'file':'assets/isolated-recipe.json','sha256':studio.digest(compiler_path)}]}]});studio.write(project/'plans/asset-inventory.json',inventory)
    run('13-isolated-preflight',project,'asset','preflight',art/'isolated.png','--out',project/'preparation/isolated-preflight')
    actions=run('14-isolated-actions',project,'workflow','stage','assets','--limit','100',pure=True)
    candidate=next(r for r in actions['items'] if r['operation']=='asset.build')
    assert candidate['state']=='ready',candidate
    compiled=run('15-suggested-isolated-build',project,argv=candidate['argv'])
    run('16-native-pack-inspect',project,'asset','inspect',candidate['argv'][-1],pure=True)
    # Wrong-view and stale evidence remain findings from WF-01, not workflow heuristics.
    proof=run('17-portrait-proof',project,'render','views-proof','--view','portrait','--seconds','1','--long-edge','160','--out',project/'render/portrait')
    run('18-register-portrait',project,'plan','evidence','pixels','--view','portrait','--receipt',Path(proof['report']).relative_to(project))
    portrait=run('19-correct-view',project,'workflow','stage','animation','--view','portrait',pure=True)
    landscape=run('20-wrong-view',project,'workflow','stage','animation','--view','landscape',pure=True)
    assert not any(r.get('expectation_id')=='pixels' for r in portrait['stages'][0]['subjects'][0]['coverage'].get('blocked',[]))
    assert any(r.get('expectation_id')=='pixels' for r in landscape['stages'][0]['subjects'][0]['coverage']['blocked'])
    run('21-capture',project,'revision','capture','v1','--selection',project/'plans/selection.json')
    # Native encoded entries use different revisions and per-entry view identities.
    run('22-capture-second',project,'revision','capture','v2','--selection',project/'plans/selection.json')
    editions=[]
    for index,(view,revision,width,height) in enumerate([('portrait','v1',90,160),('landscape','v2',160,90)]):
        movie=run(f'23{index}-native-{view}',project,'render','video','--revision',revision,'--edition',view+'-silent','--view',view,'--width',width,'--height',height,'--seconds','1','--out',project/'render'/('movie-'+view))
        editions.append({'view':view,'role':'silent','revision':revision,'edition':view+'-silent'})
    selection={'format':'ambiance-delivery-selection','schema_version':2,'id':'pair','title':'Synthetic workflow replay','default':{'view':'portrait','role':'silent'},'entries':editions}
    declaration=project/'plans/delivery.json';studio.write(declaration,selection)
    run('24-register-delivery',project,'delivery','import',declaration)
    run('25-select-review',project,'delivery','present','pair','--by','WF-02/03 engineering replay')
    selected=run('26-selected-pair',project,'workflow','inspect','--subject','review',pure=True,bounded=True)
    assert {s['revision'] for s in selected['subjects']}=={'v1','v2'}
    assert {s['view'] for s in selected['subjects']}=={'portrait','landscape'}
    run('27-selected-guided',project,'project','next','--guided','--subject','review',pure=True,bounded=True)
    run('28-selected-revision-only',project,'workflow','stage','intent','--revision','v1',pure=True)
    run('29-selected-edition',project,'workflow','inspect','--revision','v1','--edition','portrait-silent',pure=True,bounded=True)
    run('30-invalid-view',project,'workflow','inspect','--revision','v1','--edition','portrait-silent','--view','landscape',code=2,pure=True)
    token=initial['assessment']['sha256']
    run('31-stale-action-token',project,'workflow','explain',first['id'],'--expect-assessment',token,code=2,pure=True)
    # Hold an actual writer lock and remove write permissions during public reads.
    (project/'.ambiance/write.lock').write_text('Replay-held writer')
    paths=[project,*project.rglob('*')];modes={p:p.stat().st_mode&0o777 for p in paths}
    for p in paths:p.chmod(0o555 if p.is_dir() else 0o444)
    try:run('32-locked-readonly',project,'project','next','--guided',pure=True,bounded=True)
    finally:
        for p,mode in modes.items():p.chmod(mode)
    (project/'.ambiance/write.lock').unlink()
    frame=Path(proof['report']).parent/'portrait/00000.png';frame.write_bytes(frame.read_bytes()+b'changed fixture')
    stale=run('33-stale-evidence',project,'workflow','stage','animation','--view','portrait',pure=True)
    assert not stale['stages'][0]['subjects'][0]['coverage']['ready']
    working_pipeline=studio.read(project/'pipeline.json');working_pipeline['gates'][0]['criteria'].append({'id':'custom','kind':'human','description':'Synthetic custom pipeline criterion'})
    studio.write(project/'pipeline.json',working_pipeline)
    custom=run('34-custom-pipeline',project,'workflow','stage','intent',pure=True)
    assert 'custom' in custom['stages'][0]['subjects'][0]['custom_criteria']
    (project/'scene/scene.json').write_text('{malformed scene')
    partial=run('35-partial-scene',project,'workflow','stage','intent',pure=True)
    assert partial['stages'][0]['subjects'][0]['criteria']==working_pipeline['gates'][0]['criteria']
    captured=run('36-captured-after-working-damage',project,'workflow','stage','intent','--revision','v1',pure=True)
    assert len(captured['stages'][0]['subjects'][0]['criteria'])==3
    paths=[*sorted((ROOT/'ambiance_studio').glob('*.py')),ROOT/'studio.py',ROOT/'templates/workflows/painted-film.v1.json',Path(__file__)]
    manifest={'format':'ambiance-wf0203-replay','schema_version':1,'ok':True,'commands':records,'project':str(project),
              'source_files':{str(p.relative_to(ROOT)):studio.digest(p) for p in paths},'project_files':snapshot(project),
              'limits':['Actual native raster, preparation, compiler and encode/decode operations; synthetic painted geometry only.',
                        'No listening, artistic acceptance, human observation, publication or WF-04–07 adoption trial is claimed.']}
    target=out/'replay.json';studio.write(target,manifest)
    return {'ok':True,'commands':len(records),'manifest':str(target),'sha256':studio.digest(target)}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
    print(json.dumps(replay(parser.parse_args().out),indent=2))
