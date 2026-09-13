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

    def snapshot(self):
        return {str(p.relative_to(self.p)): (studio.digest(p) if p.is_file() else 'directory')
                for p in self.p.rglob('*')}

    def test_pure_cli_reads_on_nonwritable_project_do_not_acquire_writer_lock(self):
        from ambiance_studio import project as project_module
        # A live writer lock must not stop an independent read.
        lock = self.p/'.ambiance/write.lock'; lock.write_text('fixture writer')
        paths = [self.p, *self.p.rglob('*')]
        modes = {p: p.stat().st_mode & 0o777 for p in paths}
        before = self.snapshot()
        for path in paths: path.chmod(0o555 if path.is_dir() else 0o444)
        try:
            with patch.object(studio, 'write', side_effect=AssertionError('query wrote a report')), \
                 patch.object(project_module, 'project_lock', side_effect=AssertionError('query took writer lock')):
                result = coverage.assess(self.p, details=True)
                overview = self.run_cli('project', 'overview', '--details')
                next_work = self.run_cli('project', 'next')
            self.assertFalse(result['ready'])
            self.assertNotIn('report', result)
            self.assertTrue(overview['ok']); self.assertTrue(next_work['ok'])
            self.assertEqual(result['assessment']['subject']['mode'], 'working')
            self.assertIsNone(overview['subjects']['selected_movie'])
            self.assertEqual(before, self.snapshot())
        finally:
            for path, mode in modes.items(): path.chmod(mode)

    def test_scoped_inputs_preserve_intent_inventory_and_pipeline_without_runtime(self):
        from ambiance_studio.coverage_context import AssessmentInputs
        from ambiance_studio.errors import CommandError
        inputs = AssessmentInputs(self.p)
        before = self.snapshot()
        with patch.object(coverage.scene_runtime, 'scene_bridge', side_effect=CommandError('Node unavailable', 'missing_dependency', 3)) as runtime:
            self.assertEqual(inputs.get('plan')['story'], plan.load(self.p)['story'])
            self.assertEqual(len(inputs.get('inventory')['items']), 1)
            self.assertEqual(len(inputs.get('pipeline')), 9)
            runtime.assert_not_called()
            self.assertNotIn('catalog', inputs.components)
            assessment = coverage.assess(self.p, 'layout', assessment=inputs, details=True)
        self.assertFalse(assessment['ready'])
        self.assertFalse(assessment['assessment']['complete'])
        self.assertEqual(assessment['assessment']['components']['plan']['state'], 'available')
        self.assertEqual(assessment['assessment']['components']['views']['state'], 'unknown')
        self.assertTrue(all(row['ready'] is None for row in assessment['expectations']))
        self.assertNotIn('pipeline', assessment['assessment']['components'])  # independent preloaded material is outside coverage
        self.assertEqual(inputs.finish(['pipeline'])['components']['pipeline']['state'], 'available')
        self.assertEqual(before, self.snapshot())

    def test_invalid_components_and_legacy_plan_absence_remain_scoped(self):
        from ambiance_studio.coverage_context import AssessmentInputs
        for name, path in [('scene', self.p/'scene/scene.json'), ('catalog', self.p/'assets/catalog.json'),
                           ('inventory', self.p/'plans/asset-inventory.json')]:
            original = path.read_bytes()
            try:
                path.write_text('{broken')
                inputs = AssessmentInputs(self.p)
                self.assertIsNone(inputs.get(name))
                self.assertEqual(inputs.components[name]['state'], 'unknown')
                self.assertIsNotNone(inputs.get('plan')); self.assertIsNotNone(inputs.get('pipeline'))
                result = coverage.assess(self.p, details=True)
                self.assertFalse(result['ready']); self.assertFalse(result['assessment']['complete'])
                self.assertTrue(result['assessment']['diagnostics'])
                if name == 'inventory':
                    self.assertIn('plan.expectation.framing.portrait', result['fulfilled'])
            finally:
                path.write_bytes(original)
        (self.p/plan.PATH).unlink()
        inputs = AssessmentInputs(self.p)
        self.assertIsNone(inputs.get('plan')); self.assertIsNotNone(inputs.get('inventory'))
        self.assertEqual(coverage.assess(self.p)['blocked'][0]['id'], 'plan.unavailable')
        self.assertEqual(coverage.evaluate(self.p)['blocked'][0]['id'], 'plan.unavailable')

    def test_missing_wrong_view_stale_evidence_and_changed_sources_are_not_success(self):
        absent = coverage.assess(self.p, view='portrait', details=True)
        self.assertFalse(absent['ready'])
        report = self.proof(views=('portrait',))['report']; self.register(report)
        portrait = coverage.assess(self.p, view='portrait', details=True)
        self.assertTrue(portrait['ready'])
        self.assertFalse(coverage.assess(self.p, view='landscape')['ready'])
        scene_path = self.p/'scene/scene.json'; scene = studio.read(scene_path)
        scene['title'] = 'Changed input'; studio.write(scene_path, scene)
        stale = coverage.assess(self.p, view='portrait', details=True)
        self.assertFalse(stale['ready']); self.assertIn('Stale plan/expectation', str(stale['blocked']))
        source = self.p/'assets/source.png'; source.write_bytes(source.read_bytes()+b'changed')
        changed = coverage.assess(self.p, details=True)
        self.assertEqual(changed['assessment']['components']['plan']['state'], 'available')
        self.assertEqual(changed['assessment']['components']['plan_dependencies']['state'], 'unknown')
        self.assertTrue(any(row['ready'] is None for row in changed['expectations']))

    def test_changed_during_assessment_invalidates_results_and_reused_inputs(self):
        from ambiance_studio.coverage_context import AssessmentInputs
        inputs = AssessmentInputs(self.p)
        inputs.get('plan'); inputs.get('pipeline')
        original = studio.read(self.p/plan.PATH)
        changed = copy.deepcopy(original); changed['story']['premise'] = 'Concurrent intent'
        studio.write(self.p/plan.PATH, changed)
        result = coverage.assess(self.p, 'layout', assessment=inputs, details=True)
        self.assertFalse(result['ready']); self.assertFalse(result['assessment']['complete'])
        self.assertEqual(result['fulfilled'], [])
        self.assertTrue(all(row['ready'] is None for row in result['expectations']))
        self.assertTrue(result['assessment']['changed_inputs'])
        self.assertEqual(inputs.finish(['pipeline'])['components']['pipeline']['state'], 'available')
        with self.assertRaisesRegex(ValueError, 'different project/revision'):
            coverage.assess(self.p, revision='missing', assessment=inputs)
        # A previously absent file appearing is a change, too.
        path = self.p/'plans/asset-inventory.json'; raw = path.read_bytes(); path.unlink()
        inputs = AssessmentInputs(self.p); self.assertIsNone(inputs.get('inventory'))
        path.write_bytes(raw)
        self.assertTrue(inputs.finish()['changed_inputs'])

    def synthetic_movie_cache(self):
        """Typed local cache fixture tests routing/identity, never codec quality."""
        from ambiance_studio import deliveries
        self.capture()
        movie = self.p/'synthetic.mp4'; movie.write_bytes(b'\x00\x00\x00\x18ftypisom' + b'synthetic record fixture' * 20)
        verification = self.p/'synthetic-verification.json'
        report = {'ok': True, 'fully_decoded': True, 'input_unchanged': True,
                  'input_sha256': studio.digest(movie), 'input_sha256_after': studio.digest(movie),
                  'width': 90, 'height': 160, 'fps': 6, 'decoded_frames': 6, 'loop_frames': 6,
                  'duration_seconds': 1, 'audio': {'tracks': 0}, 'synthetic_test_fixture': True}
        studio.write(verification, report)
        path = revisions.edition_path(self.p, 'v1', 'synthetic')
        receipt = revisions.seal({'format': revisions.EDITION, 'schema_version': 2, 'id': 'synthetic', 'revision': 'v1',
            'revision_sha256': studio.digest(revisions.manifest_path(self.p, 'v1')),
            'view': revisions.captured_view(self.p, 'v1', 'portrait'),
            'output_expectations': {'width': 90, 'height': 160, 'fps': 6, 'frames': 6, 'loop_frames': 6, 'audio_tracks': 0},
            'output': {'path': movie.name, 'sha256': studio.digest(movie), 'bytes': movie.stat().st_size},
            'verification': {'path': verification.name, 'sha256': studio.digest(verification)},
            'dependencies': [{'path': p.name, 'sha256': studio.digest(p), 'bytes': p.stat().st_size} for p in [movie, verification]]})
        studio.write(path, receipt)
        key = studio.encoded_hash({'movie': receipt['output'], 'facts': deliveries.metadata(report), 'loop_frames': 6})
        cache = self.p/'.ambiance/evidence-decode'/key/'media-report.json'; studio.write(cache, report)
        coverage.register_evidence(self.p, 'movie', 'portrait', str(path.relative_to(self.p)), 'v1', 'silent')
        return cache, path

    def test_pure_cold_and_warm_movie_cache_never_builds_native_runtime(self):
        from ambiance_studio import native_media, media_verification
        cache, receipt = self.synthetic_movie_cache(); cache_bytes = cache.read_bytes()
        with patch.object(native_media, 'native_binary', side_effect=AssertionError('native build on pure read')), \
             patch.object(media_verification, 'verify_media', side_effect=AssertionError('decode on pure read')):
            before = self.snapshot()
            warm = coverage.assess(self.p, 'export', view='portrait', revision='v1', details=True)
            self.assertIn('plan.expectation.movie.portrait', warm['fulfilled'])
            self.assertEqual(before, self.snapshot())
            cache.unlink(); before = self.snapshot()
            cold = coverage.assess(self.p, 'export', view='portrait', revision='v1', details=True)
            row = next(row for row in cold['expectations'] if row['id'] == 'movie')
            self.assertIsNone(row['ready']); self.assertFalse(cold['assessment']['complete'])
            self.assertIn('Exact movie decode evidence is unavailable', str(cold['blocked']))
            self.assertEqual(before, self.snapshot())
            cache.write_bytes(cache_bytes + b' ')
            corrupt = coverage.assess(self.p, 'export', view='portrait', revision='v1', details=True)
            self.assertNotIn('plan.expectation.movie.portrait', corrupt['fulfilled'])
        # Explicit coverage still acquires a missing cache through the native owner.
        cache.unlink()
        def decode(*args, **kwargs):
            cache.parent.mkdir(parents=True, exist_ok=True); cache.write_bytes(cache_bytes)
        with patch.object(native_media, 'native_binary', return_value=Path('/synthetic-decoder')), \
             patch.object(media_verification, 'verify_media', side_effect=decode) as called:
            explicit = coverage.evaluate(self.p, 'export', view='portrait', revision='v1', details=True)
        called.assert_called_once()
        self.assertIn('plan.expectation.movie.portrait', explicit['fulfilled'])
        self.assertTrue(Path(explicit['report']).is_file())

    def test_selected_movie_identity_survives_broken_working_scene_without_writes(self):
        from ambiance_studio import deliveries, native_media
        cache, receipt = self.synthetic_movie_cache()
        poster = self.p/'poster.png'; Image.new('RGB', (90, 160), '#887744').save(poster)
        declarations = {'format': deliveries.SELECTION, 'schema_version': 2, 'id': 'selected',
                        'default': {'view': 'portrait', 'role': 'silent'},
                        'entries': [{'view': 'portrait', 'role': 'silent', 'revision': 'v1',
                                     'edition': 'synthetic', 'poster': poster.name}]}
        deliveries.register(self.p, declarations); deliveries.present(self.p, 'selected', 'Synthetic test')
        path = self.p/'scene/scene.json'; path.write_text('{broken working scene')
        before = self.snapshot()
        with patch.object(studio, 'write', side_effect=AssertionError('query write')), \
             patch.object(native_media, 'native_binary', side_effect=AssertionError('native build')):
            result = self.run_cli('project', 'overview', '--details')
        self.assertEqual(before, self.snapshot())
        self.assertFalse(result['production_readiness']['ready']); self.assertFalse(result['release_ready'])
        subjects = result['subjects']
        self.assertEqual(subjects['working']['scene_sha256'], studio.digest(path))
        self.assertEqual(subjects['selected_movie']['delivery'], 'selected')
        entry = next(iter(subjects['selected_movie']['entries'].values()))
        self.assertEqual(entry['revision'], 'v1'); self.assertEqual(entry['edition'], 'synthetic')
        self.assertNotEqual(result['production_readiness']['assessment']['subject']['scene_sha256'],
                            studio.digest(revisions.render_context(self.p, 'v1')['scene']))

    def test_persisted_report_identity_projection_and_exit_compatibility(self):
        import contextlib
        import io
        pure = coverage.assess(self.p, 'layout', details=True)
        self.assertFalse((self.p/'.ambiance/coverage').exists())
        persisted = coverage.evaluate(self.p, 'layout', details=True)
        payload = {k: value for k, value in pure.items() if k != 'assessment'}
        self.assertEqual(payload, {k: value for k, value in persisted.items() if k != 'report'})
        identity = studio.encoded_hash({k: v for k, v in persisted.items() if k not in ['report', 'expectations']})
        self.assertEqual(Path(persisted['report']).name, identity+'.json')
        before = Path(persisted['report']).read_bytes()
        compact = coverage.evaluate(self.p, 'layout')
        self.assertEqual(compact['report'], persisted['report'])
        self.assertEqual(Path(compact['report']).read_bytes(), before)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(['--project', str(self.p), 'plan', 'coverage', '--stage', 'layout']), 0)
            self.assertEqual(cli.main(['--project', str(self.p), 'plan', 'coverage']), 1)
            self.assertEqual(cli.main(['--project', str(self.p), 'project', 'overview']), 0)
        Path(persisted['report']).write_bytes(before+b'changed')
        with self.assertRaises((ValueError, json.JSONDecodeError)):
            coverage.evaluate(self.p, 'layout')

    def test_captured_inputs_isolate_stale_controls_without_working_fallback(self):
        from ambiance_studio.coverage_context import AssessmentInputs
        self.capture()
        manifest = revisions.load(self.p, 'v1')
        scene = studio.inside(self.p, manifest['controls']['scene']); scene.write_text('{changed captured scene')
        inputs = AssessmentInputs(self.p, 'v1')
        self.assertIsNotNone(inputs.get('plan')); self.assertIsNotNone(inputs.get('pipeline'))
        self.assertIsNotNone(inputs.get('inventory')); self.assertIsNone(inputs.get('scene'))
        report = coverage.assess(self.p, 'layout', revision='v1', assessment=inputs, details=True)
        self.assertFalse(report['ready']); self.assertEqual(report['revision'], 'v1')
        self.assertTrue(all(row['ready'] is None for row in report['expectations']))
        self.assertEqual(inputs.components['plan']['state'], 'available')
        self.assertTrue(coverage.assess(self.p, 'layout')['ready'])  # working is independent
        missing = coverage.assess(self.p, revision='never-captured')
        self.assertFalse(missing['ready']); self.assertEqual(missing['revision'], 'never-captured')
        self.assertIsNone(missing['plan_sha256'])

    def test_captured_dependency_integrity_remains_required_but_material_stays_readable(self):
        from ambiance_studio.coverage_context import AssessmentInputs
        selection_path = self.p/'plans/selection.json'
        selection = studio.read(selection_path)
        sound = self.p/'sound/selected-note.txt'; sound.parent.mkdir(exist_ok=True); sound.write_text('Selected sound intent')
        selection['documents'] = {'sound_plan': str(sound.relative_to(self.p))}; studio.write(selection_path, selection)
        self.capture()
        manifest = revisions.load(self.p, 'v1')
        studio.inside(self.p, manifest['controls']['sound_plan']).write_text('Changed captured sound intent')
        inputs = AssessmentInputs(self.p, 'v1')
        self.assertIsNotNone(inputs.get('plan')); self.assertIsNotNone(inputs.get('pipeline'))
        assessed = coverage.assess(self.p, 'layout', revision='v1', assessment=inputs, details=True)
        self.assertFalse(assessed['ready'])
        self.assertEqual(assessed['assessment']['components']['revision_dependencies']['state'], 'unknown')
        self.assertEqual(assessed['assessment']['components']['plan']['state'], 'available')
        self.assertFalse(coverage.evaluate(self.p, 'layout', revision='v1')['ready'])

    def test_removed_view_and_evidence_race_are_explicitly_diagnosed(self):
        report = self.proof()['report']; self.register(report)
        scene_path = self.p/'scene/scene.json'; scene = studio.read(scene_path)
        del scene['framing']['views']['landscape']; studio.write(scene_path, scene)
        missing = coverage.assess(self.p, 'layout', details=True)
        self.assertIn('plan.view-missing.landscape', [row['id'] for row in missing['blocked']])
        self.assertIsNone(next(row for row in missing['expectations'] if row['view_id'] == 'landscape')['ready'])
        # Restore exact proof inputs, then edit verified pixels before assessment finishes.
        scene = studio.read(Path(report).parent/'scene.snapshot.json'); studio.write(scene_path, scene)
        from ambiance_studio.coverage_evidence import ProviderVerifier
        frame = Path(report).parent/'portrait/00000.png'
        class EditingVerifier:
            def verify(self, request):
                result = ProviderVerifier().verify(request)
                frame.write_bytes(frame.read_bytes()+b'concurrent change')
                return result
        raced = coverage.assess(self.p, view='portrait', details=True, verifier=EditingVerifier())
        self.assertFalse(raced['ready']); self.assertEqual(raced['fulfilled'], [])
        self.assertIn('plan.inputs-changed', [row['id'] for row in raced['blocked']])
        self.assertTrue(any(row['path'] == str(frame) for row in raced['assessment']['changed_inputs']))

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
        overview = production.overview(self.p, 'fixture', 'http://localhost', details=True)['production_readiness']
        preflight = self.run_cli('iteration', 'preflight', file)
        ids = lambda r: [x['id'] for x in r['blocked']]
        self.assertEqual(ids(direct), ids(overview)); self.assertEqual(ids(direct), ids(preflight['readiness']))
        self.assertTrue(preflight['may_render']); self.assertFalse(preflight['ok'])
        recipe['scope'] = 'final'; recipe['views'] = ['portrait']; studio.write(file, recipe)
        preflight = self.run_cli('iteration', 'preflight', file)
        self.assertFalse(preflight['may_render'])
        self.assertIn('plan.output-missing.landscape.silent', ids(preflight['readiness']))

    def test_stage_view_matrix_keeps_cli_overview_and_preflight_in_parity(self):
        file = self.p/'recipe.json'; studio.write(file, self.recipe())
        report = self.proof()['report']
        ids = lambda value: [row['id'] for row in value['blocked']]
        for state in ['missing', 'recorded', 'tampered']:
            if state == 'recorded':
                for view in ['portrait', 'landscape']: self.register(report, view)
            elif state == 'tampered':
                frame = Path(report).parent/'portrait/00000.png'
                frame.write_bytes(frame.read_bytes()+b'tampered')
            for stage in ['layout', 'assets', 'animation', 'export']:
                with self.subTest(state=state, stage=stage):
                    direct = self.run_cli('plan', 'coverage', '--stage', stage, '--details')
                    overview = production.overview(self.p, 'fixture', 'http://localhost',
                        readiness_options={'stage': stage, 'details': True}, details=True)['production_readiness']
                    self.assertEqual({k: v for k, v in direct.items() if k != 'report'},
                                     {k: v for k, v in overview.items() if k != 'assessment'})
                    self.assertNotIn('report', overview)
                    pending = self.run_cli('plan', 'coverage', '--stage', stage, '--phase', 'preflight')
                    preflight = self.run_cli('iteration', 'preflight', file, '--stage', stage)['readiness']
                    self.assertEqual(pending, preflight)
                    for view in ['portrait', 'landscape']:
                        scoped = self.run_cli('plan', 'coverage', '--stage', stage, '--view', view, '--details')
                        self.assertEqual(ids(scoped), [id for id in ids(direct) if id.endswith('.'+view)])

    def test_verifier_boundary_preserves_history_reuse_and_rejects_failures(self):
        from ambiance_studio.coverage_evidence import ProviderVerifier
        from ambiance_studio.errors import CommandError
        report = Path(self.proof()['report']); calls = []
        class RecordingVerifier:
            def verify(self, request):
                calls.append(request)
                return ProviderVerifier().verify(request)
        inventory = self.p/'plans/asset-inventory.json'
        # Noncanonical whitespace is intentional: the snapshot preserves bytes.
        original = b'  '+inventory.read_bytes()+b'\n\n'; inventory.write_bytes(original)
        registered = coverage.register_evidence(self.p, 'pixels', 'portrait', str(report.relative_to(self.p)),
                                                verifier=RecordingVerifier())
        record = Path(registered['record']); saved = record.read_bytes(); index = inventory.read_bytes()
        history = list((self.p/'.ambiance/inventory-history').glob('*.json'))
        self.assertEqual(len(history), 1); self.assertEqual(history[0].read_bytes(), original)
        self.assertTrue(coverage.register_evidence(self.p, 'pixels', 'portrait', str(report.relative_to(self.p)),
                                                  verifier=RecordingVerifier())['reused'])
        self.assertEqual(record.read_bytes(), saved); self.assertEqual(inventory.read_bytes(), index)
        self.assertEqual(calls[0].project, self.p); self.assertEqual(calls[0].receipt, report)
        self.assertEqual(calls[0].expectation['id'], 'pixels'); self.assertEqual(calls[0].view, 'portrait')
        calls.clear()
        self.assertTrue(coverage.evaluate(self.p, 'layout', verifier=RecordingVerifier())['ready'])
        self.assertEqual(calls, [])
        self.assertTrue(coverage.evaluate(self.p, view='portrait', verifier=RecordingVerifier())['ready'])
        self.assertEqual(len(calls), 1)
        class FailedVerifier:
            def verify(self, request):
                raise CommandError('Injected provider decode failure', 'runtime_failed', 3)
        failed = coverage.evaluate(self.p, view='portrait', verifier=FailedVerifier())
        self.assertFalse(failed['ready']); self.assertIn('Injected provider decode failure', str(failed['blocked']))
        with self.assertRaises(CommandError):
            coverage.register_evidence(self.p, 'pixels', 'landscape', str(report.relative_to(self.p)), verifier=FailedVerifier())
        self.assertEqual(record.read_bytes(), saved); self.assertEqual(inventory.read_bytes(), index)
        self.assertEqual(len(list(record.parent.glob('*.json'))), 1)
        self.assertFalse((self.p/'.ambiance/write.lock').exists())
        calls.clear()
        changed = plan.load(self.p); changed['expectations'][1]['direction'] = 'New authored requirement'
        studio.write(self.p/plan.PATH, changed)
        stale = coverage.evaluate(self.p, view='portrait', verifier=RecordingVerifier())
        self.assertFalse(stale['ready']); self.assertIn('Stale plan/expectation', str(stale['blocked']))
        self.assertEqual(calls, [])

    def test_compatibility_exports_retain_their_dedicated_owners(self):
        from ambiance_studio import coverage_context, coverage_evidence, coverage_records
        for owner, names in [(coverage_context, ['context', 'subject', 'expectation', 'pinned', 'relative_file']),
                             (coverage_evidence, ['raster_receipt', 'movie_receipt', 'activity_receipt', 'observed_receipt', 'verify_provider']),
                             (coverage_records, ['register_evidence', 'evidence_for', 'observation_drafts', 'normalize_observations'])]:
            for name in names: self.assertIs(getattr(coverage, name), getattr(owner, name))

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
        with patch.dict(sys.modules,{'ambiance_studio.activity':provider}), \
             patch.object(sys.modules['ambiance_studio'],'activity',provider,create=True):
            self.assertEqual(coverage.activity_receipt(self.p,file,ctx,exp,'portrait')['kind'],'activity')
            for key, value in [('start_frame', 1), ('frames', 5), ('stride', 2)]:
                original = report['clock'][key]; report['clock'][key] = value
                with self.assertRaisesRegex(ValueError, 'full picture loop'):
                    coverage.activity_receipt(self.p, file, ctx, exp, 'portrait')
                report['clock'][key] = original
            exp['requirement'].update(metric='pixel_change', minimum=1, maximum=5)
            for value in [None, float('nan'), float('inf'), 0, 6]:
                row['pixel_change'] = value
                with self.assertRaisesRegex(ValueError, 'Activity metric'):
                    coverage.activity_receipt(self.p, file, ctx, exp, 'portrait')
            row['pixel_change'] = 3
            self.assertEqual(coverage.activity_receipt(self.p, file, ctx, exp, 'portrait')['kind'], 'activity')
            row['timing_target_diagnostics']=['sampled_onset_exceeds_authored_target']
            with self.assertRaisesRegex(ValueError,'timing targets'):coverage.activity_receipt(self.p,file,ctx,exp,'portrait')
            row['timing_target_diagnostics']=[];report['actions']=[{**action,'method':'wrong realization'}]
            with self.assertRaisesRegex(ValueError,'realization'):coverage.activity_receipt(self.p,file,ctx,exp,'portrait')

    @unittest.skipUnless(os.environ.get('AMBIANCE_TEST_NATIVE') == '1' and sys.platform == 'darwin', 'Requires actual native encode/decode')
    def test_native_movie_registration_decodes_once_and_rejects_changed_cache(self):
        from ambiance_studio import media_verification
        self.capture()
        self.run_cli('render', 'video', '--revision', 'v1', '--view', 'portrait', '--edition', 'native-cache',
                     '--out', self.p/'render/native-cache')
        receipt = revisions.edition_path(self.p, 'v1', 'native-cache')
        original = (self.p/'plans/asset-inventory.json').read_bytes()
        from ambiance_studio.errors import CommandError
        with patch.object(media_verification, 'verify_media', side_effect=CommandError('Injected native decoder failure')):
            with self.assertRaisesRegex(CommandError, 'native decoder failure'):
                self.run_cli('plan', 'evidence', 'movie', '--view', 'portrait', '--revision', 'v1',
                             '--role', 'silent', '--receipt', receipt.relative_to(self.p))
        self.assertEqual((self.p/'plans/asset-inventory.json').read_bytes(), original)
        self.assertFalse((self.p/'evidence/expectations').exists())
        with patch.object(media_verification, 'verify_media', wraps=media_verification.verify_media) as decode:
            registered = self.run_cli('plan', 'evidence', 'movie', '--view', 'portrait', '--revision', 'v1',
                                     '--role', 'silent', '--receipt', receipt.relative_to(self.p))
            self.assertEqual(decode.call_count, 1)
            record = Path(registered['record']); saved = record.read_bytes()
            cached = list((self.p/'.ambiance/evidence-decode').glob('*/media-report.json'))
            self.assertEqual(len(cached), 1)
            report = studio.read(cached[0])
            self.assertTrue(report['fully_decoded']); self.assertTrue(report['input_unchanged'])
            for _ in range(2):
                state = self.run_cli('plan', 'coverage', '--stage', 'export', '--revision', 'v1', '--view', 'portrait', '--details')
                self.assertIn('plan.expectation.movie.portrait', state['fulfilled'])
            self.assertEqual(decode.call_count, 1)
            reused = self.run_cli('plan', 'evidence', 'movie', '--view', 'portrait', '--revision', 'v1',
                                 '--role', 'silent', '--receipt', receipt.relative_to(self.p))
            self.assertTrue(reused['reused']); self.assertEqual(record.read_bytes(), saved)
            with self.assertRaisesRegex(ValueError, 'soundtrack'):
                self.run_cli('plan', 'evidence', 'movie', '--view', 'portrait', '--revision', 'v1',
                             '--role', 'score', '--receipt', receipt.relative_to(self.p))
            history = list((self.p/'.ambiance/inventory-history').glob('*.json'))
            self.assertEqual(len(history), 1); self.assertEqual(history[0].read_bytes(), original)
            # Even a semantically harmless cache edit must break the sealed identity.
            report['extra'] = 'altered'; studio.write(cached[0], report)
            state = self.run_cli('plan', 'coverage', '--stage', 'export', '--revision', 'v1', '--view', 'portrait', '--details')
            gap = next(r for r in state['blocked'] if r['id'] == 'plan.expectation.movie.portrait')
            self.assertIn('Evidence artifact identity changed', str(gap))
            self.assertEqual(decode.call_count, 1)
            # Preflight defers encoded evidence and must not consume the bad cache.
            pending = self.run_cli('plan', 'coverage', '--stage', 'export', '--phase', 'preflight', '--revision', 'v1', '--view', 'portrait')
            self.assertIn('plan.expectation.movie.portrait', pending['future_outputs'])

    @unittest.skipUnless(os.environ.get('AMBIANCE_TEST_NATIVE') == '1' and sys.platform == 'darwin', 'Requires actual native encode/decode')
    def test_small_review_movie_is_presented_without_claiming_final_evidence(self):
        self.capture(); recipe = self.recipe(); recipe['long_edge'] = 128
        result = production.iteration(self.p, recipe, 'Synthetic small review fixture')
        self.assertTrue(result['ok'])
        self.assertFalse(result['production_readiness']['ready'])
        self.assertEqual(len(result['production_readiness']['evidence_registration_gaps']), 2)
        from ambiance_studio import deliveries
        self.assertEqual(deliveries.latest(self.p)['delivery']['id'], recipe['id'])
        self.assertFalse(deliveries.inspect(self.p, recipe['id'])['production_scope']['ready'])

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
