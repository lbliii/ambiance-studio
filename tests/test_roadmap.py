import tempfile
from pathlib import Path
import unittest
from ambiance_studio.roadmap import check


class RoadmapTests(unittest.TestCase):
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
