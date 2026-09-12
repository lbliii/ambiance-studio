import json,hashlib,subprocess,math
from pathlib import Path
from PIL import Image
P=Path(__file__).resolve().parents[1];ROOT=P.parents[1]
def save(p,d):Path(p).parent.mkdir(parents=True,exist_ok=True);Path(p).write_text(json.dumps(d,indent=2)+'\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return {'file':str(Path(p).relative_to(P)),'sha256':sha(p)}
def cli(*args,allow=False):
 r=subprocess.run([str(ROOT/'ambiance'),'--project',str(P),*map(str,args)],capture_output=True,text=True);d=json.loads(r.stdout)
 if r.returncode and not allow:raise RuntimeError(str(d)[:2200])
 return d
s=json.loads((P/'scene/scene.json').read_text());layers=s['layers'];catalog=json.loads((P/'assets/catalog.json').read_text());assets={a['id']:a for a in catalog['assets']}
# Explicit elliptical feather mask for bounded local light responses.
d=P/'assets/derivatives/v3';d.mkdir(parents=True,exist_ok=True);m=Image.new('RGBA',(256,128));px=m.load()
for y in range(128):
 for x in range(256):
  radius=math.sqrt(((x-127.5)/127.5)**2+((y-63.5)/63.5)**2);a=round(255*max(0,min(1,(1-radius)/.4)))
  px[x,y]=(255,255,255,a)
m.save(d/'receiver-falloff.png')
recipe={'version':1,'id':'receiver-falloff','input':{'frames':['../derivatives/v3/receiver-falloff.png']},'registration':{'mode':'fixed','point':[128,64],'target':[.5,.5]},'output':{'cell_size':[260,132],'columns':1,'padding':2}}
save(P/'assets/recipes/receiver-falloff.json',recipe);cli('asset','build',P/'assets/recipes/receiver-falloff.json','--out',P/'assets/production/receiver-falloff');cli('asset','admit',P/'assets/production/receiver-falloff')
for light in s['finishing']['lights']:light['mask_asset']='receiver-falloff'
save(P/'plans/receiver-masks-v3.json',{'version':1,'operations':[{'op':'finishing','value':s['finishing']}]});cli('scene','apply',P/'plans/receiver-masks-v3.json')
s=json.loads((P/'scene/scene.json').read_text());layers=s['layers']
groups={'sky':['sky','cloud-veil'],'valley':['valley'],'cottage':['cottage'],'path':['path'],'tree':['tree'],'fences':['fence-left','fence-right'],'cat':['cat'],'chair':['chair'],'planters':['planter-left','planter-right','hanging-basket','pumpkin-shelf'],'wreath':['wreath'],'pumpkins':[l['id'] for l in layers if l['id'].startswith('pumpkin-') and l['id']!='pumpkin-shelf'],'lanterns':[l['id'] for l in layers if l['id'].startswith('lantern-') or l['id'].startswith('sconce-')],'leaves':[l['id'] for l in layers if l['id'].startswith('leaf-')],'sound':[],'delivery':[]}
planpath=P/'plans/production-plan.json';plan=json.loads(planpath.read_text());oldsha=sha(planpath)
for e in plan['elements']:
 e['realization']['layer_ids']=groups[e['id']]
 # Sound is authored in its own PCM session, not a visual scene action.
 if e['id']=='sound':e['cadence']='still';e['purpose']+=' Continuous soundtrack exists in the separately captured PCM session; still here describes the absence of a visual layer.'
for a in plan['actions']:
 a['layer_ids']=['cloud-veil'] if a['id']=='cloud-drift' else ['cat'] if a['id']=='leaf-watch' else [l for l in groups[a['element_id']] if l.endswith('-emission') or l.endswith('-flame')] if a['element_id'] in ['pumpkins','lanterns'] else groups[a['element_id']]
plan['relations']=[{'id':'pumpkin-to-stones','kind':'receiver','source_element':'pumpkins','target_element':'path','scene_ref':'light:pumpkin-left-stones','dependencies':[]},{'id':'lantern-to-stones','kind':'receiver','source_element':'lanterns','target_element':'path','scene_ref':'light:lantern-left-receiver','dependencies':[]}]
for e in plan['expectations']:
 if e['id']=='light-review':e['relation_ids']=['pumpkin-to-stones','lantern-to-stones']
plan['change']={'reason':'Bind completed production layers, exact action layers and local light receivers. Sound remains a separate PCM runtime; no visual sound layer is invented.','supersedes_sha256':oldsha}
save(P/'plans/bound-plan-v3.json',plan);cli('plan','spec','apply',P/'plans/bound-plan-v3.json','--expect-sha256',oldsha)
# Whole-object proof matrix covers real assembled stage with seed and composition absent.
samples=[{'id':'production-only','label':'Production layers only; no seed or whole-scene fallback exists','time':0},{'id':'cat-look','time':3.6},{'id':'cat-blink','time':9.1}]
for obj in ['cat','cottage','chair','pumpkins','lanterns','planters','wreath','tree','fences']:
 owned=groups[obj]
 samples.append({'id':obj+'-hidden','time':0,'overrides':{lid:{'visible':False} for lid in owned}})
 samples.append({'id':obj+'-isolated','time':0,'overrides':{l['id']:{'visible':False} for l in layers if l['id'] not in owned}})
proof={'version':1,'title':'Amberwatch complete object ownership and contact inspection','inventory':'plans/asset-inventory.json','part_ids':['cat','cottage','chair','pumpkins','lanterns','planters','wreath','tree','fences'],'samples':samples,'regions':[{'id':'portrait','rect':[531/1448,0,610.875/1448,1]},{'id':'landscape','rect':[0,30/1086,1,814.5/1086]},{'id':'cat-contact','rect':[.405,.30,.10,.18]}],'comparisons':[{'id':'cat-reveal','left':'production-only','right':'cat-hidden','difference':True},{'id':'cat-extreme','left':'production-only','right':'cat-look','difference':True},{'id':'house-backing','left':'production-only','right':'cottage-hidden','difference':True}]}
save(P/'plans/whole-object-proof-v3.json',proof)
save(P/'plans/layer-plan.json',{'version':1,'canonical_intent':'plans/production-plan.json','stage':[1448,1086],'groups':groups,'art_sources':'assets/source','prepared_manifest':'assets/derivatives/v1/preparation-manifest.json','assembly_manifest':'assets/derivatives/v2/assembly-assets.json','camera':'Fixed','contacts':{'cat':'Paw anchor [676,452] on railing; shared cel scale, source paw landmarks in compiler recipe.'},'backing':'Generated clean architecture plus independent sky, valley and ground reconstructed behind objects.','proof':'plans/whole-object-proof-v3.json'})
print(json.dumps({'ok':True,'groups':len(groups),'proof_samples':len(samples)}))
