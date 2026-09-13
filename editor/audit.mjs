import {compileScene,point,inverseVector,ENGINE_VERSION} from './engine.mjs';
import {resolveView,viewIds,planViews,fitView} from './views.mjs';
import {createStageRenderer} from './stage-raster.mjs';

export const ALPHA_THRESHOLD=254;

const distance=(a,b)=>Math.hypot(a[0]-b[0],a[1]-b[1]);
export function auditScene(scene,catalog,{coverageRect=null}={}){
  const rig=compileScene(scene,catalog),{width:W,height:H,fps,loop_seconds:T}=scene.canvas;
  const N=Math.round(fps*T),failures=[],warnings=[],coverage=scene.coverage_layers||[];
  const [vx,vy,vw,vh]=coverageRect??[0,0,W,H];
  let maxAttachmentError=0,minCoverageMargin=Infinity;
  const closure=JSON.stringify(rig.sample(0))===JSON.stringify(rig.sample(T));
  if(!closure)failures.push({check:'state closure'});
  if(!coverage.length)warnings.push('No coverage plate declared; geometric coverage was not checked.');
  for(let frame=0;frame<N;frame++){
    const states=rig.sample(frame/fps),byId=new Map(states.map(s=>[s.id,s]));
    if(states.some(s=>!s.matrix.every(Number.isFinite)))failures.push({check:'finite transforms',frame});
    for(const layer of scene.layers.filter(l=>l.attach)){
      const s=byId.get(layer.id),parent=byId.get(layer.attach.layer);
      const socket=parent.sockets[layer.attach.socket];
      const actual=point(s.parent,0,0),error=distance(actual,socket);
      maxAttachmentError=Math.max(maxAttachmentError,error);
      if(error>1e-7)failures.push({check:'attachment',layer:layer.id,frame,error});
    }
    for(const id of coverage){
      const s=byId.get(id),[x,y,w,h]=s.rect;
      const local=[[vx,vy],[vx+vw,vy],[vx+vw,vy+vh],[vx,vy+vh]].map(([px,py])=>inverseVector(s.matrix,px-s.matrix[4],py-s.matrix[5]));
      const margin=Math.min(...local.flatMap(([px,py])=>[px-x,x+w-px,py-y,y+h-py]));
      minCoverageMargin=Math.min(minCoverageMargin,margin);
      if(margin<-.001||!s.visible||s.opacity<1)failures.push({check:'coverage plate',layer:id,frame,margin});
    }
  }
  return {ok:!failures.length,engine_version:ENGINE_VERSION,scene:scene.id,frame_count:N,
    state_closure:closure,attachment_count:scene.layers.filter(l=>l.attach).length,max_attachment_error_pixels:maxAttachmentError,
    coverage_layers:coverage,min_coverage_margin_local_pixels:Number.isFinite(minCoverageMargin)?minCoverageMargin:null,
    failure_count:failures.length,failures:failures.slice(0,30),warnings,
    limits:['Geometric coverage assumes declared plates are opaque; browser pixel audit checks actual composite alpha at preview resolution.',
      'The evaluator wraps time by design. State closure does not establish cel artwork continuity or the encoded video join.',
      'Attachments follow authored sockets; this does not detect an incorrectly placed socket in the painting.']};
}

export function auditViews(scene,catalog,ids=null){
  const named=viewIds(scene).filter(id=>id!=='authored');
  const selected=ids??(named.length?named:['authored']);
  if(!Array.isArray(selected)||!selected.length||new Set(selected).size!==selected.length)throw Error('Select one or more unique view IDs');
  const views=Object.fromEntries(selected.map(id=>{
    const view=resolveView(scene,id),report=auditScene(scene,catalog,{coverageRect:view.rect_scene_px});
    if(!scene.layers.length){report.ok=false;report.failure_count++;report.failures.push({check:'Scene has no layers'});}
    return [id,{view,...report,coverage_checked:!!scene.coverage_layers?.length}];
  }));
  return {ok:Object.values(views).every(report=>report.ok),views,
    limits:['All-frame geometry only. Actual alpha, view composition and encoded media require separate inspection.']};
}

