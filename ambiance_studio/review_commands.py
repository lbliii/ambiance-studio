"""Review draft and record adapters preserving context validation and locks."""
from .command_output import Output, add_output
from pathlib import Path

import studio
from . import revisions
from .errors import CommandError
from .project import locations, project_lock

def add_parsers(sub):
    group=sub.add_parser('review').add_subparsers(dest='action',required=True)
    from . import review_packets
    review_packets.add_parsers(group)
    q=group.add_parser('draft');q.add_argument('gate');add_output(q, Output.FILE, type=Path,required=True)
    q.add_argument('--revision');q.add_argument('--edition');q.add_argument('--view')
    q=group.add_parser('record');q.add_argument('file',type=Path)


def run(args, project):
    if args.action == 'packet':
        from . import review_packets
        return review_packets.run(args, project)
    # Preserve configuration validation before legacy draft/record operations.
    locations(project)
    if args.action == 'draft':
        if args.edition and not args.revision:
            raise CommandError('--edition requires --revision')
        if args.view and not args.revision:
            raise CommandError('--view requires --revision')
        context = revisions.review_context(project, args.revision, args.edition, args.view) if args.revision else None
        draft = studio.review_template(project, args.gate, context)
        if args.out.exists():
            raise CommandError('Review draft already exists.')
        studio.write(args.out, draft)
        return {'draft': str(args.out.resolve()), 'review': draft}
    if args.action == 'record':
        with project_lock(project):
            source = studio.read(args.file)
            subject = source.get('subject', {})
            context = revisions.review_context(project, subject['revision'], subject.get('edition'), subject.get('view')) if source.get('version') == 2 else None
            return studio.record_review(project, args.file, context)
    raise CommandError('Unsupported command')
