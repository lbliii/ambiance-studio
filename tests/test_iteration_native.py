"""Opt-in real encode/compose/register/present workflow, with an isolated scene."""
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import wave

import studio
from ambiance_studio import deliveries, production
from ambiance_studio.cli import init_project, parser, run


@unittest.skipUnless(os.environ.get('AMBIANCE_TEST_NATIVE') == '1' and sys.platform == 'darwin',
                     'Set AMBIANCE_TEST_NATIVE=1 with macOS media services')
class NativeIterationTests(unittest.TestCase):
    def test_real_iteration_and_resume_preserve_movie_identity(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); project = root/'film'
            init_project(project, None, 'Native iteration fixture', 'blank')
            art = project/'assets/plate.png'; Image.new('RGB', (32, 48), '#513d67').save(art)
            catalog = {'version': 1, 'assets': [{'id': 'plate', 'kind': 'plate', 'file': 'assets/plate.png', 'width': 32, 'height': 48, 'sha256': studio.digest(art)}]}
            studio.write(project/'assets/catalog.json', catalog)
            scene = studio.read(project/'scene/scene.json'); scene['canvas'].update(width=32, height=48, fps=4, loop_seconds=1)
            studio.write(project/'scene/scene.json', scene)
            run(parser().parse_args(['--project', str(project), 'scene', 'add', 'plate', '--id', 'base', '--width', '1']))
            master = project/'audio/master.wav'
            with wave.open(str(master), 'wb') as output:
                output.setnchannels(2); output.setsampwidth(2); output.setframerate(48000)
                output.writeframes(b'\0\0\0\0'*96000)
            shutil.copyfile(master, project/'audio/source.wav')
            (project/'audio/identity.txt').write_text('Fixture: copied source PCM unchanged to master. Silence is intentional.')
            def ref(name): return {'path': 'audio/'+name, 'sha256': studio.digest(project/'audio'/name)}
            studio.write(project/'audio/preparation.json', {'format': 'ambiance-external-preparation', 'schema_version': 1,
                'sources': [ref('source.wav')], 'recipes': [ref('identity.txt')], 'outputs': [ref('master.wav')]})
            studio.write(project/'selection.json', {'format': 'ambiance-revision-selection', 'schema_version': 1,
                'scene': 'scene/scene.json', 'catalog': 'assets/catalog.json',
                'audio': {'preparations': ['audio/preparation.json'], 'masters': ['audio/master.wav']}})
            recipe = {'format': 'ambiance-iteration', 'schema_version': 1, 'id': 'take-1', 'revision': 'v1',
                      'capture_selection': 'selection.json', 'default_role': 'score',
                      'editions': [{'role': 'silent'}, {'role': 'score', 'audio': 'audio/master.wav', 'repeats': 2}]}
            result = production.iteration(project, recipe, 'Native fixture')
            self.assertTrue(result['ok'])
            current = deliveries.latest(project)
            self.assertTrue(current['ok']); self.assertEqual(current['delivery']['editions']['score']['frames'], 8)
            token = current['selection']['payload_sha256']
            self.assertTrue(production.iteration(project, recipe, 'Native fixture')['reused'])
            self.assertEqual(deliveries.current(project)['payload_sha256'], token)
            saved = studio.read(production.run_file(project, 'take-1'))
            saved['state'] = 'failed'; saved['steps'].pop('score')
            # Model interruption after the edition receipt but before run-state persistence.
            saved['expected_selection'] = token
            studio.write(production.run_file(project, 'take-1'), saved)
            self.assertTrue(production.iteration(project, recipe, 'Native fixture')['ok'])
            self.assertEqual(deliveries.latest(project)['delivery']['editions']['score']['movie'], current['delivery']['editions']['score']['movie'])


if __name__ == '__main__':
    unittest.main()
