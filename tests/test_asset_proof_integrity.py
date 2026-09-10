"""Asset proof must show the selected source geometry and verified registration."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from PIL import Image,ImageDraw
from ambiance_studio import assets
from tools import asset_tool
import studio

class AssetProofIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        (self.root/'assets').mkdir()
        image=Image.new('RGBA',(48,24));draw=ImageDraw.Draw(image)
        draw.rectangle((7,4,16,20),fill='#ffaa33');draw.rectangle((29,4,41,20),fill='#ffa033')
        image.save(self.root/'source.png')
        recipe={'version':1,'id':'proof-fixture','input':{'sheet':'source.png','columns':2,'rows':1,'frame_count':2},
                'registration':{'mode':'fixed','point':[12,20],'target':[.5,.75]},
                'output':{'cell_size':[32,32],'columns':2,'padding':2}}
        studio.write(self.root/'recipe.json',recipe)
        self.pack=self.root/'assets/pack';asset_tool.build(self.root/'recipe.json',self.pack)
        self.catalog=self.root/'assets/catalog.json';studio.write(self.catalog,{'version':1,'assets':[]})
        asset_tool.admit(self.pack,self.catalog)
        studio.write(self.root/'ambiance-project.json',{'version':1,'catalog':'assets/catalog.json','scene':'scene.json'})

    def tearDown(self):self.temp.cleanup()

    def proof(self):return assets.proof('proof-fixture',self.root/'proof',project=self.root)

    def test_catalog_and_direct_pack_proofs_keep_original_registration(self):
        result=self.proof();self.assertEqual(result['anchor_input'],'original recipe input frames')
        self.assertTrue((self.root/'proof/index.html').is_file())
        direct=assets.proof(str(self.pack),self.root/'direct')
        self.assertEqual(direct['source_sha256'],result['source_sha256'])

    def test_changed_pack_recipe_is_not_reused_by_catalog_proof(self):
        recipe=studio.read(self.pack/'recipe.json');recipe['registration']['point']=[4,4]
        studio.write(self.pack/'recipe.json',recipe)
        with self.assertRaisesRegex(ValueError,'Pack outputs changed'):self.proof()
        self.assertFalse((self.root/'proof').exists())

    def test_recipe_input_must_match_recorded_source_even_if_report_is_updated(self):
        Image.new('RGBA',(48,24),'red').save(self.root/'different.png')
        recipe=studio.read(self.pack/'recipe.json');recipe['input']['sheet']='../../different.png'
        studio.write(self.pack/'recipe.json',recipe)
        report=studio.read(self.pack/'report.json');report['outputs']['recipe.json']=studio.digest(self.pack/'recipe.json')
        studio.write(self.pack/'report.json',report)
        with self.assertRaisesRegex(ValueError,'input order/path differs'):self.proof()

    def test_report_pivot_changes_cannot_silently_move_exported_anchors(self):
        report=studio.read(self.pack/'report.json');report['frames'][0]['source_pivot']=[1,1]
        studio.write(self.pack/'report.json',report)
        with self.assertRaisesRegex(ValueError,'source pivots differ'):self.proof()

    def test_catalog_registration_cannot_relabel_a_different_pack(self):
        catalog=studio.read(self.catalog);catalog['assets'][0]['pivot']=[.5,.5];studio.write(self.catalog,catalog)
        with self.assertRaisesRegex(ValueError,'Catalog asset differs'):self.proof()

    def test_changed_original_source_leaves_no_finished_proof(self):
        Image.new('RGBA',(48,24),'green').save(self.root/'source.png')
        with self.assertRaisesRegex(ValueError,'Recipe source changed'):self.proof()
        self.assertFalse((self.root/'proof').exists())

    def test_decoded_dimensions_must_match_static_and_atlas_metadata(self):
        original=studio.read(self.catalog)['assets'][0]
        for asset in [dict(original,width=12),{'id':'static','file':'source.png','width':1,'height':1,'sha256':studio.digest(self.root/'source.png')}]:
            with self.assertRaisesRegex(ValueError,'dimensions do not match'):assets.read_asset(asset,self.root)

    def test_uncompiled_library_study_still_produces_prepared_anchor_proof(self):
        studio.write(self.catalog,{'version':1,'assets':[{'id':'study','file':'source.png','width':48,'height':24,'sha256':studio.digest(self.root/'source.png')} ]})
        result=assets.proof('study',self.root/'proof',project=self.root)
        self.assertTrue(result['anchor_input'].startswith('prepared cels'))

    def test_pack_report_cannot_omit_output_hashes(self):
        report=studio.read(self.pack/'report.json');report['outputs']={};studio.write(self.pack/'report.json',report)
        with self.assertRaisesRegex(ValueError,'needs hashed'):assets.inspect_pack(self.pack)

if __name__=='__main__':unittest.main()
