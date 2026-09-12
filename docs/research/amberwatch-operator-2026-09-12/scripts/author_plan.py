"""Author Amberwatch's initial scope; does not claim production or review completion."""
import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parents[1]
def save(path,data):
    (P/path).parent.mkdir(parents=True,exist_ok=True)
    (P/path).write_text(json.dumps(data,indent=2)+'\n')
def digest(path):return hashlib.sha256((P/path).read_bytes()).hexdigest()
rows=[
 ('sky','environment','far-background','ambient','continuous',1,'Clouded dusk gives cool contrast; cloud veils drift slowly above the stationary valley.','painted-effect',['surface','cloud-cels']),
 ('valley','environment','background','stable','still',0,'Pines, mountains, lake and small remote settlement establish distance. Water receives a subdued shifting reflection.','cutout',['surface']),
 ('cottage','structure','midground','stable','still',0,'Heavy timber house, chimney, roof, porch posts, windows, door and stairs provide shelter. House windows stay steady.','cutout',['structure','backing']),
 ('path','environment','foreground','stable','still',0,'Stone path, boulders, leaf litter and low rooted shrubs guide the eye to the door and receive lantern light.','cutout',['surface','light-receivers']),
 ('tree','environment','near-foreground','stable','still',0,'The old trunk and heavy overhead branches frame the valley; scattered detached leaves reveal the breeze.','cutout',['trunk-canopy']),
 ('fences','structure','near-foreground','stable','still',0,'Edge posts, rails and iron hanging hook frame the approach and remain weighty.','cutout',['left','right']),
 ('cat','character','midground','primary','recurring',3,'The whole perched black cat tracks a leaf, blinks and curls its hanging tail, with paws fixed on the railing.','rig',['whole-character-cels','clean-surroundings','contact-proof']),
 ('chair','prop','midground','stable','still',0,'Empty rocking chair and folded blanket suggest someone has just gone indoors. No unsupported rocking.','cutout',['whole-chair']),
 ('planters','prop','foreground','stable','still',0,'Potted rusty chrysanthemums, hanging basket and tucked pumpkin shelf provide seasonal abundance.','cutout',['whole-planters']),
 ('wreath','prop','midground','stable','still',0,'The complete wreath centers the welcoming door; its mounting remains fixed.','cutout',['whole-wreath']),
 ('pumpkins','prop','foreground','supporting','continuous',2,'Four complete carved pumpkins hold separate candles; their shells stay fixed as warm cut faces and nearby stones respond.','rig',['whole-shells','emissive-masks','receiver-proof']),
 ('lanterns','prop','foreground','supporting','continuous',2,'Five portable candle lanterns and three fixed wall sconces enclose changing flame shapes. Portable fixtures retain separate ownership.','rig',['whole-fixtures','flame-cels','receiver-masks']),
 ('leaves','effect','foreground','supporting','continuous',2,'An autumn breeze carries a sparse staggered fall of painted maple leaves across near path and porch; one pass motivates the cat.','painted-effect',['tumbling-cels','routes']),
 ('sound','effect','midground','ambient','continuous',1,'Listener stands on the path. Soft outdoor air and dry foliage underpin a sparse warm nocturne with space between notes.','painted-effect',['source-selection','score-master','effects-master']),
 ('delivery','effect','foreground','stable','still',0,'Review both requested compositions and expose exact selected movies.','baked',['portrait-composition','landscape-composition','paired-movies'])]
views=['portrait','landscape'];elements=[];items=[];actions=[];exps=[]
for eid,kind,depth,role,cadence,level,purpose,method,parts in rows:
    pr=[{'item_id':eid,'part_id':part} for part in parts]
    elements.append(dict(id=eid,kind=kind,depth_band=depth,motion_role=role,cadence=cadence,readability_target=level,origin='proposed' if eid in ['leaves','sound','delivery'] else 'observed',purpose=purpose,source_ids=['seed'],action_ids=[],realization={'method':method,'inventory_parts':pr,'layer_ids':[]},required_art=[{'id':eid+'-'+part,'role':'backing' if 'backing' in part or 'surroundings' in part else 'mask' if 'mask' in part or 'receiver' in part else 'source' if eid in ['sound','delivery'] else 'cutout','purpose':purpose,'inventory_part':ref} for part,ref in zip(parts,pr)]))
    items.append({'id':eid,'name':eid.title(),'required':True,'state':'planned','priority':'next' if eid in ['cat','cottage','delivery'] else 'prepare-with-flame','method':method,'required_parts':[{'id':part,'description':part,'stage':'planned','target_stage':'prepared' if 'proof' in part or eid in ['sound','delivery'] or part in ['routes','clean-surroundings'] else 'placed','review':{'state':'pending'}} for part in parts],'dependencies':[],'next_action':purpose})
