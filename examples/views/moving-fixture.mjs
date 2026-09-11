// Independent local art for view/rig/finishing tests; no generation provider.
export function movingFixture(createCanvas) {
  const images = new Map(), assets = [];
  function art(id, width, height, paint, extra = {}) {
    const canvas = createCanvas(width, height); paint(canvas.getContext('2d'));
    images.set(id, canvas); assets.push({id, kind:extra.atlas?'atlas':'plate', file:`assets/${id}.png`, width, height, ...extra});
  }
  art('room', 160, 160, ctx => {
    ctx.fillStyle='#263545';ctx.fillRect(0,0,160,160);
    ctx.strokeStyle='#637981';ctx.lineWidth=1;
    for(let n=0;n<160;n+=20){ctx.beginPath();ctx.moveTo(n,0);ctx.lineTo(n,160);ctx.moveTo(0,n);ctx.lineTo(160,n);ctx.stroke();}
    ctx.fillStyle='#cf8759';ctx.fillRect(0,0,24,24);ctx.fillStyle='#6eaaa0';ctx.fillRect(136,136,24,24);
  });
  art('body', 32, 32, ctx => {ctx.fillStyle='#e4be82';ctx.beginPath();ctx.arc(16,16,14,0,Math.PI*2);ctx.fill();ctx.strokeStyle='#5b4225';ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(16,5);ctx.lineTo(16,27);ctx.moveTo(5,16);ctx.lineTo(27,16);ctx.stroke();});
  art('hand', 32, 16, ctx => {
    ctx.fillStyle='#f4ddb0';ctx.fillRect(1,6,14,5);ctx.fillStyle='#7eddd4';ctx.fillRect(19,1,5,14);
  }, {atlas:{columns:2,rows:1,cell_width:16,cell_height:16,frame_count:2}});
  art('rim', 32, 8, ctx => {ctx.fillStyle='#709f9e';ctx.fillRect(0,0,32,8);});
  const layer=(id,asset,x,y,width,height,extra={})=>({id,name:id,asset,x,y,width,height,anchor:[.5,.5],scale:1,rotation:0,opacity:1,visible:true,blend:'source-over',depth:0,...extra});
  const scene={version:1,id:'moving-views',title:'One scene · two views',
    canvas:{width:160,height:160,fps:8,loop_seconds:2,background:'#13202c'},
    camera:{overscan:1.04,x_amplitude:.008,y_amplitude:.008,zoom_amplitude:.01},groups:[],coverage_layers:['room'],
    framing:{version:1,views:{portrait:{rect_scene_px:[35,0,90,160],output:{width:1080,height:1920}},landscape:{rect_scene_px:[0,35,160,90],output:{width:1920,height:1080}}}},
    layers:[layer('room','room',.5,.5,1.1,1.1),
      layer('body','body',.5,.48,.28,.28,{depth:.6,sockets:{wrist:[.8,.35]},motion:{x_amplitude:.08,y_amplitude:.02,rotation_amplitude:.08,cycles:1,phase:0}}),
      layer('hand','hand',0,0,.14,.14,{attach:{layer:'body',socket:'wrist'},cycle_seconds:1,phase_frames:0}),
      layer('fixed-rim','rim',.5,.64,.7,.045,{depth:0})],
    finishing:{version:1,working_space:'linear-srgb',output_space:'srgb',grade:{saturation:.9},
      lights:[{id:'cool-window',receivers:['room','body','hand'],rect:[.25,.1,.58,.8],color:'#619dda',gain:.35,feather:.2}],
      shadows:[{id:'body-shadow',caster:'body',receiver:'room',offset:[.02,.06],scale:[1.1,.35],opacity:.5,softness:.015}],
      reflections:[{id:'body-reflection',caster:'body',receiver:'room',offset:[0,.02],scale:[1,.6],opacity:.35,softness:.01}]}};
  delete scene.layers[2].depth;
  return {scene,catalog:{version:1,assets},images};
}
