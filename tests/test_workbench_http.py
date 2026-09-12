"""Wire contracts for the three draft workbenches, using real captured artifacts."""
from contextlib import contextmanager
import copy
from concurrent.futures import ThreadPoolExecutor
import http.client
from http.server import ThreadingHTTPServer
import io
import json
import mimetypes
from pathlib import Path
import socket
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
from urllib.parse import urlencode

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import test_asset_motion as motion_fixture
from ambiance_studio import art_regions, asset_prep, asset_motion, motion_proof, preparation
from ambiance_studio import motion_server, preparation_server, region_server


CSP = {
    'prepare': "default-src 'self'; img-src 'self' data: blob:; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'",
    'region': "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'",
    'motion': "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'",
}


@contextmanager
def running(handler):
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .01})
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def request(server, method, path, body=b'', headers=None, *, short=False):
    """Send exactly the supplied framing, including missing/invalid length cases."""
    connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
    try:
        connection.putrequest(method, path, skip_host=True)
        for key, value in {'Host': f'127.0.0.1:{server.server_port}', **(headers or {})}.items():
            connection.putheader(key, value)
        connection.endheaders(body)
        if short:
            connection.sock.shutdown(socket.SHUT_WR)
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        connection.close()


class WorkbenchHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        asset_prep.write(cls.root/'ambiance-project.json', {'version': 1})
        Image.new('RGBA', (32, 48), '#17324a').save(cls.root/'source.png')
        Image.new('RGBA', (32, 48), '#adc6cf').save(cls.root/'backing.png')
        recipe = preparation.initial_recipe(cls.root, cls.root/'source.png', cls.root/'backing.png')
        recipe['masks']['cutout']['polygons'] = [
            {'operation': 'add', 'points': [[8, 8], [24, 8], [24, 32], [8, 32]]}]
        asset_prep.write(cls.root/'prepare.json', recipe)
        preparation.build(cls.root, cls.root/'prepare', recipe_path=cls.root/'prepare.json')
        region = art_regions.initial(cls.root, cls.root/'source.png', 'window')
        region['visible_mask']['polygons'] = copy.deepcopy(recipe['masks']['cutout']['polygons'])
        region['sizing'].update(display_size=[32, 48], quality_multiplier=1, export_size=[64, 96])
        art_regions.save_draft(cls.root, region, cls.root/'region-draft')
        art_regions.build(cls.root, cls.root/'region-draft', cls.root/'region')
        motion_root = motion_fixture.fixture(cls.root/'motion-project')
        study = motion_fixture.annotated(motion_root)
        asset_prep.write(motion_root/'study.json', study)
        motion_proof.proof(asset_motion.load(motion_root, data=study), motion_root/'study.json', motion_root/'proof')
        cls.directories = {'prepare': cls.root/'prepare', 'region': cls.root/'region', 'motion': motion_root/'proof'}
        cls.candidates = {'prepare': recipe, 'region': region, 'motion': {
            'study': study, 'changes': {'version': 1, 'operations': [{'op': 'note', 'text': 'HTTP café'}]}}}
        cls.factories = {'prepare': preparation_server.handler_for,
                         'region': region_server.handler_for, 'motion': motion_server.handler}
        cls.routes = {'prepare': '/api/preview', 'region': '/api/preview', 'motion': '/api/draft'}
        cls.before = cls.files()

    @classmethod
    def files(cls):
        return {str(p.relative_to(cls.root)): p.read_bytes() for p in cls.root.rglob('*') if p.is_file()}

    def tearDown(self):
        self.assertEqual(self.files(), self.before, 'HTTP drafts must never change captured or project files')

    def handler(self, kind):
        return self.factories[kind](self.directories[kind])

    def post(self, server, kind, *, candidate=None, headers=None, route=None):
        body = json.dumps(self.candidates[kind] if candidate is None else candidate).encode()
        return request(server, 'POST', route or self.routes[kind], body,
                       {'Content-Length': str(len(body)), 'Content-Type': 'application/json', **(headers or {})})

    def assert_response(self, response, kind, status=200, mime='application/json'):
        code, headers, body = response
        self.assertEqual(code, status)
        self.assertEqual(headers['Content-Type'], mime)
        self.assertEqual(headers['Content-Length'], str(len(body)))
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(headers['Content-Security-Policy'], CSP[kind])
        self.assertNotIn('Access-Control-Allow-Origin', headers)
        return body

    def test_routes_content_types_and_captured_bytes(self):
        for kind in self.factories:
            with self.subTest(kind=kind), running(self.handler(kind)) as server:
                home = self.assert_response(request(server, 'GET', '/?view=1'), kind, mime='text/html')
                name = 'region-workbench.html' if kind == 'region' else 'index.html'
                source = ROOT/'editor'/name if kind == 'region' else self.directories[kind]/name
                self.assertEqual(home, source.read_bytes())
                script = {'prepare': 'preparation-workbench.mjs', 'region': 'region-workbench.mjs',
                          'motion': 'workbench.mjs'}[kind]
                # Motion deliberately uses the platform MIME lookup; other handlers force JS.
                mime = mimetypes.guess_type(script)[0] if kind == 'motion' else 'text/javascript'
                self.assert_response(request(server, 'GET', '/'+script), kind, mime=mime)
                for route in ('/../source.png', '/%2e%2e/source.png', '/inputs/source', '/snapshots/source.bin', '/recipe.json'):
                    self.assertEqual(request(server, 'GET', route)[0], 404, route)
                self.assertEqual(request(server, 'POST', '/api/unknown')[0], 404)
                self.assertEqual(request(server, 'OPTIONS', '/')[0], 501)
                self.assertEqual(request(server, 'HEAD', '/')[0], 501)
                # URL decoding is intentionally preparation-only.
                self.assertEqual(request(server, 'GET', '/%'+format(ord(script[0]), 'x')+script[1:])[0],
                                 200 if kind == 'prepare' else 404)
                state = '/api/state' if kind == 'region' else '/report.json'
                self.assertEqual(request(server, 'GET', state)[0], 404 if kind == 'prepare' else 200)

    def test_exact_host_origin_and_error_formats(self):
        for kind in self.factories:
            with self.subTest(kind=kind), running(self.handler(kind)) as server:
                origin = f'http://127.0.0.1:{server.server_port}'
                self.assertEqual(request(server, 'GET', '/', headers={'Origin': origin})[0], 200)
                for headers in ({'Host': f'localhost:{server.server_port}'}, {'Host': 'evil.invalid'},
                                {'Origin': 'null'}, {'Origin': origin+'/'}, {'Origin': 'https://evil.invalid'}):
                    for method, route in (('GET', '/'), ('POST', self.routes[kind])):
                        response = request(server, method, route, headers=headers)
                        if kind == 'motion':
                            self.assertEqual(self.assert_response(response, kind, 403), b'{"error":"Local origin required"}')
                        else:
                            self.assertEqual(response[0], 403)
                            self.assertEqual(response[1]['Content-Type'], 'text/html;charset=utf-8')
                            message = ('Use the exact local preview origin' if kind == 'region' else
                                       'Use the exact local preview address' if 'Host' in headers else
                                       'Cross-origin preview requests are not supported')
                            self.assertIn(message.encode(), response[2])

    def test_success_and_content_type_query_differences(self):
        for kind in self.factories:
            with self.subTest(kind=kind), running(self.handler(kind)) as server:
                body = self.assert_response(self.post(server, kind), kind)
                self.assertTrue(json.loads(body)['solution' if kind == 'motion' else 'ok'])
                for mime in ('text/plain', 'application/json; charset=utf-8'):
                    self.assertEqual(self.post(server, kind, headers={'Content-Type': mime})[0],
                                     200 if kind == 'motion' else 415)
                self.assertEqual(self.post(server, kind, route=self.routes[kind]+'?view=1')[0],
                                 404 if kind == 'motion' else 200)

    def test_length_bounds_malformed_json_and_transfer_encoding(self):
        for kind in self.factories:
            with self.subTest(kind=kind), running(self.handler(kind)) as server:
                invalid_status = {'prepare': 413, 'region': 400, 'motion': 422}[kind]
                for length in (None, '0', '-1', '1000001', 'bad'):
                    headers = {'Content-Type': 'application/json'}
                    if length is not None:
                        headers['Content-Length'] = length
                    response = request(server, 'POST', self.routes[kind], headers=headers)
                    self.assertEqual(response[0], (400 if kind != 'motion' else 422) if length == 'bad' else invalid_status)
                    if length == 'bad':
                        self.assert_response(response, kind, response[0])
                        self.assertIn(b'invalid literal', response[2])
                response = self.post(server, kind, headers={'Transfer-Encoding': 'chunked'})
                self.assertEqual(response[0], 200 if kind == 'motion' else invalid_status)
                response = request(server, 'POST', self.routes[kind], b'{',
                                   {'Content-Type': 'application/json', 'Content-Length': '1'})
                self.assert_response(response, kind, 422 if kind == 'motion' else 400)
                # Exact maximum length remains valid (whitespace is legal JSON padding).
                body = json.dumps(self.candidates[kind]).encode().ljust(1_000_000, b' ')
                response = request(server, 'POST', self.routes[kind], body,
                                   {'Content-Type': 'application/json', 'Content-Length': str(len(body))})
                self.assert_response(response, kind)

    def test_short_reads_keep_workbench_specific_behavior(self):
        for kind in self.factories:
            with self.subTest(kind=kind), running(self.handler(kind)) as server:
                body = json.dumps(self.candidates[kind]).encode()
                response = request(server, 'POST', self.routes[kind], body,
                                   {'Content-Length': str(len(body)+1), 'Content-Type': 'application/json'}, short=True)
                self.assert_response(response, kind, 200 if kind == 'motion' else 400)
                if kind != 'motion':
                    self.assertIn(b'Incomplete', response[2])
                self.assertEqual(self.post(server, kind)[0], 200, 'failed reads release the evaluation slot')

    def test_export_bytes_download_and_identity_rejection(self):
        with running(self.handler('prepare')) as server:
            recipe = copy.deepcopy(self.candidates['prepare'])
            recipe['source']['sha256'] = 'a'*64
            for candidate, status in ((self.candidates['prepare'], 200), (recipe, 400)):
                body = urlencode({'recipe': json.dumps(candidate)}).encode()
                response = request(server, 'POST', '/api/export', body,
                                   {'Content-Type': 'application/x-www-form-urlencoded', 'Content-Length': str(len(body))})
                data = self.assert_response(response, 'prepare', status)
                if status == 200:
                    self.assertEqual(data, (json.dumps(candidate, indent=2, allow_nan=False)+'\n').encode())
                    self.assertEqual(response[1]['Content-Disposition'], 'attachment; filename="preparation-recipe.json"')
                else:
                    self.assertNotIn('Content-Disposition', response[1])
            for body in (b'other=%7B%7D', b'recipe=%7B%7D&recipe=%7B%7D', b'recipe=', b'recipe'):
                self.assertEqual(request(server, 'POST', '/api/export', body,
                    {'Content-Type': 'application/x-www-form-urlencoded', 'Content-Length': str(len(body))})[0], 400)

    def test_drafts_reject_changed_captured_identities(self):
        for kind in self.factories:
            with self.subTest(kind=kind), running(self.handler(kind)) as server:
                candidate = copy.deepcopy(self.candidates[kind])
                if kind == 'motion':
                    candidate['study']['view']['display_width'] = 99
                else:
                    candidate['source']['sha256'] = 'a'*64
                self.assert_response(self.post(server, kind, candidate=candidate), kind, 422 if kind == 'motion' else 400)
                self.assertEqual(self.post(server, kind)[0], 200)

    def test_concurrent_drafts_keep_lock_order_and_release_after_failure(self):
        targets = {'prepare': (preparation_server.preparation, 'preview_result'),
                   'region': (region_server, 'preview'), 'motion': (motion_server, 'evaluate')}
        for kind in self.factories:
            with self.subTest(kind=kind), running(self.handler(kind)) as server:
                entered, release = threading.Event(), threading.Event()
                def held(*args):
                    entered.set()
                    if not release.wait(5):
                        raise AssertionError('test did not release evaluator')
                    raise ValueError('injected evaluation failure')
                with patch.object(*targets[kind], side_effect=held), ThreadPoolExecutor(max_workers=1) as pool:
                    pending = pool.submit(self.post, server, kind)
                    try:
                        self.assertTrue(entered.wait(5))
                        busy = 409 if kind == 'motion' else 429
                        self.assertEqual(self.post(server, kind)[0], busy)
                        self.assertEqual(self.post(server, kind, headers={'Content-Length': 'bad'})[0],
                                         422 if kind == 'motion' else busy)
                        self.assertEqual(request(server, 'GET', '/')[0], 200)
                        if kind == 'prepare':
                            self.assertEqual(self.post(server, kind, route='/api/export',
                                headers={'Content-Type': 'application/x-www-form-urlencoded'})[0], busy)
                    finally:
                        release.set()
                    self.assert_response(pending.result(timeout=5), kind, 422 if kind == 'motion' else 400)
                self.assertEqual(self.post(server, kind)[0], 200, 'failed evaluation must release the slot')

    def test_read_timeouts_remain_specific_to_each_workbench(self):
        for kind in self.factories:
            handler = self.handler(kind)
            connections = []
            class Observed(handler):
                def setup(self):
                    super().setup()
                    self.connection = Mock(wraps=self.connection)
                    connections.append(self.connection)
            with self.subTest(kind=kind), running(Observed) as server:
                self.assertEqual(self.post(server, kind)[0], 200)
                if kind == 'motion':
                    connections[0].settimeout.assert_not_called()
                else:
                    connections[0].settimeout.assert_called_once_with(10)


