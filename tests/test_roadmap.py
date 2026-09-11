import tempfile
import argparse
import json
from pathlib import Path
import unittest
from ambiance_studio.roadmap import check, check_capabilities


class RoadmapTests(unittest.TestCase):
    def test_capability_index_rejects_stale_routes_and_never_registers_planned_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / 'docs').mkdir()
            (root / 'docs/contract.md').write_text('contract')
            parser = argparse.ArgumentParser()
            parser.add_subparsers().add_parser('actual').add_subparsers().add_parser('inspect')
            row = {'id': 'scope', 'status': 'implemented', 'public_cli': [['actual', 'inspect']],
                   'references': ['docs/contract.md'], 'limits': ['No artistic verdict.']}
            data = {'format': 'ambiance-capability-index', 'schema_version': 1, 'capabilities': [row]}
            def result():
                (root / 'docs/CAPABILITIES.json').write_text(json.dumps(data))
                return check_capabilities(root, parser)
            self.assertTrue(result()['ok'])
            row['public_cli'] = [['actual', 'missing']]
            self.assertIn('unregistered', str(result()['errors']))
            row['status'] = 'planned'
            self.assertIn('planned capability', str(result()['errors']))
            row['public_cli'] = []
            self.assertTrue(result()['ok'])
            row['references'] = ['../outside']
            self.assertIn('missing/escaped', str(result()['errors']))

    def test_dependencies_sources_and_duplicate_keys_fail_without_calling_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); p = root / 'docs/architecture/PRODUCTION-IMPROVEMENTS.yaml'; p.parent.mkdir(parents=True)
            (root / 'design.md').write_text('design')
            base = '''format: ambiance-improvement-roadmap
schema_version: 1
design: design.md
tasks:
- id: CI-01
  depends_on: []
  source_specs: [design.md]
completion:
  core_tasks: [CI-01]
'''
            p.write_text(base); self.assertTrue(check(root)['ok'])
            p.write_text(base.replace('depends_on: []', 'depends_on: [CI-01]'))
            self.assertIn('cycle', str(check(root)['errors']))
            p.write_text(base.replace('depends_on: []', 'depends_on: [CI-99]'))
            self.assertIn('unknown dependency', str(check(root)['errors']))
            p.write_text(base.replace('source_specs: [design.md]', 'source_specs: [missing.md]'))
            self.assertIn('missing/escaped', str(check(root)['errors']))
            p.write_text(base + 'design: overwritten.md\n')
            with self.assertRaisesRegex(ValueError, 'Duplicate'):
                check(root)
