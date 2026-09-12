const $=id=>document.getElementById(id),clone=structuredClone;
export function sourcePoint(event,rect,width,height){return [Math.max(0,Math.min(width-1,(event.clientX-rect.left)/rect.width*width)),Math.max(0,Math.min(height-1,(event.clientY-rect.top)/rect.height*height))];}

async function boot(){
  const response=await fetch('/api/state');if(!response.ok)throw Error('Unable to load region');
  const saved=await response.json();let state=saved,recipe=clone(saved.recipe),history=[],points=[],drag=null,busy=false,sourceImage=new Image();
  sourceImage.src=state.images.source;await sourceImage.decode();
  const W=recipe.source.width,H=recipe.source.height,canvas=$('source'),ctx=canvas.getContext('2d');canvas.width=W;canvas.height=H;
  function message(text,error=false){$('status').textContent=text;$('status').className=error?'error':'';}
  function selected(){return Number($('outline').value)||0;}
  function draw(){
    ctx.clearRect(0,0,W,H);ctx.drawImage(sourceImage,0,0,W,H);ctx.lineWidth=Math.max(1,W/600);
    if($('overlay').checked){
      for(const [i,poly] of recipe.visible_mask.polygons.entries()){
        ctx.beginPath();poly.points.forEach(([x,y],j)=>j?ctx.lineTo(x,y):ctx.moveTo(x,y));ctx.closePath();ctx.fillStyle=poly.operation==='add'?'#68dfce44':'#ffa67377';ctx.strokeStyle=poly.operation==='add'?'#83f0df':'#ffc395';ctx.fill();ctx.stroke();
        if(i===selected()&&$('tool').value==='vertex')for(const [x,y] of poly.points){ctx.fillStyle='#fff';ctx.fillRect(x-W/200,y-W/200,W/100,W/100);}
      }
      const f=state.report.frame_xyxy;if(f){ctx.strokeStyle='#f4d68b';ctx.setLineDash([W/80,W/150]);ctx.strokeRect(f[0],f[1],f[2]-f[0],f[3]-f[1]);ctx.setLineDash([]);}
    }
    if(points.length){ctx.strokeStyle='#fff';ctx.beginPath();points.forEach(([x,y],i)=>i?ctx.lineTo(x,y):ctx.moveTo(x,y));ctx.stroke();for(const [x,y] of points){ctx.fillStyle='#fff';ctx.fillRect(x-2,y-2,4,4);}}
    if(drag?.start&&$('tool').value==='rectangle'){const p=drag.end??drag.start;ctx.strokeStyle='#fff';ctx.strokeRect(drag.start[0],drag.start[1],p[0]-drag.start[0],p[1]-drag.start[1]);}
    const zoom=Number($('zoom').value)/100;canvas.style.width=Math.min(W,$('viewport').clientWidth)*zoom+'px';canvas.style.height='auto';$('zoom-label').textContent=$('zoom').value+'%';
  }
  function sync(){
    $('subtitle').textContent=recipe.title+' · '+(saved.kind==='return'?'Returned artwork':'Saved region draft');$('dimensions').textContent=W+' × '+H+' source pixels';
    const old=selected();$('outline').replaceChildren(...recipe.visible_mask.polygons.map((p,i)=>{const o=document.createElement('option');o.value=i;o.textContent=(i+1)+' · '+p.operation+' · '+p.points.length+' vertices';return o;}));$('outline').value=Math.min(old,recipe.visible_mask.polygons.length-1);
    $('aspect').value=typeof recipe.frame.aspect==='string'?recipe.frame.aspect:'custom';
    if(Array.isArray(recipe.frame.aspect)){ $('ratio-w').value=recipe.frame.aspect[0];$('ratio-h').value=recipe.frame.aspect[1];}
    $('padding').value=recipe.frame.padding[0];$('bleed').value=recipe.paint_coverage.bleed[0];$('quality').value=recipe.sizing.quality_multiplier;
    for(const [prefix,key] of [['display','display_size'],['export','export_size']])for(const [i,suffix] of ['w','h'].entries())$(prefix+'-'+suffix).value=recipe.sizing[key]?.[i]??'';
    $('display-w').disabled=$('display-h').disabled=recipe.sizing.mode==='scene';$('binding').textContent=recipe.sizing.mode==='scene'?'Measured across '+recipe.context.views.join(' and '):'Manual display-size assumption';
    $('brief').value=recipe.intent.brief;$('preserve').value=recipe.intent.preserve;$('recipe').value=JSON.stringify(recipe,null,2);
    for(const [id,name] of [['reference','reference'],['guide','guide'],['mask','visible-export'],['context','context']]){if(state.images[name])$(id).src=state.images[name];else $(id).removeAttribute('src');}
    $('view-previews').replaceChildren();
    for(const view of state.report.measurement?.views??[]){
      const figure=document.createElement('figure'),caption=document.createElement('figcaption'),img=document.createElement('img');
      caption.textContent=`${view.id} · ${view.output.width} × ${view.output.height} · source plane at demand peak`;
      img.src=state.images['view-'+view.id];img.alt=caption.textContent;figure.append(caption,img);$('view-previews').append(figure);
    }
    $('metrics').replaceChildren();const r=state.report;
    for(const [title,value] of [['Requested image',r.export_size?.join(' × ')??'Draw a region'],['Visible source region',r.bounds?`${r.bounds[2]-r.bounds[0]} × ${r.bounds[3]-r.bounds[1]}`:'—'],['Detail density',r.effective_density?`${r.effective_density.toFixed(2)} px / source px`:'—'],['Demand',r.meets_demand?'Meets stated target':'Unresolved / study']]){const div=document.createElement('div');div.className='metric';const strong=document.createElement('strong'),label=document.createElement('span');strong.textContent=value;label.textContent=title;div.append(strong,label);$('metrics').append(div);}
    $('issues').replaceChildren(...[...(r.issues??[]),...(r.assumptions??[]),...(r.provider_compatibility==='unchecked'?['Generation provider dimensions have not been checked.']:[])].map(text=>{const li=document.createElement('li');li.textContent=text;return li;}));
    $('undo').disabled=!history.length;draw();
  }
  async function commit(candidate,mode='edit'){
    if(busy)return;busy=true;$('apply').disabled=true;message('Calculating shape, framing and size…');
    try{const response=await fetch('/api/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(candidate)}),reply=await response.json();if(!response.ok||!reply.ok)throw Error(reply.error??'Preview rejected');if(mode==='undo')history.pop();else if(mode==='reset')history=[];else history.push(clone(recipe));recipe=reply.data.recipe;state=reply.data;points=[];sync();message('Draft updated. Export its recipe to build a fresh packet.');document.documentElement.dataset.regionRevision=String(Number(document.documentElement.dataset.regionRevision??0)+1);}
    catch(error){sync();message(error.message+' The last valid preview is retained.',true);}
    finally{busy=false;$('apply').disabled=false;}
  }
  function mutate(fn){const candidate=clone(recipe);fn(candidate);return commit(candidate);}
  canvas.onpointerdown=e=>{
    if(busy)return;canvas.setPointerCapture(e.pointerId);const p=sourcePoint(e,canvas.getBoundingClientRect(),W,H),tool=$('tool').value;
    if(tool==='pan'){drag={client:[e.clientX,e.clientY],scroll:[$('viewport').scrollLeft,$('viewport').scrollTop]};return;}
    if(tool==='rectangle'){drag={start:p,end:p};return;}
    if(tool==='vertex'){const poly=recipe.visible_mask.polygons[selected()];if(!poly)return;const ds=poly.points.map(q=>Math.hypot(q[0]-p[0],q[1]-p[1])),n=ds.indexOf(Math.min(...ds));if(ds[n]<Math.max(W/canvas.getBoundingClientRect().width*16,5))drag={vertex:n,poly:selected(),original:clone(recipe)};return;}
    points.push(p);draw();
  };
  canvas.onpointermove=e=>{if(!drag)return;const p=sourcePoint(e,canvas.getBoundingClientRect(),W,H);if(drag.client){$('viewport').scrollLeft=drag.scroll[0]-(e.clientX-drag.client[0]);$('viewport').scrollTop=drag.scroll[1]-(e.clientY-drag.client[1]);return;}if(drag.vertex!==undefined){recipe.visible_mask.polygons[drag.poly].points[drag.vertex]=p;}else drag.end=p;draw();};
  canvas.onpointerup=()=>{if(!drag)return;const d=drag;drag=null;if(d.vertex!==undefined){const candidate=clone(recipe);recipe=d.original;commit(candidate);}else if(d.start){const [l,r]=[d.start[0],d.end[0]].sort((a,b)=>a-b),[t,b]=[d.start[1],d.end[1]].sort((a,b)=>a-b);if(r-l>=1&&b-t>=1)mutate(c=>c.visible_mask.polygons.push({operation:$('operation').value,points:[[l,t],[r,t],[r,b],[l,b]]}));}draw();};
  canvas.onpointercancel=()=>{if(drag?.original)recipe=drag.original;drag=null;draw();};
  $('close').onclick=()=>{if(points.length>=3)mutate(c=>c.visible_mask.polygons.push({operation:$('operation').value,points:clone(points)}));};
  $('cancel').onclick=()=>{points=[];draw();};$('delete').onclick=()=>mutate(c=>c.visible_mask.polygons.splice(selected(),1));
  for(const id of ['zoom','overlay','tool','outline'])$(id).oninput=draw;
  $('undo').onclick=()=>{if(history.length)commit(clone(history.at(-1)),'undo');};$('reset').onclick=()=>commit(clone(saved.recipe),'reset');
  $('apply').onclick=()=>{try{const c=clone(recipe),num=id=>{const v=$(id).valueAsNumber;if(!Number.isFinite(v))throw Error('Supply a number for '+id);return v;};c.frame.aspect=$('aspect').value==='custom'?[num('ratio-w'),num('ratio-h')]:$('aspect').value;if(num('padding')!==recipe.frame.padding[0])c.frame.padding=Array(4).fill(num('padding'));if(JSON.stringify(c.frame.aspect)!==JSON.stringify(recipe.frame.aspect)||JSON.stringify(c.frame.padding)!==JSON.stringify(recipe.frame.padding))c.frame.rect_xyxy=null;if(num('bleed')!==recipe.paint_coverage.bleed[0])c.paint_coverage.bleed=Array(4).fill(num('bleed'));c.sizing.quality_multiplier=num('quality');for(const [prefix,key] of [['display','display_size'],['export','export_size']])c.sizing[key]=$(`${prefix}-w`).value||$(`${prefix}-h`).value?[num(prefix+'-w'),num(prefix+'-h')]:null;c.intent.brief=$('brief').value;c.intent.preserve=$('preserve').value;commit(c);}catch(error){message(error.message,true);}};
  $('apply-json').onclick=()=>{try{commit(JSON.parse($('recipe').value));}catch(error){message(error.message,true);}};
  $('export').onclick=()=>{if(busy)return;const url=URL.createObjectURL(new Blob([JSON.stringify(recipe,null,2)+'\n'],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='region-recipe.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);message('Applied recipe exported. Unapplied fields and unfinished points are not included.');};
  if(saved.kind==='return'){$('returned').hidden=false;for(const [id,name] of [['paint','paint'],['composite','composite'],['missing','missing-paint']])$(id).src=saved.images[name];}
  sync();message('Captured region ready. Trace an opening or adjust its frame.');document.documentElement.dataset.regionReady='true';window.addEventListener('resize',draw);
}
if(typeof document!=='undefined')boot().catch(e=>{$('status').textContent=e.message;$('status').className='error';});
