"""Split native source closure must invalidate builds and recorded provenance."""
import importlib
import os
import sys
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from ambiance_studio import native_sources, rendering
from ambiance_studio.errors import CommandError


class NativeSourceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.sources = self.root / 'sources'
        self.sources.mkdir()
        for name in ['media.m', 'encode.m', 'media_common.h']:
            (self.sources / name).write_text('// ' + name)

    def test_manifest_covers_headers_additions_removals_and_names(self):
        before = native_sources.source_identity(self.sources)
        self.assertEqual(set(before['files']), {'media.m', 'encode.m', 'media_common.h'})
        (self.sources / 'README.md').write_text('Not a compiler input')
        self.assertEqual(native_sources.source_identity(self.sources), before)
        header = self.sources / 'media_common.h'
        header.write_text('// changed declaration')
        changed = native_sources.source_identity(self.sources)
        self.assertNotEqual(before['sha256'], changed['sha256'])
        header.rename(self.sources / 'renamed.h')
        renamed = native_sources.source_identity(self.sources)
        self.assertNotEqual(changed['sha256'], renamed['sha256'])
        (self.sources / 'renamed.h').unlink()
        self.assertNotEqual(renamed['sha256'], native_sources.source_identity(self.sources)['sha256'])
        self.assertEqual([p.name for p in native_sources.compilation_sources(self.sources)], ['encode.m', 'media.m'])

    def test_compiler_uses_all_units_and_header_changes_get_a_fresh_cache(self):
        # Patch the actual owner so the public compatibility import is exercised too.
        backend = importlib.import_module(rendering._native_binary.__module__)
        builds = []
        def compile(command, **kwargs):
            if '--version' in command:
                return subprocess.CompletedProcess(command, 0, b'fixture compiler', b'')
            builds.append(command)
            Path(command[command.index('-o') + 1]).write_bytes(b'compiled fixture')
            return subprocess.CompletedProcess(command, 0, '', '')
        with patch.object(backend, 'NATIVE_SOURCE', self.sources / 'media.m'), \
             patch.object(backend.platform, 'system', return_value='Darwin'), \
             patch.object(backend.platform, 'platform', return_value='fixture-platform'), \
             patch.object(backend.shutil, 'which', return_value='/fixture/xcrun'), \
             patch.object(backend.subprocess, 'run', side_effect=compile), \
             patch.dict(backend.os.environ, {}, clear=True):
            first = rendering._native_binary(self.root)
            self.assertEqual(rendering._native_binary(self.root), first)
            self.assertEqual(len(builds), 1)
            self.assertEqual([Path(v).name for v in builds[0] if str(v).endswith('.m')], ['encode.m', 'media.m'])
            (self.sources / 'media_common.h').write_text('// revised header')
            second = rendering._native_binary(self.root)
            self.assertNotEqual(first, second)
            self.assertTrue(first.is_file())
            self.assertEqual(len(builds), 2)
            (self.sources / 'encode.m').write_text('// broken source')
            with patch.object(backend.subprocess, 'run', side_effect=[
                subprocess.CompletedProcess([], 0, b'fixture compiler', b''),
                subprocess.CompletedProcess([], 1, '', 'injected compile failure'),
            ]):
                with self.assertRaisesRegex(CommandError, 'injected compile failure'):
                    rendering._native_binary(self.root)
            self.assertEqual(first.read_bytes(), b'compiled fixture')
            self.assertEqual(second.read_bytes(), b'compiled fixture')


@unittest.skipUnless(os.environ.get('AMBIANCE_TEST_NATIVE') == '1' and sys.platform == 'darwin',
                     'Set AMBIANCE_TEST_NATIVE=1 with macOS media-service access')
class NativeCommandTests(unittest.TestCase):
    def test_split_commands_decode_pcm_and_refuse_partial_raw_streams(self):
        import json
        import wave
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = rendering._native_binary(root)
            picture = root / 'picture.mp4'
            args = [str(binary), 'encode', str(picture), '16', '16', '2', '2', '100000', 'rgba', '2']
            raw = bytes([64, 96, 128, 255]) * (16 * 16 * 2)
            encoded = subprocess.run(args, input=raw, capture_output=True, timeout=30)
            self.assertEqual(encoded.returncode, 0, encoded.stderr)
            self.assertEqual(json.loads(encoded.stdout)['frames'], 2)
            before = picture.read_bytes()
            duplicate = subprocess.run(args, input=raw, capture_output=True, timeout=30)
            self.assertNotEqual(duplicate.returncode, 0)
            self.assertIn(b'Refusing to overwrite', duplicate.stderr)
            self.assertEqual(before, picture.read_bytes())
            args[2] = str(root / 'partial.mp4')
            partial = subprocess.run(args, input=raw[:32], capture_output=True, timeout=30)
            self.assertNotEqual(partial.returncode, 0)
            self.assertIn(b'Incomplete RGBA stream', partial.stderr)
            self.assertFalse(partial.stdout)
            audio = root / 'source.wav'
            with wave.open(str(audio), 'wb') as output:
                output.setnchannels(2); output.setsampwidth(2); output.setframerate(48000)
                output.writeframes(b'\0' * 48000 * 4)
            compressed = root / 'audio.m4a'
            result = rendering._json_command([binary, 'audio', audio, compressed])
            self.assertEqual(result['codec'], 'AAC')
            inspection = rendering._json_command([binary, 'inspect', compressed])
            self.assertAlmostEqual(inspection['duration'], 1)
            packets = rendering._json_command([binary, 'packets', compressed])
            self.assertGreater(packets['count'], 0)
            self.assertLessEqual(len(packets['packets']), 6)
            probe = rendering._json_command([binary, 'probe-picture', picture])
            self.assertTrue(probe['supported_cfr_h264'])
            self.assertEqual(probe['frames'], 2)


if __name__ == '__main__':
    unittest.main()
