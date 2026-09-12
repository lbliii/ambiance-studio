"""Deterministic derivative masks/crops/registration. No source paint is overwritten.

Artwork is produced with built-in imagegen. This script traces production ownership,
removes declared backing colors, and invokes the studio compiler and CLI admission.
"""
import json,hashlib,subprocess,sys,math
from pathlib import Path
from PIL import Image,ImageDraw,ImageFilter,ImageChops
P=Path(__file__).resolve().parents[1]; ROOT=P.parents[1]
RAW=P/'assets/source'; OUT=P/'assets/derivatives/v1';OUT.mkdir(parents=True,exist_ok=True)
REC=P/'assets/recipes';REC.mkdir(exist_ok=True)
records=[]
def h(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,d):Path(p).write_text(json.dumps(d,indent=2)+'\n')
def cli(*args):
 r=subprocess.run([str(ROOT/'ambiance'),'--project',str(P),*map(str,args)],capture_output=True,text=True)
 try:d=json.loads(r.stdout)
 except Exception:raise RuntimeError(r.stdout+r.stderr)
 if r.returncode:raise RuntimeError(str(args)+': '+str(d)[:1800])
 return d['data']
def compile_asset(aid,images,point,cell,columns=1,landmarks=None,source=None,mapping=None):
 rec=REC/(aid+'.json')
 recipe={'version':1,'id':aid,'input':{'frames':[str(Path(x).relative_to(REC.parent.parent)) for x in images],'allow_opaque':True},'registration':{'mode':'landmarks' if landmarks else 'fixed','target':[.5,.5]},'output':{'cell_size':cell,'columns':columns,'padding':2,'allow_upscale':False},'rights':'Project-owned built-in imagegen artwork derived from the user seed; original and mask recipe preserved.'}
 # compiler inputs are recipe-relative
 import os
 recipe['input']['frames']=[os.path.relpath(x,REC) for x in images]
 recipe['registration']['points' if landmarks else 'point']=landmarks or point
 save(rec,recipe);pack=P/'assets/production'/aid
 if not pack.exists():cli('asset','build',rec,'--out',pack)
 cat=json.loads((P/'assets/catalog.json').read_text())
 if not any(a['id']==aid for a in cat['assets']):cli('asset','admit',pack)
 info=json.loads((pack/'asset.json').read_text())
 return info
def mask_poly(size,poly):
 m=Image.new('L',size);ImageDraw.Draw(m).polygon(poly,fill=255);return m
stage=Image.open(RAW/'stage-composition-v1.png').convert('RGBA');clean=Image.open(RAW/'structure-clean-v1.png').convert('RGBA');env=Image.open(RAW/'environment-backing-v1.png').convert('RGBA')
W,H=stage.size
def part(aid,source,mask,pivot=None,offset=(0,0),item=None):
 bbox=mask.getbbox()
 if bbox is None:raise ValueError(aid)
 x0,y0,x1,y1=bbox
 rgba=source.copy();rgba.putalpha(mask);rgba=rgba.crop(bbox)
 f=OUT/(aid+'.png');rgba.save(f)
 cw,ch=rgba.size;point=[cw/2,ch/2]
 info=compile_asset(aid,[f],point,[cw+4,ch+4])
 record={'id':aid,'item':item or aid,'source_sha256':h(RAW/('stage-composition-v1.png' if source is stage else 'structure-clean-v1.png' if source is clean else 'environment-backing-v1.png')),'crop':list(bbox),'source_anchor':[x0+cw/2,y0+ch/2],'cell':[cw+4,ch+4],'offset':list(offset),'asset':info}
 records.append(record);return record
