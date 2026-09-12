"""Raster behavior tests; opt-in native tests require local macOS media services."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ambiance_studio import native_media, media_verification, rendering
from ambiance_studio.cli import CommandError
try:
    from PIL import Image
except ImportError:
    Image = None


def parse(*arguments):
    parser = argparse.ArgumentParser()
    rendering.add_parsers(parser.add_subparsers(dest='command', required=True))
    return parser.parse_args(list(map(str, arguments)))


def fixture(root):
    # Deliberately non-default config paths: the renderer must use configuration.
    project = root/'film';project.mkdir()
    (project/'art').mkdir();(project/'edit').mkdir()
    image = Image.new('RGBA', (16, 16))
    image.putdata([(35+(x*53+y*19)%190, 22+(x*7+y*47)%190, 50, 255) for y in range(16) for x in range(16)])
    source = project/'art/pattern.png';image.save(source)
    layer = {'id':'moving','asset':'paint','x':.25,'y':.35,'width':.4,'height':.3,'anchor':[.5,.5],
             'scale':1,'rotation':0,'opacity':1,'visible':True,'blend':'source-over','depth':0,
             'motion':{'x_amplitude':.1,'y_amplitude':0,'cycles':1,'phase':0}}
    scene = {'version':1,'id':'test','title':'Independent render fixture',
             'canvas':{'width':64,'height':96,'fps':6,'loop_seconds':2,'background':'#132840'},
             'camera':{'overscan':1,'x_amplitude':0,'y_amplitude':0,'zoom_amplitude':0},'groups':[],'layers':[layer]}
    catalog = {'version':1,'assets':[{'id':'paint','file':'art/pattern.png','width':16,'height':16,
                                    'sha256':hashlib.sha256(source.read_bytes()).hexdigest()}]}
    (project/'ambiance-project.json').write_text(json.dumps({'version':1,'scene':'edit/cut.json','catalog':'art/library.json'}))
    (project/'edit/cut.json').write_text(json.dumps(scene));(project/'art/library.json').write_text(json.dumps(catalog))
    return project


@unittest.skipUnless(Image and rendering.capabilities()['frame_render'], 'Requires Pillow and Node Canvas')
class RasterTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.project=fixture(self.root)
        self.source=(self.project/'edit/cut.json').read_bytes()
    def render(self, *arguments):
        return rendering.run(parse(*arguments), self.project)
    def test_frame_is_deterministic_uses_config_and_preserves_scene(self):
        a=self.render('render','frame','--time','0','--out',self.root/'a')
        b=self.render('render','frame','--time','2','--out',self.root/'b')
        self.assertEqual(a['output_sha256'],b['output_sha256'])
        with Image.open(a['output']) as image:self.assertEqual(image.size,(64,96))
        self.assertTrue(a['rgba_endpoint_exact'])
        self.assertEqual(a['scene'],str((self.project/'edit/cut.json').resolve()))
        self.assertEqual((self.project/'edit/cut.json').read_bytes(),self.source)
        with self.assertRaises(CommandError):self.render('render','frame','--out',self.root/'a')
    def test_proof_contains_actual_speed_and_distinct_disabled_variant(self):
        result=self.render('render','proof','--seconds','1','--width','64','--disable','moving','--out',self.root/'proof')
        self.assertEqual(result['variants'],2);self.assertEqual(result['frames'],6)
        current=list((self.root/'proof/current').glob('*.png'));disabled=list((self.root/'proof/disabled').glob('*.png'))
        self.assertEqual(len(current),6);self.assertEqual(len(disabled),6)
        self.assertGreater(len({p.read_bytes() for p in current}),1)
        self.assertEqual(len({p.read_bytes() for p in disabled}),1)
        self.assertNotEqual(current[0].read_bytes(),disabled[0].read_bytes())
        self.assertIn('1× (actual speed)',Path(result['output']).read_text())
        self.assertEqual((self.project/'edit/cut.json').read_bytes(),self.source)
    def test_disabling_a_visible_track_hides_every_frame(self):
        path=self.project/'edit/cut.json';scene=json.loads(path.read_text())
        scene['layers'][0]['tracks']={'visible':{'interpolation':'hold','keys':[[0,True],[1,False],[1.5,True],[2,True]]}}
        path.write_text(json.dumps(scene))
        result=self.render('render','proof','--seconds','2','--width','64','--disable','moving','--out',self.root/'tracked-proof')
        disabled=list((self.root/'tracked-proof/disabled').glob('*.png'))
        self.assertEqual(len(disabled),12)
        self.assertEqual(len({p.read_bytes() for p in disabled}),1)
    def test_invalid_ratio_unknown_effect_and_fractional_frame_reject_before_output(self):
        for args in [('render','frame','--width','64','--height','64'),
                     ('render','proof','--disable','absent'),('render','proof','--seconds','.1')]:
            with self.assertRaises(CommandError):self.render(*args,'--out',self.root/'invalid')
            self.assertFalse((self.root/'invalid').exists())
    def test_asset_tamper_and_path_escape_reject_before_output(self):
        source=self.project/'art/pattern.png';original=source.read_bytes();source.write_bytes(original+b'changed')
        with self.assertRaisesRegex(CommandError,'hash'):self.render('render','frame','--out',self.root/'invalid')
        self.assertFalse((self.root/'invalid').exists());source.write_bytes(original)
        outside=self.root/'outside.png';outside.write_bytes(original)
        catalog_path=self.project/'art/library.json';catalog=json.loads(catalog_path.read_text());catalog['assets'][0]['file']='../outside.png';catalog_path.write_text(json.dumps(catalog))
        with self.assertRaisesRegex(CommandError,'inside'):self.render('render','frame','--out',self.root/'escape')
        self.assertFalse((self.root/'escape').exists())
    def test_selected_audio_is_required_and_exact_not_synthesized(self):
        audio=self.root/'short.wav'
        with wave.open(str(audio),'wb') as file:
            file.setnchannels(2);file.setsampwidth(2);file.setframerate(48000);file.writeframes(b'\0'*48000*4)
        with self.assertRaisesRegex(CommandError,'exactly match'):
            self.render('render','video','--audio',audio,'--out',self.root/'invalid-audio')
        self.assertFalse((self.root/'invalid-audio').exists())


class CapabilityTests(unittest.TestCase):
    def test_media_changed_during_decode_invalidates_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'media.mp4';source.write_bytes(b'original encoded file')
            before=hashlib.sha256(source.read_bytes()).hexdigest()
            def fake_decode(*args,**kwargs):
                source.write_bytes(b'different encoded file')
                return {'ok':True,'decoded_frames':12}
            with patch('ambiance_studio.native_media.json_command',side_effect=fake_decode):
                result=media_verification.verify_media(ROOT/'native/media/media.m',source,root/'report',64,96,6,12,0,12)
            self.assertFalse(result['ok']);self.assertFalse(result['input_unchanged'])
            self.assertEqual(result['input_sha256'],before)
            self.assertNotEqual(result['input_sha256'],result['input_sha256_after'])
    def test_invalid_explicit_canvas_override_does_not_silently_fall_back(self):
        with patch.dict(os.environ,{'AMBIANCE_CANVAS_MODULE':'/nonexistent/explicit/canvas'}):
            result=rendering.capabilities()
        self.assertFalse(result['frame_render']);self.assertIn('AMBIANCE_CANVAS_MODULE',result['raster']['error'])
    def test_unsupported_native_platform_is_explicit(self):
        with patch('ambiance_studio.native_media.platform.system',return_value='Linux'):
            with self.assertRaisesRegex(CommandError,'requires macOS'):
                native_media.native_binary(Path('/tmp/unused'))


@unittest.skipUnless(Image and os.environ.get('AMBIANCE_TEST_NATIVE')=='1' and sys.platform=='darwin','Set AMBIANCE_TEST_NATIVE=1 with macOS media-service access')
class NativeTests(unittest.TestCase):
    def test_preroll_pcm_mux_exact_presentation_and_mismatch_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);project=fixture(root);audio=root/'master.wav'
            # Four-second stereo sine with non-zero signal on both sides of the join.
            pcm=b''.join(struct.pack('<hh',int(4000*math.sin(2*math.pi*440*n/48000)),int(3000*math.sin(2*math.pi*660*n/48000))) for n in range(192000))
            with wave.open(str(audio),'wb') as file:
                file.setnchannels(2);file.setsampwidth(2);file.setframerate(48000);file.writeframes(pcm)
            result=rendering.run(parse('render','video','--repeats','2','--audio',audio,'--out',root/'encoded'),project)
            self.assertTrue(result['ok']);self.assertEqual(result['encoder_preroll_frames'],12)
            self.assertTrue(result['preroll_trim']['start_is_sync_frame'])
            verify=result['verification'];self.assertEqual(verify['decoded_frames'],24)
            self.assertEqual(verify['audio']['presented_samples'],192000)
            self.assertTrue(verify['audio']['contiguous_presented_samples'])
            self.assertTrue(verify['input_unchanged'])
            self.assertEqual(Path(result['audio_source']['snapshot']).read_bytes(),audio.read_bytes())
            self.assertAlmostEqual(verify['audio']['track_duration'],4)
            self.assertEqual(verify['joins'][0]['first_frame_to_repeated_start']['rgb_mean_absolute_difference'],0)
            self.assertTrue((root/'encoded/verification/contacts/decoded-0012.png').is_file())
            self.assertTrue((root/'encoded/verification/contacts/decoded-audio.wav').is_file())
            wrong=rendering.run(parse('media','verify',result['output'],'--frames','25','--audio-tracks','1','--out',root/'wrong'),project)
            self.assertFalse(wrong['ok']);self.assertTrue((root/'wrong/media-report.json').is_file())
            with self.assertRaises(CommandError):
                rendering.run(parse('render','video','--audio',result['output'],'--out',root/'aac-rejected'),project)
            self.assertFalse((root/'aac-rejected').exists())


if __name__=='__main__':unittest.main()
