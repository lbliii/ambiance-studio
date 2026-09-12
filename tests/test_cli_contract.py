"""Public option compatibility and CLI output/selection boundary regressions."""
import argparse
from contextlib import contextmanager, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ambiance_studio import cli
from ambiance_studio.command_output import Output, selected_output
from ambiance_studio.errors import CommandError

FIXTURES = Path(__file__).parent/'fixtures'


def parsers(parser, route=()):
    yield route, parser
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, child in action.choices.items():
                yield from parsers(child, (*route, name))


def option_signature(parser):
    # Freeze the pre-refactor option contract, independently of help wrapping
    # differences across supported Python versions and terminal sizes.
    return [{**{key: getattr(action, key) for key in
                ['dest', 'option_strings', 'default', 'const', 'nargs', 'required', 'help', 'metavar']},
             'type': getattr(action.type, '__name__', action.type),
             'action': type(action).__name__,
             'choices': list(action.choices) if action.choices is not None else None}
            for action in parser._actions]


@contextmanager
def working_directory(path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def invoke(argv):
    output = io.StringIO()
    with redirect_stdout(output):
        code = cli.main(list(map(str, argv)))
    return code, json.loads(output.getvalue())


class CLIContractTests(unittest.TestCase):
    def test_every_public_route_retains_flags_defaults_types_and_help(self):
        expected = json.loads((FIXTURES/'cli-options.json').read_text())
        actual = {' '.join(route): hashlib.sha256(json.dumps(option_signature(p), sort_keys=True).encode()).hexdigest()
                  for route, p in parsers(cli.parser())}
        self.assertEqual(set(actual), set(expected))
        for route in expected:
            with self.subTest(route=route):
                self.assertEqual(actual[route], expected[route])

    def test_every_out_route_preserves_envelope_or_service_owned_destination(self):
        cases = json.loads((FIXTURES/'cli-outputs.json').read_text())
        parser = cli.parser()
        declared = {p.prog for _, p in parsers(parser) if '--out' in p._option_string_actions}
        exercised = set()
        with tempfile.TemporaryDirectory() as temporary:
            for index, case in enumerate(cases):
                for ok in [True, False]:
                    with self.subTest(argv=case['argv'], ok=ok):
                        out = Path(temporary)/f'{index}-{ok}'
                        argv = [str(out) if value == 'output' else value for value in case['argv']]
                        args = parser.parse_args(argv)
                        policy = selected_output(parser, args)
                        self.assertEqual(policy.value, case['output'])
                        self.assertFalse(any(key.startswith('_') for key in vars(args)))
                        # Find the selected parser via its ordinary namespace selectors.
                        leaf = parser
                        while True:
                            sub = next((a for a in leaf._actions if isinstance(a, argparse._SubParsersAction)), None)
                            if sub is None: break
                            leaf = sub.choices[getattr(args, sub.dest)]
                        exercised.add(leaf.prog)
                        sentinel = b'{"format":"service-owned","bytes":"unchanged"}\n'
                        if policy is Output.ARTIFACT:
                            out.mkdir()
                            (out/'receipt.json').write_bytes(sentinel)
                        elif policy is Output.FILE:
                            out.write_bytes(sentinel)
                        with patch.object(cli, 'run', return_value={'ok': ok, 'result': 'fixture'}):
                            code, payload = invoke(argv)
                        self.assertEqual(code, 0 if ok else 1)
                        self.assertEqual(payload['ok'], ok)
                        if policy is Output.REPORT:
                            self.assertEqual(json.loads(out.read_text()), payload)
                        elif policy is Output.ARTIFACT:
                            self.assertEqual(list(out.iterdir()), [out/'receipt.json'])
                            self.assertEqual((out/'receipt.json').read_bytes(), sentinel)
                        else:
                            self.assertEqual(out.read_bytes(), sentinel)
        self.assertEqual(exercised, declared)

    def test_missing_output_declaration_fails_before_execution(self):
        parser = cli.Parser()
        parser.add_argument('--out', type=Path)
        with self.assertRaisesRegex(ValueError, 'explicit output semantics'):
            selected_output(parser, parser.parse_args(['--out', 'file']))

    def test_errors_and_interruptions_do_not_write_report_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)/'error.json'
            cases = [(CommandError('locked', 'project_locked', 2), 2, 'project_locked'),
                     (CommandError('decoder failed', 'runtime_error', 3), 3, 'runtime_error'),
                     (ValueError('invalid'), 2, 'invalid_input'),
                     (KeyboardInterrupt(), 130, 'interrupted')]
            for error, expected, kind in cases:
                with self.subTest(kind=kind), patch.object(cli, 'run', side_effect=error):
                    code, payload = invoke(['project', 'check', '--out', out])
                self.assertEqual(code, expected)
                self.assertEqual(payload['error']['code'], kind)
                self.assertFalse(out.exists())

    def test_artifact_previews_keep_one_startup_object_and_ignore_project(self):
        targets = {'motion': 'ambiance_studio.motion_server.serve',
                   'look': 'ambiance_studio.preview.serve_look',
                   'views-proof': 'ambiance_studio.preview.serve_look',
                   'prepare': 'ambiance_studio.preparation_server.serve',
                   'region': 'ambiance_studio.region_server.serve'}
        for kind, target in targets.items():
            with self.subTest(kind=kind), patch(target, side_effect=lambda *a, **kw: cli.emit('preview', {'url': 'fixture'})) as serve, \
                    patch.object(cli, 'project_path', side_effect=AssertionError('Artifact preview must not resolve a project')):
                code, payload = invoke(['--project', 'missing', 'preview', '--'+kind, 'saved-proof', '--port', 9876])
            self.assertEqual(code, 0)
            self.assertEqual(payload['command'], 'preview')
            self.assertEqual(serve.call_args.args[:2], (Path('saved-proof'), 9876))
            self.assertEqual(serve.call_args.kwargs, {'kind': 'views-proof'} if kind == 'views-proof' else {})

    def test_optional_dependency_guard_and_project_selection_order(self):
        parser = cli.parser()
        with patch.object(cli, 'parser', return_value=parser), \
                patch('ambiance_studio.asset_commands.importlib.util.find_spec', return_value=None), \
                patch.object(cli, 'project_path', side_effect=AssertionError('Pillow guard comes first')):
            code, payload = invoke(['--project', 'missing', 'asset', 'proof', 'pack', '--out', 'out'])
        self.assertEqual(code, 3)
        self.assertEqual(payload['error']['code'], 'missing_dependency')

    def test_project_free_asset_build_preserves_shell_paths(self):
        compiler = unittest.mock.Mock()
        compiler.build.return_value = {'cached': True}
        with patch('ambiance_studio.asset_commands.asset_tool', return_value=compiler), \
                patch.object(cli, 'project_path', side_effect=AssertionError('Standalone build selects no project')):
            code, _ = invoke(['--project', 'missing', 'asset', 'build', 'shell-recipe.json', '--out', 'shell-pack'])
        self.assertEqual(code, 0)
        compiler.build.assert_called_once_with(Path('shell-recipe.json'), Path('shell-pack'))

    def test_real_reports_drafts_and_artifacts_keep_paths_and_bytes(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root/'film'
            cli.init_project(project, None, None, 'blank')
            # Run outside the project, with a competing project-relative output name.
            (project/'report.json').write_bytes(b'project sentinel')
            with working_directory(root):
                code, payload = invoke(['--project', project, 'plan', 'check', '--out', 'report.json'])
                self.assertEqual(code, 0)
                self.assertEqual(json.loads((root/'report.json').read_text()), payload)
                self.assertEqual((project/'report.json').read_bytes(), b'project sentinel')
                code, payload = invoke(['--project', project, 'project', 'check', '--out', 'failed.json'])
                self.assertEqual(code, 1)
                self.assertEqual(json.loads((root/'failed.json').read_text()), payload)
                code, payload = invoke(['--project', project, 'review', 'draft', 'intent', '--out', 'draft.json'])
                self.assertEqual(code, 0)
                self.assertEqual(json.loads((root/'draft.json').read_text()), payload['data']['review'])
                original = (root/'draft.json').read_bytes()
                self.assertEqual(invoke(['--project', project, 'review', 'draft', 'intent', '--out', 'draft.json'])[0], 2)
                self.assertEqual((root/'draft.json').read_bytes(), original)
                Image.new('RGBA', (8, 8), (100, 150, 200, 255)).save(root/'source.png')
                code, payload = invoke(['--project', project, 'asset', 'preflight', 'source.png', '--out', 'proof'])
                self.assertEqual(code, 0, payload)
                files = {str(p.relative_to(root/'proof')): p.read_bytes() for p in (root/'proof').rglob('*') if p.is_file()}
                self.assertTrue(files)
                code, _ = invoke(['--project', project, 'asset', 'preflight', 'source.png', '--out', 'proof'])
                self.assertEqual(code, 2)
                self.assertEqual(files, {str(p.relative_to(root/'proof')): p.read_bytes() for p in (root/'proof').rglob('*') if p.is_file()})
                self.assertFalse((project/'proof').exists())


if __name__ == '__main__':
    unittest.main()