def poly(aid,src,points,**kwargs):return part(aid,src,mask_poly(src.size,points),**kwargs)
# Broad environment families contain no characters or removable props.
# The sky is a full-width extension of the generated sky crop beneath the other surfaces.
sky=env.crop((0,0,W,340));skyf=OUT/'sky.png';sky.save(skyf)
skyinfo=compile_asset('sky',[skyf],[W/2,170],[W+4,344]);records.append({'id':'sky','item':'sky','crop':[0,0,W,340],'source_anchor':[W/2,170],'cell':[W+4,344],'offset':[0,0],'asset':skyinfo})
valley_mask=mask_poly((W,H),[(0,270),(115,273),(174,240),(245,276),(295,297),(372,317),(457,325),(540,348),(638,325),(724,314),(844,286),(945,234),(1070,221),(1150,225),(1270,133),(1448,95),(1448,735),(0,735)])
part('valley',env,valley_mask,item='valley')
poly('path',env,[(0,590),(220,650),(390,652),(540,624),(730,643),(840,620),(1000,611),(1180,470),(1448,360),(1448,1086),(0,1086)],item='path')
# House contour includes full roof/chimney and stairs, but excludes foreground fences.
house=[(439,243),(516,224),(516,44),(542,0),(1448,0),(1448,545),(1280,553),(1180,655),(1110,742),(785,742),(735,715),(701,668),(540,671),(444,655),(447,573),(487,558),(512,550),(512,281),(439,270)]
poly('cottage',clean,house,item='cottage')
# Tree/canopy uses the warm painted color to retain fine leaf silhouette against blue sky.
tree_region=mask_poly((W,H),[(0,0),(750,0),(689,63),(642,86),(610,30),(572,7),(530,47),(489,69),(437,105),(396,150),(338,213),(270,241),(223,276),(190,325),(152,441),(142,555),(176,593),(94,645),(0,706)])
pix=clean.load();tmask=tree_region.load()
for y in range(H):
 for x in range(min(755,W)):
  if tmask[x,y]:
   r,g,b,_=pix[x,y]
   # Within the trunk preserve dark paint; open sky and cool far pines are excluded.
   trunk=x < max(110,280-y*.37)
   if not trunk and not (r>g*1.2 and r>b*1.25):tmask[x,y]=0
part('tree',clean,tree_region,item='tree')
poly('fence-left',clean,[(0,676),(83,686),(92,591),(125,582),(212,601),(221,628),(204,636),(222,1056),(175,1086),(135,1086),(132,934),(0,946),(0,921),(128,902),(118,827),(0,812)],item='fences')
poly('fence-right',clean,[(1254,562),(1292,551),(1320,529),(1350,541),(1365,563),(1378,678),(1448,677),(1448,957),(1380,966),(1376,1086),(1281,1086),(1261,964)],item='fences')
# Source-cut whole props. Silhouette masks retain their complete visible footprint.
polygons={
 'pumpkin-near':[(162,908),(167,883),(187,865),(209,864),(216,875),(205,885),(201,905),(235,907),(269,926),(284,962),(287,1001),(276,1020),(248,1040),(206,1046),(174,1037),(143,1043),(122,1023),(114,989),(118,953),(133,925)],
 'pumpkin-left':[(639,681),(654,674),(662,668),(661,655),(674,650),(682,657),(677,670),(704,673),(724,687),(733,713),(725,734),(697,748),(660,747),(641,735),(633,713)],
 'pumpkin-right':[(1046,770),(1055,755),(1085,751),(1087,735),(1103,727),(1112,730),(1108,743),(1099,751),(1132,755),(1150,776),(1151,806),(1137,827),(1103,841),(1068,828),(1044,806)],
 'pumpkin-step':[(1047,589),(1062,578),(1065,563),(1076,559),(1086,563),(1083,575),(1107,581),(1129,599),(1126,625),(1105,643),(1073,646),(1050,635),(1041,614)],
 'chair':[(820,424),(834,423),(864,427),(883,426),(885,441),(871,442),(868,474),(895,464),(904,467),(905,477),(891,483),(905,544),(898,553),(909,555),(910,562),(888,562),(872,555),(847,557),(846,547),(834,548),(829,556),(813,551),(813,544),(826,542),(825,487),(808,478),(808,469),(823,472)],
 'wreath':[(950,358),(965,350),(977,342),(990,345),(1003,351),(1020,362),(1024,384),(1016,409),(1000,424),(976,427),(956,416),(941,397),(943,373)],
 'planter-left':[(675,639),(694,612),(719,604),(733,589),(759,590),(781,605),(803,612),(816,640),(808,672),(787,680),(782,726),(753,736),(733,721),(727,683),(701,677)],
 'planter-right':[(1038,687),(1055,663),(1092,648),(1121,628),(1158,637),(1179,655),(1202,674),(1204,708),(1181,738),(1178,785),(1156,804),(1139,801),(1129,751),(1089,740),(1064,716)],
 'hanging-basket':[(578,299),(591,307),(617,308),(633,334),(631,357),(616,376),(614,389),(591,390),(587,374),(564,360),(558,342),(568,322)],
 'pumpkin-shelf':[(1067,455),(1083,446),(1097,451),(1112,447),(1119,464),(1118,478),(1130,479),(1130,486),(1117,486),(1116,510),(1132,530),(1128,543),(1135,550),(1132,564),(1066,564),(1065,551),(1080,546),(1061,538),(1065,521),(1081,513),(1081,488),(1064,487)],
 'lantern-left':[(506,755),(509,743),(517,738),(519,728),(528,728),(531,737),(542,746),(542,757),(546,763),(545,811),(536,822),(500,821),(494,810),(496,768)],
 'lantern-step':[(833,557),(832,549),(839,543),(847,542),(852,550),(851,556),(864,563),(869,572),(868,607),(860,616),(835,617),(825,609),(826,572)],
 'lantern-step-low':[(791,634),(791,625),(799,620),(807,625),(809,634),(820,640),(822,669),(817,679),(788,681),(782,671),(783,640)],
 'lantern-right-low':[(1021,733),(1025,725),(1036,723),(1044,730),(1044,736),(1057,744),(1057,781),(1047,797),(1022,797),(1011,783),(1012,747)],
 'lantern-post':[(1320,727),(1333,719),(1336,705),(1352,697),(1363,704),(1363,715),(1380,725),(1390,742),(1390,842),(1383,855),(1391,865),(1381,875),(1321,875),(1301,861),(1308,849),(1307,747)],
}
for aid,points in polygons.items():
 item='pumpkins' if aid.startswith('pumpkin-') and aid!='pumpkin-shelf' else 'lanterns' if aid.startswith('lantern-') else 'planters' if aid.startswith('planter') or aid in ['hanging-basket','pumpkin-shelf'] else aid
 mask=mask_poly((W,H),points)
 if aid=='wreath':
  ImageDraw.Draw(mask).ellipse((959,369,1008,409),fill=0)
 if aid=='chair':
  d=ImageDraw.Draw(mask)
  for hole in [[(834,440),(842,443),(841,474),(832,472)],[(847,442),(854,444),(852,475),(846,474)],[(859,443),(866,444),(861,475),(856,475)]]:d.polygon(hole,fill=0)
 part(aid,stage,mask,offset=(0,-42) if aid=='lantern-post' else (0,0),item=item)
