"""Placement identity checks and timing integration using independent compiled art."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ambiance_studio import scene_authoring
import kit
import studio

spec = importlib.util.spec_from_file_location('placement_fixture', ROOT/'examples/source-placement/create_fixture.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


class SceneAuthoringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template_temp = tempfile.TemporaryDirectory()
        cls.template = Path(cls.template_temp.name)/'template'
        fixture.create(cls.template)

    @classmethod
    def tearDownClass(cls):
        cls.template_temp.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)/'project'
        shutil.copytree(self.template, self.project)
        self.catalog = studio.read(self.project/'assets/catalog.json')
        self.scene = studio.read(self.project/'scene/before-reparent.json')
        self.scene['layers'] = self.scene['layers'][:1]
        self.scene['layers'][0].pop('sockets', None)
        self.manifest = studio.read(self.project/'placement.json')
        self.batch = scene_authoring.placement_batch(self.manifest)

    def bridge(self, batch):
        result = subprocess.run(['node', str(ROOT/'tools/scene-command.mjs')],
            input=json.dumps({'action': 'apply', 'scene': self.scene, 'catalog': self.catalog,
                             'args': {'batch': batch, 'report': True}}), text=True, capture_output=True)
        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0, payload)
        self.assertTrue(payload['ok'], payload)
        return payload['data']

    def test_real_mapped_compiler_outputs_resolve_and_place_without_mutating_inputs(self):
        before = copy.deepcopy((self.scene, self.catalog, self.batch))
        resolved, records = scene_authoring.resolve_batch(self.project, self.scene, self.catalog, self.batch)
        result = self.bridge(resolved)
        self.assertEqual(len(result['scene']['layers']), 5)
        self.assertEqual(len(result['operations']), 4)
        self.assertEqual((self.scene, self.catalog, self.batch), before)
        self.assertTrue(scene_authoring.verify_dependencies(self.project, records))
        roles = {role for record in records for role in record['roles']}
        self.assertIn('project configuration', roles)
        self.assertIn('placement catalog', roles)
        self.assertIn('compiler recipe body-cutout', roles)
        self.assertTrue(all(row['path_base'] == 'project' and Path(row['resolved_path']).is_absolute() for row in records))

    def test_change_after_resolution_is_detected_before_save(self):
        _, records = scene_authoring.resolve_batch(self.project, self.scene, self.catalog, self.batch)
        selected = self.project/'assets/source/reference.png'
        selected.write_bytes(selected.read_bytes()+b'changed')
        with self.assertRaisesRegex(ValueError, 'changed before save'):
            scene_authoring.verify_dependencies(self.project, records)

    def test_stale_reference_wrong_dimensions_and_escape_fail(self):
        for change, message in [({'sha256': '0'*64}, 'dependency changed'),
                                ({'width': 241}, 'dimensions differ'),
                                ({'file': '../reference.png'}, 'escapes project')]:
            batch = copy.deepcopy(self.batch)
            batch['operations'][0]['reference'].update(change)
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, message):
                scene_authoring.resolve_batch(self.project, self.scene, self.catalog, batch)

    def test_changed_pack_or_catalog_mapping_is_rejected(self):
        catalog = copy.deepcopy(self.catalog)
        catalog['assets'][0]['registration_mapping']['cels'][0]['reference_to_cell'][4] += 2
        with self.assertRaisesRegex(ValueError, 'Catalog/pack placement metadata differs'):
            scene_authoring.resolve_batch(self.project, self.scene, catalog, self.batch)
        recipe = self.project/self.catalog['assets'][0]['provenance']['recipe']
        spec = studio.read(recipe);spec['output']['padding'] += 1;studio.write(recipe, spec)
        with self.assertRaisesRegex(ValueError, 'Placement pack changed'):
            scene_authoring.resolve_batch(self.project, self.scene, self.catalog, self.batch)

    def test_catalog_cannot_relabel_or_omit_pack_source_provenance(self):
        for key, value in [('sources', []), ('registration_source', {'file': 'alternate.json', 'sha256': '0'*64}),
                           ('source_mapping', None)]:
            catalog = copy.deepcopy(self.catalog)
            catalog['assets'][0]['provenance'][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'Catalog/pack source provenance differs'):
                scene_authoring.resolve_batch(self.project, self.scene, catalog, self.batch)

    def test_explicit_bound_mapping_supports_immutable_legacy_base(self):
        base = self.catalog['assets'][0]
        mapping = {'version': 1, 'asset_sha256': base['sha256'],
                   'cell_size': base['registration_mapping']['cell_size'],
                   'reference': self.manifest['placements'][0]['reference'],
                   'reference_to_cell': base['registration_mapping']['cels'][0]['reference_to_cell']}
        base.pop('registration_mapping');base.pop('provenance')
        studio.write(self.project/'assets/catalog.json', self.catalog)
        studio.write(self.project/'legacy-base-mapping.json', mapping)
        batch = {'version': 1, 'operations': [copy.deepcopy(self.batch['operations'][0])]}
        batch['operations'][0]['base_mapping'] = {'file': 'legacy-base-mapping.json',
            'sha256': studio.digest(self.project/'legacy-base-mapping.json')}
        resolved, records = scene_authoring.resolve_batch(self.project, self.scene, self.catalog, batch)
        self.assertEqual(resolved['operations'][0]['base_mapping'], mapping)
        self.assertEqual(len(self.bridge(resolved)['scene']['layers']), 2)
        self.assertTrue(any(row['file'] == 'legacy-base-mapping.json' for row in records))
        # A bound mapping is not a way to bypass an incorrect asset identity.
        resolved['operations'][0]['base_mapping']['asset_sha256'] = '0'*64
        result = subprocess.run(['node', str(ROOT/'tools/scene-command.mjs')],
            input=json.dumps({'action': 'apply', 'scene': self.scene, 'catalog': self.catalog,
                             'args': {'batch': resolved}}), text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('identity differs', json.loads(result.stdout)['error'])

    def test_kit_uses_shared_timing_and_does_not_modify_scene(self):
        path = self.project/'scene/scene.json'
        scene = studio.read(path)
        gesture = next(row for row in scene['layers'] if row['id'] == 'gesture')
        gesture['tracks'] = {'cell': {'interpolation': 'hold', 'keys': [[0, 0], [.1, 1], [.2, 2], [.3, 3], [4, 0]]}}
        studio.write(path, scene);before = path.read_bytes()
        report = kit.validate(path, self.project/'assets/catalog.json')
        self.assertEqual(report['errors'], [])
        row = next(row for row in report['cycles'] if row['layer'] == 'gesture')
        self.assertIsNone(row['cel_fps']);self.assertEqual(row['seconds'], 1)
        self.assertEqual(row['timing_driver'], 'cell_track')
        self.assertEqual(row['fallback_cycle']['nominal_cel_fps'], 4)
        self.assertAlmostEqual(row['timing_summary']['authored_rate_segments'][0]['cel_selection_hz'], 10)
        self.assertEqual(report['timing']['version'], 1)
        self.assertEqual(report['timing']['output_frames'], 120)
        self.assertEqual(path.read_bytes(), before)


if __name__ == '__main__':
    unittest.main(verbosity=2)
