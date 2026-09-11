// Measurements only. The production sampler and timing reporter own the clock.
import {compileScene, multiply, point, inverseMatrix} from './engine.mjs';
import {sceneTiming} from './timing.mjs';
import {viewProjection} from './views.mjs';

export function intervals(flags, step, start = 0) {
  const rows = [];
  for (let i = 0; i < flags.length;) {
    const from = i, active = flags[i];
    while (i < flags.length && flags[i] === active) i++;
    rows.push({active, start_seconds: start + from * step, end_seconds: start + i * step,
      duration_seconds: (i - from) * step});
  }
  return rows;
}
const magnitude = a => Math.hypot(...a);
const subtract = (a, b) => a.map((n, i) => n - b[i]);
const range = a => [Math.min(...a), Math.max(...a)];
function corners(state, paint, projection) {
  if (!paint?.bounds_uv) return [];
  const [u,v,w,h] = paint.bounds_uv, [x,y,W,H] = state.rect;
  const m = multiply(projection, state.matrix);
  return [[u,v],[u+w,v],[u+w,v+h],[u,v+h]].map(([a,b]) => point(m,x+a*W,y+b*H));
}

export function measureActivity(scene, catalog, {views, painted, actions = [], stride = 1, start_frame = 0, frames = null}) {
  const {fps, loop_seconds} = scene.canvas, N = Math.round(fps * loop_seconds);
  frames ??= N;
  if (!Number.isInteger(stride) || stride < 1 || !Number.isInteger(start_frame) || start_frame < 0 ||
      !Number.isInteger(frames) || frames < 1 || start_frame + frames > N || frames % stride)
    throw Error('Activity requires whole output frames within one loop and a stride dividing the selected frame count');
  if (!views.length || views.length > 2 || Math.ceil(frames/stride)*scene.layers.length*views.length > 200000)
    throw Error('Activity exceeds two views or 200000 projected layer samples; reduce duration, layers or increase stride');
  const rig = compileScene(scene,catalog), samples = [];
  for (let f = start_frame; f < start_frame + frames; f += stride) samples.push(rig.sample(f/fps));
  const dt = stride/fps, timing = sceneTiming(scene,catalog);
  const report = {kind:'ambiance-state-activity',version:1,picture_seconds:loop_seconds,output_fps:fps,
    start_frame,frames,stride,sampling_hz:fps/stride,interval_semantics:'Half-open sampled windows; transitions describe the interval ending at the current sample. No unsampled motion is inferred.',
    units:{bounds:'display pixels',travel:'display pixels',speed:'display pixels/second',opacity:'unit interval'},
    timing,views:[],driver_samples:[],limits:['State movement is not observed readability. Bounds use decoded nonzero alpha before finishing and cannot establish occlusion.',
      'Local transform travel excludes inherited parent/camera motion; world travel includes both. Neither classifies a gesture.',
      'State rest windows are sample candidates, not proof of stillness between samples.']};
  for (const view of views) {
    const projection = viewProjection({...view.view,output:view.output}), rows = [];
    for (let j=0;j<scene.layers.length;j++) {
      const layer=scene.layers[j], data=[];
      for (let i=0;i<samples.length;i++) {
        const s=samples[i][j], paint=painted[s.asset]?.[s.cell];
        if (!paint) throw Error(`Missing decoded painted-cell facts: ${s.asset}/${s.cell}`);
        const polygon=corners(s,paint,projection), xs=polygon.map(p=>p[0]),ys=polygon.map(p=>p[1]);
        const bounds=polygon.length?[Math.min(...xs),Math.min(...ys),Math.max(...xs)-Math.min(...xs),Math.max(...ys)-Math.min(...ys)]:null;
        const localMatrix=multiply(inverseMatrix(s.parent),s.matrix).map(n=>Math.round(n*1e9)/1e9);
        const anchor=point(multiply(projection,s.matrix),0,0),local=point(localMatrix,0,0);
        const prev=data.at(-1),travel=prev?magnitude(subtract(anchor,prev.anchor_display_px)):0;
        const localTravel=prev?magnitude(subtract(local,prev.local_anchor_scene_px)):0;
        const cornerTravel=prev&&polygon.length&&prev.polygon_display_px.length?Math.max(...polygon.map((p,k)=>magnitude(subtract(p,prev.polygon_display_px[k])))):0;
        const eligible=s.visible&&s.opacity>0, inView=!!bounds&&bounds[0]<view.output.width&&bounds[1]<view.output.height&&bounds[0]+bounds[2]>0&&bounds[1]+bounds[3]>0;
        const changed=!!prev&&(cornerTravel>1e-7||paint.sha256!==prev.painted_sha256||s.opacity!==prev.opacity||s.visible!==prev.visible);
        data.push({frame:start_frame+i*stride,time_seconds:(start_frame+i*stride)/fps,cell:s.cell,painted_sha256:paint.sha256,
          visible:s.visible,opacity:s.opacity,render_eligible:eligible,intersects_view:inView,depth:s.depth,
          anchor_display_px:anchor,local_anchor_scene_px:local,local_matrix:localMatrix,polygon_display_px:polygon,painted_bounds_display_px:bounds,
          world_anchor_travel_px:travel,local_anchor_travel_scene_px:localTravel,painted_corner_travel_px:cornerTravel,
          travel_subject_diagonals:bounds&&magnitude(bounds.slice(2))?cornerTravel/magnitude(bounds.slice(2)):null,
          travel_output_diagonals:cornerTravel/Math.hypot(view.output.width,view.output.height),speed_px_per_second:cornerTravel/dt,
          sampled_state_changed:changed,projected_state_activity:changed&&eligible&&inView,binding_values:s.bindings??null,channels:s.channels??null});
      }
      const windows=intervals(data.map(d=>d.projected_state_activity),dt,start_frame/fps);
      rows.push({layer:layer.id,asset:layer.asset,group:layer.group??null,depth_range:range(data.map(d=>d.depth)),
        semantic_actions:actions.filter(a=>a.layers.includes(layer.id)).map(a=>a.id),
        summary:{cel_index_changes:data.slice(1).filter((d,i)=>d.cell!==data[i].cell).length,
          distinct_painted_cels:new Set(data.map(d=>d.painted_sha256)).size,world_anchor_travel_px:data.reduce((n,d)=>n+d.world_anchor_travel_px,0),
          local_anchor_travel_scene_px:data.reduce((n,d)=>n+d.local_anchor_travel_scene_px,0),max_speed_px_per_second:Math.max(...data.map(d=>d.speed_px_per_second)),
          opacity_range:range(data.map(d=>d.opacity)),eligible_samples:data.filter(d=>d.render_eligible).length,
          in_view_samples:data.filter(d=>d.intersects_view&&d.render_eligible).length,max_sampled_rest_seconds:Math.max(0,...windows.filter(w=>!w.active).map(w=>w.duration_seconds))},
        sampled_windows:windows,samples:data});
    }
    const actionRows=actions.map(a=>{
      const members=rows.filter(r=>a.layers.includes(r.layer)),windows=intervals(samples.map((_,i)=>members.some(r=>r.samples[i].projected_state_activity)),dt,start_frame/fps);
      return {...a,applicable:!a.views?.length||a.views.includes(view.view.id),sampled_windows:windows,
        state_onsets_seconds:windows.filter(w=>w.active).map(w=>w.start_seconds),max_sampled_rest_seconds:Math.max(0,...windows.filter(w=>!w.active).map(w=>w.duration_seconds)),
        observation:{status:'unreviewed',observed_level:null,observer:null,evidence:null}};
    });
    report.views.push({...view,layers:rows,actions:actionRows});
  }
  return report;
}

