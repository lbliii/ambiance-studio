import copy
import http.client
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from urllib.parse import urlencode
import unittest
from unittest.mock import patch
from http.server import HTTPServer

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ambiance_studio import preparation as p
from ambiance_studio import asset_prep as prep
from ambiance_studio import preparation_server
from tools import asset_tool


def polygon(rect, operation='add'):
    x0, y0, x1, y1 = rect
    return {'operation': operation, 'points': [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]}


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        prep.write(self.root/'ambiance-project.json', {'version': 1})
        backing = Image.new('RGBA', (32, 48), '#17324a')
        backing.save(self.root/'backing.png')
        source = backing.copy(); draw = ImageDraw.Draw(source)
        draw.rectangle((9, 16, 20, 29), fill='#dbaf54')
        draw.rectangle((4, 27, 27, 29), fill='#adc6cf')
        source.save(self.root/'source.png')
        self.recipe = p.initial_recipe(self.root, self.root/'source.png', self.root/'backing.png')
        self.recipe['resampling'] = 'nearest'
        self.recipe['masks']['removal']['polygons'] = [polygon((8, 15, 21, 30))]
        self.recipe['masks']['cutout']['polygons'] = [polygon((9, 16, 20, 26))]
        self.recipe['masks']['occluder']['polygons'] = [polygon((4, 27, 27, 29))]
        self.recipe['motion']['delta'] = [0, -6]
        self.inputs = p.load_inputs(self.root, self.recipe)

    def build(self, name='part-v1', recipe=None):
        path = self.root/(name+'.json'); prep.write(path, recipe or self.recipe)
        return p.build(self.root, self.root/name, recipe_path=path)

    def test_masks_are_separate_and_fixed_foreground_restores_rest_pixels(self):
        images, facts, warnings = p.evaluate(self.recipe, self.inputs)
        self.assertEqual(images['backing'].getpixel((12, 20)), (23, 50, 74, 255))
        self.assertEqual(images['cutout'].getpixel((12, 28))[3], 0)
        self.assertEqual(images['occluder'].getpixel((12, 28)), (173, 198, 207, 255))
        self.assertEqual(images['rest'].tobytes(), images['source'].tobytes())
        self.assertEqual(facts['changed_rest_pixels'], 0)
        self.assertFalse(warnings)

    def test_subtractive_polygon_leaves_a_hole_without_changing_other_masks(self):
        before = p.evaluate(self.recipe, self.inputs)[0]
        self.recipe['masks']['cutout']['polygons'].append(polygon((12, 19, 15, 22), 'subtract'))
        after, facts, _ = p.evaluate(self.recipe, self.inputs)
        self.assertEqual(after['cutout'].getpixel((13, 20))[3], 0)
        self.assertEqual(after['removal-mask'].tobytes(), before['removal-mask'].tobytes())
        self.assertEqual(facts['changed_rest_pixels'], 16)

    def test_registration_uses_existing_affine_and_reports_uncovered_repair(self):
        shifted = Image.new('RGBA', (36, 48))
        with Image.open(self.root/'backing.png') as backing:
            shifted.paste(backing, (4, 0))
        shifted.save(self.root/'shifted.png')
        self.recipe['backing'] = p.image_record(self.root, self.root/'shifted.png')
        self.recipe['backing_to_source'] = [1, 0, 0, 1, -4, 0]
        inputs = p.load_inputs(self.root, self.recipe)
        result = p.evaluate(self.recipe, inputs)
        self.assertEqual(result[1]['changed_rest_pixels'], 0)
        self.recipe['backing_to_source'][4] = 24
        _, facts, warnings = p.evaluate(self.recipe, inputs)
        self.assertGreater(facts['removal_without_opaque_backing_pixels'], 0)
        self.assertTrue(any('does not fully cover' in w for w in warnings))

    def test_imported_soft_alpha_survives_until_explicit_polygon_overrides(self):
        mask = Image.new('L', (32, 48), 91); mask.save(self.root/'soft.png')
        self.recipe['masks']['cutout'] = {'image': p.image_record(self.root, self.root/'soft.png'), 'polygons': []}
        inputs = p.load_inputs(self.root, self.recipe)
        images, _, _ = p.evaluate(self.recipe, inputs)
        self.assertEqual(images['cutout'].getchannel('A').getextrema(), (91, 91))
        Image.new('RGB', (32, 48), 'white').save(self.root/'soft.png')
        self.recipe['masks']['cutout']['image'] = p.image_record(self.root, self.root/'soft.png')
        with self.assertRaisesRegex(ValueError, 'grayscale'):
            p.load_inputs(self.root, self.recipe)

    def test_invalid_recipes_and_coordinate_bounds_fail_before_publication(self):
        cases = [lambda r: r.update(unrecognized=True),
                 lambda r: r.update(backing_to_source=[0]*6),
                 lambda r: r['motion'].update(delta=[float('nan'), 0]),
                 lambda r: r['motion'].update(seconds=1.001),
                 lambda r: r['motion'].update(seconds=1.5),
                 lambda r: r['masks']['cutout']['polygons'][0].update(operation='guess'),
                 lambda r: r['masks']['cutout']['polygons'][0].update(points=[[0, 0], [100, 1], [2, 2]]),
                 lambda r: r['source'].update(file='../source.png'),
                 lambda r: r['source'].update(width=True)]
        for i, mutate in enumerate(cases):
            with self.subTest(i=i):
                candidate = copy.deepcopy(self.recipe); mutate(candidate)
                with self.assertRaises(ValueError):
                    self.build('bad-'+str(i), candidate)
                self.assertFalse((self.root/('bad-'+str(i))).exists())

    def test_build_is_immutable_rebuildable_and_contains_compiler_mapping(self):
        original = {role: (self.root/ref['file']).read_bytes() for role, ref in p.references(self.recipe)}
        result = self.build()
        out = Path(result['directory'])
        rebuilt = p.build(self.root, self.root/'part-v2', recipe_path=out/'recipe.json')
        for name in ['backing', 'cutout', 'occluder', 'removal-mask', 'difference']:
            self.assertEqual((out/'images'/f'{name}.png').read_bytes(), (Path(rebuilt['directory'])/'images'/f'{name}.png').read_bytes())
        for role, ref in p.references(self.recipe):
            self.assertEqual((self.root/ref['file']).read_bytes(), original[role])
        asset_tool.build(out/'compiler/cutout.json', self.root/'compiled-cutout')
        compiled = prep.load(self.root/'compiled-cutout/asset.json')
        self.assertEqual(compiled['registration_mapping']['cels'][0]['reference_to_cell'], [1, 0, 0, 1, 2, 2])
        self.assertEqual(compiled['registration_mapping']['shared_scale'], 1)
        self.assertEqual(p.artifact(out)[0], self.recipe)
        with self.assertRaisesRegex(ValueError, 'Output exists'):
            p.build(self.root, out, recipe_path=out/'recipe.json')

    def test_changed_source_and_changed_artifact_are_rejected(self):
        result = self.build(); out = Path(result['directory'])
        (self.root/'source.png').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'input changed'):
            p.build(self.root, self.root/'invalid', recipe_path=out/'recipe.json')
        # Captured workbench stays usable independently of the later working source.
        self.assertEqual(p.artifact(out)[0], self.recipe)
        (out/'images/cutout.png').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'artifact changed'):
            p.artifact(out)

    def test_mid_build_source_change_and_concurrent_destination_leave_no_partial_output(self):
        real = p.encoded_result
        def change_source(*args):
            result = real(*args); (self.root/'source.png').write_bytes(b'changed'); return result
        with patch.object(p, 'encoded_result', side_effect=change_source):
            with self.assertRaisesRegex(ValueError, 'changed during'):
                self.build('raced')
        self.assertFalse((self.root/'raced').exists())
        (self.root/'source.png').write_bytes(self.inputs['source'])
        def claim_destination(*args):
            result = real(*args); (self.root/'claimed').mkdir(); (self.root/'claimed/keep').write_text('other owner'); return result
        with patch.object(p, 'encoded_result', side_effect=claim_destination):
            with self.assertRaisesRegex(ValueError, 'Output exists'):
                self.build('claimed')
        self.assertEqual((self.root/'claimed/keep').read_text(), 'other owner')

    def test_live_preview_and_saved_build_use_identical_raster_bytes(self):
        result = self.build(); out = Path(result['directory'])
        recipe, inputs, files = p.artifact(out)
        import base64
        live = p.preview_result(recipe, recipe, inputs)
        for name, url in live['images'].items():
            self.assertEqual(base64.b64decode(url.split(',')[1]), files[f'images/{name}.png'])
        candidate = copy.deepcopy(recipe); candidate['source']['file'] = 'other.png'
        with self.assertRaisesRegex(ValueError, 'retain captured'):
            p.preview_result(candidate, recipe, inputs)

    def test_public_cli_build_and_shared_renderer_preserve_rest_and_move_cutout(self):
        recipe = self.root/'recipe.json'; prep.write(recipe, self.recipe)
        def cli(*args):
            proc = subprocess.run([sys.executable, str(ROOT/'ambiance'), *map(str, args)], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stdout+proc.stderr)
            return json.loads(proc.stdout)['data']
        result = cli('--project', self.root, 'asset', 'prepare', '--recipe', recipe, '--out', self.root/'cli-part')
        preview = result['preview_project']
        cli('--project', preview, 'render', 'frame', '--time', 0, '--out', self.root/'rest')
        cli('--project', preview, 'render', 'frame', '--time', 2, '--out', self.root/'extreme')
        # The existing renderer report names the rendered frame, without assuming its filename.
        a = next((self.root/'rest').glob('*.png')); b = next((self.root/'extreme').glob('*.png'))
        with Image.open(a) as rest, Image.open(b) as extreme, Image.open(self.root/'source.png') as source:
            # The native Canvas high-quality sampler softens hard alpha edges even at
            # identity. Verify registration and preserved interior paint separately.
            for rect in [(0, 0, 8, 14), (10, 17, 19, 25), (6, 28, 26, 29)]:
                self.assertEqual(rest.convert('RGBA').crop(rect).tobytes(), source.crop(rect).tobytes())
            self.assertNotEqual(extreme.tobytes(), rest.tobytes())
            self.assertEqual(extreme.getpixel((12, 12))[:3], (219, 175, 84))
            self.assertEqual(extreme.getpixel((12, 28))[:3], (173, 198, 207))

    def test_preview_http_rejects_other_origins_paths_and_changed_sources(self):
        out = Path(self.build()['directory'])
        server = HTTPServer(('127.0.0.1', 0), preparation_server.handler_for(out))
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        def request(method, path, body=None, headers=None):
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=10)
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse(); data = response.read(); status = response.status
            connection.close(); return status, data
        self.assertEqual(request('GET', '/')[0], 200)
        self.assertEqual(request('GET', '/snapshots/source.bin')[0], 404)
        self.assertEqual(request('GET', '/../recipe.json')[0], 404)
        self.assertEqual(request('GET', '/', headers={'Host': 'evil.example'})[0], 403)
        body = json.dumps(self.recipe)
        self.assertEqual(request('POST', '/api/preview', body, {'Content-Type': 'application/json', 'Origin': 'https://evil.example'})[0], 403)
        status, data = request('POST', '/api/preview', body, {'Content-Type': 'application/json'})
        self.assertEqual(status, 200); self.assertTrue(json.loads(data)['ok'])
        candidate = copy.deepcopy(self.recipe); candidate['source']['sha256'] = 'a'*64
        self.assertEqual(request('POST', '/api/preview', json.dumps(candidate), {'Content-Type': 'application/json'})[0], 400)
        self.assertEqual(request('POST', '/api/preview', '{}', {'Content-Type': 'text/plain'})[0], 415)
        status, data = request('POST', '/api/export', urlencode({'recipe': body}), {'Content-Type': 'application/x-www-form-urlencoded'})
        self.assertEqual(status, 200); self.assertEqual(json.loads(data), self.recipe)
        self.assertEqual(request('POST', '/api/export', urlencode({'recipe': json.dumps(candidate)}), {'Content-Type': 'application/x-www-form-urlencoded'})[0], 400)


if __name__ == '__main__':
    unittest.main(verbosity=2)
