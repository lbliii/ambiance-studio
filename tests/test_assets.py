import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('asset_tool',ROOT/'tools/asset_tool.py')
tool=importlib.util.module_from_spec(spec);spec.loader.exec_module(tool)

class AssetTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.recipe=self.root/'recipe.json';self.out=self.root/'pack'
        # Same silhouette deliberately displaced in two independent source cels.
        for i,(dx,dy) in enumerate([(0,0),(7,-4)]):
            im=Image.new('RGBA',(64,64));d=ImageDraw.Draw(im)
            d.rectangle((18+dx,12+dy,29+dx,39+dy),fill=(230,120,40,255));im.save(self.root/f'{i}.png')
        self.data={'version':1,'id':'fixture-v1','input':{'frames':['0.png','1.png']},
          'registration':{'mode':'landmarks','points':[[24,40],[31,36]],'target':[.5,.75]},
          'output':{'cell_size':[64,64],'columns':2,'padding':2}}
        self.save()
    def save(self): self.recipe.write_text(json.dumps(self.data))
    def build(self): return tool.build(self.recipe,self.out)
    def test_landmarks_remove_known_displacement_without_scale_change(self):
        original=[tool.sha(self.root/f'{i}.png') for i in range(2)]
        self.build();im=Image.open(self.out/'atlas.png')
        self.assertEqual(im.crop((0,0,64,64)).tobytes(),im.crop((64,0,128,64)).tobytes())
        report=json.loads((self.out/'report.json').read_text());self.assertEqual(report['shared_scale'],1)
        self.assertEqual([tool.sha(self.root/f'{i}.png') for i in range(2)],original)
    def test_cache_hit_and_tamper_detection(self):
        self.build();self.assertEqual(self.build()['status'],'cached')
        (self.out/'atlas.png').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'differs'):self.build()
    def test_changed_recipe_requires_new_version_directory(self):
        self.build();self.data['registration']['target']=[.5,.7];self.save()
        with self.assertRaisesRegex(ValueError,'differs'):self.build()
    def test_pack_recipe_resolves_originals_and_hits_same_cache(self):
        self.build()
        self.assertEqual(tool.build(self.out/'recipe.json',self.out)['status'],'cached')
    def test_empty_frame_rejected(self):
        Image.new('RGBA',(64,64)).save(self.root/'1.png')
        with self.assertRaisesRegex(ValueError,'empty'):self.build()
    def test_opaque_proof_rejected(self):
        Image.new('RGB',(64,64),'gray').save(self.root/'1.png')
        with self.assertRaisesRegex(ValueError,'opaque'):self.build()
    def test_one_scale_preserves_relative_shape_size(self):
        im=Image.new('RGBA',(64,64));ImageDraw.Draw(im).rectangle((12,4,35,39),fill='orange');im.save(self.root/'1.png')
        self.data['registration']['points'][1]=[24,40];self.save();self.build()
        im=Image.open(self.out/'atlas.png');a=im.crop((0,0,64,64)).getbbox();b=im.crop((64,0,128,64)).getbbox()
        self.assertEqual(b[2]-b[0],2*(a[2]-a[0]))
    def test_bottom_center_estimate_recovers_shift_and_warns(self):
        self.data['registration']['mode']='bottom-center';self.save();self.build()
        report=json.loads((self.out/'report.json').read_text())
        self.assertTrue(any('silhouette estimate' in x for x in report['warnings']))
        im=Image.open(self.out/'atlas.png')
        self.assertEqual(im.crop((0,0,64,64)).tobytes(),im.crop((64,0,128,64)).tobytes())
    def test_landmark_count_rejected(self):
        self.data['registration']['points'].pop();self.save()
        with self.assertRaisesRegex(ValueError,'one source-pixel'):self.build()
    def test_catalog_id_protected(self):
        self.build();catalog=self.root/'assets/catalog.json';catalog.parent.mkdir();catalog.write_text('{"assets":[]}')
        self.assertEqual(tool.admit(self.out,catalog)['status'],'admitted')
        self.assertEqual(tool.admit(self.out,catalog)['status'],'already admitted')
        data=json.loads(catalog.read_text());data['assets'][0]['pivot']=[0,0];catalog.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,'already exists'):tool.admit(self.out,catalog)

if __name__=='__main__':unittest.main(verbosity=2)
