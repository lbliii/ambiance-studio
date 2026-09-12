// JSON stdin/stdout bridge. The transaction edits a private snapshot; shared
// evaluator validation must succeed before the CLI can persist any result.
import fs from 'node:fs';
import {createHash} from 'node:crypto';
import {compileScene,validateScene} from '../editor/engine.mjs';
import {sceneTiming} from '../editor/timing.mjs';
import {finishingDiagnostics} from '../editor/finishing.mjs';
import {placeFromSource,reparentAtTime} from '../editor/source-placement.mjs';
import {regionDemand} from '../editor/region-sizing.mjs';
import {resolveView,viewIds,viewProjection,canonicalView,dualFraming,planViews} from '../editor/views.mjs';
import {auditViews} from '../editor/audit.mjs';

const layerFields=['name','asset','x','y','width','height','anchor','scale','rotation','opacity','visible','blend','depth','group','attach','sockets','cycle_seconds','phase_frames','motion','tracks','track_loop'];
const optionalFields=['depth','group','attach','sockets','cycle_seconds','phase_frames','motion','tracks','track_loop'];
const object=value=>value&&typeof value==='object'&&!Array.isArray(value);
function fields(value,allowed,label){
  if(!object(value)||Object.keys(value).some(k=>!allowed.includes(k)))throw Error(`Unknown or invalid ${label} fields`);
}
function socketName(name){
  if(typeof name!=='string'||!/^[A-Za-z][A-Za-z0-9_-]{0,39}$/.test(name)||['constructor','prototype'].includes(name))throw Error('Invalid socket name');
}
function applyOperations(scene,catalog,operations,report=false){
  const diagnostics=[];
  const layer=id=>{const l=scene.layers.find(l=>l.id===id);if(!l)throw Error(`Unknown layer: ${id}`);return l;};
  function apply(op){
    if(!object(op)||typeof op.op!=='string')throw Error('Each operation needs an op name');
    const shapes={add:['op','asset','id','values'],set:['op','layer','values','unset'],replace:['op','layer','value'],remove:['op','layer','cascade'],order:['op','layers'],group:['op','id','value'],clock:['op','values'],camera:['op','values'],socket:['op','layer','name','value'],attach:['op','layer','to','socket','offset_x','offset_y'],coverage:['op','layers'],
      place_from_source:['op','id','asset','base','mode','reference','mapping','base_mapping','source_anchor','source_size','anchor','order','values'],
      reparent:['op','layer','to','socket','preserve','at_seconds'],finishing:['op','value'],bindings:['op','value'],framing:['op','value']};
    if(!shapes[op.op])throw Error(`Unsupported scene operation: ${op.op}`);
    fields(op,shapes[op.op],op.op);
    if(['finishing','framing','bindings'].includes(op.op)){if(op.value===null)delete scene[op.op];else scene[op.op]=structuredClone(op.value);}
    else if(op.op==='clock'){fields(op.values,['loop_seconds'],'clock');if(typeof op.values.loop_seconds!=='number'||!Number.isFinite(op.values.loop_seconds)||op.values.loop_seconds<=0)throw Error('Clock needs positive finite loop_seconds');scene.canvas.loop_seconds=op.values.loop_seconds;}
    else if(op.op==='place_from_source')diagnostics.push(placeFromSource(scene,catalog,op));
    else if(op.op==='reparent')diagnostics.push(reparentAtTime(scene,catalog,op));
    else if(op.op==='add'){
      if(typeof op.id!=='string'||!op.id||scene.layers.some(l=>l.id===op.id))throw Error(`Invalid or duplicate layer: ${op.id}`);
      const a=catalog.assets.find(a=>a.id===op.asset);if(!a)throw Error(`Unknown asset: ${op.asset}`);
      const values=op.values||{};fields(values,layerFields,'layer');
      if(values.asset!==undefined&&values.asset!==op.asset)throw Error('Add asset and values.asset must agree');
      if(values.attach&&(values.group!==undefined||values.depth!==undefined)||values.group&&values.depth!==undefined)throw Error('Attached/grouped additions must omit independent depth/group');
      const w=a.atlas?.cell_width||a.width,h=a.atlas?.cell_height||a.height,width=values.width??.35;
      const l={id:op.id,name:op.id,asset:a.id,x:.5,y:.5,width,height:width*scene.canvas.width/scene.canvas.height*h/w,
        anchor:a.pivot||[.5,.5],scale:1,rotation:0,opacity:1,visible:true,blend:'source-over',depth:.8};
      if(a.atlas){l.cycle_seconds=scene.canvas.loop_seconds/4;l.phase_frames=0;}
      Object.assign(l,values);
      if(l.attach){delete l.depth;delete l.group;}else if(l.group)delete l.depth;
      scene.layers.push(l);
    }else if(op.op==='set'){
      const l=layer(op.layer);fields(op.values,layerFields,'layer');
      if(op.unset!==undefined&&(!Array.isArray(op.unset)||op.unset.some(k=>!optionalFields.includes(k)||Object.hasOwn(op.values,k))))throw Error('Invalid or contradictory unset fields');
      for(const key of op.unset||[])delete l[key];
      Object.assign(l,op.values);
    }else if(op.op==='replace'){
      fields(op.value,['id',...layerFields],'replacement layer');
      if(op.value.id!==op.layer)throw Error('Replacement must preserve the layer ID');
      layer(op.layer);scene.layers[scene.layers.findIndex(l=>l.id===op.layer)]=structuredClone(op.value);
    }else if(op.op==='remove'){
      layer(op.layer);if(op.cascade!==undefined&&typeof op.cascade!=='boolean')throw Error('cascade must be boolean');
      const remove=new Set([op.layer]);
      let changed=true;while(changed){changed=false;for(const l of scene.layers)if(l.attach&&remove.has(l.attach.layer)&&!remove.has(l.id)){remove.add(l.id);changed=true;}}
      if(remove.size>1&&!op.cascade)throw Error(`Layer has attached descendants; detach/reparent them first or explicitly set cascade: ${op.layer}`);
      if(scene.coverage_layers?.some(id=>remove.has(id)))throw Error('Remove the layer from coverage explicitly before deleting it');
      scene.layers=scene.layers.filter(l=>!remove.has(l.id));
    }else if(op.op==='order'){
      if(!Array.isArray(op.layers)||op.layers.length!==scene.layers.length||new Set(op.layers).size!==scene.layers.length)throw Error('Paint order must contain every layer exactly once');
      scene.layers=op.layers.map(layer);
    }else if(op.op==='group'){
      if(typeof op.id!=='string'||!op.id)throw Error('Group needs an id');
      const index=scene.groups.findIndex(g=>g.id===op.id);
      if(op.value===null){if(index<0)throw Error(`Unknown group: ${op.id}`);scene.groups.splice(index,1);}
      else{
        fields(op.value,['name','x','y','scale','depth','pivot'],'group');
        const g={id:op.id,...op.value};if(index<0)scene.groups.push(g);else scene.groups[index]=g;
      }
    }else if(op.op==='camera'){
      fields(op.values,['overscan','x_amplitude','y_amplitude','zoom_amplitude'],'camera');Object.assign(scene.camera,op.values);
    }else if(op.op==='socket'){
      socketName(op.name);const l=layer(op.layer);l.sockets||={};
      if(op.value===null)delete l.sockets[op.name];else l.sockets[op.name]=structuredClone(op.value);
    }else if(op.op==='attach'){
      const l=layer(op.layer);socketName(op.socket);
      l.attach={layer:op.to,socket:op.socket};delete l.depth;delete l.group;
      l.x=op.offset_x??0;l.y=op.offset_y??0;
    }else if(op.op==='coverage'){
      if(!Array.isArray(op.layers)||new Set(op.layers).size!==op.layers.length)throw Error('Coverage must list unique layer IDs');
      scene.coverage_layers=op.layers;
    }
  }
  for(let index=0;index<operations.length;index++){
    try{apply(operations[index]);}catch(error){throw Error(`Operation ${index+1}: ${error.message}`);}
  }
  validateScene(scene,catalog);return report?{scene,operations:diagnostics}:scene;
}

