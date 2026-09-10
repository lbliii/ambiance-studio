// Declarative inspection only: variants never replace the authored scene.
import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {compileScene,drawScene} from '../editor/engine.mjs';
const sha=data=>createHash('sha256').update(data).digest('hex');
const identifier=value=>typeof value==='string'&&/^[a-zA-Z0-9][a-zA-Z0-9_-]*$/.test(value);
const escape=value=>String(value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
function keysOnly(object,allowed,label){if(!object||typeof object!=='object'||Array.isArray(object)||Object.keys(object).some(key=>!allowed.includes(key)))throw Error(`Unsupported ${label} fields`);}

export function prepareRigProof(recipe,scene,catalog){
  keysOnly(recipe,['version','title','inventory','part_ids','samples','regions','comparisons','playback_seconds'],'rig-proof recipe');
  if(recipe.version!==1||!Array.isArray(recipe.samples)||!recipe.samples.length)throw Error('Rig proof requires version 1 and explicit samples');
  if(recipe.part_ids!==undefined&&(!Array.isArray(recipe.part_ids)||recipe.part_ids.some(id=>typeof id!=='string')))throw Error('part_ids must be existing inventory ID strings');
  const ids=new Set(),variants=[];
  for(const sample of recipe.samples){
    keysOnly(sample,['id','label','time','overrides'],'rig-proof sample');
    if(!identifier(sample.id)||ids.has(sample.id))throw Error('Rig-proof sample IDs must be unique safe identifiers');ids.add(sample.id);
    if(!Number.isFinite(sample.time)||sample.time<0||sample.time>=scene.canvas.loop_seconds)throw Error(`Sample time must be within [0, scene loop): ${sample.id}`);
    const variant=structuredClone(scene),overrides=sample.overrides??{};
    if(!overrides||typeof overrides!=='object'||Array.isArray(overrides))throw Error('Sample overrides must map existing layer IDs to property values');
    for(const [layerId,values] of Object.entries(overrides)){
      const layer=variant.layers.find(l=>l.id===layerId);if(!layer)throw Error(`Unknown overridden layer: ${layerId}`);
      keysOnly(values,['x','y','scale','rotation','opacity','visible','cell'],`override ${layerId}`);
      for(const [key,value] of Object.entries(values)){
        if(key==='visible'?typeof value!=='boolean':!Number.isFinite(value))throw Error(`Invalid override value: ${layerId}.${key}`);
        // A forced state must survive the authored track. Constant replacement
        // keys retain hidden-reset validation and shared evaluator semantics.
        if(layer.tracks?.[key]||key==='cell'){
          layer.tracks??={};layer.tracks[key]={interpolation:['visible','cell'].includes(key)?'hold':'linear',keys:[[0,value],[scene.canvas.loop_seconds,value]]};
        }else layer[key]=value;
        if(layer.motion&&['x','y','rotation'].includes(key))layer.motion[key==='rotation'?'rotation_amplitude':`${key}_amplitude`]=0;
      }
    }
    const compiled=compileScene(variant,catalog),states=compiled.sample(sample.time),hidden=states.filter(s=>!s.visible).map(s=>s.id);
    const explicitlyHidden=Object.entries(overrides).filter(([,v])=>v.visible===false).map(([id])=>id);
    const descendants=[];
    for(const layer of variant.layers){let parent=layer.attach?.layer;while(parent){if(explicitlyHidden.includes(parent)){descendants.push({layer:layer.id,hidden_by:parent});break;}parent=variant.layers.find(l=>l.id===parent)?.attach?.layer;}}
    variants.push({sample,scene:variant,compiled,hidden_layers:hidden,zero_opacity_layers:states.filter(s=>s.opacity===0).map(s=>s.id),explicitly_hidden_layers:explicitlyHidden,hidden_descendants:descendants});
  }
  const regions=recipe.regions??[],regionIds=new Set();
  if(!Array.isArray(regions))throw Error('Rig-proof regions must be an array');
  for(const region of regions){
    keysOnly(region,['id','label','rect'],'comparison region');
    const r=region.rect;
    if(!identifier(region.id)||regionIds.has(region.id)||!Array.isArray(r)||r.length!==4||!r.every(Number.isFinite)||r[0]<0||r[1]<0||r[2]<=0||r[3]<=0||r[0]+r[2]>1||r[1]+r[3]>1)throw Error('Regions require unique IDs and normalized rectangles fully within the frame');regionIds.add(region.id);
  }
  const comparisons=recipe.comparisons??[],comparisonIds=new Set();
  if(!Array.isArray(comparisons))throw Error('Rig-proof comparisons must be an array');
  for(const comparison of comparisons){
    keysOnly(comparison,['id','left','right','difference','difference_gain'],'comparison');
    if(!identifier(comparison.id)||comparisonIds.has(comparison.id)||!ids.has(comparison.left)||!ids.has(comparison.right))throw Error('Comparison IDs must be unique and left/right must name samples');comparisonIds.add(comparison.id);
    if(comparison.difference!==undefined&&typeof comparison.difference!=='boolean')throw Error('comparison.difference must be boolean');
    if(comparison.difference_gain!==undefined&&(!Number.isFinite(comparison.difference_gain)||comparison.difference_gain<=0||comparison.difference_gain>32))throw Error('Difference display gain must be in (0,32]');
  }
  const seconds=recipe.playback_seconds??0,frames=seconds*scene.canvas.fps;
  if(!Number.isFinite(seconds)||seconds<0||seconds>scene.canvas.loop_seconds||!Number.isInteger(frames))throw Error('Playback seconds must be an integer frame duration within one scene loop');
  if(frames*variants.length>5000)throw Error('Rig proof exceeds 5000 playback frames; request a shorter targeted proof');
  return {recipe,variants,regions,comparisons,playback_frames:frames};
}

export async function renderRigProof(plan,{out,runtime,catalog,images,width,height,htmlProof}){
  const outputs=[],contexts=new Map(),samples=[],comparisons=[];
  const save=async(name,canvas)=>{const bytes=canvas.toBuffer('image/png'),destination=path.join(out,name);await fs.mkdir(path.dirname(destination),{recursive:true});await fs.writeFile(destination,bytes,{flag:'wx'});const result={file:name,sha256:sha(bytes),width:canvas.width,height:canvas.height};outputs.push(result);return result;};
  const crop=(canvas,region)=>{const [x,y,w,h]=region.rect,px=Math.floor(x*width),py=Math.floor(y*height),pw=Math.min(width-px,Math.ceil(w*width)),ph=Math.min(height-py,Math.ceil(h*height));const result=runtime.createCanvas(pw,ph);result.getContext('2d').drawImage(canvas,px,py,pw,ph,0,0,pw,ph);return result;};
  for(const variant of plan.variants){
    const canvas=runtime.createCanvas(width,height);drawScene(canvas,variant.scene,catalog,images,variant.sample.time,{sampler:variant.compiled.sample});contexts.set(variant.sample.id,canvas);
    const prefix=`samples/${variant.sample.id}`;
    const context=await save(`${prefix}/context.png`,canvas),details=[];
    for(const region of plan.regions)details.push({region:region.id,...await save(`${prefix}/regions/${region.id}.png`,crop(canvas,region))});
    samples.push({id:variant.sample.id,label:variant.sample.label??variant.sample.id,time_seconds:variant.sample.time,overrides:variant.sample.overrides??{},hidden_layers:variant.hidden_layers,zero_opacity_layers:variant.zero_opacity_layers,explicitly_hidden_layers:variant.explicitly_hidden_layers,hidden_descendants:variant.hidden_descendants,context,details});
  }
  for(const comparison of plan.comparisons){
    const left=contexts.get(comparison.left),right=contexts.get(comparison.right),pair=runtime.createCanvas(width*2,height);pair.getContext('2d').drawImage(left,0,0);pair.getContext('2d').drawImage(right,width,0);
    const prefix=`comparisons/${comparison.id}`;
    const result={...comparison,context:await save(`${prefix}/context.png`,pair),details:[]};
    for(const region of plan.regions){const a=crop(left,region),b=crop(right,region),combined=runtime.createCanvas(a.width*2,a.height);combined.getContext('2d').drawImage(a,0,0);combined.getContext('2d').drawImage(b,a.width,0);result.details.push({region:region.id,...await save(`${prefix}/regions/${region.id}.png`,combined)});}
    if(comparison.difference){
      const a=left.data(),b=right.data(),difference=runtime.createCanvas(width,height),ctx=difference.getContext('2d'),pixels=ctx.createImageData(width,height),gain=comparison.difference_gain??4;let sum=0,maximum=0,changed=0;
      for(let i=0;i<a.length;i+=4){let pixelChanged=false;for(let c=0;c<3;c++){const d=Math.abs(a[i+c]-b[i+c]);sum+=d;maximum=Math.max(maximum,d);pixelChanged ||= d>0;pixels.data[i+c]=Math.min(255,d*gain);}pixels.data[i+3]=255;if(pixelChanged)changed++;}
      ctx.putImageData(pixels,0,0);result.difference_image=await save(`${prefix}/difference.png`,difference);result.difference_metrics={rgb_mean_absolute_difference:sum/(width*height*3),rgb_max_difference:maximum,changed_pixels:changed,display_gain:gain};
    }
    comparisons.push(result);
  }
  let playback=null;
  if(plan.playback_frames){
    await fs.mkdir(path.join(out,'playback'));const files=[],labels=[];
    for(const variant of plan.variants){
      const dir=`playback/${variant.sample.id}`;await fs.mkdir(path.join(out,dir));const canvas=runtime.createCanvas(width,height),frames=[];
      for(let i=0;i<plan.playback_frames;i++){drawScene(canvas,variant.scene,catalog,images,variant.sample.time+i/variant.scene.canvas.fps,{sampler:variant.compiled.sample});const file=`${String(i).padStart(5,'0')}.png`;await save(`${dir}/${file}`,canvas);frames.push(`${variant.sample.id}/${file}`);}
      files.push(frames);labels.push(`${variant.sample.label??variant.sample.id} · begins at ${variant.sample.time}s`);
    }
    await fs.writeFile(path.join(out,'playback/index.html'),htmlProof(files,plan.variants[0].scene.canvas.fps,width,height,[],labels));playback='playback/index.html';
  }
  const figure=(file,label,full=false)=>`<figure><img src="${escape(file.file)}" alt="${escape(label)}" style="width:${full?width:Math.max(240,file.width)}px;max-width:100%"><figcaption>${escape(label)}</figcaption></figure>`;
  const page=`<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Rig proof</title><style>body{font:16px system-ui;background:#161922;color:#eee;margin:24px}section,.row{display:flex;gap:16px;flex-wrap:wrap}article{border-top:1px solid #556;margin-top:24px}figure{margin:12px 0}img{image-rendering:auto;display:block}figcaption{max-width:60ch;margin:8px 0}a{color:#bcd8ff}pre{white-space:pre-wrap;max-width:90ch}</style><h1>${escape(plan.recipe.title??'Rig proof')}</h1><p>Selected poses and declared overrides. These samples do not certify a full loop, clean backing, or final artwork.</p><p>Inventory parts: ${escape((plan.recipe.part_ids??[]).join(', ')||'No inventory parts selected')}</p>${playback?`<p><a href="${playback}">Play all variants at actual speed</a></p>`:''}<section>${samples.map(s=>`<article><h2>${escape(s.label)} · ${s.time_seconds}s</h2>${figure(s.context,'Full scene context',true)}<p>Hidden layers: ${escape(s.hidden_layers.join(', ')||'none')}</p><p>Zero opacity: ${escape(s.zero_opacity_layers.join(', ')||'none')}</p><p>Hidden descendants: ${escape(s.hidden_descendants.map(d=>`${d.layer} by ${d.hidden_by}`).join(', ')||'none')}</p><div class="row">${s.details.map(d=>figure(d,`Detail: ${d.region}`)).join('')}</div></article>`).join('')}</section>${comparisons.map(c=>`<article><h2>${escape(c.id)}: ${escape(c.left)} / ${escape(c.right)}</h2>${figure(c.context,'Side-by-side full context')}<div class="row">${c.details.map(d=>figure(d,`Comparison detail: ${d.region}`)).join('')}${c.difference_image?figure(c.difference_image,`Absolute RGB difference ×${c.difference_metrics.display_gain}; metrics use unamplified pixels`):''}</div></article>`).join('')}<h2>Saved inspection recipe</h2><pre>${escape(JSON.stringify(plan.recipe,null,2))}</pre></html>`;
  await fs.writeFile(path.join(out,'index.html'),page);await fs.writeFile(path.join(out,'rig-proof-recipe.json'),JSON.stringify(plan.recipe,null,2)+'\n');
  return {samples,comparisons,playback,outputs,selected_samples:plan.variants.length,full_loop_review_performed:false,output:path.join(out,'index.html'),output_sha256:sha(page)};
}
