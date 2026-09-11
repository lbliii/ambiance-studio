#!/usr/bin/env node
// Bounded raster measurement, separate from encoding, disk IO and aesthetic review.
import path from 'node:path';
import os from 'node:os';
import {createRequire} from 'node:module';
import {performance} from 'node:perf_hooks';
import {movingFixture} from './moving-fixture.mjs';
import {planViews} from '../../editor/views.mjs';
import {createStageRenderer} from '../../editor/stage-raster.mjs';
const [finishing,selection]=process.argv.slice(2);
if (!['on','off'].includes(finishing)||!['single','pair'].includes(selection)) throw Error('Usage: benchmark_raster.mjs on|off single|pair');
const require=createRequire(import.meta.url);
let runtime;
for (const candidate of [process.env.AMBIANCE_CANVAS_MODULE,'@napi-rs/canvas',path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@napi-rs/canvas')].filter(Boolean)) {
  try { runtime=require(candidate);break; } catch {}
}
if (!runtime) throw Error('Node Canvas is required');
const {scene,catalog,images}=movingFixture(runtime.createCanvas);
if (finishing==='off') delete scene.finishing;
const requests=(selection==='pair'?['portrait','landscape']:['portrait']).map(id=>({id}));
const plan=planViews(scene,requests);
const renderer=createStageRenderer(scene,catalog,images,plan,runtime.createCanvas);
const times=[0,.5,1,1.5],start=performance.now();
for (const time of times) renderer.render(time);
console.log(JSON.stringify({finishing,selection,frames:times.length,output_sizes:plan.views.map(v=>v.output),internal_canvas:plan.internal_canvas,
  elapsed_seconds:(performance.now()-start)/1000,peak_rss_bytes:process.resourceUsage().maxRSS*1024,
  node:process.version,platform:process.platform,scope:'Stage paint and view extraction only; no encoding, proof audit, file writing or human review.'}));
