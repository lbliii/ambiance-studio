import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from PIL import Image,ImageDraw
import asset_tool
from ambiance_studio import art_regions as ar, asset_prep as ap
from ambiance_studio.region_commands import edit_recipe


class Regions(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        (self.root/'ambiance-project.json').write_text('{}')
        image=Image.new('RGB',(80,60),'#253645');d=ImageDraw.Draw(image)
        d.ellipse([4,4,22,22],fill='#e3bf73');d.rectangle([30,25,60,50],fill='#cf7963')
        self.source=self.root/'source.png';image.save(self.source)
        self.recipe=ar.initial(self.root,self.source,'window')
        self.recipe['visible_mask']['polygons']=[{'operation':'add','points':[[4,4],[28,4],[28,36],[16,44],[4,36]]},
                                               {'operation':'subtract','points':[[14,4],[17,4],[17,36],[14,36]]}]
        self.recipe['frame'].update(aspect='square',padding=[8,8,8,8])
        self.recipe['sizing'].update(display_size=[50,82],quality_multiplier=1,export_size=[160,160])

    def tearDown(self): self.temp.cleanup()
    def packet(self,recipe=None):
        ar.save_draft(self.root,recipe or self.recipe,self.root/'draft')
        ar.build(self.root,self.root/'draft',self.root/'packet')
        return self.root/'packet'
    def returned(self,packet,edit=None,change=None,out='return'):
        spec=ar.read(packet/'return-template.json');spec['registration']={'edit_to_export':[1,0,0,1,0,0],'note':'Inspected fixed reference grid.'}
        if change: change(spec)
        ap.write(self.root/'alignment.json',spec)
        edit=edit or packet/'reference.png'
        return ar.return_art(self.root,packet,edit,self.root/'alignment.json',self.root/out)

    def test_square_padding_preserves_uniform_geometry_and_source(self):
        original=self.source.read_bytes();packet=self.packet();info=ar.read(packet/'report.json')
        m=info['source_to_export'];self.assertAlmostEqual(m[0],m[3]);self.assertEqual(m[1:3],[0,0])
        self.assertLess(info['frame_xyxy'][0],0)
        available=Image.open(packet/'source-availability.png');self.assertEqual(available.getpixel((0,0)),0)
        self.assertEqual(self.source.read_bytes(),original)
        roundtrip=ap.multiply(info['export_to_source'],m)
        for a,b in zip(roundtrip,[1,0,0,1,0,0]):self.assertAlmostEqual(a,b)
        self.assertNotEqual((packet/'guide.png').read_bytes(),(packet/'reference.png').read_bytes())

    def test_holes_and_native_composite_protect_original_pixels(self):
        packet=self.packet();edit=self.root/'red.png';Image.new('RGBA',(160,160),'red').save(edit)
        result=self.returned(packet,edit);composite=Image.open(self.root/'return/composite.png');original=Image.open(self.source).convert('RGBA')
        self.assertEqual(composite.getpixel((15,20)),original.getpixel((15,20)))
        self.assertEqual(composite.getpixel((0,0)),original.getpixel((0,0)))
        self.assertEqual(composite.getpixel((8,20)),(255,0,0,255))
        with Image.open(self.root/'return/patch.png') as im: self.assertEqual(im.size,(160,160))
        self.assertTrue(result['sizing']['ready'])

    def test_context_padding_increases_size_without_reducing_density(self):
        r=copy.deepcopy(self.recipe);r['sizing']['export_size']=None
        a=ar.geometry(r,ar.load_inputs(self.root,r))[0]
        r['frame']['padding']=[18]*4;b=ar.geometry(r,ar.load_inputs(self.root,r))[0]
        self.assertGreater(b['export_size'][0],a['export_size'][0]);self.assertAlmostEqual(a['required_density'],b['required_density'])
        self.assertGreaterEqual(b['effective_density'],b['required_density']-1e-9)

    def test_reopening_packet_finds_the_recorded_return_without_resubmission(self):
        from ambiance_studio import generation_ledger as ledger
        packet=self.packet();request=ar.inspect(self.root,packet)['request'];self.assertEqual(request['status'],'not-recorded')
        ledger.record(self.root,packet/'request-draft.json')
        image=packet/'reference.png';digest=ap.sha(image.read_bytes())
        ap.write(self.root/'retrieved.json',{'version':1,'event_id':'received','state':'retrieved','outputs':[{'file':ap.relative(self.root.resolve(),image),'sha256':digest,'provider_output_id':None}]})
        ledger.reconcile(self.root,request['local_request_id'],self.root/'retrieved.json')
        recovered=ar.inspect(self.root,packet)['request']
        self.assertEqual(recovered['status'],'retrieved');self.assertEqual(recovered['outputs'][0]['sha256'],digest)
        self.assertFalse(recovered['submits_requests'])

    def test_wrong_dimensions_missing_alignment_and_shift_correction(self):
        packet=self.packet()
        with self.assertRaises(ValueError): ar.return_art(self.root,packet,packet/'reference.png',packet/'return-template.json',self.root/'invalid')
        edit=self.root/'shift.png';Image.new('RGBA',(162,160),'blue').save(edit)
        with self.assertRaisesRegex(ValueError,'Unexpected returned'):self.returned(packet,edit)
        result=self.returned(packet,edit,lambda s:s.update(expected_edit_size=[162,160],registration={'edit_to_export':[1,0,0,1,-2,0],'note':'Corrected two pixel shift.'}))
        self.assertEqual(result['sizing']['missing_paint_pixels'],0)

    def test_compilation_retains_high_resolution_and_validates_dependencies(self):
        packet=self.packet();edit=self.root/'art.png';Image.new('RGBA',(160,160),'orange').save(edit);self.returned(packet,edit)
        asset_tool.build(self.root/'return/compiler.json',self.root/'pack')
        asset=ar.read(self.root/'pack/asset.json');self.assertEqual(asset['registration_mapping']['shared_scale'],1)
        self.assertEqual(asset['atlas']['cell_width'],164)
        self.assertIn('region_receipt',asset['provenance'])
        self.assertEqual(asset_tool.build(self.root/'pack/recipe.json',self.root/'pack')['status'],'cached')
        self.source.write_bytes(self.source.read_bytes()+b'changed')
        with self.assertRaisesRegex(ValueError,'dependency changed'):asset_tool.build(self.root/'return/compiler.json',self.root/'bad-pack')
        self.assertFalse((self.root/'bad-pack').exists())

    def test_explicit_shortfall_and_transparent_paint_are_not_ready(self):
        r=copy.deepcopy(self.recipe);r['sizing']['export_size']=[20,20]
        info=ar.geometry(r,ar.load_inputs(self.root,r))[0];self.assertFalse(info['ready'])
        r['sizing']['allow_under_target']=True;self.assertTrue(ar.geometry(r,ar.load_inputs(self.root,r))[0]['study'])
        packet=self.packet();edit=self.root/'empty.png';Image.new('RGBA',(160,160)).save(edit)
        result=self.returned(packet,edit);self.assertFalse(result['ready']);self.assertGreater(result['sizing']['missing_paint_pixels'],0)
        from types import SimpleNamespace
        from ambiance_studio.region_commands import run
        checked=run(SimpleNamespace(region_action='check',directory=self.root/'return'),self.root)
        self.assertFalse(checked['ok']);self.assertGreater(checked['missing_paint_pixels'],0)

    def test_invalid_edits_empty_region_and_source_races_leave_no_output(self):
        ar.save_draft(self.root,ar.initial(self.root,self.source,'empty'),self.root/'empty')
        with self.assertRaisesRegex(ValueError,'empty'):ar.build(self.root,self.root/'empty',self.root/'bad')
        with self.assertRaises(ValueError):edit_recipe(self.recipe,{'version':1,'operations':[{'op':'append-polygon','value':{'operation':'add','points':[[1,1],[1,1],[1,1]]}}]})
        self.assertEqual(len(self.recipe['visible_mask']['polygons']),2)
        original=ar.pictures
        def changed(*args,**kwargs):
            result=original(*args,**kwargs);self.source.write_bytes(self.source.read_bytes()+b'changed');return result
        with patch.object(ar,'pictures',side_effect=changed),self.assertRaisesRegex(ValueError,'changed'):
            ar.save_draft(self.root,self.recipe,self.root/'race')
        self.assertFalse((self.root/'race').exists())

    def test_imported_soft_alpha_survives_outside_polygon_edits(self):
        mask=Image.new('L',(80,60),0);ImageDraw.Draw(mask).rectangle([3,3,30,35],fill=110);mask.save(self.root/'soft.png')
        r=copy.deepcopy(self.recipe);r['visible_mask']={'image':ar.record(self.root,self.root/'soft.png'),'polygons':[]}
        native=ar.geometry(r,ar.load_inputs(self.root,r))[2];self.assertEqual(native.getpixel((10,10)),110)
        ar.save_draft(self.root,r,self.root/'draft');ar.build(self.root,self.root/'draft',self.root/'packet')
        exported=Image.open(self.root/'packet/visible-export.png');self.assertGreater(exported.histogram()[110],0)

    def test_browser_draft_and_cli_build_share_rasters_and_preserve_inputs(self):
        from ambiance_studio.region_server import handler_for
        from http.server import HTTPServer
        import threading
        import urllib.request
        import urllib.error
        import base64
        packet=self.packet();original={p.name:p.read_bytes() for p in packet.iterdir() if p.is_file()}
        server=HTTPServer(('127.0.0.1',0),handler_for(packet));thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        address=f'http://127.0.0.1:{server.server_port}'
        try:
            candidate=copy.deepcopy(self.recipe);candidate['frame']['padding']=[10]*4
            request=urllib.request.Request(address+'/api/preview',data=json.dumps(candidate).encode(),headers={'Content-Type':'application/json'})
            reply=json.loads(urllib.request.urlopen(request).read())['data']
            ap.write(self.root/'browser-export.json',candidate);ar.build(self.root,self.root/'browser-export.json',self.root/'browser-build')
            with Image.open(io.BytesIO(base64.b64decode(reply['images']['visible-export'].split(',')[1]))) as a,Image.open(self.root/'browser-build/visible-export.png') as b:
                self.assertEqual(a.tobytes(),b.tobytes())
            bad=urllib.request.Request(address+'/api/preview',data=json.dumps(candidate).encode(),headers={'Content-Type':'application/json','Origin':'https://example.invalid'})
            with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(bad)
            self.assertEqual(error.exception.code,403)
            error.exception.close()
            with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(address+'/inputs/source')
            error.exception.close()
            self.assertEqual(original,{p.name:p.read_bytes() for p in packet.iterdir() if p.is_file()})
        finally:server.shutdown();thread.join();server.server_close()

    def test_scene_context_is_current_for_builds_and_snapshotted_for_admission(self):
        scene={'version':1,'id':'test','canvas':{'width':80,'height':80,'fps':4,'loop_seconds':2,'background':'#000000'},
               'camera':{'overscan':1,'x_amplitude':0,'y_amplitude':0,'zoom_amplitude':0},'groups':[],
               'layers':[{'id':'base','asset':'source','x':0,'y':0,'width':1,'height':.75,'anchor':[0,0],'scale':1,'rotation':0,'opacity':1,'visible':True,'blend':'source-over','depth':0}]}
        source=self.recipe['source']
        catalog={'version':1,'assets':[{'id':'source','width':80,'height':60,'registration_mapping':{'version':1,'cell_size':[80,60],'reference':source,'cels':[{'reference_to_cell':[1,0,0,1,0,0]}]}}]}
        for name,value in [('scene',scene),('catalog',catalog),('scope',{'intended_views':['authored']})]:ap.write(self.root/(name+'.json'),value)
        self.recipe['context']={**{k:ar.file_ref(self.root,self.root/(k+'.json')) for k in ('scene','catalog','scope')},'base':'base','views':['authored'],'start_frame':0,'frames':None}
        self.recipe['sizing']['mode']='scene'
        packet=self.packet();edit=self.root/'paint.png';Image.new('RGBA',(160,160),'blue').save(edit);self.returned(packet,edit)
        scene['layers'][0]['scale']=2;ap.write(self.root/'scene.json',scene)
        with self.assertRaisesRegex(ValueError,'input changed'):ar.build(self.root,self.root/'draft',self.root/'stale')
        self.assertIn('scene',ar.inspect(self.root,packet)['changed_working_inputs'])
        asset_tool.build(self.root/'return/compiler.json',self.root/'pack')
        from ambiance_studio.assets import inspect_pack
        self.assertTrue(inspect_pack(self.root/'pack')['ok'])


if __name__=='__main__':unittest.main(verbosity=2)
