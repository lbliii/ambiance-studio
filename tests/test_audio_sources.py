"""Source preservation, strict formats, resampling and revision dependency tests."""
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import wave

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from ambiance_studio import audio, audio_sources as sources, audio_source_backend as backend, revisions
from ambiance_studio.audio_source_formats import inspect_structure
from ambiance_studio.revision_dependencies import Collector
from ambiance_studio.errors import CommandError


def wav(path,rate=48000,channels=1,frames=4800,bits=16):
    with wave.open(str(path),'wb') as f:
        f.setnchannels(channels);f.setsampwidth(bits//8);f.setframerate(rate)
        b=bytearray()
        for i in range(frames):
            for ch in range(channels):
                value=round(math.sin(i*2*math.pi*(440 if ch==0 else 660)/rate)*.2*(2**(bits-1)-1))
                b.extend((value+128).to_bytes(1,'little') if bits==8 else value.to_bytes(bits//8,'little',signed=True))
        f.writeframes(b)


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.project=Path(self.tmp.name).resolve()
        self.source=self.project/'source.wav';wav(self.source)

    def prepare(self,id='p1',backend='pcm',**kw):
        return sources.prepare_source(self.project,'source.wav',backend,audio.digest(self.source),id,**kw)

    def test_mono_stereo_exact_expansion_and_inspection_pure(self):
        for channels in [1,2]:
            for bits in [8,16,24]:
                wav(self.source,channels=channels,bits=bits)
                before=set(self.project.rglob('*'));original=self.source.read_bytes()
                inspected=sources.inspect_source(self.project,'source.wav','pcm')
                self.assertEqual(set(self.project.rglob('*')),before)
                self.assertEqual(inspected['format']['channels'],channels)
                r=self.prepare(f'c{channels}b{bits}');working=self.project/r['working']['path']
                left,right,info=audio.read_wav(working);ol,orr,_=audio.read_wav(self.source)
                self.assertEqual(left,ol);self.assertEqual(right,orr);self.assertEqual(info['bits'],24)
                self.assertEqual(self.source.read_bytes(),original)
                checked=sources.validate_preparation(self.project,Path(r['receipt']));self.assertTrue(checked['ok'])
                self.assertEqual(len(checked['dependencies']),5)
                self.assertNotIn('masters',checked)

    def test_duplicate_id_and_changed_original_are_rejected(self):
        r=self.prepare();before=Path(r['receipt']).read_bytes()
        with self.assertRaisesRegex(ValueError,'already exists'):self.prepare()
        self.assertEqual(Path(r['receipt']).read_bytes(),before)
        expected=audio.digest(self.source);self.source.write_bytes(self.source.read_bytes()+b'x')
        with self.assertRaisesRegex(ValueError,'hash changed'):sources.prepare_source(self.project,'source.wav','pcm',expected,'p2')
        with self.assertRaisesRegex(ValueError,'dependency changed'):sources.validate_preparation(self.project,Path(r['receipt']))
        self.assertFalse((self.project/'audio/preparations/p2').exists())

    def test_tampered_working_original_recipe_and_receipt(self):
        r=self.prepare();path=Path(r['receipt']);data=json.loads(path.read_text())
        for key in ['original','working','recipe']:
            target=self.project/data[key]['path'];original=target.read_bytes();target.write_bytes(original+b'x')
            with self.assertRaisesRegex(ValueError,'dependency changed'):sources.validate_preparation(self.project,path)
            target.write_bytes(original)
        data['conversion']['target_frames']+=1;path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,'integrity'):sources.validate_preparation(self.project,path)

    def test_wrong_rate_and_unsupported_layout_publish_nothing(self):
        wav(self.source,rate=44100)
        with self.assertRaisesRegex(ValueError,'does not resample'):self.prepare()
        self.assertFalse((self.project/'audio').exists())
        wav(self.source,channels=3)
        with self.assertRaisesRegex(ValueError,'mono or stereo'):self.prepare()
        self.assertFalse((self.project/'audio').exists())

    def test_truncated_wav_chunk_alignment_and_unsupported_float(self):
        original=self.source.read_bytes()
        for candidate in [original[:-1],original[:30],original[:4]+struct.pack('<I',len(original))+original[8:]]:
            self.source.write_bytes(candidate)
            with self.assertRaises(ValueError):self.prepare()
        data=bytearray(original);data[20:22]=struct.pack('<H',3);self.source.write_bytes(data)
        with self.assertRaisesRegex(ValueError,'integer PCM'):self.prepare()
        self.assertFalse((self.project/'audio').exists())

    def test_explicit_wav_speaker_layout_is_preserved_or_rejected(self):
        # Stereo count with a non-L/R mask must not be silently reinterpreted.
        payload=struct.pack('<hhhh',1000,-1000,2000,-2000)
        for mask,accepted in [(3,True),(12,False)]:
            fmt=struct.pack('<HHIIHHHHI',65534,2,48000,192000,4,16,22,16,mask)+bytes.fromhex('0100000000001000800000aa00389b71')
            chunks=b'fmt '+struct.pack('<I',len(fmt))+fmt+b'data'+struct.pack('<I',len(payload))+payload
            self.source.write_bytes(b'RIFF'+struct.pack('<I',len(chunks)+4)+b'WAVE'+chunks)
            if accepted:self.assertEqual(inspect_structure(self.source)['channels'],2)
            else:
                with self.assertRaisesRegex(ValueError,'channel layout'):self.prepare()

    def test_raw_declaration_and_byte_exact_source_identity(self):
        raw=self.project/'cue.pcm';raw.write_bytes(struct.pack('<hhhh',1000,-1000,2000,-2000))
        with self.assertRaisesRegex(ValueError,'explicit'):sources.inspect_source(self.project,'cue.pcm','pcm')
        declaration={'format':'s16le','sample_rate':48000,'channels':2}
        r=sources.prepare_source(self.project,'cue.pcm','pcm',audio.digest(raw),'raw',declaration)
        info=sources.validate_preparation(self.project,Path(r['receipt']))['working_format']
        self.assertEqual(info['frames'],2);self.assertEqual(info['channels'],2)
        with self.assertRaisesRegex(ValueError,'override'):sources.inspect_source(self.project,'source.wav','pcm',declaration)
        raw.write_bytes(raw.read_bytes()+b'x')
        with self.assertRaisesRegex(ValueError,'Truncated'):sources.inspect_source(self.project,'cue.pcm','pcm',declaration)

    def test_mp3_structure_and_declared_frame_truncation(self):
        # Three valid-sized MPEG1 Layer III frames; structural test, no listening claim.
        header=bytes.fromhex('fffb9000');frame=bytearray(header+b'\0'*413)
        frame[36:48]=b'Info'+struct.pack('>II',1,2)
        p=self.project/'fixture.mp3';p.write_bytes(frame+(header+b'\0'*413)*2)
        self.assertEqual(inspect_structure(p)['mpeg_frames'],3)
        for data in [p.read_bytes()[:-1],p.read_bytes()[:-417],b'ID3\x04\0\0\0\0\x10\0']:
            p.write_bytes(data)
            with self.assertRaisesRegex(ValueError,'Truncated'):inspect_structure(p)

    def test_mp4_malformed_lengths_and_unknown_format(self):
        p=self.project/'fixture.m4a'
        for data in [struct.pack('>I4s',32,b'ftyp')+b'x',b'garbage',struct.pack('>I4s',4,b'ftyp')]:
            p.write_bytes(data)
            with self.assertRaises(ValueError):inspect_structure(p)

    def test_symlink_escape_and_provenance_validation(self):
        with tempfile.TemporaryDirectory() as external:
            other=Path(external)/'cue.wav';wav(other);(self.project/'escape.wav').symlink_to(other)
            with self.assertRaisesRegex(ValueError,'inside'):sources.inspect_source(self.project,'escape.wav','pcm')
        for provenance in [{'api_key':'secret'}, {'retrieval':{'signed_url':'https://example.com?token=abc'}}, {'generation':{'route':'Bearer abc'}}]:
            with self.assertRaises(ValueError):self.prepare(provenance=provenance)
        self.assertFalse((self.project/'audio').exists())

    def test_revision_adapter_never_marks_source_as_complete_mix(self):
        r=self.prepare();collector=Collector(self.project);collector.preparation(Path(r['receipt']),0)
        self.assertEqual(collector.masters,[]);self.assertEqual(collector.sound_complete,set())
        roles={x['role'] for x in collector.refs}
        self.assertIn('audio_prepared_source',roles);self.assertIn('audio_source_original',roles)

    def test_public_cli_and_revision_capture_pins_preparation(self):
        # Minimal real command replay, no fake media edition or review.
        (self.project/'ambiance-project.json').write_text(json.dumps({'version':1,'scene':'scene.json','catalog':'catalog.json'}))
        (self.project/'project.json').write_text(json.dumps({'version':1,'title':'Audio fixture','reference':None}))
        (self.project/'pipeline.json').write_text(json.dumps({'version':1,'gates':[]}))
        (self.project/'scene.json').write_text(json.dumps({'version':1,'canvas':{'width':32,'height':32,'fps':30,'loop_seconds':1,'background':'#000000'},'camera':{'overscan':1,'x_amplitude':0,'y_amplitude':0,'zoom_amplitude':0},'groups':[],'layers':[]}))
        (self.project/'catalog.json').write_text(json.dumps({'version':1,'assets':[]}))
        def cli(*argv):
            run=subprocess.run([str(ROOT/'ambiance'),'--project',str(self.project),*argv],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stdout+run.stderr);return json.loads(run.stdout)['data']
        info=cli('audio','source-inspect','source.wav','--backend','pcm')
        result=cli('audio','source-prepare','source.wav','--backend','pcm','--source-sha256',info['source']['sha256'],'--preparation-id','cli')
        receipt=str(Path(result['receipt']).relative_to(self.project));cli('audio','source-check',receipt)
        selection=self.project/'selection.json';selection.write_text(json.dumps({'format':'ambiance-revision-selection','schema_version':1,'scene':'scene.json','catalog':'catalog.json','audio':{'preparations':[receipt]}}))
        cli('revision','capture','audio-fixture','--selection',str(selection));cli('revision','check','audio-fixture')
        manifest=json.loads((self.project/'revisions/audio-fixture/manifest.json').read_text())
        self.assertIn('audio_prepared_source',json.dumps(manifest))
        self.source.write_bytes(self.source.read_bytes()+b'x')
        run=subprocess.run([str(ROOT/'ambiance'),'--project',str(self.project),'revision','check','audio-fixture'],capture_output=True,text=True)
        self.assertNotEqual(run.returncode,0)

    def test_backend_failure_publishes_nothing(self):
        with patch.object(backend,'convert',side_effect=CommandError('decoder unavailable','runtime_error',3)),patch.object(backend,'identity',return_value={'id':'macos-afconvert'}),patch.object(backend,'probe',return_value={'codec':'pcm_integer','sample_rate':48000,'channels':1}):
            with self.assertRaises(CommandError):self.prepare(backend='macos-afconvert')
        self.assertFalse((self.project/'audio').exists())


@unittest.skipUnless(os.environ.get('AMBIANCE_TEST_NATIVE')=='1','Set AMBIANCE_TEST_NATIVE=1 for actual Core Audio decode/resample')
class NativeSourceTests(unittest.TestCase):
    setUp = SourceTests.setUp
    prepare = SourceTests.prepare
    # Real local compressed fixtures complement the portable invariants.
    def test_native_aac_alac_mono_stereo_and_resampling(self):
        self.assertTrue(backend.capabilities()['macos-afconvert']['available'],'Core Audio unavailable')
        for channels in [1,2]:
            wav(self.source,rate=44100,channels=channels,frames=4410)
            for codec in ['aac','alac']:
                compressed=self.project/f'c{channels}-{codec}.m4a'
                backend.execute([backend.AFCONVERT,'-f','m4af','-d',codec,self.source,compressed])
                inspected=sources.inspect_source(self.project,compressed.name,'macos-afconvert')
                self.assertTrue(inspected['format']['decoded']['complete']);self.assertEqual(inspected['format']['bits'],None if codec=='aac' else 16)
                r=sources.prepare_source(self.project,compressed.name,'macos-afconvert',audio.digest(compressed),f'{channels}-{codec}',provenance={'origin_kind':'synthesized','generation':{'model':'local-test-tone'},'retrieval':{'returned_format':codec}})
                checked=sources.validate_preparation(self.project,Path(r['receipt']))
                self.assertEqual(checked['working_format']['channels'],channels);self.assertEqual(checked['working_format']['frames'],4800)
                if codec=='alac':
                    # Same take lossless retrieval: preserve known channel waveforms through resampling.
                    left,right,_=audio.read_wav(self.project/r['working']['path'])
                    reference=[.2*math.sin(i*2*math.pi*440/48000) for i in range(4800)]
                    rms=math.sqrt(sum((a-b)**2 for a,b in zip(left[100:-100],reference[100:-100]))/4600)
                    self.assertLess(rms,0.0002)
                    if channels==2:self.assertNotEqual(left,right)
                original=compressed.read_bytes();compressed.write_bytes(original[:-10])
                with self.assertRaises(ValueError):sources.inspect_source(self.project,compressed.name,'macos-afconvert')

    def test_native_non_integral_duration_and_pcm32(self):
        wav(self.source,rate=44100,frames=101,bits=32,channels=2)
        r=self.prepare(backend='macos-afconvert');checked=sources.validate_preparation(self.project,Path(r['receipt']))
        self.assertIn(checked['working_format']['frames'],[109,110])
        self.assertEqual(r['conversion']['ideal_target_frames'],{'numerator':101*48000,'denominator':44100})


if __name__=='__main__':unittest.main()
