#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {movingFixture} from './moving-fixture.mjs';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..'),require=createRequire(import.meta.url);
let runtime;for(const p of [process.env.AMBIANCE_CANVAS_MODULE,'@napi-rs/canvas',path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@napi-rs/canvas')].filter(Boolean))try{runtime=require(p);break;}catch{}
if(!runtime)throw Error('Node Canvas is required');
if(process.argv.length!==3)throw Error('Usage: node examples/views/create_motion_fixture.mjs NEW_PROJECT');
const project=path.resolve(process.argv[2]),write=(name,value)=>fs.writeFileSync(path.join(project,name),JSON.stringify(value,null,2)+'\n');
function command(...args){return JSON.parse(execFileSync(path.join(root,'ambiance'),args,{encoding:'utf8'})).data;}
command('project','init',project,'--format','dual','--title','One scene · two views');
const {scene,catalog,images}=movingFixture(runtime.createCanvas);
for(const asset of catalog.assets){const bytes=images.get(asset.id).toBuffer('image/png');asset.sha256=createHash('sha256').update(bytes).digest('hex');asset.provenance={source:'examples/views/moving-fixture.mjs',purpose:'Local geometric test art'};fs.writeFileSync(path.join(project,asset.file),bytes);}
write('assets/catalog.json',catalog);
// This independent small stage keeps the browser/finishing pilot inexpensive.
// All view, layer and finishing authoring then uses the normal CLI transaction.
const initial=JSON.parse(fs.readFileSync(path.join(project,'scene/scene.json')));
initial.canvas=scene.canvas;delete initial.framing;write('scene/scene.json',initial);
const operations=[{op:'camera',values:scene.camera},{op:'framing',value:scene.framing},
  ...scene.layers.map(({id,asset,...values})=>({op:'add',asset,id,values})),
  {op:'coverage',layers:scene.coverage_layers},{op:'finishing',value:scene.finishing}];
write('plans/motion-fixture.json',{version:1,operations});
const dry=command('--project',project,'scene','apply',path.join(project,'plans/motion-fixture.json'),'--dry-run');
command('--project',project,'scene','apply',path.join(project,'plans/motion-fixture.json'),'--expect-sha256',dry.previous_sha256);
command('--project',project,'project','check','--out',path.join(project,'reports/project.json'));
const proof=command('--project',project,'render','views-proof','--view','portrait','--view','landscape','--seconds','2','--long-edge','320','--out',path.join(project,'render/paired-proof'));
console.log(JSON.stringify({project,proof:proof.output,report:proof.report,review_needed:proof.review_needed,elapsed_seconds:proof.elapsed_seconds,peak_rss_bytes:proof.peak_rss_bytes},null,2));
