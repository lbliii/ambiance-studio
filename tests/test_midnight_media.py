import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import studio
from ambiance_studio import activity, assets, cel_trim, benchmarking
from ambiance_studio.cli import parser, run
from tools import asset_tool

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('midnight_fixture', ROOT/'examples/activity/create_fixture.py')
fixture = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixture)


class MidnightMediaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.project = fixture.create(Path(self.tmp.name)/'film', fps=6).resolve()

    def test_cel_comparison_preserves_geometry_and_rejects_companion_conflicts(self):
        scene = studio.read(self.project/'scene/scene.json'); catalog = studio.read(self.project/'assets/catalog.json')
        recipe = {'version': 2, 'variants': [{'id': 'still', 'kind': 'held-pose', 'layers': [{'layer': 'actor', 'cell': 0}]},
                                          {'id': 'restrained', 'kind': 'cel-alternative', 'layers': [{'layer': 'actor', 'asset': 'actor', 'cell_map': [0, 0]}]}]}
        variants = activity.cel_variants(recipe, scene, catalog)
        for variant in variants:
            layer = variant['scene']['layers'][0]
            for key in ['x', 'y', 'width', 'height', 'anchor', 'scale', 'motion']:
                self.assertEqual(layer.get(key), scene['layers'][0].get(key))
        bad = copy.deepcopy(recipe); bad['variants'][0]['layers'][0]['scale'] = .5
        with self.assertRaises(ValueError): activity.cel_variants(bad, scene, catalog)
        scene['layers'][0]['sockets'] = {'pin': {'frames': [[0, 0], [1, 1]]}}
        with self.assertRaisesRegex(ValueError, 'socket'): activity.cel_variants(recipe, scene, catalog)

    def test_trim_compiles_exact_pixels_and_rejects_source_tampering(self):
        scene = studio.read(self.project/'scene/scene.json'); scene['layers'][0]['sockets'] = {'pin': {'frames': [[.2, .3], [.8, .6]]}}
        studio.write(self.project/'scene/scene.json', scene)
        prepared = cel_trim.prepare(self.project, 'actor', 'trimmed', self.project/'assets/trim')
        result = asset_tool.build(prepared['recipe'], self.project/'assets/trimmed')
        checked = assets.inspect_pack(self.project/'assets/trimmed'); self.assertTrue(checked['ok'])
        original_asset = studio.read(self.project/'assets/catalog.json')['assets'][0]
        _, original = assets.read_asset(original_asset, self.project); _, trimmed = assets.read_asset(checked['asset'], self.project/'assets/trimmed')
        receipt = studio.read(prepared['receipt']); left, top, right, bottom = receipt['crop']
        for before, after in zip(original, trimmed):
            self.assertEqual(before.crop(receipt['crop']).tobytes(), after.crop((2, 2, right-left+2, bottom-top+2)).tobytes())
        self.assertIsInstance(receipt['placement']['sockets']['pin'], dict)
        original_file = self.project/original_asset['file']; original_file.write_bytes(b'changed')
        with self.assertRaises(ValueError): assets.inspect_pack(self.project/'assets/trimmed')

    def test_benchmark_records_actual_view_work_and_unknown_native_cost(self):
        recipe = dict(format='ambiance-iteration', schema_version=2, id='bench', revision='not-captured', views=['portrait', 'landscape'],
                      default={'view': 'portrait', 'role': 'silent'}, editions=[{'role': 'silent'}], long_edge=64)
        path = self.project/'plans/benchmark-iteration.json'; studio.write(path, recipe)
        request = dict(format='ambiance-render-benchmark', schema_version=1, recipe='plans/benchmark-iteration.json', sample_count=3, encode_sample_seconds=0)
        result = benchmarking.benchmark(self.project, request, self.project/'reports/benchmark')
        self.assertEqual(len(result['views']), 2); self.assertIsNone(result['total_estimate_seconds'])
        self.assertTrue(all(v['picture_render_frames'] == 48 for v in result['views']))
        self.assertTrue(all(v['median_frame_seconds'] >= 0 for v in result['views']))


if __name__ == '__main__': unittest.main()