for eid,aid,description,level in [
 ('cat','leaf-watch','At 3–6 seconds a near leaf passes; cat looks up, returns, then blinks at 9 seconds. Tail changes drawing with planted paws.',3),
 ('sky','cloud-drift','Slow periodic opacity exchange and modest travel of painted cloud veil, without moving mountains.',1),
 ('pumpkins','pumpkin-light','Independent bounded combustion signals animate cut faces and their local stone receivers together.',2),
 ('lanterns','candle-flames','Changing registered flame drawings have differing phases; nearby light follows the source signal.',2),
 ('leaves','leaf-fall','Staggered diagonal wind routes with tumbling drawings; hide each leaf outside its visible journey before resetting.',2)]:
    next(e for e in elements if e['id']==eid)['action_ids'].append(aid)
    actions.append({'id':aid,'element_id':eid,'description':description,'method':'painted cels, deterministic tracks and bounded source signals as appropriate','targets':[{'view_id':v,'readability_target':level} for v in views],'timing':{'onset_max_seconds':4,'duration_min_seconds':1,'rest_max_seconds':8}})
def exp(eid,stage,check,targets,acts,direction):
    typ='structural' if check in ['view','art','independent-control','relation'] else 'measured' if check in ['raster','movie','activity'] else 'observed'
    exps.append({'id':eid,'rationale':direction,'direction':direction,'stage':stage,'view_ids':views,'element_ids':targets,'action_ids':acts,'relation_ids':[],'requirement':{'type':typ,'check':check}})
exp('dual-framing','layout','view',['cat','cottage','path'],[],'Portrait and landscape fill frame with useful cat size, visible doorway and warm path. Reposition right hanging lantern upward to avoid lower landscape cut.')
exp('composition-pixels','layout','raster',['cat','cottage','path'],[],'Save actual painted blocking proof for each output.')
exp('composition-review','layout','composition',['cat','cottage','path'],[],'Inspect both whole compositions at normal display size.')
exp('independent-art','assets','art',[e['id'] for e in elements if e['id'] not in ['delivery','sound']],[],'Complete independent characters, meaningful props and depth surfaces with clean backing and preserved source recipes.')
exp('whole-object-controls','assets','independent-control',['cat','cottage','chair','pumpkins','lanterns','planters','wreath','tree','fences'],[],'Show production-only scene, whole-object isolation/removal, and cat contact/extreme poses; no seed fallback.')
for a in actions:exp(a['id']+'-readability','animation','readability',[a['element_id']],[a['id']],a['description'])
exp('light-review','animation','lighting',['pumpkins','lanterns','path'],[],'Fixtures remain still; source and local receivers respond together without global exposure pumping.')
exp('review-movies','export','movie',['delivery'],[],'Encode portrait 1080×1920 and landscape 1920×1080, with score and effects options, complete short cycles.')
plan={'format':'ambiance-production-plan','schema_version':1,'story':{'premise':'A watchful black cat keeps company with the last warm lights of an autumn evening.','direction':'Amberwatch: inviting painted Halloween porch; 16-second picture, compact 48-second soundtrack; dual full-frame formats; fixed camera, expressive cat and drifting leaves, living combustion and stable architecture.'},'sources':[{'id':'seed','path':'inputs/reference.png','sha256':digest('inputs/reference.png')},{'id':'staging','path':'assets/source/stage-composition-v1.png','sha256':digest('assets/source/stage-composition-v1.png')}],'elements':elements,'actions':actions,'outputs':[{'view_id':v,'roles':['score','effects']} for v in views],'relations':[],'expectations':exps,'change':{'reason':'Initial whole-scene scope from the user seed and go-forth instruction.','supersedes_sha256':digest('plans/production-plan.json') if (P/'plans/production-plan.json').exists() else None}}
save('plans/initial-plan-proposal.json',plan);save('plans/asset-inventory.json',{'version':1,'reference':{'file':'inputs/reference.png','sha256':digest('inputs/reference.png')},'items':items})
