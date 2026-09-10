"""Public authoring commands must retain dependency checks and transaction safety."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from ambiance_studio import cli
import studio
from ambiance_studio import scene_runtime

spec=importlib.util.spec_from_file_location('authoring_cli_fixture',ROOT/'examples/source-placement/create_fixture.py')
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)


class AuthoringCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_template=tempfile.TemporaryDirectory()
        cls.template=Path(cls.temp_template.name)/'template';fixture.create(cls.template)

    @classmethod
    def tearDownClass(cls):cls.temp_template.cleanup()

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.project=Path(self.temp.name)/'project';shutil.copytree(self.template,self.project)
        self.scene_path=self.project/'scene/scene.json'
        self.catalog_path=self.project/'assets/catalog.json'
        self.history=self.project/'.ambiance/scene-history'
        scene=studio.read(self.project/'scene/before-reparent.json')
        scene['layers']=scene['layers'][:1];scene['layers'][0].pop('sockets',None)
        studio.write(self.scene_path,scene)
        self.manifest=self.project/'placement.json'

    def public(self,*args):
        process=subprocess.run([sys.executable,str(ROOT/'ambiance'),'--project',str(self.project),*map(str,args)],capture_output=True,text=True)
        return process.returncode,json.loads(process.stdout)

    def parsed(self,*args):return cli.parser().parse_args(['--project',str(self.project),*map(str,args)])

    def assert_no_transaction(self,previous):
        self.assertEqual(self.scene_path.read_bytes(),previous)
        self.assertFalse(self.history.exists())
        self.assertFalse((self.project/'.ambiance/write.lock').exists())

    def test_public_place_dry_run_commit_stale_hash_and_restore(self):
        previous=self.scene_path.read_bytes();digest=studio.digest(self.scene_path)
        code,response=self.public('scene','place',self.manifest,'--dry-run')
        self.assertEqual(code,0,response);data=response['data']
        self.assertTrue(data['dry_run']);self.assertEqual(data['operations'],4)
        self.assertEqual(data['previous_sha256'],digest);self.assertEqual(len(data['diagnostics']),4)
        self.assertIn('assets/source/reference.png',{r['file'] for r in data['dependencies']})
        self.assert_no_transaction(previous)
        code,response=self.public('scene','place',self.manifest,'--expect-sha256','0'*64)
        self.assertEqual(code,2);self.assertEqual(response['error']['code'],'stale_input')
        self.assert_no_transaction(previous)
        code,response=self.public('scene','place',self.manifest,'--expect-sha256',digest)
        self.assertEqual(code,0,response);saved=response['data']
        self.assertEqual(saved['operation'],'place');self.assertEqual(saved['previous_sha256'],digest)
        self.assertEqual((self.history/f'{digest}.json').read_bytes(),previous)
        self.assertEqual(len(studio.read(self.scene_path)['layers']),5)
        code,response=self.public('scene','restore',digest)
        self.assertEqual(code,0,response);self.assertEqual(studio.read(self.scene_path),json.loads(previous))

    def test_public_apply_routes_source_placement_and_keeps_legacy_dry_run_fields(self):
        manifest=studio.read(self.manifest)
        batch={'version':1,'operations':[{'op':'place_from_source',**manifest['placements'][0]},
                                       {'op':'set','layer':'base','values':{'opacity':.9}}]}
        path=self.project/'authoring-batch.json';studio.write(path,batch)
        previous=self.scene_path.read_bytes()
        code,response=self.public('scene','apply',path,'--dry-run')
        self.assertEqual(code,0,response);result=response['data']
        self.assertEqual(result['operations'],2);self.assertEqual(result['diagnostics'][0]['layer'],'body')
        self.assertTrue(result['dependencies']);self.assertIn('scene',result)
        self.assert_no_transaction(previous)

    def test_source_changed_after_evaluator_never_saves_or_creates_history(self):
        previous=self.scene_path.read_bytes();bridge=scene_runtime.scene_bridge
        def changed(*args,**kwargs):
            result=bridge(*args,**kwargs)
            source=self.project/'assets/source/reference.png'
            source.write_bytes(source.read_bytes()+b'changed during evaluator')
            return result
        with patch('ambiance_studio.scene_runtime.scene_bridge',side_effect=changed):
            with self.assertRaisesRegex(ValueError,'changed before save'):
                cli.run(self.parsed('scene','place',self.manifest))
        self.assert_no_transaction(previous)

    def test_catalog_and_configuration_changed_during_validation_never_save(self):
        previous=self.scene_path.read_bytes();bridge=scene_runtime.scene_bridge
        for selected in [self.catalog_path,self.project/'ambiance-project.json']:
            before=selected.read_bytes()
            def changed(*args,**kwargs):
                result=bridge(*args,**kwargs);selected.write_bytes(before+b'\n');return result
            try:
                with patch('ambiance_studio.scene_runtime.scene_bridge',side_effect=changed):
                    with self.assertRaises(cli.CommandError) as error:
                        cli.run(self.parsed('scene','place',self.manifest))
                self.assertEqual(error.exception.code,'stale_input');self.assert_no_transaction(previous)
            finally:selected.write_bytes(before)

    def test_bad_reference_identity_fails_publicly_before_any_scene_write(self):
        previous=self.scene_path.read_bytes();manifest=studio.read(self.manifest)
        manifest['placements'][0]['reference']['sha256']='0'*64;studio.write(self.manifest,manifest)
        code,response=self.public('scene','place',self.manifest)
        self.assertEqual(code,2);self.assertIn('dependency changed',response['error']['message'])
        self.assert_no_transaction(previous)

    def test_simple_edits_and_restore_reject_concurrent_project_changes(self):
        previous=self.scene_path.read_bytes();bridge=scene_runtime.scene_bridge
        digest=studio.digest(self.scene_path)
        self.history.mkdir(parents=True)
        (self.history/f'{digest}.json').write_bytes(previous)
        commands=[['scene','set','base','--x','.4'],
                  ['scene','add','body-cutout','--id','copy'],
                  ['scene','socket','base','mount','--u','.5','--v','.5'],
                  ['scene','restore',digest]]
        for command in commands:
            for selected in [self.scene_path,self.catalog_path,self.project/'ambiance-project.json']:
                with self.subTest(command=command,changed=selected.name):
                    before=selected.read_bytes()
                    def changed(*args,**kwargs):
                        result=bridge(*args,**kwargs);selected.write_bytes(before+b'\n');return result
                    try:
                        with patch.object(scene_runtime,'scene_bridge',side_effect=changed):
                            with self.assertRaises(cli.CommandError) as error:cli.run(self.parsed(*command))
                        self.assertEqual(error.exception.code,'stale_input')
                        self.assertEqual(selected.read_bytes(),before+b'\n')
                        if selected!=self.scene_path:self.assertEqual(self.scene_path.read_bytes(),previous)
                        self.assertEqual([p.name for p in self.history.iterdir()],[f'{digest}.json'])
                        self.assertFalse((self.project/'.ambiance/write.lock').exists())
                    finally:selected.write_bytes(before)

    def test_batch_and_track_input_changes_abort_without_history(self):
        previous=self.scene_path.read_bytes();bridge=scene_runtime.scene_bridge
        inputs=[(['scene','apply'],{'version':1,'operations':[{'op':'set','layer':'base','values':{'x':.4}}]}),
                (['scene','track','base'],{'version':1,'tracks':{'x':{'interpolation':'linear','keys':[[0,.5],[4,.5]]}}})]
        for command,document in inputs:
            with self.subTest(command=command):
                path=self.project/'input.json';studio.write(path,document)
                def changed(*args,**kwargs):
                    result=bridge(*args,**kwargs);path.write_bytes(path.read_bytes()+b'\n');return result
                with patch.object(scene_runtime,'scene_bridge',side_effect=changed):
                    with self.assertRaisesRegex(ValueError,'changed before save'):
                        cli.run(self.parsed(*command,path))
                self.assert_no_transaction(previous)

    def test_retargeting_scene_symlink_with_identical_bytes_is_stale(self):
        previous=self.scene_path.read_bytes();bridge=scene_runtime.scene_bridge
        original=self.project/'scene/first.json';other=self.project/'scene/second.json'
        self.scene_path.rename(original);other.write_bytes(previous);self.scene_path.symlink_to(original.name)
        def changed(*args,**kwargs):
            result=bridge(*args,**kwargs);self.scene_path.unlink();self.scene_path.symlink_to(other.name);return result
        with patch.object(scene_runtime,'scene_bridge',side_effect=changed):
            with self.assertRaises(cli.CommandError) as error:
                cli.run(self.parsed('scene','set','base','--x','.4'))
        self.assertEqual(error.exception.code,'stale_input')
        self.assertEqual(original.read_bytes(),previous);self.assertEqual(other.read_bytes(),previous)
        self.assert_no_transaction(previous)

    def test_changed_history_snapshot_is_not_restored_or_replaced(self):
        previous=self.scene_path.read_bytes();digest=studio.digest(self.scene_path)
        self.history.mkdir(parents=True)
        snapshot=self.history/f'{digest}.json';snapshot.write_bytes(previous+b'\n')
        for command in [('scene','restore',digest),('scene','set','base','--x','.4')]:
            with self.subTest(command=command):
                code,response=self.public(*command)
                self.assertEqual(code,2,response);self.assertIn('snapshot has changed',response['error']['message'])
                self.assertEqual(self.scene_path.read_bytes(),previous)
                self.assertEqual(snapshot.read_bytes(),previous+b'\n')
                self.assertFalse((self.project/'.ambiance/write.lock').exists())

    def test_invalid_track_shape_is_a_structured_error(self):
        previous=self.scene_path.read_bytes();path=self.project/'track.json';studio.write(path,[])
        code,response=self.public('scene','track','base',path)
        self.assertEqual(code,2,response);self.assertEqual(response['error']['code'],'invalid_input')
        self.assert_no_transaction(previous)

    def test_public_reparent_reports_exact_pose_and_preserves_gesture_timing(self):
        scene=studio.read(self.project/'scene/before-reparent.json')
        body=next(l for l in scene['layers'] if l['id']=='body');body['sockets']={'hand':[.6,.3]}
        studio.write(self.scene_path,scene);before=self.scene_path.read_bytes()
        arguments=['scene','reparent','gesture','--to','body','--socket','hand','--keep-world','--at','1.37']
        code,response=self.public(*arguments,'--dry-run')
        self.assertEqual(code,0,response);report=response['data']['diagnostics'][0]
        self.assertLess(report['max_world_corner_error_pixels'],1e-7)
        self.assertEqual(report['preserve'],'world_at_time');self.assertEqual(report['at_seconds'],1.37)
        self.assert_no_transaction(before)
        code,response=self.public(*arguments)
        self.assertEqual(code,0,response)
        after=studio.read(self.scene_path)
        self.assertEqual([l['id'] for l in after['layers']],[l['id'] for l in scene['layers']])
        old=next(l for l in scene['layers'] if l['id']=='gesture');new=next(l for l in after['layers'] if l['id']=='gesture')
        for key in ['cycle_seconds','phase_frames','asset']:self.assertEqual(new[key],old[key])
        self.assertEqual(new['attach'],{'layer':'body','socket':'hand'})

    def test_public_timing_is_read_only_and_reports_actual_cell_tracks(self):
        scene=studio.read(self.project/'scene/before-reparent.json')
        gesture=next(l for l in scene['layers'] if l['id']=='gesture')
        gesture['tracks']={'cell':{'interpolation':'hold','keys':[[0,0],[.1,1],[.2,2],[.3,3],[4,0]]}}
        studio.write(self.scene_path,scene);before=self.scene_path.read_bytes();out=self.project/'timing.json'
        code,response=self.public('scene','timing','--layer','gesture','--out',out)
        self.assertEqual(code,0,response);row=response['data']['layers'][0]
        self.assertEqual(row['timing_driver'],'cell_track');self.assertFalse(row['fallback_cycle']['active'])
        self.assertEqual(studio.read(out),response);self.assert_no_transaction(before)


if __name__=='__main__':unittest.main(verbosity=2)
