"""Proof labels cannot overwrite a different image while retaining its receipt."""
import copy
import hashlib
import unittest

import test_media_compose as fixtures


@unittest.skipUnless(fixtures.Image and fixtures.rendering.capabilities()['frame_render'],
                     'Requires Pillow and Node Canvas')
class ProofOutputIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.RigProofTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def assert_receipts_match_files(self, report):
        outputs = report['outputs']
        paths = [record['file'] for record in outputs]
        self.assertEqual(len(paths), len(set(paths)))
        for record in outputs:
            path = self.fixture.root / 'proof' / record['file']
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), record['sha256'])
            with fixtures.Image.open(path) as image:
                self.assertEqual(image.size, (record['width'], record['height']))
        for sample in report['samples']:
            self.assertEqual((sample['context']['width'], sample['context']['height']), (64, 96))
        self.assertEqual(self.fixture.scene_path.read_bytes(), self.fixture.original)

    def test_context_difference_and_comparison_names_are_valid_without_overwriting(self):
        recipe = copy.deepcopy(self.fixture.recipe)
        recipe['regions'] = [{'id': name, 'rect': [.2, .2, .6, .6]}
                             for name in ('context', 'comparison', 'difference')]
        recipe['comparisons'][0]['id'] = 'rest'  # Also a valid sample ID.
        report = self.fixture.execute(recipe)
        self.assertTrue(report['ok'])
        self.assert_receipts_match_files(report)
        sample = report['samples'][0]
        self.assertNotEqual(sample['context']['file'], sample['details'][0]['file'])
        comparison = report['comparisons'][0]
        self.assertNotEqual(comparison['difference_image']['file'], comparison['details'][2]['file'])

    def test_hyphenated_ids_do_not_alias_concatenated_sample_and_region_names(self):
        recipe = copy.deepcopy(self.fixture.recipe)
        recipe['samples'] = [{'id': 'rest-body', 'time': 0}, {'id': 'rest', 'time': 1}]
        recipe['regions'] = [{'id': 'edge', 'rect': [0, 0, .5, .5]},
                             {'id': 'body-edge', 'rect': [.5, .5, .5, .5]}]
        recipe['comparisons'] = []
        recipe['playback_seconds'] = 0
        report = self.fixture.execute(recipe)
        self.assert_receipts_match_files(report)
        self.assertNotEqual(report['samples'][0]['details'][0]['file'],
                            report['samples'][1]['details'][1]['file'])


if __name__ == '__main__':
    unittest.main()
