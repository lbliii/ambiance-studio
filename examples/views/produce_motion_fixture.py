#!/usr/bin/env python3
"""CLI-operated dual production demo using locally drawn art and a labeled test tone."""
import argparse
import array
import json
import math
from pathlib import Path
import subprocess
import sys
import wave

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import studio

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('project',type=Path)
parser.add_argument('--long-edge',type=int,default=320)
args=parser.parse_args();project=args.project.resolve()
subprocess.run(['node',str(ROOT/'examples/views/create_motion_fixture.mjs'),str(project)],check=True,capture_output=True,text=True)
def command(*args):
    result=subprocess.run([str(ROOT/'ambiance'),'--project',str(project),*map(str,args)],capture_output=True,text=True)
    data=json.loads(result.stdout)
    if result.returncode:raise RuntimeError(json.dumps(data))
    return data['data']

samples=array.array('h',(round(1200*math.sin(2*math.pi*220*frame/48000)) for frame in range(192000) for _ in range(2)))
if sys.byteorder!='little':samples.byteswap()
for name in ['source','master']:
    with wave.open(str(project/f'audio/{name}.wav'),'wb') as file:
        file.setnchannels(2);file.setsampwidth(2);file.setframerate(48000);file.writeframes(samples.tobytes())
(project/'audio/identity.txt').write_text('Engineering fixture: stereo 220 Hz test tone, 48000 Hz, 16-bit PCM, four seconds. Source copied unchanged to master. Not a creative soundtrack.\n')
def ref(name):return {'path':'audio/'+name,'sha256':studio.digest(project/'audio'/name)}
studio.write(project/'audio/preparation.json',{'format':'ambiance-external-preparation','schema_version':1,
    'sources':[ref('source.wav')],'recipes':[ref('identity.txt')],'outputs':[ref('master.wav')]})
(project/'plans/brief.md').write_text('# Dual-format engineering pilot\n\nOne 160 × 160 scene, two saved crops, one clock and shared PCM.\nPortrait 1080 × 1920 and landscape 1920 × 1080 preferred sizes; selected review ceiling '+str(args.long_edge)+'.\nA locally drawn moving circle, attached changing hand, camera, fixed rim and receiving effects test geometric preservation. The score role contains a labeled 220 Hz test tone for codec testing, not a composed soundtrack. No human listening or phone check is claimed.\n')
settings=studio.read(project/'project.json');settings['output'].update(fps=8,picture_seconds=2,master_seconds=4);studio.write(project/'project.json',settings)
studio.write(project/'plans/revision-selection.json',{'format':'ambiance-revision-selection','schema_version':1,
    'scene':'scene/scene.json','catalog':'assets/catalog.json','audio':{'preparations':['audio/preparation.json'],'masters':['audio/master.wav']}})
recipe={'format':'ambiance-iteration','schema_version':2,'id':'dual-demo','revision':'dual-r1','capture_selection':'plans/revision-selection.json',
    'views':['portrait','landscape'],'long_edge':args.long_edge,'default':{'view':'portrait','role':'silent'},
    'title':'One scene · two formats','notes':'Engineering review. Local geometric artwork; the score option is a quiet test tone. Human creative and phone checks are open.',
    'editions':[{'role':'silent'},{'role':'score','audio':'audio/master.wav','repeats':2}]}
studio.write(project/'plans/iteration.json',recipe)
result=command('iteration','run',project/'plans/iteration.json','--by','Codex engineering pilot')
print(json.dumps({'project':str(project),'delivery':result['delivery'],'run':str(project/'runs/dual-demo/run.json'),
                  'elapsed_seconds':result['run']['elapsed_seconds'],'entries':list(command('delivery','inspect','dual-demo')['entries'])},indent=2))
