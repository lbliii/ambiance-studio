"""Public picture reuse, requested contacts, and deterministic rig inspection."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import wave

from test_rendering import ROOT, Image, fixture, parse
from ambiance_studio import rendering
from ambiance_studio.cli import CommandError


def pcm(path, seconds, value=1200):
    with wave.open(str(path),'wb') as file:
        file.setnchannels(2);file.setsampwidth(2);file.setframerate(48000)
        file.writeframes(int(value).to_bytes(2,'little',signed=True)*2*round(seconds*48000))


class ContactTests(unittest.TestCase):
    def test_requested_times_and_exact_boundaries(self):
        result=rendering.requested_contacts([3.67,18.13,0.3,0.3-1e-10],[719],30,720)
        self.assertEqual([r['frame_index'] for r in result],[110,543,9,9,719])
        self.assertEqual(result[0]['presentation_time_seconds'],110/30)
    def test_out_of_range_nonfinite_and_fractional_indices_fail(self):
        for times,indices in [([24],[]),([-0.1],[]),([float('nan')],[]),([],[-1]),([],[720]),([],[2.5])]:
            with self.assertRaises(CommandError):rendering.requested_contacts(times,indices,30,720)


@unittest.skipUnless(Image and rendering.capabilities()['frame_render'],'Requires Pillow and Node Canvas')
class RigProofTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.project=fixture(self.root)
        self.scene_path=self.project/'edit/cut.json';scene=json.loads(self.scene_path.read_text())
        # A residual painted body remains in the rear plate, separate from the
        # active body. Hiding the active body must expose, not erase, this defect.
        rear=copy.deepcopy(scene['layers'][0]);rear['id']='contaminated-rear';rear.pop('motion');rear['x']=.5;rear['y']=.5
        body=copy.deepcopy(rear);body['id']='body';body['sockets']={'hand':[.5,.5]};body['tracks']={'visible':{'interpolation':'hold','keys':[[0,True],[2,True]]}}
        hand=copy.deepcopy(body);hand['id']='hand';hand.pop('depth');hand.pop('tracks');hand['attach']={'layer':'body','socket':'hand'};hand['x']=0;hand['y']=0;hand['width']=.1;hand['height']=.1
        scene['layers']=[rear,body,hand];self.scene_path.write_text(json.dumps(scene));self.original=self.scene_path.read_bytes()
        inventory=self.project/'inventory.json';inventory.write_text(json.dumps({'version':1,'items':[{'id':'mummy-body'},{'id':'casket-rig'}]}))
        self.recipe={'version':1,'title':'Backing contamination fixture','inventory':'inventory.json','part_ids':['mummy-body','casket-rig'],
                     'samples':[{'id':'rest','time':0},{'id':'lift','time':1,'overrides':{'body':{'y':.35}}},{'id':'body-hidden','time':1,'overrides':{'body':{'visible':False}}}],
                     'regions':[{'id':'body-detail','rect':[.2,.2,.6,.6]}],
                     'comparisons':[{'id':'hidden-vs-rest','left':'rest','right':'body-hidden','difference':True}], 'playback_seconds':.5}
    def execute(self, recipe=None, out='proof'):
        path=self.root/'proof-recipe.json';path.write_text(json.dumps(recipe or self.recipe))
        return rendering.run(parse('render','rig-proof',path,'--width','64','--out',self.root/out),self.project)
    def test_variant_overrides_preserve_canonical_scene_and_expose_contamination(self):
        result=self.execute();samples={s['id']:s for s in result['samples']}
        hidden=samples['body-hidden'];self.assertEqual(hidden['explicitly_hidden_layers'],['body'])
        self.assertIn({'layer':'hand','hidden_by':'body'},hidden['hidden_descendants'])
        self.assertIn('hand',hidden['hidden_layers']);self.assertIn('body',hidden['hidden_layers'])
        self.assertEqual(self.scene_path.read_bytes(),self.original)
        self.assertFalse(result['full_loop_review_performed']);self.assertEqual(result['part_ids'],['mummy-body','casket-rig'])
        self.assertIsNone(result['frames']);self.assertIsNone(result['seconds'])
        self.assertIsNone(result['start_seconds']);self.assertEqual(result['scene_loop_frames'],12)
        self.assertEqual(result['saved_sample_frames'],3)
        self.assertEqual(result['saved_playback_frames_per_variant'],3)
        self.assertEqual(result['saved_playback_frames_total'],9)
        self.assertTrue((self.root/'proof/playback/index.html').is_file())
        self.assertTrue(result['comparisons'][0]['difference_metrics']['changed_pixels']>0)
        with Image.open(self.root/'proof'/hidden['context']['file']) as image:
            # The residual rear patch is still visibly non-background at center.
            self.assertNotEqual(image.convert('RGB').getpixel((32,48)),(19,40,64))
        self.assertEqual(len(result['samples']),3);self.assertEqual(len(result['samples'][0]['details']),1)
    def test_malformed_variant_region_or_inventory_rejected_without_output(self):
        for update in ['layer','region','time','part']:
            recipe=copy.deepcopy(self.recipe)
            if update=='layer':recipe['samples'][0]['overrides']={'missing':{'visible':False}}
            if update=='region':recipe['regions'][0]['rect']=[.8,0,.5,1]
            if update=='time':recipe['samples'][0]['time']=2
            if update=='part':recipe['part_ids']=['not-in-inventory']
            with self.assertRaises(CommandError):self.execute(recipe,out=update)
            self.assertFalse((self.root/update).exists())
    def test_explicit_revision_context_never_reads_changed_working_scene(self):
        scene_copy=self.project/'captured.json';scene_copy.write_bytes(self.original)
        catalog_path=self.project/'art/library.json'
        changed=json.loads(self.original);changed['layers']=[];self.scene_path.write_text(json.dumps(changed))
        context={'scene':scene_copy,'catalog':catalog_path,'revision_id':'frozen','manifest_sha256':'f'*64}
        with patch('ambiance_studio.rendering._context',return_value=context) as selected:
            result=rendering.run(parse('render','frame','--revision','frozen','--out',self.root/'frozen'),self.project)
        self.assertTrue(result['ok']);self.assertEqual(result['scene'],str(scene_copy.resolve()))
        self.assertEqual(result['revision']['revision_id'],'frozen');self.assertEqual(selected.call_count,2)


@unittest.skipUnless(Image and os.environ.get('AMBIANCE_TEST_NATIVE')=='1' and sys.platform=='darwin','Set AMBIANCE_TEST_NATIVE=1 with macOS media-service access')
class CompositionNativeTests(unittest.TestCase):
    def test_two_public_editions_preserve_elementary_picture_payloads_and_requested_contacts(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);project=fixture(root)
            picture=rendering.run(parse('render','video','--out',root/'picture'),project)['output']
            audio_a=root/'score.wav';audio_b=root/'ambience.wav';pcm(audio_a,4,1400);pcm(audio_b,4,700)
            editions=[]
            for name,audio in [('score',audio_a),('ambience',audio_b)]:
                command=[sys.executable,str(ROOT/'ambiance'),'--project',str(project),'media','compose',picture,'--audio',str(audio),'--repeats','2','--out',str(root/name)]
                process=subprocess.run(command,capture_output=True,text=True)
                result=json.loads(process.stdout);self.assertEqual(process.returncode,0,result);editions.append(result['data'])
            for edition in editions:
                self.assertFalse(edition['video_reencoded']);self.assertTrue(edition['compressed_sample_payloads_preserved'])
                self.assertEqual(edition['output_video_sample_sha256'],edition['input_video_sample_sha256']*2)
                self.assertEqual(edition['verification']['audio']['presented_samples'],192000)
            self.assertEqual(editions[0]['output_video_sample_sha256'],editions[1]['output_video_sample_sha256'])
            contact=rendering.run(parse('media','verify',editions[0]['output'],'--frames','24','--audio-tracks','1','--contact-time','3.67','--contact-frame','7','--out',root/'contacts'),project)
            self.assertTrue(contact['ok']);self.assertEqual([r['frame_index'] for r in contact['requested_contacts']],[22,7])
            for requested in contact['requested_contacts']:
                self.assertEqual(hashlib.sha256(Path(requested['resolved_path']).read_bytes()).hexdigest(),requested['sha256'])
            # Documented replacement: an existing input audio track is ignored.
            replacement=rendering.run(parse('media','compose',editions[0]['output'],'--audio',audio_b,'--out',root/'replacement'),project)
            self.assertTrue(replacement['ok']);self.assertEqual(replacement['input_tracks']['audio'],1);self.assertEqual(replacement['output_tracks']['audio'],1)
            self.assertTrue(replacement['compressed_sample_payloads_preserved'])
            with self.assertRaises(CommandError):rendering.run(parse('media','compose',picture,'--audio',audio_b,'--out',root/'wrong-duration'),project)
            self.assertFalse((root/'wrong-duration').exists())
            with self.assertRaises(CommandError):rendering.run(parse('media','compose',picture,'--audio',audio_b,'--repeats','2','--out',root/'score'),project)
    def test_original_changed_during_composition_invalidates_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);project=fixture(root)
            picture=Path(rendering.run(parse('render','video','--out',root/'picture'),project)['output'])
            audio=root/'audio.wav';pcm(audio,2)
            original=rendering._json_command
            def mutate_after_compose(command,*args,**kwargs):
                result=original(command,*args,**kwargs)
                if str(command[1])=='compose':picture.write_bytes(picture.read_bytes()+b'changed during mux')
                return result
            with patch('ambiance_studio.rendering._json_command',side_effect=mutate_after_compose):
                result=rendering.run(parse('media','compose',picture,'--audio',audio,'--out',root/'changed'),project)
            self.assertFalse(result['ok']);self.assertFalse(result['inputs_unchanged']);self.assertTrue(result['snapshots_unchanged'])
            self.assertTrue(Path(result['report']).is_file())


if __name__=='__main__':unittest.main()
