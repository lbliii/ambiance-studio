// Region demand uses the actual scene sampler and source/view mappings.
import {compileScene, multiply, point} from './engine.mjs';
import {referenceMapping} from './source-placement.mjs';
import {resolveView, viewProjection} from './views.mjs';

export function largestScale(m) {
  const [a,b,c,d]=m, x=a*a+b*b, y=c*c+d*d, z=a*c+b*d;
  return Math.sqrt((x+y+Math.hypot(x-y,2*z))/2);
}

export function regionDemand(scene,catalog,options) {
  const {base,reference,bounds,views,start_frame=0,frames}=options;
  const N=Math.round(scene.canvas.fps*scene.canvas.loop_seconds), count=frames??N;
  if(!Number.isInteger(start_frame)||start_frame<0||!Number.isInteger(count)||count<1||start_frame+count>N)
    throw Error('Region sizing needs whole output frames within one loop');
  if(!Array.isArray(views)||!views.length||views.length>8||new Set(views).size!==views.length||count*views.length>200000)
    throw Error('Region sizing requires 1–8 unique views and at most 200000 samples');
  if(!Array.isArray(bounds)||bounds.length!==4||!bounds.every(Number.isFinite))throw Error('Invalid region bounds');
  const layer=scene.layers.find(l=>l.id===base), asset=catalog.assets.find(a=>a.id===layer?.asset);
  if(!asset||(asset.atlas?.frame_count??1)!==1)throw Error('Region base must be an existing one-cell source plane');
  const B=referenceMapping(asset,reference), cw=asset.atlas?.cell_width??asset.width, ch=asset.atlas?.cell_height??asset.height;
  const rig=compileScene(scene,catalog), resolved=views.map(id=>resolveView(scene,id));
  const rows=resolved.map(v=>({id:v.id,output:v.output,max_density:0,maximum_frame:null,intersects_view:false,fully_contained_every_frame:true}));
  let maximum=0,cause=null;
  for(let frame=start_frame;frame<start_frame+count;frame++){
    const state=rig.sample(frame/scene.canvas.fps).find(l=>l.id===base), [x,y,w,h]=state.rect;
    const sourceToScene=multiply(state.matrix,multiply([w/cw,0,0,h/ch,x,y],B));
    for(let i=0;i<resolved.length;i++){
      const m=multiply(viewProjection(resolved[i]),sourceToScene),density=largestScale(m),row=rows[i];
      if(!Number.isFinite(density)||density<=0)throw Error('Invalid projected region density');
      if(density>row.max_density){row.max_density=density;row.maximum_frame=frame;row.source_to_output=m;}
      if(density>maximum){maximum=density;cause={view:row.id,frame,time_seconds:frame/scene.canvas.fps};}
      const [l,t,r,b]=bounds, pts=[[l,t],[r,t],[r,b],[l,b]].map(p=>point(m,...p));
      const xs=pts.map(p=>p[0]),ys=pts.map(p=>p[1]);
      row.intersects_view ||= Math.min(...xs)<row.output.width&&Math.max(...xs)>0&&Math.min(...ys)<row.output.height&&Math.max(...ys)>0;
      row.fully_contained_every_frame &&= Math.min(...xs)>=0&&Math.max(...xs)<=row.output.width&&Math.min(...ys)>=0&&Math.max(...ys)<=row.output.height;
    }
  }
  return {max_density:maximum,cause,views:rows,start_frame,frames:count,fps:scene.canvas.fps,
    scope:'Every output-frame time in the declared interval; no hidden-paint or occlusion inference.'};
}
