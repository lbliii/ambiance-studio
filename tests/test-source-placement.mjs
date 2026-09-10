import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {compileScene,point} from '../editor/engine.mjs';
import {sceneTiming} from '../editor/timing.mjs';
const checks=[];function check(name,fn){fn();checks.push(name);}
const ref={file:'reference.png',sha256:'c'.repeat(64),width:200,height:100};
const baseAsset={id:'plate',file:'plate.png',width:204,height:104,sha256:'a'.repeat(64),registration_mapping:{version:1,cell_size:[204,104],input_sources:[ref],cels:[{index:0,source_index:0,source_to_cell:[1,0,0,1,2,2]}]}};
const cutout={id:'cutout',file:'cutout.png',width:19,height:24,sha256:'b'.repeat(64),pivot:[.5,.5],registration_mapping:{version:1,cell_size:[19,24],reference:ref,cels:[{index:0,reference_to_cell:[.5,0,0,.5,-23,-8]}]}};
const gait={id:'gait',file:'gait.png',width:80,height:20,sha256:'d'.repeat(64),atlas:{columns:4,rows:1,cell_width:20,cell_height:20,frame_count:4}};
const catalog={assets:[baseAsset,cutout,gait]};
const card=(id,extra={})=>({id,name:id,asset:'cutout',x:.5,y:.5,width:.2,height:.1,anchor:[.5,.5],scale:1,rotation:0,opacity:1,visible:true,blend:'source-over',depth:0,...extra});
const scene=(width=300,height=600)=>({version:1,id:'coordinates',canvas:{width,height,fps:30,loop_seconds:4,background:'#142030'},camera:{overscan:1,x_amplitude:0,y_amplitude:0,zoom_amplitude:0},groups:[],layers:[card('base',{asset:'plate',width:204/width,height:104/height,rotation:.3,scale:1.25})]});
const track=(keys,interpolation='hold')=>({keys,interpolation});
const run=(s,ops,report=true)=>{const p=spawnSync(process.execPath,[new URL('../tools/scene-command.mjs',import.meta.url).pathname],{input:JSON.stringify({action:'apply',scene:s,catalog,args:{batch:{version:1,operations:ops},report}}),encoding:'utf8'});return {...JSON.parse(p.stdout),exit:p.status};};
const near=(a,b)=>assert.ok(Math.abs(a-b)<1e-7,`${a} != ${b}`);
const corners=s=>{const [x,y,w,h]=s.rect;return [[x,y],[x+w,y],[x+w,y+h],[x,y+h]].map(p=>point(s.matrix,...p));};
check('Native cutout maps padding and compiler scale in portrait and landscape parent coordinates',()=>{
 for(const [w,h] of [[300,600],[600,300]]){
  const s=scene(w,h),r=run(s,[{op:'place_from_source',id:'cut',asset:'cutout',base:'base',mode:'native',reference:ref}]);assert.equal(r.ok,true,r.error);
  const states=compileScene(r.data.scene,catalog).sample(0),base=states[0],actual=corners(states[1]);
  const source=[[46,16],[84,16],[84,64],[46,64]];
  source.forEach(([x,y],i)=>{const expected=point(base.matrix,base.rect[0]+x+2,base.rect[1]+y+2);near(actual[i][0],expected[0]);near(actual[i][1],expected[1]);});
  assert.deepEqual(r.data.operations[0].source_anchor,[65,40]);assert.equal(s.layers.length,1);
 }
});
check('Generated sprite uses explicit intended source size and an explicit paint order',()=>{
 const s=scene(),r=run(s,[{op:'place_from_source',id:'flame',asset:'gait',base:'base',mode:'sprite',reference:ref,source_anchor:[50,20],source_size:[10,18],anchor:[.5,1],order:{before:'base'}}]);
 assert.equal(r.ok,true,r.error);assert.equal(r.data.scene.layers[0].id,'flame');near(r.data.scene.layers[0].width,10/300);near(r.data.scene.layers[0].height,18/600);
 assert.deepEqual(r.data.operations[0].source_anchor,[50,20]);
 const missing=run(s,[{op:'place_from_source',id:'flame',asset:'gait',base:'base',mode:'sprite',reference:ref}]);assert.equal(missing.ok,false);
});
check('Malformed native mappings, wrong identities and unsupported shear fail without a candidate',()=>{
 const explicit={version:1,asset_sha256:cutout.sha256,cell_size:[19,24],reference:ref,reference_to_cell:[.5,0,0,.5,-23,-8]};
 for(const change of [m=>m.asset_sha256='f'.repeat(64),m=>m.cell_size=[20,24],m=>m.reference={...ref,width:201},m=>m.reference_to_cell=[1,0,1,1,0,0],m=>m.reference_to_cell=[0,0,0,0,0,0]]){
  const m=structuredClone(explicit);change(m);const r=run(scene(),[{op:'place_from_source',id:'cut',asset:'cutout',base:'base',mode:'native',reference:ref,mapping:m}]);assert.equal(r.ok,false);assert.equal(r.data,undefined);
 }
});
function rig(motion){
 const s=scene();s.layers[0].sockets={old:[.4,.3]};s.layers[0].opacity=.5;
 s.layers.push(card('casket',{x:.65,y:.7,rotation:-.2,scale:.8,opacity:.8,sockets:{bed:[.25,.75]}}));
 s.layers.push(card('gesture',{asset:'gait',x:.01,y:.02,cycle_seconds:1,phase_frames:2,attach:{layer:'base',socket:'old'},opacity:.6,...(motion?{motion}:{} )}));delete s.layers[2].depth;
 s.layers.push(card('front-rim'),card('fixed-glass'));return s;
}
check('Exact-at-time reparent preserves gesture corners, cel timing, opacity and unchanged paint order',()=>{
 const s=rig(),r=run(s,[{op:'reparent',layer:'gesture',to:'casket',socket:'bed',preserve:'world_at_time',at_seconds:0}]);assert.equal(r.ok,true,r.error);
 const old=compileScene(s,catalog),next=compileScene(r.data.scene,catalog);const a=corners(old.sample(0)[2]),b=corners(next.sample(0)[2]);a.forEach((p,i)=>p.forEach((n,k)=>near(n,b[i][k])));
 for(let f=0;f<120;f++)assert.equal(old.sample(f/30)[2].cell,next.sample(f/30)[2].cell);
 near(next.sample(0)[2].opacity,.3);near(r.data.scene.layers[2].opacity,.375);
 assert.deepEqual(r.data.scene.layers.map(l=>l.id),s.layers.map(l=>l.id));assert.deepEqual(r.data.scene.layers[4],s.layers[4]);
});
check('Sinusoidal child reparent solves nonzero phase and time without rewriting future local motion',()=>{
 const motion={x_amplitude:.02,y_amplitude:.03,rotation_amplitude:.08,cycles:2,phase:.7};const s=rig(motion),time=1.37;
 const r=run(s,[{op:'reparent',layer:'gesture',to:'casket',socket:'bed',preserve:'world_at_time',at_seconds:time}]);assert.equal(r.ok,true,r.error);
 assert.deepEqual(r.data.scene.layers[2].motion,motion);assert.ok(r.data.operations[0].max_world_corner_error_pixels<1e-7);
 const before=compileScene(s,catalog).sample(0)[2],after=compileScene(r.data.scene,catalog).sample(0)[2];assert.notDeepEqual(after.matrix,before.matrix);
});
check('Impossible inheritance and transform tracks reject; representable hidden/zero-alpha states survive',()=>{
 for(const mutate of [s=>s.layers[1].visible=false,s=>s.layers[1].opacity=.1,s=>s.layers[2].tracks={x:track([[0,0],[4,0]],'linear')},s=>{s.layers[2].tracks={opacity:track([[0,.6],[4,.6]],'linear')};}]){
  const s=rig();mutate(s);const r=run(s,[{op:'reparent',layer:'gesture',to:'casket',socket:'bed',preserve:'world_at_time',at_seconds:0}]);assert.equal(r.ok,false);assert.equal(r.data,undefined);
 }
 const s=rig();s.layers[0].visible=false;s.layers[0].opacity=0;const r=run(s,[{op:'reparent',layer:'gesture',to:'casket',socket:'bed',preserve:'world_at_time',at_seconds:0}]);assert.equal(r.ok,true,r.error);
 const state=compileScene(r.data.scene,catalog).sample(0)[2];assert.equal(state.visible,false);assert.equal(state.opacity,0);
});
check('Timing distinguishes static/cycle/fallback and inherited presentation windows',()=>{
 const s=rig();s.layers[1].tracks={visible:track([[0,false],[1,true],[3,false],[4,false]])};s.layers[2].attach={layer:'casket',socket:'bed'};
 s.layers[2].tracks={cell:track([[0,0],[1,0],[1.1,1],[1.2,2],[1.3,3],[2,3],[2.1,0],[4,0]])};
 const r=sceneTiming(s,catalog),g=r.layers.find(l=>l.layer==='gesture');assert.equal(g.timing_driver,'cell_track');assert.equal(g.fallback_cycle.active,false);
 assert.equal(g.authored.holds[0].end_seconds,1.1);assert.equal(g.authored.holds[3].duration_seconds,2.1-1.3);
 assert.deepEqual(g.sampled.effective_visibility_windows,[{start_frame:30,end_frame_exclusive:90,start_seconds:1,end_seconds:3}]);
 assert.equal(r.layers[0].timing_driver,'static');const cycle=sceneTiming(rig(),catalog,{layer:'gesture'}).layers[0];assert.equal(cycle.timing_driver,'cycle');assert.equal(cycle.fallback_cycle.nominal_cel_fps,4);
});
check('Timing reports 10/15 Hz segments, fractional holds, skipped source cels and hidden seam resets',()=>{
 const s=scene();s.layers.push(card('actor',{asset:'gait',cycle_seconds:4,phase_frames:0,track_loop:'hidden-reset',tracks:{visible:track([[0,false],[.2,true],[3.8,false],[4,false]]),cell:track([[0,0],[.2,1],[.3,2],[.4,3],[1,0],[1+1/15,1],[1+2/15,2],[1.5,3],[1.505,0],[1.51,1],[4,0]])}}));
 const row=sceneTiming(s,catalog,{layer:'actor'}).layers[0];const rates=row.authored.rate_segments.map(r=>r.cel_selection_hz);
 assert.ok(rates.some(n=>Math.abs(n-10)<1e-8));assert.ok(rates.some(n=>Math.abs(n-15)<1e-8));
 assert.ok(row.sampled.unpresented_authored_holds.some(h=>h.start_seconds===1.505));
 assert.equal(row.join.leading_nonrendered_frames,6);assert.equal(row.join.trailing_nonrendered_frames,6);
 assert.equal(row.sampled.segments.at(-1).end_frame_exclusive,120);
});
console.log(JSON.stringify({ok:true,checks},null,2));
