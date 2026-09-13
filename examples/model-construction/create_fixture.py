"""Prepare compiler-backed copies of the mc/1 geometric art; no production art claim."""
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.asset_tool import build
from ambiance_studio.file_identity import digest
import studio


def create(out):
    out = Path(out).resolve(); out.mkdir(parents=True, exist_ok=False)
    source = ROOT/'tests/fixtures/model-contract'
    (out/'art').mkdir(); (out/'models').mkdir(); (out/'recipes').mkdir()
    for name in ['housing', 'frame-square', 'frame-arched', 'wax', 'flame']:
        shutil.copyfile(source/f'art/{name}.png', out/f'art/{name}.png')
    # A separate translucent pane for authored glass-role coverage, explicitly synthetic.
    from PIL import Image
    # Preserve repository originals. This test derivative gives the rear frame
    # an actual opening so excluding glass/flame cannot silently fill it.
    housing = Image.open(out/'art/housing.png').convert('RGBA')
    housing.paste((0,0,0,0),(6,7,26,41)); housing.save(out/'art/housing.png')
    pane = Image.new('RGBA', (32,48)); pane.paste((127,179,193,65),(7,16,25,39)); pane.save(out/'art/glass.png')
    defs = {name: studio.read(source/f'models/{name}-v1.json') for name in ['lantern', 'candle']}
    specs = {'housing': ([32,48],[16,46]), 'frame-square': ([32,48],[16,46]), 'frame-arched': ([32,48],[16,46]), 'glass': ([32,48],[16,46]), 'wax': ([12,20],[6,18]), 'flame': ([8,12],[4,12])}
    packs = {}
    for name,(size,pivot) in specs.items():
        cw,ch = size[0]+8,size[1]+8
        recipe = {'version':1,'id':name+'-compiled','input': {'sheet': '../art/'+name+'.png','columns':4 if name=='flame' else 1,'rows':1,'frame_count':4 if name=='flame' else 1}, 'output':{'cell_size':[cw,ch],'columns':4 if name=='flame' else 1,'padding':2},'registration':{'mode':'fixed','point':pivot,'target':[(pivot[0]+4)/cw,(pivot[1]+4)/ch]},'rights':'Synthetic mc/1 engineering specimen; no production-art acceptance.'}
        studio.write(out/f'recipes/{name}.json',recipe); build(out/f'recipes/{name}.json',out/f'packs/{name}')
        packs[name] = studio.read(out/f'packs/{name}/asset.json')
    for name, definition in defs.items():
        definition.pop('packet_version'); definition.pop('local_cycles',None); definition.pop('emitters',None)
        definition.update(format='ambiance-model-definition',schema_version=1,notes='Complete geometric raster-root engineering specimen, not accepted painted production art.')
        definition['controls'] = [c for c in definition['controls'] if c['control_id'] != 'flame-phase']
        if name=='lantern':
            definition['drawings'].append({'drawing_id':'glass','asset':{},'cel_index':0,'material_role':'glass'})
            definition['parts'].insert(1,{'part_id':'glass','drawing_id':'glass','cell_to_local':[1,0,0,1,0,0],'mount':{'part_path':['housing'],'socket_id':'origin'}})
            definition['paint_order'].insert(1,['glass'])
            definition['controls'].extend([{'control_id':'sway','type':'number','unit':'radians','default':0,'min':-.12,'max':.12,'target':{'part_path':['housing'],'channel':'rotation'}},{'control_id':'visible','type':'boolean','default':True,'target':{'part_path':['housing'],'channel':'visible'}}])
        else:
            definition['controls'].extend([{'control_id':'bend','type':'number','unit':'radians','default':0,'min':-.25,'max':.25,'target':{'part_path':['flame'],'channel':'rotation'}},{'control_id':'flame-shape','type':'drawing','default':'flame-0','drawings':['flame-0','flame-1','flame-2','flame-3'],'target':{'part_path':['flame'],'channel':'drawing'}}])
        original = {p['drawing_id']:p['cell_to_local'][:] for p in definition['parts'] if 'drawing_id' in p}
        for drawing in definition['drawings']:
            art = 'flame' if drawing['drawing_id'].startswith('flame-') else drawing['drawing_id']
            if art in ['frame-square','frame-arched']: local = original['frame-square'][:]
            elif art=='flame': local = original['flame-0'][:]
            else: local = original[art][:]
            asset=packs[art]; cel=asset['registration_mapping']['cels'][drawing['cel_index']]; sc=asset['registration_mapping']['shared_scale']; stc=cel['source_to_cell']
            # Sheet cels preserve whole-input origin; artistically identical local registration.
            local[4]-=(drawing['cel_index']*8 if art=='flame' else 0)
            drawing['source_to_local']=local
            drawing['asset']={'file':f'../packs/{art}/asset.json','sha256':digest(out/f'packs/{art}/asset.json'),'report_sha256':digest(out/f'packs/{art}/report.json')}
            ctl=[1/sc,0,0,1/sc,local[4]-stc[4]/sc,local[5]-stc[5]/sc]
            for part in definition['parts']:
                if part.get('drawing_id')==drawing['drawing_id']:part['cell_to_local']=ctl
        # Preserve authored socket locations under the compiler's padding/scale.
        for socket in definition.get('sockets',[]):
            part=next(p for p in definition['parts'] if p['part_id']==socket['part_path'][0]); d=next(d for d in definition['drawings'] if d['drawing_id']==part['drawing_id']); art='flame' if d['drawing_id'].startswith('flame-') else d['drawing_id']; size,pivot=specs[art]; asset=packs[art]; cel=asset['registration_mapping']['cels'][d['cel_index']]; m=cel['source_to_cell']; x,y=socket['cell_uv'][0]*size[0],socket['cell_uv'][1]*size[1]; socket['cell_uv']=[(m[0]*x+m[4])/asset['atlas']['cell_width'],(m[3]*y+m[5])/asset['atlas']['cell_height']]
        if name=='lantern':
            ref=next(p['definition'] for p in definition['parts'] if 'definition' in p);ref['sha256']='pending'
        if name=='lantern':
            # Output viewport includes the complete extreme poses. Geometry is
            # still local and unclipped; no film composition is inherited.
            definition['local_frame']={'size':[64,80],'pivot':[32,62],'clip':'none'}
            for drawing in definition['drawings']:
                drawing['source_to_local'][4]+=16;drawing['source_to_local'][5]+=16
            for part in definition['parts']:
                matrix=part['local_to_parent'] if 'definition' in part else part['cell_to_local']
                matrix[4]+=16;matrix[5]+=16
        studio.write(out/f'models/{name}.json',definition)
    candle=out/'models/candle.json'; lantern=defs['lantern']; ref=next(p['definition'] for p in lantern['parts'] if 'definition' in p);ref.update(file='candle.json',sha256=digest(candle));studio.write(out/'models/lantern.json',lantern)
    states=[]
    for frame in ['square','arched']:
        for pose,controls in [('rest',[]),('left',[([], 'sway',-.12),(['candle'],'bend',-.25),(['candle'],'flame-shape','flame-1')]),('right',[([], 'sway',.12),(['candle'],'bend',.25),(['candle'],'flame-shape','flame-3')]),('unlit',[([], 'source-on',False)]),('hidden',[([], 'visible',False)])]:
            states.append({'schema_version':1,'pose_id':frame+'-'+pose,'controls':[{'model_path':p,'control_id':c,'value':v} for p,c,v in controls],'variants':[{'model_path':[],'variant_set_id':'frame','variant_id':frame}]})
    studio.write(out/'proof.json',{'schema_version':1,'states':states,'roles':['solid','glass','flame'],'threshold':16});studio.write(out/'rest.json',states[0])
    return out

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);args=p.parse_args();print(json.dumps({'source_root':str(create(args.out))}))
