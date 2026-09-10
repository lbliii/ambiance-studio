"""Independent raster fixtures for explicit crop/return and compiler placement."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from ambiance_studio import asset_prep as prep
from tools import asset_tool


def raster_copy(path):
    with Image.open(path) as raw:
        raw.load()
        return raw.copy()


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);(self.root/'ambiance-project.json').write_text('{"version":1}')
        self.source=self.root/'reference.png';self.recipe=self.root/'crop.json'
        image=Image.new('RGB',(8,6));image.putdata([(x*25,y*35,(x+y)*15) for y in range(6) for x in range(8)]);image.save(self.source)
        self.recipe.write_text(json.dumps({'version':1,'crop_xyxy':[2,1,6,5],'export_size':[8,8],'resampling':'nearest'}))

    def crop(self): return prep.crop(self.root,self.source,self.recipe,self.root/'crop')
    def mapping(self,correction=None):
        path=self.root/'return.json';spec=prep.load(self.root/'crop/return-template.json')
        spec['registration']['edit_to_export']=correction or [1,0,0,1,0,0];prep.write(path,spec);return path
    def returned(self,mapping=None,edit=None,out='return'):
        return prep.return_edit(self.root,edit or self.root/'crop/crop.png',mapping or self.mapping(),self.root/out)

    def test_preflight_distinguishes_rgb_opaque_rgba_and_real_alpha(self):
        checker=Image.new('RGB',(8,8));checker.putdata([(180,180,180) if (x+y)%2 else (240,240,240) for y in range(8) for x in range(8)])
        for name,image in [('rgb',checker),('rgba',checker.convert('RGBA')),('alpha',checker.convert('RGBA'))]:
            if name=='alpha': image.putpixel((0,0),(50,20,10,0));image.putpixel((1,0),(50,20,10,120))
            file=self.root/f'{name}.png';image.save(file);r=prep.preflight(file,self.root/name)
            self.assertEqual(r['source']['has_alpha_channel'],name!='rgb')
            self.assertEqual(r['alpha']['fully_transparent_pixels'],int(name=='alpha'))
            self.assertEqual(r['alpha']['partially_transparent_pixels'],int(name=='alpha'))
            self.assertTrue((self.root/name/'light.png').is_file());self.assertTrue((self.root/name/'dark.png').is_file())
        self.assertEqual(prep.load(self.root/'rgb/report.json')['alpha']['opaque_pixels'],64)

    def test_preflight_rejects_source_changed_while_building_previews(self):
        original_previews=prep.previews
        def changing(stage,image):
            original_previews(stage,image)
            self.source.write_bytes(self.source.read_bytes()+b'changed after decode')
        out=self.root/'preflight-race'
        with patch.object(prep,'previews',side_effect=changing), self.assertRaisesRegex(ValueError,'source changed'):
            prep.preflight(self.source,out)
        self.assertFalse(out.exists())
        self.assertFalse(any(self.root.glob('.asset-prep-*')))

    def test_nearest_crop_return_preserves_original_and_native_coordinates(self):
        before=self.source.read_bytes();self.crop();r=self.returned()
        self.assertEqual(self.source.read_bytes(),before)
        self.assertEqual(raster_copy(r['composite']).convert('RGBA').tobytes(),raster_copy(self.source).convert('RGBA').tobytes())
        m=prep.load(r['mapping']);self.assertEqual(m['image_to_reference'],[1,0,0,1,2,1]);self.assertEqual(m['native_crop_xyxy'],[2,1,6,5])
        self.assertEqual(m['reference']['sha256'],hashlib.sha256(before).hexdigest())

    def test_missing_registration_and_unexpected_return_size_fail(self):
        self.crop()
        with self.assertRaisesRegex(ValueError,'explicit finite'): self.returned(self.root/'crop/return-template.json')
        edit=self.root/'resized.png';raster_copy(self.root/'crop/crop.png').resize((10,8)).save(edit)
        with self.assertRaisesRegex(ValueError,'Unexpected returned geometry'):self.returned(edit=edit)
        self.assertFalse((self.root/'return').exists())

    def test_explicit_translation_returns_enlarged_shifted_edit(self):
        self.crop();raw=raster_copy(self.root/'crop/crop.png');shifted=Image.new('RGBA',(10,8));shifted.paste(raw,(2,0));edit=self.root/'shifted.png';shifted.save(edit)
        mapping=self.mapping([1,0,0,1,-2,0]);spec=prep.load(mapping);spec['expected_edit_size']=[10,8];prep.write(mapping,spec)
        result=self.returned(mapping,edit)
        self.assertEqual(raster_copy(result['composite']).convert('RGBA').tobytes(),raster_copy(self.source).convert('RGBA').tobytes())

    def test_grayscale_mask_limits_replacement_and_is_hashed(self):
        self.crop();edit=self.root/'red.png';Image.new('RGB',(8,8),'red').save(edit)
        mask=self.root/'mask.png';im=Image.new('L',(4,4));ImageDraw.Draw(im).rectangle((0,0,1,3),fill=255);im.save(mask)
        mapping=self.mapping();spec=prep.load(mapping);spec['blend_mask']={'kind':'image','file':'mask.png','sha256':prep.sha(mask.read_bytes())};prep.write(mapping,spec)
        result=self.returned(mapping,edit);composite=raster_copy(result['composite']);original=raster_copy(self.source)
        self.assertEqual(composite.getpixel((2,1)),(255,0,0,255));self.assertEqual(composite.getpixel((4,1))[:3],original.getpixel((4,1)))
        mask.write_bytes(mask.read_bytes()+b'changed')
        with self.assertRaisesRegex(ValueError,'mask changed'):self.returned(mapping,edit,out='invalid')

    def test_original_tamper_path_escape_and_existing_destination_fail(self):
        self.crop();self.source.write_bytes(self.source.read_bytes()+b'changed')
        with self.assertRaisesRegex(ValueError,'identity changed'):self.returned()
        with self.assertRaisesRegex(ValueError,'Output exists'):self.crop()
        with self.assertRaisesRegex(ValueError,'inside'):prep.project_file(self.root,'../elsewhere.png')
        occupied=self.root/'occupied';occupied.mkdir();(occupied/'keep').write_text('original')
        with self.assertRaisesRegex(ValueError,'Output exists'):prep.preflight(self.source,occupied)
        self.assertEqual((occupied/'keep').read_text(),'original')

    def test_mapped_compiler_composes_resize_padding_and_pivot(self):
        self.crop();mapping=self.root/'crop/source-mapping.json';recipe=self.root/'compile.json'
        spec={'version':1,'id':'mapped-v1','input':{'frames':['crop/crop.png'],'allow_opaque':True},'source_mapping':{'file':'crop/source-mapping.json','sha256':prep.sha(mapping.read_bytes())},'registration':{'mode':'fixed','point':[4,4],'target':[.5,.5]},'output':{'cell_size':[12,12],'columns':1,'padding':2}}
        prep.write(recipe,spec);out=self.root/'pack';asset_tool.build(recipe,out)
        asset=prep.load(out/'asset.json');m=asset['registration_mapping']
        self.assertEqual(m['shared_scale'],1);self.assertEqual(m['cels'][0]['raw_cel_to_cell'],[1,0,0,1,2,2]);self.assertEqual(m['cels'][0]['reference_to_cell'],[2,0,0,2,-2,0])
        self.assertEqual(m['reference']['file'],'reference.png');self.assertEqual(m['input_sources'][0]['width'],8)
        self.assertEqual(asset_tool.build(out/'recipe.json',out)['status'],'cached')
        self.source.write_bytes(self.source.read_bytes()+b'changed')
        with self.assertRaisesRegex(ValueError,'identity changed'):asset_tool.build(recipe,self.root/'changed')

    def test_sheet_mapping_uses_whole_source_coordinates(self):
        sheet=Image.new('RGBA',(16,8));ImageDraw.Draw(sheet).rectangle((2,2,5,5),fill='orange');ImageDraw.Draw(sheet).rectangle((10,2,13,5),fill='orange');sheet.save(self.root/'sheet.png')
        recipe=self.root/'sheet.json';prep.write(recipe,{'version':1,'id':'sheet-v1','input':{'sheet':'sheet.png','columns':2,'rows':1,'frame_count':2},'registration':{'mode':'fixed','point':[4,4],'target':[.5,.5]},'output':{'cell_size':[12,12],'columns':2,'padding':2}})
        asset_tool.build(recipe,self.root/'sheet-pack');m=prep.load(self.root/'sheet-pack/asset.json')['registration_mapping']
        self.assertEqual(m['cels'][1]['source_rect'],[8,0,16,8]);self.assertEqual(m['cels'][1]['source_to_cell'],[1,0,0,1,-6,2]);self.assertEqual(m['cels'][1]['raw_cel_to_cell'],[1,0,0,1,2,2])


if __name__=='__main__':unittest.main(verbosity=2)
