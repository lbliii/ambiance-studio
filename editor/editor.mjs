import {drawScene,compileScene,point,inverseVector,validateScene} from './engine.mjs';
import {auditScene,auditPixels} from './audit.mjs';
const $=id=>document.getElementById(id);
let scene,catalog,original,selected='cottage',time=0,playing=false,last=0,states=[],drag=null,exportUrl=null;
let compiled=null,placingSocket=false,auditInput=null;
const images=new Map();
const selectedLayer=()=>scene.layers.find(l=>l.id===selected);
const groupFor=l=>scene.groups.find(g=>g.id===l?.group);
const target=()=>($('edit-group').checked&&groupFor(selectedLayer()))||selectedLayer();
function error(message){$('error').textContent=message;$('error').hidden=!message;}
function setStatus(message){$('status').textContent=message;}
function options(el,entries,value){el.replaceChildren(...entries.map(([v,t])=>new Option(t,v)));el.value=value;}
function refreshList(){options($('layer'),[...scene.layers].reverse().map(l=>[l.id,l.name]),selected);$('count').textContent=`${scene.layers.length} layers`;}
function refreshFields(){
  const l=selectedLayer(),g=groupFor(l),obj=target(),a=catalog.assets.find(a=>a.id===l.asset);
  $('x').value=(obj.x*100).toFixed(2);$('y').value=(obj.y*100).toFixed(2);$('scale').value=obj.scale.toFixed(3);
  $('opacity').value=Math.round(l.opacity*100);$('visible').checked=l.visible;
  const state=compileScene(scene,catalog).sample(time).find(s=>s.id===l.id);
  $('depth').value=state.depth;$('depth-value').value=state.depth.toFixed(3);$('depth').disabled=!!l.attach;
  $('rotation').value=(l.rotation*180/Math.PI).toFixed(2);$('rotation').disabled=!!($('edit-group').checked&&g);
  $('anchor-x').value=l.anchor[0];$('anchor-y').value=l.anchor[1];
  $('group-note').textContent=l.attach?`Attached to ${l.attach.layer} → ${l.attach.socket}`:(g?`Shared depth: ${g.name}`:'Independent depth layer');
  const entries=[['','Independent / detach']];
  for(const p of scene.layers){
    // Exclude this layer and descendants so a UI choice cannot create a cycle.
    let ancestor=p,descendant=false;
    while(ancestor){if(ancestor.id===l.id){descendant=true;break;}ancestor=scene.layers.find(n=>n.id===ancestor.attach?.layer);}
    if(descendant)continue;
    const asset=catalog.assets.find(a=>a.id===p.asset);
    for(const name of Object.keys({...asset.sockets,...p.sockets}))entries.push([JSON.stringify([p.id,name]),`${p.name} → ${name}`]);
  }
  options($('attachment'),entries,l.attach?JSON.stringify([l.attach.layer,l.attach.socket]):'');
  $('edit-group').disabled=!g;
  $('cel-panel').hidden=!a.atlas;
  if(a.atlas){
    const T=scene.canvas.loop_seconds;
    const durations=[T/16,T/8,T/4,T/2,T].filter((v,i,a)=>v>0&&a.indexOf(v)===i);
    if(!durations.includes(l.cycle_seconds))durations.push(l.cycle_seconds);
    options($('cycle'),durations.sort((a,b)=>a-b).map(v=>[String(v),`${v} seconds`]),String(l.cycle_seconds));
    $('phase').max=a.atlas.frame_count-1;$('phase').value=l.phase_frames;
  }
  $('back').disabled=scene.layers[0].id===selected;$('front').disabled=scene.layers.at(-1).id===selected;
}
function render(changed=true){
  if(changed||!compiled)compiled=compileScene(scene,catalog);
  if(changed&&auditInput&&auditInput!==JSON.stringify(scene))$('audit-status').textContent='Scene changed since inspection. Run the checks again.';
  states=drawScene($('stage'),scene,catalog,images,time,{selected,grid:$('grid').checked,solo:$('solo').checked,sockets:$('sockets').checked,sampler:compiled.sample});
  $('time').value=`${time.toFixed(2)} / ${scene.canvas.loop_seconds} s`;
  $('timeline').value=Math.round(time*scene.canvas.fps);
  const s=states.find(s=>s.id===selected),a=catalog.assets.find(a=>a.id===s?.asset);
  if(a?.atlas)$('cel-state').value=`Cel ${s.cell+1} / ${a.atlas.frame_count}`;
}
function stop(){playing=false;$('play').textContent='Play';}
function install(next){
  validateScene(next,catalog);scene=structuredClone(next);
  if(!scene.layers.length)throw Error('The editor requires at least one layer.');
  selected=scene.layers.some(l=>l.id==='cottage')?'cottage':scene.layers[0].id;
  time=0;stop();$('edit-group').checked=false;
  $('timeline').max=Math.round(scene.canvas.loop_seconds*scene.canvas.fps)-1;
  $('title').textContent=scene.title;
  $('stage-size').textContent=`${scene.canvas.width} × ${scene.canvas.height}`;
  $('stage').setAttribute('aria-label','Authored painting with independently animated layers. Select a layer, then drag in the picture to move it.');
  refreshList();refreshFields();render();
}
function save(){
  validateScene(scene,catalog);
  const data=JSON.stringify(scene,null,2)+'\n';
  if(exportUrl)URL.revokeObjectURL(exportUrl);
  exportUrl=URL.createObjectURL(new Blob([data],{type:'application/json'}));
  $('scene-json').value=data;$('download-scene').href=exportUrl;$('download-scene').download=`${scene.id}-scene.json`;
  $('export-panel').hidden=false;$('scene-json').focus();
  setStatus('Scene JSON is ready below. Download it or copy the text to keep your changes.');
}
async function start(){
  const project=new URLSearchParams(location.search).get('project');
  const configResponse=project?null:await fetch('/api/config');
  const config=project?{scene:`/api/editor/${encodeURIComponent(project)}/scene`,catalog:`/api/editor/${encodeURIComponent(project)}/catalog`}:configResponse.ok?await configResponse.json():{scene:'../scenes/last-lantern-rigged.json',catalog:'../assets/catalog.json'};
  const responses=await Promise.all([fetch(config.scene),fetch(config.catalog)]);
  if(responses.some(r=>!r.ok))throw Error('Unable to load this working scene or catalog. Saved movies remain available in the studio library.');
  [original,catalog]=await Promise.all(responses.map(r=>r.json()));
  await Promise.all(catalog.assets.map(async a=>{
    const im=new Image();im.src=a.file.startsWith('/')?a.file:`../${a.file}`;await im.decode();images.set(a.id,im);
    if(im.naturalWidth!==a.width||im.naturalHeight!==a.height)throw Error(`Unexpected image size: ${a.id}`);
  }));
  install(original);
  for(const id of ['layer','play','timeline','export','reset','add'])$(id).disabled=false;
  options($('asset'),catalog.assets.map(a=>[a.id,a.id.replaceAll('-',' ')]),'smoke-cels');
  $('asset-count').textContent=`${catalog.assets.length} assets`;
  setStatus('Ready. Local edits stay in memory until you export a scene.');
  requestAnimationFrame(tick);
}
function tick(now){
  if(playing){time=(time+(now-last)/1000)%scene.canvas.loop_seconds;render(false);}
  last=now;requestAnimationFrame(tick);
}
$('play').onclick=()=>{playing=!playing;last=performance.now();$('play').textContent=playing?'Pause':'Play';};
$('timeline').oninput=()=>{stop();time=Number($('timeline').value)/scene.canvas.fps;render();};
$('layer').onchange=()=>{selected=$('layer').value;$('edit-group').checked=false;refreshFields();render();};
$('edit-group').onchange=()=>{refreshFields();render();};
for(const id of ['grid','solo','sockets'])$(id).onchange=()=>render(false);
for(const id of ['x','y','scale','rotation','opacity','depth','anchor-x','anchor-y','phase'])$(id).oninput=()=>{
  if(!scene)return;
  const n=Number($(id).value);if(!Number.isFinite(n)||$(id).value==='')return;
  const l=selectedLayer(),g=groupFor(l),obj=target();
  if(id==='x'||id==='y')obj[id]=n/100;
  else if(id==='scale')obj.scale=Math.max(.05,Math.min(4,n));
  else if(id==='rotation')l.rotation=n*Math.PI/180;
  else if(id==='depth'){(g||l).depth=n;$('depth-value').value=n.toFixed(3);}
  else if(id==='opacity')l.opacity=Math.max(0,Math.min(100,n))/100;
  else if(id==='anchor-x'||id==='anchor-y')l.anchor[id==='anchor-x'?0:1]=Math.max(0,Math.min(1,n));
  else if(id==='phase'){const a=catalog.assets.find(a=>a.id===l.asset);l.phase_frames=Math.max(0,Math.min(a.atlas.frame_count-1,Math.round(n)));}
  render();setStatus('Unsaved placement changes. Export the scene to keep them.');
};
$('visible').onchange=()=>{selectedLayer().visible=$('visible').checked;render();};
$('cycle').onchange=()=>{selectedLayer().cycle_seconds=Number($('cycle').value);render();};
function reorder(offset){const i=scene.layers.findIndex(l=>l.id===selected);if(i+offset<0||i+offset>=scene.layers.length)return;const [l]=scene.layers.splice(i,1);scene.layers.splice(i+offset,0,l);refreshList();refreshFields();render();}
$('back').onclick=()=>reorder(-1);$('front').onclick=()=>reorder(1);
$('export').onclick=()=>{try{save();}catch(e){error(e.message);}};
$('close-export').onclick=()=>{$('export-panel').hidden=true;};
$('use-json').onclick=()=>{
  try{const next=JSON.parse($('scene-json').value);validateScene(next,catalog);if(!next.layers.length)throw Error('The editor requires at least one layer.');install(next);error('');setStatus('Scene loaded from JSON.');}
  catch(e){error(e.message);}
};
$('reset').onclick=()=>{install(original);error('');setStatus('Original study restored.');};
$('add').onclick=()=>{
  const a=catalog.assets.find(a=>a.id===$('asset').value),w=a.atlas?.cell_width||a.width,h=a.atlas?.cell_height||a.height;
  let i=1;while(scene.layers.some(l=>l.id===`${a.id}-${i}`))i++;
  const l={id:`${a.id}-${i}`,name:`${a.id.replaceAll('-',' ')} ${i}`,asset:a.id,x:.5,y:.5,width:.35,height:.35*scene.canvas.width/scene.canvas.height*h/w,
    anchor:a.pivot||[.5,.5],scale:1,rotation:0,opacity:1,visible:true,blend:'source-over',depth:.8};
  if(a.atlas){l.cycle_seconds=scene.canvas.loop_seconds/4;l.phase_frames=0;}
  scene.layers.push(l);selected=l.id;$('edit-group').checked=false;refreshList();refreshFields();render();setStatus('Added a reusable asset instance. The source artwork is unchanged.');
};
$('import').onchange=async()=>{
  try{const file=$('import').files[0];if(!file)return;if(file.size>1000000)throw Error('Scene JSON is too large (maximum 1 MB).');
    const next=JSON.parse(await file.text());validateScene(next,catalog);if(!next.layers.length)throw Error('The editor requires at least one layer.');install(next);error('');setStatus('Scene loaded.');
  }catch(e){error(e.message);}finally{$('import').value='';}
};
$('stage').onpointerdown=e=>{
  if(!scene)return;stop();const obj=target(),s=states.find(s=>s.id===selected);
  if(placingSocket){
    const name=$('socket-name').value.trim();
    if(!/^[a-zA-Z][a-zA-Z0-9_-]{0,39}$/.test(name)){error('Use a short socket name beginning with a letter.');return;}
    const r=$('stage').getBoundingClientRect(),x=(e.clientX-r.left)/r.width*scene.canvas.width,y=(e.clientY-r.top)/r.height*scene.canvas.height;
    const local=inverseVector(s.matrix,x-s.matrix[4],y-s.matrix[5]);
    const l=selectedLayer();l.sockets||={};l.sockets[name]=[(local[0]-s.rect[0])/s.rect[2],(local[1]-s.rect[1])/s.rect[3]];
    placingSocket=false;$('place-socket').textContent='Place socket';error('');refreshFields();render();setStatus(`Socket ${name} placed. Export the scene to keep it.`);return;
  }
  // Moving a group uses only the outer camera matrix; an object uses its parent matrix.
  const parent=[...s.parent];if(obj===groupFor(selectedLayer())){parent[0]/=obj.scale;parent[1]/=obj.scale;parent[2]/=obj.scale;parent[3]/=obj.scale;}
  drag={x:e.clientX,y:e.clientY,startX:obj.x,startY:obj.y,obj,parent};$('stage').setPointerCapture(e.pointerId);
};
$('stage').onpointermove=e=>{
  if(!drag)return;const r=$('stage').getBoundingClientRect();
  const delta=inverseVector(drag.parent,(e.clientX-drag.x)/r.width*scene.canvas.width,(e.clientY-drag.y)/r.height*scene.canvas.height);
  drag.obj.x=drag.startX+delta[0]/scene.canvas.width;drag.obj.y=drag.startY+delta[1]/scene.canvas.height;refreshFields();render();
};
function endDrag(){if(drag)setStatus('Placement changed. Export the scene to keep it.');drag=null;}
$('stage').onpointerup=endDrag;$('stage').onpointercancel=endDrag;
window.addEventListener('keydown',e=>{if(e.code==='Space'&&e.target===document.body){e.preventDefault();$('play').click();}});
$('place-socket').onclick=()=>{placingSocket=!placingSocket;$('place-socket').textContent=placingSocket?'Cancel placement':'Place socket';setStatus(placingSocket?'Click a point on the selected layer to place the named socket.':'Socket placement canceled.');};
$('attachment').onchange=()=>{
  stop();const l=selectedLayer(),old=states.find(s=>s.id===l.id),value=$('attachment').value;
  if(value){const [layer,socket]=JSON.parse(value);l.attach={layer,socket};delete l.group;delete l.depth;l.x=0;l.y=0;}
  else if(l.attach){
    delete l.attach;l.depth=old.depth;
    const next=compileScene(scene,catalog).sample(time).find(s=>s.id===l.id),parent=next.parent;
    const local=inverseVector(parent,old.matrix[4]-parent[4],old.matrix[5]-parent[5]);
    const motion=l.motion,p=2*Math.PI*((time%scene.canvas.loop_seconds)/scene.canvas.loop_seconds),q=motion?p*motion.cycles+motion.phase:0;
    l.x=local[0]/scene.canvas.width-(motion?.x_amplitude||0)*Math.sin(q);l.y=local[1]/scene.canvas.height-(motion?.y_amplitude||0)*Math.sin(2*q);
    l.scale=Math.hypot(old.matrix[0],old.matrix[1])/Math.hypot(parent[0],parent[1]);
    l.rotation=Math.atan2(old.matrix[1],old.matrix[0])-Math.atan2(parent[1],parent[0])-(motion?.rotation_amplitude||0)*Math.sin(q+.3);
  }
  $('edit-group').checked=false;refreshFields();render();setStatus('Attachment changed. Export the scene to keep it.');
};
$('audit').onclick=async()=>{
  if(!scene)return;stop();$('audit').disabled=true;
  const snapshot=structuredClone(scene),input=JSON.stringify(snapshot);
  try{
    const state=auditScene(snapshot,catalog);
    const pixels=await auditPixels(snapshot,catalog,images,(n,total)=>{$('audit-status').textContent=`Inspecting frame ${n} / ${total}…`;});
    const report={scene:snapshot,asset_hashes:Object.fromEntries(catalog.assets.map(a=>[a.id,a.sha256])),state,pixels};
    $('audit-report').value=JSON.stringify(report,null,2);$('audit-json').hidden=false;auditInput=input;
    const stale=input!==JSON.stringify(scene);
    $('audit-status').textContent=stale?'Scene changed during inspection. Report refers to the earlier snapshot; run again.':
      `${state.frame_count} frames checked · ${state.attachment_count} attachments · ${pixels.uncovered_frames} frames with exposed canvas · ${state.ok&&pixels.ok?'technical checks passed':'review needed'}.${pixels.seam_review_suggested?' The join has a larger change than typical frames; inspect it.':''} Visual review is still required.`;
  }catch(e){error(e.message);$('audit-status').textContent='Inspection could not complete.';}
  finally{$('audit').disabled=false;}
};
$('audit-json').onclick=()=>{$('audit-report').hidden=!$('audit-report').hidden;};
$('join').onclick=()=>{time=scene.canvas.loop_seconds-1;playing=true;last=performance.now();$('play').textContent='Pause';render(false);};
start().catch(e=>error(e.message));
