import assert from 'node:assert/strict';
import fs from 'node:fs';
import {compileScene,validateScene,point} from '../editor/engine.mjs';
import {auditViews,auditScene} from '../editor/audit.mjs';
import {dualFraming,resolveView,viewIds,viewProjection,canonicalView,resizeSceneCanvas} from '../editor/views.mjs';
const checks=[];
function check(name,fn){fn();checks.push(name);}
const read=name=>JSON.parse(fs.readFileSync(new URL(name,import.meta.url)));
const source=read('../scenes/last-lantern-rigged.json'),catalog=read('../assets/catalog.json');
function fixture(){
  const scene=structuredClone(source);
  scene.framing={version:1,views:{landscape:{rect_scene_px:[0,656.25,1080,607.5],output:{width:1920,height:1080}}}};
  return scene;
}
check('Framing preserves every sampled rig, cel and camera state',()=>{
  const before=compileScene(source,catalog),after=compileScene(fixture(),catalog);
  for(let frame=0;frame<480;frame++)assert.deepEqual(after.sample(frame/30),before.sample(frame/30));
});
check('Fractional crop has a uniform projection and stable resolved identity',()=>{
  const scene=fixture(),view=resolveView(scene,'landscape'),matrix=viewProjection(view);
  assert.deepEqual(point(matrix,0,656.25),[0,0]);
  assert.deepEqual(point(matrix,1080,1263.75),[1920,1080]);
  assert.equal(matrix[0],matrix[3]);
  const reordered=structuredClone(scene);
  reordered.framing.views.landscape={output:{height:1080,width:1920},rect_scene_px:[0,656.25,1080,607.5]};
  assert.equal(canonicalView(view),canonicalView(resolveView(reordered,'landscape')));
  view.rect_scene_px[0]=99;
  assert.equal(scene.framing.views.landscape.rect_scene_px[0],0);
});
check('Legacy authored view and dual defaults preserve explicit framing',()=>{
  assert.deepEqual(viewIds(source),['authored']);
  assert.deepEqual(resolveView(source).output,{width:1080,height:1920});
  const scene=structuredClone(source);scene.canvas.width=1920;scene.framing=dualFraming();
  assert.deepEqual(viewIds(scene),['authored','portrait','landscape']);
  validateScene(scene,catalog);
});
check('Invalid crops, aspect ratios and reserved/unknown fields fail',()=>{
  const mutations=[
    s=>s.framing.views.landscape.rect_scene_px[0]=-1,
    s=>s.framing.views.landscape.rect_scene_px[2]=1081,
    s=>s.framing.views.landscape.rect_scene_px[2]=0,
    s=>s.framing.views.landscape.rect_scene_px[0]=NaN,
    s=>s.framing.views.landscape.rect_scene_px[0]=true,
    s=>s.framing.views.landscape.output.height=1920,
    s=>s.framing.views.landscape.output.width=4097,
    s=>s.framing.views.landscape.output.width=1.5,
    s=>s.framing.views.landscape.output.width=true,
    s=>s.framing.views.landscape.extra=true,
    s=>s.framing.views.landscape.output.extra=true,
    s=>s.framing.extra=true,
    s=>s.framing.views.authored=s.framing.views.landscape,
    s=>s.framing.views['../escape']=s.framing.views.landscape,
    s=>s.framing.views={},
    s=>s.framing.version=2,
    s=>s.framing=null,
  ];
  for(const mutate of mutations){const scene=fixture();mutate(scene);assert.throws(()=>validateScene(scene,catalog));}
  assert.throws(()=>resolveView(fixture(),'missing'),/Unknown view/);
});
check('Each view checks its own coverage at every frame',()=>{
  const scene={version:1,id:'coverage',canvas:{width:1920,height:1920,fps:4,loop_seconds:2,background:'#000000'},
    camera:{overscan:1,x_amplitude:0,y_amplitude:0,zoom_amplitude:0},groups:[],framing:dualFraming(),coverage_layers:['plate'],
    layers:[{id:'plate',asset:'paint',x:0,y:420/1920,width:1,height:1080/1920,anchor:[0,0],scale:1,rotation:0,opacity:1,visible:true,blend:'source-over',depth:0}]};
  const assets={version:1,assets:[{id:'paint',width:16,height:16}]};
  const result=auditViews(scene,assets);
  assert.equal(result.ok,false);assert.equal(result.views.portrait.ok,false);assert.equal(result.views.landscape.ok,true);
  assert.equal(result.views.landscape.frame_count,8);assert.equal(result.views.landscape.coverage_checked,true);
  assert.equal(auditScene(scene,assets).ok,false);
  scene.layers[0].motion={x_amplitude:.01,y_amplitude:0,cycles:1,phase:0};
  assert.equal(auditViews(scene,assets,['landscape']).ok,false);
  assert.throws(()=>auditViews(scene,assets,['landscape','landscape']),/unique/);
  delete scene.coverage_layers;
  assert.equal(auditViews(scene,assets).views.portrait.coverage_checked,false);
  scene.layers=[];assert.equal(auditViews(scene,assets).ok,false);
});
check('Runtime downscaling/supersampling keeps framing valid and shape-preserving',()=>{
  for(const width of [135,360,1080,2160]){
    const scene=fixture(),scale=width/1080;
    resizeSceneCanvas(scene,width,1920*scale);
    validateScene(scene,catalog);
    assert.deepEqual(scene.framing.views.landscape.rect_scene_px,[0,656.25*scale,1080*scale,607.5*scale]);
    const scaled=compileScene(scene,catalog).sample(1),original=compileScene(source,catalog).sample(1);
    for(let i=0;i<scaled.length;i++){
      assert.ok(Math.abs(scaled[i].rect[2]/original[i].rect[2]-scale)<1e-9);
      assert.ok(Math.abs(scaled[i].rect[3]/original[i].rect[3]-scale)<1e-9);
    }
  }
  assert.throws(()=>resizeSceneCanvas(fixture(),1920,1080),/aspect ratio/);
});
console.log(JSON.stringify({ok:true,checks},null,2));
