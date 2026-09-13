"""CLI envelope/selector regressions; synthetic movies test identity, never decode."""
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
from ambiance_studio import cli, deliveries, editions, record_contracts, revision_capture, workflow
from test_production_coverage import fixture


def synthetic_delivery(project, id, revision, view, edition):
    # Explicit engineering fixture: no claim that these bytes were encoded/decoded.
    movie=project/f'reports/{id}.mp4';movie.write_bytes(('Not playable: identity fixture '+id).encode())
    output={'path':str(movie.relative_to(project)),'sha256':studio.digest(movie),'bytes':movie.stat().st_size}
    selected=editions.captured_view(project,revision,view)
    dimensions=selected['definition']['output']
    receipt=record_contracts.seal({'format':editions.EDITION,'schema_version':2,'id':edition,'revision':revision,
        'revision_sha256':studio.digest(revision_capture.manifest_path(project,revision)),
        'view':selected,'output':{**output,'role':'edition_output','section':'export','path_base':'project'},
        'dependencies':[{**output,'role':'edition_output','section':'export','path_base':'project'}],
        'sound_complete':[],'audio':None,'output_expectations':{**dimensions,'fps':6,'frames':6,'loop_frames':6,'audio_tracks':0}})
    studio.write(editions.edition_path(project,revision,edition),receipt)
    return {'id':view+'.silent','view':view,'role':'silent','revision':revision,'edition':edition,'movie':output}


