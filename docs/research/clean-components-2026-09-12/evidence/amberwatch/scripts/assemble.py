"""Assemble source-bound production artwork through CLI transactions."""
import json,hashlib,subprocess,os,math
from pathlib import Path
from PIL import Image,ImageDraw,ImageChops
P=Path(__file__).resolve().parents[1];ROOT=P.parents[1];W,H=1448,1086
def save(p,d):Path(p).parent.mkdir(parents=True,exist_ok=True);Path(p).write_text(json.dumps(d,indent=2)+'\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def cli(*args):
 r=subprocess.run([str(ROOT/'ambiance'),'--project',str(P),*map(str,args)],capture_output=True,text=True)
 d=json.loads(r.stdout)
 if r.returncode:raise RuntimeError(str(args)+': '+str(d)[:2000])
 return d['data']
def compile(aid,frames,point,cell,columns=1,landmarks=None):
 rp=P/'assets/recipes'/(aid+'.json');reg={'mode':'landmarks' if landmarks else 'fixed','target':[.5,.5]};reg['points' if landmarks else 'point']=landmarks or point
 save(rp,{'version':1,'id':aid,'input':{'frames':[os.path.relpath(f,rp.parent) for f in frames],'allow_opaque':True},'registration':reg,'output':{'cell_size':cell,'columns':columns,'padding':2,'allow_upscale':False},'rights':'User seed / built-in imagegen, deterministic project derivative.'})
 pack=P/'assets/production'/aid
 if not pack.exists():cli('asset','build',rp,'--out',pack)
 catalog=json.loads((P/'assets/catalog.json').read_text())
 if not any(a['id']==aid for a in catalog['assets']):cli('asset','admit',pack)
 return json.loads((pack/'asset.json').read_text())
D=P/'assets/derivatives/v2';D.mkdir(parents=True,exist_ok=True)
records=json.loads((P/'assets/derivatives/v1/preparation-manifest.json').read_text())['parts']
# New clean structure source keeps the existing ownership mask and registration.
old=json.loads((P/'assets/derivatives/v1/preparation-manifest.json').read_text())
house=next(r for r in records if r['id']=='cottage');box=house['crop'];alpha=Image.open(P/'assets/derivatives/v1/cottage.png').getchannel('A')
im=Image.open(P/'assets/source/structure-clean-v2.png').convert('RGBA').crop(box);im.putalpha(alpha);im.save(D/'cottage-v2.png');compile('cottage-v2',[D/'cottage-v2.png'],[im.width/2,im.height/2],[im.width+4,im.height+4]);house['asset']['id']='cottage-v2'
# Native alpha exists on leaf and flame returns. Preserve it rather than replacing it.
for typ,cols,rows,cell,points in [('leaf',3,2,[520,520],None),('flame',4,2,[460,470],[[220,368],[221,368],[222,368],[222,368],[220,360],[221,360],[222,360],[222,360]])]:
 src=Image.open(P/f'assets/source/{typ}-cels-v1.png').convert('RGBA');fs=[]
 for j in range(rows):
  for i in range(cols):
   c=src.crop((round(i*src.width/cols),round(j*src.height/rows),round((i+1)*src.width/cols),round((j+1)*src.height/rows)))
   f=D/f'{typ}-{j*cols+i}.png';c.save(f);fs.append(f)
 compile(typ+'-native-alpha',fs,[src.width/cols/2,src.height/rows/2],cell,cols,points)
# Cut fixed sconces, their clean wall exists in cottage-v2.
stage=Image.open(P/'assets/source/stage-composition-v1.png').convert('RGBA')
for n,box in enumerate([(847,304,881,374),(1080,301,1111,368),(1137,297,1169,364)]):
 c=stage.crop(box);f=D/f'sconce-{n}.png';c.save(f);compile(f'sconce-{n}',[f],[c.width/2,c.height/2],[c.width+4,c.height+4]);records.append({'id':f'sconce-{n}','item':'lanterns','crop':list(box),'cell':[c.width+4,c.height+4],'source_anchor':[(box[0]+box[2])/2,(box[1]+box[3])/2],'offset':[0,0],'asset':{'id':f'sconce-{n}'}})
# Fixture bodies are dimmed only inside their glass. The complete source remains preserved.
glass_centers={'lantern-left':(523,788,19,29),'lantern-step':(848,584,15,22),'lantern-step-low':(802,658,12,20),'lantern-right-low':(1034,766,14,22),'lantern-post':(1350,797,30,49),'sconce-0':(864,344,13,22),'sconce-1':(1096,336,12,22),'sconce-2':(1153,333,12,22)}
emissions=[]
for r in records:
 aid=r['id']
 if aid not in glass_centers and not (aid.startswith('pumpkin-') and aid!='pumpkin-shelf'):continue
 src=Image.open(P/f'assets/derivatives/v1/{aid}.png').convert('RGBA') if not aid.startswith('sconce') else Image.open(D/(aid+'.png')).convert('RGBA')
 pix=src.load();mask=Image.new('L',src.size);mp=mask.load()
 for y in range(src.height):
  for x in range(src.width):
   rr,g,b,a=pix[x,y]
   if aid in glass_centers:
    cx,cy,rx,ry=glass_centers[aid];nx=x+r['crop'][0];ny=y+r['crop'][1];inside=((nx-cx)/rx)**2+((ny-cy)/ry)**2<1
   else:inside=True
   strength=max(0,min(1,(g-95)/95)) if inside and rr>g*.95 and g>b*1.25 else 0
   if strength:
    dim=.18 if aid in glass_centers else .35
    pix[x,y]=(round(rr*(1-strength*(1-dim))),round(g*(1-strength*(1-dim))),round(b*(1-strength*(1-dim))),a)
    mp[x,y]=round(strength*a)
 f=D/(aid+'-dim.png');src.save(f);compile(aid+'-dim',[f],[src.width/2,src.height/2],[src.width+4,src.height+4]);r['asset']['id']=aid+'-dim'
 if aid.startswith('pumpkin'):
  lit=Image.open(P/f'assets/derivatives/v1/{aid}.png').convert('RGBA');lit.putalpha(mask);f=D/(aid+'-emission.png');lit.save(f);compile(aid+'-emission',[f],[lit.width/2,lit.height/2],[lit.width+4,lit.height+4]);emissions.append({**r,'id':aid+'-emission','asset':{'id':aid+'-emission'},'owner':aid})
# Blank-scene basis setup, saved before any authored layers. All placements use a transaction.
scene_path=P/'scene/scene.json';scene=json.loads(scene_path.read_text())
if not scene['layers']:
 save(P/'scene/initial-blank.json',scene)
 scene['canvas'].update(width=W,height=H);scene['camera']['overscan']=1
 scene['framing']={'version':1,'views':{'portrait':{'rect_scene_px':[531,0,610.875,1086],'output':{'width':1080,'height':1920}},'landscape':{'rect_scene_px':[0,15,1448,814.5],'output':{'width':1920,'height':1080}}}}
 save(scene_path,scene)
else:raise RuntimeError('Assembly expects empty scene; revise through a new transaction.')
ops=[];layers=[]
def add(aid,lid,x,y,w,h,depth=1,anchor=[.5,.5],**extra):
 v=dict(x=x/W,y=y/H,width=w/W,height=h/H,anchor=anchor,scale=1,rotation=0,opacity=1,visible=True,depth=depth,blend='source-over',cycle_seconds=16,phase_frames=0,**extra)
 ops.append({'op':'add','asset':aid,'id':lid,'values':v});layers.append(lid);return v
def track(keys,kind='smoothstep'):return {'interpolation':kind,'keys':keys}
for r in records:
 if 'crop' not in r:continue
 aid=r['asset']['id'];x,y=r['source_anchor'];dx,dy=r['offset'];cw,ch=r['cell']
 add(aid,r['id'],x+dx,y+dy,cw,ch,depth=.1 if r['id']=='sky' else .25 if r['id']=='valley' else 1)
 # sky duplicate is a slow, small crossfade drift under the still valley and architecture.
 if r['id']=='sky':
  add(aid,'cloud-veil',x,y,cw,ch,depth=.1,tracks={'x':track([[0,x/W],[8,(x+18)/W],[16,x/W]]),'opacity':track([[0,.16],[8,.38],[16,.16]])})
# Complete cat feet in the compiler are at cell center. Destination is moderately larger than seed.
add('cat-cels','cat',676,452,155,212,tracks={'cell':track([[0,0],[2.8,0],[3.0,1],[3.25,2],[5.4,1],[5.7,0],[8.9,3],[9.05,4],[9.25,3],[9.45,5],[11.8,1],[12.1,2],[13.3,1],[13.6,0],[16,0]],'hold')})
for r in emissions:
 x,y=r['source_anchor'];cw,ch=r['cell'];add(r['asset']['id'],r['id'],x,y,cw,ch)
flames=[]
for n,(lid,(cx,cy,rx,ry)) in enumerate(glass_centers.items()):
 dy=-42 if lid=='lantern-post' else 0
 # Original base glass shows a candle block, the changing emission starts at its wick.
 base_y=cy+ry*.25+dy;height=ry*2.3;width=height*460/470
 fid=lid+'-flame';add('flame-native-alpha',fid,cx,base_y,width,height,tracks={'cell':track([[0,n%8],[.25,(n+1)%8],[.5,(n+2)%8],[.75,(n+3)%8],[1,(n+4)%8],[1.25,(n+5)%8],[1.5,(n+6)%8],[1.75,(n+7)%8],[2,n%8],[16,n%8]],'hold')})
 # Replace provisional track with 8fps loop, phase separated between fixtures.
 ops[-1]['values'].pop('tracks');ops[-1]['values']['cycle_seconds']=2;ops[-1]['values']['phase_frames']=n%8;flames.append(fid)
# Drift routes use explicit hidden resets. Cadence is staggered; no unique leaf resets in view.
for n in range(14):
 t0=(n*1.13)%13;dur=3.0+(n%4)*.55;t1=min(15.7,t0+dur)
 x0=490+(n*97)%850;y0=60+(n*119)%570;x1=x0-160-(n%3)*55;y1=y0+265+(n%4)*25
 sz=15+(n%4)*5
 keysx=[[0,x0/W]];keysy=[[0,y0/H]];vis=[[0,False]]
 if t0>0:keysx.append([t0,x0/W]);keysy.append([t0,y0/H]);vis.append([t0,True])
 else:vis.append([.04,True])
 keysx += [[t1,x1/W],[16,x0/W]];keysy += [[t1,y1/H],[16,y0/H]];vis += [[t1,False],[16,False]]
 add('leaf-native-alpha','leaf-'+str(n),x0,y0,sz,sz,depth=1.4,track_loop='hidden-reset',tracks={'x':track(keysx,'linear'),'y':track(keysy,'linear'),'visible':track(vis,'hold'),'rotation':track([[0,-.7+n*.3],[t1,1.2+n*.3],[16,-.7+n*.3]],'linear')})
 ops[-1]['values']['cycle_seconds']=4;ops[-1]['values']['phase_frames']=n%6
# Fixed source/receiver light zones, independent deterministic source signals.
signals=[];lights=[];links=[]
for n,r in enumerate(emissions):
 owner=r['owner'];signal=owner+'-power';keys=[[i/4,.68+.20*math.sin(i*1.61+n)+.09*math.sin(i*3.19+n*2)] for i in range(64)];keys.append([16,keys[0][1]])
 signals.append({'id':signal,'keys':keys,'interpolation':'smoothstep'})
 links.append({'id':owner+'-face','source':{'signal':signal,'range':[0,1]},'target':{'layer':r['id'],'channel':'opacity','range':[0,1]},'map':{'interpolation':'linear','keys':[[0,0],[1,1]]},'off':0})
 x,y=r['source_anchor'];cw,ch=r['cell'];lights.append({'id':owner+'-stones','receivers':['path','cottage'],'rect':[(x-cw*.8)/W,(y+ch*.25)/H,cw*1.9/W,ch*.75/H],'color':'#ffad51','gain':.42,'feather':.45,'signal':signal})
for n,(lid,(cx,cy,rx,ry)) in enumerate(glass_centers.items()):
 signal=lid+'-power';signals.append({'id':signal,'layer':lid+'-flame','values':[.85,1,.74,.62,.9,.68,1.08,.8]})
 dy=-42 if lid=='lantern-post' else 0
 lights.append({'id':lid+'-receiver','receivers':['path','cottage','fence-right','fence-left'],'rect':[(cx-rx*2.8)/W,(cy+dy-ry*1.2)/H,rx*5.6/W,ry*3.8/H],'color':'#ffb766','gain':.24,'feather':.45,'signal':signal})
ops.append({'op':'finishing','value':{'version':1,'working_space':'linear-srgb','output_space':'srgb','signals':signals,'lights':lights,'layers':{'cat':{'exposure':-.35}},'grade':{'saturation':.94}}})
ops.append({'op':'bindings','value':{'version':1,'links':links}})
save(P/'plans/assembly-v1.json',{'version':1,'operations':ops});result=cli('scene','apply',P/'plans/assembly-v1.json');save(P/'reports/assembly-v1.json',result)
save(D/'assembly-assets.json',{'sources':{f.name:sha(f) for f in (P/'assets/source').glob('*.png')},'records':records,'emissions':emissions,'script_sha256':sha(__file__)})
print(json.dumps({'ok':True,'layers':len(layers),'scene':str(scene_path)}))
