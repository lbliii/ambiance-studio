// Model-local construction adapter. Evaluation and mount preservation stay in the engine.
import {createHash} from 'node:crypto';
import {compileScene, multiply, inverseMatrix, point} from '../../editor/engine.mjs';
import {reparentAtTime} from '../../editor/source-placement.mjs';
const key = value => JSON.stringify(value);
const near = (a,b) => a.length===b.length && a.every((v,i)=>Math.abs(v-b[i])<1e-7);
const identity = [1,0,0,1,0,0];
const id = (kind, tuple) => kind+'-'+createHash('sha256').update(key(tuple)).digest('hex');
const fields = (o, names, label) => {if(!o||typeof o!=='object'||Array.isArray(o)||Object.keys(o).some(k=>!names.includes(k)))throw Error('Unsupported '+label+' fields');};
function transform(m) {
  const s=Math.hypot(m[0],m[1]);
  if(!Number.isFinite(s)||s<=0||!near([m[2],m[3]],[-m[1],m[0]]))throw Error('Unsupported model transform');
  return {scale:s,rotation:Math.atan2(m[1],m[0])};
}
function checkedValue(c,v) {
  if(c.type==='boolean' ? typeof v!=='boolean' : c.type==='number' ? !Number.isFinite(v)||v<c.min||v>c.max : c.type==='drawing' ? !c.drawings.includes(v) : true)throw Error('Invalid control value: '+c.control_id);
  return v;
}
export function lower(request, state={schema_version:1,pose_id:'rest',controls:[],variants:[]}) {
  fields(state,['schema_version','pose_id','controls','variants'],'model state');
  if(state.schema_version!==1||typeof state.pose_id!=='string'||!/^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$/.test(state.pose_id))throw Error('Invalid static pose identity');
  const models=new Map(),leaves=new Map(),slots=new Map(),sockets=new Map(),controls=new Map(),sets=new Map(),runtimeIds=new Map();
  const rootModel=request.models[request.root];
  const namespace = ['model-local',rootModel.model_id];
  function runtime(kind,tuple) {const value=id(kind,[namespace,tuple]);if(runtimeIds.has(value)&&runtimeIds.get(value)!==key(tuple))throw Error('Runtime identity collision');runtimeIds.set(value,key(tuple));return value;}
  function expand(file,prefix,outer) {
    const def=request.models[file];if(!def)throw Error('Missing model');
    models.set(key(prefix),{def,prefix,outer});
    const localLeaves=[];
    for(const p of def.parts) {
      const full=[...prefix,p.part_id];
      if(p._model){const before=new Set(leaves.keys());expand(p._model,full,multiply(outer,p.local_to_parent));const nested=request.models[p._model];slots.set(key(full),[...full,nested.root_part_id]);const root=leaves.get(key(slots.get(key(full))));root.mount={prefix,mount:p.mount};for(const [k,l]of leaves)if(!before.has(k))localLeaves.push(l.path);}
      else {const leaf={path:full,p,def,prefix,outer,drawing_id:p.drawing_id,matrix:multiply(outer,p.cell_to_local),mount:p.mount?{prefix,mount:p.mount}:null};leaves.set(key(full),leaf);localLeaves.push(full);}
    }
    const order=def.paint_order.map(p=>key([...prefix,...p]));
    if(order.length!==localLeaves.length||new Set(order).size!==order.length||localLeaves.some(p=>!order.includes(key(p))))throw Error('Paint order must list every owned drawing leaf exactly once');
    for(const c of def.controls??[])controls.set(key([prefix,c.control_id]),{...c,prefix});
    for(const s of def.variant_sets??[])sets.set(key([prefix,s.variant_set_id]),{...s,prefix});
    for(const socket of def.sockets??[])sockets.set(key([prefix,socket.socket_id]),{...socket,path:[...prefix,...socket.part_path],runtime:runtime('socket',[prefix,socket.socket_id])});
  }
  expand(request.root,[],identity);
  function leafAt(p){return leaves.get(key(slots.get(key(p))??p));}
  for(const leaf of leaves.values()) {
    for(const drawing of leaf.def.drawings) {
      const a=drawing._asset,m=a.registration_mapping,cel=m.cels[drawing.cel_index];
      if(!cel||!near(m.cell_size,[a.atlas.cell_width,a.atlas.cell_height]))throw Error('Wrong compiler registration');
      drawing._cell_to_local=multiply(drawing.source_to_local,inverseMatrix(cel.source_to_cell));transform(drawing._cell_to_local);
    }
    const base=leaf.def.drawings.find(d=>d.drawing_id===leaf.p.drawing_id);
    if(!near(base._cell_to_local,leaf.p.cell_to_local))throw Error('Part registration differs from compiler/source mapping: '+key(leaf.path));
  }
  function compatible(leaf,drawingId){const d=leaf.def.drawings.find(d=>d.drawing_id===drawingId),base=leaf.def.drawings.find(d=>d.drawing_id===leaf.p.drawing_id);if(!d||!near(d._cell_to_local,leaf.p.cell_to_local)||!near(d._asset.pivot,base._asset.pivot)||!near(d._asset.registration_mapping.cell_size,base._asset.registration_mapping.cell_size)||d.material_role!==base.material_role)throw Error('Incompatible drawing registration/contact/role: '+drawingId);return d;}
  const variantValues=new Map(),variantOwners=new Map();
  for(const row of state.variants??[]) {fields(row,['model_path','variant_set_id','variant_id'],'variant selection');const k=key([row.model_path,row.variant_set_id]);if(!sets.has(k)||variantValues.has(k))throw Error('Undeclared/duplicate variant selection');variantValues.set(k,row.variant_id);}
  for(const [k,set]of sets) {
    const selection=variantValues.get(k)??set.default, variant=set.variants.find(v=>v.variant_id===selection);if(!variant)throw Error('Unknown variant ID');variantValues.set(k,selection);
    const owned=new Set();
    for(const v of set.variants){const inVariant=new Set();for(const r of v.replacements){const leaf=leaves.get(key([...set.prefix,...r.part_path]));if(!leaf)throw Error('Variant target is not a drawing leaf');compatible(leaf,r.drawing_id);const target=key(leaf.path);if(inVariant.has(target))throw Error('Competing variant writers');inVariant.add(target);owned.add(target);}}
    for(const target of owned){if(variantOwners.has(target))throw Error('Competing variant sets');variantOwners.set(target,k);}
    for(const r of variant.replacements)leaves.get(key([...set.prefix,...r.part_path])).drawing_id=r.drawing_id;
  }
  const explicit=new Map(),incoming=new Map(),writers=new Map();
  for(const row of state.controls??[]) {fields(row,['model_path','control_id','value'],'control override');const k=key([row.model_path,row.control_id]);if(!controls.has(k)||explicit.has(k))throw Error('Undeclared/duplicate override');explicit.set(k,checkedValue(controls.get(k),row.value));}
  for(const [k,c]of controls){const t=c.target;if(t.control_id!==undefined){const target=key([[...c.prefix,...t.part_path],t.control_id]);const child=controls.get(target);if(!child||child.type!==c.type||c.type==='number'&&(c.unit!==child.unit||c.min<child.min||c.max>child.max)||c.type==='drawing'&&c.drawings.some(d=>!child.drawings.includes(d)))throw Error('Missing/incompatible forwarded control');if(incoming.has(target))throw Error('Competing forwarded writers');incoming.set(target,k);}else{
      const leaf=leaves.get(key([...c.prefix,...t.part_path]));if(!leaf)throw Error('Control target is not a drawing leaf');const channel=t.channel;
      const units={opacity:'ratio',rotation:'radians',scale:'multiplier',x:'local-pixels',y:'local-pixels'};
      if(channel==='visible' ? c.type!=='boolean' : channel==='drawing' ? c.type!=='drawing' : !Object.hasOwn(units,channel)||c.type!=='number'||c.unit!==units[channel])throw Error('Unsupported control channel/type/unit');
      if(channel==='opacity'&&(c.min<0||c.max>1)||channel==='scale'&&c.min<=0)throw Error('Invalid channel range');
      if(channel==='drawing'){if(variantOwners.has(key(leaf.path)))throw Error('Competing variant/drawing control writers');for(const d of c.drawings)compatible(leaf,d);}
      const target=key([leaf.path,channel]);if(writers.has(target))throw Error('Competing channel writers');writers.set(target,k);
    }}
  const effective=new Map(),visiting=new Set();
  function value(k){if(effective.has(k))return effective.get(k);if(visiting.has(k))throw Error('Control forwarding cycle');visiting.add(k);const c=controls.get(k);if(incoming.has(k)&&explicit.has(k))throw Error('Competing direct and forwarded overrides');const v=checkedValue(c,incoming.has(k)?value(incoming.get(k)):(explicit.get(k)??c.default));effective.set(k,v);visiting.delete(k);return v;}
  for(const k of controls.keys())value(k);
  for(const [target,k]of writers){const [p,channel]=JSON.parse(target);if(channel==='drawing')leaves.get(key(p)).drawing_id=effective.get(k);}
  const [W,H]=rootModel.local_frame.size;
  const scene={version:1,id:'model-local',title:rootModel.name??rootModel.model_id,canvas:{width:W,height:H,fps:1,loop_seconds:1,background:'rgba(0,0,0,0)'},camera:{overscan:1,x_amplitude:0,y_amplitude:0,zoom_amplitude:0},groups:[],layers:[],coverage_layers:[]};
  const catalog={version:1,assets:[]},mapping=[];
  for(const p of rootModel.paint_order){const leaf=leaves.get(key(p)),d=compatible(leaf,leaf.drawing_id),a=structuredClone(d._asset);a.id=runtime('asset',leaf.path);catalog.assets.push(a);leaf.asset=a;leaf.runtime=runtime('leaf',leaf.path);const cw=a.atlas.cell_width,ch=a.atlas.cell_height;
    const anchor=a.pivot,position=point(leaf.matrix,anchor[0]*cw,anchor[1]*ch),geometry=transform(leaf.matrix);
    leaf.layer={id:leaf.runtime,name:leaf.path.join(' / '),asset:a.id,x:position[0]/W,y:position[1]/H,width:cw/W,height:ch/H,anchor,scale:geometry.scale,rotation:geometry.rotation,opacity:1,visible:true,blend:'source-over',depth:0,cycle_seconds:1,phase_frames:0,tracks:{cell:{interpolation:'hold',keys:[[0,d.cel_index],[1,d.cel_index]]}},sockets:{}};
    scene.layers.push(leaf.layer);
    mapping.push({part_path:leaf.path,layer_id:leaf.runtime,asset_id:a.id,drawing_id:d.drawing_id,cel_index:d.cel_index,material_role:d.material_role,cell_to_model:leaf.matrix,source_to_local:d.source_to_local});
  }
  for(const socket of sockets.values()){const leaf=leaves.get(key(socket.path));if(!leaf)throw Error('Socket must identify a drawing leaf');leaf.layer.sockets[socket.runtime]=socket.cell_uv;}
  // Every painted root pivot is the declared model pivot, including nested frames.
  for(const {def,prefix}of models.values()){const root=leaves.get(key([...prefix,def.root_part_id]));const a=root.asset,m=def.parts.find(p=>p.part_id===def.root_part_id).cell_to_local;
    if(!near(point(m,a.pivot[0]*a.atlas.cell_width,a.pivot[1]*a.atlas.cell_height),def.local_frame.pivot))throw Error('Painted root pivot differs from model local pivot');}
  const done=new Set(),busy=new Set(),mounts=[];
  function mount(leaf){if(done.has(leaf.runtime))return;if(busy.has(leaf.runtime))throw Error('Mount cycle');busy.add(leaf.runtime);
    if(leaf.mount){const {prefix,mount:m}=leaf.mount,parent=leafAt([...prefix,...m.part_path]),socket=sockets.get(key([prefix,m.socket_id]));if(!parent||!socket||key(socket.path)!==key(parent.path))throw Error('Missing/wrong mount socket');mount(parent);
      const proof=reparentAtTime(scene,catalog,{op:'reparent',layer:leaf.runtime,to:parent.runtime,socket:socket.runtime,preserve:'world_at_time',at_seconds:0});mounts.push({...proof,part_path:leaf.path,parent_part_path:parent.path,rest_offset_local_pixels:[leaf.layer.x*W,leaf.layer.y*H]});}
    busy.delete(leaf.runtime);done.add(leaf.runtime);}
  for(const leaf of leaves.values())mount(leaf);
  const rootId=leaves.get(key([rootModel.root_part_id])).runtime;
  for(const l of scene.layers){let cursor=l,seen=new Set();while(cursor.attach){if(seen.has(cursor.id))throw Error('Mount cycle');seen.add(cursor.id);cursor=scene.layers.find(p=>p.id===cursor.attach.layer);}if(cursor.id!==rootId)throw Error('Member does not resolve to painted root');}
  const rest=compileScene(scene,catalog).sample(0);
  for(const row of mapping){const s=rest.find(s=>s.id===row.layer_id),leaf=leaves.get(key(row.part_path)),[cw,ch]=leaf.asset.registration_mapping.cell_size;
    const actual=[[0,0],[cw,0],[cw,ch],[0,ch]].map(([x,y])=>point(s.matrix,s.rect[0]+x,s.rect[1]+y));const expected=[[0,0],[cw,0],[cw,ch],[0,ch]].map(p=>point(row.cell_to_model,...p));if(!near(actual.flat(),expected.flat()))throw Error('Lowered raster registration differs');row.rest_corners=actual;}
  for(const [target,k]of writers){const [p,channel]=JSON.parse(target),l=leaves.get(key(p)).layer,v=effective.get(k);if(channel==='drawing')continue;if(channel==='rotation')l.rotation+=v;else if(channel==='x'||channel==='y')l[channel]+=v/(channel==='x'?W:H);else if(channel==='scale')l.scale*=v;else l[channel]=v;}
  const compiled=compileScene(scene,catalog),states=compiled.sample(0);
  return {scene,catalog,mapping,mounts,state,exported_sockets:[...sockets].map(([k,s])=>({identity:JSON.parse(k),part_path:s.path,layer_id:leaves.get(key(s.path)).runtime,runtime_socket:s.runtime,cell_uv:s.cell_uv})),effective_controls:[...effective].sort().map(([k,value])=>({identity:JSON.parse(k),value})),selected_variants:[...variantValues].sort().map(([k,variant_id])=>({identity:JSON.parse(k),variant_id})),clock:{mode:'static',pose_id:state.pose_id,sample_seconds:0,host_clock:'constant compatibility scene only; no model animation'},selected_leaves:states.filter(s=>s.visible&&s.opacity>0).map(s=>s.id),hidden_leaves:states.filter(s=>!s.visible||s.opacity===0).map(s=>s.id)};
}
