import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import os from 'node:os';
import path from 'node:path';
import {compileScene,drawScene,point} from '../editor/engine.mjs';
import {bindingFixture} from './fixtures/binding-scene.mjs';
const require=createRequire(import.meta.url);let runtime;
for(const p of [process.env.AMBIANCE_CANVAS_MODULE,'@napi-rs/canvas',path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@napi-rs/canvas')].filter(Boolean))try{runtime=require(p);break;}catch{}
if(!runtime)throw Error('Canvas runtime required for binding raster tests');
const {createCanvas}=runtime,fixture=()=>bindingFixture(createCanvas),checks=[];
const test=(name,fn)=>{fn();checks.push(name);},near=(a,b)=>assert.ok(Math.abs(a-b)<1e-10,`${a} != ${b}`);
function render(f,t,pass='beauty'){const c=createCanvas(128,96);drawScene(c,f.scene,f.catalog,f.images,t,{createCanvas,pass});return c.getContext('2d').getImageData(0,0,128,96).data;}
const pixel=(data,x,y)=>Array.from(data.slice((y*128+x)*4,(y*128+x)*4+4));
test('Cel signal/pose/state drive bounded values on the sole clock, under seeks and exact loop closure',()=>{
  const f=fixture(),compiled=compileScene(f.scene,f.catalog);
  for(const [time,opacity,x,cell] of [[0,.25,0,0],[1,1,.03125,1],[2,0,0,2],[3,.25,-.03125,0]]){
    const state=compiled.sample(time).find(s=>s.id==='floor-paint');near(state.channels.opacity,opacity);near(state.channels.x,x);assert.equal(state.cell,cell);
    assert.equal(compiled.inspectBindings(time).samples.find(s=>s.id==='strength').value,opacity);
  }
  assert.deepEqual(compiled.sample(4),compiled.sample(0));assert.deepEqual(compiled.sample(-1),compiled.sample(3));
  const saved=compiled.sample(.375);compiled.sample(2.83);assert.deepEqual(compiled.sample(.375),saved);
});
test('Floor attachment supplies receiver motion; source pose maps a different distance and local direction',()=>{
  const f=fixture(),states=compileScene(f.scene,f.catalog).sample(1),floor=states[0],paint=states[1];
  near(paint.matrix[4]-floor.matrix[4],4);near(paint.matrix[5]-floor.matrix[5],0);
  f.scene.layers[0].rotation=Math.PI/2;f.scene.layers[0].scale=2;
  const moved=compileScene(f.scene,f.catalog).sample(1);near(moved[1].matrix[4]-moved[0].matrix[4],0);near(moved[1].matrix[5]-moved[0].matrix[5],8);
  assert.deepEqual(point(moved[3].matrix,0,0),moved[2].sockets.wick);
});
test('Hidden parent turns shared intensity off and chooses explicit pose/state off responses',()=>{
  const f=fixture();f.scene.layers.find(l=>l.id==='pumpkin').visible=false;
  const sampled=compileScene(f.scene,f.catalog).inspectBindings(1).samples;
  assert.deepEqual(sampled.map(s=>s.value),[0,0,2]);assert.ok(sampled.every(s=>!s.source.active));
  f.scene.layers.find(l=>l.id==='pumpkin').visible=true;f.scene.layers.find(l=>l.id==='pumpkin').opacity=.5;
  near(compileScene(f.scene,f.catalog).inspectBindings(1).samples[0].value,.5);
});
test('Closed key signal can drive source appearance with no extra clock; clamped maps and hold cel boundary are deterministic',()=>{
  const f=fixture();f.scene.finishing.signals.push({id:'power',keys:[[0,0],[2,2],[4,0]],interpolation:'linear'});
  f.scene.bindings.links.push({id:'bulb',source:{signal:'power',range:[0,1]},target:{layer:'flame',channel:'opacity',range:[0,1]},map:{interpolation:'smoothstep',keys:[[0,0],[1,1]]},off:0});
  near(compileScene(f.scene,f.catalog).sample(.5).find(s=>s.id==='flame').opacity,.5);
  near(compileScene(f.scene,f.catalog).sample(1.5).find(s=>s.id==='flame').opacity,1);
  f.scene.bindings.links[2]={id:'shape',source:{signal:'power',range:[0,1]},target:{layer:'floor-paint',channel:'cell',range:[0,2]},map:{interpolation:'hold',keys:[[0,0],[.5,1],[1,2]]},off:0};
  assert.equal(compileScene(f.scene,f.catalog).sample(.5)[1].cell,1);assert.equal(compileScene(f.scene,f.catalog).sample(1)[1].cell,2);
});
test('Invalid endpoints, tables, ranges, fields, mixed cycles and writer conflicts fail before sampling',()=>{
  const bad=[s=>s.bindings.links[0].source.signal='missing',s=>s.bindings.links[0].target.layer='missing',s=>s.bindings.links[0].target.range=[1,0],s=>s.bindings.links[0].off=2,s=>s.bindings.links[0].expression='x',s=>s.bindings.links[2].map.values.pop(),s=>s.bindings.links.push(structuredClone(s.bindings.links[0])),s=>{s.bindings.links.push({...structuredClone(s.bindings.links[0]),id:'second'});},s=>s.layers[1].tracks={opacity:{interpolation:'linear',keys:[[0,0],[4,0]]}},s=>s.layers[1].motion={x_amplitude:.1,y_amplitude:0,rotation_amplitude:0,cycles:1,phase:0},s=>{s.bindings.links[1].source.layer='floor-paint';},s=>{s.layers[2].attach={layer:'floor-paint',socket:'origin'};s.layers[1].sockets={origin:[0,0]};delete s.layers[2].depth;},s=>s.bindings.links[1].map.keys[1][0]=.8,s=>s.bindings.links[2].map.values=[0,.5,2]];
  for(const mutate of bad){const f=fixture();mutate(f.scene);assert.throws(()=>compileScene(f.scene,f.catalog));}
});
test('Low/high/off painted illumination clips to receiver UV mask and fixed foreground, including isolated contribution',()=>{
  const f=fixture(),low=render(f,0),high=render(f,1),off=render(f,2),pass=render(f,1,'illuminations');
  assert.ok(pixel(high,60,55)[0]>pixel(low,60,55)[0]);assert.equal(pixel(off,60,55)[0],32);
  assert.equal(pixel(high,29,55)[0],32);assert.equal(pixel(pass,29,55)[0],0);
  assert.deepEqual(pixel(high,78,70),[16,36,56,255]);assert.deepEqual(pixel(pass,78,70),[0,0,0,255]);
  assert.equal(pixel(pass,60,88)[0],0);assert.ok(pixel(pass,60,55)[0]>0);
  assert.deepEqual(render(f,4),render(f,0));assert.deepEqual(render(f,-1),render(f,3));
  f.scene.layers[2].visible=false;assert.deepEqual(pixel(render(f,1),60,55),[32,40,56,255]);
});
test('Add uses linear contribution; mix restores painted target color and preserves receiver opacity once',()=>{
  const f=fixture();f.scene.bindings.links[0].map.keys=[[0,1],[1,1]];f.scene.finishing.illuminations[0].mode='mix';
  assert.deepEqual(pixel(render(f,1),60,55),[136,96,34,255]);
  f.scene.layers[0].opacity=.5;const value=pixel(render(f,1,'illuminations'),60,55)[0];assert.ok(value>90&&value<103,`opacity inherited once: ${value}`);
});
console.log(JSON.stringify({ok:true,checks},null,2));
