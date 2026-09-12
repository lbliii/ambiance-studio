"""Project-only browser coverage diagnostic, sharing the production renderer."""
import sys
from pathlib import Path
from http.server import ThreadingHTTPServer
P=Path(__file__).resolve().parents[1]; R=P.parents[1]; sys.path.insert(0,str(R))
from ambiance_studio.preview import handler_for
Base=handler_for(R,P)
HTML='''<!doctype html><meta charset="utf-8"><title>Amberwatch coverage diagnosis</title><style>body{background:#222;color:#eee;font:16px system-ui}canvas{width:640px;image-rendering:pixelated}pre{white-space:pre-wrap}</style><h1>Painted coverage</h1><p>Magenta marks alpha below 254. Diagnostic only; picture remains unchanged.</p><div id="images"></div><pre id="result">Loading…</pre><script type="module">
import {createStageRenderer} from '/editor/stage-raster.mjs';
import {planViews} from '/editor/views.mjs';
const scene=await(await fetch('/api/scene')).json(),catalog=await(await fetch('/api/catalog')).json(),images=new Map();
await Promise.all(catalog.assets.map(async a=>{const im=new Image();im.src=a.file;await im.decode();images.set(a.id,im)}));
const make=(w,h)=>{const c=document.createElement('canvas');c.width=w;c.height=h;return c};
const rows=[];
for(const edge of [240,1086]){
const plan=planViews(scene,[{id:'portrait'},{id:'landscape'}],{long_edge:edge}),r=createStageRenderer(scene,catalog,images,plan,make);
for(const t of [0,1/30,3.8]){r.render(t,{coverage:true});for(const[id,c]of r.outputs){const ctx=c.getContext('2d'),d=ctx.getImageData(0,0,c.width,c.height);let n=0,interior=0,min=255,b=[c.width,c.height,0,0],xs={},ys={};for(let i=3;i<d.data.length;i+=4){const a=d.data[i];if(a>=254)continue;const q=(i-3)/4,x=q%c.width,y=Math.floor(q/c.width);n++;min=Math.min(min,a);b=[Math.min(b[0],x),Math.min(b[1],y),Math.max(b[2],x),Math.max(b[3],y)];if(x>2&&y>2&&x<c.width-3&&y<c.height-3)interior++;xs[x]=(xs[x]||0)+1;ys[y]=(ys[y]||0)+1;d.data[i-3]=255;d.data[i-2]=0;d.data[i-1]=255;d.data[i]=255;}rows.push({edge,t,id,size:[c.width,c.height],n,interior,min,b,xs:Object.entries(xs).sort((a,b)=>b[1]-a[1]).slice(0,5),ys:Object.entries(ys).sort((a,b)=>b[1]-a[1]).slice(0,5)});if(edge===240&&t===1/30){const h=document.createElement('h2');h.textContent=id;const show=make(c.width,c.height);show.getContext('2d').putImageData(d,0,0);document.querySelector('#images').append(h,show)}}r.render(t)}
}
document.querySelector('#result').textContent=JSON.stringify(rows,null,2);
</script>'''
class Handler(Base):
 def do_GET(self):
  if self.path=='/diagnostic':
   data=HTML.encode();self.send_response(200);self.send_header('Content-Type','text/html');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
  else:super().do_GET()
ThreadingHTTPServer(('127.0.0.1',8794),Handler).serve_forever()
