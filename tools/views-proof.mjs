export function viewsProofPage(views, fps, start, frames, loopSeconds, {measurePlayback=false,alphaDiagnostics=[]}={}) {
  const payload = JSON.stringify({views, fps, start, frames, loopSeconds, measurePlayback, alphaDiagnostics}).replaceAll('<', '\\u003c');
  return `<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Portrait and landscape proof</title>
<style>body{background:#171a21;color:#f1eee7;font:16px system-ui;margin:28px}h1{font:32px Georgia}p{max-width:75ch;color:#b4b6be}main{display:flex;align-items:start;gap:24px;flex-wrap:wrap}figure{margin:0;max-width:100%}canvas{display:block;max-width:100%;height:auto;background:#000}figcaption{margin:14px 0 8px}button,select,input{font:inherit;margin:8px 12px 8px 0}#seek{width:min(500px,80vw)}output{font-variant-numeric:tabular-nums}.diagnostic{margin:24px 0;padding:20px;border:1px solid #4a505e;border-radius:8px}.diagnostic-images{display:flex;gap:20px;flex-wrap:wrap}.diagnostic img{display:block;max-width:100%;height:auto;image-rendering:pixelated;background:repeating-conic-gradient(#353b45 0% 25%,#20242c 0% 50%) 0/16px 16px}.diagnostic h3{margin-top:0}.diagnostic a{color:#aedaff}.diagnostic pre{white-space:pre-wrap;font-size:13px}</style>
<h1>One scene, shared timing</h1><p>Each view comes from the same finished scene at the same time. This saved segment repeats for inspection; a partial-loop restart is an arbitrary cut. Visual and encoded-movie reviews remain separate.</p>
<button id="play" disabled>Pause</button><label>Speed <select id="speed"><option value="1">1× (actual speed)</option><option value=".5">0.5×</option></select></label><br>
<label>Frame <input id="seek" type="range" min="0" value="0"></label><output id="status">Loading frames…</output><main id="panes"></main><section id="alpha-diagnostics" aria-label="Painted alpha diagnostics"></section>
<script>
const config=${payload},seek=document.querySelector('#seek'),status=document.querySelector('#status'),play=document.querySelector('#play');
const diagnosticRoot=document.querySelector('#alpha-diagnostics');
if(config.alphaDiagnostics.length){
  const title=document.createElement('h2');title.textContent='Painted alpha diagnostics';diagnosticRoot.append(title);
  const note=document.createElement('p');note.textContent='Exact worst frames from the all-frame audit, before background fill and finishing. These may fall outside the saved playback segment. Reduced resolution can miss small holes; opaque unrelated paint cannot be diagnosed by alpha.';diagnosticRoot.append(note);
}
for(const item of config.alphaDiagnostics){
  const card=document.createElement('article');card.className='diagnostic';card.dataset.view=item.view_id;
  const title=document.createElement('h3');title.textContent=item.view_id+' · source frame '+item.frame+' · '+item.time_seconds.toFixed(3)+' s · '+item.resolution.join(' × ');card.append(title);
  const summary=document.createElement('p');summary.textContent='Alpha < '+item.alpha.threshold+': '+item.alpha.all.count+' pixels. Interior: '+item.alpha.interior.count+'; boundary ('+item.alpha.boundary_pixels+' px): '+item.alpha.boundary.count+'. Boundary filtering does not change the failing audit result.';card.append(summary);
  const grid=document.createElement('div');grid.className='diagnostic-images';
  for(const [key,label] of [['frame_image','Measured painted alpha'],['heatmap','Heatmap · magenta interior / amber boundary']]){
    const figure=document.createElement('figure'),caption=document.createElement('figcaption'),link=document.createElement('a'),image=new Image();
    caption.textContent=label;link.href=item[key].file;image.src=item[key].file;image.alt=item.view_id+' '+label;image.width=item.resolution[0];image.height=item.resolution[1];link.append(image);figure.append(caption,link);grid.append(figure);
  }
  card.append(grid);
  const details=document.createElement('details'),label=document.createElement('summary'),text=document.createElement('pre');label.textContent='Defect bounds and bounded coordinates';text.textContent=JSON.stringify(item.alpha,null,2);details.append(label,text);card.append(details);
  const link=document.createElement('a');link.href=item.metadata.file;link.textContent='Exact source, renderer, view and raster metadata (JSON)';card.append(link);diagnosticRoot.append(card);
}
let playing=true,clock=0,last=performance.now();
let measurements;
function resetMeasurements(){measurements={elapsed_seconds:0,observed_frame_updates:0,skipped_frame_steps:0,long_tick_gaps:0,previous_frame:null};}
resetMeasurements();
function measurePresentation(frame,seconds){if(!config.measurePlayback)return;const m=measurements,speed=Number(document.querySelector('#speed').value);m.elapsed_seconds+=seconds;if(m.previous_frame!==null){const steps=(frame-m.previous_frame+config.frames)%config.frames;if(steps){m.observed_frame_updates++;m.skipped_frame_steps+=Math.max(0,steps-1);}}if(seconds>=config.frames/config.fps/speed)m.long_tick_gaps++;m.previous_frame=frame;document.querySelector('#panes').dataset.playbackMetrics=JSON.stringify({...m,observed_updates_per_second:m.elapsed_seconds?m.observed_frame_updates/m.elapsed_seconds:null,configured_fps:config.fps,playback_rate:speed,scope:'Browser presentation samples since last seek/resume/speed change; not observer readability'});}
const panes=config.views.map(view=>{const figure=document.createElement('figure'),label=document.createElement('figcaption'),canvas=document.createElement('canvas');canvas.width=view.output.width;canvas.height=view.output.height;canvas.setAttribute('aria-label',view.id+' view');label.textContent=view.id+' · '+canvas.width+' × '+canvas.height;figure.append(label,canvas);document.querySelector('#panes').append(figure);return {canvas,ctx:canvas.getContext('2d'),images:view.files.map(file=>{const image=new Image();image.src=file;return image;})};});
seek.max=config.frames-1;
function draw(frame){for(const pane of panes){pane.ctx.clearRect(0,0,pane.canvas.width,pane.canvas.height);pane.ctx.drawImage(pane.images[frame],0,0);pane.canvas.dataset.frame=frame;}seek.value=frame;status.textContent=((config.start+frame/config.fps)%config.loopSeconds).toFixed(3)+' s · frame '+frame;}
Promise.all(panes.flatMap(p=>p.images.map(image=>image.decode()))).then(()=>{draw(0);play.disabled=false;last=performance.now();function tick(now){if(playing){clock=(clock+Math.max(0,now-last)/1000*Number(document.querySelector('#speed').value))%(config.frames/config.fps);const frame=Math.floor(clock*config.fps);draw(frame);measurePresentation(frame,Math.max(0,now-last)/1000);}last=now;requestAnimationFrame(tick);}requestAnimationFrame(tick);}).catch(error=>{status.textContent='Could not load proof: '+error.message;});
play.onclick=()=>{playing=!playing;last=performance.now();if(playing)resetMeasurements();play.textContent=playing?'Pause':'Play';};seek.oninput=()=>{playing=false;resetMeasurements();play.textContent='Play';const frame=Number(seek.value);clock=frame/config.fps;draw(frame);};document.querySelector('#speed').onchange=resetMeasurements;
</script></html>`;
}
