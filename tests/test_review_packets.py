import importlib.util
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

import studio
from ambiance_studio import review_packets, revisions, deliveries, rendering, run_control, production

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('midnight_replay', ROOT/'examples/midnight-production/replay.py')
example = importlib.util.module_from_spec(spec); spec.loader.exec_module(example)


class PacketTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.project = example.fixture(Path(self.tmp.name)/'film')

    def test_atomic_init_rejects_missing_pcm_and_no_partial_bundle_on_failure(self):
        request = example.packet_request(); out = self.project/'recipes/packet'
        original = studio.write
        def fail(path, value):
            if Path(path).name == 'packet-request.json': raise OSError('simulated interruption')
            return original(path, value)
        with patch('ambiance_studio.review_packets.studio.write', side_effect=fail):
            with self.assertRaisesRegex(OSError, 'interruption'): review_packets.initialize(self.project, request, out)
        self.assertFalse(out.exists()); self.assertFalse(revisions.manifest_path(self.project, 'first-review').exists())
        (self.project/'audio/master.wav').unlink()
        with self.assertRaises(Exception): review_packets.initialize(self.project, request, out)
        self.assertFalse(out.exists())

    @unittest.skipUnless(os.environ.get('AMBIANCE_TEST_NATIVE') == '1' and sys.platform == 'darwin', 'Requires native media services')
    def test_native_packet_resume_preserves_selection_and_detects_tampering(self):
        request = review_packets.initialize(self.project, example.packet_request(), self.project/'recipes/packet')
        token = deliveries.selection_token(self.project)
        result = review_packets.execute(self.project, request['request'], 'Native packet fixture')
        self.assertEqual(deliveries.selection_token(self.project), token)
        self.assertEqual(len(review_packets.verify(self.project, result['packet'])['movies']), 2)
        self.assertTrue(review_packets.execute(self.project, request['request'], 'Native packet fixture')['reused'])
        movie = Path(result['movies'][0]); movie.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'artifact changed'): review_packets.verify(self.project, result['packet'])

    @unittest.skipUnless(os.environ.get('AMBIANCE_TEST_NATIVE') == '1' and sys.platform == 'darwin', 'Requires native media services')
    def test_native_recovery_at_render_and_verification_boundaries(self):
        # Inject cooperative cancellation at two real media boundaries. The render
        # interruption follows an actual completed native call; verification stops
        # before the next decode. Process termination itself has subprocess tests.
        for phase in ['render', 'verify']:
            request = review_packets.initialize(self.project, example.packet_request('cancel-'+phase), self.project/'recipes'/phase)
            original = rendering._json_command; fired = False
            def interrupt(command, *args, **kwargs):
                nonlocal fired
                is_renderer = len(command) > 1 and str(command[1]).endswith('render-scene.mjs')
                is_verify = len(command) > 1 and str(command[1]) == 'verify'
                if not fired and phase == 'verify' and is_verify:
                    fired = True; raise KeyboardInterrupt('Native verification boundary fixture')
                result = original(command, *args, **kwargs)
                if not fired and phase == 'render' and is_renderer:
                    fired = True; raise KeyboardInterrupt('Native render boundary fixture')
                return result
            with patch('ambiance_studio.rendering._json_command', side_effect=interrupt):
                with self.assertRaises(KeyboardInterrupt): review_packets.execute(self.project, request['request'], 'Native interruption fixture')
            self.assertTrue(fired)
            state = studio.read(production.run_file(self.project, 'cancel-'+phase))
            self.assertEqual(state['state'], 'interrupted'); self.assertFalse(run_control.live_children(self.project, state))
            self.assertIsNone(deliveries.current(self.project))
            self.assertTrue(review_packets.execute(self.project, request['request'], 'Native interruption fixture')['ok'])
            self.assertIsNone(deliveries.current(self.project))

    @unittest.skipUnless(os.environ.get('AMBIANCE_TEST_NATIVE') == '1' and sys.platform == 'darwin', 'Requires native media services')
    def test_owned_cancellation_requested_during_native_phases_and_resume(self):
        for phase in ['render-encode', 'media-verify', 'media-compose']:
            id = 'owned-'+phase; initialized = review_packets.initialize(self.project, example.packet_request(id), self.project/'recipes'/id)
            command = [str(ROOT/'ambiance'), '--project', str(self.project), 'review', 'packet', 'run', initialized['request'], '--by', 'Native cancellation fixture']
            with tempfile.TemporaryFile(mode='w+') as output:
                child = subprocess.Popen(command, cwd=ROOT, stdout=output, stderr=output)
                try:
                    deadline = time.monotonic()+45; observed = None
                    progress_path = self.project/'runs'/id/'progress.json'
                    while child.poll() is None and time.monotonic() < deadline:
                        if progress_path.exists():
                            progress = studio.read(progress_path)
                            if progress.get('phase') == phase:
                                observed = progress; break
                        time.sleep(.005)
                    self.assertIsNotNone(observed, 'Native phase was not observed: '+phase)
                    before = studio.read(production.run_file(self.project, id))
                    run_control.cancel(self.project, id, before['run_uuid'])
                    child.wait(timeout=15); self.assertEqual(child.returncode, 130)
                    stopped = studio.read(production.run_file(self.project, id)); self.assertEqual(stopped['state'], 'interrupted')
                    self.assertFalse(run_control.live_children(self.project, stopped))
                    self.assertTrue(review_packets.execute(self.project, initialized['request'], 'Native cancellation fixture')['ok'])
                    after = studio.read(production.run_file(self.project, id))
                    for name, step in before['steps'].items(): self.assertEqual(after['steps'][name]['outputs'], step['outputs'])
                    self.assertIsNone(deliveries.current(self.project))
                finally:
                    if child.poll() is None: child.terminate(); child.wait(timeout=15)


if __name__ == '__main__': unittest.main()
