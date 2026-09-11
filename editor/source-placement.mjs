// Coordinate authoring over the same matrices used by preview and export.
import {compileScene,validateScene,point,multiply,inverseMatrix,translation,wrapTime,sampleLayerMotion,sampleLayerAppearance} from './engine.mjs';
const finite=n=>typeof n==='number'&&Number.isFinite(n);
const pair=v=>Array.isArray(v)&&v.length===2&&v.every(finite);
const fields=(value,allowed,label)=>{if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).some(k=>!allowed.includes(k)))throw Error(`Invalid ${label} fields`);};
const cellSize=a=>a.atlas?[a.atlas.cell_width,a.atlas.cell_height]:[a.width,a.height];
const corners=s=>{const [x,y,w,h]=s.rect;return [[x,y],[x+w,y],[x+w,y+h],[x,y+h]].map(p=>point(s.matrix,...p));};
const referenceEqual=(a,b)=>a&&b&&a.sha256===b.sha256&&a.width===b.width&&a.height===b.height;
function referenceMapping(asset,reference,explicit){
  const dimensions=cellSize(asset);
  if(explicit){
    fields(explicit,['version','asset_sha256','cell_size','reference','reference_to_cell'],'explicit source mapping');
    if(explicit.version!==1||explicit.asset_sha256!==asset.sha256||!samePair(explicit.cell_size,dimensions)||!referenceEqual(explicit.reference,reference))throw Error(`Explicit mapping identity differs: ${asset.id}`);
    return affine(explicit.reference_to_cell,asset.id);
  }
  const map=asset.registration_mapping;
  if(!map||map.version!==1||!samePair(map.cell_size,dimensions)||map.cels?.length!==1)throw Error(`Asset needs one-cell compiler registration mapping or an explicit bound mapping: ${asset.id}`);
  if(referenceEqual(map.reference,reference))return affine(map.cels[0].reference_to_cell,asset.id);
  const source=map.input_sources?.[map.cels[0].source_index];
  if(referenceEqual(source,reference))return affine(map.cels[0].source_to_cell,asset.id);
  throw Error(`Asset mapping does not identify the selected reference: ${asset.id}`);
}
function samePair(a,b){return pair(a)&&a[0]===b[0]&&a[1]===b[1];}
function affine(value,label){
  if(!Array.isArray(value)||value.length!==6||!value.every(finite))throw Error(`Invalid source affine: ${label}`);
  inverseMatrix(value);return value;
}
function orthogonalGeometry(matrix,label){
  const sx=Math.hypot(matrix[0],matrix[1]),sy=Math.hypot(matrix[2],matrix[3]);
  const dot=matrix[0]*matrix[2]+matrix[1]*matrix[3],det=matrix[0]*matrix[3]-matrix[1]*matrix[2];
  if(!finite(sx)||!finite(sy)||sx<=0||sy<=0||det<=0||Math.abs(dot)>1e-9*sx*sy)throw Error(`Source mapping needs unsupported shear/reflection: ${label}`);
  return {sx,sy,rotation:Math.atan2(matrix[1],matrix[0])};
}
export function placeFromSource(scene,catalog,op){
  const allowed=['op','id','asset','base','mode','reference','mapping','base_mapping','source_anchor','source_size','anchor','order','values'];
  fields(op,allowed,'place_from_source');
  if(typeof op.id!=='string'||!op.id||scene.layers.some(l=>l.id===op.id))throw Error(`Invalid/duplicate placement layer: ${op.id}`);
  if(!['native','sprite'].includes(op.mode))throw Error('Placement mode must be native or sprite');
  const reference=op.reference;
  fields(reference,['file','sha256','width','height','path_base'],'reference');
  if(typeof reference.file!=='string'||!reference.file||!/^[a-f0-9]{64}$/.test(reference.sha256)||![reference.width,reference.height].every(n=>Number.isInteger(n)&&n>0))throw Error('Reference needs file, SHA-256 and positive integer dimensions');
  const base=scene.layers.find(l=>l.id===op.base),asset=catalog.assets.find(a=>a.id===op.asset);
  if(!base||!asset)throw Error('Placement needs an existing base layer and catalog asset');
  const baseAsset=catalog.assets.find(a=>a.id===base.asset);
  if((baseAsset.atlas?.frame_count||1)!==1)throw Error('Reference base must be a one-cell painted plane');
  const [bw,bh]=cellSize(baseAsset),[cw,ch]=cellSize(asset),B=referenceMapping(baseAsset,reference,op.base_mapping);
  const anchor=op.anchor||asset.pivot||[.5,.5];if(!pair(anchor)||anchor.some(n=>n<0||n>1))throw Error('Invalid placement anchor');
  let cellToReference,sourceAnchor;
  if(op.mode==='native'){
    if((asset.atlas?.frame_count||1)!==1)throw Error('Native placement currently supports one-cell cutouts; use explicit sprite size for a sequence');
    if(op.source_size!==undefined)throw Error('Native size is derived from registration, not source_size');
    cellToReference=inverseMatrix(referenceMapping(asset,reference,op.mapping));
    sourceAnchor=point(cellToReference,anchor[0]*cw,anchor[1]*ch);
    if(op.source_anchor!==undefined&&(!pair(op.source_anchor)||Math.hypot(op.source_anchor[0]-sourceAnchor[0],op.source_anchor[1]-sourceAnchor[1])>1e-7))throw Error('Native source_anchor conflicts with the recorded registration');
  }else{
    if(op.mapping!==undefined)throw Error('Sprite placement uses explicit intended size, not a native mapping');
    if(!pair(op.source_anchor)||!pair(op.source_size)||op.source_size.some(n=>n<=0))throw Error('Sprite placement needs source_anchor and positive full-cell source_size');
    sourceAnchor=op.source_anchor;
    cellToReference=[op.source_size[0]/cw,0,0,op.source_size[1]/ch,sourceAnchor[0]-anchor[0]*op.source_size[0],sourceAnchor[1]-anchor[1]*op.source_size[1]];
  }
  const W=scene.canvas.width,H=scene.canvas.height;
  const pixelsToLocal=[base.width*W/bw,0,0,base.height*H/bh,0,0];
  const mapping=multiply(pixelsToLocal,multiply(B,cellToReference)),geometry=orthogonalGeometry(mapping,op.id);
  const values=op.values||{};
  fields(values,['name','opacity','visible','blend','cycle_seconds','phase_frames','motion','tracks','track_loop'],'placement values');
  // Derived dimensions/placement remain inspectable ordinary scene fields.
  let code=2166136261;for(const c of op.id)code=Math.imul(code^c.charCodeAt(0),16777619);
  const socket=`src-${op.id.replace(/[^A-Za-z0-9_-]/g,'-').slice(0,22)}-${(code>>>0).toString(16).padStart(8,'0')}`;
  if(Object.hasOwn({...baseAsset.sockets,...base.sockets},socket))throw Error(`Placement socket already exists: ${socket}`);
  const uv=point(B,...sourceAnchor);base.sockets||={};base.sockets[socket]=[uv[0]/bw,uv[1]/bh];
  const layer={id:op.id,name:op.id,asset:asset.id,x:0,y:0,width:geometry.sx*cw/W,height:geometry.sy*ch/H,anchor,
    scale:1,rotation:geometry.rotation,opacity:1,visible:true,blend:'source-over',attach:{layer:base.id,socket},...values};
  if(asset.atlas){layer.cycle_seconds=values.cycle_seconds??scene.canvas.loop_seconds;layer.phase_frames=values.phase_frames??0;}
  if(op.order!==undefined){
    fields(op.order,['before','after'],'paint order');const keys=Object.keys(op.order);
    if(keys.length!==1)throw Error('Specify exactly one before/after paint-order target');
    const target=scene.layers.findIndex(l=>l.id===op.order[keys[0]]);if(target<0)throw Error('Unknown paint-order target');
    scene.layers.splice(target+(keys[0]==='after'?1:0),0,layer);
  }else scene.layers.push(layer);
  validateScene(scene,catalog);
  const state=compileScene(scene,catalog).sample(0).find(l=>l.id===layer.id);
  return {op:'place_from_source',layer:layer.id,mode:op.mode,base:base.id,source_anchor:sourceAnchor,full_cell_source_size:[Math.hypot(cellToReference[0],cellToReference[1])*cw,Math.hypot(cellToReference[2],cellToReference[3])*ch],
    authored_layer:structuredClone(layer),socket:{name:socket,uv:base.sockets[socket]},world_corners_at_zero:corners(state),inherited:{depth:state.depth,visible:state.visible,opacity:state.opacity},paint_index:scene.layers.indexOf(layer)};
}
export function reparentAtTime(scene,catalog,op){
  fields(op,['op','layer','to','socket','preserve','at_seconds'],'reparent');
  if(op.preserve!=='world_at_time'||!finite(op.at_seconds))throw Error('Reparent requires preserve=world_at_time and finite at_seconds');
  const layer=scene.layers.find(l=>l.id===op.layer);
  if(!layer||!scene.layers.some(l=>l.id===op.to))throw Error('Unknown child or parent layer');
  if(['x','y','scale','rotation'].some(k=>layer.tracks?.[k]))throw Error('Reparent cannot rebase child transform tracks; use an explicit authored-track revision');
  if(scene.bindings?.links.some(b=>b.target.layer===layer.id&&['x','y','scale','rotation','opacity'].includes(b.target.channel)))throw Error('Reparent cannot rebase bound child channels; author an explicit binding revision');
  const beforeLayer=structuredClone(layer),before=compileScene(scene,catalog).sample(op.at_seconds),old=before.find(s=>s.id===op.layer),parent=before.find(s=>s.id===op.to);
  if(!parent.socketLocal[op.socket])throw Error('Missing target socket');
  const parentMatrix=multiply(parent.matrix,translation(...parent.socketLocal[op.socket]));
  const local=multiply(inverseMatrix(parentMatrix),old.matrix),geometry=orthogonalGeometry(local,layer.id);
  if(Math.abs(geometry.sx-geometry.sy)>1e-9*Math.max(geometry.sx,geometry.sy))throw Error('Reparent needs unsupported nonuniform matrix scale');
  const t=wrapTime(op.at_seconds,scene.canvas.loop_seconds),motion=sampleLayerMotion(layer,t,scene.canvas.loop_seconds),appearance=sampleLayerAppearance(layer,t);
  layer.x=local[4]/scene.canvas.width-motion.x;layer.y=local[5]/scene.canvas.height-motion.y;
  layer.rotation=geometry.rotation-motion.rotation;layer.scale=geometry.sx;
  if(old.visible&&!parent.visible)throw Error(`Cannot preserve visible child under hidden parent: ${parent.id}`);
  const visible=parent.visible?old.visible:appearance.visible;
  if(layer.tracks?.visible&&visible!==appearance.visible)throw Error('Preserving visibility would rewrite the child visibility track');
  if(!layer.tracks?.visible)layer.visible=visible;
  if(parent.opacity===0&&old.opacity!==0)throw Error(`Cannot preserve nonzero opacity under zero-opacity parent: ${parent.id}`);
  const opacity=parent.opacity===0?appearance.opacity:old.opacity/parent.opacity;
  if(opacity<0||opacity>1)throw Error(`Cannot preserve opacity without an out-of-range child opacity under parent: ${parent.id}`);
  if(layer.tracks?.opacity&&Math.abs(opacity-appearance.opacity)>1e-10)throw Error('Preserving opacity would rewrite the child opacity track');
  if(!layer.tracks?.opacity)layer.opacity=opacity;
  layer.attach={layer:op.to,socket:op.socket};delete layer.depth;delete layer.group;
  validateScene(scene,catalog);
  const after=compileScene(scene,catalog).sample(op.at_seconds).find(s=>s.id===op.layer),a=corners(old),b=corners(after);
  const error=Math.max(...a.map((p,i)=>Math.hypot(p[0]-b[i][0],p[1]-b[i][1])));
  if(error>1e-7||old.visible!==after.visible||Math.abs(old.opacity-after.opacity)>1e-10)throw Error('Reparent reference-pose preservation failed numeric verification');
  return {op:'reparent',layer:layer.id,preserve:op.preserve,at_seconds:op.at_seconds,max_world_corner_error_pixels:error,
    before:{matrix:old.matrix,corners:a,depth:old.depth,visible:old.visible,opacity:old.opacity},
    after:{matrix:after.matrix,corners:b,depth:after.depth,visible:after.visible,opacity:after.opacity},
    changed_fields:Object.fromEntries([...new Set([...Object.keys(beforeLayer),...Object.keys(layer)])].filter(k=>JSON.stringify(beforeLayer[k])!==JSON.stringify(layer[k])).map(k=>[k,{before:beforeLayer[k]??null,after:layer[k]??null}])),
    motion_interpretation:'Existing sinusoidal motion remains in the new parent-local axes; future world trajectory is not preserved.',paint_index:scene.layers.indexOf(layer)};
}