// Uses the same sampled matrices, cel rectangles and Canvas2D blend modes as the stage.
// A small raster catches exposed canvas and large seam outliers; it is not full-resolution export QA.
export async function auditPixels(scene,catalog,images,onProgress=()=>{}){
  const rig=compileScene(scene,catalog),W=135,H=Math.round(W*scene.canvas.height/scene.canvas.width);
  const canvas=document.createElement('canvas');canvas.width=W;canvas.height=H;
  const ctx=canvas.getContext('2d',{willReadFrequently:true}),ratio=W/scene.canvas.width;
  const N=Math.round(scene.canvas.fps*scene.canvas.loop_seconds);
  const background=document.createElement('canvas');background.width=W;background.height=H;
  const bc=background.getContext('2d',{willReadFrequently:true});
  let first,prev,uncoveredFrames=0,maxUncovered=0,worstFrame=0;
  const deltas=[];
  const delta=(a,b)=>{let sum=0;for(let i=0;i<a.length;i+=4)sum+=Math.abs(a[i]-b[i])+Math.abs(a[i+1]-b[i+1])+Math.abs(a[i+2]-b[i+2]);return sum/(a.length/4*3*255);};
  for(let f=0;f<N;f++){
    ctx.setTransform(1,0,0,1,0,0);ctx.globalAlpha=1;ctx.globalCompositeOperation='source-over';ctx.clearRect(0,0,W,H);
    for(const s of rig.sample(f/scene.canvas.fps)){
      if(!s.visible||(scene.finishing?.illuminations||[]).some(e=>e.layer===s.id))continue;
      ctx.setTransform(...s.matrix.map(n=>n*ratio));ctx.globalAlpha=s.opacity;ctx.globalCompositeOperation=s.blend;
      ctx.drawImage(images.get(s.asset),...s.source,...s.rect);
    }
    const raw=ctx.getImageData(0,0,W,H).data;
    let holes=0;for(let i=3;i<raw.length;i+=4)if(raw[i]<254)holes++;
    if(holes){uncoveredFrames++;if(holes>maxUncovered){maxUncovered=holes;worstFrame=f;}}
    bc.fillStyle=scene.canvas.background;bc.fillRect(0,0,W,H);bc.drawImage(canvas,0,0);
    const data=bc.getImageData(0,0,W,H).data;
    if(prev)deltas.push(delta(data,prev));else first=data;
    prev=data;
    if(f%12===0){onProgress(f,N);await new Promise(resolve=>setTimeout(resolve,0));}
  }
  const seam=delta(prev,first),sorted=[...deltas].sort((a,b)=>a-b),p95=sorted[Math.floor((sorted.length-1)*.95)]||0;
  onProgress(N,N);
  return {ok:!uncoveredFrames,resolution:[W,H],frames:N,uncovered_frames:uncoveredFrames,
    worst_frame:worstFrame,max_uncovered_pixels:maxUncovered,last_to_first_rgb_difference:seam,
    adjacent_difference_p95:p95,seam_review_suggested:seam>Math.max(.01,p95*2),
    limits:['Low-resolution composite pixel check only. Small fringes, fine cel jitter, artistic continuity and encoded media need separate inspection.',
      'Seam difference is an attention cue, not a perceptual pass/fail decision.']};
}

// Coordinates are zero-based audit-raster pixels. Bounds include all defects;
// samples are bounded separately for each class so a large perimeter cannot hide
// interior samples. Boundary filtering is descriptive, never a coverage waiver.
export function inspectAlpha(data,width,height,{threshold=ALPHA_THRESHOLD,boundaryPixels=1,sampleLimit=64}={}){
  if(!Number.isInteger(width)||width<1||!Number.isInteger(height)||height<1||data.length!==width*height*4)
    throw Error('Alpha diagnostic requires exact RGBA raster dimensions');
  if(!Number.isInteger(threshold)||threshold<1||threshold>255||!Number.isInteger(boundaryPixels)||boundaryPixels<0||
     !Number.isInteger(sampleLimit)||sampleLimit<0||sampleLimit>256)throw Error('Invalid alpha diagnostic limits');
  const make=()=>({count:0,min_alpha:null,bounds:null,samples:[]});
  const all=make(),boundary=make(),interior=make();
  function add(row,x,y,alpha){
    row.count++;row.min_alpha=row.min_alpha===null?alpha:Math.min(row.min_alpha,alpha);
    if(!row.bounds)row.bounds=[x,y,x+1,y+1];
    else{row.bounds[0]=Math.min(row.bounds[0],x);row.bounds[1]=Math.min(row.bounds[1],y);row.bounds[2]=Math.max(row.bounds[2],x+1);row.bounds[3]=Math.max(row.bounds[3],y+1);}
    if(row.samples.length<sampleLimit)row.samples.push({x,y,alpha});
  }
  for(let y=0;y<height;y++)for(let x=0;x<width;x++){
    const alpha=data[(y*width+x)*4+3];if(alpha>=threshold)continue;
    add(all,x,y,alpha);
    add(x<boundaryPixels||y<boundaryPixels||x>=width-boundaryPixels||y>=height-boundaryPixels?boundary:interior,x,y,alpha);
  }
  for(const row of [all,boundary,interior]){
    if(row.bounds){const [x,y,right,bottom]=row.bounds;row.bounds=[x,y,right-x,bottom-y];}
    row.samples_truncated=row.count>row.samples.length;
  }
  return {threshold,comparison:'alpha < threshold',boundary_pixels:boundaryPixels,sample_limit_per_class:sampleLimit,
    coordinates:'Zero-based audit-raster pixels; bounds are [x,y,width,height]; samples in row-major order',all,boundary,interior};
}

