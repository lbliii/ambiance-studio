// Pure, absolute-time scene sampling. Preview never advances simulation state.
export const TAU = Math.PI * 2;
const identity = [1,0,0,1,0,0];
function multiply(a,b) {
  return [a[0]*b[0]+a[2]*b[1], a[1]*b[0]+a[3]*b[1],
    a[0]*b[2]+a[2]*b[3], a[1]*b[2]+a[3]*b[3],
    a[0]*b[4]+a[2]*b[5]+a[4], a[1]*b[4]+a[3]*b[5]+a[5]];
}
const translation = (x,y) => [1,0,0,1,x,y];
const scaling = s => [s,0,0,s,0,0];
const rotation = r => [Math.cos(r),Math.sin(r),-Math.sin(r),Math.cos(r),0,0];
const chain = (...matrices) => matrices.reduce(multiply,identity);
export function point(m,x,y) { return [m[0]*x+m[2]*y+m[4],m[1]*x+m[3]*y+m[5]]; }
export function inverseVector(m,x,y) {
  const det=m[0]*m[3]-m[1]*m[2];
  return [(m[3]*x-m[2]*y)/det,(-m[1]*x+m[0]*y)/det];
}
export const ENGINE_VERSION = '0.3.0';
export function compileScene(input,inputCatalog) {
  validateScene(input,inputCatalog);
  // A compiled snapshot cannot change midway through a frame audit or playback.
  const scene=structuredClone(input),catalog=structuredClone(inputCatalog);
  const {width:W,height:H,loop_seconds:T}=scene.canvas, camera=scene.camera;
  const assets=new Map(catalog.assets.map(a=>[a.id,a]));
  const groups=new Map(scene.groups.map(g=>[g.id,g]));
  const layers=new Map(scene.layers.map(l=>[l.id,l]));
  function sample(time){
    if(!Number.isFinite(time))throw Error('Time must be finite.');
    const t=((time%T)+T)%T, p=TAU*t/T, memo=new Map();
    function visit(layer){
    if(memo.has(layer.id))return memo.get(layer.id);
    const attached=layer.attach?visit(layers.get(layer.attach.layer)):null;
    const group=groups.get(layer.group), d=attached?attached.depth:(group?group.depth:layer.depth);
    const zoom=camera.overscan+camera.zoom_amplitude*d*Math.cos(p);
    let parent=chain(translation(W/2+W*camera.x_amplitude*d*Math.sin(p),H/2+H*camera.y_amplitude*d*Math.sin(2*p+.6)),scaling(zoom),translation(-W/2,-H/2));
    if(group) parent=multiply(parent,chain(translation((group.x+group.pivot[0])*W,(group.y+group.pivot[1])*H),scaling(group.scale),translation(-group.pivot[0]*W,-group.pivot[1]*H)));
    if(attached){
      const socket=attached.socketLocal[layer.attach.socket];
      parent=multiply(attached.matrix,translation(...socket));
    }
    const motion=layer.motion, q=motion?p*motion.cycles+motion.phase:0;
    const x=(layer.x+(motion?motion.x_amplitude*Math.sin(q):0))*W;
    const y=(layer.y+(motion?motion.y_amplitude*Math.sin(2*q):0))*H;
    const r=layer.rotation+(motion?.rotation_amplitude||0)*Math.sin(q+.3);
    const matrix=chain(parent,translation(x,y),rotation(r),scaling(layer.scale));
    const asset=assets.get(layer.asset), atlas=asset.atlas;
    const cell=atlas?(Math.floor(t/layer.cycle_seconds*atlas.frame_count+1e-7)+(layer.phase_frames||0))%atlas.frame_count:0;
    const rect=[-layer.anchor[0]*layer.width*W,-layer.anchor[1]*layer.height*H,layer.width*W,layer.height*H];
    const socketLocal=Object.fromEntries(Object.entries({...asset.sockets,...layer.sockets}).map(([name,value])=>{
      const uv=Array.isArray(value)?value:value.frames[cell];
      return [name,[rect[0]+uv[0]*rect[2],rect[1]+uv[1]*rect[3]]];
    }));
    const state={id:layer.id,asset:layer.asset,matrix,parent,cell,depth:d,visible:layer.visible&&(!attached||attached.visible),
      opacity:layer.opacity*(attached?attached.opacity:1),blend:layer.blend,rect,socketLocal,
      sockets:Object.fromEntries(Object.entries(socketLocal).map(([name,xy])=>[name,point(matrix,...xy)])),
      source:atlas?[(cell%atlas.columns)*atlas.cell_width,Math.floor(cell/atlas.columns)*atlas.cell_height,atlas.cell_width,atlas.cell_height]:[0,0,asset.width,asset.height]};
    memo.set(layer.id,state);return state;
    }
    return scene.layers.map(visit);
  }
  return {sample,scene,catalog};
}
export function sampleScene(scene,catalog,time){
  return compileScene(scene,catalog).sample(time);
}

