import fs from 'node:fs';
import assert from 'node:assert/strict';
import {sampleScene,validateScene} from './engine.mjs';
const scene=JSON.parse(fs.readFileSync(new URL('../scenes/last-lantern.json',import.meta.url)));
const catalog=JSON.parse(fs.readFileSync(new URL('../assets/catalog.json',import.meta.url)));
validateScene(scene,catalog);
const sample=t=>sampleScene(scene,catalog,t),T=scene.canvas.loop_seconds;
assert.deepEqual(sample(0),sample(T));
assert.deepEqual(sample(-T),sample(0));
const before=sample(2.5);sample(14.7);assert.deepEqual(sample(2.5),before);
const copy=JSON.parse(JSON.stringify(scene));assert.deepEqual(sampleScene(copy,catalog,3),sample(3));
const groups=sample(4).filter(s=>['cottage','ground','chimney-smoke'].includes(s.id));
assert.deepEqual(groups[0].parent,groups[1].parent);assert.deepEqual(groups[1].parent,groups[2].parent);
const smoke=t=>sample(t).find(s=>s.id==='chimney-smoke');
assert.equal(smoke(0).cell,0);assert.equal(smoke(1/6).cell,1);assert.equal(smoke(2).cell,0);
const bad=structuredClone(scene);bad.layers.find(l=>l.id==='chimney-smoke').cycle_seconds=3;
assert.throws(()=>validateScene(bad,catalog),/divide/);
const invalidGroup=structuredClone(scene);invalidGroup.layers[0].group='missing';
assert.throws(()=>validateScene(invalidGroup,catalog),/group/);
for(let frame=0;frame<T*scene.canvas.fps;frame++)for(const s of sample(frame/scene.canvas.fps))assert.ok(s.matrix.every(Number.isFinite));
console.log(JSON.stringify({ok:true,checks:['exact state closure at 0 and T','negative full cycle wraps',
  'out-of-order sampling is deterministic','JSON serialization preserves sampled state',
  'cottage attachments share a parent transform','smoke cel boundaries',
  'invalid cycle and group rejected','all 480 frame transforms finite'],
  limitation:'State checks only; browser pixel and human art reviews are separate.'},null,2));
