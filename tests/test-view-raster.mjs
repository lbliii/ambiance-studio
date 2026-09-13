import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import os from 'node:os';
import path from 'node:path';
import {compileScene,drawScene} from '../editor/engine.mjs';
import {planViews} from '../editor/views.mjs';
import {createStageRenderer} from '../editor/stage-raster.mjs';
import {auditViewPixels,inspectAlpha} from '../editor/audit.mjs';
import {movingFixture} from '../examples/views/moving-fixture.mjs';
const require=createRequire(import.meta.url);
let runtime;for(const p of [process.env.AMBIANCE_CANVAS_MODULE,'@napi-rs/canvas',path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@napi-rs/canvas')].filter(Boolean))try{runtime=require(p);break;}catch{}
if(!runtime)throw Error('Node Canvas required for view raster tests');
const {createCanvas}=runtime,checks=[];
const pixels=canvas=>Buffer.from(canvas.getContext('2d').getImageData(0,0,canvas.width,canvas.height).data);
const test=async(name,fn)=>{await fn();checks.push(name);};
await test('Coverage and finished pixels are independent of render order at every supported supersampling scale',()=>{
  const f=movingFixture(createCanvas);
  f.scene.camera={overscan:1,x_amplitude:0,y_amplitude:0,zoom_amplitude:0};
  f.scene.layers[0].width=f.scene.layers[0].height=1;
  const room=f.images.get('room').getContext('2d');room.clearRect(72,16,8,8);room.clearRect(88,0,8,1);
  const source=JSON.stringify(f.scene),times=[0,.125,.625],modes=[true,false];
  for(const finishing of [true,false])for(const supersample of [1,2,4]){
    const scene=structuredClone(f.scene);if(!finishing)delete scene.finishing;
    const plan=planViews(scene,[{id:'portrait'},{id:'landscape'}],{long_edge:160,supersample});
    const make=()=>createStageRenderer(scene,f.catalog,f.images,plan,createCanvas);
    const canvases=r=>new Map([['stage',r.stage],...r.outputs]);
    const reference=new Map();
    for(const coverage of modes)for(const time of times){
      const fresh=make();fresh.render(time,{coverage});
      reference.set(`${coverage}/${time}`,new Map([...canvases(fresh)].map(([id,c])=>[id,pixels(c)])));
    }
    const sequences=[
      // The retained failing sequence, followed by a repeated identical call.
      [[true,0],[false,0],[true,.125],[true,.125]],
      times.toReversed().flatMap(t=>[[true,t],[false,t],[false,t],[true,t]]),
      modes.flatMap(c=>[.625,0,.125,0].map(t=>[c,t])),
      modes.toReversed().flatMap(c=>[.125,.625,0].map(t=>[c,t]))
    ];
    for(const [sequence,steps] of sequences.entries()){
      const renderer=make();
      for(const [coverage,time] of steps){
        renderer.render(time,{coverage});
        for(const [id,canvas] of canvases(renderer))assert(pixels(canvas).equals(reference.get(`${coverage}/${time}`).get(id)),
          `${id}: finishing=${finishing}, supersample=${supersample}, sequence=${sequence}, coverage=${coverage}, time=${time}`);
      }
    }
    // These modes intentionally differ: coverage keeps paint holes, beauty fills them.
    assert(!reference.get('true/0').get('portrait').equals(reference.get('false/0').get('portrait')));
  }
  assert.equal(JSON.stringify(f.scene),source);
});
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
await test('Alpha localization retains the measured worst raster and leaves the default audit unchanged',async()=>{
  const f=movingFixture(createCanvas);f.scene.camera={overscan:1,x_amplitude:0,y_amplitude:0,zoom_amplitude:0};
  f.scene.layers[0].width=f.scene.layers[0].height=1;
  const room=f.images.get('room').getContext('2d');room.clearRect(72,16,8,8);room.clearRect(88,0,8,1);
  const source=JSON.stringify(f.scene),plan=planViews(f.scene,[{id:'portrait'},{id:'landscape'}],{long_edge:160});
  const before=await auditViewPixels(f.scene,f.catalog,f.images,['portrait','landscape'],createCanvas,()=>{},plan),saved=[];
  const report=await auditViewPixels(f.scene,f.catalog,f.images,['portrait','landscape'],createCanvas,()=>{},plan,
    {onAlphaDiagnostic:(metadata,canvas)=>saved.push({metadata,data:pixels(canvas)})});
  assert.deepEqual(report,before);assert.equal(JSON.stringify(f.scene),source);assert.equal(saved.length,1);
  const {metadata,data}=saved[0],row=report.views.portrait;
  assert.equal(metadata.view_id,'portrait');assert.equal(metadata.frame,row.worst_frame);
  assert.equal(metadata.time_seconds,metadata.frame/f.scene.canvas.fps);assert.deepEqual(metadata.view.rect_scene_px,[35,0,90,160]);
  assert.deepEqual(metadata.resolution,[90,160]);assert.equal(metadata.alpha.threshold,254);
  assert.equal(metadata.alpha.all.count,row.max_uncovered_pixels);
  assert(metadata.alpha.interior.count>0);assert(metadata.alpha.boundary.count>0);
  const renderer=createStageRenderer(f.scene,f.catalog,f.images,report.raster_plan,createCanvas);
  // Compare the actual alternating audit sequence and an independent fresh seek.
  for(let frame=0;frame<metadata.frame;frame++){renderer.render(frame/f.scene.canvas.fps,{coverage:true});renderer.render(frame/f.scene.canvas.fps);}
  renderer.render(metadata.time_seconds,{coverage:true});
  const measured=pixels(renderer.outputs.get('portrait'));
  assert(data.equals(measured),'Saved data must be the exact pre-background measured raster');
  const fresh=createStageRenderer(f.scene,f.catalog,f.images,report.raster_plan,createCanvas);
  fresh.render(metadata.time_seconds,{coverage:true});
  assert(data.equals(pixels(fresh.outputs.get('portrait'))),'Saved coverage must also match a fresh seek');
  renderer.render(metadata.time_seconds);
  assert([...pixels(renderer.outputs.get('portrait'))].filter((_,i)=>i%4===3).every(alpha=>alpha===255));
  assert.equal(report.views.landscape.ok,true);
});
await test('Boundary filtering classifies all four edges without suppressing interior or threshold failures',()=>{
  const width=5,height=5,data=new Uint8ClampedArray(width*height*4).fill(255);
  for(const [x,y,alpha] of [[0,2,0],[2,0,253],[4,2,127],[2,4,252],[2,2,253],[1,1,254]])data[(y*width+x)*4+3]=alpha;
  const result=inspectAlpha(data,width,height,{sampleLimit:1});
  assert.equal(result.all.count,5);assert.equal(result.boundary.count,4);assert.equal(result.interior.count,1);
  assert.deepEqual(result.interior.bounds,[2,2,1,1]);assert.deepEqual(result.interior.samples,[{x:2,y:2,alpha:253}]);
  assert.deepEqual(result.all.bounds,[0,0,5,5]);assert.equal(result.all.min_alpha,0);
  assert(result.all.samples_truncated);assert(result.boundary.samples_truncated);assert(!result.interior.samples_truncated);
  const noBoundary=inspectAlpha(data,width,height,{boundaryPixels:0});
  assert.equal(noBoundary.all.count,result.all.count);assert.equal(noBoundary.interior.count,5);assert.equal(noBoundary.boundary.count,0);
  const tiny=inspectAlpha(new Uint8ClampedArray(4),1,1);assert.equal(tiny.boundary.count,1);assert.equal(tiny.interior.count,0);
  assert.throws(()=>inspectAlpha(data,4,5),/dimensions/);assert.throws(()=>inspectAlpha(data,5,5,{sampleLimit:257}),/limits/);
});
await test('A perimeter-only alpha failure remains failing with diagnostics enabled',async()=>{
  const f=movingFixture(createCanvas);f.scene.layers=f.scene.layers.slice(0,1);delete f.scene.finishing;
  f.scene.camera={overscan:1,x_amplitude:0,y_amplitude:0,zoom_amplitude:0};f.scene.layers[0].width=f.scene.layers[0].height=1;
  f.scene.canvas.fps=1;f.scene.canvas.loop_seconds=1;
  // A small inset produces a below-threshold perimeter fringe; the next row
  // stays covered at this raster size and declared threshold.
  f.scene.layers[0].y+=.05/160;
  const plan=planViews(f.scene,[{id:'portrait'}],{long_edge:160}),saved=[];
  const report=await auditViewPixels(f.scene,f.catalog,f.images,['portrait'],createCanvas,()=>{},plan,
    {onAlphaDiagnostic:metadata=>saved.push(metadata)});
  assert.equal(saved[0].alpha.interior.count,0);assert.equal(saved[0].alpha.boundary.count,90);
  assert.equal(report.ok,false);assert.equal(report.views.portrait.uncovered_frames,1);
});
console.log(JSON.stringify({ok:true,checks},null,2));