export function validateScene(scene,catalog) {
  const finite = n=>typeof n==='number' && Number.isFinite(n);
  const vector = v=>Array.isArray(v)&&v.length===2&&v.every(finite);
  if(!scene||scene.version!==1||!Array.isArray(scene.layers)||!Array.isArray(scene.groups)) throw Error('Expected a version 1 scene with layers and groups.');
  const c=scene.canvas;
  if(!c||!['width','height','fps','loop_seconds'].every(k=>finite(c[k])&&c[k]>0)||c.width>4096||c.height>4096||!Number.isInteger(c.width)||!Number.isInteger(c.height)||!Number.isInteger(c.fps)||!Number.isInteger(c.fps*c.loop_seconds)) throw Error('Invalid canvas or frame count (preview maximum 4096 pixels per side).');
  if(!scene.camera||!['overscan','x_amplitude','y_amplitude','zoom_amplitude'].every(k=>finite(scene.camera[k]))||scene.camera.overscan<1) throw Error('Invalid camera.');
  const groups=new Map();
  for(const g of scene.groups){
    if(!g.id||groups.has(g.id)||!['x','y','scale','depth'].every(k=>finite(g[k]))||g.scale<=0||!vector(g.pivot)) throw Error('Invalid or duplicate group.');
    groups.set(g.id,g);
  }
  const assets=new Map(catalog.assets.map(a=>[a.id,a])), ids=new Set();
  for(const l of scene.layers){
    if(!l.id||ids.has(l.id)||!assets.has(l.asset)) throw Error('Unknown asset or duplicate layer.');
    ids.add(l.id);
    if(!['x','y','width','height','scale','rotation','opacity'].every(k=>finite(l[k]))||l.width<=0||l.height<=0||l.scale<=0||l.opacity<0||l.opacity>1||!vector(l.anchor)||l.anchor.some(n=>n<0||n>1)||typeof l.visible!=='boolean'||!['source-over','screen','multiply'].includes(l.blend)) throw Error(`Invalid geometry or appearance: ${l.id}`);
    if(l.attach){
      if(l.group||'depth' in l||!l.attach.layer||!l.attach.socket)throw Error(`Attached layers inherit depth and group: ${l.id}`);
    }else if(l.group?(!groups.has(l.group)||'depth' in l):!finite(l.depth)) throw Error(`Invalid depth/group: ${l.id}`);
    if(assets.get(l.asset).atlas && (!finite(l.cycle_seconds)||l.cycle_seconds<=0||Math.abs(c.loop_seconds/l.cycle_seconds-Math.round(c.loop_seconds/l.cycle_seconds))>1e-8||!Number.isInteger(l.phase_frames)||l.phase_frames<0)) throw Error(`Cel cycle must divide the visual loop: ${l.id}`);
    if(l.motion&&(!['x_amplitude','y_amplitude','cycles','phase'].every(k=>finite(l.motion[k]))||!Number.isInteger(l.motion.cycles)||l.motion.cycles<1||!finite(l.motion.rotation_amplitude||0))) throw Error(`Invalid motion: ${l.id}`);
  }
  const layers=new Map(scene.layers.map(l=>[l.id,l])), visited=new Set(), visiting=new Set(),depths=new Map();
  for(const l of scene.layers){
    const asset=assets.get(l.asset),sockets={...asset.sockets,...l.sockets};
    for(const [name,value] of Object.entries(sockets)){
      const valid=Array.isArray(value)?vector(value):(Array.isArray(value?.frames)&&value.frames.length===(asset.atlas?.frame_count||1)&&value.frames.every(vector));
      if(!name||!valid)throw Error(`Invalid socket coordinates/track: ${l.id}.${name}`);
    }
  }
  function visit(l){
    if(visiting.has(l.id))throw Error(`Attachment cycle: ${l.id}`);
    if(visited.has(l.id))return;
    visiting.add(l.id);
    if(l.attach){
      const parent=layers.get(l.attach.layer);
      if(!parent||!Object.hasOwn({...assets.get(parent.asset).sockets,...parent.sockets},l.attach.socket))throw Error(`Missing attachment layer or socket: ${l.id}`);
      visit(parent);
      depths.set(l.id,depths.get(parent.id));
    }else{
      depths.set(l.id,l.group?groups.get(l.group).depth:l.depth);
    }
    if(scene.camera.overscan-Math.abs(scene.camera.zoom_amplitude*depths.get(l.id))<=0)throw Error(`Camera zoom crosses zero: ${l.id}`);
    visiting.delete(l.id);visited.add(l.id);
  }
  scene.layers.forEach(visit);
  if(scene.coverage_layers&&(!Array.isArray(scene.coverage_layers)||scene.coverage_layers.some(id=>!layers.has(id))))throw Error('Unknown coverage layer.');
  if(scene.audio&&(!finite(scene.audio.loop_seconds)||scene.audio.loop_seconds<=0||Math.abs(scene.audio.loop_seconds/c.loop_seconds-Math.round(scene.audio.loop_seconds/c.loop_seconds))>1e-8)) throw Error('Audio duration must be a whole number of picture loops.');
  return true;
}

