"""LIB-01 technical fixtures. Simulated observations exercise validation, not auditions."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import wave

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from ambiance_studio import audio, audio_sources, audio_library as lib, audio_materialization as material, cli
from ambiance_studio.audio_library_records import validate_version
from ambiance_studio.record_contracts import seal
from ambiance_studio.revision_dependencies import Collector


def tone(path, frames=480, channels=2):
    # Distinct channel/region bytes expose swaps, truncation and wrong excerpt indices.
    with wave.open(str(path), 'wb') as out:
        out.setnchannels(channels); out.setsampwidth(2); out.setframerate(48000)
        out.writeframes(b''.join(((i % 101-50)*(c+1)*20).to_bytes(2, 'little', signed=True) for i in range(frames) for c in range(channels)))


def project(path):
    path.mkdir()
    documents = {'ambiance-project.json': {'version':1,'scene':'scene.json','catalog':'catalog.json'},
        'project.json': {'version':1,'title':'LIB-01 fixture','reference':None}, 'pipeline.json': {'version':1,'gates':[]},
        'catalog.json': {'version':1,'assets':[]},
        'scene.json': {'version':1,'canvas':{'width':32,'height':32,'fps':30,'loop_seconds':1,'background':'#000000'},
                      'camera':{'overscan':1,'x_amplitude':0,'y_amplitude':0,'zoom_amplitude':0},'groups':[],'layers':[]}}
    for name, data in documents.items(): audio.write_json(path/name, data)


def invoke(*argv):
    stream = io.StringIO()
    with redirect_stdout(stream): code = cli.main(list(map(str, argv)))
    return code, json.loads(stream.getvalue())


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve(); self.origin = self.base/'origin'; project(self.origin)
        self.dest = self.base/'destination'; project(self.dest)
        self.config = self.base/'config.json'; self.root = self.base/'media'
        lib.configure(self.config, self.root, 'test-library')
        self.source = self.origin/'original.wav'; tone(self.source)
        self.prepared = audio_sources.prepare_source(self.origin, 'original.wav', 'pcm', audio.digest(self.source), 'tone-48k',
            provenance={'origin_kind':'synthesized','prior_processing':'deterministic test fixture; no audition performed'})
        self.receipt = Path(self.prepared['receipt']); self.receipt_rel = self.receipt.relative_to(self.origin)

    def import_prepared(self, asset='tone', version='p1', **kwargs):
        return lib.import_version(self.config, self.origin, asset, version, 'event', audio.digest(self.receipt), preparation=self.receipt_rel, **kwargs)

    def folder(self, asset='tone', version='p1'):
        return self.root/'versions'/asset/version

    def observation(self, selected, **overrides):
        # No file from these simulated unit-test assertions is a production review.
        data = {'version_sha256':selected['sha256'], 'source_sha256':self.prepared['working']['sha256'],
            'listened':True, 'observer':'SIMULATED UNIT TEST', 'observed_utc':'2026-01-01T00:00:00+00:00',
            'device':'SIMULATED', 'playback_path':'SIMULATED', 'start_frame':0, 'frames':480,
            'heard':'SIMULATED validation input, not a claim of listening', 'suitability':'suitable'}
        data.update(overrides); return data

    def accept(self, selected):
        observed = lib.append_event(self.config, 'tone', 'p1', selected['state_sha256'], 'obs1', 'observation', self.observation(selected))
        return lib.append_event(self.config, 'tone', 'p1', observed['state_sha256'], 'decision1', 'decision',
            {'decision':'accepted','by':'SIMULATED UNIT TEST','note':'SIMULATED acceptance branch','observation_sha256':observed['state_sha256']})

    def test_explicit_stable_config_no_implicit_worktree_or_project(self):
        for root in [ROOT/'media', self.origin/'media']:
            with self.assertRaisesRegex(ValueError, 'independent'): lib.configure(self.base/'bad.json', root, 'bad')
        with self.assertRaisesRegex(ValueError, 'absolute'): lib.load_config(Path('relative.json'))
        with self.assertRaisesRegex(ValueError, 'already exists'): lib.configure(self.config, self.base/'new-root', 'new')
        self.assertFalse((self.base/'new-root').exists())
        with patch.object(cli, 'project_path', side_effect=AssertionError('must not resolve project')):
            code, result = invoke('--project','missing','audio','library','search','--config',self.config)
        self.assertEqual(code, 0, result); self.assertEqual(result['data']['matches'], [])
        (self.root/'library.json').write_text('{}')
        with self.assertRaises(ValueError): lib.load_config(self.config)

    def test_candidate_prepared_version_parent_and_duplicate_detection(self):
        c = lib.import_version(self.config, self.origin, 'tone','c1','event',audio.digest(self.source),source='original.wav',backend='pcm')
        self.assertEqual(c['state'], 'candidate')
        with self.assertRaisesRegex(ValueError, 'Duplicate audio'): lib.import_version(self.config,self.origin,'alias','c1','event',audio.digest(self.source),source='original.wav',backend='pcm')
        with self.assertRaisesRegex(ValueError, 'pinned parent'): self.import_prepared()
        p = self.import_prepared(parent={'version':'c1','sha256':c['sha256']})
        self.assertEqual(p['state'], 'prepared')
        self.assertEqual(lib.inspect(self.config, 'tone','c1')['state'], 'candidate')
        with self.assertRaisesRegex(ValueError, 'already exists'): self.import_prepared()
        with self.assertRaisesRegex(ValueError, 'Duplicate audio'): self.import_prepared(asset='duplicate')
        self.assertEqual(len(lib.search(self.config, 'tone')['matches']), 2)
        self.assertEqual(len(lib.search(self.config, kind='event',status='candidate')['matches']), 1)
        self.assertFalse((self.folder('alias','c1')).exists())
        self.assertEqual(lib.inspect(self.config,'tone','p1')['record']['provenance']['entitlement'], 'unknown')

    def test_bad_hashes_kinds_and_wrong_parent_publish_no_version(self):
        for expected in [None, '', 'f'*63, 'g'*64, 'a'*64]:
            with self.assertRaises((ValueError, TypeError)): lib.import_version(self.config,self.origin,'bad','v1','event',expected,preparation=self.receipt_rel)
        with self.assertRaisesRegex(ValueError,'Unsupported audio kind'): lib.import_version(self.config,self.origin,'bad','v1','image',audio.digest(self.receipt),preparation=self.receipt_rel)
        for parent in [{'version':'absent','sha256':'a'*64}, {'version':'p1','sha256':'a'*64}]:
            with self.assertRaises((ValueError, OSError)): self.import_prepared(parent=parent)
        self.assertFalse(self.folder('bad','v1').exists()); self.assertFalse(self.folder().exists())

    def test_archived_preparation_exact_bytes_and_origin_unavailable(self):
        selected = self.import_prepared(); original_receipt = self.receipt.read_bytes()
        shutil.rmtree(self.origin)
        inspected = lib.inspect(self.config,'tone','p1')
        self.assertEqual(inspected['sha256'],selected['sha256'])
        self.assertEqual((self.folder()/'source-receipt.json').read_bytes(), original_receipt)
        self.assertEqual(inspected['working_format']['frames'],480)

    def test_audition_exact_region_preserves_channels_and_does_not_listen(self):
        selected = self.import_prepared(); excerpt = lib.audition(self.config,'tone','p1',selected['sha256'],'short',31,71)
        self.assertEqual(excerpt['state'],'prepared')
        with wave.open(str(self.origin/self.prepared['working']['path']),'rb') as source, wave.open(excerpt['audio'],'rb') as out:
            source.setpos(31); self.assertEqual(out.readframes(71),source.readframes(71)); self.assertEqual(out.getnchannels(),2)
        self.assertEqual(lib.inspect(self.config,'tone','p1')['auditions'][0]['sha256'],excerpt['audition_sha256'])
        with self.assertRaisesRegex(ValueError,'already exists'): lib.audition(self.config,'tone','p1',selected['sha256'],'short')
        for start, frames in [(0,481),(-1,20),(10,0)]:
            with self.assertRaises(ValueError): lib.audition(self.config,'tone','p1',selected['sha256'],'bad',start,frames)
        self.assertFalse((self.folder()/'auditions/bad').exists())

    def test_promotion_requires_actual_current_full_source_observation(self):
        selected = self.import_prepared(); lib.audition(self.config,'tone','p1',selected['sha256'],'full')
        body = {'decision':'accepted','by':'test','note':'test','observation_sha256':selected['state_sha256']}
        with self.assertRaisesRegex(ValueError,'actual recorded listening'): lib.append_event(self.config,'tone','p1',selected['state_sha256'],'accept','decision',body)
        for overrides in [{'listened':False},{'version_sha256':'a'*64},{'source_sha256':'a'*64},{'observer':''},
                          {'observed_utc':'2099-01-01T00:00:00Z'},{'observed_utc':'unknown'},{'frames':481}]:
            with self.assertRaises(ValueError): lib.append_event(self.config,'tone','p1',selected['state_sha256'],'bad','observation',self.observation(selected,**overrides))
        self.assertFalse((self.folder()/'events').exists())
        obs = lib.append_event(self.config,'tone','p1',selected['state_sha256'],'partial','observation',self.observation(selected,frames=20))
        body['observation_sha256']=obs['state_sha256']
        with self.assertRaisesRegex(ValueError,'full-source'): lib.append_event(self.config,'tone','p1',obs['state_sha256'],'accept','decision',body)
        with self.assertRaisesRegex(ValueError,'Stale'): lib.append_event(self.config,'tone','p1',selected['state_sha256'],'new','observation',self.observation(selected))

    def test_states_accept_reject_revise_and_no_inherited_acceptance(self):
        selected = self.import_prepared(); accepted = self.accept(selected)
        self.assertEqual(accepted['state'],'accepted')
        original_version = (self.folder()/'version.json').read_bytes()
        for decision in ['rejected','revise']:
            accepted = lib.append_event(self.config,'tone','p1',accepted['state_sha256'],decision,'decision',
                {'decision':decision,'by':'SIMULATED','note':'state branch','observation_sha256':None})
            self.assertEqual(accepted['state'],decision)
        self.assertEqual((self.folder()/'version.json').read_bytes(),original_version)
        # Explicitly prepare another derivative: byte-different backend recipe identity.
        recipe_path = self.origin/'audio/preparations/tone-48k/recipe.json'
        recipe = audio.read_json(recipe_path); recipe['processing'].append('Fixture identity-only provenance note; samples unchanged')
        audio.write_json(recipe_path,recipe)
        prior=audio.read_json(self.receipt); prior['recipe']['sha256']=audio.digest(recipe_path); prior['recipe']['bytes']=recipe_path.stat().st_size
        prior.pop('payload_sha256'); audio.write_json(self.receipt,seal(prior))
        new = self.import_prepared(version='p2',parent={'version':'p1','sha256':selected['sha256']})
        self.assertEqual(new['state'],'prepared')

    def test_stale_changed_or_missing_version_and_event_fail(self):
        selected = self.import_prepared(); accepted = self.accept(selected)
        path=self.folder()/'version.json'; raw=path.read_bytes(); value=audio.read_json(path)
        value['kind']='image'; value.pop('payload_sha256'); audio.write_json(path,seal(value))
        with self.assertRaisesRegex(ValueError,'Unsupported audio kind'): lib.inspect(self.config,'tone','p1')
        path.write_bytes(raw)
        events=sorted((self.folder()/'events').glob('*.json')); event=audio.read_json(events[0]); event['body']['heard']='changed'
        event.pop('payload_sha256'); audio.write_json(events[0],seal(event))
        with self.assertRaisesRegex(ValueError,'Stale'): lib.inspect(self.config,'tone','p1')
        with self.assertRaises(ValueError): material.materialize(self.config,self.dest,'tone','p1',selected['sha256'],accepted['state_sha256'],'bad')

    def test_duplicate_record_id_and_broken_parent_are_rejected(self):
        selected=self.import_prepared(); duplicate=self.root/'versions/other/p1'; duplicate.parent.mkdir(); shutil.copytree(self.folder(),duplicate)
        with self.assertRaisesRegex(ValueError,'identity mismatch'): lib.search(self.config)
        shutil.rmtree(duplicate.parent)
        value=audio.read_json(self.folder()/'version.json'); value['parent']={'version':'absent','sha256':'a'*64}; value.pop('payload_sha256')
        audio.write_json(self.folder()/'version.json',seal(value))
        with self.assertRaises((ValueError,OSError)): lib.inspect(self.config,'tone','p1')

    def test_external_symlink_escape_on_import_and_materialization(self):
        selected=self.import_prepared(); original=self.folder()/'original.source'; external=self.base/'outside.source'
        shutil.copyfile(original,external); original.unlink(); original.symlink_to(external)
        with self.assertRaisesRegex(ValueError,'inside'): lib.inspect(self.config,'tone','p1')
        original.unlink(); shutil.copyfile(external,original)
        (self.dest/'audio').symlink_to(self.origin, target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'inside'): material.materialize(self.config,self.dest,'tone','p1',selected['sha256'],selected['state_sha256'],'bad',True)

    def test_failed_copy_config_import_audition_event_and_materialization_preserve_state(self):
        with patch('ambiance_studio.audio_library.shutil.copyfile',side_effect=OSError('fixture disk failure')):
            with self.assertRaises(OSError): self.import_prepared()
        self.assertFalse(self.folder().exists())
        selected=self.import_prepared(); before=(self.folder()/'version.json').read_bytes()
        with patch('ambiance_studio.audio_library.audio.write_json',side_effect=OSError('fixture disk failure')):
            with self.assertRaises(OSError): lib.audition(self.config,'tone','p1',selected['sha256'],'fail')
            with self.assertRaises(OSError): lib.append_event(self.config,'tone','p1',selected['state_sha256'],'fail','observation',self.observation(selected))
        self.assertFalse((self.folder()/'auditions/fail').exists()); self.assertEqual(lib.inspect(self.config,'tone','p1')['state'],'prepared')
        with patch('ambiance_studio.audio_materialization.shutil.copyfile',side_effect=OSError('fixture disk failure')):
            with self.assertRaises(OSError): material.materialize(self.config,self.dest,'tone','p1',selected['sha256'],selected['state_sha256'],'fail',True)
        self.assertFalse((self.dest/'audio/library/fail').exists()); self.assertEqual((self.folder()/'version.json').read_bytes(),before)
        with patch.object(Path,'rename',side_effect=OSError('fixture rename failure')):
            with self.assertRaises(OSError): lib.configure(self.base/'fail.json',self.base/'failed-library','fail')
        self.assertFalse((self.base/'fail.json').exists()); self.assertFalse((self.base/'failed-library').exists())

    def test_portable_materialization_after_origin_and_library_removed(self):
        selected=self.import_prepared(); accepted=self.accept(selected)
        receipt_before=self.receipt.read_bytes(); original=self.source.read_bytes(); working=(self.origin/self.prepared['working']['path']).read_bytes()
        m=material.materialize(self.config,self.dest,'tone','p1',selected['sha256'],accepted['state_sha256'],'used')
        self.assertEqual(m['review']['state'],'accepted')
        shutil.rmtree(self.root); shutil.rmtree(self.origin); self.config.unlink()
        checked=material.validate_materialization(self.dest,m['receipt_path'])
        self.assertEqual((self.dest/checked['original']['path']).read_bytes(),original)
        self.assertEqual((self.dest/checked['working']['path']).read_bytes(),working)
        receipt=audio.read_json(Path(m['receipt_path']))
        self.assertEqual((self.dest/receipt['files']['source_receipt']['path']).read_bytes(),receipt_before)
        self.assertEqual(checked['working_format']['frames'],480); self.assertEqual(checked['working_format']['sample_rate'],48000)
        collector=Collector(self.dest); collector.preparation(Path(m['receipt_path']),0)
        self.assertFalse(collector.masters)
        self.assertTrue(all((self.dest/item['path']).is_file() for item in collector.refs))
        self.assertTrue(all('audio/library/used/' in item['path'] for item in collector.refs))
        session={'format':audio.FORMAT,'schema_version':1,'id':'portable','sample_rate':48000,'frames':480,
            'sources':[m['source']], 'stems':[{'id':'tone'}],
            'clips':[{'id':'tone','source':'tone','stem':'tone','frames':480,'at_frame':0}]}
        audio.write_json(self.dest/'session.json',session)
        _, loaded=audio.load_session(self.dest,self.dest/'session.json')
        self.assertTrue(loaded)
        selection={'format':'ambiance-revision-selection','schema_version':1,'scene':'scene.json','catalog':'catalog.json',
                   'audio':{'session':'session.json','preparations':[str(Path(m['receipt_path']).relative_to(self.dest))]}}
        audio.write_json(self.dest/'selection.json',selection)
        for argv in [('revision','capture','portable','--selection',self.dest/'selection.json'),('revision','check','portable')]:
            code,result=invoke('--project',self.dest,*argv); self.assertEqual(code,0,result)
        # A folder handoff can move again, with no external links or former absolute dependency.
        handed=self.base/'handoff'; shutil.copytree(self.dest,handed); shutil.rmtree(self.dest)
        code,result=invoke('--project',handed,'audio','library','check','audio/library/used/receipt.json'); self.assertEqual(code,0,result)
        code,result=invoke('--project',handed,'revision','check','portable'); self.assertEqual(code,0,result)

    def test_unaccepted_requires_opt_in_and_stale_state_fails(self):
        selected=self.import_prepared()
        with self.assertRaisesRegex(ValueError,'not accepted'): material.materialize(self.config,self.dest,'tone','p1',selected['sha256'],selected['state_sha256'],'bad')
        accepted=self.accept(selected)
        with self.assertRaisesRegex(ValueError,'Stale selected library review'): material.materialize(self.config,self.dest,'tone','p1',selected['sha256'],selected['state_sha256'],'bad')
        self.assertFalse((self.dest/'audio/library/bad').exists())

    def test_materialization_tampering_and_no_generic_archival_dependencies(self):
        selected=self.import_prepared(); m=material.materialize(self.config,self.dest,'tone','p1',selected['sha256'],selected['state_sha256'],'used',True)
        receipt_path=Path(m['receipt_path']); receipt=audio.read_json(receipt_path)
        self.assertTrue(all(item['path'].startswith('audio/library/used/') for item in m['dependencies']))
        for key in ['original','working','recipe','source_receipt']:
            path=self.dest/receipt['files'][key]['path']; raw=path.read_bytes(); path.write_bytes(raw+b'x')
            with self.assertRaises(ValueError): material.validate_materialization(self.dest,receipt_path)
            path.write_bytes(raw)
        receipt['dependencies'].append({'path':'../external.wav','sha256':'a'*64,'bytes':1,'role':'audio_source_origin','section':'sound-design'})
        receipt.pop('payload_sha256'); audio.write_json(receipt_path,seal(receipt))
        with self.assertRaisesRegex(ValueError,'dependencies differ'): material.validate_materialization(self.dest,receipt_path)

    def test_malformed_version_hashes_and_stale_existing_parent(self):
        c=lib.import_version(self.config,self.origin,'tone','c1','event',audio.digest(self.source),source='original.wav',backend='pcm')
        with self.assertRaisesRegex(ValueError,'Stale parent'): self.import_prepared(parent={'version':'c1','sha256':'a'*64})
        self.import_prepared(parent={'version':'c1','sha256':c['sha256']})
        path=self.folder()/'version.json'; raw=path.read_bytes()
        for mutation in [lambda v:v['files']['working'].pop('sha256'),lambda v:v['files']['working'].update(sha256='bad'),
                         lambda v:v['files']['working'].update(bytes=True),lambda v:v.update(schema_version=2)]:
            value=json.loads(raw); mutation(value); value.pop('payload_sha256'); audio.write_json(path,seal(value))
            with self.assertRaises(ValueError): lib.inspect(self.config,'tone','p1')
        path.write_bytes(raw)
        parent_path=self.folder(version='c1')/'version.json'; value=audio.read_json(parent_path)
        value['metadata']={'role':'changed parent metadata'}; value.pop('payload_sha256'); audio.write_json(parent_path,seal(value))
        with self.assertRaisesRegex(ValueError,'Stale parent'): lib.inspect(self.config,'tone','p1')

    def test_final_publication_failures_leave_no_version_or_use_and_allow_retry(self):
        with patch.object(Path,'rename',side_effect=OSError('fixture final rename failure')):
            with self.assertRaises(OSError): self.import_prepared()
        self.assertFalse(self.folder().exists())
        selected=self.import_prepared()
        with patch.object(Path,'rename',side_effect=OSError('fixture final rename failure')):
            with self.assertRaises(OSError): material.materialize(self.config,self.dest,'tone','p1',selected['sha256'],selected['state_sha256'],'used',True)
        self.assertFalse((self.dest/'audio/library/used').exists())
        m=material.materialize(self.config,self.dest,'tone','p1',selected['sha256'],selected['state_sha256'],'used',True)
        receipt=Path(m['receipt_path']).read_bytes()
        with self.assertRaisesRegex(ValueError,'already exists'): material.materialize(self.config,self.dest,'tone','p1',selected['sha256'],selected['state_sha256'],'used',True)
        self.assertEqual(Path(m['receipt_path']).read_bytes(),receipt)

    def test_archived_projection_validates_all_paths_before_linking(self):
        from ambiance_studio.audio_library_records import validate_archived_preparation
        self.import_prepared(); folder=self.folder()
        prior_path=folder/'source-receipt.json'; original=prior_path.read_bytes()
        value=audio.read_json(folder/'version.json')
        def check_mutation(change):
            prior=json.loads(original); change(prior); prior.pop('payload_sha256'); audio.write_json(prior_path,seal(prior))
            files=dict(value['files']); files['source_receipt']={'path':'source-receipt.json','sha256':audio.digest(prior_path),'bytes':prior_path.stat().st_size}
            with patch('ambiance_studio.audio_library_records.os.link',side_effect=AssertionError('No projection link before all paths validate')):
                with self.assertRaises(ValueError): validate_archived_preparation(folder,files)
        check_mutation(lambda p: p['working'].update(path='../outside.wav'))
        check_mutation(lambda p: p['recipe'].update(path='/tmp/outside.json'))
        check_mutation(lambda p: p['working'].update(path=p['origin']['path']))
        check_mutation(lambda p: (p['origin'].update(path='nested'),p['recipe'].update(path='nested/recipe.json')))
        prior_path.write_bytes(original)
        self.assertEqual(self.source.read_bytes(),(folder/'original.source').read_bytes())

    def test_escaped_manifest_event_and_audition_receipts_fail(self):
        selected=self.import_prepared()
        audition=lib.audition(self.config,'tone','p1',selected['sha256'],'full')
        self.accept(selected)
        paths=[self.folder()/'version.json',Path(audition['audition']),*sorted((self.folder()/'events').glob('*.json'))]
        for index,path in enumerate(paths):
            raw=path.read_bytes(); external=self.base/f'escaped-{index}.json'; external.write_bytes(raw)
            path.unlink(); path.symlink_to(external)
            with self.assertRaisesRegex(ValueError,'inside'): lib.inspect(self.config,'tone','p1')
            path.unlink(); path.write_bytes(raw)

    def test_public_routes_and_output_ownership(self):
        selected=self.import_prepared(); output=self.base/'inspect.json'
        code,result=invoke('audio','library','inspect','tone','--version','p1','--config',self.config,'--out',output)
        self.assertEqual(code,0,result); self.assertEqual(audio.read_json(output),result)
        code,result=invoke('audio','library','materialize','tone','--version','p1','--config',self.config,'--expect-version',selected['sha256'],
                           '--expect-state',selected['state_sha256'],'--materialization-id','needs-project','--allow-unaccepted')
        self.assertEqual(code,2); self.assertIn('project',result['error']['message'])
        observation=self.base/'observation.json'; audio.write_json(observation,self.observation(selected))
        code,result=invoke('audio','library','observe','tone','--version','p1','--config',self.config,'--expect-state',selected['state_sha256'],
                          '--event-id','cli-observation','--observation',observation)
        self.assertEqual(code,0,result)
        state=result['data']['state_sha256']
        code,result=invoke('audio','library','promote','tone','--version','p1','--config',self.config,'--expect-state',state,
                          '--event-id','cli-promotion','--decision','accepted','--by','SIMULATED','--note','SIMULATED fixture','--observation-sha256',state)
        self.assertEqual(code,0,result); self.assertEqual(result['data']['state'],'accepted')


if __name__ == '__main__': unittest.main()
