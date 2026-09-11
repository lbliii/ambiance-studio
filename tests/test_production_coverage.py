"""Exact typed evidence, stage scope and shared public readiness decisions."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PIL import Image
import studio
from ambiance_studio import cli, production_plan as plan, production_coverage as coverage, revisions, production


def fixture(root):
    project = (root/'film').resolve(); cli.init_project(project, None, 'Synthetic scope fixture', 'blank')
    image = project/'assets/source.png'; Image.new('RGB', (160, 160), '#887744').save(image)
    studio.write(project/'assets/catalog.json', {'version': 1, 'assets': [{'id': 'paint', 'kind': 'plate', 'file': 'assets/source.png', 'width': 160, 'height': 160, 'sha256': studio.digest(image)}]})
    scene = studio.read(project/'scene/scene.json'); scene['canvas'].update(width=160, height=160, fps=6, loop_seconds=1)
    scene['framing'] = {'version': 1, 'views': {'portrait': {'rect_scene_px': [35, 0, 90, 160], 'output': {'width': 90, 'height': 160}}, 'landscape': {'rect_scene_px': [0, 35, 160, 90], 'output': {'width': 160, 'height': 90}}}}
    studio.write(project/'scene/scene.json', scene)
    cli.run(cli.parser().parse_args(['--project', str(project), 'scene', 'add', 'paint', '--id', 'plate', '--width', '1']))
    spec = studio.read(ROOT/'examples/production-plan.json')
    spec['sources'] = [{'id': 'paint', 'path': 'assets/source.png', 'sha256': studio.digest(image)}]
    spec['elements'][0]['realization']['layer_ids'] = ['plate']; spec['elements'][0]['source_ids'] = ['paint']
    spec['outputs'] = [{'view_id': id, 'roles': ['silent']} for id in ['portrait', 'landscape']]
    spec['expectations'] = []
    for id, check, stage, type in [('framing', 'view', 'layout', 'structural'), ('pixels', 'raster', 'animation', 'measured'), ('movie', 'movie', 'export', 'measured'), ('paint', 'art', 'assets', 'structural')]:
        spec['expectations'].append({'id': id, 'rationale': 'Synthetic scope validation', 'direction': 'Test fixture; no artistic verdict', 'stage': stage, 'view_ids': ['portrait', 'landscape'], 'element_ids': ['room'], 'action_ids': [], 'relation_ids': [], 'requirement': {'type': type, 'check': check}})
    studio.write(project/'plans/asset-inventory.json', {'version': 1, 'items': [{'id': 'room', 'required': True, 'state': 'complete', 'required_parts': [{'id': 'plate', 'stage': 'placed', 'asset_id': 'paint', 'layer_ids': ['plate'], 'files': [{'file': 'assets/source.png', 'sha256': studio.digest(image)}]}]}]})
    studio.write(project/'proposal.json', spec); plan.apply(project, project/'proposal.json')
    studio.write(project/'plans/selection.json', {'format': revisions.SELECTION, 'schema_version': 1, 'scene': 'scene/scene.json', 'catalog': 'assets/catalog.json'})
    return project


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.p = fixture(self.root)

    def run_cli(self, *args):
        return cli.run(cli.parser().parse_args(['--project', str(self.p), *map(str, args)]))

    def capture(self, id='v1'):
        return self.run_cli('revision', 'capture', id, '--selection', self.p/'plans/selection.json')

    def proof(self, id='proof', revision=None, views=('portrait', 'landscape')):
        args = ['render', 'views-proof', '--seconds', '1', '--long-edge', '160', '--out', self.p/'render'/id]
        for view in views: args += ['--view', view]
        if revision: args += ['--revision', revision]
        return self.run_cli(*args)

    def register(self, report, view='portrait', revision=None, id='pixels'):
        return coverage.register_evidence(self.p, id, view, str(Path(report).relative_to(self.p)), revision)

    def test_empty_missing_and_omitted_expectations_never_vacuously_pass(self):
        data = plan.load(self.p); data['elements'] = []; data['expectations'] = []; data['outputs'] = []
        studio.write(self.p/plan.PATH, data)
        report = coverage.evaluate(self.p, 'layout')
        self.assertFalse(report['ready']); self.assertIn('plan.expectations-unplanned', [r['id'] for r in report['blocked']])
        (self.p/plan.PATH).unlink()
        self.assertEqual(coverage.evaluate(self.p)['blocked'][0]['id'], 'plan.unavailable')

    def test_layout_animation_export_applicability_and_real_raster_registration(self):
        self.assertTrue(coverage.evaluate(self.p, 'layout')['ready'])
        animation = coverage.evaluate(self.p)
        self.assertFalse(animation['ready']); self.assertNotIn('movie', json.dumps(animation))
        report = self.proof()['report']
        for view in ['portrait', 'landscape']: self.register(report, view)
        self.assertTrue(coverage.evaluate(self.p)['ready'])
        self.assertFalse(coverage.evaluate(self.p, 'export')['ready'])
        preflight = coverage.evaluate(self.p, 'export', phase='preflight')
        self.assertTrue(preflight['ready']); self.assertEqual(len(preflight['future_outputs']), 2)

    def test_arbitrary_report_wrong_view_and_changed_png_rejected(self):
        fake = self.p/'fake.json'; studio.write(fake, {'ok': True, 'report': 'looks complete'})
        with self.assertRaises(ValueError): self.register(fake)
        report = self.proof(views=('portrait',))['report']
        with self.assertRaises(ValueError): self.register(report, 'landscape')
        self.register(report)
        frame = Path(report).parent/'portrait/00000.png'; frame.write_bytes(frame.read_bytes()+b'changed')
        self.assertFalse(coverage.evaluate(self.p, view='portrait')['ready'])

    def test_stale_plan_wrong_revision_and_captured_identity(self):
        self.capture(); manifest = revisions.load(self.p, 'v1'); self.assertIn('production_plan', manifest['controls'])
        before = revisions.manifest_path(self.p, 'v1').read_bytes()
        report = self.proof(revision='v1')['report']; self.register(report, revision='v1')
        self.capture('v2')
        with self.assertRaises(ValueError): self.register(report, revision='v2')
        self.assertTrue(coverage.evaluate(self.p, view='portrait', revision='v1')['ready'])
        self.assertFalse(coverage.evaluate(self.p, view='portrait')['ready'])
        data = plan.load(self.p); data['expectations'][1]['rationale'] = 'Explicit new intent'; studio.write(self.p/plan.PATH, data)
        self.assertTrue(coverage.evaluate(self.p, view='portrait', revision='v1')['ready'])
        self.assertEqual(revisions.manifest_path(self.p, 'v1').read_bytes(), before)
        self.assertTrue(revisions.compare(self.p, 'v1')['working_diverged'])
        ctx = revisions.review_context(self.p, 'v1', view='portrait')
        self.assertEqual(ctx['subject']['production_plan']['plan_sha256'], plan.load_context(self.p, 'v1')['plan_sha256'])

    def test_two_baked_labels_do_not_prove_independent_control(self):
        data = plan.load(self.p); element = copy.deepcopy(data['elements'][0]); element['id'] = 'other'; data['elements'].append(element)
        exp = data['expectations'][0]; exp['element_ids'] = ['room', 'other']; exp['requirement']['check'] = 'independent-control'
        studio.write(self.p/plan.PATH, data)
        self.assertFalse(coverage.evaluate(self.p, 'layout')['ready'])

    def recipe(self):
        return {'format': 'ambiance-iteration', 'schema_version': 2, 'id': 'iteration', 'revision': 'v1', 'views': ['portrait', 'landscape'], 'default': {'view': 'portrait', 'role': 'silent'}, 'editions': [{'role': 'silent'}], 'scope': 'review'}

    def test_cli_overview_and_iteration_use_identical_blocked_ids_drafts_renderable(self):
        recipe = self.recipe(); file = self.p/'recipe.json'; studio.write(file, recipe)
        direct = self.run_cli('plan', 'coverage')
        overview = production.overview(self.p, 'fixture', 'http://localhost')['production_readiness']
        preflight = self.run_cli('iteration', 'preflight', file)
        ids = lambda r: [x['id'] for x in r['blocked']]
        self.assertEqual(ids(direct), ids(overview)); self.assertEqual(ids(direct), ids(preflight['readiness']))
        self.assertTrue(preflight['may_render']); self.assertFalse(preflight['ok'])
        recipe['scope'] = 'final'; recipe['views'] = ['portrait']; studio.write(file, recipe)
        preflight = self.run_cli('iteration', 'preflight', file)
        self.assertFalse(preflight['may_render'])
        self.assertIn('plan.output-missing.landscape.silent', ids(preflight['readiness']))

    def test_review_draft_preserves_unperformed_observations_and_binds_plan(self):
        data = plan.load(self.p); exp = copy.deepcopy(data['expectations'][1]); exp['id'] = 'composition'; exp['requirement'] = {'type': 'observed', 'check': 'composition'}
        data['expectations'].append(exp); studio.write(self.p/plan.PATH, data); self.capture()
        out = self.p/'draft.json'
        self.run_cli('review', 'draft', 'animation', '--revision', 'v1', '--view', 'portrait', '--out', out)
        draft = studio.read(out); self.assertEqual(draft['expectations'][0]['status'], 'unreviewed')
        draft['recorder'] = 'Synthetic test fixture'; studio.write(out, draft); self.run_cli('review', 'record', out)
        path = revisions.review_context(self.p, 'v1', view='portrait')['review_dir']/'animation.json'
        with self.assertRaises(ValueError): self.register(path, revision='v1', id='composition')
        draft['expectations'][0].update(status='meets-direction', normal_speed=True, observed_by={'kind': 'agent', 'name': 'Synthetic fixture'}, note='Test fixture only', display={'width': 90, 'height': 160}, evidence=[{'path': 'fake.json', 'kind': 'raster'}])
        studio.write(self.p/'fake.json', {'ok': True}); studio.write(out, draft)
        with self.assertRaises(ValueError): self.run_cli('review', 'record', out)

    def test_changed_source_and_missing_required_art_expectation_are_gaps(self):
        data = plan.load(self.p); data['expectations'] = [e for e in data['expectations'] if e['id'] != 'paint']; studio.write(self.p/plan.PATH, data)
        self.assertIn('plan.art-unplanned.room', [r['id'] for r in coverage.evaluate(self.p)['blocked']])
        self.capture(); image = self.p/'assets/source.png'; Image.new('RGB', (160,160), 'blue').save(image)
        self.assertFalse(coverage.evaluate(self.p, revision='v1')['ready'])
        state = revisions.status(self.p, 'v1')
        self.assertEqual(state['gates']['layout']['state'], 'blocked')

    def test_recorded_observation_is_exact_and_does_not_transfer_to_other_view(self):
        data = plan.load(self.p); exp = copy.deepcopy(data['expectations'][1]); exp['id'] = 'composition'; exp['requirement'] = {'type': 'observed', 'check': 'composition'}
        data['expectations'].append(exp); studio.write(self.p/plan.PATH, data); self.capture()
        report = self.proof(revision='v1')['report']; draft_path = self.p/'draft.json'
        self.run_cli('review', 'draft', 'animation', '--revision', 'v1', '--view', 'portrait', '--out', draft_path)
        draft = studio.read(draft_path); draft['recorder'] = 'Synthetic observation protocol fixture'
        draft['expectations'][0].update(status='meets-direction', normal_speed=True,
            observed_by={'kind': 'agent', 'name': 'Synthetic observation protocol fixture'},
            note='Protocol fixture for typed observation validation; not an actual film assessment.',
            display={'width':90,'height':160}, evidence=[{'path':str(Path(report).relative_to(self.p)),'kind':'raster'}])
        studio.write(draft_path,draft); self.run_cli('review','record',draft_path)
        path = revisions.review_context(self.p,'v1',view='portrait')['review_dir']/'animation.json'
        self.register(path,revision='v1',id='composition')
        with self.assertRaises(ValueError):self.register(path,'landscape','v1','composition')
        data = studio.read(path); data['expectations'][0]['note']='tampered'; studio.write(path,data)
        self.assertFalse(coverage.evaluate(self.p,view='portrait',revision='v1')['ready'])

    def test_typed_but_non_media_edition_cannot_satisfy_movie(self):
        self.capture(); output=self.p/'fake.mp4';output.write_text('arbitrary nonempty movie')
        verification=self.p/'fake-verification.json'; studio.write(verification,{'ok':True,'fully_decoded':True,'input_unchanged':True,'input_sha256':studio.digest(output),'audio':{'tracks':0}})
        path=revisions.edition_path(self.p,'v1','fake'); view=revisions.captured_view(self.p,'v1','portrait')
        studio.write(path,revisions.seal({'format':revisions.EDITION,'schema_version':2,'id':'fake','revision':'v1',
            'revision_sha256':studio.digest(revisions.manifest_path(self.p,'v1')),'view':view,
            'output_expectations':{'width':90,'height':160,'fps':6,'frames':6,'loop_frames':6,'audio_tracks':0},
            'output':{'path':'fake.mp4','sha256':studio.digest(output),'bytes':output.stat().st_size},'dependencies':[],
            'verification':{'path':'fake-verification.json','sha256':studio.digest(verification)}}))
        with self.assertRaisesRegex(ValueError,'MP4'):
            coverage.register_evidence(self.p,'movie','portrait',str(path.relative_to(self.p)),'v1','silent')

    def test_zero_warning_activity_receipt_is_not_an_observation(self):
        data=plan.load(self.p); exp=copy.deepcopy(data['expectations'][1]); exp['id']='composition';exp['requirement']={'type':'observed','check':'composition'}
        data['expectations'].append(exp);studio.write(self.p/plan.PATH,data);self.capture()
        ctx=coverage.context(self.p,'v1')
        receipt={key:ctx[key] for key in ['scene_sha256','catalog_sha256','revision']}
        receipt.update(kind='ambiance-scene-activity',schema_version=1,ok=True,
                       summary=[{'view':'portrait','actions':[{'id':'primary','warnings':[],'status':'unreviewed'}]}])
        path=self.p/'zero-warnings.json';studio.write(path,receipt)
        with self.assertRaisesRegex(ValueError,'captured revision review'):
            self.register(path,revision='v1',id='composition')

    def test_readiness_reports_pin_exact_inputs_and_reject_mid_check_edits(self):
        before=coverage.evaluate(self.p); scene_path=self.p/'scene/scene.json'
        scene=studio.read(scene_path);scene['title']='New working draft';studio.write(scene_path,scene)
        after=coverage.evaluate(self.p)
        self.assertNotEqual(before['report'],after['report'])
        self.assertNotEqual(before['inputs']['scene_sha256'],after['inputs']['scene_sha256'])
        bridge=coverage.scene_runtime.scene_bridge
        def edit(*args,**kwargs):
            result=bridge(*args,**kwargs)
            scene['title']='Concurrent edit';studio.write(scene_path,scene)
            return result
        with patch.object(coverage.scene_runtime,'scene_bridge',side_effect=edit):
            changed=coverage.evaluate(self.p,'layout')
        self.assertIn('plan.inputs-changed',[r['id'] for r in changed['blocked']])

    def test_unperformed_expectation_cannot_be_a_passing_review(self):
        data=plan.load(self.p);exp=copy.deepcopy(data['expectations'][1]);exp['id']='composition';exp['requirement']={'type':'observed','check':'composition'}
        data['expectations'].append(exp);studio.write(self.p/plan.PATH,data);self.capture()
        context=revisions.review_context(self.p,'v1',view='portrait')
        draft=studio.review_template(self.p,'animation',context);draft['verdict']='pass'
        with self.assertRaisesRegex(ValueError,'Passing review'):
            coverage.normalize_observations(self.p,draft,context)

    def test_activity_adapter_enforces_provider_timing_and_exact_action_realization(self):
        data=plan.load(self.p); data['elements'][0]['action_ids']=['gesture']
        action={'id':'gesture','element_id':'room','description':'Contract fixture','method':'transform','targets':[{'view_id':'portrait','readability_target':2}]}
        data['actions']=[action]
        exp=copy.deepcopy(data['expectations'][1]);exp.update(id='activity',action_ids=['gesture'],requirement={'type':'measured','check':'activity'})
        data['expectations'].append(exp);studio.write(self.p/plan.PATH,data)
        ctx=coverage.context(self.p); row={'id':'gesture','applicable':True,'warnings':[],'timing_target_diagnostics':[]}
        report={key:ctx[key] for key in ['scene_sha256','catalog_sha256','revision']}
        report.update(plan=plan.load_context(self.p),views=[{'view':ctx['views']['portrait']['view'],'view_sha256':ctx['views']['portrait']['view_sha256']}],
            clock={'start_frame':0,'frames':6,'fps':6,'picture_seconds':1,'stride':1},actions=[action],summary=[{'view':'portrait','actions':[row]}])
        file=self.p/'activity-contract.json';studio.write(file,{'fixture':'Provider interface is mocked here; no measured runtime claim'})
        provider=SimpleNamespace(verify_receipt=lambda path:report,actions_from_plan=lambda p:p['actions'])
        with patch.dict(sys.modules,{'ambiance_studio.activity':provider}):
            self.assertEqual(coverage.activity_receipt(self.p,file,ctx,exp,'portrait')['kind'],'activity')
            row['timing_target_diagnostics']=['sampled_onset_exceeds_authored_target']
            with self.assertRaisesRegex(ValueError,'timing targets'):coverage.activity_receipt(self.p,file,ctx,exp,'portrait')
            row['timing_target_diagnostics']=[];report['actions']=[{**action,'method':'wrong realization'}]
            with self.assertRaisesRegex(ValueError,'realization'):coverage.activity_receipt(self.p,file,ctx,exp,'portrait')

    @unittest.skipUnless(os.environ.get('AMBIANCE_TEST_NATIVE') == '1' and sys.platform == 'darwin', 'Requires actual native encode/decode')
    def test_full_native_iteration_registers_exact_movies_and_partial_review_stays_presentable(self):
        self.capture(); report = self.proof(revision='v1')['report']
        for view in ['portrait', 'landscape']: self.register(report, view, 'v1')
        recipe = self.recipe(); recipe['scope'] = 'final'
        result = production.iteration(self.p, recipe, 'Synthetic native fixture')
        self.assertTrue(result['ok'], result)
        self.assertTrue(result['production_readiness']['ready'])
        self.assertTrue(production.iteration(self.p, recipe, 'Synthetic native fixture')['reused'])
        from ambiance_studio import deliveries
        delivered = deliveries.load(self.p, recipe['id']); self.assertTrue(deliveries.inspect(self.p, recipe['id'])['production_scope']['ready'])
        declaration = delivered['selection']; declaration['id'] = 'partial-review'; declaration['entries'] = declaration['entries'][:1]
        deliveries.register(self.p, declaration)
        selected = deliveries.present(self.p, 'partial-review', 'Synthetic native fixture', 'Partial review, not full production')
        self.assertTrue(selected['ok'])
        self.assertFalse(deliveries.inspect(self.p, 'partial-review')['production_scope']['ready'])


if __name__ == '__main__': unittest.main()
