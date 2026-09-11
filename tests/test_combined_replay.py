"""Recovery failures must remain attributable without rerunning completed fixtures."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'examples/workflow-replay/combined.py'
spec = importlib.util.spec_from_file_location('combined_replay', SCRIPT)
combined = importlib.util.module_from_spec(spec)
spec.loader.exec_module(combined)


class CombinedReplayTests(unittest.TestCase):
    def test_failed_attempt_is_preserved_and_completed_output_cannot_be_reused_after_tamper(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'fixture.py').write_text('''import json,sys
from pathlib import Path
out=Path(sys.argv[1]);out.mkdir()
(out/'proof.txt').write_text('original')
print(json.dumps({'ok':out.name!='attempt-001'}))
sys.exit(1 if out.name=='attempt-001' else 0)
''')
            features = {'fixture': {'script': 'fixture.py', 'engine': 'python', 'position': True}}
            identity = {'commit': 'synthetic', 'tracked_tree_sha256': 'unchanged'}
            with patch.object(combined, 'ROOT', root), patch.object(combined, 'FEATURES', features), patch.object(combined, 'source_identity', return_value=identity):
                out = root / 'output'
                with self.assertRaisesRegex(ValueError, 'attempt 1 failed'):
                    combined.replay(out, ['fixture'])
                self.assertTrue((out / 'fixture/attempt-001/proof.txt').is_file())
                result = combined.replay(out, ['fixture'], resume=True)
                self.assertTrue(result['ok'])
                state = json.loads((out / 'combined.json').read_text())
                self.assertEqual(state['attempts']['fixture'], 2)
                self.assertNotIn('error', state)
                self.assertFalse(state['agent_trial_performed'])
                combined.replay(out, ['fixture'], resume=True)
                self.assertFalse((out / 'fixture/attempt-003').exists())
                (out / 'fixture/attempt-002/proof.txt').write_text('changed')
                with self.assertRaisesRegex(ValueError, 'Completed fixture changed'):
                    combined.replay(out, ['fixture'], resume=True)

    def test_unavailable_native_case_is_explicit_and_escaped_resume_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = combined.replay(root / 'output', ['paired-recovery'])
            self.assertEqual(result['cases'], {'paired-recovery': 'not-run'})
            self.assertIn('paired-recovery', result['unperformed'])
            with self.assertRaisesRegex(ValueError, 'escaped file'):
                combined.checked_file(root, '../outside')
            (root / 'target').write_text('paint')
            (root / 'alias').symlink_to(root / 'target')
            with self.assertRaisesRegex(ValueError, 'escaped file'):
                combined.checked_file(root, 'alias')

    def test_fixture_timeout_is_failure(self):
        with self.assertRaises(subprocess.TimeoutExpired) as caught:
            combined.invoke([sys.executable, '-c', 'import time;print("started",flush=True);time.sleep(20)'], timeout=.1)
        self.assertIn('started', caught.exception.stdout)
