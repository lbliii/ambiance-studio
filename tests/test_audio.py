"""Deterministic media fixtures exercise arrangement and failure boundaries."""
from array import array
import argparse
import json
from pathlib import Path
import sys
import tempfile
import unittest
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ambiance_studio import audio


class AudioTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name); (self.project/'audio').mkdir()
        self.source = self.project/'audio/cue.wav'
        # Known four samples allow sample-exact region, repeat and wrap assertions.
        self.wav(self.source, [4096, 8192, 12288, 16384])
        self.session = {'format': audio.FORMAT, 'schema_version': 1, 'id': 'fixture', 'sample_rate': 8, 'frames': 8,
                        'sources': [{'id': 'cue', 'path': 'audio/cue.wav', 'sha256': audio.digest(self.source)}],
                        'stems': [{'id': 'object', 'gain_db': 0}],
                        'clips': [{'id': 'gesture', 'source': 'cue', 'stem': 'object', 'source_start_frame': 0, 'frames': 4, 'at_frame': 6, 'circular_tail': True, 'picture_event': 'mummy gesture'}]}
        self.path = self.project/'audio/session-v1.json'; self.save()

    def wav(self, path, values, rate=8, channels=1):
        with wave.open(str(path), 'wb') as f:
            f.setnchannels(channels); f.setsampwidth(2); f.setframerate(rate)
            values = array('h', values)
            if sys.byteorder != 'little': values.byteswap()
            f.writeframes(values.tobytes())

    def save(self): self.path.write_text(json.dumps(self.session))

    def mix(self, name='proof', **kwargs): return audio.render_run(self.project, self.path, name, **kwargs)

    def test_exact_sample_circular_tail_stems_reconstruct_and_immutable_session(self):
        before = self.path.read_bytes(); report = self.mix(); folder = Path(report['run'])
        left, right, info = audio.read_wav(folder/'mix/master.wav')
        self.assertEqual(list(left), [0.375, .5, 0, 0, 0, 0, .125, .25])
        self.assertEqual(left, right); self.assertEqual(info['frames'], 8)
        self.assertEqual((folder/'session.json').read_bytes(), before)
        self.assertEqual(self.path.read_bytes(), before)
        check = audio.check_audio(folder); self.assertTrue(check['ok'], check)
        self.assertEqual(check['variants']['mix']['reconstruction_max_error'], 0)
        with self.assertRaisesRegex(ValueError, 'already exists'): self.mix()
        self.assertEqual((folder/'session.json').read_bytes(), before)

    def test_tail_longer_than_loop_and_stem_named_master(self):
        self.session['frames'] = 2; self.session['stems'][0]['id'] = 'master'
        self.session['clips'][0].update(stem='master', at_frame=1)
        self.save(); result = self.mix(); folder = Path(result['run'])
        left, _, _ = audio.read_wav(folder/'mix/master.wav')
        self.assertEqual(list(left), [.75, .5])
        self.assertTrue((folder/'mix/stem-master.wav').exists())
        self.assertTrue(audio.check_audio(folder)['ok'])

    def test_master_sum_clipping_fails_without_reducing_gain(self):
        self.session['stems'].append({'id':'second'})
        self.session['clips'].append(dict(self.session['clips'][0], id='second-clip', stem='second'))
        self.save()
        with self.assertRaisesRegex(ValueError, 'clip'): self.mix()
        self.assertFalse((self.project/'audio/runs/proof').exists())

    def test_changed_or_missing_selected_source_fails_even_when_muted(self):
        self.source.write_bytes(self.source.read_bytes()+b'changed')
        with self.assertRaisesRegex(ValueError, 'changed'): self.mix(variants={'mix': {'mute': ['object']}})
        self.assertFalse((self.project/'audio/runs/proof').exists())
        self.source.unlink()
        with self.assertRaisesRegex(ValueError, 'missing'): self.mix()

    def test_region_repeat_fades_and_pan_are_applied_at_authored_samples(self):
        self.session['frames'] = 12
        self.session['clips'][0] = dict(self.session['clips'][0], source_start_frame=1, frames=3, at_frame=1,
                                       repeat=2, every_frames=5, circular_tail=False,
                                       fade_in_frames=2, fade_out_frames=2, pan=-1)
        self.save(); result = self.mix(); left, right, _ = audio.read_wav(Path(result['run'])/'mix/master.wav')
        self.assertEqual([i for i, x in enumerate(left) if x], [2, 7])
        self.assertAlmostEqual(left[2], .375); self.assertEqual(list(right), [0]*12)

    def test_pan_travel_and_stereo_preservation(self):
        self.session['clips'][0].update(at_frame=0, circular_tail=False, pan_points=[[0,-1], [3,1]])
        self.save(); result = self.mix(); left, right, _ = audio.read_wav(Path(result['run'])/'mix/master.wav')
        self.assertEqual(left[0], .125); self.assertEqual(right[0], 0)
        self.assertEqual(left[3], 0); self.assertEqual(right[3], .5)
        # No pan means preserve the source stereo, including phase information.
        self.wav(self.source, [4096,-4096,8192,-8192], channels=2)
        self.session['sources'][0]['sha256'] = audio.digest(self.source)
        self.session['clips'][0] = {'id':'stereo','source':'cue','stem':'object','at_frame':0,'frames':2}
        self.save(); result = self.mix('stereo'); metrics = result['variants']['mix']['master']['measurements']
        self.assertIsNone(metrics['mono_rms_dbfs']); self.assertGreater(metrics['sample_peak'], 0)

    def test_compare_gain_is_relative_and_does_not_normalize_muted_sources(self):
        self.session['stems'].append({'id':'room', 'gain_db':-6})
        self.session['clips'].append(dict(self.session['clips'][0], id='bed', stem='room'))
        self.save(); result = self.mix(variants={'A':{}, 'B':{'mute':['room'], 'gain_db_by_stem':{'object':-12}}})
        a = result['variants']['A']['master']['measurements']['rms_dbfs']
        b = result['variants']['B']['master']['measurements']['rms_dbfs']
        self.assertLess(b, a-12)
        self.assertEqual(result['variants']['B']['stems'][1]['measurements']['sample_peak'], 0)
        self.assertTrue(audio.check_audio(Path(result['run']))['ok'])

    def test_excerpt_includes_wrapped_tail_without_restarting_cue(self):
        result = self.mix(start_seconds=0, duration_seconds=.25)
        left, _, info = audio.read_wav(Path(result['run'])/'mix/master.wav')
        self.assertEqual(list(left), [.375, .5]); self.assertEqual(info['frames'], 2)
        event = result['variants']['mix']['master']['measurements']['event_windows'][0]
        self.assertEqual(event['start_frame'], 0); self.assertEqual(event['end_frame'], 2)

    def test_invalid_region_rate_unknown_fields_and_clipping_never_publish(self):
        self.session['clips'][0]['frames'] = 5; self.save()
        with self.assertRaisesRegex(ValueError, 'exceeds selected source'): self.mix()
        self.session['clips'][0]['frames'] = 4; self.session['sample_rate'] = 16; self.save()
        with self.assertRaisesRegex(ValueError, 'Sample rate mismatch'): self.mix()
        self.session['sample_rate'] = 8; self.session['reverb'] = {'size':1}; self.save()
        with self.assertRaisesRegex(ValueError, 'Unsupported session fields'): self.mix()
        del self.session['reverb']; self.session['master_gain_db'] = 20; self.save()
        with self.assertRaisesRegex(ValueError, 'clip'): self.mix()
        self.assertFalse((self.project/'audio/runs/proof').exists())
        self.assertEqual(list((self.project/'audio/runs').iterdir()), [])

    def test_import_is_explicit_and_does_not_overwrite_legacy_or_prior_session(self):
        legacy = self.project/'audio/legacy.json'; legacy.write_text(json.dumps({'stems':[{'id':'cue','path':'audio/cue.wav','gain_included':True,'offset_samples':0}]}))
        before = legacy.read_bytes(); result = audio.import_stems(self.project, legacy, 'stem-diagnostic-v1')
        new = Path(result['session']); self.assertEqual(legacy.read_bytes(), before)
        session, _ = audio.load_session(self.project, new)
        self.assertEqual(session['master_gain_db'], 0); self.assertEqual(session['sources'][0]['sha256'], audio.digest(self.source))
        with self.assertRaises(FileExistsError): audio.import_stems(self.project, legacy, 'stem-diagnostic-v1')
        self.assertEqual(legacy.read_bytes(), before)

    def test_check_detects_tampered_master_and_path_escape(self):
        result = self.mix(); folder = Path(result['run']); path = folder/'mix/master.wav'; path.write_bytes(path.read_bytes()+b'changed')
        self.assertFalse(audio.check_audio(folder)['ok'])
        self.session['sources'][0]['path'] = '../elsewhere.wav'; self.save()
        with self.assertRaisesRegex(ValueError, 'inside'): self.mix('escape')

    def test_parsers_and_source_inspection(self):
        parser = argparse.ArgumentParser(); audio.add_parsers(parser.add_subparsers(dest='command', required=True))
        args = parser.parse_args(['audio','inspect',str(self.path)])
        result = audio.run(args, self.project)
        self.assertEqual(result['sources'][0]['format']['frames'], 4)
        self.assertTrue(result['sources'][0]['selected']); self.assertEqual(result['timeline'][0]['picture_event'], 'mummy gesture')
        with self.assertRaisesRegex(ValueError, 'Unknown mute'): self.mix(variants={'B':{'mute':['unknown']}})


if __name__ == '__main__': unittest.main(verbosity=2)
