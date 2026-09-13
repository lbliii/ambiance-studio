"""Native packet consumption, exact subjects, freshness and atomic failure cases."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import studio
from ambiance_studio import cli, workflow, workflow_packets as packets, production_plan, iteration_recipes, revision_capture
from test_production_coverage import fixture
from test_workflow_cli import synthetic_delivery


def invoke(project,*argv):
    output=io.StringIO()
    with contextlib.redirect_stdout(output): code=cli.main(['--project',str(project),*map(str,argv)])
    return code,json.loads(output.getvalue())


def tree(project):
    return {str(p.relative_to(project)):studio.digest(p) for p in project.rglob('*') if p.is_file()}


class PacketTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.p=fixture(Path(self.tmp.name))
    def action(self,operation,**selectors):
        assessment=workflow.Assessment(self.p,**selectors)
        return assessment,next(r for r in assessment.ordered if r['operation']==operation)
    def prepare(self,op,name='packet',inputs=None,**selectors):
        a,row=self.action(op,**selectors)
        return packets.prepare(self.p,row['id'],self.p/name,inputs=inputs,expected=a.assessment_hash,**selectors)
    def request(self):
        return {'format':'ambiance-iteration-request','schema_version':1,'id':'packet-iteration','revision':'packet-revision',
                'views':['portrait','landscape'],'editions':[{'role':'silent'}],
                'default':{'view':'portrait','role':'silent'},'scope':'proof','long_edge':160}

    def test_intent_incomplete_preserves_scope_origins_and_source_bytes(self):
        (self.p/production_plan.PATH).unlink()
        before=tree(self.p)
        result=self.prepare('intent.author')
        packet=studio.read(Path(result['packet']))
        self.assertFalse(result['ready_to_run']);self.assertIsNone(result['argv'])
        self.assertIn('story.premise',packet['missing_inputs']);self.assertIn('elements',packet['missing_inputs'])
        draft=studio.read(self.p/'packet/intent.draft.json')
        self.assertEqual(draft['format'],packets.DRAFT);self.assertIsNone(draft['values']['elements'])
        self.assertTrue(packet['origins']);self.assertFalse(packet['observations_performed'])
        self.assertEqual(before,{k:v for k,v in tree(self.p).items() if not k.startswith('packet/')})

    def test_complete_intent_packet_public_consumption_and_reprepare_preserves_first(self):
        (self.p/production_plan.PATH).unlink()
        a,row=self.action('intent.author')
        code,result=invoke(self.p,'workflow','prepare',row['id'],'--inputs',self.p/'proposal.json','--out',self.p/'one','--expect-assessment',a.assessment_hash)
        self.assertEqual(code,0,result);self.assertTrue(result['data']['ready_to_run'])
        original=tree(self.p/'one')
        result2=self.prepare('intent.author','two',self.p/'proposal.json')
        self.assertEqual(original,tree(self.p/'one'))
        code,applied=invoke(self.p,*result2['argv'][3:])
        self.assertEqual(code,0,applied)
        self.assertEqual(production_plan.load(self.p),studio.read(self.p/'proposal.json'))

    def test_native_validator_rejects_complete_invalid_intent_without_output(self):
        (self.p/production_plan.PATH).unlink()
        invalid=studio.read(self.p/'proposal.json');invalid['outputs'][0]['roles']=['guessed']
        studio.write(self.p/'invalid.json',invalid)
        with self.assertRaisesRegex(ValueError,'roles'):self.prepare('intent.author',inputs=self.p/'invalid.json')
        self.assertFalse((self.p/'packet').exists())

    def test_review_is_native_unperformed_draft_no_guessed_recorder(self):
        result=self.prepare('review.draft',stage='intent')
        self.assertFalse(result['ready_to_run']);draft=studio.read(self.p/'packet/review.draft.json')
        self.assertEqual(draft,studio.review_template(self.p,'intent'))
        self.assertEqual(draft['recorder'],'');self.assertTrue(all(c['result']=='not-run' for c in draft['checks']))
        code,error=invoke(self.p,'review','record',self.p/'packet/review.draft.json')
        self.assertEqual(code,2,error);self.assertFalse((self.p/'reviews/intent.json').exists())
        # Explicitly unperformed technical fixture record, not an invented audition.
        draft['recorder']='Engineering unperformed-draft fixture';studio.write(self.p/'review-input.json',draft)
        self.assertEqual(invoke(self.p,'review','record',self.p/'review-input.json')[0],0)
        self.assertTrue(all(c['result']=='not-run' for c in studio.read(self.p/'reviews/intent.json')['checks']))

    def test_iteration_complete_uses_native_build_and_preflight_without_capture(self):
        studio.write(self.p/'request.json',self.request());before=tree(self.p)
        result=self.prepare('iteration.init',inputs=self.p/'request.json',stage='export')
        self.assertTrue(result['ready_to_run'],result)
        native=iteration_recipes.build(self.p,self.request(),self.p/'packet')
        self.assertEqual(studio.read(self.p/'packet/iteration.json'),native['recipe'])
        self.assertEqual(before,{k:v for k,v in tree(self.p).items() if not k.startswith('packet/')})
        self.assertFalse(revision_capture.manifest_path(self.p,'packet-revision').exists())
        code,data=invoke(self.p,*result['argv'][3:]);self.assertIn(code,[0,1],data)
        self.assertEqual(data['data']['scope'],'proof');self.assertTrue(data['data']['may_render'])

    def test_iteration_incomplete_has_explicit_identity_sound_and_scope_choices(self):
        result=self.prepare('iteration.init',stage='export')
        self.assertFalse(result['ready_to_run'])
        self.assertTrue({'id','revision','editions','scope','default.view','default.role'} <= set(result['missing_inputs']))
        values=studio.read(self.p/'packet/iteration.draft.json')['values']
        self.assertEqual(values['views'],['portrait','landscape']);self.assertIsNone(values['editions'])

    def test_partial_authored_inputs_retain_origins_and_unresolved_choices(self):
        studio.write(self.p/'partial.json',{'id':'explicit-user-id'})
        result=self.prepare('iteration.init',inputs=self.p/'partial.json',stage='export')
        self.assertFalse(result['ready_to_run']);self.assertIn('editions',result['missing_inputs'])
        packet=studio.read(Path(result['packet']))
        origin=next(r['origin'] for r in packet['origins'] if r['field']=='id')
        self.assertEqual(origin['sha256'],studio.digest(self.p/'partial.json'))

    def test_symlink_input_and_reference_are_rejected_before_publication(self):
        (self.p/production_plan.PATH).unlink()
        (self.p/'input-link.json').symlink_to(self.p/'proposal.json')
        with self.assertRaisesRegex(ValueError,'symlink'):self.prepare('intent.author',inputs=self.p/'input-link.json')
        values=studio.read(self.p/'proposal.json')
        (self.p/'assets/source-link.png').symlink_to(self.p/'assets/source.png')
        values['sources'][0]['path']='assets/source-link.png';studio.write(self.p/'linked.json',values)
        with self.assertRaisesRegex(ValueError,'symlink'):self.prepare('intent.author',inputs=self.p/'linked.json')
        self.assertFalse((self.p/'packet').exists())

    def test_complete_iteration_invalid_view_or_audio_fails_native_validation(self):
        request=self.request();request['views']=['wrong'];request['default']['view']='wrong'
        studio.write(self.p/'request.json',request)
        with self.assertRaises(Exception):self.prepare('iteration.init',inputs=self.p/'request.json',stage='export')
        self.assertFalse((self.p/'packet').exists())

    def test_direct_manifest_keeps_resolved_native_command_and_file_hashes(self):
        result=self.prepare('view.inspect',stage='layout')
        self.assertTrue(result['ready_to_run']);self.assertEqual(invoke(self.p,*result['argv'][3:])[0],0)
        packet=studio.read(Path(result['packet']))
        self.assertEqual(packet['operation'],'view.inspect')
        for ref in packet['files']:self.assertEqual(studio.digest(Path(result['packet']).parent/ref['path']),ref['sha256'])

    def test_stale_assessment_and_stale_action_never_publish(self):
        a,row=self.action('review.draft',stage='intent')
        (self.p/'plans/brief.md').write_text('Explicit changed brief')
        code,error=invoke(self.p,'workflow','prepare',row['id'],'--stage','intent','--expect-assessment',a.assessment_hash,'--out',self.p/'packet')
        self.assertEqual(code,2);self.assertEqual(error['error']['code'],'stale_assessment')
        code,error=invoke(self.p,'workflow','prepare','wf1.absent','--out',self.p/'packet')
        self.assertEqual(code,2);self.assertEqual(error['error']['code'],'stale_action')
        self.assertFalse((self.p/'packet').exists())

    def test_path_escape_symlink_and_occupied_output_preserve_prior_files(self):
        a,row=self.action('review.draft',stage='intent');before=tree(self.p)
        outside=self.p.parent/'outside';outside.mkdir();(outside/'sentinel').write_text('prior')
        (self.p/'link').symlink_to(outside,target_is_directory=True)
        (self.p/'inside-link').symlink_to(self.p/'reports',target_is_directory=True)
        occupied=self.p/'occupied';occupied.mkdir();(occupied/'sentinel').write_text('prior')
        for out in [outside/'packet',self.p/'link/packet',self.p/'inside-link/packet',occupied,self.p/'reports/../escape']:
            with self.subTest(out=out),self.assertRaises(Exception):
                packets.prepare(self.p,row['id'],out,stage='intent')
        self.assertEqual((occupied/'sentinel').read_text(),'prior');self.assertEqual((outside/'sentinel').read_text(),'prior')
        self.assertTrue(all(tree(self.p)[key]==value for key,value in before.items()))

    def test_failed_write_cleans_staging_and_concurrent_arrival_is_not_replaced(self):
        a,row=self.action('review.draft',stage='intent');before=tree(self.p)
        real=studio.write
        def fail(path,value):
            if Path(path).name=='packet.json':raise OSError('Injected final write failure')
            return real(path,value)
        with patch.object(studio,'write',side_effect=fail),self.assertRaisesRegex(OSError,'Injected'):
            packets.prepare(self.p,row['id'],self.p/'packet',stage='intent')
        self.assertEqual(before,tree(self.p));self.assertFalse(list(self.p.glob('.workflow-packet-*')))
        promote=packets.promote_exclusive
        def collision(stage,out):
            out.mkdir();(out/'sentinel').write_text('concurrent owner');promote(stage,out)
        with patch.object(packets,'promote_exclusive',side_effect=collision),self.assertRaises(ValueError):
            packets.prepare(self.p,row['id'],self.p/'packet',stage='intent')
        self.assertEqual((self.p/'packet/sentinel').read_text(),'concurrent owner')
        self.assertEqual(list((self.p/'packet').iterdir()),[self.p/'packet/sentinel'])

    def test_input_changed_during_write_is_rejected(self):
        a,row=self.action('review.draft',stage='intent');real=studio.write
        def change(path,value):
            real(path,value)
            if Path(path).name=='review.draft.json':(self.p/'plans/brief.md').write_text('Concurrent change')
        with patch.object(studio,'write',side_effect=change),self.assertRaisesRegex(Exception,'changed'):
            packets.prepare(self.p,row['id'],self.p/'packet',stage='intent')
        self.assertFalse((self.p/'packet').exists());self.assertFalse(list(self.p.glob('.workflow-packet-*')))

    def test_private_staging_is_excluded_from_watched_directory_differences(self):
        parent=self.p/'reports/assets';parent.mkdir(exist_ok=True)
        result=self.prepare('review.draft','reports/assets/packet',stage='intent')
        saved=studio.read(Path(result['packet']).parent/'assessment-inputs.json')
        self.assertEqual(saved['changed_inputs'],[])
        self.assertFalse(list(parent.glob('.workflow-packet-*')))

    def test_multi_revision_delivery_packet_never_substitutes_default_entry(self):
        from ambiance_studio import deliveries, record_contracts
        for id in ['v1','v2']:revision_capture.capture(self.p,id,self.p/'plans/selection.json')
        entries=[synthetic_delivery(self.p,'portrait','v1','portrait','p'),synthetic_delivery(self.p,'landscape','v2','landscape','l')]
        value=record_contracts.seal({'format':deliveries.FORMAT,'schema_version':2,'id':'pair','title':'Identity-only fixture',
            'default':{'view':'portrait','role':'silent'},'entries':{r['id']:r for r in entries},'dependencies':[]})
        studio.write(deliveries.record_path(self.p,'pair'),value);deliveries.present(self.p,'pair','Engineering fixture')
        a=workflow.Assessment(self.p,subject='review',stage='intent')
        rows=[r for r in a.ordered if r['operation']=='review.draft' and r['stage']=='intent'];self.assertEqual(len(rows),2)
        for index,row in enumerate(rows):
            out=self.p/f'entry-{index}'
            packets.prepare(self.p,row['id'],out,subject='review',stage='intent')
            packet=studio.read(out/'packet.json');draft=studio.read(out/'review.draft.json')
            self.assertEqual(packet['subject']['revision'],row['subject']['revision'])
            self.assertEqual(draft['subject']['revision'],row['subject']['revision'])
            self.assertEqual(draft['subject']['edition'],row['subject']['edition'])
            self.assertEqual(draft['subject']['view'],row['subject']['view'])
        from ambiance_studio import feedback
        feedback.add(self.p,'pair','Delivery-wide engineering issue','Engineering fixture',scope='delivery')
        a,row=self.action('feedback.inspect',subject='review')
        result=packets.prepare(self.p,row['id'],self.p/'feedback-packet',subject='review')
        packet=studio.read(Path(result['packet']))
        self.assertEqual(packet['subject']['kind'],'delivery');self.assertNotIn('edition',packet['subject'])
        self.assertEqual({s['revision'] for s in packet['applies_to_subjects']},{'v1','v2'})
        self.assertTrue(result['ready_to_run'])


if __name__=='__main__':unittest.main()
