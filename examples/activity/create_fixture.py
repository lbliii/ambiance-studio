#!/usr/bin/env python3
"""Independent synthetic brush-mark study for activity diagnostics, never a film."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import shutil

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]


def create(out, case='visible', fps=12):
    out = Path(out).resolve()
    if out.exists(): raise ValueError('Use a fresh fixture directory')
    result = subprocess.run([str(ROOT/'ambiance'), 'project', 'init', str(out), '--title', 'Synthetic motion evidence'], capture_output=True, text=True)
    if result.returncode: raise ValueError(result.stdout)
    art = out/'assets/source'; art.mkdir(exist_ok=True)
    # Deliberately irregular painted support, with transparent atlas padding.
    atlas = Image.new('RGBA', (48, 24)); draw = ImageDraw.Draw(atlas)
    color = '#91857b' if case == 'low-contrast' else '#e8cf98'
    for cel in range(2):
        x = cel*24
        draw.ellipse((x+5,8,x+19,18), fill=color)
        draw.polygon([(x+14,10),(x+16,3+cel*3),(x+20,9)], fill=color)
        draw.line((x+8,15,x+3,18,x+1,14), fill=color, width=2)
        draw.ellipse((x+17,10,x+18,11), fill='#554e48' if case == 'low-contrast' else '#302b26')
    if case == 'duplicate': atlas.paste(atlas.crop((0,0,24,24)), (24,0))
    if case == 'low-contrast':
        # Broad but barely different from the base; tests should not confuse area with contrast.
        pixels=list(atlas.get_flattened_data() if hasattr(atlas, "get_flattened_data") else atlas.getdata());atlas.putdata([(145,133,124,a) if a else (0,0,0,0) for _,_,_,a in pixels])
    atlas.save(art/'actor.png')
    cover=Image.new('RGBA',(8,8),'#91857b');cover.save(art/'cover.png')
    layer={'id':'actor','asset':'actor','x':.5,'y':.5,'width':.28,'height':.28,'anchor':[.5,.5],
           'scale':1,'rotation':0,'opacity':1,'visible':True,'blend':'source-over','depth':0,
           'cycle_seconds':2,'phase_frames':0,'motion':{'x_amplitude':.07,'y_amplitude':0,'cycles':1,'phase':0}}
    if case in ['duplicate','pulse']: layer.pop('motion');layer['cycle_seconds']=4
    if case == 'pulse': layer['tracks']={'cell':{'interpolation':'hold','keys':[[0,0],[4,0]]}}
    if case == 'offscreen': layer['x']=1.4
    if case == 'tiny': layer['width']=layer['height']=.012
    if case == 'hidden': layer['visible']=False
    if case == 'excessive': layer['motion']['x_amplitude']=.4;layer['motion']['cycles']=4;layer['width']=layer['height']=.7
    layers=[layer]
    if case == 'occluded': layers.append({**layer,'id':'cover','asset':'cover','x':.5,'y':.5,'width':1,'height':1,'motion':None})
    if case == 'pulse':
        layers.append({**layer,'id':'exposure-pulse','asset':'cover','width':1,'height':1,'tracks':{'opacity':{'interpolation':'linear','keys':[[0,0],[2,.5],[4,0]]}}})
    scene={'version':1,'id':'activity-study','title':'Synthetic motion evidence: '+case,
           'canvas':{'width':128,'height':128,'fps':fps,'loop_seconds':4,'background':'#91857b'},
           'camera':{'overscan':1,'x_amplitude':0,'y_amplitude':0,'zoom_amplitude':0},'groups':[],'layers':layers,
           'framing':{'version':1,'views':{'portrait':{'rect_scene_px':[28,0,72,128],'output':{'width':72,'height':128}},
                                         'landscape':{'rect_scene_px':[0,28,128,72],'output':{'width':128,'height':72}}}}}
    assets=[]
    for id,size in [('actor',(48,24)),('cover',(8,8))]:
        asset={'id':id,'file':f'assets/source/{id}.png','width':size[0],'height':size[1],
               'sha256':hashlib.sha256((art/f'{id}.png').read_bytes()).hexdigest()}
        if id=='actor': asset['atlas']={'columns':2,'rows':1,'cell_width':24,'cell_height':24,'frame_count':2}
        assets.append(asset)
    if case.startswith('painted-'):
        original=next(a for a in json.loads((ROOT/'assets/catalog.json').read_text())['assets'] if a['id']=='cloud-cels')
        destination=art/'cloud-cels.png';shutil.copyfile(ROOT/original['file'],destination)
        assets[0]={k:v for k,v in original.items() if k in ['width','height','atlas','sha256']}
        assets[0].update(id='actor',file='assets/source/cloud-cels.png')
        layer['cycle_seconds']=4
        layer['width']=.65;layer['height']=.32
        if case=='painted-barely': layer['opacity']=.02
        if case=='painted-invisible': layer['x']=1.7
        if case=='painted-excessive': layer['motion']['x_amplitude']=.45;layer['motion']['cycles']=4
        (out/'source-ledger.json').write_text(json.dumps({'scope':'Read-only copy of repository-cleared painted cloud cels; no accepted asset modified',
            'source_catalog':'assets/catalog.json','asset_id':'cloud-cels','sha256':original['sha256']}))
    (out/'scene/scene.json').write_text(json.dumps(scene))
    (out/'assets/catalog.json').write_text(json.dumps({'version':1,'assets':assets}))
    if case=='visible':
        def batch(amplitude,cycles=1):return {'version':1,'operations':[{'op':'set','layer':'actor','values':{'motion':{'x_amplitude':amplitude,'y_amplitude':0,'cycles':cycles,'phase':0}}}]}
        (out/'comparison.json').write_text(json.dumps({'version':1,'strength':[{'id':'quieter','batch':batch(.015)},{'id':'stronger','batch':batch(.15)}],
                                                     'cadence':[{'id':'twice-often','batch':batch(.07,2)},{'id':'four-times-often','batch':batch(.07,4)}]}))
    return out


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--case',choices=['visible','duplicate','offscreen','tiny','hidden','occluded','low-contrast','pulse','excessive','painted-visible','painted-barely','painted-invisible','painted-excessive'],default='visible')
    args=parser.parse_args();print(json.dumps({'project':str(create(args.out,args.case)),'scope':'Independent engineering fixture, no artistic film approval'}))
