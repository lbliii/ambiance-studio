"""Public finite clock authoring, sampling, conversion and native boundaries."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ambiance_studio.timebase import frames_to_samples, samples_to_frames, round_rational
from ambiance_studio.audio_cues import alignment
spec = importlib.util.spec_from_file_location('finite_fixture', ROOT/'examples/finite-clock/create_fixture.py')
fixture = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixture)


class ClockCLI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.project = fixture.create_fixture(self.root/'project')

    def cli(self, *argv, ok=True):
        run = subprocess.run([str(ROOT/'ambiance'), '--project', str(self.project), *map(str, argv)], cwd=ROOT, capture_output=True, text=True)
        output = json.loads(run.stdout)
        self.assertEqual(run.returncode == 0, ok, output)
        return output['data'] if ok else output

    def author(self):
        self.cli('scene', 'clock', '--file', self.project/'clock.json')
        self.cli('scene', 'apply', self.project/'acting.json')

    def test_transaction_dry_run_stale_guard_and_history(self):
        path = self.project/'scene.json'; before = path.read_bytes()
        self.cli('scene', 'clock', '--file', self.project/'clock.json', '--dry-run')
        self.assertEqual(before, path.read_bytes())
        self.cli('scene', 'clock', '--file', self.project/'clock.json', '--expect-sha256', '0'*64, ok=False)
        self.assertEqual(before, path.read_bytes())
        self.cli('scene', 'clock', '--file', self.project/'clock.json', '--expect-sha256', hashlib.sha256(before).hexdigest())
        self.assertEqual((self.project/'.ambiance/scene-history'/f'{hashlib.sha256(before).hexdigest()}.json').read_bytes(), before)

    def test_public_integer_frame_and_subframe_samples_endpoint_diagnostics(self):
        self.author()
        before = (self.project/'scene.json').read_bytes()
        last = self.cli('scene', 'sample', '--frame', '59', '--context')
        end = self.cli('scene', 'sample', '--frame', '60', '--context')
        later = self.cli('scene', 'sample', '--frame', '300', '--context')
        self.assertEqual(end['states'], later['states'])
        self.assertEqual(last['states'][1]['cell'], 1); self.assertEqual(end['states'][1]['cell'], 2)
        self.assertEqual(last['clock']['requested_seconds'], {'numerator': 59, 'denominator': 24})
        self.assertIsNone(self.cli('scene', 'sample', '--time', '.001', '--context')['clock']['requested_frame'])
        self.assertIsInstance(self.cli('scene', 'sample', '--time', '0'), list)
        self.assertEqual(self.cli('scene', 'sample', '--frame', '-1'), self.cli('scene', 'sample', '--frame', '0'))
        timing = self.cli('scene', 'timing')
        self.assertEqual(timing['output_frames'], 60); self.assertEqual(timing['clock']['effective_frame'], 60)
        self.assertEqual(before, (self.project/'scene.json').read_bytes())

    def test_unknown_cycle_and_finite_export_ranges_fail_without_writes(self):
        self.author(); before = (self.project/'scene.json').read_bytes()
        fixture.write(self.root/'bad.json', {'version': 1, 'operations': [{'op': 'set', 'layer': 'root', 'values': {'local_cycle': 'missing'}}]})
        self.cli('scene', 'apply', self.root/'bad.json', ok=False)
        self.assertEqual(before, (self.project/'scene.json').read_bytes())
        for args in [('proof', '--start', '2', '--seconds', '1'), ('video', '--repeats', '2'), ('proof', '--start', '.001')]:
            self.cli('render', *args, '--out', self.root/'bad-render', ok=False)
            self.assertFalse((self.root/'bad-render').exists())

    def test_exact_audio_alignment_and_rounding_specimens(self):
        packet = json.loads((ROOT/'tests/fixtures/model-contract/clock-cues.json').read_text())
        for row in packet['rounding_cases']:
            for policy in ['floor', 'ceil', 'nearest-half-away-from-zero']:
                self.assertEqual(round_rational(dict(zip(['numerator', 'denominator'], row['value'])), policy)['value'], row[policy])
        for cue in packet['cues']:
            self.assertEqual([samples_to_frames(s, 48000, packet['fps'], 'ceil')['value'] for s in cue['shot_samples']], cue['shot_frames'])
        self.assertEqual(frames_to_samples(1, {'numerator': 30000, 'denominator': 1001}, 48000, 'floor')['residual'], {'numerator': -3, 'denominator': 5})
        links = [{'clip_id': 'clip', 'action_id': 'act', 'picture_frames': [1], 'offset_samples': 0}]
        session = {'sample_rate': 48000, 'clips': [{'id': 'clip', 'at_frame': 2000, 'frames': 2000}]}
        self.assertTrue(alignment(session, {'clock': {'fps': 24}}, links)[0]['aligned'])
        with self.assertRaisesRegex(ValueError, 'between PCM samples'):
            alignment(session, {'clock': {'fps': 29}}, links)

    @unittest.skipUnless(os.environ.get('AMBIANCE_TEST_NATIVE') == '1' and sys.platform == 'darwin', 'Set AMBIANCE_TEST_NATIVE=1 with macOS media-service access')
    def test_native_24fps_exports_only_0_through_59(self):
        self.author()
        report = self.cli('render', 'video', '--out', self.root/'movie')
        self.assertTrue(report['verification']['ok']); self.assertEqual(report['verification']['decoded_frames'], 60)
        self.assertEqual(report['final_frames'], 60)
        self.assertFalse(report['rgba_endpoint_exact'])
        self.assertEqual(report['picture_clock']['effective_frame'], 60)
        self.assertGreater(report['last_exported_to_endpoint']['rgb_mean_absolute_difference'], 0)
        contact = self.root/'movie/verification/contacts/decoded-0059.png'
        from PIL import Image
        with Image.open(contact) as image:
            r, g, b = image.convert('RGB').getpixel((240, 80))
        self.assertGreater(r, b + 80); self.assertGreater(g, b + 80)  # final cel is yellow, endpoint is blue


if __name__ == '__main__':
    unittest.main()
