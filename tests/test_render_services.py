"""Service boundary regressions: request preflight, transport and provenance."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ambiance_studio import media_inputs, media_verification, native_media, render_plan, rendering, run_control
from ambiance_studio.errors import CommandError
from test_rendering import parse


class RenderPlanTests(unittest.TestCase):
    def test_video_planning_captures_pcm_without_building_or_rendering(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory).resolve()
            scene = project/'cut.json'
            scene.write_text(json.dumps({'canvas': {'width': 64, 'height': 96, 'fps': 6, 'loop_seconds': 2}, 'layers': []}))
            audio = project/'score.wav'
            with wave.open(str(audio), 'wb') as wav:
                wav.setnchannels(2); wav.setsampwidth(2); wav.setframerate(48000)
                wav.writeframes(b'\0' * 48000 * 4 * 4)
            pcm = audio.read_bytes()
            out = project/'nested/video'
            args = parse('render', 'video', '--audio', audio, '--repeats', 2, '--bitrate', 5000, '--out', out)
            context = {'scene': scene, 'catalog': project/'catalog.json'}
            with patch.object(render_plan, 'render_context', return_value=context), \
                 patch.object(native_media, 'native_binary') as native, \
                 patch.object(native_media, 'json_command') as process:
                plan = render_plan.plan_render(args, project)
            native.assert_not_called(); process.assert_not_called()
            self.assertFalse(out.parent.exists())
            self.assertEqual(plan.request, {
                'project': str(project), 'out': str(out), 'mode': 'video', 'width': 64, 'height': 96,
                'start': 0, 'seconds': 2, 'disable': [], 'supersample': 1,
                'scene_path': str(scene), 'catalog_path': str(project/'catalog.json'), 'bitrate': 5000,
            })
            self.assertEqual((plan.fps, plan.frames, plan.repeats), (6, 12, 2))
            audio.write_bytes(b'changed after capture')
            self.assertEqual(plan.audio_bytes, pcm)

    def test_legacy_imports_resolve_to_public_owners(self):
        self.assertIs(rendering.capabilities, native_media.capabilities)
        self.assertIs(rendering.requested_contacts, media_verification.requested_contacts)
        self.assertIs(rendering._native_binary, native_media.native_binary)
        self.assertIs(rendering._json_command, native_media.json_command)
        self.assertIs(rendering._pcm_bytes, media_inputs.pcm_bytes)
        with patch.object(rendering, 'verify_media', return_value={'ok': True}) as verify:
            self.assertEqual(rendering._verify(Path('/unused'), 'binary', 'movie', 'out', 1, 2, 3, 4, 0, 4), {'ok': True})
        verify.assert_called_once_with('binary', 'movie', 'out', 1, 2, 3, 4, 0, 4)


class NativeServiceTests(unittest.TestCase):
    def test_transport_preserves_json_process_tracking_and_failure_contract(self):
        tracker = Mock()
        token = run_control.ACTIVE.set(tracker)
        self.addCleanup(run_control.ACTIVE.reset, token)
        command = [Path('/binary with spaces'), 'verify', 12]
        request = {'path': 'paint é', 'nested': [1, True, None]}
        failure = subprocess.CompletedProcess([], 1, '{"ok":false,"error":"decode failed"}', '')
        with patch.object(run_control, 'execute', return_value=failure) as execute:
            with self.assertRaisesRegex(CommandError, 'decode failed') as caught:
                native_media.json_command(command, request)
            self.assertEqual((caught.exception.code, caught.exception.exit_code), ('runtime_error', 3))
            self.assertFalse(native_media.json_command(command, request, allow_check_failure=True)['ok'])
            self.assertEqual(execute.call_args.args, ([str(value) for value in command], json.dumps(request, allow_nan=False)))
        tracker.update.assert_called_with({'phase': 'media-verify'})
        with patch.object(run_control, 'execute', return_value=subprocess.CompletedProcess([], 1, '', 'process died')):
            with self.assertRaisesRegex(CommandError, 'process died'):
                native_media.json_command(command, allow_check_failure=True)
        with patch.object(run_control, 'execute') as execute:
            with self.assertRaises(ValueError): native_media.json_command(command, {'time': float('nan')})
            execute.assert_not_called()

    def test_native_build_reuses_exact_source_platform_compiler_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            source = project/'source.m'; source.write_bytes(b'fixture native source')
            builds = []
            def compiler(command, **kwargs):
                if command[-1] == '--version':
                    return SimpleNamespace(stdout=b'fixture clang')
                builds.append(command)
                Path(command[-1]).write_bytes(b'fixture binary')
                return SimpleNamespace(returncode=0, stderr='')
            with patch.dict(os.environ, {'AMBIANCE_MEDIA_BINARY': ''}), \
                 patch.object(native_media, 'NATIVE_SOURCE', source), \
                 patch.object(native_media.platform, 'system', return_value='Darwin'), \
                 patch.object(native_media.platform, 'platform', return_value='fixture macOS'), \
                 patch.object(native_media.shutil, 'which', return_value='/fixture/xcrun'), \
                 patch.object(native_media.subprocess, 'run', side_effect=compiler):
                binary = native_media.native_binary(project)
                identity = hashlib.sha256(source.read_bytes()+b'fixture macOS'+b'fixture clang').hexdigest()
                self.assertEqual(binary, project/'.ambiance/native'/identity/'media')
                self.assertEqual(native_media.native_binary(project), binary)
                self.assertEqual(len(builds), 1)
                source.write_bytes(b'changed source')
                self.assertNotEqual(native_media.native_binary(project), binary)
                self.assertEqual(len(builds), 2)
            self.assertEqual(builds[0][:5], ['/fixture/xcrun', 'clang', '-O2', '-fobjc-arc', '-Wno-deprecated-declarations'])
            self.assertEqual(binary.read_bytes(), b'fixture binary')

    def test_failed_native_build_never_installs_binary(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            with patch.dict(os.environ, {'AMBIANCE_MEDIA_BINARY': ''}), \
                 patch.object(native_media.platform, 'system', return_value='Darwin'), \
                 patch.object(native_media.platform, 'platform', return_value='fixture macOS'), \
                 patch.object(native_media.shutil, 'which', return_value='/fixture/xcrun'), \
                 patch.object(native_media.subprocess, 'run', side_effect=[SimpleNamespace(stdout=b'clang'), SimpleNamespace(returncode=1, stderr='bad build')]):
                with self.assertRaisesRegex(CommandError, 'bad build'):
                    native_media.native_binary(project)
            self.assertEqual(list(project.rglob('media')), [])

    def test_requested_contact_missing_fails_with_provenance_and_saved_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root/'movie.mp4'; source.write_bytes(b'encoded fixture')
            binary = root/'media'; binary.write_bytes(b'binary fixture')
            with patch.object(native_media, 'json_command', return_value={'ok': True, 'decoded_frames': 12}) as decode:
                result = media_verification.verify_media(binary, source, root/'verification', 64, 96, 6, 12, 0, 12, contact_frames=[7])
            self.assertFalse(result['ok'])
            self.assertIn('not produced', result['error'])
            self.assertTrue(result['input_unchanged'])
            self.assertEqual(result['native_binary_sha256'], hashlib.sha256(binary.read_bytes()).hexdigest())
            self.assertEqual(result['native_source_sha256'], hashlib.sha256(native_media.NATIVE_SOURCE.read_bytes()).hexdigest())
            self.assertEqual(Path(result['report']).read_bytes(), (json.dumps(result, indent=2, allow_nan=False)+'\n').encode())
            self.assertEqual(decode.call_args.args[0][-1], '7')
            self.assertTrue(decode.call_args.kwargs['allow_check_failure'])


if __name__ == '__main__':
    unittest.main()
