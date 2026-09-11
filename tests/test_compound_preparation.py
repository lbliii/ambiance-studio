import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from ambiance_studio import compound_preparation as c, preparation as s, asset_prep as p, preparation_commands as commands
from tools import asset_tool


def poly(x0,y0,x1,y1):return {'operation':'add','points':[[x0,y0],[x1,y0],[x1,y1],[x0,y1]]}


class CompoundPreparationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name).resolve()
        p.write(self.root/'ambiance-project.json',{'version':1,'scene':'scene.json','catalog':'assets/catalog.json'})
        (self.root/'assets').mkdir();p.write(self.root/'assets/catalog.json',{'version':1,'assets':[]})
        backing=Image.new('RGBA',(48,64),'#102030');backing.save(self.root/'backing.png');source=backing.copy();d=ImageDraw.Draw(source)
        d.rectangle((12,20,24,37),fill='#ffee55');d.rectangle((28,24,35,32),fill='#cc8855');d.rectangle((6,36,41,39),fill='#98aabb');source.save(self.root/'source.png')
        mask=Image.new('L',(48,64));mask.putpixel((12,20),7);ImageDraw.Draw(mask).rectangle((13,21,23,34),fill=255);mask.save(self.root/'soft.png')
        ref=lambda f:s.image_record(self.root,self.root/f)
        self.recipe={'format':c.FORMAT,'version':1,'path_base':'project','title':'Two source-backed movable pieces','source':ref('source.png'),'backing':ref('backing.png'),
                     'backing_to_source':[1,0,0,1,0.25,-0.125],'resampling':'bicubic','removal':{'polygons':[poly(11,19,36,38)]},'seconds':2,'context':None,
                     'parts':[{'id':'body','kind':'cutout','mask':{'polygons':[],'image':ref('soft.png')},'pivot':[18.25,35.125],'motion':{'delta':[0,-6],'rotation_degrees':1.5},'companions':[{'id':'body-light','image':ref('soft.png')}]},
                              {'id':'handle','kind':'cutout','mask':{'polygons':[poly(28,24,35,32)]},'pivot':[29.5,28.25],'motion':{'delta':[3,0],'rotation_degrees':-4}},
                              {'id':'rail','kind':'occluder','mask':{'polygons':[poly(6,36,41,39)]},'pivot':[0,0]}]}
        self.file=self.root/'recipe.json';p.write(self.file,self.recipe)
    def build(self,name='prepared'):return c.build(self.root,self.file,self.root/name)
    def test_related_parts_companion_alpha_and_hidden_backing_remain_independent(self):
        images,facts,warnings=c.evaluate(self.recipe,c.load_inputs(self.root,self.recipe))
        self.assertEqual(images['body'].getpixel((12,20))[3],7);self.assertEqual(images['body-light'].getpixel((12,20))[3],7)
        self.assertEqual(images['body'].getpixel((18,37))[3],0);self.assertEqual(images['rail'].getpixel((18,37))[3],255)
        self.assertEqual(images['backing'].getpixel((18,27))[:3],(16,32,48));self.assertFalse(facts['cutout_occluder_overlaps'])
    def test_immutable_build_compiler_and_companion_share_exact_source_map(self):
        self.build();c.build(self.root,self.root/'prepared/recipe.json',self.root/'rebuilt')
        self.assertEqual((self.root/'prepared/images/body.png').read_bytes(),(self.root/'rebuilt/images/body.png').read_bytes())
        maps=[]
        for id in ['body','handle','rail','body-light']:
            asset_tool.build(self.root/'prepared/compiler'/f'{id}.json',self.root/('pack-'+id));maps.append(p.load(self.root/('pack-'+id)/'asset.json')['registration_mapping']['cels'][0]['reference_to_cell'])
        self.assertEqual(maps,[[1,0,0,1,2,2]]*4)
        self.assertEqual(p.load(self.root/'prepared/preparation-receipt.json')['outputs']['body-light']['owner'],'body')
        with self.assertRaisesRegex(ValueError,'Output exists'):self.build()
    def test_stale_recipe_and_invalid_late_batch_are_atomic(self):
        batch=self.root/'batch.json';p.write(batch,{'version':1,'operations':[{'op':'set-pivot','part':'body','value':[17.5,30.25]},{'op':'set-motion','part':'missing','value':{}}]})
        before=self.file.read_bytes()
        with self.assertRaisesRegex(ValueError,'exact --expect'):c.edit(self.root,self.file,batch,self.root/'bad','0'*64)
        with self.assertRaisesRegex(ValueError,'unknown part'):c.edit(self.root,self.file,batch,self.root/'bad',p.sha(before))
        self.assertEqual(before,self.file.read_bytes());self.assertFalse((self.root/'bad').exists())
        p.write(batch,{'version':1,'operations':[{'op':'set-pivot','part':'body','value':[17.5,30.25]}]})
        with patch.object(c,'checkpoint',side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):c.edit(self.root,self.file,batch,self.root/'interrupted',p.sha(before))
        result=c.edit(self.root,self.file,batch,self.root/'resumed',p.sha(before));self.assertEqual(p.load(result['recipe'])['parts'][0]['pivot'],[17.5,30.25])
        self.assertEqual((self.root/'resumed/parent-recipe.json').read_bytes(),before)
    def test_changed_source_companion_and_independent_correction_rejected(self):
        self.build();recipe=p.load(self.root/'prepared/compiler/body.json');recipe['registration']['point']=[2,2];p.write(self.root/'prepared/compiler/bad.json',recipe)
        with self.assertRaisesRegex(ValueError,'recorded fixed registration'):asset_tool.build(self.root/'prepared/compiler/bad.json',self.root/'bad')
        self.assertFalse((self.root/'bad').exists())
        (self.root/'soft.png').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'Source identity changed'):asset_tool.build(self.root/'prepared/compiler/body.json',self.root/'bad')
        self.assertFalse((self.root/'bad').exists())
    def test_diagnostics_expose_missing_backing_and_stuck_foreground(self):
        r=copy.deepcopy(self.recipe);r['parts'][0]['mask']={'polygons':[poly(12,20,24,37)]};r['backing_to_source'][4]=48
        _,facts,warnings=c.evaluate(r,c.load_inputs(self.root,r))
        self.assertTrue(facts['cutout_occluder_overlaps']);self.assertGreater(facts['parts']['body']['removal_without_opaque_backing_pixels'],0)
        self.assertTrue(any('does not fully cover' in w['message'] for w in warnings))
    def test_public_inspect_edit_build_and_rest_raster(self):
        inspect=commands.cli(self.root,'asset','prepare','inspect',self.file)
        self.assertEqual(inspect['parts'][0]['pivot_source_px'],[18.25,35.125])
        batch=self.root/'batch.json';p.write(batch,{'version':1,'operations':[{'op':'set-alignment','value':[1,0,0,1,0,0]}]})
        edit=commands.cli(self.root,'asset','prepare','edit',self.file,'--batch',batch,'--expect-sha256',inspect['sha256'],'--out',self.root/'edit')
        build=commands.cli(self.root,'asset','prepare','build',edit['recipe'],'--out',self.root/'built')
        commands.cli(build['preview_project'],'render','frame','--time',0,'--out',self.root/'frame')
        png=next((self.root/'frame').glob('*.png'))
        with Image.open(png) as image:self.assertEqual(image.getpixel((18,37))[:3],(152,170,187))


if __name__=='__main__':unittest.main()
