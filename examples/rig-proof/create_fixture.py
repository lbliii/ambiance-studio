#!/usr/bin/env python3
"""Create a fresh, independent inspection fixture. Placeholder shapes are not production art."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('directory',type=Path);args=p.parse_args()
project=args.directory.resolve()
subprocess.run([sys.executable,str(ROOT/'ambiance'),'project','init',str(project),'--title','Synthetic backing-defect inspection'],check=True,capture_output=True)
assets=[]
for name,kind,color in [('room','plate',(25,36,49,255)),('casket','plate',(70,100,130,255)),('body','plate',(185,151,90,255)),('hand','plate',(250,216,140,255)),('rim','plate',(29,55,84,255)),('glass','plate',(190,220,235,255))]:
    size=(180,320) if name=='room' else (100,40)
    image=Image.new('RGBA',size,color);draw=ImageDraw.Draw(image)
    if name=='casket':
        # Deliberate contamination: a red body-shaped imprint in the rear bed.
        draw.ellipse((25,5,75,35),fill=(188,48,70,255))
    file=project/'assets'/f'{name}.png';image.save(file)
    assets.append({'id':name,'kind':kind,'file':f'assets/{name}.png','width':image.width,'height':image.height,'bytes':file.stat().st_size,'sha256':hashlib.sha256(file.read_bytes()).hexdigest()})
(project/'assets/catalog.json').write_text(json.dumps({'version':1,'assets':assets},indent=2)+'\n')
scene=json.loads((project/'scene/scene.json').read_text());scene['canvas'].update(width=180,height=320,fps=10,loop_seconds=4);scene['camera']['overscan']=1
scene['layers']=[{'id':'room','name':'Room with deliberate backing defect','asset':'room','x':0,'y':0,'width':1,'height':1,'anchor':[0,0],'scale':1,'rotation':0,'opacity':1,'visible':True,'blend':'source-over','depth':0}]
(project/'scene/scene.json').write_text(json.dumps(scene,indent=2)+'\n')
ops=[
 {'op':'add','asset':'casket','id':'casket','values':{'x':.5,'y':.6,'width':.65,'sockets':{'bed':[.5,.5]},'tracks':{'y':{'interpolation':'smoothstep','keys':[[0,.6],[1,.6],[2,.49],[3,.6],[4,.6]]}}}},
 {'op':'add','asset':'body','id':'mummy-body','values':{'width':.5,'sockets':{'wrist':[.7,.3]},'tracks':{'visible':{'interpolation':'hold','keys':[[0,True],[4,True]]}}}},
 {'op':'attach','layer':'mummy-body','to':'casket','socket':'bed'},
 {'op':'add','asset':'hand','id':'mummy-hand','values':{'width':.1}},
 {'op':'attach','layer':'mummy-hand','to':'mummy-body','socket':'wrist'},
 {'op':'add','asset':'rim','id':'front-rim','values':{'width':.65,'height':.025}},
 {'op':'attach','layer':'front-rim','to':'casket','socket':'bed','offset_x':0,'offset_y':.04},
 {'op':'add','asset':'glass','id':'stationary-glass','values':{'x':.5,'y':.6,'width':.72,'height':.19,'opacity':.15}},
 {'op':'order','layers':['room','casket','mummy-body','mummy-hand','front-rim','stationary-glass']}
]
transaction=project/'compound-transaction.json';transaction.write_text(json.dumps({'version':1,'operations':ops},indent=2)+'\n')
subprocess.run([sys.executable,str(ROOT/'ambiance'),'--project',str(project),'scene','apply',str(transaction)],check=True,capture_output=True)
(project/'plans/asset-inventory.json').write_text(json.dumps({'version':1,'items':[{'id':id} for id in ['casket-rig','mummy-body','mummy-gesture','display-glass']]},indent=2)+'\n')
print(json.dumps({'ok':True,'project':str(project),'note':'Synthetic fixture: deliberately contaminated backing, compound lift, attached gesture, fixed glass.'},indent=2))
