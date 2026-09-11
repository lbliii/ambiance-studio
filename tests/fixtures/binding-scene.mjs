// Repository-cleared synthetic painted-light fixture; no private film inputs.
export function bindingFixture(createCanvas){
  const images=new Map(),assets=[];
  for(const [id,colors] of [['base',['#202838']],['pumpkin',['#a64f18']],['flame',['#ff8a24','#ffdc82','#382a22']],['paint',['#44300a','#886022','#44300a']],['mask',['#ffffff']],['front',['#102438']]]){
    const c=createCanvas(colors.length*16,16),ctx=c.getContext('2d');
    for(let i=0;i<colors.length;i++){ctx.fillStyle=colors[i];ctx.fillRect(i*16,0,16,16);}
    if(id==='mask'){ctx.clearRect(0,0,4,16);ctx.clearRect(12,0,4,16);}
    const atlas=colors.length>1?{columns:colors.length,rows:1,cell_width:16,cell_height:16,frame_count:colors.length}:undefined;
    assets.push({id,file:`assets/${id}.png`,width:c.width,height:c.height,...(atlas?{atlas}:{})});images.set(id,c);
  }
  const card=(id,asset,x,y,width,height,extra={})=>({id,name:id,asset,x,y,width,height,anchor:[0,0],scale:1,rotation:0,opacity:1,visible:true,blend:'source-over',depth:0,...extra});
  const scene={version:1,id:'binding-fixture',title:'Synthetic pumpkin / moving floor',canvas:{width:128,height:96,fps:12,loop_seconds:4,background:'#080c18'},camera:{overscan:1,x_amplitude:0,y_amplitude:0,zoom_amplitude:0},groups:[],layers:[
    card('floor','base',.125,.5,.75,.375,{sockets:{origin:[0,0]},tracks:{x:{interpolation:'linear',keys:[[0,.125],[2,.25],[4,.125]]}}}),
    card('floor-paint','paint',0,0,.75,.375,{attach:{layer:'floor',socket:'origin'},cycle_seconds:4,phase_frames:0}),
    card('pumpkin','pumpkin',.4375,.3125,.125,.1875,{sockets:{wick:[.5,0]}}),
    card('flame','flame',0,0,.0625,.125,{attach:{layer:'pumpkin',socket:'wick'},anchor:[.5,1],cycle_seconds:4,phase_frames:0,tracks:{cell:{interpolation:'hold',keys:[[0,0],[1,1],[2,2],[3,0],[4,0]]},rotation:{interpolation:'linear',keys:[[0,0],[1,.2],[2,0],[3,-.2],[4,0]]}}}),
    card('front','front',.5625,.625,.125,.375)
  ],finishing:{version:1,working_space:'linear-srgb',output_space:'srgb',signals:[{id:'candle-strength',layer:'flame',values:[.25,1,0]}],illuminations:[{id:'floor-glow',layer:'floor-paint',receiver:'floor',mask_asset:'mask',mode:'add'}]},bindings:{version:1,links:[
    {id:'strength',source:{signal:'candle-strength',range:[0,1]},target:{layer:'floor-paint',channel:'opacity',range:[0,1]},map:{interpolation:'linear',keys:[[0,0],[1,1]]},off:0},
    {id:'lean',source:{layer:'flame',channel:'rotation',range:[-.2,.2]},target:{layer:'floor-paint',channel:'x',range:[-.03125,.03125]},map:{interpolation:'linear',keys:[[0,-.03125],[1,.03125]]},off:0},
    {id:'shape',source:{layer:'flame',channel:'cell'},target:{layer:'floor-paint',channel:'cell',range:[0,2]},map:{values:[0,1,2]},off:2}
  ]}};
  for(const l of scene.layers)if(l.attach)delete l.depth;
  return {scene,catalog:{version:1,assets},images};
}
