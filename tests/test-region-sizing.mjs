import assert from 'node:assert/strict';
import {regionDemand,largestScale} from '../editor/region-sizing.mjs';
const reference={file:'source.png',sha256:'a'.repeat(64),width:100,height:100};
const catalog={version:1,assets:[{id:'source',width:100,height:100,registration_mapping:{version:1,cell_size:[100,100],reference,
  cels:[{reference_to_cell:[1,0,0,1,0,0]}]}}]};
const scene={version:1,id:'region-test',canvas:{width:100,height:100,fps:4,loop_seconds:2,background:'#000000'},
  camera:{overscan:1,x_amplitude:0,y_amplitude:0,zoom_amplitude:0},groups:[],
  framing:{version:1,views:{small:{rect_scene_px:[0,0,100,100],output:{width:100,height:100}},large:{rect_scene_px:[0,0,50,50],output:{width:200,height:200}}}},
  layers:[{id:'base',asset:'source',x:0,y:0,width:1,height:1,anchor:[0,0],scale:1,rotation:Math.PI/4,opacity:1,visible:true,blend:'source-over',depth:0}]};
const options={base:'base',reference,bounds:[5,5,25,25],views:['small','large']};
let report=regionDemand(scene,catalog,options);assert.ok(Math.abs(report.max_density-4)<1e-9);assert.equal(report.cause.view,'large');assert.equal(report.frames,8);
scene.layers[0].tracks={scale:{interpolation:'linear',keys:[[0,1],[1,2],[2,1]]}};
report=regionDemand(scene,catalog,options);assert.ok(Math.abs(report.max_density-8)<1e-9);assert.equal(report.cause.frame,4);
assert.equal(largestScale([0,3,-2,0,0,0]),3);
assert.throws(()=>regionDemand(scene,catalog,{...options,views:['small','small']}),/unique/);
assert.throws(()=>regionDemand(scene,catalog,{...options,start_frame:7,frames:2}),/within one loop/);
scene.canvas.fps=25;scene.canvas.loop_seconds=29/25;
scene.clock={version:1,mode:'finite',id:'region-shot',revision:'1',duration_frames:29};
scene.layers[0].tracks={scale:{interpolation:'linear',keys:[[0,1],[28/25,2],[29/25,3]]}};
report=regionDemand(scene,catalog,options);assert.equal(report.frames,29);assert.equal(report.cause.frame,28);
assert.ok(Math.abs(report.max_density-8)<1e-9);
console.log(JSON.stringify({ok:true,checks:6,scope:'Shared transforms, rotation-independent density, output demand and sampled peak'}));
