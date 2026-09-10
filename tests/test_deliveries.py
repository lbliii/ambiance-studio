"""Delivery identity/selection fixtures. Synthetic bytes test records, not codecs."""
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import studio
from ambiance_studio import deliveries, production, registry, studio_server
from ambiance_studio.cli import init_project, parser, run, CommandError

ROOT = Path(__file__).resolve().parents[1]


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.project = self.root/'film'
        init_project(self.project, None, 'Independent film', 'blank')
        self.registry = self.root/'addresses/registry.json'
        registry.register(self.registry, self.project)

    def declaration(self, id='v1', roles=('score', 'effects', 'silent')):
        entries = []
        for role in roles:
            file = self.project/f'deliverables/{id}-{role}.mp4'
            file.write_bytes((f'Synthetic {id} {role} fixture. No actual media decode. '*20).encode())
            report = self.project/f'reports/{id}-{role}.json'
            studio.write(report, {'ok': True, 'fully_decoded': True, 'input_unchanged': True,
                'input_sha256': studio.digest(file), 'input_sha256_after': studio.digest(file),
                'width': 64, 'height': 96, 'fps': 10, 'decoded_frames': 20, 'duration_seconds': 2,
                'audio': {'tracks': 0 if role == 'silent' else 1}, 'synthetic_test_fixture': True})
            entries.append({'role': role, 'file': str(file.relative_to(self.project)), 'verification': str(report.relative_to(self.project))})
        return {'format': deliveries.SELECTION, 'schema_version': 1, 'id': id, 'title': 'Study '+id,
                'default_role': roles[0], 'editions': entries, 'scene_snapshot': 'scene/scene.json', 'catalog_snapshot': 'assets/catalog.json'}

    def register(self, id='v1', roles=('score', 'effects', 'silent')):
        declaration = self.declaration(id, roles)
        deliveries.register(self.project, declaration)
        return declaration

    def request(self, route, method='GET', body=None, headers=None):
        class Socket:
            def __init__(self, raw): self.request = io.BytesIO(raw); self.response = bytearray()
            def makefile(self, *args): return self.request
            def sendall(self, data): self.response.extend(data)
        payload = json.dumps(body).encode() if body is not None else b''
        fields = {'Host': '127.0.0.1:8783', **(headers or {})}
        if body is not None: fields['Content-Length'] = str(len(payload))
        raw = f'{method} {route} HTTP/1.0\r\n'+''.join(f'{key}: {value}\r\n' for key, value in fields.items())+'\r\n'
        socket = Socket(raw.encode()+payload)
        handler = studio_server.handler_for(ROOT, self.registry, 'fixture', 'secret')
        handler.log_message = lambda *args: None
        handler(socket, ('127.0.0.1', 1), SimpleNamespace(server_port=8783))
        return bytes(socket.response).split(b'\r\n\r\n', 1)

    def test_separate_registries_in_one_directory_keep_independent_server_addresses(self):
        other = self.registry.with_name('other.json')
        registry.register(other, self.project)
        before = {path: path.read_bytes() for path in (self.registry, other)}
        studio.write(studio_server.service_path(self.registry), {'port': 8783})
        studio.write(studio_server.service_path(other), {'port': 8784})
        self.assertEqual(studio_server.base_url(self.registry), 'http://127.0.0.1:8783')
        self.assertEqual(studio_server.base_url(other), 'http://127.0.0.1:8784')
        self.assertEqual(before, {path: path.read_bytes() for path in before})

    def test_register_does_not_select_or_approve_and_duplicate_is_idempotent(self):
        declaration = self.register()
        self.assertIsNone(deliveries.current(self.project))
        self.assertTrue(deliveries.register(self.project, declaration)['reused'])
        self.assertFalse(deliveries.release_state(self.project, deliveries.load(self.project, 'v1'))['approved'])
        altered = copy.deepcopy(declaration); altered['notes'] = 'Different choice'
        with self.assertRaisesRegex(ValueError, 'different inputs'):
            deliveries.register(self.project, altered)

    def test_atomic_current_groups_roles_and_preserves_old_exact_version(self):
        self.register('v1'); self.register('v2', ('silent',))
        first = deliveries.present(self.project, 'v1', 'Test operator')['selection']
        deliveries.present(self.project, 'v2', 'Test operator', expected=first['payload_sha256'])
        latest = deliveries.latest(self.project)
        self.assertEqual(latest['delivery']['id'], 'v2')
        self.assertEqual(list(latest['delivery']['editions']), ['silent'])
        self.assertEqual(len(list((self.project/'presentations/review').glob('*.json'))), 2)
        self.assertEqual(set(deliveries.inspect(self.project, 'v1')['editions']), {'score', 'effects', 'silent'})
        with self.assertRaises(CommandError) as error:
            deliveries.present(self.project, 'v1', 'Slow earlier run', expected=first['payload_sha256'])
        self.assertEqual(error.exception.code, 'stale_selection')
        self.assertEqual(deliveries.current(self.project)['delivery'], 'v2')

    def test_changed_movie_never_falls_back_and_cannot_be_presented(self):
        self.register('v1'); self.register('v2')
        deliveries.present(self.project, 'v2', 'Test')
        (self.project/'deliverables/v2-score.mp4').write_bytes(b'changed')
        latest = deliveries.latest(self.project)
        self.assertFalse(latest['ok']); self.assertEqual(latest['selection']['delivery'], 'v2')
        self.assertFalse(latest['delivery']['editions']['score']['available'])
        self.assertTrue(latest['delivery']['editions']['effects']['available'])
        with self.assertRaises(ValueError): deliveries.present(self.project, 'v2', 'Test')
        header, _ = self.request('/media/film/v2/score'); self.assertIn(b'409', header)

    def test_verification_movie_identity_roles_and_path_escape_are_rejected(self):
        declaration = self.declaration()
        changed = copy.deepcopy(declaration); changed['editions'][0]['verification'] = declaration['editions'][1]['verification']
        with self.assertRaisesRegex(ValueError, 'selected movie bytes'): deliveries.register(self.project, changed)
        changed = copy.deepcopy(declaration); changed['editions'][0]['file'] = '../outside.mp4'
        with self.assertRaises(ValueError): deliveries.register(self.project, changed)
        changed = copy.deepcopy(declaration); changed['editions'][0]['role'] = 'silent'
        with self.assertRaises(ValueError): deliveries.register(self.project, changed)
        changed = copy.deepcopy(declaration); changed['default_role'] = 'missing'
        with self.assertRaises(ValueError): deliveries.register(self.project, changed)
        self.assertFalse((self.project/'deliveries').exists())

    def test_changed_evidence_and_broken_working_scene_do_not_hide_intact_movie(self):
        self.register(); deliveries.present(self.project, 'v1', 'Test')
        (self.project/'scene/scene.json').write_text('broken working scene')
        (self.project/'reports/v1-score.json').unlink()
        header, body = self.request('/api/projects/film')
        self.assertIn(b'200', header)
        data = json.loads(body)
        self.assertTrue(data['current']['delivery']['editions']['score']['available'])
        self.assertFalse(data['current']['delivery']['editions']['score']['technical_evidence_current'])
        header, _ = self.request('/media/film/v1/score'); self.assertIn(b'200', header)

    def test_byte_ranges_head_suffix_and_explicit_mount_boundaries(self):
        self.register()
        raw = (self.project/'deliverables/v1-score.mp4').read_bytes()
        header, body = self.request('/media/film/v1/score', headers={'Range': 'bytes=8-23'})
        self.assertIn(b'206', header); self.assertIn(b'Accept-Ranges: bytes', header); self.assertEqual(body, raw[8:24])
        _, body = self.request('/media/film/v1/score', headers={'Range': 'bytes=-12'}); self.assertEqual(body, raw[-12:])
        header, body = self.request('/media/film/v1/score', method='HEAD')
        self.assertIn(f'Content-Length: {len(raw)}'.encode(), header); self.assertEqual(body, b'')
        for value in ['bytes=999999-', 'bytes=3-1', 'bytes=0-2,4-6', 'bytes=-0']:
            header, _ = self.request('/media/film/v1/score', headers={'Range': value}); self.assertIn(b'416', header)
        for route in ['/.git/config', '/projects/film/../../studio.py', '/media/film/v1/../../project.json', '/studio/../studio.py']:
            header, _ = self.request(route); self.assertNotIn(b'200 OK', header)
        header, _ = self.request('/api/runtime', headers={'Host': 'foreign.example:8783'}); self.assertIn(b'403', header)

    def test_feedback_is_version_bound_and_cross_origin_writes_fail(self):
        self.register(); body = {'delivery': 'v1', 'role': 'score', 'seconds': 1.2, 'note': 'Hold this gesture.', 'observer': 'Fixture viewer'}
        header, _ = self.request('/api/projects/film/feedback', 'POST', body, {'Origin': 'https://foreign.example'})
        self.assertIn(b'403', header); self.assertFalse((self.project/'feedback/movies').exists())
        header, response = self.request('/api/projects/film/feedback', 'POST', body, {'Origin': 'http://127.0.0.1:8783'})
        self.assertIn(b'201', header); data = json.loads(response)['feedback']
        self.assertEqual(data['movie']['sha256'], studio.digest(self.project/'deliverables/v1-score.mp4'))
        self.assertEqual(deliveries.feedback_list(self.project, 'v1')[0]['seconds'], 1.2)
        with self.assertRaises(ValueError): deliveries.feedback(self.project, 'v1', 'score', 2, 'No', 'Viewer')
        with self.assertRaises(ValueError): deliveries.present(self.project, 'v1', 'Viewer', channel='release')

    def test_registry_and_latest_work_from_unrelated_checkout_directory(self):
        self.register(); deliveries.present(self.project, 'v1', 'Test')
        command = [sys.executable, str(ROOT/'ambiance'), '--registry', str(self.registry), '--project', 'film', 'project', 'latest']
        result = subprocess.run(command, cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(json.loads(result.stdout)['data']['delivery']['id'], 'v1')
        other = self.root/'other'; init_project(other, None, 'Other', 'blank')
        with self.assertRaises(ValueError): registry.register(self.registry, other, 'film')
        self.project.rename(self.root/'moved')
        self.assertFalse(registry.projects(ROOT, self.registry)[0]['available'])
        registry.register(self.registry, self.root/'moved', 'film', relocate=True)
        self.assertTrue(registry.resolve(ROOT, self.registry, 'film').samefile(self.root/'moved'))

    def test_hash_cache_detects_same_length_changes_even_when_mtime_restored(self):
        self.register(); cache = deliveries.Fingerprints()
        item = deliveries.load(self.project, 'v1')['editions']['score']['movie']
        self.assertTrue(deliveries.intact(self.project, item, cache)['ok'])
        file = self.project/item['path']; before = file.stat(); raw = file.read_bytes()
        file.write_bytes(b'X'+raw[1:]); os.utime(file, ns=(before.st_atime_ns, before.st_mtime_ns))
        self.assertFalse(deliveries.intact(self.project, item, cache)['ok'])

    def test_iteration_validation_and_failure_preserve_current(self):
        self.register(); deliveries.present(self.project, 'v1', 'Test')
        recipe = {'format': 'ambiance-iteration', 'schema_version': 1, 'id': 'attempt', 'revision': 'missing', 'editions': [{'role': 'silent'}]}
        with self.assertRaises(ValueError): production.iteration(self.project, recipe, 'Test')
        saved = studio.read(production.run_file(self.project, 'attempt'))
        self.assertEqual(saved['state'], 'failed')
        self.assertIsNotNone(saved['error'])
        self.assertFalse((production.run_file(self.project, 'attempt').parent/'active.lock').exists())
        self.assertEqual(deliveries.current(self.project)['delivery'], 'v1')


if __name__ == '__main__':
    unittest.main()