// The same low-resolution per-view audit runs in Node proofs and the browser.
export async function auditViewPixels(scene,catalog,images,ids,createCanvas,onProgress=()=>{},outputPlan=null,{onAlphaDiagnostic=null}={}){
  if(onAlphaDiagnostic!==null&&typeof onAlphaDiagnostic!=='function')throw Error('Alpha diagnostic callback must be a function');
  const requests=ids.map(id=>{
    const output=outputPlan?.views.find(v=>v.view.id===id)?.output;
    const ceiling=output?Math.min(240,Math.max(output.width,output.height)):240;
    return {id,...fitView(resolveView(scene,id),ceiling)};
  });
  const plan=planViews(scene,requests);
  const renderer=createStageRenderer(scene,catalog,images,plan,createCanvas);
  const frames=scene.canvas.fps*scene.canvas.loop_seconds;
  const rows=new Map(plan.views.map(v=>[v.view.id,{resolution:[v.output.width,v.output.height],frames,
    uncovered_frames:0,max_uncovered_pixels:0,worst_frame:null,deltas:[],first:null,previous:null}]));
  const delta=(a,b)=>{let sum=0;for(let i=0;i<a.length;i+=4)sum+=Math.abs(a[i]-b[i])+Math.abs(a[i+1]-b[i+1])+Math.abs(a[i+2]-b[i+2]);return sum/(a.length/4*3*255);};
  const pixels=canvas=>canvas.getContext('2d').getImageData(0,0,canvas.width,canvas.height).data;
  for(let frame=0;frame<frames;frame++){
    renderer.render(frame/scene.canvas.fps,{coverage:true});
    for(const [id,canvas] of renderer.outputs){
      const row=rows.get(id),data=pixels(canvas);let holes=0;
      for(let i=3;i<data.length;i+=4)if(data[i]<ALPHA_THRESHOLD)holes++;
      if(holes){row.uncovered_frames++;if(holes>row.max_uncovered_pixels){row.max_uncovered_pixels=holes;row.worst_frame=frame;if(onAlphaDiagnostic)row.worstPixels=new Uint8ClampedArray(data);}}
    }
    renderer.render(frame/scene.canvas.fps);
    for(const [id,canvas] of renderer.outputs){const row=rows.get(id),data=pixels(canvas);if(row.previous)row.deltas.push(delta(data,row.previous));else row.first=data;row.previous=data;}
    if(frame%12===0){onProgress(frame,frames);await new Promise(resolve=>setTimeout(resolve,0));}
  }
  // Retain the actual measured pixels, rather than re-rendering the selected time
  // at the proof resolution or trying to recover alpha from a finished frame.
  if(onAlphaDiagnostic)for(const resolved of plan.views){
    const row=rows.get(resolved.view.id);if(!row.worstPixels)continue;
    const [width,height]=row.resolution,canvas=createCanvas(width,height),ctx=canvas.getContext('2d');
    const image=ctx.createImageData(width,height);image.data.set(row.worstPixels);ctx.putImageData(image,0,0);
    await onAlphaDiagnostic({view_id:resolved.view.id,frame:row.worst_frame,time_seconds:row.worst_frame/scene.canvas.fps,
      fps:scene.canvas.fps,audit_frames:frames,resolution:row.resolution,view:resolved.view,raster_view:resolved,internal_canvas:plan.internal_canvas,
      alpha:inspectAlpha(row.worstPixels,width,height)},canvas);
  }
  const views=Object.fromEntries([...rows].map(([id,row])=>{
    const {first,previous,deltas,worstPixels,...report}=row,sorted=deltas.sort((a,b)=>a-b),p95=sorted[Math.floor((sorted.length-1)*.95)]||0,seam=delta(first,previous);
    return [id,{...report,ok:!row.uncovered_frames,last_to_first_rgb_difference:seam,adjacent_difference_p95:p95,seam_review_suggested:seam>Math.max(.01,p95*2)}];
  }));
  onProgress(frames,frames);
  return {ok:Object.values(views).every(v=>v.ok),views,raster_plan:plan,
    limits:['All frame times at reduced resolution; coverage measures painted alpha before the background fill. Seam measurements use finished view pixels.',
      'Small defects, composition and encoded output require separate inspection. A large seam difference is an attention cue, not an artistic failure.']};
}