try{
  const input=JSON.parse(fs.readFileSync(0,'utf8'));
  const {action,catalog,args={}}=input,scene=structuredClone(input.scene);
  validateScene(scene,catalog);
  let result;
  if(action==='sample')result=compileScene(scene,catalog).sample(args.time);
  else if(action==='region-demand')result=regionDemand(scene,catalog,args);
  else if(action==='binding-check')result=compileScene(scene,catalog).inspectBindings(args.time??0);
  else if(action==='view-defaults')result=dualFraming();
  else if(action==='view-plan')result=planViews(scene,args.requests,args.options);
  else if(action==='view-check')result=auditViews(scene,catalog,args.views);
  else if(action==='view-inspect'){
    const views=Object.fromEntries((args.id?[args.id]:viewIds(scene)).map(id=>{
      const view=resolveView(scene,id);
      return [id,{...view,projection:viewProjection(view),view_sha256:createHash('sha256').update(canonicalView(view)).digest('hex')}];
    }));
    result={authored_canvas:{width:scene.canvas.width,height:scene.canvas.height},views,
      limits:['Saved framing definitions; use render commands for raster evidence.']};
  }
  else if(action==='finishing-check')result=finishingDiagnostics(scene,catalog,args.time??0,compileScene(scene,catalog).sample(args.time??0));
  else if(action==='timing')result=sceneTiming(scene,catalog,{layer:args.layer});
  else if(action==='inspect')result=args.full?scene:{id:scene.id,title:scene.title,canvas:scene.canvas,layers:scene.layers};
  else if(action==='restore'){validateScene(args.snapshot,catalog);result=args.snapshot;}
  else if(action==='apply'){
    const batch=args.batch;
    if(!object(batch)||batch.version!==1||!Array.isArray(batch.operations)||!batch.operations.length)throw Error('Expected a version 1 batch with nonempty operations');
    result=applyOperations(scene,catalog,batch.operations,args.report===true);
  }else{
    let op;
    if(action==='set'){
      const values={};for(const key of layerFields)if(args[key]!==null&&args[key]!==undefined)values[key]=args[key];
      if(args.rotation_deg!==null&&args.rotation_deg!==undefined)values.rotation=args.rotation_deg*Math.PI/180;
      op={op:'set',layer:args.layer,values};
    }else if(action==='socket')op={op:'socket',layer:args.layer,name:args.name,value:args.value??[args.u,args.v]};
    else if(action==='attach')op={op:'attach',layer:args.layer,to:args.to,socket:args.socket,offset_x:args.offset_x??0,offset_y:args.offset_y??0};
    else if(action==='add'){
      const values={};for(const key of ['name','x','y','width','depth'])if(args[key]!==null&&args[key]!==undefined)values[key]=args[key];
      op={op:'add',asset:args.asset,id:args.id,values};
    }else if(['remove','replace','order','group','camera','coverage'].includes(action))op={op:action,...args};
    else throw Error(`Unsupported scene operation: ${action}`);
    result=applyOperations(scene,catalog,[op]);
  }
  console.log(JSON.stringify({ok:true,data:result}));
}catch(e){console.log(JSON.stringify({ok:false,error:e.message}));process.exitCode=2;}
