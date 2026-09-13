"""Loopback-only draft evaluation over receipt-verified, in-memory source snapshots."""
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import BoundedSemaphore
from urllib.parse import parse_qs, unquote, urlsplit

from . import preparation
from . import workbench_http as http

MAX_REQUEST = 1_000_000
CSP = "default-src 'self'; img-src 'self' data: blob:; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'"


def handler_for(directory):
    original, inputs, files = preparation.artifact(directory)
    body_policy = http.BodyPolicy(
        maximum=MAX_REQUEST, missing_length='-1',
        bounds_error='Preview recipe is too large or has no bounded length',
        reject_transfer_encoding=True, timeout=10, incomplete_error='Incomplete preview recipe')
    evaluation_slot = BoundedSemaphore(1)
    # Source originals and compiler records stay on disk; only viewer assets are mounted.
    public = {name: data for name, data in files.items()
              if name in ('index.html', 'workbench.json', 'engine.mjs', 'clock.mjs', 'finishing.mjs', 'bindings.mjs', 'views.mjs',
                          'preparation-workbench.mjs', 'preparation-workbench.css') or name.startswith('images/')}

    class Handler(BaseHTTPRequestHandler):
        def local_request(self):
            violation = http.local_origin_violation(self)
            if violation == 'Host':
                self.send_error(403, 'Use the exact local preview address')
                return False
            if violation == 'Origin':
                self.send_error(403, 'Cross-origin preview requests are not supported')
                return False
            return True

        def respond(self, data, mime, status=200, download=False):
            http.respond(self, data, mime, status=status, csp=CSP,
                         disposition='attachment; filename="preparation-recipe.json"' if download else None)

        def do_GET(self):
            if not self.local_request():
                return
            name = unquote(urlsplit(self.path).path).lstrip('/') or 'index.html'
            if name not in public:
                self.send_error(404); return
            mime = 'text/javascript' if name.endswith('.mjs') else mimetypes.guess_type(name)[0] or 'application/octet-stream'
            self.respond(public[name], mime)

        def do_POST(self):
            if not self.local_request():
                return
            route = urlsplit(self.path).path
            if route not in ('/api/preview', '/api/export'):
                self.send_error(404); return
            expected_type = 'application/x-www-form-urlencoded' if route == '/api/export' else 'application/json'
            if self.headers.get('Content-Type') != expected_type:
                self.send_error(415, 'Unexpected recipe content type'); return
            if not evaluation_slot.acquire(blocking=False):
                self.send_error(429, 'A preparation preview is already being calculated'); return
            try:
                length = http.body_length(self, body_policy)
                body = http.read_body(self, length, body_policy)
                if route == '/api/export':
                    values = parse_qs(body.decode(), strict_parsing=True, max_num_fields=1)
                    if set(values) != {'recipe'} or len(values['recipe']) != 1:
                        raise ValueError('Expected exactly one recipe')
                    candidate = json.loads(values['recipe'][0])
                    preparation.validate(candidate)
                    if dict(preparation.references(candidate)) != dict(preparation.references(original)):
                        raise ValueError('Exports must retain captured input identities')
                    data = (json.dumps(candidate, indent=2, allow_nan=False)+'\n').encode()
                    self.respond(data, 'application/json', download=True)
                    return
                candidate = json.loads(body)
                data = preparation.preview_result(candidate, original, inputs)
                self.respond(json.dumps({'ok': True, 'data': data}, allow_nan=False).encode(), 'application/json')
            except http.BodyBoundsError as error:
                self.send_error(413, str(error))
            except (ValueError, KeyError, TypeError, OSError) as error:
                self.respond(json.dumps({'ok': False, 'error': str(error)}).encode(), 'application/json', 400)
            finally:
                evaluation_slot.release()

    return Handler


def serve(directory, port):
    # Concurrent asset requests, with a single bounded full-resolution evaluation.
    server = ThreadingHTTPServer(('127.0.0.1', port), handler_for(directory))
    print(json.dumps({'ok': True, 'schema_version': 1, 'command': 'preview', 'data': {
        'url': f'http://127.0.0.1:{server.server_port}/', 'prepare': str(Path(directory).resolve()),
        'project_writes': False, 'draft_evaluation': True}}), flush=True)
    http.serve_until_interrupt(server)
