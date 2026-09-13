"""WF-04/05 public argv replay; synthetic local media and no artistic approvals."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import studio
from PIL import Image, ImageDraw
from test_production_coverage import fixture


def snapshot(project):
    return {str(p.relative_to(project)):studio.digest(p) for p in project.rglob('*') if p.is_file()}


def replay(out):
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    sources=[*sorted((ROOT/'ambiance_studio').glob('*.py')),ROOT/'studio.py',ROOT/'templates/workflows/painted-film.v1.json',
             ROOT/'editor/engine.mjs',Path(__file__),ROOT/'tests/test_production_coverage.py']
    before_sources={str(p.relative_to(ROOT)):studio.digest(p) for p in sources}
    records=[];report={'format':'ambiance-workflow-packets-replay','schema_version':1,'records':records,'source_hashes':before_sources,
        'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'meaning':'Synthetic engineering fixture. Native operations and decode are real; no artistic or human audition acceptance.'}
    def run(name,project,*args,code=0,argv=None):
        vector=argv or [str(ROOT/'ambiance'),'--project',str(project),*map(str,args)]
        start=time.monotonic();process=subprocess.run(vector,cwd=ROOT,text=True,capture_output=True)
        path=out/(name+'.json');path.write_text(process.stdout)
        stderr=out/(name+'.stderr.txt');stderr.write_text(process.stderr)
        row={'name':name,'argv':vector,'exit_code':process.returncode,'expected_exit_code':code,
             'seconds':round(time.monotonic()-start,3),'stdout':str(path),'sha256':studio.digest(path),'bytes':path.stat().st_size,
             'stderr':str(stderr),'stderr_sha256':studio.digest(stderr)}
        records.append(row);studio.write(out/'run.json',report)
        assert process.returncode==code,(name,process.stdout,process.stderr)
        return json.loads(process.stdout)
    def action(name,project,operation,stage=None):
        args=['workflow','inspect','--limit','100']+(['--stage',stage] if stage else [])
        output=run(name,project,*args)['data']
        row=next(r for r in output['items'] if r['operation']==operation)
        return row,output['assessment']['sha256']
    def prepare(name,project,row,token,inputs=None,stage=None):
        directory=project/name
        args=['workflow','prepare',row['id'],'--out',directory,'--expect-assessment',token]
        if inputs:args+=['--inputs',inputs]
        if stage:args+=['--stage',stage]
        return run(name,project,*args)['data']
    try:
        blank=out/'blank'
        run('01-init-auto',blank,'--guidance','auto','project','init',blank,'--format','dual')
        row,token=action('02-blank-inspect',blank,'intent.author','intent')
        state=snapshot(blank);draft=prepare('03-incomplete-intent',blank,row,token,stage='intent')
        assert not draft['ready_to_run'] and draft['argv'] is None
        assert state=={k:v for k,v in snapshot(blank).items() if not k.startswith('03-incomplete-intent/')}
        project=fixture(out)
        (project/'plans/production-plan.json').unlink()
        row,token=action('04-intent-inspect',project,'intent.author','intent')
        native=prepare('05-complete-intent',project,row,token,project/'proposal.json','intent')
        assert native['ready_to_run']
        run('06-consume-plan-packet',project,argv=native['argv'])
        # Native artifacts remain service-owned with auto guidance, including cache hits.
        art=project/'assets'
        image=Image.new('RGBA',(24,24));ImageDraw.Draw(image).ellipse((5,3,18,21),fill='#d49654');image.save(art/'isolated.png')
        recipe={'version':1,'id':'packet-art','input':{'frames':['isolated.png']},
            'registration':{'mode':'fixed','point':[12,12],'target':[.5,.5]},'output':{'cell_size':[28,28],'columns':1,'padding':2}}
        studio.write(art/'compiler.json',recipe)
        build=run('07-build-auto',project,'--guidance','auto','asset','build',art/'compiler.json','--out',art/'pack')
        assert build['guidance']['output_ownership']=='artifact-directory'
        original=snapshot(art/'pack')
        run('08-build-off-cache',project,'asset','build',art/'compiler.json','--out',art/'pack')
        assert original==snapshot(art/'pack')
        row,token=action('09-proof-action',project,'asset.proof','assets')
        packet=prepare('10-direct-proof-packet',project,row,token,stage='assets')
        assert packet['ready_to_run']
        proof=run('11-consume-proof-packet',project,argv=[packet['argv'][0],'--guidance','auto',*packet['argv'][1:]])
        assert proof['data']['html']==proof['guidance']['native_facts']['html']
        row,token=action('12-review-action',project,'review.draft','intent')
        review=prepare('13-review-draft',project,row,token,stage='intent')
        assert not review['ready_to_run']
        review_input=studio.read(Path(review['native_files'][0]));assert all(c['result']=='not-run' for c in review_input['checks'])
        review_input['recorder']='WF-04/05 engineering replay (unperformed observations)'
        studio.write(project/'review-input.json',review_input)
        run('14-consume-unperformed-review',project,'--guidance','auto','review','record',project/'review-input.json')
        request={'format':'ambiance-iteration-request','schema_version':1,'id':'packet-movie','revision':'packet-revision',
            'views':['portrait','landscape'],'editions':[{'role':'silent'}],'default':{'view':'portrait','role':'silent'},'scope':'proof','long_edge':160}
        studio.write(project/'request.json',request)
        row,token=action('15-iteration-action',project,'iteration.init','export')
        before=snapshot(project)
        iteration=prepare('16-iteration-packet',project,row,token,project/'request.json','export')
        assert before=={k:v for k,v in snapshot(project).items() if not k.startswith('16-iteration-packet/')}
        assert iteration['ready_to_run']
        preflight=run('17-consume-preflight',project,argv=iteration['argv'],code=1)
        assert preflight['data']['may_render'] and preflight['data']['scope']=='proof'
        run('18-consume-iteration-run',project,'--guidance','auto','iteration','run',project/'16-iteration-packet/iteration.json','--by','WF-04/05 engineering replay')
        selected=run('19-present-full',project,'--guidance','full','delivery','present','packet-movie','--by','WF-04/05 engineering replay')
        subjects=selected['guidance']['reassessment']['subjects']
        assert len(subjects)==2 and {s['view'] for s in subjects}=={'portrait','landscape'}
        assert len({s['edition'] for s in subjects})==2
        # Stale token refuses publication with every existing packet preserved.
        row,token=action('20-review-fresh-token',project,'review.draft','intent')
        (project/'plans/brief.md').write_text('Changed explicit engineering brief for stale-token test')
        protected=snapshot(project/'13-review-draft')
        stale=run('21-stale-prepare',project,'workflow','prepare',row['id'],'--stage','intent','--expect-assessment',token,'--out',project/'stale-packet',code=2)
        assert stale['error']['code']=='stale_assessment' and not (project/'stale-packet').exists()
        assert protected==snapshot(project/'13-review-draft')
        # A real native mutation succeeds, then full guidance rejects a malformed
        # workflow selector. All original success fields and snapshot survive.
        settings=studio.read(project/'project.json');saved_plan=(project/'plans/production-plan.json').read_bytes()
        invalid=dict(settings,intended_views='invalid selector fixture');studio.write(project/'project.json',invalid)
        (project/'plans/production-plan.json').write_text('{ unavailable plan fixture')
        studio.write(project/'change.json',{'version':1,'operations':[{'op':'set','layer':'plate','values':{'x':0.4}}]})
        previous=studio.digest(project/'scene/scene.json')
        changed=run('22-mutation-guidance-failure',project,'--guidance','full','scene','apply',project/'change.json')
        assert changed['ok'] and changed['guidance']['diagnostic']['code']=='guidance_unavailable'
        assert changed['data']['sha256']==studio.digest(project/'scene/scene.json')!=previous
        assert studio.digest(project/f'.ambiance/scene-history/{previous}.json')==previous
        studio.write(project/'project.json',settings);(project/'plans/production-plan.json').write_bytes(saved_plan)
        check=run('23-check-auto-report',project,'--guidance','auto','scene','check','--out',project/'check.json')
        assert 'guidance' not in studio.read(project/'check.json') and studio.read(project/'check.json')['data']==check['data']
        frame=run('24-current-raster',project,'render','frame','--time','0','--view','portrait','--out',project/'raster')
        report.update(ok=True,source_unchanged=before_sources=={str(p.relative_to(ROOT)):studio.digest(p) for p in sources},
                      packet_consumption=['plan spec apply','asset proof','review record (not-run)','iteration preflight','iteration run'],
                      actual_observations='Native dual-view encode/decode receipts exist. Raster/playback observations are recorded separately after inspection.',
                      project=str(project),picture=frame['data'])
        assert report['source_unchanged'],'Source changed during replay'
    except BaseException as error:
        report.update(ok=False,error=repr(error));raise
    finally:
        studio.write(out/'run.json',report)
    return {'ok':True,'report':str(out/'run.json'),'sha256':studio.digest(out/'run.json'),'calls':len(records)}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
    print(json.dumps(replay(parser.parse_args().out),indent=2))
