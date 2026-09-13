#!/usr/bin/env node
// Bounded local-art replay for alpha localization. No provider or canonical film.
// Usage: node tests/fixtures/create-alpha-fixture.mjs NEW_PROJECT
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {movingFixture} from '../../examples/views/moving-fixture.mjs';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..'),require=createRequire(import.meta.url);
let runtime;for(const name of [process.env.AMBIANCE_CANVAS_MODULE,'@napi-rs/canvas',path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@napi-rs/canvas')].filter(Boolean))try{runtime=require(name);break;}catch{}
if(!runtime)throw Error('Node Canvas is required');
if(process.argv.length!==3)throw Error('Usage: node tests/fixtures/create-alpha-fixture.mjs NEW_PROJECT');
const project=path.resolve(process.argv[2]);
execFileSync(path.join(root,'ambiance'),['project','init',project,'--format','dual','--title','Alpha localization fixture']);
const {scene,catalog,images}=movingFixture(runtime.createCanvas);
scene.id='alpha-localization';scene.title='Known interior hole and portrait boundary';
scene.camera={overscan:1,x_amplitude:0,y_amplitude:0,zoom_amplitude:0};
scene.layers[0].width=scene.layers[0].height=1;
const ctx=images.get('room').getContext('2d');ctx.clearRect(72,16,8,8);ctx.clearRect(88,0,8,1);
for(const asset of catalog.assets){
  const bytes=images.get(asset.id).toBuffer('image/png');asset.sha256=createHash('sha256').update(bytes).digest('hex');
  fs.writeFileSync(path.join(project,asset.file),bytes);
}
fs.writeFileSync(path.join(project,'scene/scene.json'),JSON.stringify(scene,null,2)+'\n');
fs.writeFileSync(path.join(project,'assets/catalog.json'),JSON.stringify(catalog,null,2)+'\n');
console.log(JSON.stringify({project,known_source_holes:[[72,16,8,8],[88,0,8,1]],portrait_crop:[35,0,90,160],
  landscape_crop:[0,35,160,90],expected:'Interior hole and boundary defect in portrait only; exact fringes depend on the recorded backend and audit sequence'},null,2));
