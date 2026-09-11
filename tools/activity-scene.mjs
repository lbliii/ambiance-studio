#!/usr/bin/env node
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {createRequire} from 'node:module';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {compileScene} from '../editor/engine.mjs';
import {finishingAssetIds} from '../editor/finishing.mjs';
import {planViews,canonicalView} from '../editor/views.mjs';
import {createStageRenderer} from '../editor/stage-raster.mjs';
import {measureActivity,pixelMetrics,intervals,diagnosticWarnings} from '../editor/activity.mjs';
import {viewsProofPage} from './views-proof.mjs';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),require=createRequire(import.meta.url);
const sha=b=>createHash('sha256').update(b).digest('hex');
const json=o=>JSON.stringify(o,null,2)+'\n';
function runtime(){
  const choices=process.env.AMBIANCE_CANVAS_MODULE?[process.env.AMBIANCE_CANVAS_MODULE]:['@napi-rs/canvas',path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@napi-rs/canvas')];
  for(const name of choices)try{const resolved=require.resolve(name);return {...require(resolved),module:resolved,version:require(path.join(path.dirname(resolved),'package.json')).version};}catch{}
  throw Error('Canvas is required to decode painted bounds; run ambiance doctor or set AMBIANCE_CANVAS_MODULE');
}
function paintFacts(asset,image,rt){
  const a=asset.atlas,count=a?.frame_count??1,W=a?.cell_width??asset.width,H=a?.cell_height??asset.height;
  const canvas=rt.createCanvas(W,H),ctx=canvas.getContext('2d'),result=[];
  for(let cell=0;cell<count;cell++){
    ctx.clearRect(0,0,W,H);ctx.drawImage(image,a?(cell%a.columns)*W:0,a?Math.floor(cell/a.columns)*H:0,W,H,0,0,W,H);
    const bytes=Buffer.from(canvas.data());let minX=W,minY=H,maxX=-1,maxY=-1,pixels=0;
    for(let y=0;y<H;y++)for(let x=0;x<W;x++){const k=(y*W+x)*4;if(bytes[k+3]){pixels++;minX=Math.min(minX,x);minY=Math.min(minY,y);maxX=Math.max(maxX,x);maxY=Math.max(maxY,y);}else bytes.fill(0,k,k+4);}
    result.push({cell,sha256:sha(bytes),painted_pixels:pixels,bounds_uv:pixels?[minX/W,minY/H,(maxX-minX+1)/W,(maxY-minY+1)/H]:null});
  }
  return result;
}
async function main(){
  const started=performance.now();let input='';for await(const b of process.stdin)input+=b;const req=JSON.parse(input);
  const resuming=req.resume===true;delete req.resume;
  const rt=runtime(),project=await fs.realpath(req.project),out=path.resolve(req.out);
  const inside=async p=>{const real=await fs.realpath(path.resolve(project,p));if(!real.startsWith(project+path.sep))throw Error(`Input outside project: ${p}`);return real;};
  const scenePath=await inside(req.scene_path),catalogPath=await inside(req.catalog_path);
  const sceneBytes=await fs.readFile(scenePath),catalogBytes=await fs.readFile(catalogPath);
  if(sha(sceneBytes)!==req.scene_sha256||sha(catalogBytes)!==req.catalog_sha256)throw Error('Activity inputs changed after preflight');
  const scene=JSON.parse(sceneBytes),catalog=JSON.parse(catalogBytes),rig=compileScene(scene,catalog);
  const viewPlan=planViews(scene,req.views,{long_edge:req.long_edge??null});
  const variants=[{id:'target',scene},...(req.variants??[])];
  if(variants.length>5)throw Error('At most target plus two strength and two cadence variants are supported');
  const painted={},images=new Map(),assets=[];
  const used=new Set(variants.flatMap(v=>[...v.scene.layers.map(l=>l.asset),...finishingAssetIds(v.scene)]));
  for(const asset of catalog.assets.filter(a=>used.has(a.id))){
    const file=await inside(asset.file),bytes=await fs.readFile(file),image=await rt.loadImage(bytes);
    if(sha(bytes)!==asset.sha256||image.width!==asset.width||image.height!==asset.height)throw Error(`Asset identity mismatch: ${asset.id}`);
    images.set(asset.id,image);painted[asset.id]=paintFacts(asset,image,rt);assets.push({id:asset.id,path:file,sha256:sha(bytes)});
  }
  const state=measureActivity(scene,catalog,{views:viewPlan.views,painted,actions:req.actions,stride:req.stride,start_frame:req.start_frame,frames:req.frames});
  if(rig.inspectBindings)for(let f=req.start_frame;f<req.start_frame+req.frames;f+=req.stride)state.driver_samples.push({frame:f,values:rig.inspectBindings(f/scene.canvas.fps)});
  const frames=req.frames/req.stride,actions=req.raster?(req.actions??[]):[];
  if(req.raster&&(actions.length>8||frames>600||(actions.length+variants.length)*viewPlan.views.length>16||frames*(actions.length+variants.length)*viewPlan.internal_canvas.width*viewPlan.internal_canvas.height>400000000))
    throw Error('Raster workload exceeds 8 actions, 16 panes, 600 samples or 400 million stage pixels; shorten proof, filter actions, increase stride or lower --long-edge');
  const renderers=new Map();
  if(req.raster){
    for(const v of variants)renderers.set(v.id,createStageRenderer(v.scene,catalog,images,viewPlan,rt.createCanvas));
    for(const action of actions){const copy=structuredClone(scene);for(const l of copy.layers)if(action.layers.includes(l.id)){l.visible=false;if(l.tracks?.visible)l.tracks.visible={interpolation:'hold',keys:[[0,false],[scene.canvas.loop_seconds,false]]};}renderers.set('disabled-'+action.id,createStageRenderer(copy,catalog,images,viewPlan,rt.createCanvas));}
  }
  if(!resuming)await fs.mkdir(out,{recursive:false});
  const files=[];
  async function save(relative,bytes){const target=path.join(out,relative);await fs.mkdir(path.dirname(target),{recursive:true});
    try{const existing=await fs.readFile(target);if(sha(existing)!==sha(bytes))throw Error(`Partial activity artifact changed: ${relative}; choose a fresh output directory`);}
    catch(error){if(error.code!=='ENOENT')throw error;await fs.writeFile(target,bytes,{flag:'wx'});}
    files.push({path:relative,sha256:sha(bytes),bytes:Buffer.byteLength(bytes)});}
  await save('scene.snapshot.json',sceneBytes);await save('catalog.snapshot.json',catalogBytes);await save('request.json',json(req));
  for(const v of variants.slice(1))await save(`variants/${v.id}.json`,json(v.scene));
  const rows=[],previous=new Map(),firstSaved=new Map(),maps=new Map(),panes=[];
  const makePane=(variant,view)=>({id:variant+' / '+view.view.id,variant,view:view.view.id,output:view.output,files:[],hashes:[]});
  if(req.raster)for(const variant of renderers.keys())for(const view of viewPlan.views)panes.push(makePane(variant,view));
  const rasterStarted=performance.now();
  for(let i=0;req.raster&&i<frames;i++){
    const frame=req.start_frame+i*req.stride,time=frame/scene.canvas.fps,now=new Map();
    for(const [variant,renderer] of renderers){renderer.render(time);for(const v of viewPlan.views){
      const id=v.view.id,canvas=renderer.outputs.get(id),key=variant+'/'+id,bytes=canvas.toBuffer('image/png'),relative=`frames/${key}/${String(i).padStart(5,'0')}.png`;
      now.set(key,Buffer.from(canvas.data()));if(i===0)firstSaved.set(key,now.get(key));await save(relative,bytes);const pane=panes.find(p=>p.variant===variant&&p.view===id);pane.files.push(relative);pane.hashes.push(sha(bytes));
    }}
    for(const v of viewPlan.views){const id=v.view.id,current=now.get('target/'+id),before=previous.get('target/'+id);
      for(const action of [null,...actions]){
        const key=(action?.id??'whole-frame')+'/'+id,off=action?now.get('disabled-'+action.id+'/'+id):null,priorOff=action?previous.get('disabled-'+action.id+'/'+id):null;
        const {metrics,map}=pixelMetrics(current,before,off,priorOff);rows.push({frame,time_seconds:time,view:id,action:action?.id??null,...metrics});
        if(!maps.has(key))maps.set(key,new Float64Array(map.length));const heat=maps.get(key);map.forEach((n,k)=>heat[k]=Math.max(heat[k],n));
      }
    }
    previous.clear();for(const [key,value] of now)previous.set(key,value);
  }
  const rasterSeconds=(performance.now()-rasterStarted)/1000;
  const joins=[];
  for(const [variant,renderer] of renderers){renderer.render(scene.canvas.loop_seconds);const endpoint=new Map([...renderer.outputs].map(([id,c])=>[id,Buffer.from(c.data())]));renderer.render(0);
    for(const [id,c] of renderer.outputs)joins.push({variant,view:id,zero_to_endpoint_rgba_exact:endpoint.get(id).equals(Buffer.from(c.data())),
      saved_last_to_first:pixelMetrics(firstSaved.get(variant+'/'+id),previous.get(variant+'/'+id)).metrics,
      saved_segment_is_full_loop:req.start_frame===0&&req.frames===scene.canvas.fps*scene.canvas.loop_seconds});}
  for(const [key,values] of maps){const view=viewPlan.views.find(v=>v.view.id===key.split('/')[1]);const canvas=rt.createCanvas(view.output.width,view.output.height),ctx=canvas.getContext('2d'),pixels=ctx.createImageData(canvas.width,canvas.height);values.forEach((n,i)=>{pixels.data[i*4]=Math.min(255,n);pixels.data[i*4+3]=255;});ctx.putImageData(pixels,0,0);await save('maps/'+key+'.png',canvas.toBuffer('image/png'));}
  if(req.raster)await save('index.html',viewsProofPage(panes,scene.canvas.fps/req.stride,req.start_frame/scene.canvas.fps,frames,scene.canvas.loop_seconds)
    .replace('Portrait and landscape proof','Motion activity proof').replace('One scene, shared timing','Motion activity proof')
    .replace('Each view comes from the same finished scene at the same time.',`Target, explicit variants and disabled-layer interventions share the same picture clock and views. Strength and cadence are separate experiments. Sampling: every ${req.stride} production frame(s); playback remains 1×.`));
  for(const v of state.views)for(const a of v.actions){const raster=rows.filter(r=>r.view===v.view.id&&r.action===a.id);a.warnings=diagnosticWarnings({layers:v.layers.filter(l=>a.layers.includes(l.layer))},raster);a.raster_sample_count=raster.length;
    a.candidate_quiet_intervals=intervals(raster.map(r=>r.residual_changed_pixels===0),req.stride/scene.canvas.fps,req.start_frame/scene.canvas.fps).filter(r=>r.active).map(({active,...r})=>r);
    a.attribution='Disabled layer set includes attached descendants and coupled lighting. Residual change is an intervention result, not exclusive gesture attribution or an artistic pass.';
  }
  await save('state.json',json(state));await save('raster.json',json({version:1,rows,units:'8-bit sRGB maximum absolute RGB channel delta; alpha excluded',first_sample:'No temporal comparison before first saved sample',map:'Maximum per-pixel sampled temporal difference; action maps use signed residual difference',warnings:'Diagnostic thresholds are fixture-calibrated prompts to inspect, never salience levels or requirement satisfaction'}));
  await save('painted-cells.json',json(painted));
  const modules={};for(const name of ['editor/engine.mjs','editor/timing.mjs','editor/activity.mjs','editor/views.mjs','editor/stage-raster.mjs','editor/finishing.mjs','tools/activity-scene.mjs'])modules[name]=sha(await fs.readFile(path.join(root,name)));
  if(rig.inspectBindings)modules['editor/bindings.mjs']=sha(await fs.readFile(path.join(root,'editor/bindings.mjs')));
  const inputsUnchanged=sha(await fs.readFile(scenePath))===req.scene_sha256&&sha(await fs.readFile(catalogPath))===req.catalog_sha256&&(!req.plan||sha(await fs.readFile(req.plan.path))===req.plan.plan_sha256)&&(await Promise.all(assets.map(async a=>sha(await fs.readFile(a.path))===a.sha256))).every(Boolean);
  if(!inputsUnchanged)throw Error('Inputs changed during activity proof; completed receipt was not published');
  const report={kind:'ambiance-scene-activity',version:1,schema_version:1,ok:true,scene_sha256:req.scene_sha256,catalog_sha256:req.catalog_sha256,plan:req.plan??null,revision:req.revision??null,
    views:viewPlan.views.map(v=>({...v,view_sha256:sha(canonicalView(v.view))})),clock:{picture_seconds:scene.canvas.loop_seconds,fps:scene.canvas.fps,start_frame:req.start_frame,frames:req.frames,stride:req.stride,sampling_hz:scene.canvas.fps/req.stride},
    actions:req.actions,variants:variants.map(v=>({id:v.id,experiment:v.experiment??'target',scene_sha256:sha(json(v.scene))})),
    artifacts:files,source_assets:assets,modules,runtime:{node:process.version,canvas:rt.version,platform:process.platform},
    performance:{elapsed_seconds:(performance.now()-started)/1000,raster_seconds:rasterSeconds,peak_rss_bytes:process.resourceUsage().maxRSS*1024,stage_pixel_samples:req.raster?frames*renderers.size*viewPlan.internal_canvas.width*viewPlan.internal_canvas.height:0,saved_frames:panes.reduce((n,p)=>n+p.files.length,0)},
    summary:state.views.map(v=>({view:v.view.id,actions:v.actions.map(a=>({id:a.id,applicable:a.applicable,warnings:a.warnings,max_sampled_rest_seconds:a.max_sampled_rest_seconds,status:'unreviewed'}))})),
    raster_performed:req.raster,joins,visual_review_performed:false,attribution:'Unresolved nonlinear/overlap/source-follower attribution; global frame change cannot satisfy character or environmental action.'};
  await fs.writeFile(path.join(out,'activity-report.json'),json(report));
  return {ok:true,report:path.join(out,'activity-report.json'),report_sha256:sha(json(report)),proof:req.raster?path.join(out,'index.html'):null,summary:report.summary,performance:report.performance};
}
try{console.log(JSON.stringify(await main()));}catch(error){console.log(JSON.stringify({ok:false,error:error.message}));process.exitCode=1;}
