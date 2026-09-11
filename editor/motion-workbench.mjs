const $=id=>document.getElementById(id);
const packet=await fetch('packet.json').then(r=>r.json());
let study=structuredClone(packet.study),sol=packet.solution,draft=false,playing=true,t=0,last=performance.now(),sequence=0,draftImages=null;
const images=new Map();
async function getImage(src){if(!images.has(src)){const im=new Image();const promise=new Promise((resolve,reject)=>{im.onload=()=>resolve(im);im.onerror=()=>reject(Error(`Image unavailable: ${src}`));});im.src=src;images.set(src,promise);}return images.get(src);}
await Promise.all([...packet.images.original,...packet.images.candidate,...packet.images.raw].map(getImage));
if(packet.scene?.ok)await Promise.all(packet.scene.frames.flat().map(getImage));
$('mode').querySelector('[value=scene]').disabled=!packet.scene?.ok;
for(const [name,mark] of Object.entries(study.landmarks)){const option=new Option(`${name} · ${mark.role}`,name);$('landmark').add(option);}
for(const f of packet.findings)$('finding').add(new Option(`${f.id}${f.reason?' · '+f.reason:''}`,f.id));
for(const file of [...packet.contacts,...(packet.transition_strips||[]),'packet.json','report.json']){const a=document.createElement('a');a.href=file;a.textContent=file;a.style.marginRight='14px';$('links').append(a);}
$('evidence').textContent=JSON.stringify({clock:packet.clock,solution:sol,regions:packet.regional,limits:packet.limits},null,2);
function clock(){return $('mode').value==='scene'?{seconds:packet.scene.seconds,fps:packet.scene.fps}:packet.clock;}
function segment(){return packet.clock.segments.find(r=>t>=r.start&&t<r.end)||packet.clock.segments[0];}
function selectedCel(){if($('mode').value==='scene'){const absolute=(packet.scene.start+t)%packet.scene.loop_seconds;return packet.clock.segments.find(r=>absolute>=r.start&&absolute<r.end)?.cell??0;}return segment().cell;}
function sourceToCell(i,p){const m=study.baseline.mapping.cels[i].raw_cel_to_cell;return [m[0]*p[0]+m[2]*p[1]+m[4],m[1]*p[0]+m[3]*p[1]+m[5]];}
function alignment(i){return $('align').checked&&$('mode').value==='prepared'?(sol.translations_cell_px[i]||[0,0]):[0,0];}
function overlays(ctx,i,width,height,side){if(!$('marks').checked||$('mode').value==='scene')return;const raw=$('mode').value==='raw'&&side===0;const sx=raw?1:width/packet.cell_size[0],sy=raw?1:height/packet.cell_size[1];const shift=side===1?(sol.translations_cell_px[i]||[0,0]):alignment(i);
 for(const [name,m] of Object.entries(study.landmarks)){const obs=m.observations[i];if(!obs||!obs.visible)continue;const p=raw?obs.point:sourceToCell(i,obs.point);const x=(p[0]+(raw?0:shift[0]))*sx,y=(p[1]+(raw?0:shift[1]))*sy;ctx.strokeStyle=m.role==='fit'?'#f9c383':'#7ae0d7';ctx.fillStyle=ctx.strokeStyle;ctx.lineWidth=1;ctx.beginPath();ctx.arc(x,y,4,0,Math.PI*2);ctx.stroke();ctx.font='10px system-ui';ctx.fillText(name,x+6,y-4);
 if(!raw){ctx.globalAlpha=.3;ctx.beginPath();let began=false;for(let cel=0;cel<m.observations.length;cel++){const o=m.observations[cel];if(!o||!o.visible)continue;const a=sourceToCell(cel,o.point);if(began)ctx.lineTo(a[0]*sx,a[1]*sy);else{ctx.moveTo(a[0]*sx,a[1]*sy);began=true;}}ctx.stroke();ctx.globalAlpha=1;}}
 if(!raw)for(const r of Object.values(study.regions)){if(!r.points)continue;ctx.strokeStyle=r.mode==='stable'?'#83c1a7':'#b89bd5';ctx.setLineDash([4,3]);ctx.beginPath();r.points.forEach((p,j)=>ctx[j?'lineTo':'moveTo'](p[0]*sx,p[1]*sy));ctx.closePath();ctx.stroke();ctx.setLineDash([]);}}
