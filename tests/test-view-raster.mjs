import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import os from 'node:os';
import path from 'node:path';
import {compileScene,drawScene} from '../editor/engine.mjs';
import {planViews} from '../editor/views.mjs';
import {createStageRenderer} from '../editor/stage-raster.mjs';
import {auditViewPixels} from '../editor/audit.mjs';
import {movingFixture} from '../examples/views/moving-fixture.mjs';
const require=createRequire(import.meta.url);
let runtime;for(const p of [process.env.AMBIANCE_CANVAS_MODULE,'@napi-rs/canvas',path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@napi-rs/canvas')].filter(Boolean))try{runtime=require(p);break;}catch{}
if(!runtime)throw Error('Node Canvas required for view raster tests');
const {createCanvas}=runtime,checks=[];
const pixels=canvas=>Buffer.from(canvas.getContext('2d').getImageData(0,0,canvas.width,canvas.height).data);
const test=async(name,fn)=>{await fn();checks.push(name);};
await test('Paired finished crops match an independently specified stage at every frame and supersampling scale',()=>{
  const {scene,catalog,images}=movingFixture(createCanvas),before=JSON.stringify(scene);
  for(const supersample of [1,2]){
    const plan=planViews(scene,[{id:'portrait'},{id:'landscape'}],{long_edge:160,supersample});
    const renderer=createStageRenderer(scene,catalog,images,plan,createCanvas);
    // Reference bypasses both the view resolver and the stage adapter.
    const reference=structuredClone(scene);delete reference.framing;reference.canvas.width=reference.canvas.height=160*supersample;
    const compiled=compileScene(reference,catalog),stage=createCanvas(160*supersample,160*supersample);
    for(const time of [...Array.from({length:16},(_,n)=>n/8),2,-.25,.25]){
      renderer.render(time);drawScene(stage,reference,catalog,images,time,{sampler:compiled.sample,createCanvas});
      for(const [id,rect,width,height] of [['portrait',[35,0,90,160],90,160],['landscape',[0,35,160,90],160,90]]){
        const target=createCanvas(width,height),ctx=target.getContext('2d');ctx.imageSmoothingEnabled=true;ctx.imageSmoothingQuality='high';
        ctx.drawImage(stage,...rect.map(n=>n*supersample),0,0,width,height);
        assert.deepEqual(pixels(renderer.outputs.get(id)),pixels(target),`${id} at ${time}, scale ${supersample}`);
      }
    }
  }
  assert.equal(JSON.stringify(scene),before);
});
await test('Fractional crop coordinates reach the raster unchanged',()=>{
  const {scene,catalog,images}=movingFixture(createCanvas);
  scene.framing.views.landscape.rect_scene_px=[0,35.125,160,90];
  const renderer=createStageRenderer(scene,catalog,images,planViews(scene,[{id:'landscape',width:160,height:90}]),createCanvas);
  renderer.render(.625);
  const expected=createCanvas(160,90),ctx=expected.getContext('2d');ctx.imageSmoothingEnabled=true;ctx.imageSmoothingQuality='high';
  const reference=structuredClone(scene);delete reference.framing;
  const stage=createCanvas(160,160);drawScene(stage,reference,catalog,images,.625,{createCanvas});
  ctx.drawImage(stage,0,35.125,160,90,0,0,160,90);
  assert.deepEqual(pixels(renderer.outputs.get('landscape')),pixels(expected));
});
await test('Transparent art hole is attributed only to the view exposing it, despite opaque background and finishing',async()=>{
  const f=movingFixture(createCanvas);f.scene.camera={overscan:1,x_amplitude:0,y_amplitude:0,zoom_amplitude:0};
  f.scene.layers[0].width=f.scene.layers[0].height=1;
  f.images.get('room').getContext('2d').clearRect(70,0,20,12);
  const report=await auditViewPixels(f.scene,f.catalog,f.images,['portrait','landscape'],createCanvas);
  assert.equal(report.views.portrait.uncovered_frames,16);assert.equal(report.views.landscape.uncovered_frames,0);assert.equal(report.ok,false);
});
console.log(JSON.stringify({ok:true,checks},null,2));
