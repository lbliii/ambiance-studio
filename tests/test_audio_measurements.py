"""Deterministic published reference signals plus explicit unsupported states.

Signal definitions/tolerances: EBU Tech 3341 (2023), table 1 cases 1-5,15-19.
Generated locally, not redistributed EBU recordings; no full conformance claim.
"""
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import wave
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from ambiance_studio import audio_measurements as meter, audio_encoding, native_media, rendering
from ambiance_studio.file_identity import digest
from ambiance_studio.errors import CommandError


def signal(path, segments, *, channels=2, rate=48000, frequency=1000, phase=0, taper=False, invert=False):
    """PCM24 with per-channel sine peak in dBFS; segment durations in seconds."""
    data = bytearray(); index = 0
    for seconds, db in segments:
        frames = round(seconds*rate); amplitude = 0 if db is None else 10**(db/20)
        for i in range(frames):
            gain = min(1, i/(rate*.01), (frames-1-i)/(rate*.01)) if taper else 1
            x = round(amplitude*gain*math.sin(2*math.pi*frequency*index/rate+math.radians(phase))*(2**23))
            x = min(2**23-1,max(-2**23,x)); index += 1
            for ch in range(channels): data.extend((-x if invert and ch==1 else x).to_bytes(3,'little',signed=True))
    with wave.open(str(path),'wb') as f:
        f.setnchannels(channels); f.setsampwidth(3); f.setframerate(rate); f.writeframes(data)


class MeasurementTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name); self.path=self.root/'source.wav'

    def test_ebu_integrated_reference_cases_1_to_5(self):
        cases=[([(20,-23)],-23), ([(20,-33)],-33), ([(10,-36),(60,-23),(10,-36)],-23),
               ([(10,-72),(10,-36),(60,-23),(10,-36),(10,-72)],-23),
               ([(20,-26),(20.1,-20),(20,-26)],-23)]
        for segments, expected in cases:
            with self.subTest(segments=segments):
                signal(self.path,segments); r=meter.measure_file(self.path)
                self.assertAlmostEqual(r['integrated_lufs']['value'],expected,delta=.1)
                self.assertEqual(r['source']['sha256'],digest(self.path))
                self.assertEqual(r['backend']['version'],1)
                self.assertEqual(len(r['implementation']['meter_sha256']),64)

    def test_ebu_true_peak_reference_cases_15_to_19(self):
        for divisor,phase,amplitude,expected in [(4,0,.5,-6),(4,45,.5,-6),(6,60,.5,-6),(8,67.5,.5,-6),(4,45,1.41,3)]:
            with self.subTest(divisor=divisor,phase=phase,amplitude=amplitude):
                signal(self.path,[(.2,20*math.log10(amplitude))],frequency=48000/divisor,phase=phase,taper=True)
                r=meter.measure_file(self.path); tp=r['true_peak']['dbtp']
                self.assertGreaterEqual(tp,expected-.4); self.assertLessEqual(tp,expected+.2)
                if divisor==4 and phase==45: self.assertGreater(tp-r['sample_peak']['dbfs'],2.5)

    def test_mono_stereo_and_phase_cancellation_are_distinct(self):
        results=[]
        for channels,invert in [(1,False),(2,False),(2,True)]:
            signal(self.path,[(1,-23)],channels=channels,invert=invert); results.append(meter.measure_file(self.path))
        mono,stereo,anti=results
        self.assertAlmostEqual(stereo['integrated_lufs']['value']-mono['integrated_lufs']['value'],10*math.log10(2),places=8)
        self.assertAlmostEqual(stereo['integrated_lufs']['value'],anti['integrated_lufs']['value'],places=8)
        self.assertEqual(anti['mono_fold_down']['cancellation'],'complete')
        self.assertEqual(anti['mono_fold_down']['rms_ratio'],0)
        self.assertIsNone(anti['mono_fold_down']['integrated_lufs']['value'])
        self.assertEqual(anti['mono_fold_down']['integrated_lufs']['status'],'silence')

    def test_silence_short_and_below_gate_have_no_invented_lufs(self):
        for segments,status in [([(1,None)],'silence'), ([(.399,-23)],'insufficient_duration'), ([(1,-80)],'below_gate')]:
            signal(self.path,segments); r=meter.measure_file(self.path)
            self.assertEqual(r['integrated_lufs']['status'],status); self.assertIsNone(r['integrated_lufs']['value'])
            json.dumps(r,allow_nan=False)
        signal(self.path,[(.05,None),(.01,-10),(.94,None)])
        self.assertEqual(meter.measure_file(self.path)['integrated_lufs']['status'],'measured')

    def test_complete_blocks_and_interval_hash(self):
        signal(self.path,[(.55,-23)])
        r=meter.measure_file(self.path)
        self.assertEqual(r['integrated_lufs']['complete_blocks'],2)
        self.assertEqual(r['integrated_lufs']['trailing_frames_excluded'],2400)
        with self.assertRaisesRegex(ValueError,'hash changed'): meter.measure_file(self.path,'0'*64)
        signal(self.path,[(.5,-23)],rate=44100)
        with self.assertRaisesRegex(ValueError,'48 kHz'): meter.measure_file(self.path)
        signal(self.path,[(.5,-23)],channels=3)
        with self.assertRaisesRegex(ValueError,'mono or stereo'): meter.measure_file(self.path)

    def test_unclipped_float_and_truncated_nonfinite_failures(self):
        path=self.root/'decoded.f32le'; path.write_bytes(struct.pack('<ff',1.2,-1.2))
        info={'codec':'pcm_float','bits':32,'sample_rate':48000,'channels':1,'frames':2,'data_offset':0}
        r=meter.measure_file(path,decoded_format=info)
        self.assertGreater(r['sample_peak']['dbfs'],0)
        self.assertEqual(r['integrated_lufs']['status'],'insufficient_duration')
        path.write_bytes(b'x')
        with self.assertRaisesRegex(ValueError,'Incomplete'): meter.measure_file(path,decoded_format=info)
        path.write_bytes(struct.pack('<ff',float('nan'),0))
        with self.assertRaisesRegex(CommandError,'Non-finite'): meter.measure_file(path,decoded_format=info)

    def test_invalid_bitrate_and_silent_export_reject_before_native(self):
        for value in [0,128000,383999,True,'384000']:
            with self.assertRaises(CommandError): audio_encoding.encoding_settings(value)
        with self.assertRaisesRegex(CommandError,'requires'): audio_encoding.encoding_settings(384000,has_audio=False)
        self.assertEqual(audio_encoding.encoding_settings()['bitrate_bps'],256000)
        from test_rendering import fixture,parse
        project=fixture(self.root); signal(self.path,[(2,-23)])
        with patch.object(native_media,'native_binary') as native:
            with self.assertRaises(CommandError):
                rendering.run(parse('render','video','--audio',self.path,'--audio-bitrate','383999','--out',self.root/'invalid'),project)
            native.assert_not_called()
        self.assertFalse((self.root/'invalid').exists())

    def test_iteration_bitrate_validator_and_typed_argv(self):
        from ambiance_studio.iteration_plan import validate_recipe
        from ambiance_studio.media_operations import ComposeRequest,request_argv
        recipe={'format':'ambiance-iteration','schema_version':1,'id':'trial','revision':'rev',
                'editions':[{'role':'score','audio':'tone.wav','audio_bitrate':320000}]}
        validate_recipe(recipe)
        request=ComposeRequest(revision='rev',edition='score',picture=self.root/'picture.mp4',picture_receipt='render.json',audio=self.path,audio_bitrate=320000)
        argv=request_argv(self.root,request,self.root/'out')
        self.assertEqual(argv[argv.index('--audio-bitrate')+1],'320000')
        recipe['editions'][0]['audio_bitrate']=383999
        with self.assertRaises(CommandError):validate_recipe(recipe)

    def test_iteration_preflight_starts_no_picture_on_unsupported_and_skips_saved_outputs(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from ambiance_studio import iterations,editions
        from ambiance_studio.media_operations import execute_job
        recipe={'id':'trial','revision':'rev','schema_version':1,'editions':[{'role':'score','audio':'tone.wav','audio_bitrate':384000}]}
        progress=SimpleNamespace(executor=execute_job,state={'steps':{}},directory=self.root/'run',save=Mock(),step=Mock())
        with patch.object(native_media,'native_binary',return_value='backend'),patch.object(audio_encoding,'preflight',side_effect=CommandError('unsupported bitrate')):
            with self.assertRaisesRegex(CommandError,'unsupported'):iterations._produce_delivery(self.root,recipe,progress)
            progress.step.assert_not_called()
        jobs=[{'stage':'compose','key':'score','role':'score','edition':'trial-score'}]
        progress.state['steps']['score']={'result':'previously completed'}
        with patch.object(native_media,'native_binary') as native:
            self.assertEqual(audio_encoding.preflight_iteration_audio(self.root,recipe,jobs,progress),[])
            native.assert_not_called()
        progress.state['steps']={}
        receipt=editions.edition_path(self.root,'rev','trial-score');receipt.parent.mkdir(parents=True);receipt.write_text('{}')
        # The recovery owner, not codec preflight, checks saved edition integrity.
        with patch.object(native_media,'native_binary') as native:
            self.assertEqual(audio_encoding.preflight_iteration_audio(self.root,recipe,jobs,progress),[])
            native.assert_not_called()

    def test_cli_measure_owns_envelope_and_preserves_original(self):
        (self.root/'ambiance-project.json').write_text(json.dumps({'version':1,'scene':'scene.json','catalog':'catalog.json'}))
        signal(self.path,[(.4,-23)]); original=digest(self.path); out=self.root/'measurement.json'
        run=subprocess.run([str(ROOT/'ambiance'),'--project',str(self.root),'audio','measure','source.wav',
                            '--source-sha256',original,'--out',str(out)],capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stdout+run.stderr)
        self.assertEqual(json.loads(run.stdout),json.loads(out.read_text()))
        self.assertEqual(digest(self.path),original)
        run=subprocess.run([str(ROOT/'ambiance'),'--project',str(self.root),'audio','measure','source.wav','--out',str(self.path)],capture_output=True,text=True)
        self.assertEqual(run.returncode,2); self.assertEqual(digest(self.path),original)


@unittest.skipUnless(os.environ.get('AMBIANCE_TEST_NATIVE')=='1','Requires actual macOS media-service access')
class AudioEncodingNativeTests(unittest.TestCase):
    def test_384_trial_is_admitted_only_when_applicable_before_raster(self):
        from test_rendering import fixture,parse
        from ambiance_studio import render_execution
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); project=fixture(root); source=root/'tone.wav'
            signal(source,[(2,-23)])
            binary=native_media.native_binary(project)
            capability=audio_encoding.preflight(binary,audio_encoding.encoding_settings(256000))
            if 384000 in capability['applicable_bitrates_bps']:
                self.assertEqual(audio_encoding.preflight(binary,audio_encoding.encoding_settings(384000))['bitrate_bps'],384000)
            else:
                with patch.object(render_execution,'require_node') as raster:
                    with self.assertRaisesRegex(CommandError,'384000 is unsupported'):
                        rendering.run(parse('render','video','--audio',source,'--audio-bitrate','384000','--out',root/'unsupported'),project)
                    raster.assert_not_called()
                self.assertFalse((root/'unsupported').exists())

    def test_configured_native_mux_decode_and_legacy_pcm16(self):
        from test_rendering import fixture,parse
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); project=fixture(root); source=root/'tone.wav'
            signal(source,[(2,-18)],frequency=12000,phase=45,taper=True)
            original=digest(source)
            for rate in [256000,320000]:
                r=rendering.run(parse('render','video','--audio',source,'--audio-bitrate',str(rate),'--out',root/str(rate)),project)
                self.assertTrue(r['ok'],r)
                self.assertEqual(r['audio_encoding']['bitrate_bps'],rate)
                self.assertEqual(r['composition']['audio_encoding']['bitrate_bps'],rate)
                decoded=r['verification']['audio']; m=decoded['level_measurement']
                self.assertEqual(m['interval']['frames'],96000)
                self.assertEqual(m['encoded_source']['sha256'],r['output_sha256'])
                self.assertEqual(m['source']['sha256'],digest(Path(decoded['decoded_float'])))
                with wave.open(decoded['decoded_wav']) as wav:
                    self.assertEqual(wav.getsampwidth(),2); self.assertEqual(wav.getnframes(),96000)
                    legacy=wav.readframes(96000)
                floating=Path(decoded['decoded_float']).read_bytes()
                error=max(abs(q[0]/32768-max(-1,min(32767/32768,f[0]))) for q,f in zip(struct.iter_unpack('<h',legacy),struct.iter_unpack('<f',floating)))
                self.assertLessEqual(error,.5/32768+1e-7)
                self.assertEqual(digest(source),original)
                self.assertEqual(r['audio_source_measurement']['source']['sha256'],original)


if __name__=='__main__': unittest.main()
