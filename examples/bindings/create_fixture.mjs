#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {browserPacket} from './browser-packet.mjs';
import {bindingFixture} from '../../tests/fixtures/binding-scene.mjs';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..'),require=createRequire(import.meta.url);
let runtime;for(const p of [process.env.AMBIANCE_CANVAS_MODULE,'@napi-rs/canvas',path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@napi-rs/canvas')].filter(Boolean))try{runtime=require(p);break;}catch{}
if(!runtime)throw Error('Node Canvas required');
if(process.argv.length!==3)throw Error('Usage: node examples/bindings/create_fixture.mjs FRESH_PROJECT');
const project=path.resolve(process.argv[2]);
const write=(name,value)=>fs.writeFileSync(path.join(project,name),JSON.stringify(value,null,2)+'\n');
function cli(...args){return JSON.parse(execFileSync(path.join(root,'ambiance'),args,{encoding:'utf8'})).data;}
const run=(...args)=>cli('--project',project,...args);
cli('project','init',project,'--format','dual','--title','Synthetic coordinated painted light');
const {scene,catalog,images}=bindingFixture(runtime.createCanvas);
scene.framing={version:1,views:{portrait:{rect_scene_px:[37,0,54,96],output:{width:108,height:192}},landscape:{rect_scene_px:[0,12,128,72],output:{width:256,height:144}}}};
scene.layers.unshift({...structuredClone(scene.layers[0]),id:'stage-back',name:'Prepared backdrop',asset:'front',x:0,y:0,width:1,height:1,tracks:undefined,sockets:undefined});
scene.coverage_layers=['stage-back'];
for(const a of catalog.assets){const bytes=images.get(a.id).toBuffer('image/png');a.sha256=createHash('sha256').update(bytes).digest('hex');a.provenance={source:'tests/fixtures/binding-scene.mjs',purpose:'Repository-cleared local test paint'};fs.writeFileSync(path.join(project,a.file),bytes);}
write('assets/catalog.json',catalog);
// Only initialize the independent fixture's small canvas directly. All scene,
// look, view and binding authoring uses public validated transactions below.
const initial=JSON.parse(fs.readFileSync(path.join(project,'scene/scene.json')));initial.canvas=scene.canvas;delete initial.framing;write('scene/scene.json',initial);
const ops=[{op:'camera',values:scene.camera},{op:'framing',value:scene.framing},...scene.layers.map(({id,asset,...values})=>({op:'add',id,asset,values})),{op:'coverage',layers:scene.coverage_layers},{op:'finishing',value:scene.finishing},{op:'bindings',value:scene.bindings}];
write('plans/fixture.json',{version:1,operations:ops});
const dry=run('scene','apply',path.join(project,'plans/fixture.json'),'--dry-run');run('scene','apply',path.join(project,'plans/fixture.json'),'--expect-sha256',dry.previous_sha256);
run('binding','check','--time','1','--out',path.join(project,'reports/binding.json'));
write('plans/selection.json',{format:'ambiance-revision-selection',schema_version:1,scene:'scene/scene.json',catalog:'assets/catalog.json'});
run('revision','capture','bindings-v1','--selection',path.join(project,'plans/selection.json'));
const pair=run('render','views-proof','--revision','bindings-v1','--view','portrait','--view','landscape','--seconds','4','--long-edge','256','--out',path.join(project,'render/paired'));
write('plans/look.json',{version:1,time:1,title:'Painted source and receiver',selected_layer:'floor-paint'});
const look=run('render','look-proof',path.join(project,'plans/look.json'),'--revision','bindings-v1','--width','256','--out',path.join(project,'render/look'));
const hidden=run('render','proof','--revision','bindings-v1','--disable','pumpkin','--seconds','4','--width','256','--out',path.join(project,'render/source-hidden'));
for(const time of [0,1,2,3])run('render','frame','--revision','bindings-v1','--time',String(time),'--width','128','--out',path.join(project,`render/state-${time}`));
const pkg=run('look','export','--include-rig','--out',path.join(project,'looks/painted-floor'));
const browser=browserPacket(project,root);
console.log(JSON.stringify({project,browser,paired:pair,look:look.output,hidden:hidden.output,package:pkg.package,limits:['Synthetic tool proof, not a completed film. No human or phone review recorded.']},null,2));
