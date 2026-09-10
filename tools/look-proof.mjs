// Portable, immutable look-development artifact using the exact shared renderer.
import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {compileScene,drawScene} from '../editor/engine.mjs';
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const safe=value=>typeof value==='string'&&/^[A-Za-z0-9][A-Za-z0-9_-]*$/.test(value);
const esc=value=>String(value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
function only(value,allowed,label){if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).some(k=>!allowed.includes(k)))throw Error(`Unsupported ${label} fields`);}
export function prepareLookProof(recipe,scene,catalog){
  only(recipe,['version','title','time','finishing','variants','selected_layer','scope'],'look-proof recipe');
  if(recipe.version!==1)throw Error('Look proof requires version 1');
  const time=recipe.time??0;if(!Number.isFinite(time)||time<0||time>=scene.canvas.loop_seconds)throw Error('Look sample time must be within [0, scene loop)');
  if(recipe.title!==undefined&&typeof recipe.title!=='string'||recipe.scope!==undefined&&typeof recipe.scope!=='string')throw Error('Look title and scope must be text');
  if(recipe.selected_layer!==undefined&&!scene.layers.some(l=>l.id===recipe.selected_layer))throw Error('Look selected_layer must exist in scene');
  if(recipe.variants!==undefined&&(!Array.isArray(recipe.variants)||recipe.variants.length>12))throw Error('Look variants must be an array with at most 12 named configurations');
  const specs=[{id:'baseline',label:'Saved scene',finishing:scene.finishing??null},{id:'current',label:'Candidate',finishing:recipe.finishing===undefined?(scene.finishing??null):recipe.finishing},...(recipe.variants??[])];
  const ids=new Set();const variants=specs.map(spec=>{
    only(spec,['id','label','finishing'],'look variant');
    if(!safe(spec.id)||ids.has(spec.id)||!Object.hasOwn(spec,'finishing'))throw Error('Look variants need unique safe IDs and explicit finishing');ids.add(spec.id);
    if(spec.label!==undefined&&typeof spec.label!=='string')throw Error('Look variant label must be text');
    const copy=structuredClone(scene);if(spec.finishing===null)delete copy.finishing;else copy.finishing=structuredClone(spec.finishing);
    return {...spec,scene:copy,compiled:compileScene(copy,catalog)};
  });
  return {recipe,time,variants};
}
async function moduleGraph(root,out,entry){
  const files=[],visited=new Set(),editor=path.join(root,'editor');
  async function visit(relative){
    if(visited.has(relative))return;visited.add(relative);
    const source=path.resolve(editor,relative);if(!source.startsWith(editor+path.sep))throw Error('Look module graph must remain inside shared editor');
    const bytes=await fs.readFile(source),text=bytes.toString('utf8');
    const refs=[...text.matchAll(/(?:import|export)\s+(?:[^'";]*?\s+from\s*)?['"]([^'"]+)['"]/g)].map(m=>m[1]);
    for(const ref of refs){if(!ref.startsWith('.'))throw Error(`Look workbench requires local browser modules: ${ref}`);await visit(path.normalize(path.join(path.dirname(relative),ref)));}
    const file=`modules/${relative}`,destination=path.join(out,file);await fs.mkdir(path.dirname(destination),{recursive:true});await fs.writeFile(destination,bytes,{flag:'wx'});files.push({file,sha256:sha(bytes),bytes:bytes.length});
  }
  await visit(entry);return files;
}
export async function renderLookProof(plan,{out,root,runtime,catalog,images,assetBytes,width,height,supersample,sourceScene,sceneHash,catalogHash}){
  const runtimeCatalog={version:catalog.version,assets:[]},outputs=[],variants=[];
  await fs.mkdir(path.join(out,'assets'));await fs.mkdir(path.join(out,'samples'));
  for(const asset of catalog.assets.filter(a=>assetBytes.has(a.id))){const bytes=assetBytes.get(asset.id),file=`assets/${sha(bytes)}${path.extname(asset.file).toLowerCase()||'.png'}`;try{await fs.writeFile(path.join(out,file),bytes,{flag:'wx'});}catch(error){if(error.code!=='EEXIST')throw error;}runtimeCatalog.assets.push({...structuredClone(asset),file});}
  for(const variant of plan.variants){
    const internal=runtime.createCanvas(width*supersample,height*supersample);drawScene(internal,variant.scene,catalog,images,plan.time,{sampler:variant.compiled.sample,createCanvas:runtime.createCanvas});
    const canvas=supersample===1?internal:runtime.createCanvas(width,height);if(supersample!==1){const ctx=canvas.getContext('2d');ctx.imageSmoothingEnabled=true;ctx.imageSmoothingQuality='high';ctx.drawImage(internal,0,0,width,height);}
    const bytes=canvas.toBuffer('image/png'),file=`samples/${variant.id}.png`;await fs.writeFile(path.join(out,file),bytes,{flag:'wx'});outputs.push({file,sha256:sha(bytes),width,height,finishing_diagnostics:internal.finishingReport??null});variants.push({id:variant.id,label:variant.label??variant.id,finishing:variant.finishing,sample:file});
  }
  const modules=await moduleGraph(root,out,'look-workbench.mjs');
  const payload={version:1,title:plan.recipe.title??'Ambiance look workbench',scope:plan.recipe.scope??'Selected look sample and interactive preview',time:plan.time,width,height,supersample,scene_sha256:sceneHash,catalog_sha256:catalogHash,selected_layer:plan.recipe.selected_layer??sourceScene.layers[0]?.id,scene:sourceScene,catalog:runtimeCatalog,variants,modules};
  const data=JSON.stringify(payload,null,2)+'\n';await fs.writeFile(path.join(out,'workbench.json'),data,{flag:'wx'});await fs.writeFile(path.join(out,'look-proof-recipe.json'),JSON.stringify(plan.recipe,null,2)+'\n',{flag:'wx'});
  const html=`<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${esc(payload.title)}</title><link rel="stylesheet" href="workbench.css"><main id="workbench"><p>Loading saved scene and assets…</p></main><script type="module" src="modules/look-workbench.mjs"></script></html>`;
  const css=await fs.readFile(path.join(root,'editor/look-workbench.css'));
  await fs.writeFile(path.join(out,'index.html'),html,{flag:'wx'});await fs.writeFile(path.join(out,'workbench.css'),css,{flag:'wx'});
  return {output:path.join(out,'index.html'),output_sha256:sha(html),saved_sample_frames:outputs.length,samples:outputs,workbench:{data:'workbench.json',sha256:sha(data),stylesheet_sha256:sha(css),modules,asset_snapshots:runtimeCatalog.assets.map(a=>({id:a.id,file:a.file,sha256:a.sha256})),source_scene_sha256:sceneHash,source_catalog_sha256:catalogHash,writes:'Browser memory and explicit JSON download only; no project writes',serve:'Serve this directory with a local static HTTP server; file:// module loading is not supported'},visual_review_performed:false,full_loop_review_performed:false};
}
