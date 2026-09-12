"""Reports preserve uncertainty, immutable identities and independent dispositions."""
import copy
import unittest
from concurrent.futures import ThreadPoolExecutor

import studio
from ambiance_studio import deliveries, feedback, revisions
from ambiance_studio.cli import parser, run
from ambiance_studio.errors import CommandError
import test_deliveries as fixtures


class FeedbackTests(unittest.TestCase):
    setUp = fixtures.DeliveryTests.setUp
    declaration = fixtures.DeliveryTests.declaration
    register = fixtures.DeliveryTests.register
    request = fixtures.DeliveryTests.request

    def add(self, **kw):
        return feedback.add(self.project, 'v1', 'The curtain moves too much.', 'Reporter', scope='delivery', **kw)['feedback']

    def test_delivery_report_retry_and_original_survive_new_selection(self):
        self.register(); row = self.add(request_id='curtain')
        self.assertIsNone(row['time']); self.assertIsNone(row['observer']); self.assertNotIn('view', row)
        original = feedback._path(self.project, row['id']).read_bytes()
        self.assertEqual(row['id'], self.add(request_id='curtain')['id'])
        with self.assertRaisesRegex(ValueError, 'different content'):
            feedback.add(self.project, 'v1', 'Different', 'Reporter', scope='delivery', request_id='curtain')
        self.register('v2'); deliveries.present(self.project, 'v2', 'Operator')
        self.assertEqual(feedback.listing(self.project, 'v1')['total'], 1)
        resolution = {'outcome': 'addressed', 'delivery': 'v2', 'note': 'Held cloth in the derivative.'}
        resolved = feedback.transition(self.project, row['id'], 'resolved', 'Operator', resolution['note'], row['head'], resolution)['feedback']
        self.assertEqual(resolved['state'], 'resolved'); self.assertEqual(original, feedback._path(self.project, row['id']).read_bytes())
        self.assertFalse(deliveries.release_state(self.project, deliveries.load(self.project, 'v2'))['approved'])
        with self.assertRaises(CommandError):
            feedback.transition(self.project, row['id'], 'open', 'Operator', 'Revisit', row['head'])
        reopened = feedback.transition(self.project, row['id'], 'open', 'Operator', 'Still needs work', resolved['head'])['feedback']
        self.assertEqual(len(reopened['events']), 2)

    def test_entry_ambiguity_and_time_boundaries(self):
        self.register()
        for kw in [dict(), dict(role='score', seconds=True), dict(role='score', seconds=float('nan')),
                   dict(role='score', seconds=2), dict(role='score', start=1), dict(role='score', start=1, end=1),
                   dict(role='score', seconds=0, start=0, end=1)]:
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                feedback.add(self.project, 'v1', 'Note', 'Viewer', **kw)
        row = feedback.add(self.project, 'v1', 'Range', 'Reporter', role='score', start=0, end=2)['feedback']
        self.assertEqual(row['time']['kind'], 'range'); self.assertEqual(row['seconds'], 0)
        with self.assertRaises(ValueError): self.add(role='score')

    def test_legacy_reads_and_tamper_do_not_rewrite_history(self):
        self.register(); entry = deliveries.load(self.project, 'v1')['editions']['score']
        raw = revisions.seal(dict(format=feedback.FORMAT, schema_version=1, id='old', created_utc=deliveries.now(),
            delivery='v1', role='score', seconds=1, movie=entry['movie'], observer='Known viewer', note='Original', state='open'))
        studio.write(feedback._path(self.project, 'old'), raw)
        row = feedback.inspect(self.project, 'old'); self.assertEqual(row['observer'], 'Known viewer')
        self.assertEqual(raw, studio.read(feedback._path(self.project, 'old')))
        (self.project/entry['movie']['path']).write_bytes(b'changed')
        self.assertFalse(feedback.inspect(self.project, 'old')['integrity']['ok'])
        raw['note'] = 'tampered'; studio.write(feedback._path(self.project, 'old'), raw)
        with self.assertRaisesRegex(ValueError, 'integrity'): feedback.inspect(self.project, 'old')

    def test_event_chain_gap_and_concurrent_resolution(self):
        self.register(); row = self.add(); resolution = {'outcome': 'withdrawn', 'note': 'Direction changed'}
        def update():
            try: return feedback.transition(self.project, row['id'], 'resolved', 'Operator', 'Direction changed', row['head'], resolution)['ok']
            except (ValueError, CommandError): return False
        with ThreadPoolExecutor(2) as pool: results = list(pool.map(lambda _: update(), range(2)))
        self.assertEqual(sum(results), 1)
        events = list((self.project/'feedback/events'/row['id']).glob('*.json'))
        data = studio.read(events[0]); data.pop('payload_sha256'); data['sequence'] = 2; studio.write(events[0], revisions.seal(data))
        with self.assertRaisesRegex(ValueError, 'chain'): feedback.inspect(self.project, row['id'])

    def test_cli_and_http_untimed_and_resolution(self):
        self.register()
        row = run(parser().parse_args(['--project', str(self.project), 'feedback', 'add', 'v1', '--scope', 'delivery', '--note', 'Quiet cloth', '--by', 'Reporter']))['feedback']
        self.assertIsNone(row['time'])
        header, _ = self.request('/api/projects/film/feedback', 'POST', {'delivery': 'v1', 'scope': 'delivery', 'note': 'Another', 'reporter': 'Reporter'}, {'Origin': 'http://127.0.0.1:8783'})
        self.assertIn(b'201', header)
        header, _ = self.request('/api/projects/film/feedback/'+row['id']+'/resolve', 'POST', {'reporter': 'Reporter', 'note': 'Withdrawn', 'expected': row['head'], 'resolution': {'outcome': 'withdrawn', 'note': 'Withdrawn'}}, {'Origin': 'http://127.0.0.1:8783'})
        self.assertIn(b'200', header)
        self.assertEqual(feedback.listing(self.project, state='open')['total'], 1)

    def test_import_source_and_pagination(self):
        self.register(); source = self.project/'feedback/curtain.md'; source.write_text('Original report')
        args = parser().parse_args(['--project', str(self.project), 'feedback', 'add', 'v1', '--scope', 'delivery', '--note-file', str(source), '--by', 'Reporter'])
        row = run(args)['feedback']; self.assertEqual(row['references'][0]['sha256'], studio.digest(source))
        self.add(); self.assertEqual(feedback.listing(self.project, limit=1)['next_offset'], 1)
        source.write_text('changed'); self.assertFalse(feedback.inspect(self.project, row['id'])['integrity']['ok'])


if __name__ == '__main__': unittest.main()
