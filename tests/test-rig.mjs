import fs from 'node:fs';
import assert from 'node:assert/strict';
import {compileScene,validateScene,point} from '../editor/engine.mjs';
import {auditScene} from '../editor/audit.mjs';
const read=name=>JSON.parse(fs.readFileSync(new URL(name,import.meta.url)));
const scene=read('../scenes/last-lantern-rigged.json'),catalog=read('../assets/catalog.json');
const checks=[];
function check(name,fn){fn();checks.push(name);}
const close=(a,b)=>assert.ok(Math.hypot(a[0]-b[0],a[1]-b[1])<1e-7,`${a} differs from ${b}`);
check('Parent translation, rotation, scale and depth preserve attachment through all 480 frames',()=>{
  const s=structuredClone(scene),house=s.layers.find(l=>l.id==='cottage');
  house.x+=.12;house.y-=.09;house.rotation=.25;house.scale=1.7;
  house.motion={x_amplitude:.03,y_amplitude:.02,cycles:2,phase:.7,rotation_amplitude:.12};
  const rig=compileScene(s,catalog);
  for(let f=0;f<480;f++){
    const states=rig.sample(f/30),parent=states.find(s=>s.id==='cottage'),child=states.find(s=>s.id==='chimney-smoke');
    close(point(child.matrix,0,0),parent.sockets.chimney);
    assert.equal(child.depth,parent.depth);assert.equal(child.matrix[0],parent.matrix[0]);
  }
});
check('Nested attachment works regardless of paint order',()=>{
  const s=structuredClone(scene),smoke=s.layers.find(l=>l.id==='chimney-smoke');smoke.sockets={tip:[.5,0]};
  const child={...structuredClone(smoke),id:'nested',attach:{layer:smoke.id,socket:'tip'},sockets:{}};
  s.layers.unshift(child);const states=compileScene(s,catalog).sample(4);
  close(point(states[0].matrix,0,0),states.find(s=>s.id===smoke.id).sockets.tip);
});
check('Cel-specific socket tracks follow the sampled parent cel',()=>{
  const s=structuredClone(scene),house=s.layers.find(l=>l.id==='cottage');
  house.sockets.chimney={frames:Array.from({length:12},(_,i)=>[i/12,.1])};
  const rig=compileScene(s,catalog),a=rig.sample(0).find(s=>s.id==='chimney-smoke'),b=rig.sample(1/6).find(s=>s.id==='chimney-smoke');
  assert.notDeepEqual(a.matrix,b.matrix);
  const parent=rig.sample(1/6).find(s=>s.id==='cottage');close(point(b.matrix,0,0),parent.sockets.chimney);
});
check('Cycles, missing sockets, mixed depth, and incomplete tracks are rejected',()=>{
  for(const mutate of [s=>{s.layers.find(l=>l.id==='cottage').attach={layer:'chimney-smoke',socket:'tip'};delete s.layers.find(l=>l.id==='cottage').group;s.layers.find(l=>l.id==='chimney-smoke').sockets={tip:[0,0]};},
    s=>s.layers.find(l=>l.attach).attach.socket='absent',s=>s.layers.find(l=>l.attach).depth=1,
    s=>s.layers.find(l=>l.id==='cottage').sockets.chimney={frames:[[0,0]]}]){
    const bad=structuredClone(scene);mutate(bad);assert.throws(()=>validateScene(bad,catalog));
  }
});
check('Camera can pass endpoint closure yet fail coverage midway',()=>{
  const s=structuredClone(scene);s.camera.overscan=1;s.camera.x_amplitude=10;
  const report=auditScene(s,catalog);assert.equal(report.state_closure,true);assert.equal(report.ok,false);assert.ok(report.failure_count>0);
});
check('Compiled snapshots survive later authoring edits and arbitrary seek order',()=>{
  const s=structuredClone(scene),rig=compileScene(s,catalog),before=rig.sample(2.3);
  s.layers[0].x=10;rig.sample(13);assert.deepEqual(rig.sample(2.3),before);assert.deepEqual(rig.sample(0),rig.sample(16));
});
check('Attached visibility and opacity inherit from the parent',()=>{
  const s=structuredClone(scene),house=s.layers.find(l=>l.id==='cottage');house.visible=false;house.opacity=.5;
  const child=compileScene(s,catalog).sample(0).find(s=>s.id==='chimney-smoke');
  assert.equal(child.visible,false);assert.equal(child.opacity,s.layers.find(l=>l.id==='chimney-smoke').opacity*.5);
});
console.log(JSON.stringify({ok:true,checks},null,2));