# Cat: remove an explicitly diagnosed pale neutral checkerboard, preserving warm fur.
cat=Image.open(RAW/'cat-cels-v1.png').convert('RGB');cp=cat.load();cm=Image.new('L',cat.size);mp=cm.load()
for y in range(cat.height):
 for x in range(cat.width):
  r,g,b=cp[x,y];neutral=max(r,g,b)-min(r,g,b)
  a=max(0,min(255,round((180-min(r,g,b))*12))) if neutral<35 else 255
  mp[x,y]=a
cat=cat.convert('RGBA');cat.putalpha(cm)
catframes=[]
for j in range(2):
 for i in range(3):
  f=OUT/f'cat-{j*3+i}.png';cat.crop((i*512,j*512,(i+1)*512,(j+1)*512)).save(f);catframes.append(f)
# Paws measured from source. Shared scale; shift only registration, never per-cel resize.
catinfo=compile_asset('cat-cels',catframes,[350,375],[380,520],columns=3,landmarks=[[356,376],[323,376],[324,376],[351,375],[322,375],[322,373]])
records.append({'id':'cat-cels','item':'cat','asset':catinfo,'source':'assets/source/cat-cels-v1.png','matte':'Pale neutral backdrop: alpha=clamp((180-minRGB)*12), chroma >=35 retained; original preserved.','paws':[[356,376],[323,376],[324,376],[351,375],[322,375],[322,373]]})
# Flame emission: black-is-transparent, preserve linear-looking premultiplied visual result.
fl=Image.open(RAW/'flame-cels-v1.png').convert('RGB');fw,fh=fl.size;flames=[]
for j in range(2):
 for i in range(4):
  cel=fl.crop((round(i*fw/4),round(j*fh/2),round((i+1)*fw/4),round((j+1)*fh/2))).convert('RGBA');a=Image.new('L',cel.size);px=cel.load();ap=a.load()
  for y in range(cel.height):
   for x in range(cel.width):
    rgb=px[x,y][:3];v=max(rgb);ap[x,y]=v if v>10 else 0
    if v: px[x,y]=tuple(round(c*255/v) for c in rgb)+(255,)
  cel.putalpha(a);f=OUT/f'flame-{j*4+i}.png';cel.save(f);flames.append(f)
