#!/usr/bin/env node
// Rasterize through the exact engine used by the browser. Python owns CLI options.
import fs from 'node:fs/promises';
import {writeSync} from 'node:fs';
import {resizeSceneCanvas,planViews,canonicalView} from '../editor/views.mjs';
import {createStageRenderer} from '../editor/stage-raster.mjs';
import {viewsProofPage} from './views-proof.mjs';
import path from 'node:path';
import os from 'node:os';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import {createHash} from 'node:crypto';
import {spawn} from 'node:child_process';
import {once} from 'node:events';
import {compileScene,drawScene,ENGINE_VERSION} from '../editor/engine.mjs';
import {prepareRigProof,renderRigProof} from './rig-proof.mjs';
import {prepareLookProof,renderLookProof} from './look-proof.mjs';
import {finishingAssetIds} from '../editor/finishing.mjs';
import {auditViews,auditViewPixels} from '../editor/audit.mjs';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const require=createRequire(import.meta.url);
const sha=data=>createHash('sha256').update(data).digest('hex');

const children=new Set();let lastProgress=0;
function progress(event,force=false){
  const fd=Number(process.env.AMBIANCE_PROGRESS_FD);if(!process.env.AMBIANCE_PROGRESS_FD||!Number.isInteger(fd))return;
  if(!force&&Date.now()-lastProgress<500)return;lastProgress=Date.now();
  try{writeSync(fd,JSON.stringify(event)+'\n');}catch{}
}
function own(child){children.add(child);child.once('close',()=>children.delete(child));return child;}
for(const sig of ['SIGTERM','SIGINT'])process.on(sig,()=>{for(const child of children)if(child.exitCode===null)child.kill('SIGTERM');process.exitCode=130;setTimeout(()=>process.exit(130),100).unref();});

