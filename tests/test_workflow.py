"""Consequential workflow boundaries; synthetic observations never approve a film."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import studio
from ambiance_studio import cli, workflow, workflow_catalog, workflow_operations, revision_capture, scene_runtime
from ambiance_studio.errors import CommandError
from ambiance_studio.workflow_subjects import Query
from test_production_coverage import fixture


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.p=fixture(self.root)

    def run_cli(self,*args):return cli.run(cli.parser().parse_args(['--project',str(self.p),*map(str,args)]))
    def snapshot(self):return {str(p.relative_to(self.p)):studio.digest(p) for p in self.p.rglob('*') if p.is_file()}
    def capture(self,id='v1'):return self.run_cli('revision','capture',id,'--selection',self.p/'plans/selection.json')

    def test_catalog_routes_docs_and_bindings_reject_executable_or_unknown_fields(self):
        catalog=workflow_catalog.load();self.assertEqual(len(catalog['stages']),9)
        for stage in catalog['stages'].values():
            self.assertTrue(stage['inputs']);self.assertTrue(stage['outputs'])
        source=studio.read(workflow_catalog.CATALOG)
        for change in [lambda d:d['operations'][0].update(shell='bad'),lambda d:d['operations'][0].update(resolver='invented'),lambda d:d['stages'][0].update(coverage_stage='mix')]:
            value=copy.deepcopy(source);change(value);path=self.root/'invalid.json';studio.write(path,value)
            with self.assertRaises(ValueError):workflow_catalog.load(path)

    def test_pure_queries_with_lock_and_readonly_project_no_persistence(self):
        lock=self.p/'.ambiance/write.lock';lock.write_text('Held writer fixture')
        before=self.snapshot()
        with patch.object(studio,'write',side_effect=AssertionError('Query wrote project files')):
            result=self.run_cli('workflow','inspect')
            guided=self.run_cli('project','next','--guided')
            self.run_cli('workflow','stage','intent','--details')
            self.run_cli('workflow','explain',result['items'][0]['id'],'--expect-assessment',result['assessment']['sha256'])
        self.assertEqual(before,self.snapshot());self.assertTrue(result['ok']);self.assertTrue(guided['ok'])
        for result in [result,guided]:self.assertLessEqual(len(json.dumps({'data':result},indent=2)),16384)

    def test_blank_begins_reference_intent_and_preserves_creative_fields(self):
        project=self.root/'blank';cli.init_project(project,None,'Blank','blank')
        data=workflow.inspect(project,limit=8)
        self.assertEqual([r['operation'] for r in data['items'][:2]],['reference.inspect','intent.author'])
        self.assertIn('story.premise',data['items'][1]['missing_inputs'])
        self.assertNotIn('argv',data['items'][1]);self.assertEqual(data['assessment']['coverage_calls'],0)
        self.assertEqual(len(data['stages']),9)
        sound=workflow.inspect(project,stage='sound-design')['stages'][0]
        self.assertEqual(sound['subjects'][0]['coverage']['state'],'unsupported')

    def test_actual_custom_pipeline_criteria_and_native_verdict_no_catalog_authority(self):
        pipeline=studio.read(self.p/'pipeline.json')
        pipeline['gates'][0]['criteria'][0]['description']='Explicit different local direction'
        pipeline['gates'].append({'id':'custom','name':'Custom','depends':[],'watch':['handoff.md'],
                                 'criteria':[{'id':'operator-rule','kind':'human','description':'Actual custom condition'}]})
        studio.write(self.p/'pipeline.json',pipeline)
        data=workflow.inspect(self.p,stage='intent')['stages'][0]['subjects'][0]
        self.assertEqual(data['criteria'],pipeline['gates'][0]['criteria'])
        self.assertEqual(data['criterion_bindings']['reference-read'],'custom-or-altered')
        native=studio.gate_status(self.p)['gates']['intent']
        self.assertEqual(data['gate']['state'],native['state'])
        custom=workflow.inspect(self.p,stage='custom')['stages'][0]
        self.assertEqual(custom['subjects'][0]['criteria'],pipeline['gates'][-1]['criteria'])
        self.assertEqual(custom['subjects'][0]['coverage']['state'],'unsupported')
        self.assertEqual(custom['guidance']['operations'],['review.draft'])
        with self.assertRaisesRegex(ValueError,'Unknown gate'):workflow.inspect(self.p,stage='not-present')

    def test_missing_runtime_and_malformed_scene_keep_intent_pipeline_material(self):
        with patch.object(scene_runtime,'scene_bridge',side_effect=CommandError('Node unavailable','missing_dependency',3)),patch.object(workflow_operations.Operations,'available',return_value={'available':False}):
            result=workflow.inspect(self.p,stage='intent')
        self.assertEqual(len(result['stages'][0]['subjects'][0]['criteria']),3)
        self.assertTrue(result['subjects'][0]['control_hashes']['plan'])
        (self.p/'scene/scene.json').write_text('{broken')
        result=workflow.inspect(self.p,stage='intent')
        self.assertTrue(result['ok']);self.assertFalse(result['assessment']['complete'])
        self.assertIn('pipeline',result['subjects'][0]['control_hashes'])
        self.assertNotIn('scene',result['subjects'][0]['control_hashes'])

    def test_revision_without_edition_does_not_fallback_after_working_or_captured_scene_damage(self):
        self.capture()
        expected=studio.read(self.p/'revisions/v1/controls/pipeline.json')
        (self.p/'pipeline.json').write_text('{broken')
        (self.p/'scene/scene.json').write_text('{broken')
        result=workflow.inspect(self.p,revision='v1',stage='intent')
        self.assertEqual(result['stages'][0]['subjects'][0]['criteria'],expected['gates'][0]['criteria'])
        self.assertEqual(result['subjects'][0]['revision'],'v1')
        captured=revision_capture.load(self.p,'v1')['controls']['scene'];(self.p/captured).write_text('{broken')
        result=workflow.inspect(self.p,revision='v1',stage='intent')
        self.assertEqual(result['stages'][0]['subjects'][0]['criteria'],expected['gates'][0]['criteria'])
        self.assertFalse(result['assessment']['complete'])
        self.assertTrue(any(r.get('component')=='scene' for r in workflow.inspect(self.p,revision='v1',details=True)['diagnostics']))

    def test_invalid_selectors_no_fallback(self):
        for options in [{'subject':'review'},{'subject':'release'},{'revision':'absent'},{'edition':'a'},{'view':'unknown'},{'subject':'working','revision':'v1'}]:
            with self.subTest(options=options),self.assertRaises((ValueError,CommandError)):workflow.inspect(self.p,**options)

    def test_stable_logical_ids_separate_freshness_and_removed_action_rejects(self):
        first=workflow.inspect(self.p)
        item=next(r for r in first['items'] if r['operation']=='asset.proof')
        scene=studio.read(self.p/'scene/scene.json');scene['title']='Changed working title';studio.write(self.p/'scene/scene.json',scene)
        second=workflow.inspect(self.p)
        self.assertIn(item['id'],[r['id'] for r in second['items']]);self.assertNotEqual(first['assessment']['sha256'],second['assessment']['sha256'])
        with self.assertRaises(CommandError) as error:workflow.explain(self.p,item['id'],first['assessment']['sha256'])
        self.assertEqual(error.exception.code,'stale_assessment')
        with self.assertRaises(CommandError) as error:workflow.explain(self.p,'wf1.'+'0'*64)
        self.assertEqual(error.exception.code,'stale_action')

    def test_concurrent_inputs_diagnose_and_remove_runnable_commands(self):
        real=Query.finish
        def changing(query):
            scene=studio.read(self.p/'scene/scene.json');scene['title']='Racing writer';studio.write(self.p/'scene/scene.json',scene)
            return real(query)
        with patch.object(Query,'finish',changing):data=workflow.inspect(self.p,limit=1000)
        self.assertTrue(data['assessment']['changed_inputs'])
        self.assertTrue(all('argv' not in r and r['state']=='unavailable' for r in data['items']))
        self.assertTrue(all(r['subjects'][0]['gate_state']=='unknown' for r in data['stages']))

    def test_inventory_work_dependencies_dedup_and_pending_gates_do_not_hide_proofs(self):
        inventory=studio.read(self.p/'plans/asset-inventory.json')
        inventory['items'] += [{'id':'ground','required':True,'required_parts':['complete backing']},
                               {'id':'lantern','required':True,'dependencies':['ground'],'required_parts':['complete lantern']},
                               {'id':'pumpkin','required':True,'dependencies':['ground'],'required_parts':['complete pumpkin']}]
        studio.write(self.p/'plans/asset-inventory.json',inventory)
        a=workflow.Assessment(self.p);rows=a.ordered
        items={r.get('item_id'):r for r in rows if r.get('item_id')}
        self.assertEqual(len([r for r in rows if r.get('item_id')=='ground']),1)
        for id in ['lantern','pumpkin']:
            self.assertIn(items['ground']['id'],items[id]['dependencies'])
            self.assertLess(rows.index(items['ground']),rows.index(items[id]))
        proof=next(r for r in rows if r['operation']=='asset.proof')
        self.assertEqual(proof['state'],'ready');self.assertEqual(proof['dependencies'],[])
        self.assertEqual(proof['gate_dependencies'],['layout'])
        filtered=a.project(kind='production',limit=1000)
        self.assertIn(proof['id'],[r['id'] for r in filtered['items']])

    def test_wrong_view_and_stale_raster_are_projected_from_native_coverage(self):
        proof=self.run_cli('render','views-proof','--view','portrait','--seconds','1','--long-edge','160','--out',self.p/'render/portrait')
        self.run_cli('plan','evidence','pixels','--view','portrait','--receipt',str(Path(proof['report']).relative_to(self.p)))
        a=workflow.Assessment(self.p,stage='animation')
        issues=[r for r in a.ordered if r.get('expectation',{}).get('id')=='pixels']
        self.assertEqual([r['expectation']['view'] for r in issues],['landscape'])
        scene=studio.read(self.p/'scene/scene.json');scene['title']='New scene';studio.write(self.p/'scene/scene.json',scene)
        a=workflow.Assessment(self.p,stage='animation')
        issues=[r for r in a.ordered if r.get('expectation',{}).get('id')=='pixels']
        self.assertEqual({r['expectation']['view'] for r in issues},{'portrait','landscape'})
        for row in issues:self.assertTrue(row['dependencies'])
        self.assertIn('Stale',str(issues))

    def test_prepared_art_has_direct_compiler_path_and_all_argv_parse(self):
        inventory=studio.read(self.p/'plans/asset-inventory.json')
        inventory['items'].append({'id':'isolated','required_parts':[{'id':'cutout','stage':'prepared','files':[{'file':'assets/source.png','sha256':studio.digest(self.p/'assets/source.png')}]}]})
        studio.write(self.p/'plans/asset-inventory.json',inventory)
        a=workflow.Assessment(self.p)
        isolated=[r for r in a.ordered if 'part.isolated.cutout' in r['issue_ids']]
        self.assertEqual(isolated[0]['operation'],'asset.build');self.assertNotIn('argv',isolated[0])
        self.assertTrue(any(r['operation']=='art.preflight' and 'argv' in r for r in a.ordered))
        for row in a.ordered:
            if 'argv' in row:
                cli.parser().parse_args(row['argv'][1:]);self.assertTrue(Path(row['argv'][0]).is_absolute())
                self.assertNotIn('model',row['argv']);self.assertFalse(any('YOUR_' in p for p in row['argv']))
        assets=workflow.inspect(self.p,stage='assets',details=True)
        verbs={r.get('native_suboperation') for r in assets['stages'][0]['operations']}
        self.assertTrue({'init','inspect','check','edit','build','proof','place'}<=verbs)

    def test_guidance_edit_does_not_stale_native_gate_receipt(self):
        evidence=self.p/'plans/engineering-note.txt';evidence.write_text('Synthetic observation for native receipt identity testing only.')
        draft=studio.review_template(self.p,'intent');draft.update(verdict='pass',recorder='Engineering fixture')
        for row in draft['checks']:
            row.update(result='pass',observed_by={'kind':'agent','name':'Engineering fixture'},note='Synthetic gate contract check.',evidence=['plans/engineering-note.txt'])
        path=self.p/'review-drafts/intent.json';studio.write(path,draft);studio.record_review(self.p,path)
        before=self.snapshot();catalog=workflow_catalog.load();catalog['stages']['intent']['purpose']='Editorial guidance change'
        catalog['sha256']='a'*64
        with patch.object(workflow,'load_catalog',return_value=catalog):result=workflow.inspect(self.p,stage='intent')
        self.assertEqual(result['stages'][0]['subjects'][0]['gate']['state'],'passed')
        self.assertEqual(before,self.snapshot())

    def test_shared_proof_dedup_and_stage_filter_retains_native_prerequisites(self):
        spec=studio.read(self.p/'plans/production-plan.json');extra=copy.deepcopy(next(e for e in spec['expectations'] if e['id']=='pixels'))
        extra['id']='second-raster';spec['expectations'].append(extra);studio.write(self.p/'plans/production-plan.json',spec)
        inventory=studio.read(self.p/'plans/asset-inventory.json');inventory['items'][0]['required_parts'][0]['stage']='source';inventory['items'][0]['state']='in-progress';studio.write(self.p/'plans/asset-inventory.json',inventory)
        a=workflow.Assessment(self.p,stage='animation');data=a.project(limit=1000)
        for view in ['portrait','landscape']:
            dependents=[r for r in a.ordered if r.get('expectation',{}).get('id') in ['pixels','second-raster'] and r['expectation']['view']==view]
            self.assertEqual(len(dependents),2);self.assertEqual(dependents[0]['dependencies'],dependents[1]['dependencies'])
        self.assertTrue(any(r['stage']=='assets' and r['kind']=='coverage' for r in data['items']))

    def test_captured_view_inspection_uses_supported_native_revision_route(self):
        self.capture()
        a=workflow.Assessment(self.p,revision='v1',view='portrait',stage='layout')
        row=next(r for r in a.ordered if r['operation']=='view.inspect')
        self.assertEqual(row['state'],'ready');self.assertEqual(row['argv'][-5:],['view','inspect','portrait','--revision','v1'])
        parsed=cli.parser().parse_args(row['argv'][1:]);self.assertEqual(parsed.revision,'v1')
        result=cli.run(parsed);self.assertEqual(result['revision'],'v1');self.assertEqual(set(result['views']),{'portrait'})


if __name__=='__main__':unittest.main()
