"""Cleared raster and PCM ground truth, with exact receipt and CLI checks."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ambiance_studio import activity, audio_cues, rendering
from ambiance_studio.cli import parser

spec = importlib.util.spec_from_file_location('activity_fixture', ROOT/'examples/activity/create_fixture.py')
fixture = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixture)


def args(*values): return parser().parse_args(list(map(str, values)))


@unittest.skipUnless(rendering.capabilities()['frame_render'], 'Requires Node Canvas')
class ActivityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.project = fixture.create(self.root/'film', fps=6)
        self.counter = 0

    def measure(self, *options, project=None):
        self.counter += 1; out = self.root/f'proof-{self.counter}'
        result = activity.run(args('scene', 'activity', '--layer', 'actor', '--long-edge', '128', '--out', out, *options), project or self.project)
        return result, activity.verify_receipt(out), out

    def test_real_raster_parity_clock_identity_and_resume(self):
        result, report, out = self.measure('--raster', '--view', 'portrait', '--view', 'landscape')
        self.assertLess(len(json.dumps(result)), 4000)
        self.assertFalse(report['visual_review_performed'])
        self.assertTrue(result['review_required']);self.assertFalse(result['diagnostic_coverage']['no_warning_is_readability'])
        self.assertEqual(report['summary'][0]['actions'][0]['status'],'unreviewed')
        self.assertIn('unflagged',result['next_action'])
        self.assertEqual(report['clock']['sampling_hz'], 6)
        self.assertEqual(len(report['views']), 2)
        reference = rendering.run(args('render', 'frame', '--view', 'portrait', '--time', '1', '--width', '72', '--out', self.root/'reference'), self.project)
        self.assertEqual(Path(reference['output']).read_bytes(), (out/'frames/target/portrait/00006.png').read_bytes())
        request = args('scene', 'activity', '--layer', 'actor', '--long-edge', '128', '--out', out, '--raster', '--view', 'portrait', '--view', 'landscape', '--resume')
        self.assertTrue(activity.run(request, self.project)['resumed'])
        (out/'maps/layer-actor/portrait.png').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'changed'): activity.run(request, self.project)

    def test_occluded_offscreen_duplicate_tiny_and_low_contrast(self):
        for case, warning in [('occluded','no_measured_contribution'),('offscreen','no_projected_painted_presence'),
                              ('duplicate','cel_indices_repeat_identical_paint'),('hidden','no_measured_contribution'),
                              ('tiny','small_measured_support'),('low-contrast','low_frame_average_contribution')]:
            with self.subTest(case=case):
                project = fixture.create(self.root/case, case, fps=6)
                _, report, out = self.measure('--raster', project=project)
                self.assertIn(warning, report['summary'][0]['actions'][0]['warnings'])
                state = json.loads((out/'state.json').read_text())
                if case == 'duplicate':
                    row=state['views'][0]['layers'][0]['summary']
                    self.assertGreater(row['cel_index_changes'],0);self.assertEqual(row['distinct_painted_cels'],1)

    def test_global_pulse_never_becomes_character_approval(self):
        project=fixture.create(self.root/'pulse','pulse',fps=6)
        _, report, out=self.measure('--raster',project=project)
        rows=json.loads((out/'raster.json').read_text())['rows']
        self.assertGreater(max(r['frame_changed_pixels'] for r in rows),0)
        self.assertEqual(report['summary'][0]['actions'][0]['status'],'unreviewed')
        # Residual may change through an overlaid pulse: attribution stays explicit.
        self.assertIn('Unresolved',report['attribution'])

    def test_strength_and_cadence_are_separate_bounded_experiments(self):
        _, report, _=self.measure('--raster','--compare',self.project/'comparison.json')
        self.assertEqual([v['experiment'] for v in report['variants']],['target','strength','strength','cadence','cadence'])
        recipe=json.loads((self.project/'comparison.json').read_text())
        recipe['strength'][0]['batch']['operations'][0]['values']['motion']['cycles']=2
        path=self.root/'invalid.json';path.write_text(json.dumps(recipe))
        with self.assertRaisesRegex(ValueError,'cycles'): self.measure('--raster','--compare',path)

    def test_invalid_limits_and_unknown_fields_publish_no_success_receipt(self):
        with self.assertRaises(Exception): self.measure('--stride','0')
        with self.assertRaises(Exception): self.measure('--frames','999999')
        self.assertFalse((self.root/'proof-1/activity-report.json').exists())
        self.assertFalse((self.root/'proof-2/activity-report.json').exists())

    def test_full_loop_raster_uses_last_sample_predecessor_but_partial_does_not(self):
        _,_,full=self.measure('--raster')
        full_rows=json.loads((full/'raster.json').read_text())
        first=next(r for r in full_rows['rows'] if r['action']=='layer-actor')
        self.assertTrue(full_rows['circular']);self.assertGreater(first['residual_changed_pixels'],0)
        _,_,partial=self.measure('--raster','--start-frame','1','--frames','6')
        partial_rows=json.loads((partial/'raster.json').read_text())
        first=next(r for r in partial_rows['rows'] if r['action']=='layer-actor')
        self.assertFalse(partial_rows['circular']);self.assertIsNone(first['residual_changed_pixels'])

    def test_partial_raster_run_resumes_and_never_overwrites_changed_frames(self):
        _,_,out=self.measure('--raster')
        original=(out/'frames/target/authored/00000.png').read_bytes()
        (out/'activity-report.json').unlink();(out/'frames/target/authored/00002.png').unlink()
        request=args('scene','activity','--layer','actor','--long-edge','128','--out',out,'--raster','--resume')
        activity.run(request,self.project)
        self.assertEqual(original,(out/'frames/target/authored/00000.png').read_bytes())
        activity.verify_receipt(out)
        (out/'activity-report.json').unlink();(out/'frames/target/authored/00000.png').write_bytes(b'corrupt')
        with self.assertRaises(Exception):activity.run(request,self.project)
        self.assertEqual((out/'frames/target/authored/00000.png').read_bytes(),b'corrupt')

    def test_actual_observation_requires_exact_raster_view_and_speed(self):
        _, report, out=self.measure('--raster','--view','portrait')
        doc={'kind':'ambiance-activity-observation','schema_version':1,'receipt':str(out/'activity-report.json'),
             'receipt_sha256':activity.digest(out/'activity-report.json'),'action_id':'layer-actor','view_id':'portrait',
             'status':'revise','observer':'test fixture author (schema validation only)','note':'Synthetic supplied statement, not a human audition.',
             'observed_level':1,'playback_rate':.5,'display_width':72,'display_height':128,'watched_start_seconds':0,'watched_end_seconds':4}
        source=self.root/'observation.json';source.write_text(json.dumps(doc))
        with self.assertRaisesRegex(ValueError,'normal speed'): activity.record_observation(source,self.root/'record.json')
        doc['status']='unreviewed';doc['observed_level']=None;source.write_text(json.dumps(doc))
        self.assertEqual(activity.record_observation(source,self.root/'record.json')['status'],'unreviewed')

    def make_session(self):
        source=self.project/'audio/tone.wav'; source.parent.mkdir(exist_ok=True)
        with wave.open(str(source),'wb') as wav:
            wav.setnchannels(2);wav.setsampwidth(2);wav.setframerate(48000)
            wav.writeframes(b''.join(struct.pack('<hh',1200 if i%100<50 else -1200,1200 if i%100<50 else -1200) for i in range(192000)))
        session={'format':'ambiance-audio-session','schema_version':1,'id':'cues','sample_rate':48000,'frames':192000,
                 'sources':[{'id':'tone','path':'audio/tone.wav','sha256':activity.digest(source)}],
                 'stems':[{'id':'effects'}],'clips':[{'id':'cue','source':'tone','stem':'effects','source_start_frame':0,'frames':8000,'at_frame':8000}]}
        file=self.project/'audio/session.json';file.write_text(json.dumps(session))
        links=self.root/'links.json';links.write_text(json.dumps([{'clip_id':'cue','action_id':'layer-actor','picture_frames':[1],'offset_samples':0}]))
        return file,source,links

    def test_explicit_audio_binding_detects_retime_delete_repeat_and_preserves_pcm(self):
        _,_,out=self.measure()
        session,pcm,links=self.make_session();before=pcm.read_bytes();bound=self.project/'audio/bound.json'
        audio_cues.bind(args('audio','cue-bind',session,'--activity',out,'--links',links,'--pcm',pcm,'--out',bound),self.project)
        check=lambda proof:audio_cues.check(args('audio','cue-check',bound,'--activity',proof,'--pcm',pcm),self.project)
        self.assertTrue(check(out)['ok']);self.assertEqual(before,pcm.read_bytes())
        self.assertEqual(check(out)['alignment'][0]['delta_samples'],[0])
        _,_,paired=self.measure('--view','portrait','--view','landscape')
        self.assertTrue(check(paired)['ok'])
        scene_path=self.project/'scene/scene.json';scene=json.loads(scene_path.read_text())
        scene['layers'][0]['motion']['cycles']=2;scene_path.write_text(json.dumps(scene))
        _,_,changed=self.measure();self.assertFalse(check(changed)['ok'])
        self.assertIn('picture_action_repeated_or_removed',[i['code'] for i in check(changed)['issues']])
        scene['layers'][0]['motion']['cycles']=1;scene['layers'][0]['motion']['phase']=.5;scene_path.write_text(json.dumps(scene))
        _,_,shifted=self.measure();self.assertIn('picture_action_retimed',[i['code'] for i in check(shifted)['issues']])
        scene['canvas']['loop_seconds']=8;scene_path.write_text(json.dumps(scene))
        _,_,longer=self.measure();self.assertIn('picture_loop_changed',[i['code'] for i in check(longer)['issues']])
        # Explicitly delete the measured action from a new receipt through CLI selection.
        empty=self.root/'empty';activity.run(args('scene','activity','--out',empty),self.project)
        self.assertIn('picture_action_deleted',[i['code'] for i in check(empty)['issues']])
        session_data=json.loads(bound.read_text());session_data['clips'][0]['at_frame']+=1;bound.write_text(json.dumps(session_data))
        self.assertIn('cue_session_retimed',[i['code'] for i in check(out)['issues']])

    @unittest.skipUnless(os.environ.get('AMBIANCE_TEST_NATIVE')=='1' and sys.platform=='darwin','Requires native media services')
    def test_paired_movies_preserve_selected_pcm_and_exact_sample_clock(self):
        _,pcm,_=self.make_session();identity=audio_cues.pcm_identity(pcm)
        for view in ['portrait','landscape']:
            result=rendering.run(args('render','video','--view',view,'--audio',pcm,'--out',self.root/view),self.project)
            self.assertTrue(result['ok'])
            selected=audio_cues.pcm_identity(result['audio_source']['snapshot'])
            self.assertEqual(selected['pcm_sha256'],identity['pcm_sha256'])
            self.assertEqual(selected['sha256'],identity['sha256'])
            self.assertEqual(result['verification']['audio']['presented_samples'],192000)
            self.assertTrue(result['verification']['audio']['contiguous_presented_samples'])

    def test_public_cli_out_is_artifact_directory(self):
        out=self.root/'cli'
        p=subprocess.run([str(ROOT/'ambiance'),'--project',str(self.project),'scene','activity','--layer','actor','--out',str(out)],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr);self.assertTrue(out.is_dir())
        self.assertEqual(json.loads(p.stdout)['data']['report'],str(out.resolve()/'activity-report.json'))

    def test_semantic_plan_adapter_pins_exact_action_targets_and_expectations(self):
        from ambiance_studio import cli, production_plan
        action_id='A'*98+'.X'
        plan=json.loads((ROOT/'examples/production-plan.json').read_text())
        element=plan['elements'][0];element.update(kind='character',motion_role='primary',cadence='recurring',action_ids=[action_id],required_art=[])
        element['realization']={'method':'rig','inventory_parts':[],'layer_ids':['actor']}
        plan['actions']=[{'id':action_id,'element_id':'room','description':'Turn and travel','method':'cel and rigid motion','layer_ids':['actor'],
                          'targets':[{'view_id':'portrait','readability_target':2},{'view_id':'landscape','readability_target':3}],
                          'timing':{'rest_max_seconds':1}}]
        plan['outputs']=[{'view_id':v,'roles':['silent']} for v in ['portrait','landscape']]
        plan['expectations']=[{**plan['expectations'][0],'id':'activity','view_ids':['portrait','landscape'],'action_ids':[action_id],
                               'requirement':{'type':'measured','check':'activity'}}]
        proposal=self.root/'plan.json';proposal.write_text(json.dumps(plan))
        cli.run(args('--project',self.project,'plan','spec','apply',proposal,'--expect-sha256','absent'))
        out=self.root/'semantic';activity.run(args('scene','activity','--action-id',action_id,'--view','portrait','--view','landscape','--out',out),self.project)
        report=activity.verify_receipt(out)
        self.assertEqual(report['plan']['plan_sha256'],activity.digest(self.project/production_plan.PATH))
        self.assertIn('activity',report['plan']['expectation_sha256'])
        self.assertEqual(report['actions'][0]['targets'][1]['readability_target'],3)
        self.assertEqual(report['actions'][0]['layers'],['actor'])
        state=json.loads((out/'state.json').read_text())
        self.assertEqual(state['views'][0]['profile']['kind']['character']['action_ids'],[action_id])
        scene_path=self.project/'scene/scene.json';scene=json.loads(scene_path.read_text());scene['layers'][0]['visible']=False;scene_path.write_text(json.dumps(scene))
        hidden=self.root/'semantic-hidden';activity.run(args('scene','activity','--action-id',action_id,'--view','portrait','--out',hidden),self.project)
        hidden_report=activity.verify_receipt(hidden)
        self.assertIn('sampled_rest_exceeds_authored_target',hidden_report['summary'][0]['actions'][0]['timing_target_diagnostics'])

    def test_binding_samples_and_disabled_source_include_coupled_receiver(self):
        project=self.root/'binding'
        process=subprocess.run(['node',str(ROOT/'examples/bindings/create_fixture.mjs'),str(project)],capture_output=True,text=True)
        self.assertEqual(process.returncode,0,process.stdout+process.stderr)
        out=self.root/'binding-activity'
        activity.run(args('scene','activity','--layer','flame','--view','portrait','--view','landscape','--raster',
                          '--revision','bindings-v1','--long-edge','128','--out',out),project)
        report=activity.verify_receipt(out);state=json.loads((out/'state.json').read_text())
        self.assertIn('editor/bindings.mjs',report['modules'])
        floor=next(r for r in state['views'][0]['layers'] if r['layer']=='floor-paint')
        self.assertEqual(floor['samples'][12]['channels']['cell'],1)
        self.assertEqual(floor['samples'][24]['channels']['opacity'],0)
        self.assertEqual(len(state['driver_samples']),48)
        self.assertTrue(all(j['zero_to_endpoint_rgba_exact'] for j in report['joins']))
        rows=json.loads((out/'raster.json').read_text())['rows']
        high=next(r for r in rows if r['action']=='layer-flame' and r['view']=='landscape' and r['frame']==12)
        flame=next(r for r in state['views'][1]['layers'] if r['layer']=='flame')['samples'][12]
        width,height=flame['painted_bounds_display_px'][2:]
        self.assertGreater(high['contribution_pixels'],width*height)


if __name__=='__main__': unittest.main()
