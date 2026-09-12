"""Revision CLI adapter and compatibility exports for existing Python callers.

New consumers import the owning record, reference, capture, edition or review
module directly. These aliases retain the original public revision entry points.
"""
from pathlib import Path

from .record_contracts import (
    identifier, fields, seal, read_sealed,
)
from .project_references import (
    relative, ref, changed, unique,
)
from .revision_dependencies import (
    SELECTION, PREPARATION, DOCUMENTS, Collector, collect,
)
from .revision_capture import (
    FORMAT, capture, manifest_path, load, check, compare, render_context,
)
from .editions import (
    EDITION, edition_path, load_edition, captured_view, edition_view, report_view, collect_edition_audio, prepare_edition, record_edition,
)
from .revision_reviews import (
    review_context, status, project_status, handoff,
)


def add_parsers(sub):
    group = sub.add_parser('revision', help='Capture and verify explicit production revisions').add_subparsers(dest='action', required=True)
    q = group.add_parser('capture'); q.add_argument('id'); q.add_argument('--selection', type=Path, required=True)
    q.add_argument('--dry-run', action='store_true'); q.add_argument('--expect-selection-sha256')
    for action in ['inspect', 'check', 'compare', 'handoff']:
        q = group.add_parser(action); q.add_argument('id')
        if action in ['check', 'compare']: q.add_argument('--out', type=Path)
        if action == 'compare': q.add_argument('--working', action='store_true', required=True)
        if action == 'handoff': q.add_argument('--edition'); q.add_argument('--out', type=Path, required=True)


def run(args, project):
    if args.action == 'capture': return capture(project, args.id, args.selection, args.dry_run, args.expect_selection_sha256)
    if args.action == 'inspect': return {'ok': True, 'manifest': load(project, args.id), 'integrity': check(project, args.id)}
    if args.action == 'check': return check(project, args.id)
    if args.action == 'compare': return compare(project, args.id)
    if args.action == 'handoff': return handoff(project, args.id, args.edition, args.out)
    raise ValueError('Unknown revision command')
