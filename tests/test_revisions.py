"""Revision freshness fixtures; synthetic observations never approve a film."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PIL import Image
import studio
from ambiance_studio import revisions
from ambiance_studio.cli import init_project, parser, run, main


class RevisionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.p = self.root/'film'
        source = self.root/'ref.png'; Image.new('RGB', (12, 20), '#58477a').save(source)
        init_project(self.p, source, 'Independent revision fixture', 'blank')
        self.art = self.p/'assets/paint.png'; Image.new('RGBA', (12, 20), '#ab874a').save(self.art)
        catalog = {'version': 1, 'assets': [{'id': 'paint', 'kind': 'plate', 'file': 'assets/paint.png', 'width': 12, 'height': 20, 'sha256': studio.digest(self.art)}]}
        studio.write(self.p/'assets/catalog.json', catalog)
        run(parser().parse_args(['--project', str(self.p), 'scene', 'add', 'paint', '--id', 'base', '--width', '1']))
        for name in ['source', 'master']:
            with wave.open(str(self.p/f'audio/{name}.wav'), 'wb') as f:
                f.setnchannels(2); f.setsampwidth(2); f.setframerate(48000); f.writeframes(b'\x01\x00\x01\x00'*4800)
        (self.p/'audio/process.txt').write_text('Synthetic fixture identity: copy the source PCM unchanged. No external processing executed.\n')
        prep = {'format': revisions.PREPARATION, 'schema_version': 1,
                'sources': [self.audio_ref('source.wav')], 'recipes': [self.audio_ref('process.txt')], 'outputs': [self.audio_ref('master.wav')]}
        studio.write(self.p/'audio/preparation.json', prep)
        self.selection = {'format': revisions.SELECTION, 'schema_version': 1, 'scene': 'scene/scene.json', 'catalog': 'assets/catalog.json',
                          'documents': {'brief': 'plans/brief.md', 'layer_plan': 'plans/layer-plan.json', 'sound_plan': 'plans/sound-brief.md'},
                          'audio': {'preparations': ['audio/preparation.json'], 'masters': ['audio/master.wav']}}
        self.selection_path = self.p/'selection.json'; studio.write(self.selection_path, self.selection)
        (self.p/'plans/evidence.txt').write_text('Synthetic evidence for receipt behavior only.\n')

    def audio_ref(self, name): return {'path': 'audio/'+name, 'sha256': studio.digest(self.p/'audio'/name)}
    def capture(self, id='v1'): return revisions.capture(self.p, id, self.selection_path)
    def record(self, gate, edition=None, verdict='pass'):
        context = revisions.review_context(self.p, 'v1', edition)
        draft = studio.review_template(self.p, gate, context); draft['verdict'] = verdict; draft['recorder'] = 'Synthetic fixture'
        for check in draft['checks']:
            check.update(result='pass', observed_by={'kind': 'agent', 'name': 'Synthetic fixture'}, note='Synthetic observation for freshness tests.', evidence=['plans/evidence.txt'])
        file = self.p/'review-drafts'/f'{gate}.json'; studio.write(file, draft)
        return studio.record_review(self.p, file, context)
    def pass_through_mix(self):
        for gate in ['intent', 'layout', 'assets', 'animation', 'sound-design', 'mix']: self.record(gate)

    def synthetic_edition(self, id):
        # Unit-test the receipt boundary; native integration independently decodes real media.
        out = self.p/'reports'/id
        args = parser().parse_args(['--project', str(self.p), 'render', 'video', '--revision', 'v1', '--edition', id,
                                    '--audio', str(self.p/'audio/master.wav'), '--out', str(out)])
        prepared = revisions.prepare_edition(self.p, args); out.mkdir()
        (out/'picture.mp4').write_bytes(b'Synthetic picture identity fixture; not encoded media.')
        (out/'output.mp4').write_bytes(b'Synthetic movie identity fixture; not encoded media: '+id.encode())
        report = out/'verification.json'; studio.write(report, {'synthetic': True, 'note': 'No actual decode claimed by this unit fixture'})
        result = {'ok': True, 'output': str(out/'output.mp4'), 'output_sha256': studio.digest(out/'output.mp4'), 'verification': {'ok': True, 'report': str(report)}}
        revisions.record_edition(self.p, prepared, result, args)
        return out

    def test_capture_freezes_controls_and_ignores_new_working_drafts(self):
        result = self.capture(); self.assertEqual(result['review'], 'not-recorded')
        original = revisions.render_context(self.p, 'v1')['scene'].read_bytes()
        scene = studio.read(self.p/'scene/scene.json'); scene['layers'][0]['x'] = .25; studio.write(self.p/'scene/scene.json', scene)
        (self.p/'assets/rejected.txt').write_text('unselected')
        self.assertTrue(revisions.check(self.p, 'v1')['ok'])
        self.assertTrue(revisions.compare(self.p, 'v1')['working_diverged'])
        self.assertEqual(revisions.render_context(self.p, 'v1')['scene'].read_bytes(), original)
        with self.assertRaisesRegex(ValueError, 'exists'): self.capture()

    def test_capture_selection_digest_and_concurrent_change_fail_without_promotion(self):
        preview = revisions.capture(self.p, 'v1', self.selection_path, True)
        self.assertFalse((self.p/'revisions/v1').exists())
        (self.p/'plans/brief.md').write_text('new brief')
        with self.assertRaisesRegex(ValueError, 'changed since dry run'):
            revisions.capture(self.p, 'v1', self.selection_path, expected=preview['selection_sha256'])
        real = revisions.collect
        def racing(project, selection):
            c = real(project, selection); (project/'plans/brief.md').write_text('changed during collect'); return c
        with patch.object(revisions, 'collect', side_effect=racing), self.assertRaisesRegex(ValueError, 'Inputs changed'):
            self.capture()
        self.assertFalse((self.p/'revisions/v1').exists())

    def test_capture_validates_the_exact_scene_bytes_it_snapshots(self):
        from ambiance_studio import cli
        original = cli.scene_bridge
        def mutate_after_validation(*args, **kwargs):
            result = original(*args, **kwargs)
            scene = studio.read(self.p/'scene/scene.json'); scene['canvas']['fps'] = 0; studio.write(self.p/'scene/scene.json', scene)
            return result
        with patch.object(cli, 'scene_bridge', side_effect=mutate_after_validation), self.assertRaisesRegex(ValueError, 'Inputs changed'):
            self.capture()
        self.assertFalse((self.p/'revisions/v1').exists())

    def test_compiler_mapping_cannot_be_relabelled_only_in_catalog(self):
        from tools import asset_tool
        recipe = {'version': 1, 'id': 'compiled', 'input': {'frames': ['paint.png'], 'allow_opaque': True},
                  'registration': {'mode': 'fixed', 'point': [6, 10], 'target': [.5, .5]},
                  'output': {'cell_size': [16, 24], 'columns': 1, 'padding': 2}}
        path = self.p/'assets/recipe.json'; studio.write(path, recipe)
        pack = self.p/'assets/compiled/test'; asset_tool.build(path, pack); asset_tool.admit(pack, self.p/'assets/catalog.json')
        scene = studio.read(self.p/'scene/scene.json'); scene['layers'][0]['asset'] = 'compiled'; scene['layers'][0]['cycle_seconds'] = 16
        scene['layers'][0]['phase_frames'] = 0
        studio.write(self.p/'scene/scene.json', scene)
        catalog = studio.read(self.p/'assets/catalog.json'); item = next(a for a in catalog['assets'] if a['id'] == 'compiled')
        item['registration_mapping']['input_sources'][0]['file'] = 'different.png'; studio.write(self.p/'assets/catalog.json', catalog)
        with self.assertRaisesRegex(ValueError, 'registration_mapping mismatch'): self.capture()

    def test_image_change_stales_picture_and_preserves_independent_sound(self):
        self.capture(); self.pass_through_mix()
        self.art.write_bytes(b'changed image')
        states = revisions.status(self.p, 'v1')['gates']
        self.assertEqual(states['assets']['state'], 'stale')
        self.assertIn('assets/paint.png', ' '.join(states['assets']['reasons']))
        self.assertEqual(states['sound-design']['state'], 'passed')
        self.assertNotEqual(states['mix']['state'], 'passed')
        with self.assertRaisesRegex(ValueError, 'integrity failed'): revisions.render_context(self.p, 'v1')

    def test_wav_change_detected_when_recipe_and_reports_unchanged(self):
        self.capture(); self.pass_through_mix()
        before = (self.p/'audio/preparation.json').read_bytes()
        with (self.p/'audio/master.wav').open('ab') as f: f.write(b'changed')
        states = revisions.status(self.p, 'v1')['gates']
        self.assertEqual(states['mix']['state'], 'stale')
        self.assertIn('audio/master.wav', ' '.join(states['mix']['reasons']))
        self.assertEqual(before, (self.p/'audio/preparation.json').read_bytes())
        self.assertEqual(states['sound-design']['state'], 'passed')

    def test_captured_scene_manifest_and_pipeline_changes_are_detected(self):
        self.capture(); self.pass_through_mix()
        context = revisions.render_context(self.p, 'v1')
        original = context['scene'].read_bytes(); context['scene'].write_bytes(original+b' ')
        self.assertEqual(revisions.status(self.p, 'v1')['gates']['animation']['state'], 'stale')
        context['scene'].write_bytes(original)
        pipeline = studio.read(self.p/'pipeline.json'); pipeline['gates'][0]['name'] = 'New working criteria'; studio.write(self.p/'pipeline.json', pipeline)
        self.assertEqual(revisions.status(self.p, 'v1')['gates']['intent']['state'], 'passed')
        manifest = revisions.manifest_path(self.p, 'v1'); data = studio.read(manifest); data['id'] = 'tampered'; studio.write(manifest, data)
        self.assertFalse(revisions.check(self.p, 'v1')['ok'])
        self.assertFalse(revisions.project_status(self.p)['revisions'][0]['integrity']['ok'])

    def test_legacy_reviews_not_migrated_and_edition_needs_its_own_evidence(self):
        draft = studio.review_template(self.p, 'intent'); draft['recorder'] = 'Legacy synthetic fixture'
        path = self.p/'review-drafts/legacy.json'; studio.write(path, draft); studio.record_review(self.p, path)
        legacy = (self.p/'reviews/intent.json').read_bytes()
        self.capture(); self.assertEqual(revisions.status(self.p, 'v1')['gates']['intent']['state'], 'pending')
        self.assertEqual(legacy, (self.p/'reviews/intent.json').read_bytes())
        self.pass_through_mix(); self.assertEqual(revisions.status(self.p, 'v1')['gates']['export']['state'], 'blocked')
        self.assertFalse(revisions.status(self.p, 'v1')['release_ready'])

    def test_bad_paths_missing_sources_and_unknown_contracts_fail(self):
        for edit in [dict(scene='../escape.json'), dict(audio={'runs': ['audio/missing']}), dict(schema_version=99)]:
            studio.write(self.selection_path, {**self.selection, **edit})
            with self.assertRaises((ValueError, OSError)): self.capture()
            self.assertFalse((self.p/'revisions/v1').exists())

    def test_master_without_processing_record_cannot_pass_mix(self):
        self.selection['audio'] = {'masters': ['audio/master.wav']}; studio.write(self.selection_path, self.selection)
        self.capture(); result = revisions.status(self.p, 'v1')
        self.assertTrue(any('dependency record' in reason for reason in result['gates']['mix']['reasons']))

    def test_editions_have_separate_output_freshness_and_exact_human_membership(self):
        self.capture(); a = self.synthetic_edition('a'); b = self.synthetic_edition('b')
        self.assertEqual(revisions.load_edition(self.p, 'v1', 'a')['picture']['sha256'], revisions.load_edition(self.p, 'v1', 'b')['picture']['sha256'])
        for gate in ['intent', 'layout', 'assets', 'animation', 'sound-design', 'mix', 'export']:
            self.record(gate, 'a'); self.record(gate, 'b')
        context = revisions.review_context(self.p, 'v1', 'a')
        d = studio.review_template(self.p, 'release', context); d['recorder'] = 'Synthetic observer'; d['verdict'] = 'pass'
        (self.p/'feedback/fixture.txt').write_text('Synthetic unit-test feedback only; nobody reviewed any film.')
        for check in d['checks']:
            check.update(result='pass', observed_by={'kind': 'human', 'name': 'Synthetic observer'}, note='Synthetic unit case.',
                         evidence=['feedback/fixture.txt', str((b/'output.mp4').relative_to(self.p))])
        file = self.p/'review-drafts/exact.json'; studio.write(file, d)
        with self.assertRaisesRegex(ValueError, 'exact selected edition'): studio.record_review(self.p, file, context)
        a.joinpath('output.mp4').write_bytes(b'changed while all descriptive reports remain untouched')
        self.assertEqual(revisions.status(self.p, 'v1', 'a')['gates']['export']['state'], 'stale')
        self.assertEqual(revisions.status(self.p, 'v1', 'b')['gates']['export']['state'], 'passed')

    def test_compose_cannot_relabel_unbound_picture_as_selected_revision(self):
        self.capture(); picture = self.p/'reports/older-picture.mp4'; picture.write_bytes(b'older picture')
        args = parser().parse_args(['--project', str(self.p), 'media', 'compose', str(picture), '--revision', 'v1', '--edition', 'bad',
                                    '--audio', str(self.p/'audio/master.wav'), '--out', str(self.p/'reports/bad')])
        with self.assertRaisesRegex(ValueError, 'not bound'): revisions.prepare_edition(self.p, args)
        receipt = self.p/'reports/old-render.json'; studio.write(receipt, {'ok': True, 'mode': 'video', 'scene_sha256': '0'*64})
        args.picture_receipt = str(receipt.relative_to(self.p))
        with self.assertRaisesRegex(ValueError, 'different captured scene'): revisions.prepare_edition(self.p, args)

    def test_edition_rechecks_media_inputs_before_registering(self):
        self.capture(); out = self.p/'reports/changed-edition'
        args = parser().parse_args(['--project', str(self.p), 'render', 'video', '--revision', 'v1', '--edition', 'changed',
                                    '--audio', str(self.p/'audio/master.wav'), '--out', str(out)])
        prepared = revisions.prepare_edition(self.p, args)
        with (self.p/'audio/master.wav').open('ab') as f: f.write(b'changed')
        with self.assertRaisesRegex(ValueError, 'changed during media'): revisions.record_edition(self.p, prepared, {'ok': True}, args)
        self.assertFalse(revisions.edition_path(self.p, 'v1', 'changed').exists())

    def test_cli_draft_status_handoff_and_nonzero_bad_check(self):
        self.capture(); output = io.StringIO()
        with contextlib.redirect_stdout(output): code = main(['--project', str(self.p), 'review', 'draft', 'intent', '--revision', 'v1', '--out', str(self.p/'draft.json')])
        self.assertEqual(code, 0, output.getvalue()); self.assertEqual(studio.read(self.p/'draft.json')['version'], 2)
        handoff = self.p/'reports/revision-handoff'; old = (self.p/'handoff.md').read_bytes()
        with contextlib.redirect_stdout(io.StringIO()): code = main(['--project', str(self.p), 'revision', 'handoff', 'v1', '--out', str(handoff)])
        self.assertEqual(code, 0); self.assertTrue((handoff/'handoff.md').exists()); self.assertEqual(old, (self.p/'handoff.md').read_bytes())
        self.art.unlink()
        with contextlib.redirect_stdout(io.StringIO()): code = main(['--project', str(self.p), 'revision', 'check', 'v1'])
        self.assertEqual(code, 1)


if __name__ == '__main__': unittest.main(verbosity=2)