function canvasRuntime(){
  const override=process.env.AMBIANCE_CANVAS_MODULE;
  const candidates=override?[override]:['@napi-rs/canvas',path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@napi-rs/canvas')];
  for(const candidate of candidates)try{
    const resolved=require.resolve(candidate),api=require(resolved);
    return {...api,module:resolved,version:require(path.join(path.dirname(resolved),'package.json')).version};
  }catch(error){if(override)throw Error(`AMBIANCE_CANVAS_MODULE cannot be loaded: ${error.message}`);}
  throw Error('Install @napi-rs/canvas for this Node runtime or set AMBIANCE_CANVAS_MODULE to its installed module path.');
}
function finite(value,name){if(!Number.isFinite(value))throw Error(`${name} must be finite`);return value;}
function difference(a,b){let sum=0,max=0;for(let i=0;i<a.length;i++)if(i%4!==3){const d=Math.abs(a[i]-b[i]);sum+=d;max=Math.max(max,d);}return {rgb_mean_absolute_difference:sum/(a.length/4*3),rgb_max_difference:max};}
function gcd(a,b){return b?gcd(b,a%b):a;}
async function native(binary,args){
  progress({phase:'native-'+args[0],completed_frames:null,expected_frames:null},true);
  const child=own(spawn(binary,args.map(String),{stdio:['ignore','pipe','pipe']}));let stdout='',stderr='';child.stdout.on('data',b=>stdout+=b);child.stderr.on('data',b=>stderr+=b);
  const code=await new Promise((resolve,reject)=>{child.on('error',reject);child.on('close',resolve);});
  let result;try{result=JSON.parse(stdout);}catch{throw Error(`Native media command failed (${code}): ${stderr||stdout}`);}
  if(code!==0)throw Error(`Native media command failed (${code}): ${stderr}`);return result;
}
function htmlProof(files,fps,width,height,disabled,labels=null){
  const payload=JSON.stringify({files,fps,width,height,disabled,labels}).replaceAll('<','\\u003c');
  return `<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Ambiance motion proof</title>
<style>body{background:#14151b;color:#eee;font:16px system-ui;margin:24px}main{display:flex;gap:16px;flex-wrap:wrap}figure{margin:0}canvas{display:block;max-width:100%;height:auto;background:#000;width:${width}px}figcaption{margin:8px 0}button,select,input{font:inherit;margin:6px}p{max-width:70ch}</style>
<h1>Motion proof</h1><p>Normal-speed raster frames from the shared scene engine. This short segment repeats for inspection; its end may be an arbitrary cut within the full scene loop. Selected layers are hidden in the comparison, revealing the existing backing.</p>
<button id="play" disabled>Pause</button><label>Speed <select id="speed"><option value="1">1× (actual speed)</option><option value=".5">0.5×</option></select></label><input aria-label="Frame" id="seek" type="range" min="0" value="0"><span id="status">Loading frames…</span><main id="panes"></main>
<script>const config=${payload};const panes=document.querySelector('#panes'),status=document.querySelector('#status'),seek=document.querySelector('#seek'),play=document.querySelector('#play');let playing=true,current=0,base=0,last=performance.now();const views=config.files.map((list,i)=>{const f=document.createElement('figure'),label=document.createElement('figcaption'),c=document.createElement('canvas');c.width=config.width;c.height=config.height;label.textContent=config.labels?.[i]??(i?'Disabled: '+config.disabled.join(', '):'Current scene');f.append(label,c);panes.append(f);return {ctx:c.getContext('2d'),images:list.map(src=>{const image=new Image();image.src=src;return image;})};});seek.max=config.files[0].length-1;function draw(n){for(const v of views)v.ctx.drawImage(v.images[n],0,0);seek.value=n;status.textContent=(n/config.fps).toFixed(2)+' s · frame '+n;}Promise.all(views.flatMap(v=>v.images.map(i=>i.decode()))).then(()=>{play.disabled=false;last=performance.now();draw(0);function tick(now){if(playing){base+=Math.max(0,now-last)/1000*Number(document.querySelector('#speed').value);current=Math.floor(base*config.fps)%config.files[0].length;draw(current);}last=now;requestAnimationFrame(tick);}requestAnimationFrame(tick);}).catch(e=>{status.textContent='Could not load proof frames: '+e.message;});play.onclick=()=>{playing=!playing;play.textContent=playing?'Pause':'Play';};seek.oninput=()=>{playing=false;play.textContent='Play';current=Number(seek.value);base=current/config.fps;draw(current);};</script></html>`;
}
async function main(){
  const initializationStarted=performance.now();
  const runtime=canvasRuntime();
  if(process.argv.includes('--probe'))return {ok:true,module:runtime.module,version:runtime.version,node:process.version};
  let input='';for await(const chunk of process.stdin)input+=chunk;const request=JSON.parse(input);
  const project=await fs.realpath(request.project),out=path.resolve(request.out);
  const inside=async relative=>{const resolved=await fs.realpath(path.resolve(project,relative));if(resolved!==project&&!resolved.startsWith(project+path.sep))throw Error(`Project input must stay inside project: ${relative}`);return resolved;};
  let scenePath,catalogPath;
  if(request.scene_path||request.catalog_path){
    if(!request.scene_path||!request.catalog_path)throw Error('Both explicit scene and catalog are required');
    scenePath=await inside(request.scene_path);catalogPath=await inside(request.catalog_path);
  }else{
    const config=JSON.parse(await fs.readFile(path.join(project,'ambiance-project.json'),'utf8'));
    if(config.version!==1)throw Error('Unsupported project configuration version');
    scenePath=await inside(config.scene);catalogPath=await inside(config.catalog);
  }
  const [sceneBytes,catalogBytes,engineBytes]=await Promise.all([fs.readFile(scenePath),fs.readFile(catalogPath),fs.readFile(path.join(root,'editor/engine.mjs'))]);
  const scene=JSON.parse(sceneBytes),catalog=JSON.parse(catalogBytes),sourceCanvas=structuredClone(scene.canvas);
  if(request.expected_scene_sha256&&sha(sceneBytes)!==request.expected_scene_sha256||request.expected_catalog_sha256&&sha(catalogBytes)!==request.expected_catalog_sha256)throw Error('Scene or catalog changed after view preflight; rerun the render');
  const viewPlan=request.views?planViews(scene,request.views,request.view_options):null;
  const width=viewPlan?.views[0].output.width??request.width??sourceCanvas.width,height=viewPlan?.views[0].output.height??request.height??width*sourceCanvas.height/sourceCanvas.width;
  if(!Number.isInteger(width)||!Number.isInteger(height)||width<1||height<1||(!viewPlan&&width*sourceCanvas.height!==height*sourceCanvas.width))throw Error('Render dimensions must be positive integers preserving the authored aspect ratio.');
  const supersample=viewPlan?.supersample??request.supersample??1;
  if(![1,2,4].includes(supersample)||width*supersample>4096||height*supersample>4096)throw Error('Supersampling requires scale 1, 2, or 4 and internal dimensions <=4096');
  const internalWidth=viewPlan?.internal_canvas.width??width*supersample,internalHeight=viewPlan?.internal_canvas.height??height*supersample;
  if(!viewPlan)resizeSceneCanvas(scene,internalWidth,internalHeight);
  const compiled=compileScene(scene,catalog),fps=scene.canvas.fps,loopFrames=fps*scene.canvas.loop_seconds;
  if(!scene.layers.length)throw Error('Cannot render an empty scene');
  const start=finite(request.start??0,'start');if(start<0)throw Error('start must be nonnegative');
  const mode=request.mode;if(!['frame','proof','rig-proof','look-proof','video','views-proof','benchmark'].includes(mode))throw Error('Unknown render mode');
  if(mode==='views-proof'&&!viewPlan)throw Error('Paired proof requires explicit views');
  if(viewPlan&&['rig-proof','look-proof'].includes(mode))throw Error('Named views cannot be combined with rig/look matrices');
  if(viewPlan&&mode!=='views-proof'&&viewPlan.views.length!==1)throw Error('Select one view for a single-output render');
  if(mode==='rig-proof'&&supersample!==1)throw Error('Rig-proof matrix uses fixed resolution; supersampling is supported for frame, proof, look-proof and video');
  const seconds=finite(request.seconds??(['proof','views-proof'].includes(mode)?Math.min(3,scene.canvas.loop_seconds):scene.canvas.loop_seconds),'seconds');
  const frames=mode==='frame'?1:seconds*fps;
  if(!Number.isInteger(frames)||frames<1||frames>loopFrames)throw Error('Duration must contain an integer frame count within one scene loop');
  if(mode==='video'&&(width%2||height%2))throw Error('Native H.264 dimensions must be even');
  const disable=request.disable??[];
  if(!Array.isArray(disable)||disable.some(id=>!scene.layers.some(l=>l.id===id)))throw Error('Every disabled layer must exist in this scene');
  if(mode==='views-proof'&&disable.length)throw Error('Paired proofs cannot add disabled-layer variants');
  const alternate=structuredClone(scene);for(const layer of alternate.layers)if(disable.includes(layer.id)){layer.visible=false;if(layer.tracks?.visible)layer.tracks.visible={interpolation:'hold',keys:[[0,false],[scene.canvas.loop_seconds,false]]};}
  const alternateCompiled=compileScene(alternate,catalog);
  const rigPlan=mode==='rig-proof'?prepareRigProof(request.rig_recipe,scene,catalog):null;
  const lookPlan=mode==='look-proof'?prepareLookProof(request.look_recipe,scene,catalog):null;
  const images=new Map(),assetBytes=new Map(),assetHashes=[],used=new Set([...scene.layers.map(l=>l.asset),...finishingAssetIds(scene),...(lookPlan?lookPlan.variants.flatMap(v=>finishingAssetIds(v.scene)):[])]);
  for(const asset of catalog.assets.filter(a=>used.has(a.id))){
    const assetPath=await inside(asset.file),bytes=await fs.readFile(assetPath),hash=sha(bytes);
    if(hash!==asset.sha256)throw Error(`Asset hash does not match catalog: ${asset.id}`);
    let decoded;
    try { decoded=await runtime.loadImage(bytes); }
    catch (error) { throw Error(`Cannot decode asset ${asset.id} (${asset.file}): ${error.message}`); }
    if(decoded.width!==asset.width||decoded.height!==asset.height)throw Error(`Asset dimensions do not match catalog: ${asset.id}`);
    images.set(asset.id,decoded);assetBytes.set(asset.id,bytes);assetHashes.push({id:asset.id,file:asset.file,sha256:hash});
  }
  // Validate everything above before creating the immutable result directory.
  await fs.mkdir(out,{recursive:false});
  await fs.writeFile(path.join(out,'scene.snapshot.json'),sceneBytes);await fs.writeFile(path.join(out,'catalog.snapshot.json'),catalogBytes);
  const stageRenderer=viewPlan?createStageRenderer(scene,catalog,images,viewPlan,runtime.createCanvas):null;
  const alternateRenderer=viewPlan&&disable.length?createStageRenderer(alternate,catalog,images,viewPlan,runtime.createCanvas):null;
  const canvas=stageRenderer?.outputs.get(viewPlan.views[0].view.id)??runtime.createCanvas(width,height),internalCanvas=stageRenderer?.stage??(supersample===1?canvas:runtime.createCanvas(internalWidth,internalHeight));
  const finishingDiagnostics=[];
  const render=(time,off=false)=>{
    if(stageRenderer){const active=off?alternateRenderer:stageRenderer;active.render(time);if(active.stage.finishingReport)finishingDiagnostics.push({...active.stage.finishingReport,time_seconds:time,disabled_variant:off});if(off){const ctx=canvas.getContext('2d');ctx.clearRect(0,0,width,height);ctx.drawImage(active.outputs.values().next().value,0,0);}return;}
    drawScene(internalCanvas,off?alternate:scene,catalog,images,time,{sampler:off?alternateCompiled.sample:compiled.sample,createCanvas:runtime.createCanvas});
    if(internalCanvas.finishingReport)finishingDiagnostics.push({...internalCanvas.finishingReport,time_seconds:time,disabled_variant:off});
    if(supersample!==1){const ctx=canvas.getContext('2d');ctx.clearRect(0,0,width,height);ctx.imageSmoothingEnabled=true;ctx.imageSmoothingQuality='high';ctx.drawImage(internalCanvas,0,0,width,height);}
  };
  const endpoints=new Map();
  render(0);const first=Buffer.from(canvas.data());
  if(stageRenderer)for(const [id,c] of stageRenderer.outputs)endpoints.set(id,{first:Buffer.from(c.data())});
  render(scene.canvas.loop_seconds);const endpoint=Buffer.from(canvas.data());
  if(stageRenderer)for(const [id,c] of stageRenderer.outputs){const row=endpoints.get(id);row.rgba_endpoint_exact=row.first.equals(c.data());row.endpoint_difference=difference(row.first,c.data());if(!row.rgba_endpoint_exact)throw Error('Raster endpoint differs for view '+id);}
  const endpointDifference=difference(first,endpoint);
  if(!first.equals(endpoint))throw Error('Raster endpoint differs from frame zero');
  render((loopFrames-1)/fps);const seam=difference(first,canvas.data());
  if(stageRenderer)for(const [id,c] of stageRenderer.outputs)endpoints.get(id).last_to_first=difference(endpoints.get(id).first,c.data());
  const report={ok:true,mode,scene:scenePath,scene_sha256:sha(sceneBytes),catalog:catalogPath,catalog_sha256:sha(catalogBytes),engine_version:ENGINE_VERSION,engine_sha256:sha(engineBytes),source_canvas:sourceCanvas,render_canvas:{...scene.canvas,width,height},internal_canvas:structuredClone(scene.canvas),supersample,downsample:supersample===1?null:{passes:1,filter:'Canvas high-quality image smoothing',alpha:'Canvas premultiplied interpolation',stage:'after complete scene render; before PNG or native encoder'},bindings_engine_sha256:sha(await fs.readFile(path.join(root,'editor/bindings.mjs'))),finishing_engine_sha256:sha(await fs.readFile(path.join(root,'editor/finishing.mjs'))),views_module_sha256:sha(await fs.readFile(path.join(root,'editor/views.mjs'))),start_seconds:start,frames,seconds:frames/fps,source_assets:assetHashes,canvas_module:runtime.module,canvas_version:runtime.version,node_version:process.version,platform:process.platform,renderer_sha256:sha(await fs.readFile(fileURLToPath(import.meta.url))),rig_proof_renderer_sha256:rigPlan?sha(await fs.readFile(path.join(root,'tools/rig-proof.mjs'))):null,rgba_endpoint_exact:true,endpoint_difference:endpointDifference,last_to_first:seam,visual_review_performed:false};
  if(viewPlan){
    report.raster_plan=viewPlan;report.internal_canvas={...sourceCanvas,...viewPlan.internal_canvas};
    report.stage_adapter_sha256=sha(await fs.readFile(path.join(root,'editor/stage-raster.mjs')));
    report.extraction={passes:1,filter:'Canvas high-quality image smoothing',stage:'after complete finished stage; before PNG or native encoder'};
    report.downsample=null;
    report.views=Object.fromEntries(viewPlan.views.map(v=>{const {first,...measurements}=endpoints.get(v.view.id);return [v.view.id,{...v,view_sha256:sha(canonicalView(v.view)),...measurements}];}));
    if(mode==='views-proof'){report.render_canvas=null;report.views_proof_renderer_sha256=sha(await fs.readFile(path.join(root,'tools/views-proof.mjs')));}
    else report.view=report.views[viewPlan.views[0].view.id];
  }
  const started=Date.now();finishingDiagnostics.length=0;
  if(mode==='look-proof'){
    Object.assign(report,await renderLookProof(lookPlan,{out,root,runtime,catalog,images,assetBytes,width,height,supersample,sourceScene:JSON.parse(sceneBytes),sceneHash:sha(sceneBytes),catalogHash:sha(catalogBytes)}));
    report.frames=null;report.seconds=null;report.start_seconds=null;report.scene_loop_frames=loopFrames;
    report.look_recipe={resolved_path:request.look_recipe_path,path_base:'absolute',sha256:request.look_recipe_sha256};
    report.full_loop_review_performed=false;report.check_scope='Saved look samples and editable shared-engine preview; no automatic artistic or full-loop approval';
  }else if(mode==='rig-proof'){
    Object.assign(report,await renderRigProof(rigPlan,{out,runtime,catalog,images,width,height,htmlProof}));
    // A pose matrix is not one continuous clip. Keep saved-frame scope separate
    // from the authored loop whose endpoints were measured above.
    report.frames=null;report.seconds=null;report.start_seconds=null;
    report.scene_loop_frames=loopFrames;
    report.saved_sample_frames=rigPlan.variants.length;
    report.saved_playback_frames_per_variant=rigPlan.playback_frames;
    report.saved_playback_frames_total=rigPlan.playback_frames*rigPlan.variants.length;
    report.rig_recipe={resolved_path:request.rig_recipe_path,path_base:'absolute',sha256:request.rig_recipe_sha256};
    report.inventory=request.inventory_identity??null;report.part_ids=request.rig_recipe.part_ids??[];
    report.full_loop_review_performed=false;report.check_scope='Selected variant poses, optional targeted playback, plus endpoint measurement; no full-loop visual inspection';
  }else if(mode==='benchmark'){
    const times=request.sample_times;if(!Array.isArray(times)||times.length<3||times.length>20||times.some(t=>!Number.isFinite(t)||t<0||t>=scene.canvas.loop_seconds))throw Error('Invalid benchmark sample times');
    report.benchmark={initialization_seconds:(performance.now()-initializationStarted)/1000,samples:[]};
    for(const [index,time] of times.entries()){
      const before=performance.now();render(time);const elapsed=(performance.now()-before)/1000;
      const name=`sample-${String(index).padStart(2,'0')}.png`;await fs.writeFile(path.join(out,name),canvas.toBuffer('image/png'));
      report.benchmark.samples.push({time,render_seconds:elapsed,file:name});
      progress({phase:'benchmark',completed_frames:index+1,expected_frames:times.length},true);
    }
    report.output=path.join(out,'sample-00.png');report.output_sha256=sha(await fs.readFile(report.output));
  }else if(mode==='frame'){
    render(start);const bytes=canvas.toBuffer('image/png');await fs.writeFile(path.join(out,'frame.png'),bytes);report.output=path.join(out,'frame.png');report.output_sha256=sha(bytes);
  }else if(mode==='views-proof'){
    const ids=viewPlan.views.map(v=>v.view.id);
    report.geometry=auditViews(scene,catalog,ids);
    report.pixels=await auditViewPixels(scene,catalog,images,ids,runtime.createCanvas,()=>{},viewPlan);
    report.audit_module_sha256=sha(await fs.readFile(path.join(root,'editor/audit.mjs')));
    report.review_needed=!report.geometry.ok||!report.pixels.ok;
    const outputs=viewPlan.views.map(v=>({id:v.view.id,output:v.output,files:[],hashes:[]}));
    for(const output of outputs)await fs.mkdir(path.join(out,output.id));
    for(let frame=0;frame<frames;frame++){
      render(start+frame/fps);
      for(const output of outputs){const relative=output.id+'/'+String(frame).padStart(5,'0')+'.png',bytes=stageRenderer.outputs.get(output.id).toBuffer('image/png');await fs.writeFile(path.join(out,relative),bytes);output.files.push(relative);output.hashes.push(sha(bytes));}
    }
    await fs.writeFile(path.join(out,'index.html'),viewsProofPage(outputs,fps,start,frames,scene.canvas.loop_seconds));
    report.output_sha256=sha(await fs.readFile(path.join(out,'index.html')));
    report.output=path.join(out,'index.html');report.outputs=outputs;report.sample_times=Array.from({length:frames},(_,frame)=>start+frame/fps);report.playback='One timeline; every output samples each identical source time';report.stage_frames_rendered=frames;
  }else if(mode==='proof'){
    const files=[];
    for(const off of disable.length?[false,true]:[false]){
      const dir=off?'disabled':'current';await fs.mkdir(path.join(out,dir));const list=[];
      for(let frame=0;frame<frames;frame++){render(start+frame/fps,off);const relative=`${dir}/${String(frame).padStart(5,'0')}.png`;await fs.writeFile(path.join(out,relative),canvas.toBuffer('image/png'));list.push(relative);}
      files.push(list);
    }
    await fs.writeFile(path.join(out,'index.html'),htmlProof(files,fps,width,height,disable));report.output=path.join(out,'index.html');report.disabled_layers=disable;report.variants=files.length;report.playback='Actual frame rate by default; disabled layers are hidden, not repainted';
  }else{
    const nativePath=request.native;if(!nativePath)throw Error('Native media binary is required for video');
    const prerollFrames=loopFrames,encodedFrames=frames+prerollFrames;
    const bitrate=request.bitrate??Math.max(300000,Math.round(12000000*width*height/(1080*1920)));
    if(!Number.isInteger(bitrate)||bitrate<1000)throw Error('bitrate must be a positive integer >= 1000');
    const intermediate=path.join(out,'preroll-and-picture.mp4'),video=path.join(out,'picture.mp4');
    const child=own(spawn(nativePath,['encode',intermediate,width,height,fps,encodedFrames,bitrate,'rgba',gcd(loopFrames,fps*2)].map(String),{stdio:['pipe','pipe','pipe']}));
    progress({phase:'render-encode',completed_frames:0,expected_frames:encodedFrames,preroll_frames:prerollFrames,encoded_frames:0},true);
    let stdout='',stderr='',stdinError;child.stdout.on('data',b=>stdout+=b);child.stderr.on('data',b=>stderr+=b);child.stdin.on('error',e=>stdinError=e);
    const done=new Promise((resolve,reject)=>{child.on('error',reject);child.on('close',code=>code===0?resolve():reject(Error(`Native encoder failed (${code}): ${stderr}`)));});done.catch(()=>{});
    try{for(let frame=0;frame<encodedFrames;frame++){
      render(start+(frame-prerollFrames)/fps);
      progress({phase:'render-encode',completed_frames:frame+1,expected_frames:encodedFrames,preroll_frames:prerollFrames,encoded_frames:Math.max(0,frame+1-prerollFrames)},frame+1===encodedFrames);
      if(stdinError)throw stdinError;
      if(!child.stdin.write(canvas.data()))await Promise.race([once(child.stdin,'drain'),done.then(()=>{throw Error('Encoder exited before consuming all frames');})]);
    }
    child.stdin.end();await done;}catch(error){child.stdin.destroy();try{await done;}catch(nativeError){throw nativeError;}throw error;}
    report.native_encoder=JSON.parse(stdout);report.encoder_preroll_frames=prerollFrames;
    await fs.writeFile(path.join(out,'encode-checkpoint.json'),JSON.stringify({...report,ok:false,stage:'encoded-before-trim',intermediate,intermediate_sha256:sha(await fs.readFile(intermediate))},null,2)+'\n');
    report.preroll_trim=await native(nativePath,['trim',intermediate,video,prerollFrames,frames,fps]);
    report.output=video;report.output_sha256=sha(await fs.readFile(video));
  }
  if(finishingDiagnostics.length)report.finishing_diagnostics={samples:finishingDiagnostics.length,max_clipped_pixels:finishingDiagnostics.reduce((n,x)=>Math.max(n,x.clipped_pixels),0),clipped_pixels_sum:finishingDiagnostics.reduce((n,x)=>n+x.clipped_pixels,0),internal_pixels_per_frame:internalWidth*internalHeight,scope:mode==='video'?'Encoded output and encoder preroll samples':'Saved render samples',automatic_artistic_judgment:false};
  report.elapsed_seconds=(Date.now()-started)/1000;
  report.peak_rss_bytes=process.resourceUsage().maxRSS*1024;
  await fs.writeFile(path.join(out,'render-report.json'),JSON.stringify(report,null,2)+'\n');return report;
}
try{console.log(JSON.stringify(await main()));}catch(error){console.log(JSON.stringify({ok:false,error:error.message}));process.exitCode=1;}
