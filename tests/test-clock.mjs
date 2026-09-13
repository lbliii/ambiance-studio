import assert from 'node:assert/strict';
import fs from 'node:fs';
import {compileScene,drawScene,point,validateScene} from '../editor/engine.mjs';
import {compileClock,consumerTime,framesToSamples,samplesToFrames,roundRational,secondsToFrames} from '../editor/clock.mjs';
import {sceneTiming} from '../editor/timing.mjs';
import {reparentAtTime} from '../editor/source-placement.mjs';
import {auditScene} from '../editor/audit.mjs';
import {finishingDiagnostics} from '../editor/finishing.mjs';
import {canvasRuntime} from '../tools/render/canvas-runtime.mjs';
const packet=JSON.parse(fs.readFileSync(new URL('./fixtures/model-contract/clock-cues.json',import.meta.url)));
const checks=[];function check(name,fn){fn();checks.push(name);}
const near=(a,b)=>assert.ok(Math.abs(a-b)<1e-8,`${a} != ${b}`);
const track=(keys,interpolation='hold')=>({keys,interpolation});
const card=(id,extra={})=>({id,name:id,asset:'paint',x:0,y:0,width:.1,height:.1,anchor:[0,0],scale:1,rotation:0,opacity:1,visible:true,blend:'source-over',depth:0,...extra});
const catalog={assets:[{id:'paint',width:32,height:32},{id:'cels',width:96,height:32,atlas:{columns:3,rows:1,cell_width:32,cell_height:32,frame_count:3}}]};
function fixture(N=60){
  const T=N/24,scene={version:1,id:'finite',canvas:{width:320,height:180,fps:24,loop_seconds:T,background:'#000000'},clock:{version:1,mode:'finite',id:'shot-a',revision:'fixture-a-v1',duration_frames:N,local_cycles:{flame:{period_seconds:{numerator:1,denominator:1},phase_turns:.25}}},camera:{overscan:1,x_amplitude:0,y_amplitude:0,zoom_amplitude:0},groups:[],layers:[]};
  scene.layers=[card('root',{asset:'cels',height:32/180,cycle_seconds:1,phase_frames:0,sockets:{tip:{frames:[[0,0],[10/32,0],[20/32,0]]}},tracks:{x:track([[0,0],[T,N/320]],'linear'),cell:track([[0,0],[(N-1)/24,1],[T,2]]),visible:track([[0,true],[T,false]])}}),card('child',{x:3/320,attach:{layer:'root',socket:'tip'}})];delete scene.layers[1].depth;return scene;
}
check('mc/1 finite specimen holds authored endpoint N independently from final exported N-1',()=>{
  for(const N of [60,96]){
    const scene=fixture(N),rig=compileScene(scene,catalog);
    for(const f of [N+1,18,-1,N-1,N,0,33,N+24]){
      const [root,child]=rig.sampleFrame(f),effective=Math.max(0,Math.min(N,f)),cell=effective>=N?2:effective>=N-1?1:0;
      near(root.matrix[4],effective);assert.equal(root.cell,cell);near(child.matrix[4],effective+10*cell+3);
      assert.equal(root.visible,effective<N);assert.equal(child.visible,effective<N);
      assert.deepEqual(point(child.parent,0,0),root.sockets.tip);
    }
    assert.deepEqual(rig.sample(-100),rig.sample(0));assert.deepEqual(rig.sample(100),rig.sample(N/24));
    assert.notDeepEqual(rig.sampleFrame(N-1),rig.sampleFrame(N));
    assert.equal(auditScene(scene,catalog).ok,true);
    const report=sceneTiming(scene,catalog);assert.equal(report.output_frames,N);assert.equal(report.layers[0].endpoint.cell,2);assert.equal(report.layers[0].last_exported.cell,1);
    assert.equal(rig.clock.seconds(.001).requested_frame,null);assert.equal(rig.clock.frame(-1).requested_frame,-1);
    assert.throws(()=>rig.sampleFrame(.5));assert.throws(()=>rig.sample(Infinity));
  }
});
check('Local cycles evaluate from clamped time once for motion, camera, cels, sockets and held tracks',()=>{
  const scene=fixture();scene.camera={...scene.camera,local_cycle:'flame',x_amplitude:.1};
  scene.layers[0]={...card('root',{asset:'cels',depth:1}),cycle_seconds:7,phase_frames:0,local_cycle:'flame',sockets:{tip:{frames:[[0,0],[.5,0],[1,0]]}},motion:{x_amplitude:.1,y_amplitude:0,cycles:1,phase:0},tracks:{cell:track([[0,0],[.5,1],[.8,2],[1,0]])}};
  const rig=compileScene(scene,catalog);
  for(const row of packet.local_cycle.samples){const context=rig.clock.frame(row.shot_frame);near(context.local_cycles.flame.progress,row.progress);const [root,child]=rig.sample(context);near(root.matrix[4],64*Math.sin(Math.PI*2*row.progress));assert.deepEqual(point(child.parent,0,0),root.sockets.tip);}
  assert.deepEqual(rig.sample(2.5),rig.sample(12));assert.deepEqual(consumerTime(rig.clock.frame(60),'flame'),{seconds:.75,duration:1,progress:.75});
  const other=fixture(96);assert.throws(()=>rig.sample(compileClock(other).frame(1)),/different clock/);
  const timing=sceneTiming(scene,catalog);assert.equal(timing.layers[0].authored.holds.at(-1).end_seconds,2.5);
});
check('Finite finishing pixels and signal bindings share endpoint holds; local signals do not double wrap',()=>{
  const scene=fixture();scene.layers=[card('floor',{width:1,height:1}),card('follower',{x:.5,y:.5})];
  scene.finishing={version:1,working_space:'linear-srgb',output_space:'srgb',signals:[{id:'fade',keys:[[0,0],[2.5,1]],interpolation:'hold'},{id:'local',local_cycle:'flame',keys:[[0,0],[.5,1],[1,0]],interpolation:'linear'}],lights:[{id:'light',receivers:['floor'],rect:[0,0,1,1],color:'#ffffff',gain:1,feather:0,signal:'fade'}]};
  scene.bindings={version:1,links:[{id:'bound',source:{signal:'fade',range:[0,1]},target:{layer:'follower',channel:'x',range:[0,1]},off:0,map:{interpolation:'linear',keys:[[0,0],[1,1]]}}]};
  const rig=compileScene(scene,catalog),runtime=canvasRuntime(),paint=runtime.createCanvas(32,32),ctx=paint.getContext('2d');ctx.fillStyle='#202020';ctx.fillRect(0,0,32,32);
  const images=new Map([['paint',paint]]),canvas=runtime.createCanvas(320,180);
  const render=frame=>{drawScene(canvas,scene,catalog,images,rig.clock.frame(frame),{sampler:rig.sample,createCanvas:runtime.createCanvas});return Buffer.from(canvas.data());};
  const last=render(59),end=render(60);assert.notDeepEqual(last,end);assert.deepEqual(render(61),end);assert.ok(end[0]>last[0]);assert.equal(last[0],32);
  assert.equal(rig.sampleFrame(60)[1].channels.x,1);assert.equal(rig.sampleFrame(59)[1].channels.x,0);
  const d=finishingDiagnostics(scene,catalog,100,rig.sample(100));assert.equal(d.signals.fade,1);near(d.signals.local,.5);
});
check('Reparent uses finite endpoint and local motion without recomputing modulo time',()=>{
  const scene=fixture();scene.layers[0].tracks.visible=track([[0,true],[2.5,true]]);scene.layers.push(card('free',{x:.6,y:.5,local_cycle:'flame',motion:{x_amplitude:.1,y_amplitude:.03,cycles:1,phase:0}}));
  const report=reparentAtTime(scene,catalog,{op:'reparent',layer:'free',to:'root',socket:'tip',preserve:'world_at_time',at_seconds:9});assert.ok(report.max_world_corner_error_pixels<1e-7);
});
check('Bad clock metadata, unknown cycles, nonclosing local tracks and incompatible loop periods reject',()=>{
  for(const mutate of [s=>s.clock.duration_frames++,s=>s.clock.revision='',s=>s.clock.mode='once',s=>s.layers[0].local_cycle='missing',s=>s.camera.local_cycle='missing',s=>s.clock.local_cycles.flame.period_seconds={numerator:0,denominator:1},s=>s.clock.mode='loop',s=>{s.layers[0].local_cycle='flame';s.layers[0].tracks={x:track([[0,0],[1,1]],'linear')};}]){const scene=fixture();mutate(scene);assert.throws(()=>validateScene(scene,catalog));}
  const short=fixture();short.canvas.loop_seconds=1/24;short.clock.duration_frames=1;short.layers=[card('still')];
  assert.equal(compileClock(short).seconds(1/24).region,'at-or-after-end');
  assert.deepEqual(compileClock(short).seconds(1/24).effective_seconds,{numerator:1,denominator:24});
  short.clock.mode='loop';short.clock.local_cycles.flame.period_seconds={numerator:1,denominator:24};
  assert.equal(compileClock(short).seconds(1/24).local_cycles.flame.progress,.25);
  const scene=fixture(96);scene.clock.mode='loop';scene.layers=[card('local',{local_cycle:'flame'})];const rig=compileScene(scene,catalog);assert.deepEqual(rig.sample(-1),rig.sample(3));assert.deepEqual(rig.sample(0),rig.sample(4));
});
check('Exact rational conversions preserve signed ties, residuals, cue membership and rejection',()=>{
  for(const row of packet.rounding_cases)for(const policy of ['floor','ceil','nearest-half-away-from-zero'])assert.equal(roundRational({numerator:row.value[0],denominator:row.value[1]},policy).value,row[policy]);
  assert.equal(framesToSamples(18,packet.fps,48000).value,36000);
  for(const cue of packet.cues)assert.deepEqual(cue.shot_samples.map(s=>samplesToFrames(s,48000,packet.fps,'ceil').value),cue.shot_frames);
  assert.throws(()=>framesToSamples(1,{numerator:30000,denominator:1001},48000),/Exact/);
  assert.deepEqual(framesToSamples(1,{numerator:30000,denominator:1001},48000,'floor').residual,{numerator:-3,denominator:5});
  assert.equal(secondsToFrames({numerator:59,denominator:24},24).value,59);
  assert.throws(()=>framesToSamples(Number.MAX_SAFE_INTEGER+1,24,48000));assert.throws(()=>roundRational(1,'implicit'));
});
console.log(JSON.stringify({ok:true,checks},null,2));
