"""Compatibility with records sealed before the revision ownership extraction."""
import importlib
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import studio
from ambiance_studio import revisions, record_contracts, project_references
from revision_contract_fixture import build

FIXTURES = ROOT/'tests/fixtures/revision-contracts'


class RevisionContractTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()

    def test_capture_and_both_edition_versions_retain_exact_baseline_bytes(self):
        project = self.root/'film'
        for name, path in build(project, revisions).items():
            with self.subTest(record=name):
                self.assertEqual(path.read_bytes(), (FIXTURES/name).read_bytes())
        self.assertTrue(revisions.check(project, 'fixture')['ok'])
        for id, version in [('legacy', 1), ('portrait', 2)]:
            receipt = revisions.load_edition(project, 'fixture', id)
            self.assertEqual(receipt['schema_version'], version)
        self.assertEqual((project/'brief.md').read_bytes(), (project/'revisions/fixture/controls/brief.md').read_bytes())

    def test_persisted_seals_are_kind_and_version_specific_and_do_not_rewrite(self):
        for name, kind, versions in [('manifest.json', revisions.FORMAT, (1,)),
                                     ('legacy.json', revisions.EDITION, (1,)),
                                     ('portrait.json', revisions.EDITION, (1, 2))]:
            path = FIXTURES/name; before = path.read_bytes()
            data = record_contracts.read_sealed(path, kind, versions)
            unsigned = {k: v for k, v in data.items() if k != 'payload_sha256'}
            output = self.root/name; studio.write(output, record_contracts.seal(unsigned))
            self.assertEqual(output.read_bytes(), before)
            self.assertEqual(path.read_bytes(), before)
            with self.assertRaisesRegex(ValueError, 'Unsupported'):
                record_contracts.read_sealed(path, 'ambiance-cleanup-plan', versions)
        with self.assertRaisesRegex(ValueError, 'Unsupported'):
            record_contracts.read_sealed(FIXTURES/'portrait.json', revisions.EDITION)

    def test_tampering_and_noninteger_versions_reject_even_with_a_valid_seal(self):
        source = studio.read(FIXTURES/'manifest.json'); path = self.root/'record.json'
        altered = {**source, 'id': 'tampered'}; studio.write(path, altered)
        with self.assertRaisesRegex(ValueError, 'integrity changed'):
            record_contracts.read_sealed(path, revisions.FORMAT)
        source.pop('payload_sha256')
        for version in [True, 1.0, '1', 2]:
            studio.write(path, record_contracts.seal({**source, 'schema_version': version}))
            with self.assertRaisesRegex(ValueError, 'Unsupported'):
                record_contracts.read_sealed(path, revisions.FORMAT)

    def test_seals_preserve_legacy_unicode_nan_and_existing_payload_policy(self):
        data = {'format': 'fixture', 'schema_version': 1, 'text': 'café 雨', 'number': float('nan')}
        sealed = record_contracts.seal(data)
        self.assertNotIn('payload_sha256', data)
        self.assertEqual(sealed['payload_sha256'], '7ccffe06c0314dfc1ec7439f7ad4452d6cf73e92f86b02799aa2dbba86c12980')
        path = self.root/'record.json'; studio.write(path, sealed)
        self.assertTrue(math.isnan(record_contracts.read_sealed(path, 'fixture')['number']))
        # Existing callers remove a prior payload explicitly before re-sealing.
        studio.write(path, record_contracts.seal(sealed))
        with self.assertRaisesRegex(ValueError, 'integrity changed'):
            record_contracts.read_sealed(path, 'fixture')

    def test_identifier_and_field_validation_remain_import_compatible(self):
        for value in ['a', 'A'+'x'*99, 'v1.edition-role_name']:
            self.assertEqual(record_contracts.identifier(value), value)
        for value in ['', 'x'*101, '../escape', '.hidden', 'café', 1, None]:
            with self.assertRaises(ValueError): record_contracts.identifier(value)
        record_contracts.fields({'format': 'fixture'}, ['format'], 'fixture')
        for value in [[], None, {'unexpected': 1}]:
            with self.assertRaisesRegex(ValueError, 'Unsupported fixture fields'):
                record_contracts.fields(value, ['format'], 'fixture')

    def test_reference_identity_retains_roles_order_and_stale_byte_checks(self):
        project = self.root/'film'; project.mkdir(); path = project/'paint.bin'; path.write_bytes(b'paint')
        first = project_references.ref(project, path, 'assets', 'image')
        duplicate = {**first, 'sha256': '0'*64}
        release = project_references.ref(project, path, 'release', 'image')
        self.assertEqual(project_references.unique([first, release, duplicate]), [duplicate, release])
        self.assertEqual(first['path_base'], 'project')
        self.assertEqual(project_references.changed(project, [first]), [])
        with self.assertRaisesRegex(ValueError, 'Changed image'):
            project_references.ref(project, path, 'assets', 'image', '0'*64)
        self.assertEqual(project_references.changed(project, [{**first, 'bytes': 99}])[0]['path'], 'paint.bin')
        path.write_bytes(b'other')
        self.assertEqual(project_references.changed(project, [first])[0]['expected_sha256'], first['sha256'])
        path.unlink()
        self.assertIsNone(project_references.changed(project, [first])[0]['actual_sha256'])
        for content in [None, b'']:
            if content is not None: path.write_bytes(content)
            with self.assertRaisesRegex(ValueError, 'Missing or empty'):
                project_references.ref(project, path, 'assets', 'image')

    def test_reference_paths_keep_containment_and_distinct_resolution_rules(self):
        project = self.root/'film'; project.mkdir(); path = project/'paint.bin'; path.write_bytes(b'paint')
        outside = self.root/'outside.bin'; outside.write_bytes(b'outside')
        (project/'alias').symlink_to(path); (project/'escape').symlink_to(outside)
        self.assertEqual(project_references.ref(project, project/'alias', 'assets', 'image')['path'], 'paint.bin')
        self.assertEqual(project_references.relative(project, project/'unused/../paint.bin'), 'paint.bin')
        for escaped in [outside, project/'escape']:
            with self.assertRaises(ValueError): project_references.ref(project, escaped, 'assets', 'image')
        reference = project_references.ref(project, path, 'assets', 'image')
        # Persisted references use studio.inside: even in-project absolute paths
        # and lexical parent traversal are rejected instead of normalized.
        for name in [str(path), 'unused/../paint.bin', '../outside.bin', 'escape', '']:
            with self.assertRaises(ValueError): project_references.changed(project, [{**reference, 'path': name}])

    def test_record_and_reference_consumers_do_not_load_revision_services(self):
        for owner in ['record_contracts', 'project_references', 'registry', 'project_storage']:
            code = (f'import ambiance_studio.{owner}; import sys; '
                    "assert not {'ambiance_studio.revisions', 'ambiance_studio.editions', "
                    "'ambiance_studio.revision_capture', 'ambiance_studio.revision_reviews'} & set(sys.modules)")
            subprocess.run([sys.executable, '-c', code], cwd=ROOT, check=True, capture_output=True)

    def test_all_previous_public_functions_and_constants_are_aliases(self):
        owners = {
            'record_contracts': 'identifier fields seal read_sealed',
            'project_references': 'relative ref changed unique',
            'revision_dependencies': 'SELECTION PREPARATION DOCUMENTS Collector collect',
            'revision_capture': 'FORMAT capture manifest_path load check compare render_context',
            'editions': 'EDITION edition_path load_edition captured_view edition_view report_view collect_edition_audio prepare_edition record_edition',
            'revision_reviews': 'review_context status project_status handoff',
        }
        for owner, names in owners.items():
            module = importlib.import_module('ambiance_studio.'+owner)
            for name in names.split(): self.assertIs(getattr(revisions, name), getattr(module, name))
        for owner in owners:
            code = f'import ambiance_studio.{owner}; import ambiance_studio.revisions'
            subprocess.run([sys.executable, '-c', code], cwd=ROOT, check=True, capture_output=True)


if __name__ == '__main__': unittest.main()
