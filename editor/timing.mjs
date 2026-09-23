// Reporting only: use the production sampler for cel selection and inheritance.
import {compileScene,ENGINE_VERSION} from './engine.mjs';
import {consumerTime} from './clock.mjs';
const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
function runs(values,describe){
  const result=[];let start=0;
  for(let i=1;i<=values.length;i++)if(i===values.length||!same(values[i],values[start])){
    result.push({start_frame:start,end_frame_exclusive:i,...describe(values[start])});start=i;
  }
  return result;
}
function windows(values,fps,predicate){
  return runs(values,v=>({selected:predicate(v)})).filter(r=>r.selected).map(({start_frame,end_frame_exclusive})=>({start_frame,end_frame_exclusive,start_seconds:start_frame/fps,end_seconds:end_frame_exclusive/fps}));
}
export function sceneTiming(scene,catalog,{layer:filter}={}){
  const rig=compileScene(scene,catalog),{fps,loop_seconds:T}=scene.canvas,N=rig.clock.duration_frames;
  const selected=filter?scene.layers.filter(l=>l.id===filter):scene.layers;
  if(filter&&!selected.length)throw Error(`Unknown layer: ${filter}`);
  if(N*Math.max(1,scene.layers.length)>2_000_000)throw Error('Timing report exceeds two million layer samples; reduce the diagnostic scene or output clock');
  const ids=new Set(selected.map(l=>l.id)),sampled=new Map(selected.map(l=>[l.id,[]]));
  for(let f=0;f<N;f++)for(const state of rig.sampleFrame(f))if(ids.has(state.id)){
    sampled.get(state.id).push({cell:state.cell,visible:state.visible,zero_opacity:state.opacity===0,render_eligible:state.visible&&state.opacity>0});
  }
  const assets=new Map(catalog.assets.map(a=>[a.id,a]));
  const layers=selected.map(layer=>{
    const asset=assets.get(layer.asset),count=asset.atlas?.frame_count||1;
    const binding=scene.bindings?.links.find(b=>b.target.layer===layer.id&&b.target.channel==='cell');
    const driver=binding?'binding':layer.tracks?.cell?'cell_track':count>1?(layer.local_cycle?'local_cycle':'cycle'):'static';
    const fallback=asset.atlas?{seconds:layer.cycle_seconds,phase_frames:layer.phase_frames,nominal_cel_fps:count/layer.cycle_seconds,active:driver==='cycle'}:null;
    let boundaries=driver==='binding'?[]:[0,T];
    if(layer.local_cycle&&driver!=='binding'){
      const local=consumerTime(rig.clock.frame(0),layer.local_cycle),P=local.duration;
      const offsets=layer.tracks?.cell?layer.tracks.cell.keys.slice(0,-1).map(k=>k[0]):Array.from({length:count},(_,i)=>i*P/count);
      if(Math.ceil(T/P+2)*offsets.length>100000)throw Error(`Too many local cel intervals: ${layer.id}`);
      boundaries=[0,T];for(let turn=-1;turn<=Math.ceil(T/P)+1;turn++)for(const offset of offsets){const t=turn*P+offset-local.seconds;if(t>0&&t<T)boundaries.push(t);}
      boundaries=[...new Set(boundaries)].sort((a,b)=>a-b);
    }else if(driver==='cell_track')boundaries=layer.tracks.cell.keys.map(k=>k[0]);
    else if(driver==='cycle'){
      const events=Math.ceil(T/layer.cycle_seconds*count);
      if(events>100000)throw Error(`Timing report exceeds 100000 authored cel intervals: ${layer.id}`);
      boundaries=Array.from({length:events+1},(_,i)=>i===events?T:i*layer.cycle_seconds/count);
    }
    const holds=[];
    for(let i=0;i<boundaries.length-1;i++){
      const start=boundaries[i],end=boundaries[i+1];
      const cell=rig.sample((start+end)/2).find(s=>s.id===layer.id).cell;
      if(holds.length&&holds.at(-1).cell===cell)holds.at(-1).end_seconds=end;
      else holds.push({start_seconds:start,end_seconds:end,cell});
    }
    for(const h of holds)h.duration_seconds=h.end_seconds-h.start_seconds;
    const rates=[];
    for(const h of holds){
      const previous=rates.at(-1);
      if(previous&&Math.abs(previous.hold_seconds-h.duration_seconds)<1e-9){previous.end_seconds=h.end_seconds;previous.cel_holds++;}
      else rates.push({start_seconds:h.start_seconds,end_seconds:h.end_seconds,hold_seconds:h.duration_seconds,cel_holds:1});
    }
    for(const r of rates)r.cel_selection_hz=r.cel_holds>=2?1/r.hold_seconds:null;
    const values=sampled.get(layer.id),segments=runs(values,v=>v);
    const visibility=windows(values.map(v=>v.visible),fps,v=>v);
    const zeroOpacity=windows(values.map(v=>v.zero_opacity),fps,v=>v);
    const eligible=windows(values.map(v=>v.render_eligible),fps,v=>v);
    const unpresented=[];
    for(const h of holds){
      const first=Math.max(0,Math.ceil(h.start_seconds*fps-1e-9));
      const end=Math.min(N,Math.ceil(h.end_seconds*fps-1e-9));
      if(first>=end||!values.slice(first,end).some(v=>v.cell===h.cell))unpresented.push({...h});
    }
    let transitions=0,visibleTransitions=0;
    for(let i=1;i<N;i++)if(values[i].cell!==values[i-1].cell){transitions++;if(values[i].render_eligible&&values[i-1].render_eligible)visibleTransitions++;}
    const first=values[0],last=values.at(-1),endpoint=rig.sampleFrame(N).find(s=>s.id===layer.id);
    let leading=0,trailing=0;
    while(leading<N&&!values[leading].render_eligible)leading++;
    while(trailing<N&&!values[N-1-trailing].render_eligible)trailing++;
    return {layer:layer.id,asset:layer.asset,local_cycle:layer.local_cycle??null,endpoint:{cell:endpoint.cell,visible:endpoint.visible,opacity:endpoint.opacity},last_exported:last,timing_driver:driver,fallback_cycle:fallback,
      binding:binding??null,authored:{available:driver!=='binding',reason:driver==='binding'?'Binding follows evaluated source; consult sampled intervals and binding inspection for exact at-time values.':null,holds,rate_segments:rates,cel_changes:driver==='binding'?null:holds.length-1,seam_cel_change:driver==='binding'||rig.clock.mode==='finite'?null:holds.at(-1).cell!==holds[0].cell},
      sampled:{segments,cel_transitions:transitions,render_eligible_cel_transitions:visibleTransitions,
        seam_cel_change:rig.clock.mode==='loop'?last.cell!==first.cell:null,unpresented_authored_holds:unpresented,
        effective_visibility_windows:visibility,zero_opacity_intervals:zeroOpacity,render_eligible_windows:eligible},
      join:{declared_policy:rig.clock.mode==='finite'?'finite-endpoint':layer.track_loop||'closed',leading_nonrendered_frames:leading,trailing_nonrendered_frames:trailing,
        first_render_eligible:first.render_eligible,last_render_eligible:last.render_eligible}};
  });
  return {version:1,engine_version:ENGINE_VERSION,scene:scene.id,clock:rig.clock.frame(N),last_exported_clock:rig.clock.frame(N-1),picture_seconds:T,output_fps:fps,output_frames:N,layers,
    limits:['Authored holds describe source-cel indices, not distinct painted drawings or different decoded pixels.',
      'Visibility/opacity come from the shared evaluator and parent inheritance; painted occluders and offscreen placement are not evaluated.',
      'Sampled presentation uses exactly frames 0 through N-1. Authored subframe cel intervals may have no output sample.',
      'A rate is reported only across consecutive equal-duration authored holds; isolated and variable holds remain explicit intervals.']};
}
