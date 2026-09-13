import fs from 'node:fs/promises';
import path from 'node:path';
import {createRequire} from 'node:module';
import {lower} from './lower.mjs';
import {compileScene,drawScene,multiply,translation} from '../../editor/engine.mjs';
import {canvasRuntime} from '../render/canvas-runtime.mjs';
import {prepareRigProof,renderRigProof} from '../rig-proof.mjs';
import {prepareRaster} from '../render/raster.mjs';
import {htmlProof} from '../render/proof-page.mjs';
import {sha} from '../render/source-identity.mjs';
async function runtimeIdentity(runtime) {
  const require=createRequire(import.meta.url),nativeFiles=Object.keys(require.cache).filter(file=>file.endsWith('.node'));
  const natives=[];for(const file of nativeFiles)natives.push({name:path.basename(file),sha256:sha(await fs.readFile(file))});
  return {node:process.version,canvas_version:runtime.version,module_sha256:sha(await fs.readFile(runtime.module)),native_modules:natives.sort((a,b)=>a.name.localeCompare(b.name))};
}
const request=JSON.parse(await new Promise(resolve=>{let s='';process.stdin.on('data',b=>s+=b);process.stdin.on('end',()=>resolve(s));}));
try {
  if(request.action==='lower')console.log(JSON.stringify({ok:true,...lower(request,request.state)}));
  else if(request.action==='runtime') {const runtime=canvasRuntime();console.log(JSON.stringify({ok:true,...await runtimeIdentity(runtime)}));}
  else if(request.action==='proof') {
    const runtime=canvasRuntime(),samples=[],out=request.out;
    for(const state of request.recipe.states){const resolved=lower(request,state),{scene,catalog}=resolved,W=scene.canvas.width,H=scene.canvas.height,images=new Map();
      for(const a of catalog.assets)images.set(a.id,await runtime.loadImage(path.join(request.source_root,a.file)));
      const compiled=compileScene(scene,catalog),sampleDir=path.join(out,state.pose_id);await fs.mkdir(sampleDir);
      const raster=prepareRaster({scene,catalog,viewPlan:null,width:W,height:H,supersample:1,internalWidth:W,internalHeight:H,compiled,fps:1,loopFrames:1,disable:[],alternate:scene,alternateCompiled:compiled,images,runtime});
      const rig=prepareRigProof({version:1,title:state.pose_id,samples:[{id:'static',time:0}]},scene,catalog);
      const report=await renderRigProof(rig,{out:sampleDir,runtime,catalog,images,width:W,height:H,htmlProof});
      const evaluated=compiled.sample(0),roles={};
      const sourceImages=new Map(),sourceRows=[];
      const sourceStates=[];
      for(const s of evaluated){const a=catalog.assets.find(a=>a.id===s.asset),registration=a.registration_mapping,cel=registration.cels[s.cell],input=registration.input_sources[cel.source_index];
        const file=path.normalize(path.join(path.dirname(a.provenance.recipe),input.file));
        sourceImages.set(s.asset,await runtime.loadImage(path.join(request.source_root,file)));
        const r=cel.source_rect,rect=[r[0],r[1],r[2]-r[0],r[3]-r[1]];
        const sourceToWorld=multiply(multiply(s.matrix,translation(s.rect[0],s.rect[1])),cel.source_to_cell);
        sourceStates.push({...s,matrix:sourceToWorld,source:rect,rect});
        sourceRows.push({layer_id:s.id,file,sha256:input.sha256,source_rect:r,source_to_model:sourceToWorld});
      }
      const sourceCanvas=runtime.createCanvas(W,H);drawScene(sourceCanvas,scene,catalog,sourceImages,0,{sampler:()=>sourceStates,createCanvas:runtime.createCanvas});
      const sourceBytes=sourceCanvas.toBuffer('image/png');await fs.writeFile(path.join(sampleDir,'source.png'),sourceBytes,{flag:'wx'});
      const assembly=runtime.createCanvas(W,H);drawScene(assembly,scene,catalog,images,0,{sampler:()=>evaluated,createCanvas:runtime.createCanvas});
      const pair=runtime.createCanvas(W*2,H),pairCtx=pair.getContext('2d');pairCtx.drawImage(sourceCanvas,0,0);pairCtx.drawImage(assembly,W,0);
      const pairBytes=pair.toBuffer('image/png');await fs.writeFile(path.join(sampleDir,'source-versus-assembly.png'),pairBytes,{flag:'wx'});
      const raw=sourceCanvas.getContext('2d').getImageData(0,0,W,H).data,prepared=assembly.getContext('2d').getImageData(0,0,W,H).data;let difference=0,maximum=0;
      for(let i=0;i<raw.length;i++){const delta=Math.abs(raw[i]-prepared[i]);difference+=delta;maximum=Math.max(maximum,delta);}
      const sourceComparison={sources:sourceRows,source:{file:'source.png',sha256:sha(sourceBytes)},pair:{file:'source-versus-assembly.png',sha256:sha(pairBytes)},rgba_mean_absolute_difference:difference/raw.length,rgba_maximum_difference:maximum,meaning:'Original input art versus compiled assembly through the same evaluated transforms and drawScene. Resampling differences are diagnostic, not an artistic verdict.'};
      for(const role of ['composite',...request.recipe.roles]){
        const included=resolved.mapping.filter(m=>role==='composite'||m.material_role===role).map(m=>m.layer_id);
        // Filter evaluated states, never hide a parent: excluded paint still supplies mounts.
        const canvas=runtime.createCanvas(W,H);drawScene(canvas,scene,catalog,images,0,{sampler:()=>evaluated.filter(s=>included.includes(s.id)),createCanvas:runtime.createCanvas});
        const bytes=canvas.toBuffer('image/png'),file=role+'.png';await fs.writeFile(path.join(sampleDir,file),bytes,{flag:'wx'});
        const ctx=canvas.getContext('2d'),data=ctx.getImageData(0,0,W,H),mask=runtime.createCanvas(W,H),mc=mask.getContext('2d'),md=mc.createImageData(W,H);let minX=W,minY=H,maxX=-1,maxY=-1,covered=0,partial=0;
        for(let y=0;y<H;y++)for(let x=0;x<W;x++){const i=(y*W+x)*4,a=data.data[i+3];if(a>0&&a<255)partial++;const yes=a>=request.recipe.threshold;if(yes){minX=Math.min(minX,x);minY=Math.min(minY,y);maxX=Math.max(maxX,x);maxY=Math.max(maxY,y);covered++;}md.data[i]=md.data[i+1]=md.data[i+2]=255;md.data[i+3]=yes?255:0;}
        mc.putImageData(md,0,0);const maskBytes=mask.toBuffer('image/png'),maskFile=role+'-mask.png';await fs.writeFile(path.join(sampleDir,maskFile),maskBytes,{flag:'wx'});
        roles[role]={included_leaves:included,excluded_leaves:resolved.mapping.filter(m=>!included.includes(m.layer_id)).map(m=>m.layer_id),visible_leaves:included.filter(id=>resolved.selected_leaves.includes(id)),rgba:{file,sha256:sha(bytes)},mask:{file:maskFile,sha256:sha(maskBytes)},bounds:covered?[minX,minY,maxX+1,maxY+1]:null,covered_pixels:covered,partial_alpha_pixels:partial,threshold:request.recipe.threshold,empty_mask:'transparent; bounds null',crop_to_local:[1,0,0,1,0,0],resolution:[W,H]};
      }
      await fs.writeFile(path.join(sampleDir,'resolved.json'),JSON.stringify(resolved,null,2)+'\n');
      samples.push({pose_id:state.pose_id,resolved,roles,source_comparison:sourceComparison,rig_proof:report.samples,rgba_endpoint_exact:raster.endpointDifference.rgb_max_difference===0,source_receiver_links:[],limitations:['Local static model only; no receiver contribution or scene removal evidence.','Output clips to the declared local frame; bounds describe this raster only.']});
    }
    console.log(JSON.stringify({ok:true,samples,runtime:await runtimeIdentity(runtime)}));
  } else throw Error('Unknown model bridge operation');
} catch(error) {console.log(JSON.stringify({ok:false,error:error.message}));process.exitCode=2;}
