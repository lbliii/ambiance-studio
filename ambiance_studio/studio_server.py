"""Local film library, exact movie streaming, and reusable server lifecycle."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import threading
import time
from urllib.error import URLError, HTTPError
from urllib.parse import urlsplit, unquote, parse_qs
from urllib.request import Request, urlopen
import webbrowser

import studio
from . import __version__, deliveries, production, registry

ROOT = Path(__file__).resolve().parents[1]


def service_path(path):
    return path.with_name(path.name + '.server.json')


def base_url(path):
    try:
        record = studio.read(service_path(path))
        return f'http://127.0.0.1:{int(record["port"])}'
    except (OSError, ValueError, KeyError, TypeError):
        return 'http://127.0.0.1:8783'


def byte_range(header, size):
    if not header:
        return 0, size-1, 200
    match = re.fullmatch(r'bytes=(\d*)-(\d*)', header)
    if not match or not any(match.groups()):
        raise ValueError('Unsupported byte range')
    first, last = match.groups()
    if first:
        start = int(first); end = min(int(last), size-1) if last else size-1
    else:
        length = int(last)
        if length < 1:
            raise ValueError('Invalid suffix range')
        start = max(0, size-length); end = size-1
    if start > end or start >= size:
        raise ValueError('Range outside movie')
    return start, end, 206


def handler_for(root, path, instance, shutdown_token):
    fingerprints = deliveries.Fingerprints()
    class Handler(BaseHTTPRequestHandler):
        def host_ok(self):
            return self.headers.get('Host') in [f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}']

        def respond(self, value, status=200):
            self.send_bytes(json.dumps(value, allow_nan=False).encode(), 'application/json', status)

        def send_bytes(self, data, mime, status=200):
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(data)

        def project(self, alias):
            return registry.resolve(root, path, alias)

        def stream(self, project, item, attachment=False):
            check = deliveries.intact(project, item, fingerprints)
            if not check['ok']:
                self.respond({'error': 'Selected file is missing or changed', 'detail': check}, 409); return
            file = studio.inside(project, item['path'])
            with file.open('rb') as source:
                stat = os.fstat(source.fileno())
                if stat != file.stat():
                    self.respond({'error': 'Selected file changed while opening'}, 409); return
                size = stat.st_size
                try:
                    start, end, status = byte_range(self.headers.get('Range'), size)
                except ValueError:
                    self.send_response(416); self.send_header('Content-Range', f'bytes */{size}')
                    self.send_header('Content-Length', '0'); self.end_headers(); return
                self.send_response(status)
                self.send_header('Content-Type', mimetypes.guess_type(file.name)[0] or 'application/octet-stream')
                self.send_header('Content-Length', str(end-start+1))
                self.send_header('Accept-Ranges', 'bytes')
                self.send_header('ETag', '"'+item['sha256']+'"')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('X-Content-Type-Options', 'nosniff')
                if status == 206:
                    self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
                if attachment:
                    name = re.sub(r'[^a-zA-Z0-9_.-]', '_', file.name)
                    self.send_header('Content-Disposition', f'attachment; filename="{name}"')
                self.end_headers()
                if self.command == 'HEAD':
                    return
                source.seek(start); remaining = end-start+1
                while remaining:
                    chunk = source.read(min(256*1024, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk); remaining -= len(chunk)

        def do_HEAD(self):
            self.do_GET()

        def do_GET(self):
            if not self.host_ok():
                self.respond({'error': 'Localhost access only'}, 403); return
            route = unquote(urlsplit(self.path).path)
            parts = route.strip('/').split('/')
            origin = f'http://127.0.0.1:{self.server.server_port}'
            try:
                if route == '/api/runtime':
                    self.respond({'application': 'ambiance-studio', 'version': __version__, 'instance': instance,
                                  'code_root': str(root), 'registry': str(path), 'url': origin, 'pid': os.getpid()}); return
                if route == '/api/projects':
                    rows = registry.projects(root, path)
                    for row in rows:
                        row['url'] = '/projects/'+row['id']
                        if row['available']:
                            try:
                                row['current'] = deliveries.latest(Path(row['path']), fingerprints=fingerprints)
                            except (OSError, ValueError, KeyError, TypeError) as error:
                                row['current'] = {'ok': False, 'error': str(error)}
                    self.respond({'projects': rows}); return
                if len(parts) >= 3 and parts[:2] == ['api', 'projects']:
                    alias = parts[2]; project = self.project(alias)
                    if len(parts) == 3:
                        result = production.overview(project, alias, origin, fingerprints)
                        result['title'] = registry.describe(project)['title']
                        self.respond(result); return
                    if parts[3:] == ['current']:
                        self.respond({'selection': deliveries.current(project), 'runs': production.runs(project)[:5]}); return
                    if len(parts) == 5 and parts[3] == 'deliveries':
                        data = deliveries.inspect(project, parts[4], fingerprints)
                        data['feedback'] = deliveries.feedback_list(project, parts[4])
                        self.respond(data); return
                if len(parts) == 4 and parts[0] in ['media', 'files']:
                    project = self.project(parts[1]); data = deliveries.load(project, parts[2]); key = parts[3]
                    if parts[0] == 'media':
                        item = data['poster'] if key == 'poster' else data['editions'][key]['movie']
                    else:
                        item = data['editions'][key]['verification']
                    if item is None:
                        self.respond({'error': 'No cover recorded'}, 404); return
                    self.stream(project, item, parse_qs(urlsplit(self.path).query).get('download') == ['1']); return
                if len(parts) == 4 and parts[:2] == ['api', 'editor']:
                    from .preview import resolve_routes
                    project = self.project(parts[2]); scene, catalog, media = resolve_routes(root, project)
                    if parts[3] == 'scene':
                        self.send_bytes(scene.read_bytes(), 'application/json'); return
                    if parts[3] == 'catalog':
                        for asset in catalog['assets']:
                            asset['file'] = f'/art/{parts[2]}/{asset["id"]}'
                        self.respond(catalog); return
                if len(parts) == 3 and parts[0] == 'art':
                    from .preview import resolve_routes
                    project = self.project(parts[1]); _, _, media = resolve_routes(root, project)
                    file = media['/media/'+parts[2]]
                    self.send_bytes(file.read_bytes(), mimetypes.guess_type(file.name)[0] or 'application/octet-stream'); return
                if route == '/' or (parts[0] == 'projects' and len(parts) in [2, 4]):
                    self.send_bytes((root/'studio/index.html').read_bytes(), 'text/html'); return
                if parts[0] in ['studio', 'editor']:
                    file = root/parts[0]/('index.html' if len(parts) == 1 else parts[-1])
                    if len(parts) <= 2 and file.resolve().parent == root/parts[0] and file.suffix in ['.html', '.mjs', '.css']:
                        self.send_bytes(file.read_bytes(), 'text/javascript' if file.suffix == '.mjs' else mimetypes.guess_type(file.name)[0]); return
                self.respond({'error': 'Not found'}, 404)
            except (OSError, ValueError, KeyError, TypeError) as error:
                self.respond({'error': str(error)}, 400)

        def do_POST(self):
            if not self.host_ok():
                self.respond({'error': 'Localhost access only'}, 403); return
            route = urlsplit(self.path).path
            if route == '/api/shutdown':
                if self.headers.get('Authorization') != 'Bearer '+shutdown_token:
                    self.respond({'error': 'Server token required'}, 403); return
                self.respond({'ok': True})
                threading.Thread(target=self.server.shutdown, daemon=True).start(); return
            allowed = [f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}']
            if self.headers.get('Origin') not in allowed:
                self.respond({'error': 'Feedback must come from this studio page'}, 403); return
            parts = route.strip('/').split('/')
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 16000:
                    raise ValueError('Feedback request too large or empty')
                body = json.loads(self.rfile.read(size))
                if len(parts) == 4 and parts[:2] == ['api', 'projects'] and parts[3] == 'feedback':
                    result = deliveries.feedback(self.project(parts[2]), body['delivery'], body['role'], body['seconds'], body['note'], body['observer'])
                    self.respond(result, 201); return
                self.respond({'error': 'Not found'}, 404)
            except (OSError, ValueError, KeyError, TypeError) as error:
                self.respond({'error': str(error)}, 400)

        def handle(self):
            try:
                super().handle()
            except (BrokenPipeError, ConnectionResetError):
                pass
    return Handler


def status(path):
    record_path = service_path(path)
    if not record_path.exists():
        return {'ok': True, 'running': False, 'registry': str(path)}
    try:
        record = studio.read(record_path)
        port = int(record['port'])
        if not 1 <= port <= 65535:
            raise ValueError('Invalid recorded studio port')
        with urlopen(f'http://127.0.0.1:{port}/api/runtime', timeout=1) as response:
            live = json.load(response)
        if live.get('application') != 'ambiance-studio' or live.get('instance') != record['instance'] or live.get('registry') != str(path):
            raise ValueError('Port belongs to a different server')
        return {'ok': True, 'running': True, **live}
    except (OSError, ValueError, KeyError, TypeError) as error:
        return {'ok': True, 'running': False, 'registry': str(path), 'stale_record': str(error)}


def serve(root, path, port):
    instance = secrets.token_hex(16); token = secrets.token_urlsafe(32)
    server = ThreadingHTTPServer(('127.0.0.1', port), handler_for(root, path, instance, token))
    server.daemon_threads = True
    file = service_path(path)
    try:
        with registry.registry_lock(path):
            if status(path)['running']:
                raise ValueError('A studio server is already running for this registry')
            studio.write(file, {'port': server.server_port, 'instance': instance, 'token': token,
                                'pid': os.getpid(), 'code_root': str(root)})
            file.chmod(0o600)
        print(json.dumps({'ok': True, 'schema_version': 1, 'command': 'studio serve',
                          'data': {'url': f'http://127.0.0.1:{server.server_port}/', 'registry': str(path)}}), flush=True)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        try:
            if studio.read(file).get('instance') == instance:
                file.unlink()
        except (OSError, ValueError):
            pass


def open_studio(root, path, port=8783, browser=True):
    running = status(path)
    reused = running['running']
    if not reused:
        path.parent.mkdir(parents=True, exist_ok=True)
        log_path = service_path(path).with_suffix('.log')
        with log_path.open('ab') as log:
            child = subprocess.Popen([sys.executable, str(root/'ambiance'), '--registry', str(path), 'studio', 'serve', '--port', str(port)],
                                     stdout=log, stderr=log, stdin=subprocess.DEVNULL, start_new_session=True, cwd=root)
        for _ in range(60):
            running = status(path)
            if running['running']:
                break
            if child.poll() is not None:
                raise ValueError(f'Studio could not start on port {port}; inspect {log_path}. No alternate port was selected.')
            time.sleep(.1)
        if not running['running']:
            child.terminate()
            raise ValueError('Studio did not become ready within six seconds')
    if browser:
        webbrowser.open(running['url']+'/')
    return {**running, 'reused': reused, 'serving_other_checkout': running['code_root'] != str(root)}


def stop(path):
    running = status(path)
    if not running['running']:
        return running
    record = studio.read(service_path(path))
    request = Request(running['url']+'/api/shutdown', data=b'', method='POST',
                      headers={'Authorization': 'Bearer '+record['token']})
    with urlopen(request, timeout=2) as response:
        json.load(response)
    return {'ok': True, 'stopped': True, 'url': running['url']}