export function drawScene(canvas,scene,catalog,images,time,{selected=null,grid=false,solo=false,sockets=false,sampler=null}={}) {
  const {width:W,height:H}=scene.canvas;
  if(canvas.width!==W||canvas.height!==H){canvas.width=W;canvas.height=H;}
  const ctx=canvas.getContext('2d');
  ctx.setTransform(...identity);ctx.globalAlpha=1;ctx.globalCompositeOperation='source-over';
  ctx.fillStyle=scene.canvas.background;ctx.fillRect(0,0,W,H);
  ctx.imageSmoothingEnabled=true;ctx.imageSmoothingQuality='high';
  const states=sampler?sampler(time):sampleScene(scene,catalog,time);
  for(const s of states){
    if(!s.visible||(solo&&s.id!==selected))continue;
    ctx.save();ctx.setTransform(...s.matrix);ctx.globalAlpha=s.opacity;ctx.globalCompositeOperation=s.blend;
    ctx.drawImage(images.get(s.asset),...s.source,...s.rect);ctx.restore();
  }
  if(sockets){
    ctx.font='20px sans-serif';ctx.fillStyle='#79e1db';ctx.strokeStyle='#79e1db';ctx.lineWidth=2;
    for(const state of states)for(const [name,[x,y]] of Object.entries(state.sockets)){
      ctx.beginPath();ctx.arc(x,y,9,0,TAU);ctx.stroke();ctx.fillText(name,x+14,y-12);
    }
    for(const layer of scene.layers.filter(l=>l.attach)){
      const child=states.find(s=>s.id===layer.id),parent=states.find(s=>s.id===layer.attach.layer);
      const origin=point(child.matrix,0,0),socket=parent.sockets[layer.attach.socket];
      ctx.beginPath();ctx.moveTo(...socket);ctx.lineTo(...origin);ctx.stroke();
    }
  }
  ctx.setTransform(...identity);
  if(grid){
    ctx.strokeStyle='rgba(255,238,205,.45)';ctx.lineWidth=2;ctx.beginPath();
    for(let i=1;i<10;i++){ctx.moveTo(W*i/10,0);ctx.lineTo(W*i/10,H);ctx.moveTo(0,H*i/10);ctx.lineTo(W,H*i/10);}
    ctx.stroke();
  }
  const s=states.find(s=>s.id===selected);
  if(s){
    const [x,y,w,h]=s.rect;
    const corners=[[x,y],[x+w,y],[x+w,y+h],[x,y+h]].map(([x,y])=>point(s.matrix,x,y));
    ctx.strokeStyle='#ffe3a2';ctx.lineWidth=3;ctx.setLineDash([12,9]);ctx.beginPath();
    corners.forEach(([x,y],i)=>i?ctx.lineTo(x,y):ctx.moveTo(x,y));ctx.closePath();ctx.stroke();ctx.setLineDash([]);
    const anchor=point(s.matrix,0,0);ctx.fillStyle='#ffe3a2';ctx.beginPath();ctx.arc(...anchor,7,0,TAU);ctx.fill();
  }
  return states;
}
