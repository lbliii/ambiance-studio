// Transport ordinary model layers into a host scene. The engine remains the
// authority for transforms, sockets, channel writers and visibility inheritance.
import {createHash} from 'node:crypto';
import {isDeepStrictEqual} from 'node:util';
import {compileScene,validateScene,multiply,translation,rotation,scaling,point} from '../../editor/engine.mjs';
import {reparentAtTime} from '../../editor/source-placement.mjs';

const id=(kind,tuple)=>kind+'-'+createHash('sha256').update(JSON.stringify(tuple)).digest('hex');
const finite=n=>typeof n==='number'&&Number.isFinite(n);
const pair=v=>Array.isArray(v)&&v.length===2&&v.every(finite);
const fields=(o,keys,name)=>{if(!o||typeof o!=='object'||Array.isArray(o)||Object.keys(o).some(k=>!keys.includes(k)))throw Error('Invalid '+name+' fields');};

export function placeInstance(scene,catalog,args) {
  const {instance_id:instanceId,resolved,pin,placement,mount,order,previous}=args;
  if(resolved.clock?.mode!=='static'||resolved.scene.layers.some(l=>l.motion||Object.keys(l.tracks??{}).some(k=>k!=='cell')||l.tracks?.cell?.keys.some(k=>k[1]!==l.tracks.cell.keys[0][1])))throw Error('Instance transport supports static model states only; animated retiming is unsupported');
  fields(placement,['position','scale','rotation','depth'],'instance placement');
  if(!pair(placement.position)||!finite(placement.scale)||placement.scale<=0||!finite(placement.rotation)||!finite(placement.depth))throw Error('Invalid instance placement');
  const originalIds=new Set(previous?.mapping.map(r=>r.layer_id)??[]);
  const oldIndex=scene.layers.findIndex(l=>originalIds.has(l.id));
  if(previous) {
    scene.layers=scene.layers.filter(l=>!originalIds.has(l.id));
    const signals=new Set(previous.relationships.signals),links=new Set(previous.relationships.bindings);
    if(scene.finishing)scene.finishing.signals=scene.finishing.signals.filter(s=>!signals.has(s.id));
    if(scene.bindings)scene.bindings.links=scene.bindings.links.filter(b=>!links.has(b.id));
  }
  const layerIds=new Map(resolved.mapping.map(r=>[r.layer_id,id('mi-leaf',[instanceId,r.part_path])]));
  const socketId=s=>id('mi-socket',[instanceId,s]);
  const mapping=resolved.mapping.map(row=>({...row,layer_id:layerIds.get(row.layer_id),
    asset_id:id('mi-art',[pin.sha256,row.part_path,row.drawing_id])}));
  const assets=resolved.catalog.assets.map((a,i)=>({...structuredClone(a),id:mapping[i].asset_id,
    file:args.package_source+'/'+a.file,provenance:{...a.provenance,recipe:args.package_source+'/'+a.provenance.recipe}}));
  for(const asset of assets) {
    const existing=catalog.assets.find(a=>a.id===asset.id);
    if(existing&&!isDeepStrictEqual(existing,asset))throw Error('Managed asset identity collision');
    if(!existing)catalog.assets.push(asset);
  }
  const W=scene.canvas.width,H=scene.canvas.height,w=resolved.scene.canvas.width,h=resolved.scene.canvas.height;
  const localToScene=multiply(multiply(multiply(translation(...placement.position),rotation(placement.rotation)),scaling(placement.scale)),translation(-args.pivot[0],-args.pivot[1]));
  const layers=resolved.scene.layers.map((source,i)=>{
    const l=structuredClone(source);l.id=layerIds.get(source.id);l.asset=assets[i].id;
    if(scene.layers.some(row=>row.id===l.id))throw Error('Occupied instance layer identity');
    l.name=instanceId+' / '+source.name;
    l.x*=w/W;l.y*=h/H;l.width*=w/W;l.height*=h/H;
    // The source proof is explicitly static. Hold the registered cel across
    // the host duration; source proof fps/duration never become host timing.
    l.cycle_seconds=scene.canvas.loop_seconds;
    l.tracks.cell.keys=[[0,mapping[i].cel_index],[scene.canvas.loop_seconds,mapping[i].cel_index]];
    l.sockets=Object.fromEntries(Object.entries(l.sockets).map(([s,uv])=>[socketId(s),uv]));
    if(l.attach)l.attach={layer:layerIds.get(l.attach.layer),socket:socketId(l.attach.socket)};
    else {const p=point(localToScene,l.x*W,l.y*H);l.x=p[0]/W;l.y=p[1]/H;l.scale*=placement.scale;l.rotation+=placement.rotation;l.depth=placement.depth;}
    return l;
  });
  const root=layers.find(l=>!l.attach);
  let index=previous?oldIndex:scene.layers.length;
  if(order!==undefined) {
    fields(order,['before','after'],'instance paint order');
    const keys=Object.keys(order);if(keys.length!==1)throw Error('Order needs one before/after target');
    const target=scene.layers.findIndex(l=>l.id===order[keys[0]]);if(target<0)throw Error('Unknown paint order target');
    index=target+(keys[0]==='after'?1:0);
    // One contiguous block per instance; do not insert inside another block.
    for(const record of scene.model_instances?.instances??[]) {
      if(record.instance_id===instanceId)continue;
      const positions=record.mapping.map(r=>scene.layers.findIndex(l=>l.id===r.layer_id));
      if(index>Math.min(...positions)&&index<=Math.max(...positions))throw Error('Paint order would split an instance block');
    }
  }
  scene.layers.splice(index,0,...layers);
  let mountProof=null;
  if(mount!==null) {
    fields(mount,['layer','socket','at_seconds'],'instance mount');
    if(!finite(mount.at_seconds))throw Error('Mount needs finite at_seconds');
    // Preserve the placed pose; no alternate affine decomposition/evaluator.
    mountProof=reparentAtTime(scene,catalog,{op:'reparent',layer:root.id,to:mount.layer,socket:mount.socket,preserve:'world_at_time',at_seconds:mount.at_seconds});
  }
  const relationships={signals:[],bindings:[],receivers:[]};
  for(const contact of args.receivers) {
    fields(contact,['id','source_part_path','illumination','values','valid_bounds'],'receiver contact');
    const member=mapping.find(m=>JSON.stringify(m.part_path)===JSON.stringify(contact.source_part_path));
    const illumination=scene.finishing?.illuminations.find(i=>i.id===contact.illumination);
    if(!member||!illumination)throw Error('Receiver contact needs an owned source and existing illumination');
    const bounds=contact.valid_bounds;
    if(!Array.isArray(bounds)||bounds.length!==4||!bounds.every(finite)||bounds[0]>bounds[2]||bounds[1]>bounds[3])throw Error('Receiver needs explicit valid_bounds in host pixels');
    const compiled=compileScene(scene,catalog),frames=compiled.clock.duration_frames;
    if(frames>100000)throw Error('Receiver envelope check supports at most 100000 output frames');
    for(const time of [compiled.clock.seconds(mount?.at_seconds??0),...Array.from({length:frames},(_,i)=>compiled.clock.frame(i))]) {
      const frame=compiled.sample(time).find(s=>s.id===root.id),position=point(frame.matrix,0,0);
      if(position[0]<bounds[0]||position[1]<bounds[1]||position[0]>bounds[2]||position[1]>bounds[3])throw Error('Source outside receiver valid_bounds; reauthor the contact before moving');
    }
    const asset=catalog.assets.find(a=>a.id===member.asset_id);
    if(!Array.isArray(contact.values)||contact.values.length!==(asset.atlas?.frame_count??1)||!contact.values.every(v=>finite(v)&&v>=0&&v<=1))throw Error('Receiver values must match source cels in [0,1]');
    const signal=id('mi-signal',[instanceId,contact.id]),binding=id('mi-binding',[instanceId,contact.id]);
    if(scene.finishing.signals.some(s=>s.id===signal)||scene.bindings?.links.some(b=>b.id===binding))throw Error('Receiver relationship identity collision');
    scene.finishing.signals.push({id:signal,layer:member.layer_id,values:contact.values});
    scene.bindings??={version:1,links:[]};
    scene.bindings.links.push({id:binding,source:{signal,range:[0,1]},target:{layer:illumination.layer,channel:'opacity',range:[0,1]},map:{interpolation:'linear',keys:[[0,0],[1,1]]},off:0});
    relationships.signals.push(signal);relationships.bindings.push(binding);
    relationships.receivers.push({id:contact.id,illumination:illumination.id,layer:illumination.layer,receiver:illumination.receiver,source_layer:member.layer_id,valid_bounds:bounds});
  }
  validateScene(scene,catalog);
  const states=compileScene(scene,catalog).sample(mount?.at_seconds??0);
  return {scene,catalog,mapping,root_layer:root.id,relationships,mount_proof:mountProof,
    sockets:args.sockets.map(s=>({...s,layer_id:layerIds.get(s.layer_id),runtime_socket:socketId(s.runtime_socket)})),
    selected_leaves:states.filter(s=>mapping.some(m=>m.layer_id===s.id)&&s.visible&&s.opacity>0).map(s=>s.id)};
}
