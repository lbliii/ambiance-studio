"""Public named-view rendering and immutable paired-proof artifacts."""
import json
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_rendering import fixture, parse, Image
from ambiance_studio import native_media, rendering, preview, cli, revisions
from ambiance_studio.errors import CommandError


@unittest.skipUnless(Image and rendering.capabilities()['frame_render'], 'Requires Pillow and Node Canvas')
class ViewRenderTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.project=fixture(self.root)
        self.scene_path=self.project/'edit/cut.json'
        scene=json.loads(self.scene_path.read_text());scene['canvas'].update(width=160,height=160)
        scene['framing']={'version':1,'views':{
            'portrait':{'rect_scene_px':[35,0,90,160],'output':{'width':1080,'height':1920}},
            'landscape':{'rect_scene_px':[0,35,160,90],'output':{'width':1920,'height':1080}}}}
        self.scene_path.write_text(json.dumps(scene));self.source=self.scene_path.read_bytes()

    def render(self,*args):
        return rendering.run(parse('render',*args),self.project)

    def test_named_frame_and_disabled_proof_keep_selected_dimensions_and_source(self):
        frame=self.render('frame','--view','landscape','--width','160','--out',self.root/'frame')
        self.assertEqual(frame['view']['view']['id'],'landscape')
        self.assertEqual(frame['view']['output'],{'width':160,'height':90})
        with Image.open(frame['output']) as image:self.assertEqual(image.size,(160,90))
        proof=self.render('proof','--view','portrait','--width','90','--seconds','1','--disable','moving','--out',self.root/'proof')
        self.assertEqual(proof['variants'],2)
        with Image.open(self.root/'proof/current/00000.png') as image:self.assertEqual(image.size,(90,160))
        self.assertNotEqual((self.root/'proof/current/00000.png').read_bytes(),(self.root/'proof/disabled/00000.png').read_bytes())
        self.assertEqual(self.scene_path.read_bytes(),self.source)

    def test_paired_frames_have_common_times_hashes_and_verified_preview(self):
        result=self.render('views-proof','--view','portrait','--view','landscape','--seconds','1','--start','.5','--long-edge','160','--out',self.root/'pair')
        report=json.loads(Path(result['report']).read_text())
        self.assertEqual(report['stage_frames_rendered'],6)
        self.assertEqual(report['sample_times'],[.5+n/6 for n in range(6)])
        self.assertIsNone(report['render_canvas'])
        self.assertEqual([v['output'] for v in report['outputs']],[{'width':90,'height':160},{'width':160,'height':90}])
        routes=preview.views_proof_routes(self.root/'pair');self.assertEqual(len(routes),14+3*len(report['alpha_diagnostics']))
        self.assertNotIn('outputs',result)  # Per-frame evidence stays in the report.
        frame=self.root/'pair/portrait/00000.png';frame.write_bytes(frame.read_bytes()+b'tampered')
        with self.assertRaisesRegex(ValueError,'changed'):preview.views_proof_routes(self.root/'pair')

    def alpha_proof(self):
        scene=json.loads(self.source);scene['layers']=scene['layers'][:1]
        scene['layers'][0].update(x=.5,y=.5,width=1,height=1)
        scene['layers'][0].pop('motion',None)
        self.scene_path.write_text(json.dumps(scene))
        source=self.project/'art/pattern.png'
        image=Image.new('RGBA',(160,160),(25,70,110,255))
        image.paste((0,0,0,0),(72,16,80,24));image.paste((0,0,0,0),(88,0,96,1));image.save(source)
        catalog_path=self.project/'art/library.json';catalog=json.loads(catalog_path.read_text())
        catalog['assets'][0].update(width=160,height=160,sha256=hashlib.sha256(source.read_bytes()).hexdigest())
        catalog_path.write_text(json.dumps(catalog))
        result=self.render('views-proof','--view','portrait','--view','landscape','--start','.5','--seconds','.5','--long-edge','160','--out',self.root/'alpha')
        return result,json.loads(Path(result['report']).read_text())

    def test_alpha_proof_preserves_holes_and_lists_exact_source_frame_artifacts(self):
        result,report=self.alpha_proof();out=Path(result['output']).parent
        self.assertTrue(report['review_needed']);self.assertFalse(report['pixels']['ok'])
        self.assertEqual(len(report['alpha_diagnostics']),1)
        item=report['alpha_diagnostics'][0];self.assertEqual(item['view_id'],'portrait')
        self.assertLess(item['time_seconds'],report['start_seconds'])
        metadata=json.loads((out/item['metadata']['file']).read_text())
        self.assertEqual(metadata['source']['scene_sha256'],hashlib.sha256(self.scene_path.read_bytes()).hexdigest())
        self.assertEqual(metadata['view']['rect_scene_px'],[35,0,90,160]);self.assertEqual(metadata['resolution'],[90,160])
        for name in ['scene','catalog']:
            self.assertEqual(metadata['source'][name+'_sha256'],hashlib.sha256((out/(name+'.snapshot.json')).read_bytes()).hexdigest())
        for name,digest in metadata['source']['renderer_sources'].items():
            self.assertEqual(digest,hashlib.sha256((Path(__file__).resolve().parents[1]/name).read_bytes()).hexdigest())
        with Image.open(out/item['frame_image']['file']) as image,Image.open(out/item['heatmap']['file']) as heat:
            raw=list(zip(*[iter(image.convert('RGBA').tobytes())]*4));marked=list(zip(*[iter(heat.convert('RGBA').tobytes())]*4))
            holes=[(i%90,i//90,rgba[3]) for i,rgba in enumerate(raw) if rgba[3]<254]
            self.assertEqual(len(holes),item['alpha']['all']['count'])
            # Independent source-to-crop landmarks: the known 8x8 hole is at
            # scene (72,16), hence view (37,16). Allow the stated raster fringe.
            self.assertEqual(raw[20*90+41][3],0)
            self.assertTrue(all((35<=x<47 and 14<=y<26) or (51<=x<63 and 0<=y<3) for x,y,a in holes))
            for i,(rgba,color) in enumerate(zip(raw,marked)):
                if rgba[3]>=254:self.assertEqual(color[3],0)
                else:self.assertEqual(color,(255,170,0,255) if i%90 in [0,89] or i//90 in [0,159] else (255,0,170,255))
        with Image.open(out/'portrait/00000.png') as image:self.assertEqual(image.getextrema()[3],(255,255))
        routes=preview.views_proof_routes(out)
        for key in ['metadata','frame_image','heatmap']:
            artifact=item[key];self.assertEqual(artifact['path_base'],'artifact-relative')
            self.assertEqual(hashlib.sha256(routes['/'+artifact['file']]).hexdigest(),artifact['sha256'])
        self.assertNotIn('alpha_diagnostics',result)  # Ordinary CLI envelope remains compact.
        self.assertIn('Painted alpha diagnostics',Path(result['output']).read_text())

    def test_alpha_preview_rejects_changed_missing_escaping_or_misattributed_files(self):
        result,report=self.alpha_proof();out=Path(result['output']).parent;receipt=Path(result['report']);original=receipt.read_bytes()
        item=report['alpha_diagnostics'][0]
        for key in ['metadata','frame_image','heatmap']:
            file=out/item[key]['file'];data=file.read_bytes();file.write_bytes(data+b'changed')
            with self.assertRaisesRegex(ValueError,'changed'):preview.views_proof_routes(out)
            file.unlink()
            with self.assertRaises(FileNotFoundError):preview.views_proof_routes(out)
            file.write_bytes(data)
        item['heatmap']['file']='../escape.png';receipt.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError,'escapes'):preview.views_proof_routes(out)
        receipt.write_bytes(original);report=json.loads(original);item=report['alpha_diagnostics'][0]
        item['frame']+=1;receipt.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError,'differs'):preview.views_proof_routes(out)
        receipt.write_bytes(original);report=json.loads(original);item=report['alpha_diagnostics'][0]
        file=out/item['metadata']['file'];metadata=json.loads(file.read_text());metadata['source']['scene_sha256']='0'*64
        file.write_text(json.dumps(metadata));item['metadata']['sha256']=hashlib.sha256(file.read_bytes()).hexdigest();receipt.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError,'source differs'):preview.views_proof_routes(out)

    def test_diagnostic_directory_does_not_collide_with_a_view_named_alpha(self):
        scene=json.loads(self.source);scene['framing']['views']={'alpha':scene['framing']['views']['portrait']}
        self.scene_path.write_text(json.dumps(scene))
        result=self.render('views-proof','--view','alpha','--seconds','.5','--long-edge','160','--out',self.root/'alpha-view')
        report=json.loads(Path(result['report']).read_text())
        self.assertEqual(report['alpha_diagnostics'][0]['view_id'],'alpha')
        preview.views_proof_routes(Path(result['output']).parent)

    def test_invalid_views_dimensions_and_internal_stage_fail_before_output(self):
        for args in [
            ['frame','--view','missing'],['frame','--view','landscape','--width','360'],
            ['frame','--view','portrait','--supersample','4'],
            ['views-proof','--view','portrait','--view','portrait'],
            ['views-proof','--view','landscape','--long-edge','8'],
        ]:
            with self.assertRaises(CommandError):self.render(*args,'--out',self.root/'invalid')
            self.assertFalse((self.root/'invalid').exists())

    def test_source_change_after_planning_rejects_before_output(self):
        original=native_media.json_command
        def changed(command,*args,**kwargs):
            if command[-1]=='--probe':self.scene_path.write_bytes(self.source+b' ')
            return original(command,*args,**kwargs)
        with patch.object(native_media,'json_command',side_effect=changed),self.assertRaisesRegex(CommandError,'changed after view preflight'):
            self.render('frame','--view','landscape','--width','160','--out',self.root/'changed')
        self.assertFalse((self.root/'changed').exists())

    def test_implicit_authored_proof_keeps_previous_default_and_named_default_is_valid(self):
        implicit=self.render('proof','--seconds','1','--out',self.root/'implicit')
        named=self.render('proof','--view','landscape','--seconds','1','--out',self.root/'named')
        self.assertEqual(implicit['render_canvas']['width'],360)
        self.assertEqual(named['view']['output'],{'width':640,'height':360})

    def test_tiny_view_audit_does_not_require_more_detail_than_the_requested_proof(self):
        scene=json.loads(self.source);scene['framing']['views']={'detail':{'rect_scene_px':[1,1,1,1],'output':{'width':16,'height':16}}}
        self.scene_path.write_text(json.dumps(scene))
        result=self.render('views-proof','--view','detail','--seconds','1','--long-edge','1','--out',self.root/'tiny')
        report=json.loads(Path(result['report']).read_text())
        self.assertEqual(report['pixels']['views']['detail']['resolution'],[1,1])

    def test_captured_render_uses_the_captured_crop_after_working_framing_changes(self):
        project=self.root/'captured';cli.init_project(project,None,'Captured views','blank','dual')
        (project/'scene/scene.json').write_bytes(self.source)
        catalog=json.loads((self.project/'art/library.json').read_text());catalog['assets'][0]['file']='assets/pattern.png'
        (project/'assets/pattern.png').write_bytes((self.project/'art/pattern.png').read_bytes())
        (project/'assets/catalog.json').write_text(json.dumps(catalog))
        selection=project/'plans/selection.json';selection.write_text(json.dumps({'format':'ambiance-revision-selection','schema_version':1,'scene':'scene/scene.json','catalog':'assets/catalog.json'}))
        revisions.capture(project,'v1',selection)
        def render(id,revision):
            args=['render','frame','--view','portrait','--width','90','--out',str(project/'render'/id)]
            if revision:args+=['--revision',revision]
            return rendering.run(parse(*args),project)
        before=render('before','v1')
        scene=json.loads(self.source);scene['framing']['views']['portrait']['rect_scene_px'][0]=40
        (project/'scene/scene.json').write_text(json.dumps(scene))
        after=render('after','v1');working=render('working',None)
        self.assertEqual(before['output_sha256'],after['output_sha256'])
        self.assertNotEqual(after['output_sha256'],working['output_sha256'])
        self.assertEqual(after['revision']['revision_id'],'v1')

    @unittest.skipUnless(os.environ.get('AMBIANCE_TEST_NATIVE')=='1' and sys.platform=='darwin','Requires native macOS media services')
    def test_both_orientations_encode_and_decode_at_requested_dimensions(self):
        for id,width,height in [('portrait',90,160),('landscape',160,90)]:
            result=self.render('video','--view',id,'--width',str(width),'--out',self.root/id)
            self.assertTrue(result['verification']['ok'])
            self.assertEqual(result['verification']['decoded_frames'],12)
            self.assertEqual((result['render_canvas']['width'],result['render_canvas']['height']),(width,height))
            self.assertTrue(result['preroll_trim']['start_is_sync_frame'])


if __name__=='__main__':unittest.main()
