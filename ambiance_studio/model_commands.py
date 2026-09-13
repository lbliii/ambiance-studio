"""Project-free, explicitly located local model operations."""
from pathlib import Path
from .command_output import Output, add_output
from . import model_package


def add_parsers(sub):
    group = sub.add_parser('model', help='Build and inspect immutable local model candidates').add_subparsers(dest='action', required=True)
    q = group.add_parser('build'); q.add_argument('definition', type=Path); q.add_argument('--source-root', type=Path, required=True); add_output(q, Output.ARTIFACT, type=Path, required=True)
    q = group.add_parser('inspect'); q.add_argument('package', type=Path); add_output(q, Output.REPORT, type=Path)
    q = group.add_parser('lower'); q.add_argument('package', type=Path); q.add_argument('--state', type=Path, required=True); add_output(q, Output.ARTIFACT, type=Path, required=True)
    q = group.add_parser('proof'); q.add_argument('package', type=Path); q.add_argument('--recipe', type=Path, required=True); add_output(q, Output.ARTIFACT, type=Path, required=True)
    q = group.add_parser('check'); q.add_argument('proof', type=Path); q.add_argument('--package', type=Path, required=True); q.add_argument('--recipe', type=Path, required=True); add_output(q, Output.REPORT, type=Path)
    q = group.add_parser('admit'); q.add_argument('package', type=Path); q.add_argument('--proof', type=Path, required=True); q.add_argument('--recipe', type=Path, required=True); add_output(q, Output.ARTIFACT, type=Path, required=True)


def run(args, project=None):
    if args.action == 'build': return model_package.build(args.definition, args.source_root, args.out)
    if args.action == 'inspect': return model_package.inspect(args.package)
    if args.action == 'lower': return model_package.lower(args.package, args.state, args.out)
    if args.action == 'proof': return model_package.proof(args.package, args.recipe, args.out)
    if args.action == 'check': return model_package.check(args.proof, args.package, args.recipe)
    if args.action == 'admit': return model_package.admit(args.package, args.proof, args.recipe, args.out)
    raise ValueError('Unsupported model action')
