"""Render geometry before downsampling; portable look artifacts retain exact inputs."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ambiance_studio import rendering
from ambiance_studio.cli import CommandError
from test_rendering import fixture, parse, Image


@unittest.skipUnless(Image and rendering.capabilities()['frame_render'], 'Requires Pillow and Node Canvas')
class FinishingRenderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.project = fixture(self.root)
        self.scene_path = self.project/'edit/cut.json'

    def run_render(self, *args):
        return rendering.run(parse(*args), self.project)

    def test_supersampling_renders_geometry_at_internal_resolution_before_output(self):
        scene = json.loads(self.scene_path.read_text()); scene['layers'][0]['rotation'] = .17
        self.scene_path.write_text(json.dumps(scene)); source = self.scene_path.read_bytes()
        ordinary = self.run_render('render', 'frame', '--out', self.root/'ordinary')
        sample = self.run_render('render', 'frame', '--supersample', 2, '--out', self.root/'sample')
        endpoint = self.run_render('render', 'frame', '--supersample', 2, '--time', 2, '--out', self.root/'endpoint')
        self.assertEqual(sample['render_canvas']['width'], 64)
        self.assertEqual(sample['internal_canvas']['width'], 128)
        self.assertEqual(sample['internal_canvas']['height'], 192)
        self.assertEqual(sample['downsample']['passes'], 1)
        self.assertEqual(sample['output_sha256'], endpoint['output_sha256'])
        self.assertNotEqual(sample['output_sha256'], ordinary['output_sha256'])
        with Image.open(sample['output']) as image:
            self.assertEqual(image.size, (64, 96))
        self.assertEqual(self.scene_path.read_bytes(), source)
        self.assertTrue(sample['rgba_endpoint_exact'])

    def test_supersampling_limit_rejects_before_creating_output(self):
        for scale, width in [(2, 2048), (4, 1024)]:
            with self.assertRaisesRegex(CommandError, '4096'):
                self.run_render('render', 'frame', '--width', width, '--supersample', scale, '--out', self.root/'invalid')
            self.assertFalse((self.root/'invalid').exists())

    def test_supersampled_motion_proof_outputs_exact_requested_size_and_frame_count(self):
        proof = self.run_render('render', 'proof', '--width', 64, '--seconds', 1, '--supersample', 4,
                                '--disable', 'moving', '--out', self.root/'proof')
        self.assertEqual(proof['frames'], 6); self.assertEqual(proof['variants'], 2)
        self.assertEqual(proof['internal_canvas']['height'], 384)
        for path in (self.root/'proof').glob('*/*.png'):
            with Image.open(path) as image:
                self.assertEqual(image.size, (64, 96))

    def test_look_artifact_pins_extra_masks_and_shared_modules_and_preserves_originals(self):
        mask = self.project/'art/mask.png'
        with Image.new('RGBA', (16, 16), (255, 255, 255, 255)) as image:
            image.save(mask)
        catalog_path = self.project/'art/library.json'; catalog = json.loads(catalog_path.read_text())
        catalog['assets'].append({'id':'mask','file':'art/mask.png','width':16,'height':16,
                                  'sha256':hashlib.sha256(mask.read_bytes()).hexdigest()})
        catalog_path.write_text(json.dumps(catalog))
        source = self.scene_path.read_bytes()
        finish = {'version':1,'working_space':'linear-srgb','output_space':'srgb',
                  'layers':{'moving':{'balance':[.6,.8,1.5]}},
                  'lights':[{'id':'moon','rect':[0,0,1,1],'receivers':['moving'],
                             'color':'#3366cc','gain':.6,'mask_asset':'mask'}]}
        recipe = self.root/'recipe.json'; recipe.write_text(json.dumps({'version':1,'title':'Moon <light>',
                    'time':.5,'selected_layer':'moving','finishing':finish,
                    'variants':[{'id':'warm','finishing':{**finish,'layers':{'moving':{'balance':[1.5,.8,.6]}}}}]}))
        result = self.run_render('render', 'look-proof', recipe, '--width', 64, '--supersample', 2, '--out', self.root/'look')
        self.assertEqual(result['saved_sample_frames'], 3)
        self.assertIsNone(result['frames']); self.assertFalse(result['full_loop_review_performed'])
        self.assertEqual(self.scene_path.read_bytes(), source)
        data = json.loads((self.root/'look/workbench.json').read_text())
        self.assertEqual(data['scene'], json.loads(source))
        self.assertEqual(data['scene_sha256'], hashlib.sha256(source).hexdigest())
        self.assertEqual({a['id'] for a in data['catalog']['assets']}, {'paint', 'mask'})
        for item in result['workbench']['modules']:
            file = self.root/'look'/item['file']
            self.assertEqual(hashlib.sha256(file.read_bytes()).hexdigest(), item['sha256'])
        self.assertIn('modules/finishing.mjs', {m['file'] for m in result['workbench']['modules']})
        for asset in data['catalog']['assets']:
            self.assertEqual(hashlib.sha256((self.root/'look'/asset['file']).read_bytes()).hexdigest(), asset['sha256'])
        self.assertNotEqual(result['samples'][0]['sha256'], result['samples'][1]['sha256'])
        self.assertIn('Moon &lt;light&gt;', Path(result['output']).read_text())

    def test_workbench_download_operation_round_trips_through_scene_apply(self):
        scene = json.loads(self.scene_path.read_text())
        catalog = json.loads((self.project/'art/library.json').read_text())
        finishing = {'version':1,'working_space':'linear-srgb','output_space':'srgb','layers':{'moving':{'exposure':.4}}}
        script = "import {finishingBatch} from './editor/look-workbench.mjs'; console.log(JSON.stringify(finishingBatch(JSON.parse(process.argv[1]))));"
        exported = subprocess.run(['node','--input-type=module','-e',script,json.dumps(finishing)], cwd=ROOT,
                                  capture_output=True,text=True,check=True)
        batch = json.loads(exported.stdout)
        bridge = subprocess.run(['node',str(ROOT/'tools/scene-command.mjs')], input=json.dumps({
            'action':'apply','scene':scene,'catalog':catalog,'args':{'batch':batch}}),capture_output=True,text=True,check=True)
        updated = json.loads(bridge.stdout)['data']
        self.assertEqual(updated.pop('finishing'),finishing)
        self.assertEqual(updated,scene)

    def test_look_unknown_recipe_or_finishing_fields_fail_before_artifact(self):
        recipe = self.root/'invalid.json'
        for value in [{'version':1,'unimplemented':True},
                      {'version':1,'finishing':{'version':1,'working_space':'linear-srgb','output_space':'srgb','automatic_lighting':True}},
                      {'version':1,'time':2}]:
            recipe.write_text(json.dumps(value))
            with self.assertRaises(CommandError):
                self.run_render('render', 'look-proof', recipe, '--width', 64, '--out', self.root/'invalid')
            self.assertFalse((self.root/'invalid').exists())


@unittest.skipUnless(Image and os.environ.get('AMBIANCE_TEST_NATIVE')=='1' and sys.platform=='darwin', 'Set AMBIANCE_TEST_NATIVE=1 for macOS media verification')
class SupersampledNativeTests(unittest.TestCase):
    def test_supersampled_picture_is_encoded_and_decoded_at_output_dimensions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); project = fixture(root)
            result = rendering.run(parse('render','video','--supersample',2,'--seconds',1,'--out',root/'video'),project)
            self.assertTrue(result['verification']['ok']); self.assertEqual(result['verification']['decoded_frames'],6)
            self.assertEqual(result['internal_canvas']['width'],128)
            for path in (root/'video/verification/contacts').glob('decoded-*.png'):
                with Image.open(path) as image:
                    self.assertEqual(image.size,(64,96))

    def test_finished_neutral_and_color_patches_survive_native_encoding_with_bounded_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); project = fixture(root)
            colors = [(v, v, v) for v in [16, 40, 72, 104, 136, 168, 200, 232]]
            source = project/'art/pattern.png'
            with Image.new('RGB', (128, 128)) as image:
                image.putdata([colors[x//16] if y < 64 else [(32,64,128),(128,64,32),(40,120,100),(140,70,130)][x//32]
                               for y in range(128) for x in range(128)])
                image.save(source)
            catalog_path = project/'art/library.json'; catalog = json.loads(catalog_path.read_text())
            catalog['assets'][0].update(width=128, height=128, sha256=hashlib.sha256(source.read_bytes()).hexdigest())
            catalog_path.write_text(json.dumps(catalog))
            scene_path = project/'edit/cut.json'; scene = json.loads(scene_path.read_text())
            scene['canvas'].update(width=128,height=128)
            scene['layers'][0].update(x=.5,y=.5,width=1,height=1)
            scene['layers'][0].pop('motion')
            scene['finishing']={'version':1,'working_space':'linear-srgb','output_space':'srgb','grade':{'exposure':0}}
            scene_path.write_text(json.dumps(scene))
            frame = rendering.run(parse('render','frame','--supersample',2,'--out',root/'frame'),project)
            movie = rendering.run(parse('render','video','--supersample',2,'--seconds',1,'--bitrate',1000000,'--out',root/'video'),project)
            self.assertTrue(movie['verification']['ok'])
            with Image.open(frame['output']) as png, Image.open(root/'video/verification/contacts/decoded-0000.png') as encoded:
                png = png.convert('RGB'); encoded = encoded.convert('RGB')
                try:
                    for x,y in [(8+16*i,32) for i in range(8)]+[(16+32*i,96) for i in range(4)]:
                        errors = [abs(png.getpixel((xx,yy))[c]-encoded.getpixel((xx,yy))[c])
                                  for yy in range(y-4,y+4) for xx in range(x-4,x+4) for c in range(3)]
                        self.assertLessEqual(sum(errors)/len(errors),8, (x,y))
                        self.assertLessEqual(max(errors),35, (x,y))
                finally:
                    png.close(); encoded.close()


if __name__=='__main__': unittest.main()
