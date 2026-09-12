"""Bake bounded receiver contributions into compact painted layers.

Uses source texture, prepared alpha and existing authored source phases. Native Canvas
composites these layers; this avoids repeated software grading of the static whole stage.
"""
import json,hashlib,subprocess,os,math
from pathlib import Path
from PIL import Image,ImageDraw,ImageChops
P=Path(__file__).resolve().parents[1];ROOT=P.parents[1];W,H=1448,1086
def save(p,d):Path(p).parent.mkdir(parents=True,exist_ok=True);Path(p).write_text(json.dumps(d,indent=2)+'\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def cli(*args):
 r=subprocess.run([str(ROOT/'ambiance'),'--project',str(P),*map(str,args)],capture_output=True,text=True);j=json.loads(r.stdout)
 if r.returncode:raise RuntimeError(str(j)[:1800])
 return j['data']
def compile(aid,frames,cell):
 rp=P/'assets/recipes'/(aid+'.json');save(rp,{'version':1,'id':aid,'input':{'frames':[os.path.relpath(f,rp.parent) for f in frames],'allow_opaque':True},'registration':{'mode':'fixed','point':[(cell[0]-4)/2,(cell[1]-4)/2],'target':[.5,.5]},'output':{'cell_size':cell,'columns':min(4,len(frames)),'padding':2,'allow_upscale':False}})
 if not (P/'assets/production'/aid).exists():cli('asset','build',rp,'--out',P/'assets/production'/aid)
 if not any(a['id']==aid for a in json.loads((P/'assets/catalog.json').read_text())['assets']):cli('asset','admit',P/'assets/production'/aid)
def track(keys,kind='smoothstep'):return {'interpolation':kind,'keys':keys}
s=json.loads((P/'scene/scene.json').read_text());cat=json.loads((P/'assets/catalog.json').read_text());assets={a['id']:a for a in cat['assets']};layers={l['id']:l for l in s['layers']};D=P/'assets/derivatives/v4';D.mkdir(parents=True,exist_ok=True);ops=[{'op':'socket','layer':r,'name':'paint-origin','value':[0,0]} for r in ['path','cottage','fence-left','fence-right']];links=[];newlayers={};receipts=[]
records=json.loads((P/'assets/derivatives/v2/assembly-assets.json').read_text())['records'];rec={r['id']:r for r in records}
for lid in ['sconce-0','sconce-1','sconce-2','lantern-right-low']:
 r=rec[lid];src=Image.open(P/('assets/derivatives/v2/'+lid+'.png' if lid.startswith('sconce') else 'assets/derivatives/v1/'+lid+'.png')).convert('RGBA');m=Image.new('L',src.size);dr=ImageDraw.Draw(m)
 if lid.startswith('sconce'):
  ww,hh=src.size;pts=[(.49,.03),(.61,.10),(.57,.23),(.85,.35),(.85,.63),(.73,.80),(.60,.86),(.65,.95),(.32,.95),(.35,.85),(.20,.79),(.08,.38),(.16,.31),(.39,.23),(.39,.13)]
  dr.polygon([(int(x*ww),int(y*hh)) for x,y in pts],fill=255)
 else:
  m=src.getchannel('A');dr=ImageDraw.Draw(m);dr.polygon([(37,52),(50,46),(50,80),(32,80)],fill=0)
 src.putalpha(ImageChops.multiply(src.getchannel('A'),m));f=D/(lid+'-trim.png');src.save(f);compile(lid+'-trim',[f],[src.width+4,src.height+4]);ops.append({'op':'set','layer':lid,'values':{'asset':lid+'-trim'}})
# Eight light-only face drawings keep each pumpkin's shape fixed and source intensity explicit.
values=[.74,.94,.66,.81,1,.72,.9,.79]
for n,l in enumerate(s['layers']):
 if not l['id'].endswith('-emission'):continue
 a=assets[l['asset']];atlas=Image.open(P/a['file']).convert('RGBA');base=atlas.crop((2,2,a['atlas']['cell_width']-2,a['atlas']['cell_height']-2));fs=[]
 for i,v in enumerate(values):
  im=base.copy();im.putalpha(base.getchannel('A').point(lambda x,v=v:round(x*v)));f=D/(l['id']+f'-{i}.png');im.save(f);fs.append(f)
 aid=l['id']+'-phases';compile(aid,fs,[base.width+4,base.height+4]);ops.append({'op':'set','layer':l['id'],'values':{'asset':aid,'cycle_seconds':4,'phase_frames':n%8}})
for light in s['finishing']['lights']:
 signal=next(a for a in s['finishing']['signals'] if a['id']==light['signal'])
 driver=signal.get('layer') or light['id'].replace('-stones','-emission');phase_values=signal.get('values') or values
 rx,ry,rw,rh=[light['rect'][0]*W,light['rect'][1]*H,light['rect'][2]*W,light['rect'][3]*H]
 for receiver in light['receivers']:
  layer=layers[receiver];a=assets[layer['asset']];atlas=Image.open(P/a['file']).convert('RGBA');cw=a['atlas']['cell_width'];ch=a['atlas']['cell_height'];paint=atlas.crop((0,0,cw,ch));left=layer['x']*W-layer['width']*W*.5;top=layer['y']*H-layer['height']*H*.5
  x0=max(0,math.floor(rx-left));y0=max(0,math.floor(ry-top));x1=min(cw,math.ceil(rx+rw-left));y1=min(ch,math.ceil(ry+rh-top))
  if x1<=x0 or y1<=y0:continue
  p=paint.crop((x0,y0,x1,y1));pix=p.load();nonzero=False
  for y in range(p.height):
   for x in range(p.width):
    rr,g,b,alpha=pix[x,y];wx=left+x0+x;wy=top+y0+y;dist=math.sqrt(((wx-(rx+rw/2))/(rw/2))**2+((wy-(ry+rh/2))/(rh/2))**2);weight=max(0,min(1,(1-dist)/.45));aa=round(alpha*weight*.28)
    pix[x,y]=(min(255,round(rr*1.5)),round(g*.9),round(b*.5),aa);nonzero=nonzero or aa>0
  if not nonzero or p.getchannel('A').getextrema()[1]<20:continue
  aid=light['id']+'-'+receiver+'-paint';f=D/(aid+'.png');p.save(f);compile(aid,[f],[p.width+4,p.height+4])
  lid=aid;v={'x':(left+x0+p.width/2)/W,'y':(top+y0+p.height/2)/H,'width':(p.width+4)/W,'height':(p.height+4)/H,'anchor':[.5,.5],'depth':layer.get('depth',1),'scale':1,'rotation':0,'opacity':1,'visible':True,'blend':'screen','cycle_seconds':16,'phase_frames':0}
  v.pop('depth');v['attach']={'layer':receiver,'socket':'paint-origin'};v['x']=(x0+p.width/2)/W;v['y']=(y0+p.height/2)/H
  ops.append({'op':'add','asset':aid,'id':lid,'values':v});newlayers.setdefault(receiver,[]).append(lid)
  links.append({'id':lid+'-driver','source':{'layer':driver,'channel':'cell'},'target':{'layer':lid,'channel':'opacity','range':[0,1]},'map':{'values':[min(1,v) for v in phase_values]},'off':0})
  receipts.append({'layer':lid,'driver':driver,'receiver':receiver,'source_asset':a['id'],'crop':[x0,y0,x1,y1],'region':light['rect'],'mask':'elliptical 45% feather × receiver alpha; screen contribution retains source texture','file':str(f.relative_to(P)),'sha256':sha(f)})
ops.append({'op':'finishing','value':None});ops.append({'op':'bindings','value':{'version':1,'links':links}})
order=[]
for l in s['layers']:order += [l['id']]+newlayers.get(l['id'],[])
ops.append({'op':'order','layers':order});save(P/'plans/painted-lighting-v4.json',{'version':1,'operations':ops});cli('scene','apply',P/'plans/painted-lighting-v4.json')
save(D/'lighting-receipt.json',{'version':1,'sources':[{'file':'scene/scene.json','sha256':sha(P/'scene/scene.json')}],'script_sha256':sha(__file__),'contributions':receipts,'decision':'Use source-textured bounded paint and actual flame/face cel bindings. Static full-frame source grading is unnecessary; project still uses the shared studio renderer.'})
print(json.dumps({'ok':True,'light_contributions':len(receipts)}))
