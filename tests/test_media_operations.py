"""CLI/job parity and the edition validation boundary shared by both callers."""
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
import wave
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ambiance_studio import cli, media_operations as media
from ambiance_studio.file_identity import digest
import studio


class MediaOperationsTests(unittest.TestCase):
    def test_typed_jobs_and_saved_cli_commands_have_identical_options(self):
        project = Path('/tmp/film with spaces')
        out = project/'runs/edition'
        requests = [
            media.PictureRequest(revision='v1', edition='picture'),
            media.PictureRequest(revision='v1', edition='portrait', view='portrait', width=90, height=160, supersample=2),
            media.ComposeRequest(revision='v1', edition='score', picture=project/'paint é.mp4',
                                 picture_receipt='reports/picture.json', audio=project/'music.wav',
                                 repeats=2, audio_run='audio/runs/score'),
        ]
        for request in requests:
            with self.subTest(request=request):
                parsed = cli.parser().parse_args(media.request_argv(project, request, out))
                with patch.object(media, 'execute_media', return_value={'ok': True}) as execute:
                    media.execute_job(project, request, out)
                typed = execute.call_args.args[0]
                self.assertEqual(vars(typed), {key: vars(parsed)[key] for key in vars(typed)})
                self.assertEqual(execute.call_args.args[1], project)

    def test_invalid_edition_inputs_never_reach_renderer(self):
        with patch.object(media.revisions, 'prepare_edition', side_effect=ValueError('changed input')), \
             patch.object(media.rendering, 'run') as render, \
             patch.object(media.revisions, 'record_edition') as record:
            with self.assertRaisesRegex(ValueError, 'changed input'):
                media.execute_job(Path('/tmp/film'), media.PictureRequest(revision='v1', edition='picture'), Path('/tmp/out'))
        render.assert_not_called()
        record.assert_not_called()

    def test_runtime_failure_does_not_record_an_edition(self):
        with patch.object(media.revisions, 'prepare_edition', return_value={'captured': True}), \
             patch.object(media.rendering, 'run', side_effect=RuntimeError('encoder failed')), \
             patch.object(media.revisions, 'record_edition') as record:
            with self.assertRaisesRegex(RuntimeError, 'encoder failed'):
                media.execute_job(Path('/tmp/film'), media.PictureRequest(revision='v1', edition='picture'), Path('/tmp/out'))
        record.assert_not_called()

    def test_video_rejects_truncated_pcm_before_starting_native_encoder(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            scene = project/'scene.json'
            studio.write(scene, {'canvas': {'width': 64, 'height': 64, 'fps': 1, 'loop_seconds': 1}, 'layers': []})
            audio = project/'truncated.wav'
            with wave.open(str(audio), 'wb') as wav:
                wav.setnchannels(2)
                wav.setsampwidth(2)
                wav.setframerate(48000)
                wav.writeframes(b'\0' * 48000 * 4)
            audio.write_bytes(audio.read_bytes()[:-4])
            args = cli.parser().parse_args(['render', 'video', '--audio', str(audio), '--out', str(project/'render')])
            with patch.object(media.rendering, '_context', return_value={'scene': scene, 'catalog': project/'catalog.json'}), \
                 patch.object(media.rendering, '_native_binary') as native:
                with self.assertRaisesRegex(cli.CommandError, 'truncated'):
                    media.rendering.run(args, project)
            native.assert_not_called()
            self.assertFalse((project/'render').exists())

    def test_file_identity_streams_large_and_empty_files(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'media'
            for data in [b'', b'painted media' * 200_000]:
                path.write_bytes(data)
                with patch.object(Path, 'read_bytes', side_effect=AssertionError('Do not buffer the entire file')):
                    self.assertEqual(digest(path), hashlib.sha256(data).hexdigest())


if __name__ == '__main__':
    unittest.main()
