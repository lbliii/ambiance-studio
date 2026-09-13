#!/usr/bin/env node
// Bounded render-history evidence, using existing scene/view evaluation only.
// node examples/views/reproduce_canvas_sequence.mjs --out NEW_DIRECTORY
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {canvasRuntime} from '../../tools/render/canvas-runtime.mjs';
import {createStageRenderer} from '../../editor/stage-raster.mjs';
import {planViews} from '../../editor/views.mjs';
import {movingFixture} from './moving-fixture.mjs';

if(process.argv.length!==4||process.argv[2]!=='--out')throw Error('Usage: node examples/views/reproduce_canvas_sequence.mjs --out NEW_DIRECTORY');
const root=fileURLToPath(new URL('../../',import.meta.url)),out=path.resolve(process.argv[3]);
const runtime=canvasRuntime(),{createCanvas}=runtime,require=createRequire(import.meta.url);
const sha=data=>createHash('sha256').update(data).digest('hex');
const sources={};
for(const name of ['editor/engine.mjs','editor/finishing.mjs','editor/bindings.mjs','editor/views.mjs','editor/stage-raster.mjs','tools/render/canvas-runtime.mjs','examples/views/moving-fixture.mjs','examples/views/reproduce_canvas_sequence.mjs'])
  sources[name]=sha(fs.readFileSync(path.join(root,name)));
const f=movingFixture(createCanvas);
f.scene.camera={overscan:1,x_amplitude:0,y_amplitude:0,zoom_amplitude:0};f.scene.layers[0].width=f.scene.layers[0].height=1;
const room=f.images.get('room').getContext('2d');room.clearRect(72,16,8,8);room.clearRect(88,0,8,1);
// Validate every requested plan before claiming a new output directory.
const plans=[1,2,4].map(supersample=>planViews(f.scene,[{id:'portrait'},{id:'landscape'}],{long_edge:160,supersample}));
fs.mkdirSync(path.dirname(out),{recursive:true});fs.mkdirSync(out);
const write=(file,bytes)=>{fs.writeFileSync(path.join(out,file),bytes);return {file,sha256:sha(bytes)};};
const json=(file,value)=>write(file,JSON.stringify(value,null,2)+'\n');
const assets={};fs.mkdirSync(path.join(out,'inputs'));
for(const [id,image] of f.images)assets[id]=write(`inputs/${id}.png`,image.toBuffer('image/png'));
const inputs={scene:json('inputs/scene.json',f.scene),catalog:json('inputs/catalog.json',f.catalog),assets};
const report={version:1,source_root:root,sources,inputs,runtime:{node:process.version,platform:process.platform,arch:process.arch,
  canvas_version:runtime.version,canvas_module:runtime.module,canvas_module_sha256:sha(fs.readFileSync(runtime.module)),
  native_modules:Object.keys(require.cache).filter(p=>p.endsWith('.node')).map(p=>({path:p,sha256:sha(fs.readFileSync(p))}))},
  threshold:254,plans,cases:[],limits:'One local-art fixture, fixed runtime and inputs; coverage and finished modes intentionally differ. No cross-runtime determinism or artistic approval.'};
const times=[0,.125,.625];
const histories={repeated:[[true,.125],[true,.125],[false,.125],[false,.125]],
  coverage_out_of_order:[[true,.625],[true,0],[true,.125]],
  finished_out_of_order:[[false,.625],[false,0],[false,.125]],
  interleaved:[[true,0],[false,0],[true,.125],[false,.125],[true,.625],[false,.625],[false,0],[true,0]]};
function difference(a,b){let rgbaBytes=0,alphaPixels=0;for(let i=0;i<a.length;i++)if(a[i]!==b[i]){rgbaBytes++;if(i%4===3)alphaPixels++;}return {rgba_bytes_different:rgbaBytes,alpha_pixels_different:alphaPixels};}
for(const finishing of [true,false])for(const plan of plans){
  const scene=structuredClone(f.scene);if(!finishing)delete scene.finishing;
  const make=()=>createStageRenderer(scene,f.catalog,f.images,plan,createCanvas),references=new Map();
  const row={finishing,supersample:plan.supersample,scene_sha256:sha(JSON.stringify(scene)),samples:[]};
  const prefix=`finishing-${finishing}-ss${plan.supersample}`;fs.mkdirSync(path.join(out,prefix));
  function capture(renderer,history,step,coverage,time){
    renderer.render(time,{coverage});
    const key=`${coverage}/${time}`,sample={history,step,mode:coverage?'coverage':'finished',frame:time*scene.canvas.fps,time_seconds:time,
      smoothing_enabled:renderer.stage.getContext('2d').imageSmoothingEnabled,smoothing_quality:renderer.stage.getContext('2d').imageSmoothingQuality,images:{}};
    if(history==='fresh')references.set(key,new Map());
    for(const [id,c] of new Map([['stage',renderer.stage],...renderer.outputs])){
      const data=Buffer.from(c.getContext('2d').getImageData(0,0,c.width,c.height).data);
      if(history==='fresh')references.get(key).set(id,data);
      let uncovered=0;for(let i=3;i<data.length;i+=4)if(data[i]<254)uncovered++;
      sample.images[id]={...write(`${prefix}/${history}-${step}-${sample.mode}-${sample.frame}-${id}.png`,c.toBuffer('image/png')),
        resolution:[c.width,c.height],rgba_sha256:sha(data),uncovered_pixels:uncovered,...difference(data,references.get(key).get(id))};
    }
    row.samples.push(sample);
  }
  for(const coverage of [true,false])for(const [step,time] of times.entries())capture(make(),'fresh',step,coverage,time);
  for(const [history,steps] of Object.entries(histories)){
    const renderer=make();for(const [step,[coverage,time]] of steps.entries())capture(renderer,history,step,coverage,time);
  }
  report.cases.push(row);
}
report.changed_comparisons=report.cases.flatMap(c=>c.samples.flatMap(s=>Object.values(s.images))).filter(i=>i.rgba_bytes_different>0).length;
for(const [name,hash] of Object.entries(sources))if(sha(fs.readFileSync(path.join(root,name)))!==hash)throw Error(`Source changed during reproduction: ${name}`);
const saved=json('report.json',report);
console.log(JSON.stringify({report:path.join(out,saved.file),sha256:saved.sha256,cases:report.cases.length,changed_comparisons:report.changed_comparisons},null,2));