let paintId=0;
async function paint(){const id=++paintId,mode=$('mode').value,cel=selectedCel(),c=clock();$('time').max=c.seconds;$('time').value=t;
 $('caption').textContent=`${t.toFixed(3)} s · cel ${cel} · ${c.fps} fps${mode==='scene'?` · scene ${((packet.scene.start+t)%packet.scene.loop_seconds).toFixed(3)} s`:''}`;
 let sources=mode==='scene'?packet.scene.frames.map(a=>a[Math.min(a.length-1,Math.floor(t*c.fps))]):[packet.images[mode==='raw'?'raw':'original'][cel],(draft?draftImages?.[cel]:packet.images.candidate[cel])];
 const loaded=await Promise.all(sources.map(src=>src?getImage(src):null));if(id!==paintId)return;
 for(let side=0;side<2;side++){const canvas=$(side?'after':'before'),im=loaded[side];canvas.width=im?.width||packet.display_size[0];canvas.height=im?.height||packet.display_size[1];const ctx=canvas.getContext('2d');ctx.fillStyle=$('ground').value;ctx.fillRect(0,0,canvas.width,canvas.height);if(im){const shift=side===0?alignment(cel):[0,0];ctx.drawImage(im,shift[0]*canvas.width/packet.cell_size[0],shift[1]*canvas.height/packet.cell_size[1]);}else{ctx.fillStyle='#aab8c6';ctx.font='12px system-ui';ctx.fillText('No ready candidate',10,24);}
 if($('onion').checked&&mode==='prepared'){const prior=(cel+packet.images.original.length-1)%packet.images.original.length;const src=side?((draft?draftImages?.[prior]:packet.images.candidate[prior])):packet.images.original[prior];if(src){const ghost=await getImage(src);if(id!==paintId)return;ctx.globalAlpha=.22;ctx.drawImage(ghost,0,0);ctx.globalAlpha=1;}}
 overlays(ctx,cel,canvas.width,canvas.height,side);}
 $('before-label').textContent=`Original · ${mode==='raw'?'raw source':'captured baseline'}${$('align').checked?' · inspection alignment only':''}`;
 $('after-label').textContent=draft?(mode==='scene'?'Saved candidate scene · draft not rendered in context':'In-memory draft · source compiler'):(packet.candidate?'Candidate · saved pack':'Candidate · no saved correction');
}
function status(extra=''){const u=sol.unresolved||[];$('status').textContent=extra||`${draft?'Draft':'Saved study'} · ${sol.ok?'constraints satisfied':`${u.length} unresolved constraints`} · ${packet.clock.driver}\n${u.slice(0,3).map(x=>x.reason+(x.landmark?' · '+x.landmark:'')).join('\n')}`;}
async function update(operations){playing=false;$('play').textContent='Play';const mine=++sequence;$('status').textContent='Recalculating draft from original inputs…';try{const response=await fetch('/api/draft',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({study,changes:{version:1,operations}})});const result=await response.json();if(mine!==sequence)return;if(!response.ok)throw Error(result.error||'Draft endpoint unavailable');study=result.study;sol=result.solution;draft=true;draftImages=result.images?.length?result.images:null;await Promise.all((draftImages||[]).map(getImage));status(result.raster_error?`Draft is not buildable: ${result.raster_error}`:'');await paint();}catch(error){if(mine===sequence)status(`Draft unavailable: ${error.message}. Use ambiance preview --motion for editing.`);}}
$('before').addEventListener('click',event=>{if(playing||$('mode').value==='scene'||$('align').checked||!$('landmark').value)return;const canvas=$('before'),rect=canvas.getBoundingClientRect(),cel=selectedCel(),id=`${$('mode').value==='raw'?'raw':'prepared'}-${cel}`,v=packet.views[id];const x=(event.clientX-rect.left)*canvas.width/rect.width,y=(event.clientY-rect.top)*canvas.height/rect.height,m=v.view_to_source;update([{op:'observe',name:$('landmark').value,cel,value:{point:[m[0]*x+m[2]*y+m[4],m[1]*x+m[3]*y+m[5]],visible:true,origin:'manual',state:'selected'}}]);});
$('landmark').onchange=()=>{$('tolerance').value=study.landmarks[$('landmark').value]?.tolerance_px??'';};
$('apply-tolerance').onclick=()=>{const name=$('landmark').value;if(name)update([{op:'landmark',name,value:{...study.landmarks[name],tolerance_px:Number($('tolerance').value)}}]);};
$('export').onclick=()=>{const blob=new Blob([JSON.stringify(study,null,2)+'\n'],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='motion-study.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
$('reset').onclick=()=>{sequence++;study=structuredClone(packet.study);sol=packet.solution;draftImages=null;draft=false;$('tolerance').value=study.landmarks[$('landmark').value]?.tolerance_px??'';status();paint();};
$('play').onclick=()=>{playing=!playing;$('play').textContent=playing?'Pause':'Play';};
$('time').oninput=()=>{t=Number($('time').value);playing=false;$('play').textContent='Play';paint();};
$('seam').onclick=()=>{t=$('mode').value==='scene'?Math.max(0,packet.scene.loop_seconds-packet.scene.start-.25):Math.max(0,clock().seconds-.25);playing=true;$('play').textContent='Pause';paint();};
$('finding').onchange=()=>{const f=packet.findings.find(r=>r.id===$('finding').value);if(f){$('mode').value='prepared';t=packet.clock.segments.find(r=>r.cell===f.cel)?.start||0;playing=false;$('play').textContent='Play';status(`${f.id} · cel ${f.cel}\n${f.next||f.reason||'Inspect this transition'}`);paint();}};
for(const id of ['mode','ground','onion','marks','align'])$(id).onchange=()=>{t=Math.min(t,clock().seconds-1e-6);paint();};
status();await paint();let lastFrame=-1;
function tick(now){const elapsed=Math.min(.1,(now-last)/1000);last=now;if(playing){t=(t+elapsed)%clock().seconds;const frame=Math.floor(t*clock().fps);if(frame!==lastFrame){lastFrame=frame;paint();}}requestAnimationFrame(tick);}requestAnimationFrame(tick);
