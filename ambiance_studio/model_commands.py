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
    instances = group.add_parser('instance', help='Place, inspect and explicitly adopt contained scene models').add_subparsers(dest='instance_action', required=True)
    q = instances.add_parser('apply'); q.add_argument('recipe', type=Path); q.add_argument('--dry-run', action='store_true'); add_output(q, Output.REPORT, type=Path)
    q = instances.add_parser('inspect'); q.add_argument('--id'); add_output(q, Output.REPORT, type=Path)
    q = instances.add_parser('evidence'); q.add_argument('--receipt', type=Path, required=True); q.add_argument('--instance', dest='instance_ids', action='append', required=True); add_output(q, Output.FILE, type=Path, required=True)


def run(args, project=None):
    if args.action == 'instance':
        from . import model_instances
        if args.instance_action == 'inspect': return model_instances.inspect(project, args.id)
        if args.instance_action == 'evidence':
            from . import model_evidence
            return model_evidence.bind(project, args.receipt, args.instance_ids, args.out)
        return model_instances.apply(project, args.recipe, dry_run=args.dry_run)
    if args.action == 'build': return model_package.build(args.definition, args.source_root, args.out)
    if args.action == 'inspect': return model_package.inspect(args.package)
    if args.action == 'lower': return model_package.lower(args.package, args.state, args.out)
    if args.action == 'proof': return model_package.proof(args.package, args.recipe, args.out)
    if args.action == 'check': return model_package.check(args.proof, args.package, args.recipe)
    if args.action == 'admit': return model_package.admit(args.package, args.proof, args.recipe, args.out)
    raise ValueError('Unsupported model action')
