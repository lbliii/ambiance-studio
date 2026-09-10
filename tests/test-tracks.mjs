import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import fs from 'node:fs';
import {compileScene,validateScene,point} from '../editor/engine.mjs';
import {auditScene} from '../editor/audit.mjs';
const checks=[];
function check(name,fn){fn();checks.push(name);}
const catalog={assets:[{id:'paint',width:32,height:32},{id:'gait',width:128,height:32,atlas:{cell_width:32,cell_height:32,columns:4,rows:1,frame_count:4}}]};
const card=(id,extra={})=>({id,name:id,asset:'paint',x:.5,y:.5,width:.2,height:.1,anchor:[.5,.5],scale:1,rotation:0,opacity:1,visible:true,blend:'source-over',depth:0,...extra});
const scene=(layers=[card('subject')])=>({version:1,id:'track-fixture',title:'Track fixture',canvas:{width:100,height:200,fps:10,loop_seconds:4,background:'#000'},camera:{overscan:1,x_amplitude:0,y_amplitude:0,zoom_amplitude:0},groups:[],layers});
const track=(keys,interpolation='linear')=>({interpolation,keys});
const close=(a,b)=>assert.ok(Math.abs(a-b)<1e-7,`${a} differs from ${b}`);
const bridge=(s,action,args={})=>{
  const out=spawnSync(process.execPath,[new URL('../tools/scene-command.mjs',import.meta.url).pathname],{input:JSON.stringify({scene:s,catalog,action,args}),encoding:'utf8'});
  return {...JSON.parse(out.stdout),exit:out.status};
};
const batch=(s,operations)=>bridge(s,'apply',{batch:{version:1,operations}});
check('Legacy layer values, periodic motion and source timing remain unchanged',()=>{
  const s=scene([card('old',{asset:'gait',cycle_seconds:2,phase_frames:1,motion:{x_amplitude:.1,y_amplitude:.05,cycles:1,phase:0,rotation_amplitude:0}})]);
  const rig=compileScene(s,catalog);
  for(const t of [0,.13,1,2,3.7,4,-1]){
    const wrapped=((t%4)+4)%4,p=Math.PI*2*wrapped/4,a=rig.sample(t)[0];
    close(a.matrix[4],(.5+.1*Math.sin(p))*100);close(a.matrix[5],(.5+.05*Math.sin(2*p))*200);
    assert.equal(a.cell,(Math.floor(wrapped/2*4+1e-7)+1)%4);
    assert.equal(a.visible,true);assert.equal(a.opacity,1);
  }
});
check('Absolute keyframe interpolation, stops, scaling, rotation and opacity survive arbitrary seeking',()=>{
  const s=scene([card('subject',{tracks:{x:track([[0,.1],[1,.9],[2,.9],[4,.1]]),scale:track([[0,1],[2,2],[4,1]],'smoothstep'),rotation:track([[0,0],[2,.6],[4,0]]),opacity:track([[0,1],[2,.4],[4,1]])}})]);
  const rig=compileScene(s,catalog),a=rig.sample(.5)[0];
  close(a.matrix[4],50);close(a.opacity,.85);close(Math.hypot(a.matrix[0],a.matrix[1]),1.15625);
  close(rig.sample(1.5)[0].matrix[4],90);
  const original=rig.sample(1.2);s.layers[0].tracks.x.keys[0][1]=99;rig.sample(3.9);
  assert.deepEqual(rig.sample(1.2),original);assert.deepEqual(rig.sample(0),rig.sample(4));
});
check('Scheduled cels hold and per-cel attachment sockets follow the scheduled source frame',()=>{
  const parent=card('parent',{asset:'gait',cycle_seconds:2,phase_frames:0,sockets:{foot:{frames:[[0,0],[.25,.25],[.5,.5],[1,1]]}},tracks:{cell:track([[0,0],[.5,2],[2,3],[4,0]],'hold')}});
  const child=card('child',{x:0,y:0,attach:{layer:'parent',socket:'foot'}});delete child.depth;
  const rig=compileScene(scene([child,parent]),catalog);
  assert.equal(rig.sample(1.9)[1].cell,2);assert.equal(rig.sample(2)[1].cell,3);
  for(const t of [0,.5,1.2,2,3.9])assert.deepEqual(point(rig.sample(t)[0].matrix,0,0),rig.sample(t)[1].sockets.foot);
});
check('Near and far route instances reset while hidden, with fixed paint order and no depth sorting',()=>{
  const near=card('near-rat',{track_loop:'hidden-reset',tracks:{x:track([[0,-.1],[2,1.1],[4,1.1]]),visible:track([[0,false],[.2,true],[2.5,false],[4,false]],'hold')}});
  const far=card('far-rat',{depth:9,scale:.3,track_loop:'hidden-reset',tracks:{x:track([[0,1.1],[2,1.1],[3.7,-.1],[4,-.1]]),visible:track([[0,false],[2,true],[3.8,false],[4,false]],'hold')}});
  const s=scene([far,card('arch-occluder'),near,card('foreground-occluder')]),rig=compileScene(s,catalog);
  for(const t of [0,.2,2,3.7,3.9,4])assert.deepEqual(rig.sample(t).map(s=>s.id),s.layers.map(l=>l.id));
  assert.equal(rig.sample(0)[0].visible,false);assert.equal(rig.sample(0)[2].visible,false);
  assert.equal(rig.sample(3)[0].visible,true);assert.equal(rig.sample(3)[2].visible,false);
  assert.equal(auditScene(s,catalog).ok,true);
});
check('Track contracts reject gaps, unknown fields, non-finite values, bad ranges and visible seam teleports',()=>{
  const mutations=[
    l=>l.tracks={x:track([[.1,0],[4,0]])},
    l=>l.tracks={x:track([[0,0],[3,0]])},
    l=>l.tracks={x:track([[0,0],[1,0],[1,.5],[4,0]])},
    l=>l.tracks={x:track([[0,0],[4,1]])},
    l=>l.tracks={x:track([[0,NaN],[4,NaN]])},
    l=>l.tracks={depth:track([[0,0],[4,0]])},
    l=>l.tracks={scale:track([[0,1],[2,0],[4,1]])},
    l=>l.tracks={opacity:track([[0,1],[2,2],[4,1]])},
    l=>l.tracks={visible:track([[0,true],[4,true]])},
    l=>l.tracks={cell:track([[0,0],[4,0]],'hold')},
    l=>{l.asset='gait';l.cycle_seconds=2;l.phase_frames=0;l.tracks={cell:track([[0,0],[2,4],[4,0]],'hold')};},
    l=>{l.track_loop='hidden-reset';l.tracks={x:track([[0,0],[4,1]])};},
    l=>{l.track_loop='hidden-reset';l.tracks={visible:track([[0,false],[.01,true],[3,false],[4,false]],'hold')};},
    l=>{l.track_loop='hidden-reset';l.tracks={visible:track([[0,false],[1,true],[4,false]],'hold')};},
    l=>l.track_loop='hidden-reset',
    l=>l.tracks={x:{...track([[0,0],[4,0]]),typo:1}}
  ];
  for(const mutate of mutations){const s=scene();mutate(s.layers[0]);assert.throws(()=>validateScene(s,catalog));}
});
check('One batch builds a nested casket rig and preserves explicit front rim overlap and stationary glass',()=>{
  const s=scene([]),operations=[
    {op:'add',asset:'paint',id:'body'},
    {op:'attach',layer:'body',to:'casket',socket:'bed'},
    {op:'add',asset:'paint',id:'casket',values:{x:.4,y:.6}},
    {op:'socket',layer:'casket',name:'bed',value:[.5,.5]},
    {op:'add',asset:'paint',id:'hand'},
    {op:'socket',layer:'body',name:'wrist',value:[.4,.5]},
    {op:'attach',layer:'hand',to:'body',socket:'wrist'},
    {op:'add',asset:'paint',id:'front-rim'},
    {op:'attach',layer:'front-rim',to:'casket',socket:'bed'},
    {op:'add',asset:'paint',id:'stationary-glass'},
    {op:'set',layer:'casket',values:{tracks:{y:track([[0,.6],[2,.5],[4,.6]])}}},
    {op:'order',layers:['casket','body','hand','front-rim','stationary-glass']}
  ];
  const result=batch(s,operations);assert.equal(result.ok,true,result.error);assert.equal(result.exit,0);assert.equal(s.layers.length,0);
  const rig=compileScene(result.data,catalog),start=rig.sample(0),lift=rig.sample(2);
  assert.deepEqual(lift.map(l=>l.id),operations.at(-1).layers);
  for(let i=0;i<4;i++)close(lift[i].matrix[5]-start[i].matrix[5],-20);
  assert.deepEqual(lift[4].matrix,start[4].matrix);
  assert.deepEqual(point(lift[2].matrix,0,0),lift[1].sockets.wrist);
});
check('Batch updates groups, camera, tracked sockets, complete replacement and optional field removal',()=>{
  const s=scene([card('subject',{asset:'gait',cycle_seconds:2,phase_frames:0})]);
  const operations=[{op:'group',id:'rig',value:{x:.1,y:0,scale:1,depth:.3,pivot:[.5,.5]}},
    {op:'set',layer:'subject',values:{group:'rig'},unset:['depth']},
    {op:'camera',values:{overscan:1.1}},
    {op:'socket',layer:'subject',name:'wick',value:{frames:[[0,0],[0,.1],[0,.2],[0,.3]]}}];
  let result=batch(s,operations);assert.equal(result.ok,true,result.error);
  assert.equal(bridge(result.data,'inspect',{full:true}).data.groups[0].id,'rig');
  result=batch(result.data,[{op:'replace',layer:'subject',value:card('subject')},{op:'group',id:'rig',value:null}]);
  assert.equal(result.ok,true,result.error);assert.equal(result.data.groups.length,0);assert.deepEqual(result.data.layers[0],card('subject'));
});
check('Invalid batches yield no candidate scene and removals require explicit dependency handling',()=>{
  const s=scene([card('parent',{sockets:{base:[.5,.5]}}),card('child',{x:0,y:0,attach:{layer:'parent',socket:'base'}})]);delete s.layers[1].depth;
  const before=JSON.stringify(s);
  for(const operations of [[{op:'set',layer:'parent',values:{x:.2}},{op:'set',layer:'child',values:{scale:-1}}],
    [{op:'remove',layer:'parent'}],[{op:'order',layers:['parent','parent']}],
    [{op:'set',layer:'parent',values:{roation:2}}],[{op:'replace',layer:'parent',value:card('renamed')}],
    [{op:'set',layer:'parent',values:{scale:1},unset:['width']}],
    [{op:'socket',layer:'parent',name:'constructor',value:[0,0]}]]){
    const result=batch(s,operations);assert.equal(result.ok,false);assert.equal(result.exit,2);assert.equal(result.data,undefined);
  }
  assert.equal(JSON.stringify(s),before);
  const result=batch(s,[{op:'remove',layer:'parent',cascade:true}]);assert.equal(result.ok,true);assert.equal(result.data.layers.length,0);
  const covered=scene();covered.coverage_layers=['subject'];assert.equal(batch(covered,[{op:'remove',layer:'subject'}]).ok,false);
  assert.equal(batch(covered,[{op:'coverage',layers:[]},{op:'remove',layer:'subject'}]).ok,true);
});
check('Saved route and compound-rig examples validate and sample through the same bridge',()=>{
  for(const name of ['rat-route-batch.json','casket-rig-batch.json']){
    const example=JSON.parse(fs.readFileSync(new URL(`../examples/scene-transactions/${name}`,import.meta.url)));
    const result=bridge(scene([]),'apply',{batch:example});assert.equal(result.ok,true,result.error);assert.equal(auditScene(result.data,catalog).ok,true);
  }
});
console.log(JSON.stringify({ok:true,checks},null,2));
