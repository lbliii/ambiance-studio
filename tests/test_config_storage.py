import copy
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

import studio
from ambiance_studio import recipe_config, iteration_recipes, project_storage
from ambiance_studio.cli import init_project, parser, run, main


class ConfigStorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.project = (Path(self.tmp.name)/'film').resolve(); init_project(self.project, None, 'Config and storage fixture', 'blank', 'dual')

    def layers(self):
        request = {'format': 'ambiance-iteration-request', 'schema_version': 1, 'id': {'$value': 'take'}, 'revision': {'$value': 'take'},
                   'views': ['portrait', 'landscape'], 'default': {'view': 'portrait', 'role': 'silent'}, 'editions': [{'role': 'silent'}], 'long_edge': {'$value': 'size'}}
        studio.write(self.project/'config/base.json', {'format': recipe_config.LAYER, 'schema_version': 1, 'recipe': request, 'values': {'size': 64, 'take': 'base'}})
        (self.project/'config/project.yaml').write_text('format: ambiance-iteration-layer\nschema_version: 1\nvalues:\n  size: 128\nrecipe:\n  notes: "Project note"\n')
        return {'format': recipe_config.FORMAT, 'schema_version': 1, 'layers': ['config/base.json', 'config/project.yaml'],
                'values': {'take': 'draft'}, 'overrides': {'notes': None}}

    def test_config_order_typed_values_origin_and_frozen_recipe(self):
        config = self.layers(); resolution = recipe_config.resolve(self.project, config)
        self.assertEqual(resolution['request']['long_edge'], 128); self.assertEqual(resolution['request']['id'], 'draft')
        self.assertNotIn('notes', resolution['request']); self.assertEqual(resolution['value_origins']['size'], 'config/project.yaml')
        result = iteration_recipes.initialize(self.project, config, self.project/'recipes/draft')
        recipe = Path(result['recipe']).read_bytes(); self.assertTrue((Path(result['recipe']).parent/'config-resolution.json').is_file())
        (self.project/'config/project.yaml').write_text('changed')
        self.assertEqual(Path(result['recipe']).read_bytes(), recipe)

    def test_public_cli_initializer_emits_valid_envelope(self):
        config = self.layers(); file = self.project/'config/draft.json'; studio.write(file,config)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout): code = main(['--project',str(self.project),'iteration','init',str(file),'--out',str(self.project/'recipes/from-cli')])
        self.assertEqual(code,0); self.assertTrue(json.loads(stdout.getvalue())['data']['recipe'])

    def test_config_missing_values_duplicate_keys_and_path_escape_fail(self):
        config = self.layers(); config['overrides'] = {'id': {'$value': 'missing'}}
        with self.assertRaisesRegex(ValueError, 'Unresolved'): recipe_config.resolve(self.project, config)
        file = self.project/'config/duplicate.yaml'; file.write_text('values: 1\nvalues: 2\n')
        with self.assertRaisesRegex(ValueError, 'unique'): recipe_config.read(file)
        config['layers'] = ['../../outside.json']
        with self.assertRaises(ValueError): recipe_config.resolve(self.project, config)
        config['layers'] = [{}]
        with self.assertRaisesRegex(ValueError, 'layer paths'): recipe_config.resolve(self.project, config)

    def artifact(self, name):
        root = self.project/'reports'/name; root.mkdir(parents=True)
        studio.write(root/'render-report.json', {'ok': True, 'case': name}); (root/'frame.png').write_bytes(name.encode())
        return root

    def test_cleanup_preserves_refs_stale_plan_and_roundtrip(self):
        protected = self.artifact('selected'); scratch = self.artifact('scratch')
        studio.write(self.project/'reviews/evidence.json', {'movie': {'path': 'reports/selected/frame.png', 'sha256': studio.digest(protected/'frame.png')}})
        plan = self.project/'.ambiance/cleanup/plans/first.json'
        result = project_storage.plan(self.project, [], 0, plan); self.assertEqual(result['eligible_bundles'], 1)
        studio.write(self.project/'reviews/new.json', {'file': '../reports/scratch/frame.png'})
        with self.assertRaisesRegex(ValueError, 'changed'): project_storage.apply(self.project, plan)
        (self.project/'reviews/new.json').unlink()
        moved = project_storage.apply(self.project, plan); self.assertFalse(scratch.exists()); self.assertTrue(protected.exists())
        project_storage.restore(self.project, moved['id']); self.assertEqual((scratch/'frame.png').read_bytes(), b'scratch')

    def test_cleanup_retention_unknown_bundle_and_modified_trash(self):
        scratch = self.artifact('new'); result = project_storage.plan(self.project, [], 30, Path(self.tmp.name)/'retention.json')
        self.assertEqual(result['eligible_bundles'], 0)
        with self.assertRaises(ValueError): project_storage.plan(self.project, ['assets'], 0, Path(self.tmp.name)/'bad.json')
        path = Path(self.tmp.name)/'move.json'; project_storage.plan(self.project, [], 0, path)
        moved = project_storage.apply(self.project, path)
        target = self.project/'.ambiance/trash'/moved['id']/'reports/new/frame.png'; target.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'changed'): project_storage.restore(self.project, moved['id'])

    def test_cleanup_yaml_relative_references_and_invalid_evidence(self):
        self.artifact('scratch')
        note = self.project/'reports/selection.yaml'
        note.write_text('movie: scratch/frame.png\nmovie: superseded/frame.png\n')
        result = project_storage.plan(self.project, [], 0, Path(self.tmp.name)/'yaml.json')
        self.assertEqual(result['eligible_bundles'], 0)
        self.assertIn('selection.yaml', result['protected'][0]['reason'])
        note.write_text('movie: [broken')
        with self.assertRaisesRegex(ValueError, 'Unreadable YAML'):
            project_storage.plan(self.project, [], 0, Path(self.tmp.name)/'invalid.json')


if __name__ == '__main__': unittest.main()
