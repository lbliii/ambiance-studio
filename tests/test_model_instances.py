"""Instance transactions: independent state, pins, recovery and real pixels."""
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import studio
from ambiance_studio import cli, model_instances, model_package
from ambiance_studio.file_identity import digest
from ambiance_studio.errors import CommandError
from ambiance_studio.project import locations

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('instance_fixture', ROOT/'examples/model-instances/create_fixture.py')
fixture = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixture)


def invoke(*argv):
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream): code = cli.main(list(map(str, argv)))
    return code, json.loads(stream.getvalue())


class InstanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(); cls.base = Path(cls.temp.name)
        cls.source = fixture.model_source(cls.base/'source'); cls.package = cls.base/'package'
        model_package.build(cls.source/'models/lantern.json', cls.source, cls.package)
        second = cls.base/'source-v2'; shutil.copytree(cls.source, second)
        path = second/'models/lantern.json'; definition = studio.read(path)
        definition.update(version='2', name='Lantern label revision')
        studio.write(path, definition); cls.package2 = cls.base/'package-v2'
        model_package.build(path, second, cls.package2)

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def setUp(self):
        self.temp_case = tempfile.TemporaryDirectory(dir=self.base); self.work = Path(self.temp_case.name)
        self.addCleanup(self.temp_case.cleanup); self.project = fixture.create(self.work/'project')

    def command(self, *argv, code=0):
        actual, result = invoke('--project', self.project, *argv)
        self.assertEqual(actual, code, result)
        return result.get('data', result)

    def scene(self): return studio.read(locations(self.project)[0])

    def recipe(self, operations, name='operations.json'):
        path = self.work/name
        studio.write(path, {'format': model_instances.RECIPE, 'schema_version': 1,
            'expected_scene_sha256': digest(locations(self.project)[0]), 'operations': operations})
        return path

    def place(self, name='a', x=60, receivers=False):
        op = {'op': 'place', 'instance_id': name, 'package': str(self.package),
              'package_sha256': digest(self.package/'model-package.json'),
              'placement': {'position': [x, 100], 'scale': 1.5, 'rotation': 0, 'depth': 0}}
        if receivers:
            op['receivers'] = [{'id': 'floor', 'source_part_path': ['candle', 'flame'], 'illumination': 'a-floor',
                               'values': [.4, .7, 1, .6], 'valid_bounds': [20, 60, 110, 120]}]
        return op

    def update(self, name='a', **values):
        r = next(r for r in self.scene()['model_instances']['instances'] if r['instance_id'] == name)
        return {'op': 'update', 'instance_id': name, 'expected_pin': r['pin'], 'expected_managed_sha256': r['managed_sha256'], **values}

    def save(self, ops): return self.command('model', 'instance', 'apply', self.recipe(ops))

    def test_two_instances_dry_save_retry_and_portable_reopen(self):
        original = (self.project/'ambiance-project.json').read_bytes()
        recipe = self.recipe([self.place(), self.place('b', 180)])
        dry = self.command('model', 'instance', 'apply', recipe, '--dry-run')
        self.assertEqual((self.project/'ambiance-project.json').read_bytes(), original)
        self.assertFalse((self.project/'.ambiance/model-generations').exists())
        saved = self.command('model', 'instance', 'apply', recipe)
        self.assertEqual(dry['scene'], self.scene())
        self.assertNotEqual(locations(self.project)[0], self.project/'scene/scene.json')
        self.command('model', 'instance', 'apply', recipe, code=2)
        self.command('model', 'instance', 'apply', self.recipe([self.place()]), code=2)
        records = self.command('model', 'instance', 'inspect')['instances']
        self.assertEqual(len(records), 2)
        self.assertTrue(set(r['layer_id'] for r in records[0]['mapping']).isdisjoint(r['layer_id'] for r in records[1]['mapping']))
        portable = self.work/'portable'; shutil.copytree(self.project, portable)
        actual, result = invoke('--project', portable, 'model', 'instance', 'inspect')
        self.assertEqual(actual, 0, result)
        self.assertEqual(records, result['data']['instances'])

    def test_late_invalid_mount_and_materialization_interrupt_leave_pointer_intact(self):
        before = {p.name: p.read_bytes() for p in [self.project/'ambiance-project.json', *locations(self.project)]}
        op = self.place('b', 180); op['mount'] = {'layer': 'missing', 'socket': 'missing', 'at_seconds': 0}
        self.command('model', 'instance', 'apply', self.recipe([self.place(), op]), code=2)
        self.assertFalse((self.project/'.ambiance/model-generations').exists())
        recipe = self.recipe([self.place()])
        with patch('ambiance_studio.model_package.copy_files', side_effect=KeyboardInterrupt):
            self.command('model', 'instance', 'apply', recipe, code=130)
        for p in [self.project/'ambiance-project.json', *locations(self.project)]: self.assertEqual(p.read_bytes(), before[p.name])
        self.assertEqual(list((self.project/'.ambiance/model-generations').iterdir()), [])

    def test_ordinary_edit_restore_and_independent_move_variant_hide(self):
        original = self.scene()
        self.save([self.place(receivers=True), self.place('b', 180)])
        scene = self.scene(); b = scene['model_instances']['instances'][1]
        before = {l['id']: l for l in scene['layers'] if l['id'] in {r['layer_id'] for r in b['mapping']}}
        self.save([self.update(placement={'position': [80, 100], 'scale': 1.3, 'rotation': .12, 'depth': 0},
            state={'schema_version': 1, 'pose_id': 'arched', 'controls': [], 'variants': [{'model_path': [], 'variant_set_id': 'frame', 'variant_id': 'arched'}]})])
        self.assertEqual(before, {l['id']: l for l in self.scene()['layers'] if l['id'] in before})
        self.assertEqual(self.scene()['bindings']['links'][0], original['bindings']['links'][0])
        hidden = {'schema_version': 1, 'pose_id': 'hidden', 'controls': [{'model_path': [], 'control_id': 'visible', 'value': False}], 'variants': []}
        self.save([self.update(state=hidden)])
        sample = self.command('scene', 'sample', '--time', 0)
        self.assertEqual(next(s['opacity'] for s in sample if s['id'] == 'ground-a-light'), 0)
        self.assertGreater(next(s['opacity'] for s in sample if s['id'] == 'unrelated-light'), 0)
        prior = digest(locations(self.project)[0])
        self.command('scene', 'set', 'unrelated-light', '--x', .3)
        self.command('scene', 'restore', prior)
        self.assertEqual(digest(locations(self.project)[0]), prior)
        self.command('model', 'instance', 'inspect')

    def test_mount_uses_real_reparent_and_preserves_all_corners(self):
        self.save([self.place()])
        result = self.save([self.update(mount={'layer': 'ground', 'socket': 'light', 'at_seconds': 0})])
        self.assertLess(result['previews'][0]['mount']['max_world_corner_error_pixels'], 1e-7)
        self.command('model', 'instance', 'inspect')

    def test_project_root_checker_legacy_generation_and_escape(self):
        from kit import validate
        self.assertTrue(validate(*locations(self.project))['ok'])
        self.save([self.place()]); self.command('scene', 'check')
        scene_path, catalog_path = locations(self.project)
        self.assertTrue(validate(scene_path, catalog_path, project_root=self.project)['ok'])
        catalog = studio.read(catalog_path); catalog['assets'][0]['file'] = '../outside.png'
        shutil.copyfile(self.project/'assets/ground.png', self.work/'outside.png')
        studio.write(catalog_path, catalog)
        failed = self.command('scene', 'check', code=1)
        self.assertFalse(failed['ok'])
        self.assertTrue(any('outside' in e for e in failed['integrity']['errors']))

    def test_changed_input_at_materialization_cannot_select_partial_bundle(self):
        before = (self.project/'ambiance-project.json').read_bytes()
        original = model_package.copy_files
        def changed(*args):
            original(*args)
            scene = self.scene(); scene['title'] = 'Concurrent direct edit'
            studio.write(locations(self.project)[0], scene)
        with patch('ambiance_studio.model_package.copy_files', side_effect=changed):
            self.command('model', 'instance', 'apply', self.recipe([self.place()]), code=2)
        self.assertEqual((self.project/'ambiance-project.json').read_bytes(), before)
        self.assertEqual(self.scene()['title'], 'Concurrent direct edit')
        self.assertNotIn('model_instances', self.scene())

    def test_raster_provider_pixels_and_revision_model_edges(self):
        from PIL import Image, ImageChops
        from ambiance_studio import model_evidence, coverage_evidence, revision_dependencies
        self.save([self.place(receivers=True), self.place('b', 180)])
        before = self.project/'render/before'
        self.command('render', 'frame', '--view', 'authored', '--out', before)
        report = studio.read(before/'render-report.json')
        wrapper = self.project/'evidence/model.json'
        self.command('model', 'instance', 'evidence', '--receipt', before/'render-report.json', '--instance', 'a', '--instance', 'b', '--out', wrapper)
        ctx = {'scene_sha256': report['scene_sha256'], 'catalog_sha256': report['catalog_sha256'], 'revision': None,
               'views': {'authored': report['view']}, 'asset_references': []}
        verified = coverage_evidence.verify_provider(self.project, wrapper, ctx, {'requirement': {'check': 'raster'}}, 'authored')
        self.assertEqual(verified['kind'], 'model-raster')
        config = studio.read(self.project/'ambiance-project.json')
        selection = {'format': revision_dependencies.SELECTION, 'schema_version': 1, 'scene': config['scene'], 'catalog': config['catalog']}
        collector = revision_dependencies.collect(self.project, selection)
        self.assertIn('model_definition', {r['role'] for r in collector.refs})
        self.assertIn('model_source', {r['role'] for r in collector.refs})
        selection_path = self.project/'selection.json'; studio.write(selection_path, selection)
        self.command('revision', 'capture', 'before', '--selection', selection_path)
        op = self.update(state={'schema_version': 1, 'pose_id': 'hidden', 'controls': [{'model_path': [], 'control_id': 'visible', 'value': False}], 'variants': []})
        self.save([op]); after = self.project/'render/hidden'
        self.command('render', 'frame', '--view', 'authored', '--out', after)
        new_report = studio.read(after/'render-report.json')
        with self.assertRaisesRegex(ValueError, 'different scene'):
            coverage_evidence.verify_provider(self.project, wrapper, {**ctx, 'scene_sha256': new_report['scene_sha256']}, {'requirement': {'check': 'raster'}}, 'authored')
        with Image.open(report['output']) as a, Image.open(new_report['output']) as b:
            self.assertIsNotNone(ImageChops.difference(a.convert('RGB'), b.convert('RGB')).getbbox())
            self.assertIsNone(ImageChops.difference(a.crop((130, 0, 240, 160)), b.crop((130, 0, 240, 160))).getbbox())
        # The captured old revision renders its unchanged instance/pins after edits.
        self.command('render', 'frame', '--revision', 'before', '--view', 'authored', '--out', self.project/'render/captured')

    def test_adoption_old_pin_reset_and_restore(self):
        op = self.place(); op['state'] = {'schema_version': 1, 'pose_id': 'tilt', 'controls': [{'model_path': [], 'control_id': 'sway', 'value': .1}], 'variants': []}
        self.save([op]); before = self.scene(); old_hash = digest(locations(self.project)[0])
        adopt = self.update(); adopt.update(op='adopt', package=str(self.package2), package_sha256=digest(self.package2/'model-package.json'), reset_controls=[{'model_path': [], 'control_id': 'sway'}])
        recipe = self.recipe([adopt]); dry = self.command('model', 'instance', 'apply', recipe, '--dry-run')
        self.assertEqual(len(dry['previews'][0]['adoption']['reset']), 1)
        self.command('model', 'instance', 'apply', recipe)
        self.assertEqual(self.scene()['model_instances']['instances'][0]['pin']['definition']['version'], '2')
        self.command('scene', 'restore', old_hash)
        self.assertEqual(self.scene(), before)
        self.command('model', 'instance', 'inspect')

    def test_drift_stale_pin_and_outside_receiver_envelope_reject(self):
        self.save([self.place(receivers=True)])
        self.command('model', 'instance', 'apply', self.recipe([self.update(placement={'position': [120, 100], 'scale': 1, 'rotation': 0, 'depth': 0})]), code=2)
        op = self.update(); op['expected_pin']['sha256'] = '0'*64
        self.command('model', 'instance', 'apply', self.recipe([op]), code=2)
        op = self.update(); scene = self.scene(); scene['layers'][3]['x'] += .01; studio.write(locations(self.project)[0], scene)
        self.command('model', 'instance', 'apply', self.recipe([op]), code=2)

    def test_changed_socket_drawing_and_nested_dependency_interfaces_conflict(self):
        self.save([self.place()])
        for case in ['socket', 'drawing', 'dependency']:
            with self.subTest(case=case):
                source = self.work/case; shutil.copytree(self.source, source)
                path = source/'models/lantern.json'; d = studio.read(path); d['version'] = '2'
                if case == 'socket': d['sockets'][2]['cell_uv'][0] += .1
                elif case == 'drawing': d['drawings'][0]['drawing_id'] = 'renamed'; d['parts'][0]['drawing_id'] = 'renamed'
                else:
                    child = source/'models/candle.json'; c = studio.read(child); c['version'] = '2'; studio.write(child, c)
                    next(p['definition'] for p in d['parts'] if 'definition' in p).update(version='2', sha256=digest(child))
                studio.write(path, d); package = self.work/(case+'-package'); model_package.build(path, source, package)
                op = self.update(); op.update(op='adopt', package=str(package), package_sha256=digest(package/'model-package.json'))
                recipe = self.recipe([op]); dry = self.command('model', 'instance', 'apply', recipe, '--dry-run')
                self.assertFalse(dry['applicable']); self.assertTrue(dry['previews'][0]['adoption']['conflicts'])
                self.command('model', 'instance', 'apply', recipe, code=2)

    def test_recomputed_fingerprint_cannot_disguise_swapped_mapping_or_pack(self):
        from ambiance_studio.model_evidence import model_references
        from ambiance_studio.revision_dependencies import Collector
        self.save([self.place(receivers=True)]); original_scene = self.scene(); catalog_path = locations(self.project)[1]
        original_catalog = studio.read(catalog_path)
        for case in ['mapping', 'pack', 'signal', 'binding', 'ordinary-alias']:
            with self.subTest(case=case):
                scene, catalog = copy.deepcopy(original_scene), copy.deepcopy(original_catalog)
                record = scene['model_instances']['instances'][0]
                if case == 'mapping': record['mapping'][0]['drawing_id'] = 'frame-arched'
                elif case == 'pack':
                    id = record['mapping'][-1]['asset_id']
                    asset = next(a for a in catalog['assets'] if a['id'] == id)
                    source = next(a for a in catalog['assets'] if a['id'] == record['mapping'][0]['asset_id'])
                    asset.update({**source, 'id': id})
                elif case == 'signal':
                    scene['finishing']['signals'][-1]['values'] = [1, 1, 1, 1]
                elif case == 'binding':
                    scene['bindings']['links'][-1]['map']['keys'][-1][1] = .5
                else:
                    asset = copy.deepcopy(next(a for a in catalog['assets'] if a['id'] == record['mapping'][0]['asset_id']))
                    asset['id'] = 'ordinary-unverified-alias'
                    with self.assertRaisesRegex(ValueError, 'id mismatch'): Collector(self.project).asset(asset)
                    continue
                record['managed_sha256'] = model_instances.fingerprint(scene, catalog, record)
                with self.assertRaises((ValueError, CommandError)):
                    model_references(self.project, scene, catalog)
                studio.write(locations(self.project)[0], scene); studio.write(catalog_path, catalog)
                op = {'op': 'adopt', 'instance_id': 'a', 'expected_pin': record['pin'], 'expected_managed_sha256': record['managed_sha256'],
                      'package': str(self.package2), 'package_sha256': digest(self.package2/'model-package.json')}
                self.command('model', 'instance', 'apply', self.recipe([op]), code=2)
                studio.write(locations(self.project)[0], original_scene); studio.write(catalog_path, original_catalog)


if __name__ == '__main__': unittest.main()
