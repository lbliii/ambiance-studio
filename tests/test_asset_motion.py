"""Independent drift fixtures exercise the agent-operated study/compiler path."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from PIL import Image, ImageDraw
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import studio
from ambiance_studio import asset_motion as motion, assets
from tools.asset_tool import build, admit


def fixture(root):
    root.mkdir(parents=True,exist_ok=True)
    (root/'assets').mkdir(exist_ok=True)
    studio.write(root/'ambiance-project.json',{'version':1,'scene':'scene.json','catalog':'assets/catalog.json'})
    studio.write(root/'assets/catalog.json',{'version':1,'assets':[]})
    for i,(dx,dy) in enumerate([(0,0),(3,-2),(-2,1)]):
        im=Image.new('RGBA',(64,64));d=ImageDraw.Draw(im)
        d.rectangle((19+dx,18+dy,37+dx,45+dy),fill='#a06939')
        # Distinct texture at the planted mark, head motion independent of body.
        d.rectangle((21+dx,37+dy,25+dx,41+dy),fill='#fff4ae')
        d.point((23+dx,39+dy),fill='#111111')
        d.rectangle((20+dx+i,10+dy,32+dx+i,17+dy),fill='#f1ac42')
        im.save(root/f'{i}.png')
    recipe={'version':1,'id':'figure-v1','input':{'frames':['0.png','1.png','2.png']},
            'registration':{'mode':'fixed','point':[32,32],'target':[.5,.5]},
            'output':{'cell_size':[64,64],'columns':3,'padding':2},
            'sockets':{'foot':[.36,.62],'mount':[.5,.5]}}
    studio.write(root/'recipe.json',recipe);build(root/'recipe.json',root/'baseline');admit(root/'baseline',root/'assets/catalog.json')
    return root


def annotated(root):
    s=motion.initialize(root,str(root/'baseline'),display_width=64)
    for key,role,xy in [('foot','fit',(23,39)),('shoulder','check',(30,22))]:
        s['landmarks'][key]={'role':role,'mode':'fixed','reference_cel':0,'cels':[0,1,2],'tolerance_px':.1,'weight':1,
            'observations':[{'point':[xy[0]+dx,xy[1]+dy],'visible':True,'origin':'manual','state':'selected'} for dx,dy in [(0,0),(3,-2),(-2,1)]]}
    s['solve']['socket_policies']={'foot':'follow_art','mount':'fixed_mount'}
    return s


class MotionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=fixture(Path(self.tmp.name));self.s=annotated(self.root);self.file=self.root/'study.json';studio.write(self.file,self.s)
    def context(self):return motion.load(self.root,data=self.s)
    def candidate(self):
        motion.proposal(self.root,self.file,self.root/'proposal','figure-v2')
        return build(self.root/'proposal/compiler.json',self.root/'candidate')
    def test_recovery_independent_check_pixels_and_cache(self):
        sol=motion.solution(self.context());self.assertTrue(sol['ok']);self.assertEqual(sol['translations_cell_px'],[[0,0],[-3,2],[2,-1]])
        self.candidate();asset=assets.inspect_pack(self.root/'candidate')['asset'];self.assertEqual(asset['registration_mapping']['shared_scale'],1)
        _,frames=assets.read_asset(asset,self.root/'candidate')
        # Correct planted body raster exactly, while head retains authored movement.
        self.assertEqual(frames[0].crop((0,18,64,64)).tobytes(),frames[1].crop((0,18,64,64)).tobytes())
        self.assertNotEqual(frames[0].crop((0,0,64,18)).tobytes(),frames[1].crop((0,0,64,18)).tobytes())
        self.assertEqual(asset['sockets']['mount'],[.5,.5]);self.assertEqual(asset['sockets']['foot']['frames'][1],[.36-3/64,.62+2/64])
        self.assertEqual(build(self.root/'candidate/recipe.json',self.root/'candidate')['status'],'cached')
        self.assertEqual([f.tobytes() for f in motion.raster(self.context())],[f.tobytes() for f in frames])
    def test_conflicting_check_never_fitted(self):
        self.s['landmarks']['shoulder']['observations'][1]['point'][0]+=3
        sol=motion.solution(self.context());self.assertFalse(sol['ok']);self.assertEqual(sol['translations_cell_px'][1],[-3,2])
        self.assertTrue(any(x.get('landmark')=='shoulder' and x['reason']=='constraint_conflict' for x in sol['unresolved']))
    def test_incomplete_study_inspectable(self):
        c=motion.load(self.root,data=motion.initialize(self.root,str(self.root/'baseline')))
        self.assertFalse(motion.solution(c)['ok'])
    def test_clipping_is_failure_without_published_output(self):
        for mark in self.s['landmarks'].values():mark['observations'][1]['point'][0]-=30
        # Keep observations inside source.
        self.s['landmarks']['foot']['observations'][1]['point'][0]=0
        self.s['landmarks']['shoulder']['observations'][1]['point'][0]=7
        self.s['solve']['max_shift_px']=100;studio.write(self.file,self.s)
        with self.assertRaisesRegex(ValueError,'padding'):motion.proposal(self.root,self.file,self.root/'proposal','bad')
        self.assertFalse((self.root/'proposal').exists())
    def test_tampered_source_rejected_on_cache(self):
        self.candidate();(self.root/'1.png').write_bytes(b'changed')
        with self.assertRaises((ValueError,OSError)):build(self.root/'candidate/recipe.json',self.root/'candidate')
    def test_recipe_cannot_change_scale(self):
        motion.proposal(self.root,self.file,self.root/'proposal','figure-v2');p=self.root/'proposal/compiler.json';r=studio.read(p);r['output']['cell_size']=[128,128];studio.write(p,r)
        with self.assertRaisesRegex(ValueError,'preserve baseline output'):build(p,self.root/'bad')
        self.assertFalse((self.root/'bad').exists())
    def test_revision_and_scene_provenance(self):
        self.candidate();admit(self.root/'candidate',self.root/'assets/catalog.json')
        from ambiance_studio.revisions import Collector
        c=Collector(self.root);c.asset(studio.read(self.root/'assets/catalog.json')['assets'][-1])
        self.assertTrue(any('motion' in ref['role'] for ref in c.refs))
    def test_cli_initialization_and_stale_batch(self):
        def cli(*args):return subprocess.run([str(ROOT/'ambiance'),'--project',str(self.root),*args],capture_output=True,text=True)
        result=cli('asset','motion','init',str(self.root/'baseline'),'--out',str(self.root/'draft.json'));self.assertEqual(result.returncode,0,result.stdout)
        studio.write(self.root/'batch.json',{'version':1,'operations':[{'op':'note','text':'fixture'}]})
        result=cli('asset','motion','edit',str(self.file),'--changes',str(self.root/'batch.json'),'--expect-study','bad','--out',str(self.root/'edited.json'))
        self.assertNotEqual(result.returncode,0);self.assertFalse((self.root/'edited.json').exists())

    def test_views_batch_roundtrip_and_stale_packet(self):
        from ambiance_studio.motion_proof import proof
        self.s['view']['display_width']=128;studio.write(self.file,self.s)
        context=self.context();proof(context,self.file,self.root/'analysis')
        ref=motion.identity(self.root,self.root/'analysis/packet.json')
        operations=[{'op':'observe','name':'foot','cel':i,'value':{'point':[x*2,y*2],'visible':True,'origin':'manual','state':'selected'},'view':{'packet':ref,'id':f'prepared-{i}'}} for i,(x,y) in enumerate([(23,39),(26,37)])]
        result=motion.edited(context,{'version':1,'operations':operations})
        self.assertEqual(result['study'],self.s)
        self.s['notes'].append('changed')
        with self.assertRaisesRegex(ValueError,'Stale'):motion.edited(self.context(),{'version':1,'operations':operations})
    def test_transparent_rgb_and_soft_region_measurements(self):
        from ambiance_studio.motion_proof import metrics
        a=Image.new('RGBA',(4,4),(255,0,0,0));b=Image.new('RGBA',(4,4),(0,255,255,0));mask=Image.new('L',(4,4),128)
        self.assertEqual(metrics(a,b,mask)['premultiplied_rgb_mean_abs'],0)
        b.putalpha(128);self.assertGreater(metrics(a,b,mask)['alpha_mean_abs'],120)
        self.assertGreater(metrics(a,b,mask)['premultiplied_rgb_mean_abs'],0)
        self.assertFalse(metrics(a,b,mask)['color_available'])
        a=Image.new('RGBA',(4,4),(80,90,100,128));b=Image.new('RGBA',(4,4),(80,90,100,255))
        self.assertEqual(metrics(a,b,mask)['overlap_color_mean_abs'],0)
        self.assertGreater(metrics(a,b,mask)['alpha_mean_abs'],0)
    def test_tracking_known_points_and_textureless_stop(self):
        from ambiance_studio.motion_tracking import track,plane,match
        for mark in self.s['landmarks'].values():mark['observations'][1:]=[None,None]
        studio.write(self.file,self.s);result=track(self.context(),self.file,self.root/'tracked')
        s=studio.read(self.root/'tracked/study.json')
        self.assertEqual(result['proposed'],2);self.assertEqual(result['unresolved_count'],2)
        self.assertEqual(s['landmarks']['foot']['observations'][1]['point'],[26,37]);self.assertEqual(s['landmarks']['foot']['observations'][1]['state'],'proposed')
        self.assertIsNone(s['landmarks']['shoulder']['observations'][1]);self.assertFalse(motion.solution(motion.load(self.root,data=s))['ok'])
        im=Image.new('RGBA',(64,64));d=ImageDraw.Draw(im)
        for x in [15,35]:d.rectangle((x-2,28,x+2,32),fill='white');d.point((x,30),fill='black')
        cfg={**self.s['tracking'],'radius':24}
        self.assertEqual(match(plane(im),plane(im),[15,30],[25,30],cfg)['reason'],'ambiguous_match')
        invisible=Image.new('RGBA',(64,64))
        self.assertFalse(match(plane(im),plane(invisible),[15,30],[15,30],cfg)['ok'])
    def test_region_mask_does_not_create_texture(self):
        from ambiance_studio.motion_tracking import plane,match
        flat=plane(Image.new('RGBA',(32,32),(180,180,180,255)))
        cfg={**self.s['tracking'],'patch_radius':2,'radius':3}
        for weights in [[0]*10+[1]*15,[0]*25,[.2]*10+[.8]*15]:
            self.assertEqual(match(flat,flat,[16,16],[16,16],cfg,weights)['reason'],'insufficient_texture')
    def test_context_proof_odd_frame_count_uses_export_clock(self):
        from unittest.mock import patch
        from ambiance_studio.motion_proof import context_render
        stage=self.root/'clock-proof';stage.mkdir()
        proposal={'ok':True,'scene':{'canvas':{'width':128,'height':128,'fps':12,'loop_seconds':2}},'catalog':{},'batch':{},'expected_scene_sha256':'fixture'}
        context={'project':self.root,'study':{'view':{'scene':{'scene':{},'catalog':{}}}}}
        with patch('ambiance_studio.motion_proof.scene_candidate',return_value=proposal), patch('ambiance_studio.motion_proof.motion.checked',return_value=self.file), patch('ambiance_studio.native_media.json_command') as render:
            result=context_render(context,{},stage,5/12)
        self.assertEqual(len(result['frames'][0]),5)
        self.assertEqual(result['start']*12,22)
        self.assertEqual(render.call_args_list[0].args[1]['start'],22/12)
    def test_draft_pixels_export_reproduce_saved_build(self):
        from ambiance_studio.motion_proof import proof
        from ambiance_studio.motion_server import evaluate
        import base64,io
        proof(self.context(),self.file,self.root/'analysis');packet=studio.read(self.root/'analysis/packet.json')
        result=evaluate(packet,{'study':self.s,'changes':{'version':1,'operations':[{'op':'note','text':'draft parity'}]}})
        studio.write(self.root/'draft.json',result['study']);motion.proposal(self.root,self.root/'draft.json',self.root/'proposal','draft-v2');build(self.root/'proposal/compiler.json',self.root/'candidate')
        _,frames=assets.read_asset(assets.inspect_pack(self.root/'candidate')['asset'],self.root/'candidate')
        decoded=[Image.open(io.BytesIO(base64.b64decode(x.split(',')[1]))).tobytes() for x in result['images']]
        self.assertEqual(decoded,[f.tobytes() for f in frames])
    def test_scene_clock_overrides_finishing_and_adoption(self):
        from ambiance_studio.motion_proof import timeline,scene_candidate
        layer={'id':'figure','asset':'figure-v1','x':.5,'y':.5,'width':.5,'height':.5,'anchor':[.5,.5],'scale':1,'rotation':0,'opacity':1,'visible':True,'blend':'source-over','depth':0,'cycle_seconds':2,'phase_frames':0,
            'tracks':{'cell':{'interpolation':'hold','keys':[[0,0],[.5,1],[1.5,2],[2,0]]}},'sockets':{'foot':[.36,.62]}}
        scene={'version':1,'id':'fixture','title':'Fixture','canvas':{'width':128,'height':128,'fps':12,'loop_seconds':2,'background':'#132840'},'camera':{'overscan':1,'x_amplitude':0,'y_amplitude':0,'zoom_amplitude':0},'groups':[],'layers':[layer]}
        studio.write(self.root/'scene.json',scene)
        bound=motion.initialize(self.root,layer='figure');bound['landmarks']=self.s['landmarks'];bound['solve']['socket_policies']=self.s['solve']['socket_policies'];bound['solve']['layer_socket_policies']={'foot':'follow_art'}
        self.s=bound;studio.write(self.file,bound);c=self.context();clock=timeline(c)
        self.assertEqual([(r['start'],r['end'],r['cell']) for r in clock['segments']],[(0,.5,0),(.5,1.5,1),(1.5,2,2)])
        self.candidate();a=motion.project_asset(self.root.resolve(),self.root/'candidate');proposal=scene_candidate(c,a)
        self.assertTrue(proposal['ok']);self.assertEqual(proposal['scene']['layers'][0]['sockets']['foot']['frames'][1],[.36-3/64,.62+2/64])
        from ambiance_studio import scene_authoring
        batch,deps=scene_authoring.resolve_batch(self.root.resolve(),scene,proposal['catalog'],proposal['batch']);self.assertTrue(deps)
        self.assertEqual(studio.read(self.root/'scene.json'),scene)
        scene['finishing']={'version':1,'working_space':'linear-srgb','output_space':'srgb','assets':{'figure-v1':{'exposure':.1}}}
        bound['view']['scene']['scene']=motion.snapshot(self.root.resolve(),scene);context=motion.load(self.root,data=bound)
        graded=scene_candidate(context,a);self.assertEqual(graded['scene']['finishing']['assets']['figure-v2'],{'exposure':.1})
        scene['finishing']['lights']=[{'id':'bound-light','receivers':['figure'],'rect':[0,0,1,1],'anchor_layer':'figure','color':'#ffcc88','gain':.2}]
        bound['view']['scene']['scene']=motion.snapshot(self.root.resolve(),scene);context=motion.load(self.root,data=bound)
        self.assertFalse(scene_candidate(context,a)['ok'])
    def test_subpixel_constraints_and_ignored_regions(self):
        from ambiance_studio.motion_proof import effective_mask
        for mark in self.s['landmarks'].values():
            mark['observations'][1]['point'][0]+=.25;mark['observations'][1]['point'][1]-=.5
        sol=motion.solution(self.context());self.assertTrue(sol['ok']);self.assertEqual(sol['translations_cell_px'][1],[-3.25,2.5])
        region={'mode':'stable','points':[[0,0],[63,0],[63,63],[0,63]],'cels':[0,1,2],'reference_cel':0,'alpha_threshold':10,'color_threshold':10}
        self.s['regions']={'body':region,'moving-head':{**region,'mode':'ignore','points':[[0,0],[63,0],[63,17],[0,17]],'cels':[1]}}
        c=self.context();self.assertEqual(effective_mask(c,region,1).getpixel((30,10)),0);self.assertEqual(effective_mask(c,region,0).getpixel((30,10)),255)
    def test_stale_proposal_and_output_collision_are_not_published(self):
        motion.proposal(self.root,self.file,self.root/'proposal','figure-v2')
        with self.assertRaisesRegex(ValueError,'exists'):motion.proposal(self.root,self.file,self.root/'proposal','figure-v2')
        study=self.root/'proposal/study.json';s=studio.read(study);s['notes'].append('tampered');studio.write(study,s)
        with self.assertRaisesRegex(ValueError,'changed'):build(self.root/'proposal/compiler.json',self.root/'candidate')
        self.assertFalse((self.root/'candidate').exists())
    def test_draft_http_origin_and_tamper(self):
        from ambiance_studio.motion_proof import proof
        from ambiance_studio.motion_server import handler
        from http.server import HTTPServer
        import threading,urllib.request,urllib.error
        proof(self.context(),self.file,self.root/'analysis')
        server=HTTPServer(('127.0.0.1',0),handler(self.root/'analysis'));thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            url=f'http://127.0.0.1:{server.server_port}'
            self.assertEqual(urllib.request.urlopen(url).status,200)
            req=urllib.request.Request(url+'/api/draft',data=json.dumps({'study':self.s,'changes':{'version':1,'operations':[{'op':'note','text':'HTTP'}]}}).encode(),headers={'Content-Type':'application/json'})
            result=json.load(urllib.request.urlopen(req));self.assertTrue(result['solution']['ok'])
            req.add_header('Origin','https://example.com')
            with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(req)
            self.assertEqual(error.exception.code,403);error.exception.close()
            (self.root/'0.png').write_bytes(b'changed');req.remove_header('Origin')
            with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(req)
            self.assertEqual(error.exception.code,422);error.exception.close()
        finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main(verbosity=2)
