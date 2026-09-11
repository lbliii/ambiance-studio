#!/usr/bin/env python3
"""Bounded CLI calibration and fixed-workload cost evidence (no artistic verdict)."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from create_fixture import create, ROOT


def run(project, out, *extra):
    process=subprocess.run([str(ROOT/'ambiance'),'--project',str(project),'scene','activity','--layer','actor','--raster','--long-edge','128','--out',str(out),*map(str,extra)],capture_output=True,text=True)
    result=json.loads(process.stdout)
    if process.returncode: raise ValueError(result)
    return result['data'],len(process.stdout.encode())


def replay(out):
    out=Path(out).resolve();out.mkdir(exist_ok=False,parents=True)
    # Held-out cases were not used to choose the two geometric/contrast warning
    # cutoffs. Labels are synthetic conditions, not claimed perceptual judgments.
    labels=[('visible','tuning',False),('offscreen','tuning',True),('tiny','tuning',True),
            ('hidden','held-out',True),('occluded','held-out',True),('duplicate','held-out',True),
            ('low-contrast','held-out',True),('excessive','held-out',True),('pulse','held-out',True),
            ('painted-visible','held-out-painted',False),('painted-barely','held-out-painted',True),
            ('painted-invisible','held-out-painted',True),('painted-excessive','held-out-painted',True)]
    rows=[]
    for case,split,expected in labels:
        project=create(out/case,case)
        result,size=run(project,out/(case+'-proof'),'--view','portrait','--view','landscape')
        for summary in result['summary']:
            warnings=summary['actions'][0]['warnings'];predicted=bool(warnings)
            rows.append({'case':case,'split':split,'view':summary['view'],'authored_condition_requires_inspection':expected,
                         'warnings':warnings,'outcome':'hit' if predicted and expected else 'false_warning' if predicted else 'miss' if expected else 'correct_clear',
                         'receipt':result['report'],'receipt_sha256':result['report_sha256'],'response_bytes':size,'observation_status':'unreviewed'})
    project=out/'visible';cost=[]
    benchmark=create(out/'benchmark','visible')
    base=json.loads((benchmark/'scene/scene.json').read_text())['layers'][0]
    operations=[]
    for i in range(15):
        values={k:v for k,v in base.items() if k not in ['id','asset']}
        values.update(x=.15+(i%4)*.22,y=.15+(i//4)*.22,width=.12,height=.12,phase_frames=i%2,
                      motion={'x_amplitude':.02,'y_amplitude':.008,'cycles':1+i%3,'phase':i*.3})
        operations.append({'op':'add','id':f'actor-{i+1}','asset':'actor','values':values})
    batch=benchmark/'workload.json';batch.write_text(json.dumps({'version':1,'operations':operations}))
    command=subprocess.run([str(ROOT/'ambiance'),'--project',str(benchmark),'scene','apply',str(batch)],capture_output=True,text=True)
    if command.returncode:raise ValueError(command.stdout)
    for label,views in [('single',['portrait']),('paired',['portrait','landscape'])]:
        for cache in ['cold-process','warm-os-cache']:
            extra=[arg for view in views for arg in ['--view',view]]
            result,size=run(benchmark,out/(label+'-'+cache),*extra,'--long-edge','320')
            cost.append({'workload':label,'layers':16,'stage_side_pixels':320,'production_fps':12,'production_frames':48,
                         'cache_label':cache,'process_policy':'fresh Node process each run; OS caches not flushed',
                         'response_bytes':size,**result['performance'],'report':result['report']})
    matched,_=run(project,out/'matched','--view','portrait','--view','landscape','--compare',project/'comparison.json')
    held=[r for r in rows if r['split'].startswith('held-out')]
    report={'kind':'ambiance-activity-calibration','schema_version':1,'cases':rows,
            'held_out_counts':{name:sum(r['outcome']==name for r in held) for name in ['hit','false_warning','miss','correct_clear']},
            'benchmark':cost,'matched_comparison':matched['report'],
            'limits':['Synthetic brush-mark cases plus held-out copies of repository-cleared painted cloud cels. Conditions are authored fixture labels; no real-film artistic calibration is claimed.',
                      'Excessive activity has no automatic salience detector. A pulse can change an actor residual through overlap; unresolved attribution remains visible as misses.',
                      'No universal score, threshold, listening review or artistic pass. Inspect flagged and unflagged proofs at normal speed.',
                      'Wall time and memory are measurements, never flaky CI thresholds. No renderer optimization was justified by this bounded workload.']}
    path=out/'calibration.json';path.write_text(json.dumps(report,indent=2)+'\n')
    return {'ok':True,'report':str(path),'held_out_counts':report['held_out_counts'],'matched_proof':matched['proof']}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);print(json.dumps(replay(p.parse_args().out)))
