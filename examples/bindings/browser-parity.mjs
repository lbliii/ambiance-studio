import {compileScene,drawScene} from './modules/engine.mjs';
const make=(w,h)=>{const c=document.createElement('canvas');c.width=w;c.height=h;return c;};
const load=async url=>{const im=new Image();im.src=url;await im.decode();return im;};
const status=document.querySelector('#result');
try{
  const packet=await(await fetch('packet.json')).json();
  const {scene,catalog}=packet,compiled=compileScene(scene,catalog),images=new Map(await Promise.all(catalog.assets.map(async a=>[a.id,await load(a.file)])));
  const rows=[];
  for(const sample of packet.samples){
    const canvas=make(scene.canvas.width,scene.canvas.height),reference=make(canvas.width,canvas.height);
    drawScene(canvas,scene,catalog,images,sample.time,{sampler:compiled.sample,createCanvas:make});
    reference.getContext('2d').drawImage(await load(sample.file),0,0);
    const a=canvas.getContext('2d').getImageData(0,0,canvas.width,canvas.height).data,b=reference.getContext('2d').getImageData(0,0,canvas.width,canvas.height).data;
    const source=compiled.sample(sample.time).find(s=>s.id==='flame');
    const corners=[[source.rect[0],source.rect[1]],[source.rect[0]+source.rect[2],source.rect[1]],[source.rect[0],source.rect[1]+source.rect[3]],[source.rect[0]+source.rect[2],source.rect[1]+source.rect[3]]].map(([x,y])=>[source.matrix[0]*x+source.matrix[2]*y+source.matrix[4],source.matrix[1]*x+source.matrix[3]*y+source.matrix[5]]);
    const box=[Math.min(...corners.map(p=>p[0]))-2,Math.min(...corners.map(p=>p[1]))-2,Math.max(...corners.map(p=>p[0]))+2,Math.max(...corners.map(p=>p[1]))+2];
    let total=0,max=0,changed=0,outside=0;for(let i=0;i<a.length;i++){const d=Math.abs(a[i]-b[i]);total+=d;max=Math.max(max,d);if(d){changed++;const pixel=Math.floor(i/4),x=pixel%canvas.width,y=Math.floor(pixel/canvas.width);if(x<box[0]||y<box[1]||x>box[2]||y>box[3])outside++;}}
    const mean=total/a.length;
    // Rasterizers can differ at transformed cel edges. Interior source/receiver,
    // mask and fixed-occluder pixels must still match exactly.
    const points=[[60,55],[29,55],[78,70],[60,88]];
    const exact=points.every(([x,y])=>{const i=(y*canvas.width+x)*4;return [0,1,2,3].every(k=>a[i+k]===b[i+k]);});
    rows.push({time:sample.time,mean_channel_error:mean,max_channel_error:max,changed_channels:changed,interior_pixels_exact:exact,changed_channels_outside_source_edges:outside,ok:mean<=.75&&exact&&outside===0});
    const f=document.createElement('figure'),label=document.createElement('figcaption');label.textContent=`${sample.time}s · Browser / CLI`;f.append(label,canvas,reference);document.querySelector('main').append(f);
  }
  const zero=compiled.sample(0),join=compiled.sample(scene.canvas.loop_seconds),seeks=compiled.sample(.375);compiled.sample(2.75);
  const result={ok:rows.every(r=>r.ok)&&JSON.stringify(zero)===JSON.stringify(join)&&JSON.stringify(seeks)===JSON.stringify(compiled.sample(.375)),samples:rows,state_join_exact:JSON.stringify(zero)===JSON.stringify(join),arbitrary_seek_exact:JSON.stringify(seeks)===JSON.stringify(compiled.sample(.375)),scene_sha256:packet.scene_sha256,cli_reports:packet.cli_reports,limits:['Browser versus CLI fixture raster comparison; no artistic or encoded-movie approval.']};
  status.textContent=JSON.stringify(result,null,2);
}catch(e){status.textContent=JSON.stringify({ok:false,error:e.message});}
