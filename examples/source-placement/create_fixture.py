#!/usr/bin/env python3
"""Create an isolated geometric placement/parenting fixture, never a production film."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from PIL import Image,ImageDraw
from tools import asset_tool
from ambiance_studio import scene_authoring
import studio


def create(out):
    out=Path(out).resolve()
    if out.exists():raise ValueError('Fixture output exists; choose a fresh directory')
    studio.new_project(out,None,'Source placement and parenting fixture')
    studio.write(out/'ambiance-project.json',{'version':1,'scene':'scene/scene.json','catalog':'assets/catalog.json'})
    source=out/'assets/source';source.mkdir(parents=True)
    clean=Image.new('RGB',(240,320),'#142636');d=ImageDraw.Draw(clean)
    for x in range(0,240,20):d.line((x,0,x,320),fill='#203d52')
    for y in range(0,320,20):d.line((0,y,240,y),fill='#203d52')
    clean.save(source/'clean.png');reference=clean.copy();d=ImageDraw.Draw(reference)
    d.rounded_rectangle((70,120,149,239),radius=10,fill='#ba7b3c',outline='#e7ba6d',width=3)
    d.rectangle((80,132,139,148),fill='#403331');reference.save(source/'reference.png')
    ref={'file':'assets/source/reference.png','sha256':studio.digest(source/'reference.png'),'width':240,'height':320}
    body=reference.crop((70,120,150,240)).convert('RGBA');mask=Image.new('L',(80,120));ImageDraw.Draw(mask).rounded_rectangle((0,0,79,119),radius=10,fill=255);body.putalpha(mask);body.save(source/'body.png')
    def mapped(name,offset):
        file=source/f'{name}.png'
        with Image.open(file) as image: width,height=image.size
        mapping={'format':'ambiance-asset-source-mapping','version':1,'path_base':'project','reference':ref,
                 'image':{'file':str(file.relative_to(out)),'sha256':studio.digest(file),'width':width,'height':height},
                 'image_to_reference':[1,0,0,1,*offset],'registration':'Known geometric fixture coordinates; explicitly authored'}
        path=source/f'{name}-mapping.json';studio.write(path,mapping);return path
    catalog={'version':1,'assets':[]};studio.write(out/'assets/catalog.json',catalog)
    def build(name,frames,cell,pivot=[.5,.5],mapping=None,opaque=False):
        with Image.open(frames[0]) as image: width,height=image.size
        recipe={'version':1,'id':name,'input':{'frames':[str(p.relative_to(out/'assets')) for p in frames],'allow_opaque':opaque},
                'registration':{'mode':'fixed','point':[width*pivot[0],height*pivot[1]],'target':pivot},
                'output':{'cell_size':cell,'columns':min(4,len(frames)),'padding':2}}
        if mapping:recipe['source_mapping']={'file':str(mapping.relative_to(out/'assets')),'sha256':studio.digest(mapping)}
        recipe_file=out/'assets'/f'{name}-recipe.json';studio.write(recipe_file,recipe)
        pack=out/'assets/production'/name;asset_tool.build(recipe_file,pack);asset_tool.admit(pack,out/'assets/catalog.json')
    build('reference-plate',[source/'clean.png'],[244,324],mapping=mapped('clean',[0,0]),opaque=True)
    build('body-cutout',[source/'body.png'],[84,124],mapping=mapped('body',[70,120]))
    frames=[]
    for i in range(4):
        image=Image.new('RGBA',(32,32));draw=ImageDraw.Draw(image);draw.line((10,24,13+i*3,10-i),fill='#ffeeaa',width=5);draw.ellipse((7,20,14,27),fill='#ffeeaa');f=source/f'gesture-{i}.png';image.save(f);frames.append(f)
    build('gesture-cels',frames,[36,36])
    for name,color,width in [('rim','#edc47c',3),('glass','#7bd7e9',1)]:
        im=Image.new('RGBA',(96,144));ImageDraw.Draw(im).rectangle((3,3,92,140),outline=color,width=width);im.save(source/f'{name}.png');build(name,[source/f'{name}.png'],[100,148])
    s={'version':1,'id':'placement-fixture','title':'Placement and parenting • geometric fixture',
       'canvas':{'width':360,'height':640,'fps':30,'loop_seconds':4,'background':'#142636'},
       'camera':{'overscan':1,'x_amplitude':0,'y_amplitude':0,'zoom_amplitude':0},'groups':[],
       'layers':[{'id':'base','name':'Fixed reference plane','asset':'reference-plate','x':.5,'y':.5,'width':244/240,'height':324/320,'anchor':[.5,.5],'scale':1.02,'rotation':0,'opacity':1,'visible':True,'blend':'source-over','depth':0,'cycle_seconds':4,'phase_frames':0}],
       'coverage_layers':['base']}
    manifest={'kind':'ambiance-source-placement','version':1,'placements':[
        {'id':'body','asset':'body-cutout','base':'base','mode':'native','reference':ref},
        {'id':'gesture','asset':'gesture-cels','base':'base','mode':'sprite','reference':ref,'source_anchor':[117,158],'source_size':[25,25],'values':{'cycle_seconds':1,'phase_frames':0}},
        {'id':'rim','asset':'rim','base':'base','mode':'sprite','reference':ref,'source_anchor':[110,180],'source_size':[92,140]},
        {'id':'fixed-glass','asset':'glass','base':'base','mode':'sprite','reference':ref,'source_anchor':[110,180],'source_size':[102,150]}]}
    studio.write(out/'placement.json',manifest);catalog=studio.read(out/'assets/catalog.json')
    def apply(scene,batch):
        resolved,deps=scene_authoring.resolve_batch(out,scene,catalog,batch)
        result=subprocess.run(['node',str(ROOT/'tools/scene-command.mjs')],input=json.dumps({'action':'apply','scene':scene,'catalog':catalog,'args':{'batch':resolved,'report':True}}),text=True,capture_output=True)
        payload=json.loads(result.stdout)
        if result.returncode or not payload['ok']:raise ValueError(payload.get('error',result.stderr))
        scene_authoring.verify_dependencies(out,deps);return payload['data']
    placed=apply(s,scene_authoring.placement_batch(manifest));studio.write(out/'scene/before-reparent.json',placed['scene'])
    batch={'version':1,'operations':[{'op':'socket','layer':'body','name':'hand','value':[.6,.3]},
        {'op':'socket','layer':'body','name':'rim','value':[.5,.5]},
        {'op':'reparent','layer':'gesture','to':'body','socket':'hand','preserve':'world_at_time','at_seconds':0},
        {'op':'reparent','layer':'rim','to':'body','socket':'rim','preserve':'world_at_time','at_seconds':0},
        {'op':'set','layer':'body','values':{'tracks':{'y':{'interpolation':'smoothstep','keys':[[0,0],[1,0],[2,-.035],[3,0],[4,0]]}}}}]}
    after=apply(placed['scene'],batch);studio.write(out/'reparent-batch.json',batch);studio.write(out/'scene/scene.json',after['scene'])
    studio.write(out/'transaction-report.json',{'placement':placed['operations'],'reparent':after['operations']})
    return {'project':str(out),'scene':str(out/'scene/scene.json'),'placement':str(out/'placement.json'),'scope':'Geometric fixture from the actual source-placement and reparent transaction output; no production art used.'}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
    print(json.dumps(create(parser.parse_args().out),indent=2))
