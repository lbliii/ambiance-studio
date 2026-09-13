#!/usr/bin/env python3
"""Retained public CLI measurement, source preparation, native codec and edition replay."""
import argparse
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from test_audio_measurements import signal
from ambiance_studio.file_identity import digest
from ambiance_studio.checks import source_identity
from PIL import Image


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--native',action='store_true');args=parser.parse_args()
    project=args.out.resolve()
    if project.exists():raise ValueError('Choose a fresh replay output directory')
    project.mkdir(parents=True)
    def save(name,value):(project/name).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    save('ambiance-project.json',{'version':1,'scene':'scene.json','catalog':'catalog.json'})
    save('project.json',{'version':1,'id':'audio02','title':'AUDIO-02 technical fixture','reference':None})
    save('pipeline.json',json.loads((ROOT/'templates/pipeline.json').read_text()))
    Image.new('RGBA',(8,8),(160,100,45,255)).save(project/'paint.png')
    save('scene.json',{'version':1,'canvas':{'width':32,'height':32,'fps':30,'loop_seconds':2,'background':'#182830'},
                      'camera':{'overscan':1,'x_amplitude':0,'y_amplitude':0,'zoom_amplitude':0},'groups':[],
                      'layers':[{'id':'paint','asset':'paint','x':.5,'y':.5,'width':.4,'height':.4,'anchor':[.5,.5],
                                 'scale':1,'rotation':0,'opacity':1,'visible':True,'blend':'source-over','depth':0}]})
    save('catalog.json',{'version':1,'assets':[{'id':'paint','file':'paint.png','width':8,'height':8,'sha256':digest(project/'paint.png')}]})
    steps=[];checks=[];identity=source_identity();save('source-identity.json',identity)
    def cli(*argv,expected=0):
        command=[str(ROOT/'ambiance'),'--project',str(project),*map(str,argv)]
        run=subprocess.run(command,capture_output=True,text=True)
        response=json.loads(run.stdout)
        steps.append({'argv':command,'exit_code':run.returncode,'response':response,'stderr':run.stderr})
        save('replay.json',{'ok':False,'steps':steps,'checks':checks})
        if expected is not None and run.returncode!=expected:raise ValueError(f'Unexpected CLI result: {run.stdout} {run.stderr}')
        return response.get('data',{}),run.returncode
    definitions=[('ebu-1',[(20,-23)],{},-23),('ebu-2',[(20,-33)],{},-33),
                 ('ebu-3',[(10,-36),(60,-23),(10,-36)],{},-23),
                 ('ebu-4',[(10,-72),(10,-36),(60,-23),(10,-36),(10,-72)],{},-23),
                 ('ebu-5',[(20,-26),(20.1,-20),(20,-26)],{},-23)]
    for name,segments,options,expected in definitions:
        signal(project/(name+'.wav'),segments,**options)
        result,_=cli('audio','measure',name+'.wav','--out',project/(name+'.json'))
        value=result['integrated_lufs']['value'];checks.append({'id':name,'lufs':value,'expected':expected,'tolerance':.1,'ok':abs(value-expected)<=.1})
    for number,divisor,phase,amplitude,expected in [(15,4,0,.5,-6),(16,4,45,.5,-6),(17,6,60,.5,-6),(18,8,67.5,.5,-6),(19,4,45,1.41,3)]:
        name=f'ebu-{number}'
        signal(project/(name+'.wav'),[(.2,20*math.log10(amplitude))],frequency=48000/divisor,phase=phase,taper=True)
        result,_=cli('audio','measure',name+'.wav','--out',project/(name+'.json'))
        value=result['true_peak']['dbtp'];checks.append({'id':name,'dbtp':value,'sample_peak_dbfs':result['sample_peak']['dbfs'],'expected':expected,'lower':expected-.4,'upper':expected+.2,'ok':expected-.4<=value<=expected+.2})
    for name,segments,options,status in [('silence',[(1,None)],{},'silence'),('short',[(.399,-23)],{},'insufficient_duration'),('gated',[(1,-80)],{},'below_gate'),('anti-phase',[(1,-23)],{'invert':True},'measured'),('mono',[(1,-23)],{'channels':1},'measured')]:
        signal(project/(name+'.wav'),segments,**options)
        result,_=cli('audio','measure',name+'.wav','--out',project/(name+'.json'))
        checks.append({'id':name,'ok':result['integrated_lufs']['status']==status,'status':result['integrated_lufs']['status'],'mono':result['mono_fold_down']})
    signal(project/'wrong-rate.wav',[(.4,-23)],rate=44100)
    cli('audio','measure','wrong-rate.wav',expected=2)
    cli('audio','measure','ebu-1.wav','--source-sha256','0'*64,expected=2)
    (project/'truncated.wav').write_bytes((project/'short.wav').read_bytes()[:-1])
    cli('audio','measure','truncated.wav',expected=2)
    signal(project/'source.wav',[(2,-18)],frequency=12000,phase=45,taper=True)
    original=digest(project/'source.wav')
    prepared,_=cli('audio','source-prepare','source.wav','--backend','pcm','--source-sha256',original,'--preparation-id','source-preserved')
    working=prepared['working']['path']
    cli('audio','source-check','audio/preparations/source-preserved/receipt.json')
    cli('audio','measure',working,'--source-sha256',prepared['working']['sha256'],'--out',project/'prepared-measurement.json')
    config=project/'test-library-config.json'
    # LIB-01 deliberately requires independence from a checkout and film project.
    # Retain this isolated fixture root and identify it in the final report.
    library_root=Path(tempfile.mkdtemp(prefix='ambiance-audio02-library-'))/'media'
    cli('audio','library','configure','--config',config,'--media-root',library_root,'--library-id','audio02-fixture')
    selected,_=cli('audio','library','import','tone','--config',config,'--version','prepared-v1','--kind','event',
                   '--preparation','audio/preparations/source-preserved/receipt.json','--sha256',prepared['receipt_sha256'])
    materialized,_=cli('audio','library','materialize','tone','--version','prepared-v1','--config',config,
                       '--expect-version',selected['sha256'],'--expect-state',selected['state_sha256'],
                       '--materialization-id','measured-source','--allow-unaccepted')
    library_receipt='audio/library/measured-source/receipt.json'
    cli('audio','library','check',library_receipt)
    working=materialized['source']['path']
    cli('audio','measure',working,'--source-sha256',materialized['source']['sha256'],'--out',project/'library-measurement.json')
    # A source preparation is not a master. This explicit test-only identity
    # recipe declares using that unmodified tone as the complete two-second PCM.
    save('identity-recipe.json',{'operation':'use unchanged prepared synthetic tone as two-second test master','gain_db':0,'normalization':False})
    ref=lambda p:{'path':p,'sha256':digest(project/p)}
    save('master-provenance.json',{'format':'ambiance-external-preparation','schema_version':1,'sources':[ref('source.wav')],
         'recipes':[ref('identity-recipe.json')],'outputs':[ref(working)],'notes':'Technical fixture only; not a production mix or audition.'})
    save('selection.json',{'format':'ambiance-revision-selection','schema_version':1,'scene':'scene.json','catalog':'catalog.json',
         'audio':{'preparations':['audio/preparations/source-preserved/receipt.json',library_receipt,'master-provenance.json'],'masters':[working]}})
    cli('revision','capture','levels-v1','--selection',project/'selection.json')
    native_results=[]
    if args.native:
        for bitrate in [256000,320000,384000]:
            output=project/('native-'+str(bitrate))
            result,code=cli('render','video','--revision','levels-v1','--edition','aac-'+str(bitrate),'--audio',project/working,
                           '--audio-bitrate',bitrate,'--out',output,expected=None)
            if code:
                if bitrate!=384000 or output.exists():raise ValueError('Supported native run failed, or unsupported trial created render artifacts')
                native_results.append({'bitrate_bps':bitrate,'status':'unsupported','output_created':False})
            else:
                a=result['verification']['audio'];m=a['level_measurement']
                assert a['presented_samples']==96000 and m['interval']['frames']==96000
                native_results.append({'bitrate_bps':bitrate,'status':'encoded-and-decoded','estimated_bitrate_bps':a['estimated_encoded_bitrate_bps'],
                    'presented_samples':a['presented_samples'],'raw_decoded_samples':a['raw_decoded_samples'],
                    'source_measurement':result['audio_source_measurement'],'decoded_measurement':m,'edition':result['edition']})
        picture=project/'native-256000/picture.mp4'
        cli('media','compose',picture,'--revision','levels-v1','--edition','composed-320',
            '--picture-receipt','native-256000/render-report.json','--audio',project/working,'--audio-bitrate','320000','--out',project/'compose-320')
        # Exact float dependency must stale the selected edition without affecting source bytes.
        float_path=project/'native-320000/verification/contacts/decoded-audio.f32le'
        original_float=float_path.read_bytes();float_path.write_bytes(original_float+b'x')
        status,_=cli('project','status',expected=None)
        selected=next(e for r in status['revisions'] if r['id']=='levels-v1' for e in r['editions'] if e['id']=='aac-320000')
        checks.append({'id':'changed-float-edition-dependency','ok':'Selected audio_presentation_float changed' in json.dumps(selected),
                       'edition_status':selected})
        float_path.write_bytes(original_float)
        status,_=cli('project','status',expected=None)
        checks.append({'id':'restored-float-edition-dependency','ok':'Selected audio_presentation_float changed' not in json.dumps(status)})
    cli('revision','check','levels-v1')
    checks.append({'id':'original-source-preserved','ok':digest(project/'source.wav')==original})
    files={str(p.relative_to(project)):{'sha256':digest(p),'bytes':p.stat().st_size} for p in sorted(project.rglob('*')) if p.is_file() and '.ambiance' not in p.relative_to(project).parts and p.name!='replay.json'}
    ok=all(c['ok'] for c in checks)
    save('replay.json',{'ok':ok,'steps':steps,'checks':checks,'native':native_results,'artifacts':files,
         'library_root':str(library_root),'library_artifacts':{str(p):{'sha256':digest(p),'bytes':p.stat().st_size} for p in library_root.rglob('*') if p.is_file()},
         'source':{'commit':identity['commit'],'tracked_tree_sha256':identity['tracked_tree_sha256']},
         'listening':'unperformed','reference_scope':'EBU Tech3341 deterministic definitions 1-5 and15-19; not EBU recordings or full conformance certification'})
    print(json.dumps({'ok':ok,'report':str(project/'replay.json'),'sha256':digest(project/'replay.json')}))
    return 0 if ok else 1


if __name__=='__main__':sys.exit(main())
