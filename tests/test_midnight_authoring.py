import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import studio
from ambiance_studio import planning, production_queries, iteration_recipes, inventory_authoring
from ambiance_studio.cli import init_project, parser, run
from ambiance_studio.errors import CommandError
import test_deliveries as fixtures


class QueryTests(unittest.TestCase):
    setUp = fixtures.DeliveryTests.setUp
    declaration = fixtures.DeliveryTests.declaration
    register = fixtures.DeliveryTests.register

    def test_large_reports_are_not_returned_and_open_feedback_remains_actionable(self):
        from ambiance_studio import production, feedback, deliveries
        self.register(); deliveries.present(self.project, 'v1', 'Operator')
        feedback.add(self.project, 'v1', 'Less cloth movement', 'Reporter', scope='delivery')
        data = production.overview(self.project, 'film', 'http://localhost:8783', details=True)
        data['runs'] = [dict(id=f'run-{i}', state='complete', steps={'render': {'samples': ['x'*1000]*1000}}) for i in range(100)]
        result = production_queries.summarize(self.project, data)
        self.assertLess(len(json.dumps({'ok': True, 'schema_version': 1, 'command': 'project overview', 'data': result}, indent=2)), 16384)
        self.assertNotIn('samples', json.dumps(result)); self.assertEqual(len(result['runs']), 5)
        self.assertTrue(any(row['kind'] == 'feedback' for row in result['next_work']['items']))
        self.assertEqual(result['current']['delivery']['editions']['score']['duration_seconds'], 2)

    def test_absent_or_unverifiable_owner_never_appears_active(self):
        for error, expected in [(ProcessLookupError(), 'interrupted'), (PermissionError(), 'unknown')]:
            with patch('ambiance_studio.production_queries.os.kill', side_effect=error):
                self.assertEqual(production_queries.run_summary({'id': 'x', 'state': 'running', 'pid': 99999})['effective_state'], expected)
        with patch('ambiance_studio.production_queries.os.kill'):
            self.assertEqual(production_queries.run_summary({'id': 'x', 'state': 'running', 'pid': 123})['effective_state'], 'unknown')

    def test_run_records_retain_handles_without_duplicating_media_samples(self):
        result = {'ok': True, 'output': 'picture.mp4', 'report': 'render-report.json',
                  'edition': {'id': 'proof', 'receipt': 'edition.json'},
                  'verification': {'ok': True, 'report': 'media-report.json', 'samples': ['large']*100000}}
        compact = production_queries.saved_step_result(result)
        self.assertEqual(compact['edition'], result['edition']); self.assertEqual(compact['verification']['report'], 'media-report.json')
        self.assertNotIn('samples', json.dumps(compact)); self.assertLess(len(json.dumps(compact)), 1024)


class AuthoringTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.project = Path(self.tmp.name)/'film'
        init_project(self.project, None, 'Fixture', 'blank', 'dual')

    def command(self, *argv):
        return run(parser().parse_args(['--project', str(self.project), *argv]))

    def test_clock_transaction_dry_run_invalid_batch_and_restore(self):
        path = self.project/'scene/scene.json'; original = path.read_bytes(); digest = studio.digest(path)
        dry = self.command('scene', 'clock', '--loop-seconds', '24', '--dry-run', '--expect-sha256', digest)
        self.assertEqual(dry['scene']['canvas']['loop_seconds'], 24); self.assertEqual(path.read_bytes(), original)
        self.assertFalse((self.project/'.ambiance/scene-history').exists())
        with self.assertRaises(CommandError): self.command('scene', 'clock', '--loop-seconds', '-1')
        result = self.command('scene', 'clock', '--loop-seconds', '24', '--expect-sha256', digest)
        self.assertEqual(studio.read(path)['canvas']['loop_seconds'], 24)
        with self.assertRaises(CommandError): self.command('scene', 'clock', '--loop-seconds', '16', '--expect-sha256', digest)
        self.command('scene', 'restore', result['previous_sha256']); self.assertEqual(studio.read(path)['canvas']['loop_seconds'], 16)

    def test_fulfillment_checks_real_files_and_keeps_scope_and_reviews(self):
        path = self.project/'plans/asset-inventory.json'; source = self.project/'reference/source.txt'; source.parent.mkdir(exist_ok=True); source.write_text('source')
        studio.write(path, {'version': 1, 'items': [{'id': 'cloth', 'required': True, 'required_parts': [{'id': 'cutout', 'stage': 'planned', 'target_stage': 'prepared', 'review': {'state': 'pending'}}]}]})
        digest = studio.digest(path); before = path.read_bytes()
        request = {'format': 'ambiance-fulfillment', 'schema_version': 1, 'parts': [{'item': 'cloth', 'part': 'cutout', 'values': {'stage': 'prepared', 'files': [{'file': 'reference/source.txt', 'sha256': studio.digest(source)}]}}]}
        inventory_authoring.fulfill(self.project, request, digest, True); self.assertEqual(path.read_bytes(), before)
        result = inventory_authoring.fulfill(self.project, request, digest)
        self.assertEqual(Path(result['snapshot']).read_bytes(), before)
        self.assertTrue(planning.inspect(self.project)['items'][0]['complete_for_scope'])
        self.assertEqual(studio.read(path)['items'][0]['required_parts'][0]['review']['state'], 'pending')
        with self.assertRaises(CommandError): inventory_authoring.fulfill(self.project, request, digest)
        request['parts'][0]['values']['required'] = False
        with self.assertRaises(ValueError): inventory_authoring.fulfill(self.project, request, studio.digest(path))

    def test_initializer_is_atomic_explicit_and_does_not_capture(self):
        request = dict(format='ambiance-iteration-request', schema_version=1, id='draft', revision='draft', views=['portrait', 'landscape'],
                       default={'view': 'portrait', 'role': 'silent'}, editions=[{'role': 'silent'}], scope='proof', long_edge=64)
        out = self.project/'recipes/draft'; result = iteration_recipes.initialize(self.project, request, out)
        self.assertTrue(Path(result['recipe']).is_file()); self.assertFalse((self.project/'revisions/draft').exists())
        self.assertFalse((self.project/'presentations').exists())
        with self.assertRaises(ValueError): iteration_recipes.initialize(self.project, request, out)
        request['editions'] = [{'role': 'score'}]
        with self.assertRaises(ValueError): iteration_recipes.initialize(self.project, request, self.project/'recipes/bad')
        self.assertFalse((self.project/'recipes/bad').exists())


if __name__ == '__main__': unittest.main()
