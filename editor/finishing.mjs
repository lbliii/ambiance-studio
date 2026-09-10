// Shared, deterministic painted-image finishing. RGB computations use linear
// sRGB; matte samples are data. This is authored 2D compositing, not recovered 3D.
const object=v=>v&&typeof v==='object'&&!Array.isArray(v);
const finite=v=>typeof v==='number'&&Number.isFinite(v);
const clamp=(v,a=0,b=1)=>Math.min(b,Math.max(a,v));
const fields=(v,keys,label)=>{if(!object(v)||Object.keys(v).some(k=>!keys.includes(k)))throw Error(`Unknown or invalid ${label} fields`);};
const range=(v,a,b,label)=>{if(!finite(v)||v<a||v>b)throw Error(`Invalid ${label}; expected ${a}..${b}`);};
const vec=(v,n,label,a=-100,b=100)=>{if(!Array.isArray(v)||v.length!==n)throw Error(`Invalid ${label}`);v.forEach(x=>range(x,a,b,label));};
const rgb=v=>{if(typeof v!=='string'||!/^#[0-9a-f]{6}$/i.test(v))throw Error('Finishing colors must be #rrggbb');return [1,3,5].map(i=>decode(parseInt(v.slice(i,i+2),16)/255));};
export const decode=v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4;
export const encode=v=>v<=.0031308?12.92*v:1.055*v**(1/2.4)-.055;
const LUT=Float32Array.from({length:256},(_,i)=>decode(i/255));
const xy=(m,x,y)=>[m[0]*x+m[2]*y+m[4],m[1]*x+m[3]*y+m[5]];
const inv=m=>{const d=m[0]*m[3]-m[1]*m[2];return [m[3]/d,-m[1]/d,-m[2]/d,m[0]/d,(m[2]*m[5]-m[3]*m[4])/d,(m[1]*m[4]-m[0]*m[5])/d];};
const mul=(a,b)=>[a[0]*b[0]+a[2]*b[1],a[1]*b[0]+a[3]*b[1],a[0]*b[2]+a[2]*b[3],a[1]*b[2]+a[3]*b[3],a[0]*b[4]+a[2]*b[5]+a[4],a[1]*b[4]+a[3]*b[5]+a[5]];
const config=s=>s?.finishing??(s?.version===1&&s?.working_space?s:null);
export function finishingAssetIds(scene){
  const f=config(scene);if(!f)return [];
  const ids=new Set(Object.keys(f.assets||{}));
  for(const g of [f.grade,...Object.values(f.assets||{}),...Object.values(f.groups||{}),...Object.values(f.layers||{})])if(g?.mask_asset)ids.add(g.mask_asset);
  for(const e of [...(f.lights||[]),...(f.shadows||[]),...(f.reflections||[])])if(e.mask_asset)ids.add(e.mask_asset);
  return [...ids];
}
export function validateFinishing(scene,catalog){
  if(scene.finishing===undefined)return true;
  const f=scene.finishing,T=scene.canvas.loop_seconds;
  fields(f,['version','working_space','output_space','assets','groups','layers','grade','lights','signals','shadows','reflections'],'finishing');
  if(f.version!==1||f.working_space!=='linear-srgb'||f.output_space!=='srgb')throw Error('Finishing requires version 1, linear-srgb working space and srgb output');
  rgb(scene.canvas.background);
  const assets=new Map(catalog.assets.map(a=>[a.id,a])),layers=new Map(scene.layers.map(l=>[l.id,l]));
  const groups=new Set(scene.groups.map(g=>g.id));
  const layer=id=>{if(!layers.has(id))throw Error(`Unknown finishing layer: ${id}`);};
  const mask=id=>{if(id===undefined)return;const a=assets.get(id);if(!a||(a.atlas&&a.atlas.frame_count!==1))throw Error(`Finishing mask must be a catalog image or single-cel atlas: ${id}`);};
  function grade(g){
    fields(g,['exposure','contrast','saturation','balance','curve','mask_asset'],'grade');
    for(const [k,a,b] of [['exposure',-8,8],['contrast',0,4],['saturation',0,4]])if(g[k]!==undefined)range(g[k],a,b,k);
    if(g.balance!==undefined)vec(g.balance,3,'balance',0,8);
    if(g.curve!==undefined){if(!Array.isArray(g.curve)||g.curve.length<2||g.curve.length>32)throw Error('Curve requires 2..32 knots');let last=-1;for(const p of g.curve){vec(p,2,'curve',0,1);if(p[0]<=last)throw Error('Curve x must strictly increase');last=p[0];}if(g.curve[0][0]!==0||g.curve.at(-1)[0]!==1)throw Error('Curve must span 0..1');}
    mask(g.mask_asset);
  }
  for(const [name,known] of [['assets',assets],['groups',groups],['layers',layers]])if(f[name]!==undefined){if(!object(f[name]))throw Error(`Invalid ${name} grades`);for(const [id,g] of Object.entries(f[name])){if(!known.has(id))throw Error(`Unknown ${name} grade target: ${id}`);grade(g);}}
  if(f.grade!==undefined)grade(f.grade);
  const signals=new Set();
  for(const name of ['signals','lights','shadows','reflections'])if(f[name]!==undefined&&!Array.isArray(f[name]))throw Error(`${name} must be an array`);
  for(const s of f.signals||[]){
    fields(s,['id','layer','values','keys','interpolation'],'signal');
    if(typeof s.id!=='string'||!s.id||signals.has(s.id))throw Error('Invalid/duplicate signal');signals.add(s.id);
    if(s.layer!==undefined){layer(s.layer);if(s.keys!==undefined||s.interpolation!==undefined||!Array.isArray(s.values)||s.values.length!==(assets.get(layers.get(s.layer).asset).atlas?.frame_count||1))throw Error('Cel signal requires one value per source cel');s.values.forEach(v=>range(v,0,8,'signal value'));}
    else{if(s.values!==undefined||!['linear','smoothstep','hold'].includes(s.interpolation)||!Array.isArray(s.keys)||s.keys.length<2)throw Error('Signal requires cel source or closed keys');let last=-1;for(const key of s.keys){vec(key,2,'signal key',0,Math.max(T,8));if(key[0]<=last||key[0]>T||key[1]>8)throw Error('Invalid signal keys');last=key[0];}if(s.keys[0][0]!==0||last!==T||s.keys[0][1]!==s.keys.at(-1)[1])throw Error('Signal keys must close the picture loop');}
  }
  const signal=s=>{if(s!==undefined&&!signals.has(s))throw Error(`Unknown signal: ${s}`);};
  const seen=new Set();const id=e=>{if(typeof e.id!=='string'||!e.id||seen.has(e.id))throw Error('Invalid/duplicate finishing effect ID');seen.add(e.id);};
  for(const l of f.lights||[]){
    fields(l,['id','receivers','rect','anchor_layer','mask_asset','color','gain','feather','signal'],'light');id(l);
    if(!Array.isArray(l.receivers)||!l.receivers.length||new Set(l.receivers).size!==l.receivers.length)throw Error('Light requires unique receivers');l.receivers.forEach(layer);
    vec(l.rect,4,'light rectangle');if(l.rect[2]<=0||l.rect[3]<=0)throw Error('Light rectangle must have positive extent');
    if(l.anchor_layer!==undefined)layer(l.anchor_layer);mask(l.mask_asset);rgb(l.color);range(l.gain,-1,8,'light gain');range(l.feather??.2,0,.5,'light feather');signal(l.signal);
  }
  for(const kind of ['shadows','reflections'])for(const e of f[kind]||[]){
    fields(e,['id','caster','receiver','offset','scale','opacity','color','softness','mask_asset','signal','elevation'],kind);id(e);layer(e.caster);layer(e.receiver);
    if(e.caster===e.receiver)throw Error('Effect caster and receiver must differ');
    if(scene.layers.findIndex(l=>l.id===e.receiver)>=scene.layers.findIndex(l=>l.id===e.caster))throw Error('Receiving surface must be painted before caster');
    vec(e.offset??[0,0],2,'effect offset');vec(e.scale??[1,.25],2,'effect scale',.001,8);range(e.opacity??.4,0,1,'effect opacity');range(e.softness??0,0,.1,'effect softness');
    if(kind==='shadows')rgb(e.color??'#000000');else if(e.color!==undefined)throw Error('Reflection preserves caster color; color is shadow-only');
    mask(e.mask_asset);signal(e.signal);
    if(e.elevation){const v=e.elevation;fields(v,['layer','rest_y','range','offset','scale','opacity','softness'],'elevation');layer(v.layer);range(v.rest_y,-10,10,'rest_y');range(v.range,.000001,10,'elevation range');if(v.offset!==undefined)vec(v.offset,2,'elevated offset');if(v.scale!==undefined)vec(v.scale,2,'elevated scale',.001,8);if(v.opacity!==undefined)range(v.opacity,0,1,'elevated opacity');if(v.softness!==undefined)range(v.softness,0,.1,'elevated softness');}
  }
  return true;
}
function signalValues(f,states,time,T){
  const t=((time%T)+T)%T,out={};
  for(const s of f.signals||[]){if(s.layer!==undefined){const l=states.get(s.layer);out[s.id]=l.visible?s.values[l.cell]*l.opacity:0;continue;}
    let i=0;while(i<s.keys.length-2&&t>=s.keys[i+1][0])i++;const [a,x]=s.keys[i],[b,y]=s.keys[i+1];let u=(t-a)/(b-a);if(s.interpolation==='hold')u=0;else if(s.interpolation==='smoothstep')u=u*u*(3-2*u);out[s.id]=x+(y-x)*u;
  }return out;
}
export function finishingDiagnostics(scene,catalog,time=0,states=[]){
  validateFinishing(scene,catalog);const f=scene.finishing;
  if(!f)return {ok:true,enabled:false,pipeline:'legacy-canvas',warnings:[]};
  const warnings=[];
  for(const l of scene.layers)if(l.attach&&(f.groups?.[scene.layers.find(p=>p.id===l.attach.layer)?.group]))warnings.push({layer:l.id,code:'GROUP_GRADE_EXPLICIT',message:'Group grades apply to direct group members only; attached children need explicit instance grades.'});
  for(const e of f.shadows||[])if(!scene.layers.find(l=>l.id===e.caster)?.sockets?.ground&&!catalog.assets.find(a=>a.id===scene.layers.find(l=>l.id===e.caster)?.asset)?.sockets?.ground)warnings.push({effect:e.id,code:'GROUND_ESTIMATED',message:'No ground socket; projection uses full-cell bottom center. Author a ground socket for padded sprites.'});
  return {ok:true,enabled:true,pipeline:'linear-srgb / premultiplied compositing / srgb output',mask_assets:finishingAssetIds(scene),grade_order:['asset','direct group','instance','lights','composite','scene grade'],signals:states.length?signalValues(f,new Map(states.map(s=>[s.id,s])),time,scene.canvas.loop_seconds):null,lights:(f.lights||[]).length,shadows:(f.shadows||[]).length,reflections:(f.reflections||[]).length,warnings,limits:['Authored 2D projections; no recovered geometry or physically based material lighting.','Inputs must be sRGB artwork; masks are luminance × alpha data. No automatic ICC/profile conversion.','Group grades are direct membership, independent of transform parenting.','Clipping diagnostics require raster inspection; configuration validation is not artistic approval.']};
}
function curve(v,knots){if(!knots)return v;v=clamp(v);let i=0;while(i<knots.length-2&&v>knots[i+1][0])i++;const [a,x]=knots[i],[b,y]=knots[i+1];return x+(y-x)*(v-a)/(b-a);}
export function gradeRGB(rgb,g,weight=1){
  if(!g||!weight)return rgb;
  let c=rgb.map((v,i)=>Math.max(0,(v*2**(g.exposure??0)*(g.balance?.[i]??1)-.18)*(g.contrast??1)+.18));
  const y=.2126*c[0]+.7152*c[1]+.0722*c[2];c=c.map(v=>curve(Math.max(0,y+(v-y)*(g.saturation??1)),g.curve));
  return rgb.map((v,i)=>v+(c[i]-v)*weight);
}
const imageCache=new WeakMap();
const cellCache=new WeakMap();
function isolatedCell(image,source,make){let cells=cellCache.get(image);if(!cells){cells=new Map();cellCache.set(image,cells);}const key=source.join(',');let c=cells.get(key);if(!c){c=make(source[2],source[3]);c.getContext('2d').drawImage(image,...source,0,0,c.width,c.height);cells.set(key,c);}return c;}
function cachedImage(image,make){let value=imageCache.get(image);if(value)return value;const c=make(image.width||image.naturalWidth,image.height||image.naturalHeight),ctx=c.getContext('2d');ctx.drawImage(image,0,0);value={data:ctx.getImageData(0,0,c.width,c.height).data,width:c.width,height:c.height};imageCache.set(image,value);return value;}
// Bilinear mask lookup, outside support is zero. Luminance here deliberately
// reads stored data values rather than applying a color transfer function.
function maskValue(id,u,v,images,make,catalog){
  if(!id)return 1;if(u<0||v<0||u>1||v>1)return 0;
  const image=images.get(id);if(!image)throw Error(`Missing finishing mask image: ${id}`);
  const m=cachedImage(image,make),a=catalog.assets.find(a=>a.id===id),w=a.atlas?.cell_width||m.width,h=a.atlas?.cell_height||m.height;
  const x=clamp(u*w-.5,0,w-1),y=clamp(v*h-.5,0,h-1),ix=Math.floor(x),iy=Math.floor(y),fx=x-ix,fy=y-iy;
  const read=(xx,yy)=>{const i=(Math.min(h-1,yy)*m.width+Math.min(w-1,xx))*4;return (.2126*m.data[i]+.7152*m.data[i+1]+.0722*m.data[i+2])*m.data[i+3]/65025;};
  return read(ix,iy)*(1-fx)*(1-fy)+read(ix+1,iy)*fx*(1-fy)+read(ix,iy+1)*(1-fx)*fy+read(ix+1,iy+1)*fx*fy;
}
function feather(u,v,f){if(u<0||v<0||u>1||v>1)return 0;if(!f)return 1;const x=clamp(Math.min(u,v,1-u,1-v)/f);return x*x*(3-2*x);}
function bounding(m,r,W,H,pad=0){const p=[[r[0],r[1]],[r[0]+r[2],r[1]],[r[0],r[1]+r[3]],[r[0]+r[2],r[1]+r[3]]].map(p=>xy(m,...p));const x=clamp(Math.floor(Math.min(...p.map(p=>p[0]))-pad),0,W),y=clamp(Math.floor(Math.min(...p.map(p=>p[1]))-pad),0,H);return [x,y,Math.max(0,clamp(Math.ceil(Math.max(...p.map(p=>p[0]))+pad),0,W)-x),Math.max(0,clamp(Math.ceil(Math.max(...p.map(p=>p[1]))+pad),0,H)-y)];}
function blurAlpha(data,w,h,r){
  r=Math.ceil(r);if(!r)return;const a=new Float32Array(w*h),b=new Float32Array(w*h);for(let i=0;i<a.length;i++)a[i]=data[i*4+3];
  for(let y=0;y<h;y++){let sum=0;for(let x=-r;x<=r;x++)if(x>=0&&x<w)sum+=a[y*w+x];for(let x=0;x<w;x++){b[y*w+x]=sum/(2*r+1);if(x-r>=0)sum-=a[y*w+x-r];if(x+r+1<w)sum+=a[y*w+x+r+1];}}
  for(let x=0;x<w;x++){let sum=0;for(let y=-r;y<=r;y++)if(y>=0&&y<h)sum+=b[y*w+x];for(let y=0;y<h;y++){data[(y*w+x)*4+3]=sum/(2*r+1);if(y-r>=0)sum-=b[(y-r)*w+x];if(y+r+1<h)sum+=b[(y+r+1)*w+x];}}
}
function blurLinearRGBA(data,w,h,r){
  r=Math.ceil(r);if(!r)return;const input=new Float32Array(w*h*4),temp=new Float32Array(input.length),out=new Float32Array(input.length);
  for(let i=0;i<input.length;i+=4){const a=data[i+3]/255;for(let k=0;k<3;k++)input[i+k]=LUT[data[i+k]]*a;input[i+3]=a;}
  for(let k=0;k<4;k++){
    for(let y=0;y<h;y++){let sum=0;for(let x=0;x<=r&&x<w;x++)sum+=input[(y*w+x)*4+k];for(let x=0;x<w;x++){temp[(y*w+x)*4+k]=sum/(2*r+1);if(x-r>=0)sum-=input[(y*w+x-r)*4+k];if(x+r+1<w)sum+=input[(y*w+x+r+1)*4+k];}}
    for(let x=0;x<w;x++){let sum=0;for(let y=0;y<=r&&y<h;y++)sum+=temp[(y*w+x)*4+k];for(let y=0;y<h;y++){out[(y*w+x)*4+k]=sum/(2*r+1);if(y-r>=0)sum-=temp[((y-r)*w+x)*4+k];if(y+r+1<h)sum+=temp[((y+r+1)*w+x)*4+k];}}
  }
  for(let i=0;i<data.length;i+=4){const a=out[i+3];for(let k=0;k<3;k++)data[i+k]=a>1e-8?clamp(encode(Math.max(0,out[i+k]/a)))*255:0;data[i+3]=a*255;}
}
export function drawFinished(canvas,scene,catalog,images,time,states,options={}){
  const W=scene.canvas.width,H=scene.canvas.height,f=scene.finishing,pass=options.pass??'beauty';
  if(!['beauty','ungraded','lights','shadows','reflections'].includes(pass))throw Error(`Unknown finishing pass: ${pass}`);
  const make=options.createCanvas??((w,h)=>{if(canvas.ownerDocument){const c=canvas.ownerDocument.createElement('canvas');c.width=w;c.height=h;return c;}return new canvas.constructor(w,h);});
  const ctx=canvas.getContext('2d'),scratch=make(W,H),sc=scratch.getContext('2d');
  const buffer=new Float32Array(W*H*3),baseColor=rgb(scene.canvas.background),debug=!['beauty','ungraded'].includes(pass);
  for(let i=0;i<buffer.length;i+=3){buffer[i]=debug?0:baseColor[0];buffer[i+1]=debug?0:baseColor[1];buffer[i+2]=debug?0:baseColor[2];}
  const byId=new Map(states.map(s=>[s.id,s])),layers=new Map(scene.layers.map(l=>[l.id,l])),signals=signalValues(f,byId,time,scene.canvas.loop_seconds);
  const intensity=e=>e.signal?signals[e.signal]:1;
  const zone=(f.lights||[]).map(l=>({...l,colorRGB:rgb(l.color),inverse:l.anchor_layer?inv(byId.get(l.anchor_layer).matrix):null}));
  let clipped=0;
  const renderLayer=s=>{sc.setTransform(1,0,0,1,0,0);sc.clearRect(0,0,W,H);sc.imageSmoothingEnabled=true;sc.imageSmoothingQuality='high';sc.globalAlpha=1;sc.globalCompositeOperation='source-over';sc.setTransform(...s.matrix);const im=images.get(s.asset);if(!im)throw Error(`Missing image: ${s.asset}`);
    // Isolate source cells so transformed filtering cannot see adjacent poses.
    sc.drawImage(isolatedCell(im,s.source,make),...s.rect);};
  const blit=(bounds,pixels,opacity,blend,transform)=>{const [bx,by,w,h]=bounds;for(let y=0;y<h;y++)for(let x=0;x<w;x++){const i=(y*w+x)*4,a=clamp(pixels[i+3]/255*opacity);if(!a)continue;const j=((by+y)*W+bx+x)*3;let c=[LUT[pixels[i]],LUT[pixels[i+1]],LUT[pixels[i+2]]];if(transform)c=transform(c,bx+x+.5,by+y+.5);for(let k=0;k<3;k++){let v=c[k],d=buffer[j+k];if(blend==='multiply')v*=d;else if(blend==='screen')v=1-(1-clamp(v))*(1-clamp(d));buffer[j+k]=d*(1-a)+v*a;}}};
  const appearance=new Map();
  for(const s of states){const l=layers.get(s.id),inverse=inv(s.matrix),grades=[f.assets?.[s.asset],f.groups?.[l.group],f.layers?.[s.id]].filter(Boolean),lights=zone.filter(z=>z.receivers.includes(s.id));
    appearance.set(s.id,(c,x,y,lightOnly=false)=>{
      if(grades.length){const p=xy(inverse,x,y),u=(p[0]-s.rect[0])/s.rect[2],v=(p[1]-s.rect[1])/s.rect[3];for(const g of grades)c=gradeRGB(c,g,maskValue(g.mask_asset,u,v,images,make,catalog));}
      const base=lightOnly?[...c]:null;
      for(const z of lights){let q=[x/W,y/H];if(z.inverse){const a=byId.get(z.anchor_layer),p=xy(z.inverse,x,y);q=[(p[0]-a.rect[0])/a.rect[2],(p[1]-a.rect[1])/a.rect[3]];}const u=(q[0]-z.rect[0])/z.rect[2],v=(q[1]-z.rect[1])/z.rect[3],a=feather(u,v,z.feather??.2)*maskValue(z.mask_asset,u,v,images,make,catalog)*z.gain*intensity(z);c=c.map((n,i)=>Math.max(0,n*(1+a*z.colorRGB[i])));}
      return lightOnly?c.map((n,i)=>Math.abs(n-base[i])):c;
    });
  }
  function effect(e,kind,receiverPixels,receiverBounds){
    const caster=byId.get(e.caster),receiver=byId.get(e.receiver);if(!caster.visible||caster.opacity<=0||!receiver.visible||!intensity(e))return;
    const socket=caster.sockets.ground??xy(caster.matrix,caster.rect[0]+caster.rect[2]/2,caster.rect[1]+caster.rect[3]);
    const ri=inv(receiver.matrix),ground=xy(ri,...socket);
    let lift=0,offset=e.offset??[0,0],scale=e.scale??[1,.25],opacity=e.opacity??.4,softness=e.softness??0;
    if(e.elevation){const v=e.elevation,driver=byId.get(v.layer);lift=clamp((v.rest_y-driver.matrix[5]/H)/v.range);const mix=(a,b)=>a+(b-a)*lift;offset=offset.map((n,i)=>mix(n,v.offset?.[i]??n));scale=scale.map((n,i)=>mix(n,v.scale?.[i]??n));opacity=mix(opacity,v.opacity??opacity);softness=mix(softness,v.softness??softness);
      // Remove the driver's displacement from the contact location, retaining
      // the receiving plane's transform and caster horizontal route.
      const delta=xy(ri,0,(v.rest_y-driver.matrix[5]/H)*H),origin=xy(ri,0,0);ground[0]+=delta[0]-origin[0];ground[1]+=delta[1]-origin[1];
    }
    const relative=mul(ri,caster.matrix),sy=scale[1]*(kind==='reflections'?-1:1);
    const matrix=mul(receiver.matrix,[relative[0]*scale[0],relative[1]*sy,relative[2]*scale[0],relative[3]*sy,ground[0]+offset[0]*W,ground[1]+offset[1]*H]);
    const localGround=xy(inv(caster.matrix),...socket);
    const rect=[caster.rect[0]-localGround[0],caster.rect[1]-localGround[1],caster.rect[2],caster.rect[3]],pad=softness*H*2,bounds=bounding(matrix,rect,W,H,pad);if(!bounds[2]||!bounds[3])return;
    sc.setTransform(1,0,0,1,0,0);sc.clearRect(0,0,W,H);sc.setTransform(...matrix);sc.globalAlpha=1;
    const image=images.get(e.mask_asset??caster.asset),asset=catalog.assets.find(a=>a.id===(e.mask_asset??caster.asset));
    const source=e.mask_asset?[0,0,asset.atlas?.cell_width||asset.width,asset.atlas?.cell_height||asset.height]:caster.source;
    sc.drawImage(isolatedCell(image,source,make),...rect);
    const pixels=sc.getImageData(...bounds).data,color=kind==='shadows'?rgb(e.color??'#000000'):null;
    if(kind==='reflections'){
      const inverse=inv(matrix),shade=appearance.get(caster.id);
      for(let y=0;y<bounds[3];y++)for(let x=0;x<bounds[2];x++){const i=(y*bounds[2]+x)*4;if(!pixels[i+3])continue;const local=xy(inverse,x+bounds[0]+.5,y+bounds[1]+.5),world=xy(caster.matrix,local[0]+localGround[0],local[1]+localGround[1]);const c=shade([LUT[pixels[i]],LUT[pixels[i+1]],LUT[pixels[i+2]]],...world);for(let k=0;k<3;k++)pixels[i+k]=clamp(encode(c[k]))*255;}
    }
    if(e.mask_asset){for(let i=0;i<pixels.length;i+=4)pixels[i+3]*=(.2126*pixels[i]+.7152*pixels[i+1]+.0722*pixels[i+2])/255;}
    // Blur alpha and premultiplied color together via separable filters. This
    // avoids dark fringes around colored reflections.
    if(softness){if(kind==='shadows')blurAlpha(pixels,bounds[2],bounds[3],softness*H);else blurLinearRGBA(pixels,bounds[2],bounds[3],softness*H);}
    const [rx,ry,rw,rh]=receiverBounds;
    for(let y=0;y<bounds[3];y++)for(let x=0;x<bounds[2];x++){const xx=x+bounds[0]-rx,yy=y+bounds[1]-ry,i=(y*bounds[2]+x)*4;pixels[i+3]*=xx>=0&&xx<rw&&yy>=0&&yy<rh?receiverPixels[(yy*rw+xx)*4+3]/255:0;}
    blit(bounds,pixels,opacity*intensity(e)*caster.opacity*receiver.opacity,'source-over',color?()=>debug?[1,1,1]:color:null);
  }
  for(const s of states){if(!s.visible||(options.solo&&s.id!==options.selected))continue;const bounds=bounding(s.matrix,s.rect,W,H);if(!bounds[2]||!bounds[3])continue;renderLayer(s);const pixels=sc.getImageData(...bounds).data,l=layers.get(s.id),inverse=inv(s.matrix);
    blit(bounds,pixels,s.opacity,debug?'source-over':s.blend,(c,x,y)=>{
      if(pass==='shadows'||pass==='reflections')return [0,0,0];
      if(pass==='ungraded')return c;
      return appearance.get(s.id)(c,x,y,pass==='lights');
    });
    if(pass!=='ungraded')for(const kind of ['shadows','reflections'])if(pass==='beauty'||pass===kind)for(const e of f[kind]||[])if(e.receiver===s.id)effect(e,kind,pixels,bounds);
  }
  const result=ctx.createImageData(W,H);
  for(let i=0;i<W*H;i++){let c=[buffer[i*3],buffer[i*3+1],buffer[i*3+2]];if(pass==='beauty'&&f.grade)c=gradeRGB(c,f.grade,maskValue(f.grade.mask_asset,(i%W+.5)/W,(Math.floor(i/W)+.5)/H,images,make,catalog));if(c.some(v=>v>1))clipped++;for(let k=0;k<3;k++)result.data[i*4+k]=Math.round(clamp(encode(Math.max(0,c[k])))*255);result.data[i*4+3]=255;}
  ctx.setTransform(1,0,0,1,0,0);ctx.globalAlpha=1;ctx.globalCompositeOperation='source-over';ctx.putImageData(result,0,0);
  return {clipped_pixels:clipped,total_pixels:W*H,pass};
}