class WorkbenchLifecycleTests(unittest.TestCase):
    def test_startup_envelopes_loopback_and_close_on_interrupt_or_error(self):
        for kind, module, factory in (('prepare', preparation_server, 'handler_for'),
                                      ('region', region_server, 'handler_for'),
                                      ('motion', motion_server, 'handler')):
            for failure in (None, KeyboardInterrupt, RuntimeError('serve failed')):
                with self.subTest(kind=kind, failure=failure):
                    server = Mock(server_port=12345)
                    server.serve_forever.side_effect = failure
                    with patch.object(module, factory, return_value='handler') as handler, \
                            patch.object(module, 'ThreadingHTTPServer', return_value=server) as create, \
                            patch('sys.stdout', new_callable=io.StringIO) as output:
                        if isinstance(failure, RuntimeError):
                            with self.assertRaisesRegex(RuntimeError, 'serve failed'):
                                module.serve('.', 0)
                        else:
                            module.serve('.', 0)
                    handler.assert_called_once_with('.')
                    create.assert_called_once_with(('127.0.0.1', 0), 'handler')
                    server.serve_forever.assert_called_once_with()
                    server.server_close.assert_called_once_with()
                    expected = {'ok': True, 'schema_version': 1, 'command': 'preview', 'data': {
                        'url': 'http://127.0.0.1:12345/', kind: str(Path('.').resolve()), 'project_writes': False}}
                    if kind == 'prepare':
                        expected['data']['draft_evaluation'] = True
                    if kind == 'motion':
                        expected = {'ok': True, 'url': 'http://127.0.0.1:12345',
                                    'mode': 'motion-proof', 'draft_writes_project': False}
                        self.assertIs(server.daemon_threads, True)
                    self.assertEqual(output.getvalue(), json.dumps(expected)+'\n')


if __name__ == '__main__':
    unittest.main(verbosity=2)
