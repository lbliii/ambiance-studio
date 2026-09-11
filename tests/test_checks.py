"""Injected failures exercise retained diagnostics independently of the test suite."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

from ambiance_studio import checks


class CheckArtifactsTests(unittest.TestCase):
    def test_invalid_utf8_and_multibyte_tails_remain_valid_and_byte_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for expression in ['bytes([255])*40000', "'雪'.encode('utf-8')*20000"]:
                result = checks.execute('CI-UTF8', [sys.executable, '-c', 'import os;os.write(1,' + expression + ')'], root)
                log = result['logs']['stdout']
                raw = (root / log['path']).read_bytes()
                self.assertLessEqual(len(raw), checks.LOG_LIMIT)
                self.assertTrue(raw.decode('utf-8'))
                self.assertTrue(log['truncated'])

    def test_real_failure_has_stable_id_bounded_scrubbed_logs_and_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            row = checks.execute('CI-INJECTED', [sys.executable, '-c',
                'import sys; print("x" * 100000); print(' + repr(str(Path.home() / 'private-film/scene.json')) + ', file=sys.stderr); sys.exit(7)'], root)
            self.assertFalse(row['ok']); self.assertEqual(row['exit_code'], 7)
            self.assertEqual(row['id'], 'CI-INJECTED')
            self.assertTrue(row['logs']['stdout']['truncated'])
            for entry in row['logs'].values():
                path = root / entry['path']
                self.assertLessEqual(path.stat().st_size, checks.LOG_LIMIT)
                self.assertEqual(checks.digest(path), entry['sha256'])
                self.assertNotIn(str(Path.home()), path.read_text())

    def test_timed_out_process_fails_and_retains_diagnostics(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = checks.execute('CI-TIMEOUT', [sys.executable, '-c', 'import time; time.sleep(20)'], Path(tmp), timeout=.1)
            self.assertTrue(result['timed_out']); self.assertFalse(result['ok'])
            self.assertTrue((Path(tmp) / result['logs']['stderr']['path']).is_file())

    def test_native_required_cannot_succeed_as_unavailable_or_skip(self):
        result = checks.native_requirement(True, {'final_video_export': False, 'media_verify': False})
        self.assertFalse(result['ok']); self.assertEqual(result['issue_id'], 'CI-NATIVE-UNAVAILABLE')
        self.assertIn('macOS', result['next_action'])
        self.assertEqual(checks.native_requirement(False, {})['state'], 'not-required')
        available = checks.native_requirement(True, {'final_video_export': True, 'media_verify': True})
        self.assertTrue(available['ok']); self.assertFalse(available['executed'])

    def test_real_unittest_failure_error_skip_and_junit_retain_test_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'test_injected.py').write_text('''import unittest
class Injected(unittest.TestCase):
 def test_failure(self): self.assertEqual(1, 2)
 def test_error(self): raise RuntimeError('injected encoder failure')
 @unittest.skip('unavailable test service')
 def test_skip(self): pass
''')
            result = subprocess.run([sys.executable, str(checks.ROOT / 'tools/unittest_report.py'), '--directory', str(root), '--out', str(root / 'cases.json')], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            report = json.loads((root / 'cases.json').read_text())
            self.assertEqual(report['tests_run'], 3); self.assertEqual(report['skipped'], 1)
            self.assertEqual({c['status'] for c in report['cases']}, {'failed', 'error', 'skipped'})
            self.assertTrue(all(c['id'].startswith('test_injected.Injected.') for c in report['cases']))
            checks.junit(report, root / 'junit.xml')
            xml = ET.parse(root / 'junit.xml')
            self.assertEqual(len(xml.findall('.//failure')), 2)
            self.assertEqual(len(xml.findall('.//skipped')), 1)

class BundleTests(unittest.TestCase):
    def test_combined_bundle_keeps_named_recovery_evidence_and_excludes_unlisted_media(self):
        from tools.ci_bundle import bundle
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); run = root / 'checks'; replay = root / 'replay'; combined = root / 'combined'
            run.mkdir(); replay.mkdir(); combined.mkdir()
            (combined / 'combined.json').write_text('{"state":"failed"}')
            attempt = combined / 'paired-recovery/attempt-001'
            attempt.mkdir(parents=True)
            (attempt / 'recovery.json').write_text('{"ok":false}')
            (attempt / 'private-film.mp4').write_bytes(b'excluded')
            result = bundle(run, replay, root / 'upload', combined)
            self.assertEqual(result['files'], 2)
            self.assertTrue((root / 'upload/combined/paired-recovery/attempt-001/recovery.json').is_file())
            self.assertFalse((root / 'upload/combined/paired-recovery/attempt-001/private-film.mp4').exists())
            (attempt / 'recovery.json').unlink()
            (attempt / 'recovery.json').symlink_to(attempt / 'private-film.mp4')
            with self.assertRaisesRegex(ValueError, 'Symlink'):
                bundle(run, replay, root / 'escaped', combined)

    def test_allowlist_ignores_private_project_and_rejects_symlinks_and_oversize(self):
        from tools.ci_bundle import bundle, MAX_FILE_BYTES
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); run = root / 'checks'; replay = root / 'replay'
            run.mkdir(); replay.mkdir()
            (run / 'run.json').write_text('{"ok":false}')
            (replay / 'private-film.mp4').write_bytes(b'not an upload input')
            (replay / 'replay.json').write_text('{"kind":"artifact-only"}')
            result = bundle(run, replay, root / 'upload')
            self.assertEqual(result['files'], 2)
            self.assertFalse((root / 'upload/replay/private-film.mp4').exists())
            (run / 'python.json').symlink_to(replay / 'private-film.mp4')
            with self.assertRaisesRegex(ValueError, 'Symlink'):
                bundle(run, replay, root / 'bad-symlink')
            self.assertFalse((root / 'bad-symlink').exists())
            (run / 'python.json').unlink()
            (run / 'python.json').write_bytes(b'x' * (MAX_FILE_BYTES + 1))
            with self.assertRaisesRegex(ValueError, 'file limit'):
                bundle(run, replay, root / 'bad-size')
            self.assertFalse((root / 'bad-size').exists())
