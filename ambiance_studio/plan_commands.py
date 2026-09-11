"""Dedicated intent command adapter; legacy inventory commands retain their meaning."""
from pathlib import Path
from . import production_plan as plan


def add_parsers(group):
    spec = group.add_parser('spec', help='Canonical creative intent').add_subparsers(dest='spec_action', required=True)
    for name in ['inspect', 'check']:
        q = spec.add_parser(name); q.add_argument('--details', action='store_true'); q.add_argument('--out', type=Path)
    q = spec.add_parser('apply'); q.add_argument('file', type=Path); q.add_argument('--dry-run', action='store_true'); q.add_argument('--expect-sha256')
    q = spec.add_parser('migrate'); q.add_argument('file', type=Path, help='Explicit authored mapping proposal')
    q.add_argument('--original', action='append', required=True); q.add_argument('--out', type=Path, required=True)
    q = group.add_parser('complexity'); q.add_argument('--out', type=Path)


def run(args, project):
    if args.action == 'complexity': return {'ok': True, **plan.complexity(plan.load(project))}
    if args.spec_action in ['inspect', 'check']: return plan.inspect(project, args.details)
    if args.spec_action == 'apply': return plan.apply(project, args.file, dry_run=args.dry_run, expected=args.expect_sha256)
    return plan.migrate(project, args.file, args.original, args.out)
