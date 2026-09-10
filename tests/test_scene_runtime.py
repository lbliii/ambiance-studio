"""Evaluator failures must remain structured CLI errors, never tracebacks."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ambiance_studio import cli, scene_runtime
from ambiance_studio.errors import CommandError


class SceneRuntimeTests(unittest.TestCase):
    def test_malformed_responses_report_runtime_failure_through_cli(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)/'project'
            cli.init_project(project, None, None, 'blank')
            for stdout in ['not json', 'null', '[]', '{"ok": "yes"}', '{"ok": true}', '{"ok": false}']:
                with self.subTest(stdout=stdout):
                    output = io.StringIO()
                    response = subprocess.CompletedProcess([], 0, stdout, '')
                    with patch.object(scene_runtime.subprocess, 'run', return_value=response), contextlib.redirect_stdout(output):
                        code = cli.main(['--project', str(project), 'scene', 'inspect'])
                    self.assertEqual(code, 3)
                    self.assertEqual(json.loads(output.getvalue())['error']['code'], 'runtime_error')

    def test_evaluator_rejections_keep_invalid_input_classification(self):
        response = subprocess.CompletedProcess([], 2, '{"ok": false, "error": "Unknown layer"}', '')
        with patch.object(scene_runtime.subprocess, 'run', return_value=response):
            with self.assertRaises(CommandError) as error:
                scene_runtime.scene_bridge('set', {}, {}, {})
        self.assertEqual(error.exception.code, 'invalid_input')
        self.assertEqual(error.exception.exit_code, 2)

    def test_launch_failure_or_unsuccessful_exit_is_runtime_error(self):
        cases = [{'side_effect': OSError('executable disappeared')},
                 {'return_value': subprocess.CompletedProcess([], 1, '{"ok": true, "data": {}}', 'crashed')}]
        for case in cases:
            with self.subTest(case=case), patch.object(scene_runtime.subprocess, 'run', **case):
                with self.assertRaises(CommandError) as error:
                    scene_runtime.scene_bridge('inspect', {}, {}, {})
                self.assertEqual(error.exception.code, 'runtime_error')
                self.assertEqual(error.exception.exit_code, 3)


if __name__ == '__main__':
    unittest.main(verbosity=2)