class WorkflowCLITests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.p=fixture(self.root)
    def invoke(self,*args):
        stream=io.StringIO()
        with contextlib.redirect_stdout(stream):code=cli.main(['--project',str(self.p),*map(str,args)])
        return code,json.loads(stream.getvalue()),len(stream.getvalue().encode())
    def capture(self,id):revision_capture.capture(self.p,id,self.p/'plans/selection.json')
    def select(self,id,entries,channel='review'):
        record=record_contracts.seal({'format':deliveries.FORMAT,'schema_version':2,'id':id,'title':'Synthetic identity fixture',
            'default':{'view':entries[0]['view'],'role':'silent'},'entries':{r['id']:r for r in entries},'dependencies':[]})
        studio.write(deliveries.record_path(self.p,id),record)
        deliveries.present(self.p,id,'Synthetic fixture',channel=channel)

    def test_multi_entry_preserves_revisions_views_roles_and_stale_selection_rejects(self):
        self.capture('v1');self.capture('v2')
        first=synthetic_delivery(self.p,'portrait','v1','portrait','portrait-v1')
        second=synthetic_delivery(self.p,'landscape','v2','landscape','landscape-v2')
        self.select('pair',[first,second])
        code,data,size=self.invoke('workflow','inspect','--subject','review')
        self.assertEqual(code,0,data)
        result=data['data'];self.assertEqual(result['subject_count'],2)
        self.assertEqual({r['revision'] for r in result['subjects']},{'v1','v2'})
        self.assertEqual({r['view'] for r in result['subjects']},{'portrait','landscape'})
        self.assertTrue(all(r['edition'] for r in result['subjects']))
        self.assertTrue(all(len(r['subjects'])==2 for r in result['stages']))
        self.assertLessEqual(size,16384)
        handoff=self.invoke('workflow','stage','library','--subject','review')[1]['data']
        self.assertTrue(any(r['operation']=='delivery.handoff' and r['state']=='ready' for r in handoff['items']))
        self.assertTrue(all(r['gate']['state']!='passed' for r in handoff['stages'][0]['subjects']))
        filtered=self.invoke('workflow','inspect','--subject','review','--view','portrait')[1]['data']
        self.assertEqual(filtered['subject_count'],1);self.assertFalse(filtered['full_scope'])
        token=result['assessment']['sha256'];action=result['items'][0]['id']
        self.select('second',[second])
        code,data,_=self.invoke('workflow','explain',action,'--subject','review','--expect-assessment',token)
        self.assertEqual(code,2);self.assertEqual(data['error']['code'],'stale_assessment')
        code,data,_=self.invoke('workflow','explain',action,'--subject','review')
        self.assertEqual(code,2);self.assertEqual(data['error']['code'],'stale_action')

    def test_missing_one_entry_keeps_other_entry_and_actual_captured_pipeline(self):
        self.capture('v1');self.capture('v2')
        first=synthetic_delivery(self.p,'portrait','v1','portrait','portrait-v1')
        second=synthetic_delivery(self.p,'landscape','v2','landscape','landscape-v2')
        self.select('pair',[first,second]);editions.edition_path(self.p,'v2','landscape-v2').unlink()
        code,data,_=self.invoke('workflow','inspect','--subject','review')
        self.assertEqual(code,0,data);result=data['data']
        self.assertEqual(result['subject_count'],2);self.assertTrue(result['diagnostic_count'])
        self.assertEqual(len(result['stages'][0]['subjects']),2)
        self.assertEqual(result['subjects'][0]['revision'],'v1')

    def test_no_optional_runtime_retains_selected_pipeline_and_entry_identity(self):
        self.capture('v1');entry=synthetic_delivery(self.p,'portrait','v1','portrait','portrait-v1');self.select('one',[entry])
        from ambiance_studio import scene_runtime
        with patch.object(scene_runtime,'scene_bridge',side_effect=ValueError('Runtime missing')):
            code,data,_=self.invoke('workflow','stage','intent','--subject','review')
        self.assertEqual(code,0,data)
        self.assertEqual(data['data']['subjects'][0]['view'],'portrait')
        self.assertEqual(len(data['data']['stages'][0]['subjects'][0]['criteria']),3)
        self.assertFalse(data['data']['assessment']['complete'])

    def test_unflagged_next_schema_unchanged_report_envelope_and_selector_rejection(self):
        code,legacy,_=self.invoke('project','next');self.assertEqual(code,0)
        self.assertEqual(set(legacy['data']),{'ok','items','total','omitted','next_offset'})
        code,guided,size=self.invoke('project','next','--guided')
        self.assertEqual(code,0,guided);self.assertEqual(guided['data']['format'],'ambiance-guided-next');self.assertLessEqual(size,16384)
        out=self.root/'report.json';code,data,_=self.invoke('workflow','inspect','--out',out)
        self.assertEqual(code,0);self.assertEqual(studio.read(out),data)
        code,data,_=self.invoke('project','next','--view','portrait')
        self.assertEqual(code,2);self.assertIn('--guided',data['error']['message'])
        code,data,_=self.invoke('workflow','inspect','--subject','working','--revision','v1')
        self.assertEqual(code,2)

    def test_feedback_preserves_entry_or_delivery_scope_and_never_becomes_working_advice(self):
        self.capture('v1');self.capture('v2')
        first=synthetic_delivery(self.p,'portrait','v1','portrait','portrait-v1')
        second=synthetic_delivery(self.p,'landscape','v2','landscape','landscape-v2')
        self.select('pair',[first,second])
        from ambiance_studio import feedback
        feedback.add(self.p,'pair','Portrait-specific fixture report','Engineering fixture',scope='entry',view='portrait',role='silent')
        feedback.add(self.p,'pair','Landscape-specific fixture report','Engineering fixture',scope='entry',view='landscape',role='silent')
        feedback.add(self.p,'pair','Delivery-wide fixture report','Engineering fixture',scope='delivery')
        a=workflow.Assessment(self.p,subject='review');rows=[r for r in a.ordered if r['kind']=='feedback']
        self.assertEqual(len(rows),3)
        entry=next(r for r in rows if r['subject'].get('view')=='portrait')
        self.assertEqual(entry['subject']['view'],'portrait');self.assertEqual(entry['subject']['revision'],'v1')
        delivery=next(r for r in rows if r['subject']['kind']=='delivery')
        self.assertNotIn('edition',delivery['subject']);self.assertEqual(len(delivery['applies_to_subject_ids']),2)
        self.assertEqual(workflow.explain(self.p,delivery['id'],subject='review')['subject']['kind'],'delivery')
        self.assertFalse(any(r['kind']=='feedback' for r in workflow.Assessment(self.p).ordered))
        focused=workflow.Assessment(self.p,subject='review',view='portrait')
        reports=[r for r in focused.ordered if r['kind']=='feedback']
        self.assertEqual(len(reports),2)
        self.assertFalse(any(r['subject'].get('view')=='landscape' for r in reports))
        self.assertTrue(all(r['subject'].get('revision') in [None,'v1'] for r in reports))

    def test_action_pagination_preserves_subject_page_and_subject_paging_resets_action_offset(self):
        self.capture('v1');self.capture('v2')
        first=synthetic_delivery(self.p,'portrait','v1','portrait','portrait-v1')
        second=synthetic_delivery(self.p,'landscape','v2','landscape','landscape-v2');self.select('pair',[first,second])
        code,output,_=self.invoke('workflow','inspect','--subject','review','--subject-offset','1','--subject-limit','1','--limit','1','--kind','production','--details')
        self.assertEqual(code,0,output);current=output['data']
        args=cli.parser().parse_args(current['next_argv'][1:]);self.assertEqual(args.subject_offset,1);self.assertEqual(args.subject_limit,1)
        self.assertTrue(args.details);self.assertEqual(args.kind,'production')
        following=cli.run(args);self.assertEqual(current['subjects'],following['subjects'])
        self.assertNotEqual(current['items'][0]['id'],following['items'][0]['id'])
        code,output,_=self.invoke('workflow','inspect','--subject','review','--subject-limit','1','--offset','1','--limit','2','--kind','production','--details')
        args=cli.parser().parse_args(output['data']['next_subjects_argv'][1:])
        self.assertEqual(args.subject_offset,1);self.assertEqual(args.offset,0);self.assertEqual(args.limit,2)
        self.assertEqual(args.kind,'production');self.assertTrue(args.details)


if __name__=='__main__':unittest.main()
