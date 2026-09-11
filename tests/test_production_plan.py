import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import studio
from ambiance_studio import production_plan as plan
from ambiance_studio.errors import CommandError


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name); (self.project/'plans').mkdir()
        self.proposal = self.project/'proposal.json'
        self.data = studio.read(ROOT/'examples/production-plan.json')
        studio.write(self.project/'plans/asset-inventory.json', {'version': 1, 'items': [{'id': 'room', 'required_parts': [{'id': 'plate'}]}]})

    def save(self):
        studio.write(self.proposal, self.data)

    def test_strict_contract_missing_extra_duplicate_nonfinite_and_types(self):
        plan.validate(self.project, self.data)
        for mutate in [lambda d: d.pop('story'), lambda d: d.update(extra=True),
                       lambda d: d['elements'].append(copy.deepcopy(d['elements'][0])),
                       lambda d: d['elements'][0].update(readability_target=True),
                       lambda d: d['elements'][0].update(cadence='gentle'),
                       lambda d: d['expectations'][0].update(view_ids=['missing']),
                       lambda d: d['elements'][0]['realization'].update(x=.2)]:
            bad = copy.deepcopy(self.data); mutate(bad)
            with self.assertRaises(ValueError): plan.validate(self.project, bad)
        for text in ['{"x":1,"x":2}', '{"x":NaN}']:
            self.proposal.write_text(text)
            with self.assertRaises(ValueError): plan.read(self.proposal)

    def test_source_identity_and_outside_paths(self):
        source = self.project/'paint.txt'; source.write_text('source')
        self.data['sources'] = [{'id': 'paint', 'path': 'paint.txt', 'sha256': studio.digest(source)}]
        plan.validate(self.project, self.data)
        source.write_text('changed')
        with self.assertRaisesRegex(ValueError, 'changed'): plan.validate(self.project, self.data)
        self.data['sources'][0]['path'] = '../outside'
        with self.assertRaisesRegex(ValueError, 'inside'): plan.validate(self.project, self.data)

    def test_dry_run_expected_hash_history_and_explicit_restore(self):
        self.save(); result = plan.apply(self.project, self.proposal, dry_run=True, expected='absent')
        self.assertIn('room-art', result['diff']); self.assertFalse((self.project/plan.PATH).exists())
        result = plan.apply(self.project, self.proposal, expected='absent'); previous = result['sha256']
        before = (self.project/plan.PATH).read_bytes()
        with self.assertRaises(CommandError): plan.apply(self.project, self.proposal)
        self.data['story']['direction'] = 'Intentional revised direction'
        self.data['change'] = {'reason': 'Explicit revision', 'supersedes_sha256': previous}; self.save()
        with self.assertRaises(CommandError): plan.apply(self.project, self.proposal, expected='0'*64)
        result = plan.apply(self.project, self.proposal, expected=previous)
        history = Path(result['restore_source']); self.assertEqual(before, history.read_bytes())
        restored = plan.read(history); restored['change'] = {'reason': 'Restore original direction', 'supersedes_sha256': result['sha256']}
        studio.write(self.proposal, restored); plan.apply(self.project, self.proposal)
        self.assertEqual(plan.load(self.project)['story'], json.loads(before)['story'])
        self.assertEqual(plan.load_context(self.project)['plan_sha256'], studio.digest(self.project/plan.PATH))

    def test_migration_preserves_originals_reports_contradictions_and_mapping(self):
        inventory = self.project/'plans/asset-inventory.json'
        data = studio.read(inventory); data['items'][0]['required'] = False; studio.write(inventory, data)
        original = inventory.read_bytes(); self.save()
        result = plan.migrate(self.project, self.proposal, ['plans/asset-inventory.json'], self.project/'migration')
        self.assertFalse(result['ok']); self.assertIn('required-contradiction', result['contradictions'][0]['id'])
        self.assertEqual(inventory.read_bytes(), original)
        self.assertEqual((self.project/'migration/originals/0-asset-inventory.json').read_bytes(), original)
        self.assertFalse((self.project/plan.PATH).exists())
        result = plan.apply(self.project, self.project/'migration/candidate.json')
        self.assertFalse(result['ok']); self.assertFalse((self.project/plan.PATH).exists())

    def test_binding_validates_declared_and_actual_inventory_part(self):
        binding = {'element_id': 'room', 'inventory_part': {'item_id': 'room', 'part_id': 'plate'}}
        self.assertEqual(plan.validate_binding(self.project, binding, self.data), binding)
        binding['inventory_part']['part_id'] = 'other'
        with self.assertRaises(ValueError): plan.validate_binding(self.project, binding, self.data)

    def test_required_inventory_cannot_disappear_from_new_scope(self):
        path = self.project/'plans/asset-inventory.json'; inventory = studio.read(path)
        inventory['items'].append({'id': 'character', 'required': True, 'required_parts': [{'id': 'gait', 'required': True}]})
        studio.write(path, inventory)
        conflicts = plan.contradictions(self.project, self.data)
        self.assertEqual([r['id'] for r in conflicts], ['plan.required-unmapped.character', 'plan.required-unmapped.character.gait'])

    def test_cli_replay_dry_apply_check_complexity_and_migrate(self):
        from ambiance_studio import cli
        cli.init_project(self.project/'film', None, 'Synthetic intent replay', 'blank')
        project = self.project/'film'; self.save()
        def run(*args):
            return cli.run(cli.parser().parse_args(['--project', str(project), 'plan', *map(str, args)]))
        self.assertTrue(run('spec', 'apply', self.proposal, '--dry-run')['ok'])
        self.assertTrue(run('spec', 'apply', self.proposal, '--expect-sha256', 'absent')['ok'])
        self.assertTrue(run('spec', 'check')['ok'])
        self.assertEqual(run('complexity')['output_pairs'], 1)
        self.assertNotIn('plan', run('spec', 'inspect'))
        self.assertEqual(run('spec', 'inspect', '--details')['plan'], self.data)


if __name__ == '__main__': unittest.main()
