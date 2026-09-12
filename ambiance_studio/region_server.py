"""Loopback region drafts over captured inputs; never writes project files."""
import base64
import io
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import BoundedSemaphore
from urllib.parse import urlsplit

from . import art_regions as ar


def image_url(im):
    from PIL import Image
    im=im.copy();im.thumbnail((1200,1200),Image.Resampling.LANCZOS)
    data=io.BytesIO();im.save(data,format='PNG')
    return 'data:image/png;base64,'+base64.b64encode(data.getvalue()).decode()


def preview(recipe, inputs):
    info,images=ar.pictures(recipe,inputs)
    return {'recipe':recipe,'report':info,'images':{name:image_url(im) for name,im in images.items()}}


def handler_for(directory):
    from PIL import Image
    directory=Path(directory).resolve();recipe,inputs,receipt=ar.verify(directory)
    if receipt['runtime']!=ar.runtime(): raise ValueError('Region runtime changed; rebuild the packet before editing drafts')
    state=preview(recipe,inputs);state['kind']=receipt['kind']
    if receipt['kind']=='return':
        state['report']=ar.read(directory/'report.json')
        for name in ('paint','patch','composite','missing-paint','alignment-reference'):
            with Image.open(directory/(name+'.png')) as im: state['images'][name]=image_url(im)
    public={name:(ar.ROOT/'editor'/name).read_bytes() for name in ('region-workbench.html','region-workbench.mjs','region-workbench.css')}
    slot=BoundedSemaphore(1)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def local(self):
            expected=f'127.0.0.1:{self.server.server_port}'
            if self.headers.get('Host')!=expected or self.headers.get('Origin',f'http://{expected}')!=f'http://{expected}':
                self.send_error(403,'Use the exact local preview origin');return False
            return True
        def send(self,data,mime='application/json',status=200):
            self.send_response(status);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'")
            self.end_headers();self.wfile.write(data)
        def do_GET(self):
            if not self.local(): return
            route=urlsplit(self.path).path
            if route=='/api/state': return self.send(json.dumps(state,allow_nan=False).encode())
            name=route.lstrip('/') or 'region-workbench.html'
            if name not in public: return self.send_error(404)
            self.send(public[name],{'html':'text/html','mjs':'text/javascript','css':'text/css'}[name.rsplit('.',1)[1]])
        def do_POST(self):
            if not self.local(): return
            if urlsplit(self.path).path!='/api/preview': return self.send_error(404)
            if self.headers.get('Content-Type')!='application/json': return self.send_error(415)
            if not slot.acquire(blocking=False): return self.send_error(429,'A draft is being evaluated')
            try:
                length=int(self.headers.get('Content-Length','-1'))
                if not 0<length<=1_000_000 or self.headers.get('Transfer-Encoding'): raise ValueError('Supply a bounded region recipe')
                self.connection.settimeout(10);body=self.rfile.read(length)
                if len(body)!=length: raise ValueError('Incomplete recipe')
                candidate=ar.load_scene_json(body);ar.validate(candidate)
                if dict(ar.references(candidate))!=dict(ar.references(recipe)): raise ValueError('Drafts must retain captured input identities')
                result=preview(candidate,inputs)
                self.send(json.dumps({'ok':True,'data':result},allow_nan=False).encode())
            except (ValueError,KeyError,TypeError,OSError) as error:
                self.send(json.dumps({'ok':False,'error':str(error)}).encode(),status=400)
            finally: slot.release()
    return Handler


def serve(directory,port):
    server=ThreadingHTTPServer(('127.0.0.1',port),handler_for(directory))
    print(json.dumps({'ok':True,'schema_version':1,'command':'preview','data':{'url':f'http://127.0.0.1:{server.server_port}/','region':str(Path(directory).resolve()),'project_writes':False}}),flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
