"""View-bound receipts and reviews; actual media is exercised separately below."""
import copy
import json
import os
from pathlib import Path
import sys
import unittest
import wave

import studio
from ambiance_studio import cli, revisions
import test_revisions as revision_fixtures


class ViewEditionTests(unittest.TestCase):
    def setUp(self):
        self.fixture=revision_fixtures.RevisionTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.p=self.fixture.p
        scene=studio.read(self.p/'scene/scene.json');scene['canvas'].update(width=160,height=160,fps=6,loop_seconds=2)
        scene['framing']={'version':1,'views':{
            'portrait':{'rect_scene_px':[35,0,90,160],'output':{'width':1080,'height':1920}},
            'landscape':{'rect_scene_px':[0,35,160,90],'output':{'width':1920,'height':1080}}}}
        studio.write(self.p/'scene/scene.json',scene)
        for name in ['source','master']:
            with wave.open(str(self.p/f'audio/{name}.wav'),'wb') as file:
                file.setnchannels(2);file.setsampwidth(2);file.setframerate(48000);file.writeframes(b'\x01\x00\x01\x00'*192000)
        prep=studio.read(self.p/'audio/preparation.json')
        prep['sources']=[self.fixture.audio_ref('source.wav')];prep['outputs']=[self.fixture.audio_ref('master.wav')]
        studio.write(self.p/'audio/preparation.json',prep);self.fixture.capture()

    def args(self,*args):return cli.parser().parse_args(['--project',str(self.p),*map(str,args)])

    def synthetic(self,id='portrait-unit',view='portrait',result_view=None, role='silent'):
        # A unit boundary fixture, never evidence that these bytes decode.
        out=self.p/'reports'/id
        args=self.args('render','video','--revision','v1','--edition',id,'--view',view,'--out',out)
        if role!='silent':args.audio=self.p/'audio/master.wav';args.repeats=2
        prepared=revisions.prepare_edition(self.p,args);out.mkdir()
        picture=out/'picture.mp4';picture.write_bytes(b'Synthetic view receipt fixture: '+id.encode())
        selected=revisions.captured_view(self.p,'v1',result_view or view)
        width,height=(90,160) if (result_view or view)=='portrait' else (160,90)
        verification={'ok':True,'report':str(out/'verification.json'),'width':width,'height':height,'fps':6,'decoded_frames':12*args.repeats,'loop_frames':12,'duration_seconds':2*args.repeats,
                      'fully_decoded':True,'input_unchanged':True,'input_sha256':studio.digest(picture),'input_sha256_after':studio.digest(picture),'audio':{'tracks':0 if role=='silent' else 1},'synthetic_unit_fixture':True}
        studio.write(out/'verification.json',verification)
        from PIL import Image
        (out/'contacts').mkdir();Image.new('RGB',(width,height),'purple').save(out/'contacts/decoded-0000.png')
        context=revisions.render_context(self.p,'v1')
        result={'ok':True,'mode':'video','output':str(picture),'output_sha256':studio.digest(picture),'picture_sha256':studio.digest(picture),
                'scene_sha256':studio.digest(context['scene']),'catalog_sha256':studio.digest(context['catalog']),
                'verification':verification,'view':{'view':selected['definition'],'view_sha256':selected['sha256'],'output':{'width':width,'height':height}}}
        studio.write(out/'render-report.json',result)
        return revisions.record_edition(self.p,prepared,result,args)

    def test_named_receipt_has_exact_view_and_output_while_legacy_stays_unchanged(self):
        self.synthetic();record=revisions.load_edition(self.p,'v1','portrait-unit')
        self.assertEqual(record['schema_version'],2);self.assertEqual(record['view']['id'],'portrait')
        self.assertEqual(record['output_expectations'],{'width':90,'height':160,'fps':6,'frames':12,'loop_frames':12,'audio_tracks':0})
        self.fixture.synthetic_edition('legacy')
        path=revisions.edition_path(self.p,'v1','legacy');raw=path.read_bytes();legacy=revisions.load_edition(self.p,'v1','legacy')
        self.assertEqual(legacy['schema_version'],1);self.assertEqual(revisions.edition_view(self.p,legacy)['id'],'authored')
        self.assertEqual(path.read_bytes(),raw)

    def test_wrong_render_or_forged_view_receipt_cannot_be_registered(self):
        with self.assertRaisesRegex(ValueError,'Rendered view differs'):self.synthetic('bad','portrait','landscape')
        self.assertFalse(revisions.edition_path(self.p,'v1','bad').exists())
        self.synthetic();path=revisions.edition_path(self.p,'v1','portrait-unit');record=studio.read(path)
        record['view']['id']='landscape';record.pop('payload_sha256');studio.write(path,revisions.seal(record))
        with self.assertRaisesRegex(ValueError,'Edition view differs'):revisions.load_edition(self.p,'v1','portrait-unit')

    def test_composition_inherits_picture_view_and_rejects_an_explicit_mismatch(self):
        result=self.synthetic();picture=Path(result['output'])
        args=self.args('media','compose',picture,'--revision','v1','--edition','score','--audio',self.p/'audio/master.wav','--out',self.p/'reports/score')
        self.assertEqual(revisions.prepare_edition(self.p,args)['view']['id'],'portrait')
        args.view='landscape'
        with self.assertRaisesRegex(ValueError,'cannot relabel'):revisions.prepare_edition(self.p,args)
        args.picture_receipt=str((picture.parent/'render-report.json').relative_to(self.p))
        with self.assertRaisesRegex(ValueError,'cannot relabel'):revisions.prepare_edition(self.p,args)

    def test_picture_reviews_are_separate_and_edition_reviews_require_matching_view(self):
        portrait=revisions.review_context(self.p,'v1',view='portrait')
        landscape=revisions.review_context(self.p,'v1',view='landscape')
        self.assertNotEqual(portrait['subject'],landscape['subject']);self.assertNotEqual(portrait['review_dir'],landscape['review_dir'])
        draft=studio.review_template(self.p,'intent',portrait);draft['recorder']='Synthetic fixture'
        file=self.p/'review-drafts/view.json';studio.write(file,draft)
        cli.run(self.args('review','record',file))
        self.assertEqual(revisions.status(self.p,'v1',view='portrait')['gates']['intent']['state'],'revise')
        self.assertEqual(revisions.status(self.p,'v1',view='landscape')['gates']['intent']['state'],'pending')
        self.assertEqual(revisions.status(self.p,'v1')['gates']['intent']['state'],'pending')
        with self.assertRaisesRegex(ValueError,'subject differs'):studio.record_review(self.p,file,landscape)
        self.synthetic()
        with self.assertRaisesRegex(ValueError,'Review view differs'):revisions.review_context(self.p,'v1','portrait-unit','landscape')

    def test_schema_versions_are_accepted_per_record_kind(self):
        self.synthetic();path=revisions.edition_path(self.p,'v1','portrait-unit')
        self.assertEqual(revisions.read_sealed(path,revisions.EDITION,versions=(1,2))['schema_version'],2)
        with self.assertRaisesRegex(ValueError,'Unsupported'):revisions.read_sealed(path,revisions.EDITION)
        manifest=copy.deepcopy(revisions.load(self.p,'v1'));manifest['schema_version']=2;manifest.pop('payload_sha256')
        candidate=self.p/'reports/future-manifest.json';studio.write(candidate,revisions.seal(manifest))
        with self.assertRaisesRegex(ValueError,'Unsupported'):revisions.read_sealed(candidate,revisions.FORMAT)

    @unittest.skipUnless(os.environ.get('AMBIANCE_TEST_NATIVE')=='1' and sys.platform=='darwin','Requires actual native encode/decode')
    def test_native_view_editions_compose_and_verify_using_bound_dimensions(self):
        for view,width in [('portrait',90),('landscape',160)]:
            result=cli.run(self.args('render','video','--view',view,'--width',width,'--revision','v1','--edition',view,'--out',self.p/'render'/view))
            self.assertTrue(result['verification']['ok']);self.assertEqual(revisions.load_edition(self.p,'v1',view)['view']['id'],view)
        scored=cli.run(self.args('media','compose',self.p/'render/portrait/picture.mp4','--revision','v1','--edition','portrait-score','--repeats',2,'--audio',self.p/'audio/master.wav','--out',self.p/'render/portrait-score'))
        self.assertEqual(scored['view']['view']['id'],'portrait')
        self.assertEqual(scored['verification']['audio']['presented_samples'],192000)
        working=studio.read(self.p/'scene/scene.json');working['canvas'].update(width=1920,height=1920);studio.write(self.p/'scene/scene.json',working)
        checked=cli.run(self.args('media','verify',scored['output'],'--revision','v1','--edition','portrait-score','--out',self.p/'reports/reverify'))
        self.assertTrue(checked['ok']);self.assertEqual((checked['width'],checked['height'],checked['decoded_frames']),(90,160,24))
        self.assertEqual(checked['subject']['view'],'portrait')


if __name__=='__main__':unittest.main()
