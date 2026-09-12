"""Dedicated intent command adapter; legacy inventory commands retain their meaning."""
from .command_output import Output, add_output
from pathlib import Path
from . import production_plan as plan


def add_parsers(group):
    spec = group.add_parser('spec', help='Canonical creative intent').add_subparsers(dest='spec_action', required=True)
    for name in ['inspect', 'check']:
        q = spec.add_parser(name); q.add_argument('--details', action='store_true'); add_output(q, Output.REPORT, type=Path)
    q = spec.add_parser('apply'); q.add_argument('file', type=Path); q.add_argument('--dry-run', action='store_true'); q.add_argument('--expect-sha256')
    q = spec.add_parser('migrate'); q.add_argument('file', type=Path, help='Explicit authored mapping proposal')
    q.add_argument('--original', action='append', required=True); add_output(q, Output.ARTIFACT, type=Path, required=True)
    q = group.add_parser('complexity'); add_output(q, Output.REPORT, type=Path)
    q = group.add_parser('coverage'); q.add_argument('--stage', choices=plan.STAGES, default='animation')
    q.add_argument('--view'); q.add_argument('--revision'); q.add_argument('--details', action='store_true'); add_output(q, Output.REPORT, type=Path)
    q.add_argument('--phase', choices=['current', 'preflight'], default='current')
    q = group.add_parser('evidence'); q.add_argument('expectation'); q.add_argument('--view', required=True)
    q.add_argument('--receipt', required=True, help='Project-relative typed provider receipt')
    q.add_argument('--revision'); q.add_argument('--role', choices=['score', 'effects', 'silent'])


def run(args, project):
    if args.action in ['coverage', 'evidence']:
        from . import production_coverage as coverage
        if args.action == 'coverage': return coverage.evaluate(project, args.stage, args.view, args.revision, details=args.details, phase=args.phase)
        return coverage.register_evidence(project, args.expectation, args.view, args.receipt, args.revision, args.role)
    if args.action == 'complexity': return {'ok': True, **plan.complexity(plan.load(project))}
    if args.spec_action in ['inspect', 'check']: return plan.inspect(project, args.details)
    if args.spec_action == 'apply': return plan.apply(project, args.file, dry_run=args.dry_run, expected=args.expect_sha256)
    return plan.migrate(project, args.file, args.original, args.out)
