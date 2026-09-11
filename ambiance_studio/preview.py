"""Read-only project preview with explicit mounts; never serves the repository tree."""
import json
import hashlib
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit


def resolve_routes(root, project):
    settings=json.loads((project/'ambiance-project.json').read_text())
    def inside(name):
        path=(project/name).resolve()
        if not path.is_relative_to(project): raise ValueError('Preview path escapes project')
        return path
    scene=inside(settings['scene']);catalog_path=inside(settings['catalog'])
    catalog=json.loads(catalog_path.read_text())
    media={}
    for asset in catalog['assets']:
        path=inside(asset['file'])
        media['/media/'+asset['id']]=path
        asset['file']='/media/'+asset['id']
    return scene,catalog,media


def handler_for(root,project):
    root,project=Path(root).resolve(),Path(project).resolve()
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            try:
                route=unquote(urlsplit(self.path).path)
                if route in ['/', '/editor']:
                    self.send_response(302);self.send_header('Location','/editor/');self.end_headers();return
                scene,catalog,media=resolve_routes(root,project)
                data=None;mime='application/json'
                if route=='/api/config':data=json.dumps({'scene':'/api/scene','catalog':'/api/catalog'}).encode()
                elif route=='/api/scene':data=scene.read_bytes()
                elif route=='/api/catalog':data=json.dumps(catalog).encode()
                elif route in media:
                    data=media[route].read_bytes();mime=mimetypes.guess_type(str(media[route]))[0] or 'application/octet-stream'
                elif route in ['/', '/editor', '/editor/']:data=(root/'editor/index.html').read_bytes();mime='text/html'
                elif route.startswith('/editor/'):
                    file=(root/route.lstrip('/')).resolve()
                    if file.parent==root/'editor' and file.suffix in ['.mjs','.css','.html'] and file.is_file():
                        data=file.read_bytes();mime='text/javascript' if file.suffix=='.mjs' else mimetypes.guess_type(str(file))[0]
                if data is None:self.send_error(404);return
                self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(data)))
                self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(data)
            except (ValueError,KeyError,OSError):self.send_error(400,'Project files unavailable or invalid')
    return Handler


def serve(root,project,port):
    server=ThreadingHTTPServer(('127.0.0.1',port),handler_for(root,project))
    print(json.dumps({'ok':True,'schema_version':1,'command':'preview','data':{'url':f'http://127.0.0.1:{server.server_port}/editor/','project':str(project),'read_only':True}}),flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()


def look_routes(directory):
    """Load only receipt-listed files into an immutable read-only HTTP snapshot."""
    directory=Path(directory).resolve()
    report=json.loads((directory/'render-report.json').read_text())
    if report.get('mode')!='look-proof' or not report.get('ok'):raise ValueError('Expected a completed look-proof artifact')
    routes={}
    def add(name,digest):
        file=(directory/name).resolve()
        if not file.is_relative_to(directory) or Path(name).is_absolute():raise ValueError('Look artifact path escapes its directory')
        data=file.read_bytes()
        if hashlib.sha256(data).hexdigest()!=digest:raise ValueError(f'Look artifact changed: {name}')
        routes['/'+name]=data
    work=report['workbench']
    add('index.html',report['output_sha256']);add('workbench.css',work['stylesheet_sha256']);add('workbench.json',work['sha256'])
    for item in [*work['modules'],*work['asset_snapshots'],*report['samples']]:add(item['file'],item['sha256'])
    routes['/']=routes['/index.html']
    return routes


def views_proof_routes(directory):
    directory=Path(directory).resolve()
    report=json.loads((directory/'render-report.json').read_text())
    if report.get('mode')!='views-proof' or not report.get('ok'):raise ValueError('Expected a completed views-proof artifact')
    routes={}
    def add(name,digest):
        file=(directory/name).resolve()
        if not file.is_relative_to(directory) or Path(name).is_absolute():raise ValueError('View proof path escapes its directory')
        data=file.read_bytes()
        if hashlib.sha256(data).hexdigest()!=digest:raise ValueError(f'View proof changed: {name}')
        if '/'+name in routes:raise ValueError('Duplicate view proof file')
        routes['/'+name]=data
    add('index.html',report['output_sha256'])
    if not report['outputs']:raise ValueError('View proof has no outputs')
    for output in report['outputs']:
        if len(output['files'])!=report['frames'] or len(output['hashes'])!=report['frames']:raise ValueError('View proof frame list is incomplete')
        for name,digest in zip(output['files'],output['hashes']):add(name,digest)
    routes['/']=routes['/index.html']
    return routes


def serve_look(directory,port,kind='look'):
    routes=views_proof_routes(directory) if kind=='views-proof' else look_routes(directory)
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            route=unquote(urlsplit(self.path).path)
            if route not in routes:self.send_error(404);return
            data=routes[route];mime='text/javascript' if route.endswith('.mjs') else mimetypes.guess_type(route)[0] or ('text/html' if route=='/' else 'application/octet-stream')
            self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(data)
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    print(json.dumps({'ok':True,'schema_version':1,'command':'preview','data':{'url':f'http://127.0.0.1:{server.server_port}/',kind:str(Path(directory).resolve()),'read_only':True,'verified_files':len(routes)-1}}),flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