// Signed RGB residual changes isolate the disabled-element intervention. They
// remain confounded by overlap, nonlinear finishing and source/follower coupling.
export function pixelMetrics(current, previous, disabled = null, previousDisabled = null) {
  let total=0,max=0,changed=0,contribution=0,contributionPixels=0,temporal=0,temporalPixels=0;
  const map=new Float64Array(current.length/4);
  for(let p=0;p<current.length;p+=4){let d=0,c=0,t=0;
    for(let k=0;k<3;k++){
      d=Math.max(d,previous?Math.abs(current[p+k]-previous[p+k]):0);
      if(disabled)c=Math.max(c,Math.abs(current[p+k]-disabled[p+k]));
      if(disabled&&previousDisabled&&previous)t=Math.max(t,Math.abs((current[p+k]-disabled[p+k])-(previous[p+k]-previousDisabled[p+k])));
    }
    total+=d;max=Math.max(max,d);changed+=d>0;contribution+=c;contributionPixels+=c>0;temporal+=t;temporalPixels+=t>0;map[p/4]=disabled?t:d;
  }
  const count=current.length/4;
  return {metrics:{pixels:count,frame_changed_pixels:changed,frame_mean_max_channel_delta:total/count,frame_max_channel_delta:max,
    contribution_pixels:disabled?contributionPixels:null,contribution_mean_max_channel_delta:disabled?contribution/count:null,
    residual_changed_pixels:previousDisabled?temporalPixels:null,residual_mean_max_channel_delta:previousDisabled?temporal/count:null},map};
}

export function diagnosticWarnings(state, raster) {
  const warnings=[];
  if(state.layers.some(l=>l.summary.cel_index_changes>0&&l.summary.distinct_painted_cels===1))warnings.push('cel_indices_repeat_identical_paint');
  if(!state.layers.some(l=>l.summary.in_view_samples))warnings.push('no_projected_painted_presence');
  if(raster?.length&&raster.every(r=>r.contribution_pixels===0))warnings.push('no_measured_contribution');
  if(raster?.length>1&&raster.slice(1).every(r=>r.residual_changed_pixels===0))warnings.push('no_measured_residual_change');
  if(raster?.length&&Math.max(...raster.map(r=>r.contribution_pixels??0))>0&&Math.max(...raster.map(r=>(r.contribution_pixels??0)/r.pixels))<.0005)warnings.push('small_measured_support');
  if(raster?.length&&Math.max(...raster.map(r=>r.contribution_mean_max_channel_delta??0))>0&&Math.max(...raster.map(r=>r.contribution_mean_max_channel_delta??0))<.05)warnings.push('low_frame_average_contribution');
  return warnings;
}
