"""Thin occlusion strips must compile without a zero-height diagnostic image."""
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image, ImageDraw

import test_assets as fixtures


class StripPreviewTests(unittest.TestCase):
    def test_extreme_aspect_ratios_preserve_atlas_and_produce_readable_files(self):
        for width, height in ((4096, 8), (8, 4096)):
            with self.subTest(size=(width, height)), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                source = root / 'strip.png'
                image = Image.new('RGBA', (width, height))
                ImageDraw.Draw(image).rectangle((2, 2, width-3, height-3), fill='orange')
                image.save(source)
                original_hash = fixtures.tool.sha(source)
                recipe = root / 'recipe.json'
                recipe.write_text(json.dumps({
                    'version': 1, 'id': 'strip-v1', 'input': {'frames': ['strip.png']},
                    'registration': {'mode': 'fixed', 'point': [width/2, height/2],
                                     'target': [.5, .5]},
                    'output': {'cell_size': [width, height], 'columns': 1, 'padding': 2},
                }))
                out = root / 'pack'
                fixtures.tool.build(recipe, out)
                with Image.open(out / 'atlas.png') as atlas:
                    self.assertEqual(atlas.size, image.size)
                    self.assertEqual(atlas.tobytes(), image.tobytes())
                for name in ('contact-sheet.png', 'preview.gif'):
                    with Image.open(out / name) as preview:
                        preview.load()
                        self.assertGreaterEqual(min(preview.size), 1)
                self.assertEqual(fixtures.tool.sha(source), original_hash)
                self.assertEqual(fixtures.tool.build(recipe, out)['status'], 'cached')


if __name__ == '__main__':
    unittest.main()
