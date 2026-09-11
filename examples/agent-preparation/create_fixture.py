#!/usr/bin/env python3
"""Create a cleared source-backed compound fixture and replay public preparation CLI.

All art is drawn locally by this file. It is engineering evidence, not a film pilot.
"""
import argparse
import copy
import json
import math
from pathlib import Path
import subprocess
import sys

from PIL import Image, ImageDraw
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from ambiance_studio import preparation as single, asset_prep as p, preparation_commands as commands


def run(project,*args):return commands.cli(project,*args)
def polygon(points):return {'operation':'add','points':points}
def rect(x0,y0,x1,y1):return polygon([[x0,y0],[x1,y0],[x1,y1],[x0,y1]])


def create(out,subject='tea',proof=True):
    out=Path(out).resolve()
    if subject=='cabinet':
        subprocess.run([sys.executable,str(ROOT/'examples/preparation-workbench/create_fixture.py'),str(out)],capture_output=True,text=True,check=True)
        old=p.load(out/'plans/preparation.json');w,h=old['source']['width'],old['source']['height']
        part_names=['ornament','rail'];raw=out/'assets/raw';source=Image.open(raw/'source.png').convert('RGBA')
        mask=Image.new('L',(w,h));ImageDraw.Draw(mask).polygon([tuple(v) for v in old['masks']['cutout']['polygons'][0]['points']],fill=104);mask.save(raw/'companion.png')
        parts=[{'id':'ornament','kind':'cutout','mask':old['masks']['cutout'],'pivot':[186.25,401.125],
                'motion':{'delta':[0,-32],'rotation_degrees':3},'companions':[{'id':'ornament-light','image':single.image_record(out,raw/'companion.png')}]},
               {'id':'rail','kind':'occluder','mask':old['masks']['occluder'],'pivot':[0,0]}]
    else:
        process=subprocess.run([sys.executable,str(ROOT/'ambiance'),'project','init',str(out),'--title','Tea shelf · compound preparation fixture'],capture_output=True,text=True)
        if process.returncode:raise ValueError(process.stdout+process.stderr)
        raw=out/'assets/raw';raw.mkdir(exist_ok=True);w=h=256
        backing=Image.new('RGB',(w,h),'#233948');d=ImageDraw.Draw(backing)
        d.rectangle((16,16,240,226),fill='#365465');d.rectangle((31,23,225,178),fill='#294450')
        for y in range(25,178,7): d.line((33,y,223,y),fill='#2e4956')
        d.rectangle((12,202,244,216),fill='#9b7255');d.line((12,202,244,202),fill='#d4ae83',width=2)
        backing.save(raw/'backing.png');source=backing.copy();d=ImageDraw.Draw(source)
        # Teapot body and lid are separate cutouts; the fixed rail covers the foot.
        body=[[62,128],[72,119],[97,117],[115,121],[126,134],[137,120],[158,114],[151,128],[128,151],[122,174],[109,188],[77,188],[62,177],[55,152],[36,147],[31,135],[43,125],[57,128]]
        lid=[[64,115],[71,108],[86,105],[86,98],[98,98],[100,105],[115,111],[120,118],[64,118]]
        d.polygon([tuple(v) for v in body],fill='#ba8c61');d.line([(64,135),(67,164),(78,177),(110,178)],fill='#d8b289',width=3)
        d.polygon([tuple(v) for v in lid],fill='#d4ab73');d.line([(74,111),(107,112)],fill='#f4d5a0',width=2)
        d.rectangle((24,180,233,187),fill='#73949a');d.line((24,180,233,180),fill='#bad0c9',width=2)
        source.save(raw/'source.png')
        old=single.initial_recipe(out,raw/'source.png',raw/'backing.png');old['title']='Tea shelf'
        old['masks']['removal']['polygons']=[rect(28,94,160,190)]
        old['masks']['cutout']['polygons']=[polygon(body),rect(24,180,233,187)] # intentionally includes rail until CLI edit
        old['masks']['occluder']['polygons']=[rect(24,180,233,187)]
        # Hidden paint is explicitly reconstructed in a local fixture source, not recovered by shrinking travel.
        reconstructed=source.copy();dr=ImageDraw.Draw(reconstructed);dr.polygon([tuple(v) for v in body],fill='#ba8c61');dr.line([(64,135),(67,164),(78,177),(110,178)],fill='#d8b289',width=3);reconstructed.save(raw/'body-reconstructed.png')
        soft=Image.new('L',(w,h));ds=ImageDraw.Draw(soft);ds.polygon([tuple(v) for v in body],fill=255);soft.putpixel((62,128),7);soft.save(raw/'body-mask.png')
        companion=Image.new('L',(w,h));ImageDraw.Draw(companion).ellipse((65,130,100,172),fill=75);companion.save(raw/'companion.png')
        parts=[{'id':'pot','kind':'cutout','source':single.image_record(out,raw/'body-reconstructed.png'),
                'mask':{'image':single.image_record(out,raw/'body-mask.png'),'polygons':[]},'pivot':[92.25,184.125],
                'motion':{'delta':[5,-7],'rotation_degrees':2},'companions':[{'id':'pot-light','image':single.image_record(out,raw/'companion.png')}]},
               {'id':'lid','kind':'cutout','mask':{'polygons':[polygon(lid)]},'pivot':[93.5,116.25],'motion':{'delta':[1,-14],'rotation_degrees':-3}},
               {'id':'rail','kind':'occluder','mask':{'polygons':[rect(24,180,233,187)]},'pivot':[0,0]}]
        part_names=[part['id'] for part in parts]
    # Saved views have different crops; fractional source placement exercises subpixel maps.
    canvas={'width':w,'height':h,'fps':30,'loop_seconds':2,'background':'#18232c'}
    ratio=9/16;pw=min(w,h*ratio);ph=pw/ratio;lw=min(w,h/ratio);lh=lw*ratio
    framing={'version':1,'views':{'portrait':{'rect_scene_px':[(w-pw)/2,(h-ph)/2,pw,ph],'output':{'width':144,'height':256}},
                                  'landscape':{'rect_scene_px':[(w-lw)/2,(h-lh)/2,lw,lh],'output':{'width':256,'height':144}}}}
    # Build/admit the reference using its ordinary full-source mapping.
    reference=single.image_record(out,raw/'source.png')
    mapping={'format':'ambiance-asset-source-mapping','version':1,'path_base':'project','reference':reference,'image':reference,'image_to_reference':[1,0,0,1,0,0],'registration':'Known fixture reference'}
    p.write(raw/'base-mapping.json',mapping)
    p.write(raw/'base-recipe.json',{'version':1,'id':'fixture-reference','input':{'frames':['source.png'],'allow_opaque':True},
            'source_mapping':{'file':'base-mapping.json','sha256':p.sha((raw/'base-mapping.json').read_bytes())},
            'registration':{'mode':'fixed','point':[w/2,h/2],'target':[.5,.5]},'output':{'cell_size':[w+4,h+4],'columns':1,'padding':2}})
    run(out,'asset','build',raw/'base-recipe.json','--out',out/'assets/production/reference');run(out,'asset','admit',out/'assets/production/reference')
    scene={'version':1,'id':'compound-fixture','title':old['title'],'canvas':canvas,
           'camera':{'overscan':1,'x_amplitude':0,'y_amplitude':0,'zoom_amplitude':0},'groups':[],'framing':framing,
           'layers':[{'id':'base','asset':'fixture-reference','cycle_seconds':2,'phase_frames':0,'x':.5+.25/w,'y':.5+.125/h,'width':(w+4)/w,'height':(h+4)/h,
                      'anchor':[.5,.5],'scale':1,'rotation':0,'opacity':1,'visible':True,'depth':0,'blend':'source-over'}]}
    p.write(out/'scene/scene.json',scene)
    inventory={'version':1,'items':[{'id':name,'required_parts':[{'id':'paint','role':'occluder' if name=='rail' else 'cutout'}]} for name in part_names]}
    p.write(out/'plans/asset-inventory.json',inventory)
    plan={'format':'ambiance-production-plan','schema_version':1,'story':{'premise':'Prepare independent painted parts on a shelf.','direction':'Local engineering fixture in both saved views.'},
          'sources':[],'elements':[],'actions':[],'outputs':[{'view_id':id,'roles':['silent']} for id in framing['views']], 'relations':[],'expectations':[],
          'change':{'reason':'New cleared source-backed fixture','supersedes_sha256':None}}
    for part in parts:
        binding={'element_id':part['id'],'inventory_part':{'item_id':part['id'],'part_id':'paint'}};part['binding']=binding
        plan['elements'].append({'id':part['id'],'kind':'prop','depth_band':'midground','motion_role':'stable','cadence':'still','readability_target':0,
            'origin':'proposed','purpose':'Prepare independently controllable source paint.','source_ids':[],'action_ids':[],
            'realization':{'method':'cutout','inventory_parts':[binding['inventory_part']],'layer_ids':[]},
            'required_art':[{'id':part['id']+'-paint','role':part['kind'],'purpose':'Retain independent paint and explicit hidden backing.','inventory_part':binding['inventory_part']}]})
    run(out,'plan','spec','apply',write(out/'plans/proposed-plan.json',plan),'--expect-sha256','absent')
    context={'scene':{'file':'scene/scene.json','sha256':p.sha((out/'scene/scene.json').read_bytes())},
             'production_plan':{'file':'plans/production-plan.json','sha256':p.sha((out/'plans/production-plan.json').read_bytes())},
             'inventory':{'file':'plans/asset-inventory.json','sha256':p.sha((out/'plans/asset-inventory.json').read_bytes())},
             'views':['portrait','landscape'],'source_to_scene':[1,0,0,1,.25,.125]}
    write(out/'plans/legacy-preparation.json',old)
    draft=run(out,'asset','prepare','init',out/'plans/legacy-preparation.json','--out',out/'assets/prepared/draft')
    batch={'version':1,'operations':[{'op':'remove-part','part':'subject'},{'op':'remove-part','part':'foreground'},
           *[{'op':'add-part','value':part} for part in parts],{'op':'set-seconds','value':2},{'op':'set-context','value':context}]}
    write(out/'plans/preparation-batch.json',batch)
    edited=run(out,'asset','prepare','edit',draft['recipe'],'--batch',out/'plans/preparation-batch.json','--expect-sha256',draft['sha256'],'--out',out/'assets/prepared/authoring')
    checked=run(out,'asset','prepare','inspect',edited['recipe'])
    built=run(out,'asset','prepare','build',edited['recipe'],'--out',out/'assets/prepared/compound')
    # Scene is changed only by the public transaction, after immutable pack preparation.
    placement=run(out,'asset','prepare','place',built['directory'],'--base','base','--prefix','prepared','--expect-sha256',context['scene']['sha256'])
    result={'project':str(out),'recipe':edited['recipe'],'prepared':built,'placement':placement['sha256'],'scope':'Cleared engineering fixture; no artistic pilot or human review.'}
    if proof:result['proof']=run(out,'asset','prepare','proof',built['directory'],'--out',out/'reports/preparation-proof','--long-edge',256)
    p.write(out/'reports/replay.json',result);return result


def write(path,data):p.write(path,data);return path

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory',type=Path);parser.add_argument('--subject',choices=['tea','cabinet'],default='tea');parser.add_argument('--no-proof',action='store_true');args=parser.parse_args()
    print(json.dumps(create(args.directory,args.subject,not args.no_proof),indent=2))
