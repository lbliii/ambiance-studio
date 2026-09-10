"""Pixel and failure-path checks for opt-in edge derivatives and proofs."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ambiance_studio import edge_quality as edge
from ambiance_studio import asset_prep as prep
from tools import asset_tool


def image_copy(path):
    with Image.open(path) as image:
        image.load()
        return image.convert('RGBA')


class EdgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root/'source.png'; self.recipe = self.root/'recipe.json'
        sheet = Image.new('RGBA', (32, 16), (30, 90, 180, 0))
        draw = ImageDraw.Draw(sheet)
        draw.rectangle((3, 4, 9, 12), fill=(180, 110, 55, 255))
        draw.line((2, 3, 11, 3), fill=(130, 150, 170, 32))
        draw.rectangle((19, 4, 25, 12), fill=(70, 130, 190, 255))
        draw.line((18, 3, 27, 3), fill=(140, 160, 180, 128))
        sheet.save(self.source)
        self.spec = {'format': 'ambiance-edge-repair', 'version': 1,
                     'layout': {'columns': 2, 'rows': 1, 'cell_width': 16, 'cell_height': 16, 'frame_count': 2}}
        self.save()

    def save(self):
        self.recipe.write_text(json.dumps(self.spec))

    def repair(self, name='repair'):
        return edge.edge_repair(self.source, self.recipe, self.root/name)

    def pack(self):
        recipe = self.root/'compile.json'
        prep.write(recipe, {'version': 1, 'id': 'edge-fixture-v1',
                            'input': {'sheet': 'source.png', 'columns': 2, 'rows': 1, 'frame_count': 2},
                            'registration': {'mode': 'fixed', 'point': [8, 12], 'target': [.5, .75]},
                            'output': {'cell_size': [24, 24], 'columns': 2, 'padding': 2}})
        pack = self.root/'pack'; asset_tool.build(recipe, pack)
        return pack

    def test_neutral_recipe_preserves_rgba_including_whiskers_and_hidden_rgb(self):
        before = self.source.read_bytes(); result = self.repair()
        self.assertEqual(image_copy(result['atlas']).tobytes(), image_copy(self.source).tobytes())
        self.assertEqual(self.source.read_bytes(), before)
        self.assertEqual((self.root/'repair/source-original.bin').read_bytes(), before)
        self.assertEqual((self.root/'repair/recipe.json').read_bytes(), self.recipe.read_bytes())
        self.assertTrue(all(cel['changed_rgba_pixels'] == 0 for cel in result['cels']))
        for name, digest in result['outputs'].items():
            self.assertEqual(prep.sha((self.root/'repair'/name).read_bytes()), digest)
        self.assertTrue((self.root/'repair/before/index.html').is_file())

    def test_declared_matte_recovers_known_color_and_keeps_every_alpha(self):
        self.spec['decontamination'] = {'strength': 1, 'matte_rgb': [240, 240, 240]}; self.save()
        result = self.repair(); actual = image_copy(result['atlas']); original = image_copy(self.source)
        self.assertEqual(actual.getchannel('A').tobytes(), original.getchannel('A').tobytes())
        self.assertEqual(actual.getpixel((3, 4)), original.getpixel((3, 4)))  # Opaque color unaffected.
        self.assertEqual(actual.getpixel((0, 0)), original.getpixel((0, 0)))  # Hidden color unaffected.
        recovered = actual.getpixel((18, 3))
        for value, expected in zip(recovered[:3], [41, 81, 120]):
            self.assertLessEqual(abs(value-expected), 1)
        self.assertEqual(recovered[3], 128)

    def test_choke_and_feather_are_explicit_and_preserve_hue_in_added_alpha(self):
        self.spec['alpha'] = {'choke_px': 1, 'feather_px': 1}; self.spec['padding_px'] = 3; self.save()
        result = self.repair(); im = image_copy(result['atlas'])
        self.assertEqual(im.size, (44, 22))
        self.assertLess(result['cels'][0]['after']['alpha_mass_pixels'], result['cels'][0]['before']['alpha_mass_pixels'])
        # Newly visible pixels inherit nearby paint; transparent blue storage
        # must not leak out of the original zero-alpha RGB background.
        cel = im.crop((0, 0, 22, 22))
        self.assertTrue(any(0 < a < 255 for _, _, _, a in edge.pixels(cel)))
        for r, g, b, a in edge.pixels(cel):
            if a >= 8:
                self.assertGreater(r, b)

    def test_padding_moves_each_cell_independently_and_preserves_unused_slots(self):
        self.spec['layout']['frame_count'] = 1; self.spec['padding_px'] = 2; self.save()
        result = self.repair(); im = image_copy(result['atlas']); original = image_copy(self.source)
        self.assertEqual(im.size, (40, 20))
        for i in range(2):
            self.assertEqual(im.crop((i*20+2, 2, i*20+18, 18)).tobytes(), original.crop((i*16, 0, i*16+16, 16)).tobytes())
        self.assertEqual(im.getpixel((19, 8))[3], 0)
        self.assertEqual(im.getpixel((20, 8))[3], 0)
        self.assertEqual(result['cels'][0]['raw_cel_to_output_cell'], [1, 0, 0, 1, 2, 2])

    def test_isolated_resampling_cannot_sample_adjacent_atlas_cell(self):
        sheet = Image.new('RGBA', (8, 4), (0, 0, 255, 255))
        sheet.paste(Image.new('RGBA', (4, 4), (255, 0, 0, 255)), (0, 0))
        first = edge.isolated_resize(sheet.crop((0, 0, 4, 4)), (11, 11))
        self.assertEqual(set(edge.pixels(first)), {(255, 0, 0, 255)})
        transparent = Image.new('RGBA', (3, 1), (255, 255, 255, 0)); transparent.putpixel((1, 0), (255, 0, 0, 255))
        resized = edge.isolated_resize(transparent, (15, 5))
        self.assertTrue(all(g == 0 and b == 0 for r, g, b, a in edge.pixels(resized) if a > 0))

    def test_invalid_recipe_fields_dimensions_numbers_and_undeclared_matte_fail(self):
        cases = [({'alpha': {'feather_px': float('nan')}}, 'finite'),
                 ({'alpha': {'choke_px': True}}, 'integer'),
                 ({'decontamination': {'strength': 1}}, 'matte_rgb'),
                 ({'decontamination': {'strength': .5, 'matte_rgb': [1, 2, 999]}}, 'matte_rgb'),
                 ({'alpha': {'automatic': True}}, 'Unsupported'),
                 ({'padding_px': -1}, 'integer')]
        for index, (change, message) in enumerate(cases):
            data = {**self.spec, **change}; prep.write(self.recipe, data) if index else self.recipe.write_text(json.dumps(data))
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, message):
                self.repair(f'invalid-{index}')
            self.assertFalse((self.root/f'invalid-{index}').exists())
        self.spec['layout']['cell_width'] = 15; self.save()
        with self.assertRaisesRegex(ValueError, 'dimensions exactly'):
            self.repair('geometry')

    def test_opaque_and_multiframe_sources_rejected_without_output(self):
        Image.new('RGB', (32, 16), '#ffffff').save(self.source)
        with self.assertRaisesRegex(ValueError, 'actual transparency'):
            self.repair()
        Image.new('RGBA', (32, 16)).save(self.source, format='PNG', save_all=True, append_images=[Image.new('RGBA', (32, 16), 'red')])
        with self.assertRaisesRegex(ValueError, 'still source'):
            self.repair()
        self.assertFalse((self.root/'repair').exists())

    def test_changed_input_aborts_staged_output(self):
        write = edge.write_proofs
        def changed(*args, **kwargs):
            result = write(*args, **kwargs)
            self.source.write_bytes(self.source.read_bytes()+b'changed')
            return result
        with patch.object(edge, 'write_proofs', side_effect=changed), self.assertRaisesRegex(ValueError, 'input changed'):
            self.repair()
        self.assertFalse((self.root/'repair').exists())
        self.assertFalse(any(self.root.glob('.edge-quality-*')))

    def test_existing_and_concurrent_output_are_never_replaced(self):
        out = self.root/'repair'; out.mkdir(); (out/'keep').write_text('keep')
        with self.assertRaisesRegex(ValueError, 'Output exists'):
            self.repair()
        self.assertEqual((out/'keep').read_text(), 'keep')
        check = edge.check_inputs
        def claim(records):
            check(records); (self.root/'race').mkdir(); (self.root/'race/owner').write_text('another operation')
        with patch.object(edge, 'check_inputs', side_effect=claim), self.assertRaisesRegex(ValueError, 'publish fresh'):
            self.repair('race')
        self.assertEqual((self.root/'race/owner').read_text(), 'another operation')
        self.assertEqual(sorted(p.name for p in (self.root/'race').iterdir()), ['owner'])

    def test_proof_all_cels_actual_pixels_scale_and_context_position(self):
        pack = self.pack(); background = self.root/'background.png'
        bg = Image.new('RGBA', (80, 80), '#173b62'); bg.save(background)
        result = edge.edges(str(pack), self.root/'proof', display_width=12, magnify=4, background=background, context_rect=[31, 41, 12, 12])
        self.assertEqual(result['cel_count'], 2)
        self.assertEqual(result['scale']['cell_to_display'], [.5, .5])
        self.assertEqual(result['scale']['source_registration']['compiler_shared_scale'], 1)
        for i in range(2):
            self.assertEqual(image_copy(self.root/f'proof/light-{i:03d}.png').size, (12, 12))
            self.assertEqual(image_copy(self.root/f'proof/context-magnified-{i:03d}.png').size, (48, 48))
        placement = image_copy(self.root/'proof/context-placement.png')
        self.assertEqual(placement.getpixel((0, 0)), bg.getpixel((0, 0)))
        context_tile = image_copy(self.root/'proof/context-000.png')
        self.assertEqual(placement.crop((31, 41, 43, 53)).tobytes(), context_tile.tobytes())
        for path, digest in result['outputs'].items():
            self.assertEqual(prep.sha((self.root/'proof'/path).read_bytes()), digest)

    def test_context_must_be_explicit_unscaled_in_bounds_and_paired(self):
        pack = self.pack(); background = self.root/'background.png'; Image.new('RGB', (80, 80)).save(background)
        cases = [({'background': background}, 'together'),
                 ({'background': background, 'context_rect': [0, 0, 24, 24]}, 'equal displayed'),
                 ({'background': background, 'context_rect': [72, 72, 12, 12]}, 'within'),
                 ({'display_width': 0}, 'integer')]
        for i, (params, message) in enumerate(cases):
            with self.subTest(params=params), self.assertRaisesRegex(ValueError, message):
                edge.edges(str(pack), self.root/f'bad-{i}', **{'display_width': 12, **params})
            self.assertFalse((self.root/f'bad-{i}').exists())

    def test_changed_pack_proof_rejected(self):
        pack = self.pack(); (pack/'atlas.png').write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError, 'Pack changed'):
            edge.edges(str(pack), self.root/'proof', display_width=12)
        self.assertFalse((self.root/'proof').exists())

    def test_proof_input_race_is_detected_after_rendering(self):
        pack = self.pack(); write = edge.write_proofs
        def changed(*args, **kwargs):
            result = write(*args, **kwargs)
            (pack/'asset.json').write_bytes((pack/'asset.json').read_bytes()+b'\n')
            return result
        with patch.object(edge, 'write_proofs', side_effect=changed), self.assertRaisesRegex(ValueError, 'input changed'):
            edge.edges(str(pack), self.root/'proof', display_width=12)
        self.assertFalse((self.root/'proof').exists())

    def test_compiler_keeps_preparation_chain_and_rechecks_upstream_on_cache(self):
        self.repair(); report = self.root/'repair/report.json'
        recipe = self.root/'compile-repair.json'
        prep.write(recipe, {'version': 1, 'id': 'edge-preparation-v1',
                            'input': {'sheet': 'repair/atlas.png', 'columns': 2, 'rows': 1, 'frame_count': 2},
                            'edge_preparation': {'file': 'repair/report.json', 'sha256': prep.sha(report.read_bytes())},
                            'registration': {'mode': 'fixed', 'point': [8, 12], 'target': [.5, .75]},
                            'output': {'cell_size': [24, 24], 'columns': 2, 'padding': 2}})
        pack = self.root/'prepared-pack'; asset_tool.build(recipe, pack)
        packed = prep.load(pack/'asset.json'); packed_recipe = prep.load(pack/'recipe.json')
        self.assertEqual(packed['provenance']['edge_preparation'], packed_recipe['edge_preparation'])
        self.assertEqual(asset_tool.build(pack/'recipe.json', pack)['status'], 'cached')
        deps = edge.validate_edge_preparation(report, prep.sha(report.read_bytes()), [self.root/'repair/atlas.png'])['dependencies']
        self.assertEqual({dep['role'] for dep in deps}, {'edge-preparation-report', 'edge-preparation-source', 'edge-preparation-recipe', 'edge-preparation-original-snapshot', 'edge-preparation-recipe-snapshot', 'edge-preparation-atlas'})
        self.source.write_bytes(self.source.read_bytes()+b'changed upstream')
        with self.assertRaisesRegex(ValueError, 'source changed'):
            asset_tool.build(pack/'recipe.json', pack)
        with self.assertRaisesRegex(ValueError, 'source changed'):
            asset_tool.build(recipe, self.root/'changed-pack')
        self.assertFalse((self.root/'changed-pack').exists())

    def test_preparation_verifier_rejects_snapshot_change_and_wrong_atlas(self):
        self.repair(); report = self.root/'repair/report.json'; digest = prep.sha(report.read_bytes())
        with self.assertRaisesRegex(ValueError, 'exact single compiler'):
            edge.validate_edge_preparation(report, digest, [self.source])
        original = self.root/'repair/source-original.bin'; original.write_bytes(original.read_bytes()+b'tamper')
        with self.assertRaisesRegex(ValueError, 'original_snapshot changed'):
            edge.validate_edge_preparation(report, digest)


if __name__ == '__main__':
    unittest.main(verbosity=2)
