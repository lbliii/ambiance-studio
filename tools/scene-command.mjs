// JSON stdin/stdout bridge. All scene semantics stay in the shared evaluator.
import fs from 'node:fs';
import {compileScene,validateScene} from '../editor/engine.mjs';
const input=JSON.parse(fs.readFileSync(0,'utf8'));
try{
  const {action,catalog,args={}}=input,scene=structuredClone(input.scene);
  validateScene(scene,catalog);
  const layer=id=>{const l=scene.layers.find(l=>l.id===id);if(!l)throw Error(`Unknown layer: ${id}`);return l;};
  let result;
  if(action==='sample')result=compileScene(scene,catalog).sample(args.time);
  else if(action==='inspect')result={id:scene.id,title:scene.title,canvas:scene.canvas,layers:scene.layers};
  else {
    if(action==='set'){
      const l=layer(args.layer);
      for(const key of ['x','y','scale','opacity','depth','cycle_seconds','phase_frames'])if(args[key]!==null&&args[key]!==undefined)l[key]=args[key];
      if(args.rotation_deg!==null&&args.rotation_deg!==undefined)l.rotation=args.rotation_deg*Math.PI/180;
    }else if(action==='socket'){
      if(!/^[A-Za-z][A-Za-z0-9_-]{0,39}$/.test(args.name)||['constructor','prototype'].includes(args.name))throw Error('Invalid socket name');
      const l=layer(args.layer);l.sockets||={};l.sockets[args.name]=[args.u,args.v];
    }else if(action==='attach'){
      const l=layer(args.layer);layer(args.to);
      l.attach={layer:args.to,socket:args.socket};delete l.depth;delete l.group;
      l.x=args.offset_x||0;l.y=args.offset_y||0;
    }else if(action==='add'){
      if(scene.layers.some(l=>l.id===args.id))throw Error(`Layer already exists: ${args.id}`);
      const a=catalog.assets.find(a=>a.id===args.asset);if(!a)throw Error(`Unknown asset: ${args.asset}`);
      const w=a.atlas?.cell_width||a.width,h=a.atlas?.cell_height||a.height;
      const l={id:args.id,name:args.name||args.id,asset:a.id,x:args.x??.5,y:args.y??.5,
        width:args.width??.35,height:(args.width??.35)*scene.canvas.width/scene.canvas.height*h/w,
        anchor:a.pivot||[.5,.5],scale:1,rotation:0,opacity:1,visible:true,blend:'source-over',depth:args.depth??.8};
      if(a.atlas){l.cycle_seconds=scene.canvas.loop_seconds/4;l.phase_frames=0;}scene.layers.push(l);
    }else if(action==='restore'){
      validateScene(args.snapshot,catalog);result=args.snapshot;
    }else throw Error(`Unsupported scene operation: ${action}`);
    result||=scene;validateScene(result,catalog);
  }
  console.log(JSON.stringify({ok:true,data:result}));
}catch(e){console.log(JSON.stringify({ok:false,error:e.message}));process.exitCode=2;}
