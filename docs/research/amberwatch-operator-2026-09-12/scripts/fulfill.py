import json,hashlib,subprocess,sys
from pathlib import Path
P=Path(__file__).resolve().parents[1];ROOT=P.parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def file(path):return {'file':path,'sha256':sha(P/path)}
def run(*args):
 r=subprocess.run([str(ROOT/'ambiance'),'--project',str(P),*map(str,args)],capture_output=True,text=True);j=json.loads(r.stdout)
 if r.returncode:raise RuntimeError(str(j)[:2000])
 return j
scene=json.loads((P/'scene/scene.json').read_text());layers={l['id']:l for l in scene['layers']};cat={a['id']:a for a in json.loads((P/'assets/catalog.json').read_text())['assets']};inventory=json.loads((P/'plans/asset-inventory.json').read_text());parts=[]
def placed(item,part,lid,extra=[]):
 a=cat[layers[lid]['asset']];parts.append({'item':item,'part':part,'values':{'stage':'placed','files':[file(a['file']),*[file(f) for f in extra]],'asset_id':a['id'],'layer_ids':[lid]}})
def prepared(item,part,paths):parts.append({'item':item,'part':part,'values':{'stage':'prepared','files':[file(p) for p in paths]}})
placed('sky','surface','sky');placed('sky','cloud-cels','cloud-veil',['plans/assembly-v1.json'])
placed('valley','surface','valley');placed('cottage','structure','cottage');placed('cottage','backing','valley',['assets/source/environment-backing-v1.png'])
placed('path','surface','path');placed('path','light-receivers','pumpkin-left-stones-path-paint',['assets/derivatives/v4/lighting-receipt.json'])
placed('tree','trunk-canopy','tree');placed('fences','left','fence-left');placed('fences','right','fence-right')
placed('cat','whole-character-cels','cat',['assets/source/cat-cels-v1.png','assets/production/cat-cels/report.json'])
prepared('cat','clean-surroundings',['assets/source/structure-clean-v2.png','render/whole-object-v4/samples/cat-hidden/context.png'])
prepared('cat','contact-proof',['render/whole-object-v4/render-report.json','render/whole-object-v4/samples/cat-look/regions/cat-contact.png','render/whole-object-v4/samples/cat-isolated/context.png'])
placed('chair','whole-chair','chair')
placed('planters','whole-planters','planter-left',[cat[layers[l]['asset']]['file'] for l in ['planter-right','hanging-basket','pumpkin-shelf']])
placed('wreath','whole-wreath','wreath')
placed('pumpkins','whole-shells','pumpkin-left',[cat[layers[l]['asset']]['file'] for l in ['pumpkin-right','pumpkin-step','pumpkin-near']])
placed('pumpkins','emissive-masks','pumpkin-left-emission',[cat[layers[l]['asset']]['file'] for l in ['pumpkin-right-emission','pumpkin-step-emission','pumpkin-near-emission']])
prepared('pumpkins','receiver-proof',['render/whole-object-v4/render-report.json','render/paired-motion-v4b/render-report.json','assets/derivatives/v4/lighting-receipt.json'])
placed('lanterns','whole-fixtures','lantern-left',[cat[layers[l]['asset']]['file'] for l in ['lantern-step','lantern-step-low','lantern-right-low','lantern-post','sconce-0','sconce-1','sconce-2']])
placed('lanterns','flame-cels','lantern-left-flame',['assets/source/flame-cels-v1.png'])
placed('lanterns','receiver-masks','lantern-left-receiver-path-paint',['assets/derivatives/v4/lighting-receipt.json'])
placed('leaves','tumbling-cels','leaf-0',['assets/source/leaf-cels-v1.png'])
prepared('leaves','routes',['plans/assembly-v1.json','plans/refine-v2.json','plans/leaf-readability-v5.json','reports/r2-activity/activity-report.json'])
prepared('sound','source-selection',['audio/session.json','audio/effects-session.json','audio/sources/last-lantern/generation-log.json'])
prepared('sound','score-master',['audio/runs/score-v1/mix/master.wav','audio/runs/score-v1/report.json'])
prepared('sound','effects-master',['audio/runs/effects-v1/mix/master.wav','audio/runs/effects-v1/report.json'])
for view in ['portrait','landscape']:prepared('delivery',view+'-composition',['render/r2-'+view+'-proof/render-report.json','render/r2-'+view+'-proof/frame.png'])
if len(sys.argv)>1:
 delivery=json.loads((P/'deliveries'/ (sys.argv[1]+'.json')).read_text());prepared('delivery','paired-movies',[str((P/'deliveries'/(sys.argv[1]+'.json')).relative_to(P))])
out=P/'plans'/('fulfillment-delivery.json' if len(sys.argv)>1 else 'fulfillment-art-v4.json');out.write_text(json.dumps({'format':'ambiance-fulfillment','schema_version':1,'parts':parts},indent=2)+'\n')
r=run('plan','fulfill',out,'--expect-sha256',sha(P/'plans/asset-inventory.json'));print(json.dumps({'ok':r['ok'],'fulfilled_parts':len(parts)}))
