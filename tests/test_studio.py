"""Exercise the review recorder with synthetic evidence, not real film approvals."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import studio

class StudioTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='ambiance-studio-test-')
        self.project=Path(self.tmp.name)/'test-scene'
        studio.new_project(self.project)
        (self.project/'plans/evidence.txt').write_text('Synthetic evidence for record-keeping tests; no art or media was reviewed.\n')
        (self.project/'feedback/test-observation.txt').write_text('Synthetic test observation, not a real human review.\n')
        (self.project/'deliverables/final/test-artifact.txt').write_text('Synthetic final artifact, not an encoded video.\n')
    def tearDown(self): self.tmp.cleanup()
    def status(self): return studio.gate_status(self.project)
    def draft(self,id,kind=None):
        d=studio.review_template(self.project,id);d['verdict']='pass';d['recorder']='Synthetic test recorder'
        for c in d['checks']:
            c['result']='pass';c['note']='Synthetic observation used only to test receipt behavior.'
            c['observed_by']={'kind':kind or ('human' if id=='release' else 'agent'),'name':'Synthetic test observer'}
            c['evidence']=['plans/evidence.txt']
            if id=='release': c['evidence']+=['feedback/test-observation.txt','deliverables/final/test-artifact.txt']
        return d
    def record(self,id,draft=None):
        path=self.project/'review-drafts'/f'{id}.json';studio.write(path,draft or self.draft(id))
        return studio.record_review(self.project,path)
    def all_pass(self):
        for g in studio.pipeline(self.project): self.record(g['id'])
    def test_new_project_has_no_passes(self):
        s=self.status();self.assertEqual(s['gates']['intent']['state'],'pending')
        self.assertEqual(s['gates']['layout']['state'],'blocked');self.assertFalse(s['release_ready'])
    def test_existing_project_protected(self):
        with self.assertRaises(ValueError): studio.new_project(self.project)
    def test_missing_evidence_rejected(self):
        d=self.draft('intent');d['checks'][0]['evidence']=['missing.png']
        with self.assertRaisesRegex(ValueError,'Missing or empty evidence'): self.record('intent',d)
    def test_unperformed_check_cannot_pass(self):
        d=self.draft('intent');d['checks'][0]['result']='not-run'
        with self.assertRaisesRegex(ValueError,'Unpassed criterion'): self.record('intent',d)
    def test_dependency_order_enforced(self):
        with self.assertRaisesRegex(ValueError,'dependencies'): self.record('layout')
    def test_revision_retained_without_claiming_pass(self):
        d=self.draft('intent');d['verdict']='revise';d['checks'][0]['result']='fail'
        self.record('intent',d);self.assertEqual(self.status()['gates']['intent']['state'],'revise')
    def test_evidence_change_invalidates_review(self):
        self.record('intent');(self.project/'plans/evidence.txt').write_text('changed')
        self.assertEqual(self.status()['gates']['intent']['state'],'stale')
    def test_targeted_asset_change_preserves_independent_sound_review(self):
        self.all_pass();(self.project/'assets/raw/new-asset.txt').write_text('new production input')
        s=self.status();self.assertEqual(s['gates']['assets']['state'],'stale')
        self.assertEqual(s['gates']['sound-design']['state'],'passed')
        self.assertNotEqual(s['gates']['animation']['state'],'passed');self.assertFalse(s['release_ready'])
    def configure_picture(self, generation):
        folder='.ambiance/model-generations/'+generation
        studio.write(self.project/folder/'scene.json',{'version':1,'layers':[]})
        studio.write(self.project/folder/'catalog.json',{'version':1,'assets':[]})
        studio.write(self.project/'ambiance-project.json',{'version':1,'scene':folder+'/scene.json','catalog':folder+'/catalog.json'})
        return self.project/folder
    def test_selected_generation_switch_stales_picture_but_not_sound(self):
        first=self.configure_picture('first');self.all_pass()
        self.configure_picture('second')
        s=self.status()['gates']
        self.assertEqual(s['assets']['state'],'stale');self.assertEqual(s['animation']['state'],'stale')
        self.assertEqual(s['intent']['state'],'passed');self.assertEqual(s['sound-design']['state'],'passed')
        # Restoring exact selection restores currentness without rewriting reviews.
        studio.write(self.project/'ambiance-project.json',{'version':1,'scene':str((first/'scene.json').relative_to(self.project)),
            'catalog':str((first/'catalog.json').relative_to(self.project))})
        self.assertTrue(self.status()['archived'])
    def test_selected_picture_edits_and_missing_inputs_are_gate_local(self):
        folder=self.configure_picture('first');self.all_pass()
        config=studio.read(self.project/'ambiance-project.json');config['title']='Unrelated metadata'
        studio.write(self.project/'ambiance-project.json',config)
        self.assertTrue(self.status()['archived'])
        studio.write(folder/'scene.json',{'version':1,'layers':[],'note':'Changed picture'})
        self.assertEqual(self.status()['gates']['animation']['state'],'stale')
        self.assertEqual(self.status()['gates']['assets']['state'],'passed')
        (folder/'catalog.json').unlink()
        s=self.status()['gates'];self.assertEqual(s['assets']['state'],'stale')
        self.assertEqual(s['sound-design']['state'],'passed')
        with self.assertRaisesRegex(ValueError,'Review inputs are unavailable'):self.record('assets')
        self.assertEqual(s['intent']['state'],'passed')
        studio.write(self.project/'ambiance-project.json',{'version':999})
        self.assertEqual(self.status()['gates']['intent']['state'],'passed')
        self.assertEqual(self.status()['gates']['assets']['state'],'stale')
    def test_selection_change_during_recording_does_not_publish_receipt(self):
        self.configure_picture('first');self.record('intent');self.record('layout')
        from ambiance_studio.production_coverage import normalize_observations
        def switch(*args,**kwargs):
            result=normalize_observations(*args,**kwargs);self.configure_picture('second');return result
        with patch('ambiance_studio.production_coverage.normalize_observations',side_effect=switch):
            with self.assertRaisesRegex(ValueError,'inputs changed during review'):self.record('assets')
        self.assertFalse((self.project/'reviews/assets.json').exists())
    def test_new_receipt_invalidates_dependent_and_preserves_history(self):
        self.record('intent');self.record('layout');self.record('intent')
        self.assertEqual(self.status()['gates']['layout']['state'],'stale')
        self.assertEqual(len(list((self.project/'reviews/history').glob('intent-*.json'))),1)
    def test_agent_cannot_substitute_for_required_human_observation(self):
        for g in studio.pipeline(self.project):
            if g['id']=='release': break
            self.record(g['id'])
        with self.assertRaisesRegex(ValueError,'Human observation required'): self.record('release',self.draft('release','agent'))
    def test_human_review_requires_exact_final_file_and_feedback(self):
        d=self.draft('release')
        d['checks'][0]['evidence']=['plans/evidence.txt']
        with self.assertRaisesRegex(ValueError,'feedback record'): self.record('release',d)
    def test_reference_paths_cannot_escape_project(self):
        d=self.draft('intent');d['checks'][0]['evidence']=['../outside.txt']
        with self.assertRaisesRegex(ValueError,'inside the project'): self.record('intent',d)
    def test_receipt_edit_detected(self):
        self.record('intent');path=self.project/'reviews/intent.json';r=studio.read(path)
        r['checks'][0]['note']='Changed after recording';studio.write(path,r)
        self.assertEqual(self.status()['gates']['intent']['state'],'stale')
    def test_final_change_clears_release_readiness(self):
        self.all_pass();self.assertTrue(self.status()['archived'])
        (self.project/'deliverables/final/test-artifact.txt').write_text('changed final')
        s=self.status();self.assertEqual(s['gates']['export']['state'],'stale')
        self.assertFalse(s['release_ready']);self.assertFalse(s['archived'])

if __name__=='__main__': unittest.main(verbosity=2)
