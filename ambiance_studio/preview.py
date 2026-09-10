"""Read-only project preview with explicit mounts; never serves the repository tree."""
import json
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
