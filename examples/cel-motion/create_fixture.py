#!/usr/bin/env python3
"""Known jitter and intentional articulation, with unequal holds and a child socket."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import studio
from PIL import Image,ImageDraw


def create(out):
    out=Path(out).resolve()
    if out.exists():raise ValueError('Choose a fresh fixture directory')
    studio.new_project(out,None,'Cel motion workbench • independent fixture')
    studio.write(out/'ambiance-project.json',{'version':1,'scene':'scene/scene.json','catalog':'assets/catalog.json'})
    source=out/'assets/source';source.mkdir(parents=True);studio.write(out/'assets/catalog.json',{'version':1,'assets':[]})
    offsets=[(0,0),(3,-2),(-2,1)]
    for i,(dx,dy) in enumerate(offsets):
        im=Image.new('RGBA',(64,64));d=ImageDraw.Draw(im)
        d.rectangle((19+dx,18+dy,37+dx,45+dy),fill='#a06939');d.rectangle((21+dx,37+dy,25+dx,41+dy),fill='#fff4ae');d.point((23+dx,39+dy),fill='#111111')
        d.rectangle((20+dx+i,10+dy,32+dx+i,17+dy),fill='#f1ac42');im.save(source/f'figure-{i}.png')
    recipe={'version':1,'id':'figure-v1','input':{'frames':[f'source/figure-{i}.png' for i in range(3)]},
        'registration':{'mode':'fixed','point':[32,32],'target':[.5,.5]},'output':{'cell_size':[64,64],'columns':3,'padding':2},'sockets':{'foot':[23/64,39/64],'mount':[.5,.5]}}
    studio.write(out/'assets/recipe.json',recipe)
    commands=[]
    def cli(*args):
        argv=[str(ROOT/'ambiance'),'--project',str(out),*map(str,args)];result=subprocess.run(argv,text=True,capture_output=True);commands.append({'argv':argv,'exit_code':result.returncode})
        if result.returncode:raise ValueError(result.stdout+result.stderr)
        return json.loads(result.stdout)
    pack=out/'assets/compiled/baseline';cli('asset','build',out/'assets/recipe.json','--out',pack);cli('asset','admit',pack)
    layer={'id':'figure','asset':'figure-v1','x':.5,'y':.52,'width':.5,'height':.5,'anchor':[.5,.5],'scale':1,'rotation':0,'opacity':1,'visible':True,'blend':'source-over','depth':.2,'cycle_seconds':2,'phase_frames':0,
       'tracks':{'cell':{'interpolation':'hold','keys':[[0,0],[.5,1],[1.5,2],[2,0]]}},'sockets':{'foot':[23/64,39/64]}}
    child={**layer,'id':'marker','x':0,'y':0,'width':.06,'height':.06,'depth':.2,'attach':{'layer':'figure','socket':'foot'},'tracks':{},'sockets':{}}
    child.pop('depth');child.pop('tracks')
    scene={'version':1,'id':'motion-fixture','title':'Known drift • independently moving head','canvas':{'width':256,'height':256,'fps':12,'loop_seconds':2,'background':'#122536'},
        'camera':{'overscan':1,'x_amplitude':.01,'y_amplitude':0,'zoom_amplitude':.02},'groups':[],'layers':[layer,child]}
    studio.write(out/'scene/scene.json',scene)
    operations=[]
    for name,role,xy in [('foot','fit',(23,39)),('shoulder','check',(30,22))]:
        operations.append({'op':'landmark','name':name,'value':{'role':role,'mode':'fixed','reference_cel':0,'cels':[0,1,2],'tolerance_px':.1,'weight':1,
            'observations':[{'point':[xy[0]+dx,xy[1]+dy],'visible':True,'origin':'manual','state':'selected'} for dx,dy in offsets]}})
    operations += [{'op':'region','name':'body','value':{'mode':'stable','points':[[17,18],[41,18],[41,46],[17,46]],'cels':[0,1,2],'reference_cel':0,'alpha_threshold':10,'color_threshold':10}},
        {'op':'solve','values':{'socket_policies':{'foot':'follow_art','mount':'fixed_mount'},'layer_socket_policies':{'foot':'follow_art'}}}]
    studio.write(out/'observations.json',{'version':1,'operations':operations});studio.write(out/'fixture-truth.json',{'source_offsets':offsets,'expected_corrections':[[0,0],[-3,2],[2,-1]],'intentional_head_x':[0,1,2],
       'scope':'Synthetic independent fixture, not a production movie or painted-art quality judgment','creation_commands':commands})
    return {'project':str(out),'observations':str(out/'observations.json'),'layer':'figure'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);print(json.dumps(create(p.parse_args().out),indent=2))
