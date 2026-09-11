"""Real native CLI interruption, retained editions and resumed paired delivery."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from ambiance_studio.checks import ROOT


@unittest.skipUnless(os.environ.get('AMBIANCE_TEST_NATIVE') == '1' and sys.platform == 'darwin', 'Requires actual macOS native media services')
class NativeCLIReplayTests(unittest.TestCase):
    def test_process_interruption_preserves_first_view_and_resumes_only_second(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / 'recovery'
            p = subprocess.run([sys.executable, str(ROOT / 'examples/workflow-replay/paired_delivery.py'), '--out', str(directory)], capture_output=True, text=True, timeout=180)
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            report = json.loads((directory / 'recovery.json').read_text())
            self.assertTrue(report['ok'])
            self.assertEqual(report['interruption']['exit_code'], 130)
            self.assertFalse(report['interruption']['selected_incomplete_pair'])
            self.assertTrue(report['resume']['retained_portrait_unchanged'])
            self.assertEqual(report['resume']['encode_attempts'], 3)
            self.assertEqual(set(report['resume']['entries']), {'portrait.silent', 'landscape.silent'})
            self.assertFalse(report['agent_trial_performed'])
