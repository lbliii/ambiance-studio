import assert from 'node:assert/strict';
import {compileScene,drawScene} from '../editor/engine.mjs';
import {planViews,resizeSceneCanvas} from '../editor/views.mjs';
import {createStageRenderer} from '../editor/stage-raster.mjs';
import {prepareRaster} from '../tools/render/raster.mjs';
import {canvasRuntime} from '../tools/render/canvas-runtime.mjs';
const runtime=canvasRuntime(),{createCanvas}=runtime,checks=[];
const pixels=c=>Buffer.from(c.getContext('2d').getImageData(0,0,c.width,c.height).data);
const art=createCanvas(8,8),ctx=art.getContext('2d');ctx.fillStyle='rgba(60,120,200,0.5)';ctx.fillRect(0,0,8,8);
const images=new Map([['glass',art]]),catalog={version:1,assets:[{id:'glass',file:'glass.png',width:8,height:8}]};
function fixture(background){return {version:1,id:'transparent-repeat',canvas:{width:32,height:32,fps:4,loop_seconds:2,background},
 camera:{overscan:1,x_amplitude:0,y_amplitude:0,zoom_amplitude:0},groups:[],
 framing:{version:1,views:{portrait:{rect_scene_px:[7,0,18,32],output:{width:18,height:32}},landscape:{rect_scene_px:[0,7,32,18],output:{width:32,height:18}}}},
 layers:[{id:'glass',name:'glass',asset:'glass',x:.25,y:.5,width:.25,height:.25,anchor:[.5,.5],scale:1,rotation:0,opacity:1,visible:true,blend:'source-over',depth:0,motion:{x_amplitude:.25,y_amplitude:0,cycles:1,phase:0}}]};}
for(const background of ['rgba(0,0,0,0)','rgba(20,40,60,0.25)','#132840']){
 const scene=fixture(background),compiled=compileScene(scene,catalog),canvas=createCanvas(32,32);
 for(const time of [0,0,2,.5,0,1.25,.5]){
  const fresh=createCanvas(32,32);drawScene(fresh,scene,catalog,images,time,{sampler:compiled.sample,createCanvas});
  drawScene(canvas,scene,catalog,images,time,{sampler:compiled.sample,createCanvas});
  assert(pixels(canvas).equals(pixels(fresh)),`drawScene retained earlier pixels: background=${background}, time=${time}`);
 }
}
checks.push('Transparent, translucent and opaque backgrounds preserve fresh pixels under repeated, endpoint and out-of-order drawScene calls');
for(const background of ['rgba(0,0,0,0)','rgba(20,40,60,0.25)','#132840'])for(const supersample of [1,2,4]){
 const original=fixture(background),plan=planViews(original,[{id:'portrait'},{id:'landscape'}],{long_edge:32,supersample});
 const stage=createStageRenderer(original,catalog,images,plan,createCanvas);
 for(const [coverage,time] of [[true,0],[false,0],[false,0],[true,.5],[false,.5],[false,0],[false,2]]){
  const fresh=createStageRenderer(original,catalog,images,plan,createCanvas);fresh.render(time,{coverage});stage.render(time,{coverage});
  for(const id of ['portrait','landscape'])assert(pixels(stage.outputs.get(id)).equals(pixels(fresh.outputs.get(id))),`${id}, background=${background}, scale=${supersample}, coverage=${coverage}, time=${time}`);
 }
 for(const useView of [false,true]){
  const scene=structuredClone(original);if(!useView)resizeSceneCanvas(scene,32*supersample,32*supersample);
  const alternate=structuredClone(scene);alternate.layers[0].visible=false;
  const viewPlan=useView?plan:null,width=useView?18:32,height=32;
  const job={scene,catalog,viewPlan,width,height,supersample,internalWidth:32*supersample,internalHeight:32*supersample,
   compiled:compileScene(scene,catalog),fps:4,loopFrames:8,disable:['glass'],alternate,alternateCompiled:compileScene(alternate,catalog),images,runtime};
  // prepareRaster itself samples first/endpoint/last and must not fail its endpoint gate.
  const raster=prepareRaster(job);raster.render(0);const first=pixels(raster.canvas);
  raster.render(.5);raster.render(0);assert(pixels(raster.canvas).equals(first));
  raster.render(0,true);const hidden=pixels(raster.canvas);assert(!hidden.equals(first));
  raster.render(.5);raster.render(0,true);assert(pixels(raster.canvas).equals(hidden));
  raster.render(2);assert(pixels(raster.canvas).equals(first));
 }
}
checks.push('Transparent/translucent/opaque stage views and raster endpoint/disabled variants stay stable at supersampling 1/2/4');
console.log(JSON.stringify({ok:true,checks},null,2));
