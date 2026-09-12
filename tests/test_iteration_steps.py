"""Portable checks for checkpoint reuse, failure and immutable output identity."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import studio
from ambiance_studio.iteration_steps import IterationProgress, run_file
from ambiance_studio.media_operations import PictureRequest


class IterationStepTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.project = Path(temp.name).resolve()
        self.state = {'id': 'iteration', 'recipe': {'revision': 'v1'}, 'steps': {}, 'attempts': {}}
        self.request = PictureRequest(revision='v1', edition='picture')

    def produce(self, project, request, out):
        out.mkdir(parents=True)
        (out/'picture.mp4').write_bytes(b'synthetic step identity, not playable media')
        studio.write(out/'verification.json', {'ok': True})
        studio.write(out/'edition.json', {'fixture': True})
        result = {'ok': True, 'output': str(out/'picture.mp4'), 'report': str(out/'render-report.json'),
                  'verification': {'ok': True, 'report': str(out/'verification.json')},
                  'edition': {'id': request.edition, 'receipt': str(out/'edition.json')}}
        studio.write(out/'render-report.json', result)
        return result

    def test_saved_step_reuses_outputs_and_rejects_tampering(self):
        executor = Mock(side_effect=self.produce)
        progress = IterationProgress(self.project, self.state, Mock(), executor)
        result = progress.step('picture', self.request)
        state = studio.read(run_file(self.project, 'iteration'))
        resumed_executor = Mock(side_effect=AssertionError('Completed steps must not encode again'))
        resumed = IterationProgress(self.project, state, Mock(), resumed_executor)
        self.assertEqual(resumed.step('picture', self.request)['output'], result['output'])
        resumed_executor.assert_not_called()
        self.assertEqual(executor.call_count, 1)
        self.assertEqual(state['attempts'], {'picture': 1})
        Path(result['edition']['receipt']).write_text('changed')
        with self.assertRaisesRegex(ValueError, 'Completed picture output changed'):
            resumed.step('picture', self.request)
        resumed_executor.assert_not_called()

    def test_failed_step_retains_attempt_but_never_claims_completion(self):
        progress = IterationProgress(self.project, self.state, Mock(), Mock(return_value={'ok': False}))
        with self.assertRaisesRegex(ValueError, 'picture failed'):
            progress.step('picture', self.request)
        saved = studio.read(run_file(self.project, 'iteration'))
        self.assertEqual(saved['steps'], {})
        self.assertEqual(saved['attempts'], {'picture': 1})
        self.assertEqual(saved['active_command'][:4], ['--project', str(self.project), 'render', 'video'])


if __name__ == '__main__':
    unittest.main()