flameinfo=compile_asset('flame-cels',flames,[fw/8,fh/2-68],[280,430],columns=4)
records.append({'id':'flame-cels','item':'lanterns','asset':flameinfo})
# Leaves use authored silhouette masks, excluding all generated dark halo.
leaves=Image.open(RAW/'leaf-cels-v1.png').convert('RGBA');leafpolys=[
 [(218,61),(266,122),(313,150),(374,111),(372,178),(427,168),(398,220),(450,262),(397,282),(422,327),(358,334),(368,380),(321,364),(305,400),(270,384),(260,415),(207,407),(183,432),(174,383),(144,381),(132,356),(93,363),(111,330),(73,309),(114,286),(149,275),(125,241),(145,211),(111,184),(139,167),(143,132),(176,151),(190,130),(203,156),(210,116)],
 [(190,71),(159,121),(142,179),(154,239),(188,277),(221,292),(236,307),(267,316),(283,339),(311,350),(344,358),(385,353),(419,325),(379,318),(402,287),(367,285),(367,254),(341,269),(317,240),(313,208),(288,227),(285,191),(267,209),(256,163),(235,191),(213,208),(204,182),(185,204),(177,171),(162,149)],
 [(237,43),(271,64),(297,105),(304,151),(331,186),(340,223),(338,263),(316,310),(287,354),(242,403),(211,411),(235,379),(244,347),(264,305),(272,278),(265,248),(256,224),(273,193),(279,158),(276,122),(263,86)],
 [(164,557),(195,593),(239,624),(302,595),(286,651),(330,639),(320,673),(383,650),(350,699),(414,717),(373,739),(404,775),(356,785),(358,825),(309,815),(292,844),(260,830),(242,872),(212,846),(190,891),(185,829),(153,825),(139,795),(110,788),(122,756),(80,752),(100,711),(77,690),(115,679),(110,645),(136,658),(129,613),(158,634)],
 [(181,552),(158,591),(148,641),(160,690),(184,721),(218,747),(246,766),(264,791),(292,801),(322,816),(356,817),(389,804),(410,780),(379,777),(391,750),(357,745),(347,718),(328,722),(313,696),(288,710),(282,680),(262,689),(240,647),(225,670),(208,643),(192,664),(187,630),(172,621)],
 [(263,563),(289,606),(330,627),(385,578),(384,640),(420,620),(401,676),(451,685),(406,715),(444,746),(398,770),(411,800),(365,812),(352,851),(320,830),(298,870),(275,855),(254,886),(226,858),(203,875),(193,838),(155,832),(151,801),(110,800),(124,771),(85,755),(122,727),(95,699),(139,695),(132,660),(170,675),(169,628),(205,659),(221,633),(231,659),(245,613)]
]
leaf_frames=[]
for n,points in enumerate(leafpolys):
 col=n%3;row=n//3
 # points use local X and source-global Y; first row also local Y.
 points=[(x+col*512,y) for x,y in points]
 m=mask_poly(leaves.size,points);im=leaves.copy();im.putalpha(m)
 f=OUT/f'leaf-{n}.png';im.crop((col*512,row*512,(col+1)*512,(row+1)*512)).save(f);leaf_frames.append(f)
leafinfo=compile_asset('leaf-cels',leaf_frames,[256,256],[400,460],columns=3);records.append({'id':'leaf-cels','item':'leaves','asset':leafinfo})
save(OUT/'preparation-manifest.json',{'format':'amberwatch-derivative-preparation','version':1,'script_sha256':h(__file__),'sources':{p.name:h(p) for p in RAW.glob('*.png')},'parts':records,'limits':'Authored source masks and deterministic keying. No aesthetic acceptance; exact scene proofs remain necessary.'})
print(json.dumps({'ok':True,'assets':len(records),'manifest':str(OUT/'preparation-manifest.json')}))
