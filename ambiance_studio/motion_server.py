"""Verified localhost proof, with bounded in-memory draft evaluation only."""
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import mimetypes
from pathlib import Path
import threading
from urllib.parse import urlsplit
from . import asset_motion as motion
from .motion_proof import verify
from .edge_quality import isolated_resize
from . import workbench_http as http

CSP = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'"
# Motion's existing contract neither sets a read timeout nor checks short reads
# or Transfer-Encoding. Keep those choices explicit rather than inheriting them.
BODY_POLICY = http.BodyPolicy(
    maximum=1_000_000, missing_length='0', bounds_error='Draft request must be 1–1000000 bytes',
    reject_transfer_encoding=False, timeout=None, incomplete_error=None)


def evaluate(packet,request):
    motion.fields(request,['study','changes'],'draft request',['study','changes'])
    # View edits may change artistic intent, never the proof's source or scene binding.
    if request['study']['baseline']!=packet['study']['baseline'] or request['study']['view']!=packet['study']['view']:raise ValueError('Draft source/view identity differs from proof')
    context=motion.load(Path(packet['project']),data=request['study']);updated=motion.edited(context,request['changes'])
    if updated['study']['baseline']!=packet['study']['baseline'] or updated['study']['view']!=packet['study']['view']:raise ValueError('Draft cannot replace source/view bindings')
    sol=motion.solution(updated);images=[];error=None
    if sol['ok']:
        try:
            for im in motion.raster(updated):
                buf=io.BytesIO();isolated_resize(im,tuple(packet['display_size'])).save(buf,format='PNG');images.append('data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode())
        except ValueError as exc:error=str(exc)
    return {'study':updated['study'],'solution':sol,'images':images,'raster_error':error}


def handler(directory):
    directory=Path(directory).resolve();report=verify(directory)
    routes={'/'+file:(directory/file).read_bytes() for file in report['outputs']};routes['/']=routes['/index.html'];routes['/report.json']=(directory/'report.json').read_bytes()
    packet=json.loads(routes['/packet.json']);slot=threading.Lock()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def respond(self,code,body,kind='application/json'):
            http.respond(self, body, kind, status=code, csp=CSP)
        def allowed(self):
            return http.local_origin_violation(self) is None
        def do_GET(self):
            if not self.allowed():return self.respond(403,b'{"error":"Local origin required"}')
            route=urlsplit(self.path).path
            if route not in routes:return self.respond(404,b'{"error":"Unknown proof resource"}')
            self.respond(200,routes[route],mimetypes.guess_type('index.html' if route=='/' else route)[0] or 'application/octet-stream')
        def do_POST(self):
            if not self.allowed():return self.respond(403,b'{"error":"Local origin required"}')
            if self.path!='/api/draft':return self.respond(404,b'{"error":"Unknown operation"}')
            try:
                n = http.body_length(self, BODY_POLICY)
                if not slot.acquire(blocking=False):return self.respond(409,b'{"error":"Draft evaluator busy"}')
                try:result=evaluate(packet,json.loads(http.read_body(self, n, BODY_POLICY)))
                finally:slot.release()
                self.respond(200,motion.encode(result))
            except (ValueError,OSError,KeyError,TypeError) as exc:self.respond(422,motion.encode({'error':str(exc)}))
    return Handler


def serve(directory,port):
    server=ThreadingHTTPServer(('127.0.0.1',port),handler(directory));server.daemon_threads=True
    print(json.dumps({'ok':True,'url':f'http://127.0.0.1:{server.server_port}','mode':'motion-proof','draft_writes_project':False}),flush=True)
    http.serve_until_interrupt(server)
