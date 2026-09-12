#!/usr/bin/env python3
"""Public CLI replay. Synthetic by default; optional existing paintings stay local."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[2]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('out',type=Path)
    parser.add_argument('--source',type=Path);parser.add_argument('--mask',type=Path);parser.add_argument('--paint',type=Path)
    parser.add_argument('--paint-rect',type=int,nargs=4);parser.add_argument('--no-render',action='store_true');args=parser.parse_args();out=args.out.resolve();calls=[]
    def run(*parts):
        command=[sys.executable,str(ROOT/'ambiance'),'--project',str(out),*map(str,parts)]
        process=subprocess.run(command,capture_output=True,text=True);result=json.loads(process.stdout)
        calls.append({'args':list(map(str,parts)),'ok':result['ok']})
        if process.returncode: raise ValueError(process.stdout+process.stderr)
        return result['data']
    def write(name,value):
        path=out/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2)+'\n');return path
    run('project','init',out,'--format','dual','--title','Region art workbench · independent study')
    raw=out/'assets/raw';raw.mkdir(exist_ok=True)
    if args.source: shutil.copyfile(args.source,raw/'source.png')
    else:
        im=Image.new('RGB',(320,320),'#795a44');d=ImageDraw.Draw(im)
        d.rectangle([64,100,256,276],fill='#213745');d.pieslice([64,16,256,208],180,360,fill='#213745')
        d.rectangle([154,28,165,276],fill='#b19368');d.ellipse([215,50,238,73],fill='#efce8c');im.save(raw/'source.png')
    with Image.open(raw/'source.png') as im: w,h=im.size
    base_recipe=write('plans/base.json',{'version':1,'id':'region-base','input':{'frames':['../assets/raw/source.png'],'allow_opaque':True},
               'registration':{'mode':'fixed','point':[w/2,h/2],'target':[.5,.5]},'output':{'cell_size':[w+4,h+4],'columns':1,'padding':2}})
    run('asset','build',base_recipe,'--out',out/'assets/production/base');run('asset','admit',out/'assets/production/base')
    run('scene','add','region-base','--id','base','--width','1')
    clock=write('plans/still-clock.json',{'version':1,'operations':[{'op':'camera','values':{'overscan':1,'x_amplitude':0,'y_amplitude':0,'zoom_amplitude':0}}]})
    run('scene','apply',clock)
    mask=json.loads(args.mask.read_text()) if args.mask else {'polygons':[{'operation':'add','points':[[68,272],[68,111],[75,83],[94,55],[122,37],[151,30],[180,33],[214,48],[240,76],[252,103],[252,272]]},
                                                                      {'operation':'subtract','points':[[153,27],[166,27],[166,274],[153,274]]}]}
    # Center each saved study view on the selected region before binding sizing.
    scene_path=out/'scene/scene.json';scene=json.loads(scene_path.read_text())
    pts=[point for poly in mask['polygons'] if poly['operation']=='add' for point in poly['points']]
    cx=(min(p[0] for p in pts)+max(p[0] for p in pts))/2;cy=(min(p[1] for p in pts)+max(p[1] for p in pts))/2
    factor=1920/(w+4);cx=(cx+2)*factor;cy=(1920-(h+4)*factor)/2+(cy+2)*factor
    framing=scene['framing']
    for view in framing['views'].values():
        _,_,vw,vh=view['rect_scene_px'];view['rect_scene_px']=[max(0,min(1920-vw,cx-vw/2)),max(0,min(1920-vh,cy-vh/2)),vw,vh]
    run('view','apply',write('plans/study-views.json',framing))
    draft=out/'assets/regions/draft';run('asset','region','init',raw/'source.png','--id','traced-opening','--base','base','--out',draft)
    recipe=json.loads((draft/'recipe.json').read_text())
    batch=write('plans/region-edit.json',{'version':1,'operations':[{'op':'set-visible-mask','value':mask},
        {'op':'set-frame','value':{'aspect':'square','padding':[12]*4,'rect_xyxy':None}},
        {'op':'set-sizing','value':{**recipe['sizing'],'quality_multiplier':1}},
        {'op':'set-intent','value':{'brief':'Fit this existing painted study into the traced region.','preserve':'Keep the source border and every excluded foreground detail.','asset_id':'region-insert'}}]})
    edited=out/'assets/regions/edited';run('asset','region','edit',draft,'--batch',batch,'--out',edited)
    run('asset','region','check',edited);packet=out/'assets/regions/packet';run('asset','region','build',edited,'--out',packet)
    sizing=json.loads((packet/'report.json').read_text());ew,eh=sizing['export_size']
    if args.paint:
        shutil.copyfile(args.paint,raw/'paint-source.png')
        with Image.open(raw/'paint-source.png') as im: pw,ph=im.size
        # Centered square crop uses existing local art, with an explicit resampling recipe.
        side=min(pw,ph);left=(pw-side)//2;top=(ph-side)//2
        crop=write('plans/paint-crop.json',{'version':1,'crop_xyxy':args.paint_rect or [left,top,left+side,top+side],'export_size':[ew,eh],'resampling':'bicubic'})
        run('asset','crop',raw/'paint-source.png','--recipe',crop,'--out',out/'assets/regions/paint-crop')
        returned=out/'assets/regions/paint-crop/crop.png'
    elif args.source:
        returned=packet/'reference.png'
    else:
        im=Image.new('RGB',(ew,eh),'#355665');d=ImageDraw.Draw(im)
        d.ellipse([ew*.58,eh*.15,ew*.78,eh*.35],fill='#e4ca90')
        d.polygon([(0,eh),(0,eh*.8),(ew*.4,eh*.45),(ew*.7,eh*.8),(ew,eh*.6),(ew,eh)],fill='#27434a')
        returned=raw/'returned.png';im.save(returned)
    request=run('asset','request','record',packet/'request-draft.json');request_id=json.loads((packet/'request-draft.json').read_text())['local_request_id']
    import hashlib
    digest=hashlib.sha256(returned.read_bytes()).hexdigest()
    receipt=write('plans/retrieved.json',{'version':1,'event_id':'existing-local-art','state':'retrieved','outputs':[{'file':str(returned.relative_to(out)),'sha256':digest,'provider_output_id':None}]})
    run('asset','request','reconcile',request_id,'--receipt',receipt)
    selection=write('plans/selected.json',{'version':1,'event_id':'selected-local-art','state':'selected','selected_output_sha256':digest})
    run('asset','request','reconcile',request_id,'--receipt',selection)
    spec=json.loads((packet/'return-template.json').read_text());spec.update(request_id=request_id)
    spec['registration']={'edit_to_export':[1,0,0,1,0,0],'note':'Existing rectangular paint was explicitly cropped onto this exact export canvas; identity placement selected for the study.'}
    alignment=write('plans/return.json',spec);result=out/'assets/regions/returned'
    run('asset','region','return',packet,returned,'--recipe',alignment,'--out',result)
    run('asset','build',result/'compiler.json','--out',out/'assets/production/insert');run('asset','admit',out/'assets/production/insert')
    source=json.loads((result/'source-mapping.json').read_text())['reference']
    placement=write('plans/place.json',{'version':1,'kind':'ambiance-source-placement','placements':[{'id':'insert','asset':'region-insert','base':'base','mode':'native','reference':source}]})
    run('scene','place',placement)
    captures=write('plans/capture.json',{'format':'ambiance-revision-selection','schema_version':1,'scene':'scene/scene.json','catalog':'assets/catalog.json','documents':{'generation_ledger':'plans/generation-ledger.json'}})
    # Capture through the public revision contract after placement.
    run('revision','capture','region-study','--selection',captures)
    if not args.no_render:
        for view in ('portrait','landscape'):
            run('render','frame','--view',view,'--width',360 if view=='portrait' else 640,'--out',out/'reports'/view)
    write('reports/replay.json',{'ok':True,'scope':'Static region study; synthetic art unless explicit source/paint supplied.',
          'source_origin':str(args.source) if args.source else 'locally drawn synthetic fixture','calls':calls,
          'packet':str(packet),'returned':str(result),'review_status':'unreviewed'})
    print(json.dumps({'ok':True,'project':str(out),'packet':str(packet),'returned':str(result),'calls':len(calls)}))


if __name__=='__main__':main()
