#!/usr/bin/env python3
"""Public CLI audio source replay on a fresh disposable project; no provider calls."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import wave

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from ambiance_studio.file_identity import digest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--source',type=Path,help='Copy an existing source into the new fixture; original remains read-only')
    p.add_argument('--backend',choices=['pcm','macos-afconvert'],default='pcm');p.add_argument('--provenance',type=Path)
    args=p.parse_args();project=args.out.resolve()
    if project.exists():raise ValueError('Replay output must be fresh')
    project.mkdir(parents=True)
    def write(name,data):(project/name).write_text(json.dumps(data,indent=2)+'\n')
    write('ambiance-project.json',{'version':1,'scene':'scene.json','catalog':'catalog.json'})
    write('project.json',{'version':1,'title':'Audio source replay','reference':None})
    write('pipeline.json',{'version':1,'gates':[]})
    write('scene.json',{'version':1,'canvas':{'width':32,'height':32,'fps':30,'loop_seconds':1,'background':'#000000'},'camera':{'overscan':1,'x_amplitude':0,'y_amplitude':0,'zoom_amplitude':0},'groups':[],'layers':[]})
    write('catalog.json',{'version':1,'assets':[]})
    source=project/'source.input';origin=None
    if args.source:
        before=digest(args.source);shutil.copyfile(args.source,source)
        if digest(source)!=before or digest(args.source)!=before:raise ValueError('Source changed while copied')
        origin={'path':str(args.source.resolve()),'sha256':before,'bytes':args.source.stat().st_size}
    else:
        with wave.open(str(source),'wb') as w:
            w.setnchannels(2);w.setsampwidth(2);w.setframerate(48000)
            w.writeframes(b''.join(struct.pack('<hh',round(4000*math.sin(i*2*math.pi*440/48000)),round(3000*math.sin(i*2*math.pi*660/48000))) for i in range(4800)))
    provenance=json.loads(args.provenance.read_text()) if args.provenance else {'origin_kind':'imported' if origin else 'synthesized','prior_processing':'fixture copy of exact source bytes' if origin else 'local deterministic 100ms tone fixture','audition':'not performed'}
    write('provenance.json',provenance)
    steps=[]
    def cli(*argv,expected=0):
        command=[str(ROOT/'ambiance'),'--project',str(project),*argv]
        result=subprocess.run(command,capture_output=True,text=True)
        data=json.loads(result.stdout)
        steps.append({'argv':command,'exit_code':result.returncode,'result':data})
        write('replay.json',{'ok':False,'origin':origin,'steps':steps})
        if result.returncode!=expected:raise ValueError(f'CLI returned {result.returncode}, expected {expected}: {result.stdout}')
        return data.get('data',{})
    inspection=cli('audio','source-inspect','source.input','--backend',args.backend)
    prepared=cli('audio','source-prepare','source.input','--backend',args.backend,'--source-sha256',inspection['source']['sha256'],'--preparation-id','working-v1','--provenance','provenance.json')
    receipt='audio/preparations/working-v1/receipt.json'
    cli('audio','source-check',receipt)
    write('selection.json',{'format':'ambiance-revision-selection','schema_version':1,'scene':'scene.json','catalog':'catalog.json','audio':{'preparations':[receipt]}})
    cli('revision','capture','source-v1','--selection',str(project/'selection.json'))
    cli('revision','check','source-v1')
    cli('audio','source-prepare','source.input','--backend',args.backend,'--source-sha256',inspection['source']['sha256'],'--preparation-id','working-v1',expected=2)
    # A distinct damaged candidate proves rejection without changing captured dependencies.
    (project/'truncated.input').write_bytes(source.read_bytes()[:-7])
    cli('audio','source-inspect','truncated.input','--backend',args.backend,expected=2)
    artifacts={str(x.relative_to(project)):{'sha256':digest(x),'bytes':x.stat().st_size} for x in sorted(project.rglob('*')) if x.is_file() and x.name not in ['replay.json'] and '.ambiance' not in x.parts}
    write('replay.json',{'ok':True,'origin':origin,'steps':steps,'artifacts':artifacts,'limits':['Synthetic/technical replay only; no listening or film approval.','Library relocation/version adoption is deferred.']})
    print(json.dumps({'ok':True,'project':str(project),'report':str(project/'replay.json'),'report_sha256':digest(project/'replay.json'),'working':prepared['working']}))

if __name__=='__main__':main()
