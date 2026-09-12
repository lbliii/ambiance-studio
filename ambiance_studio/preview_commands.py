"""Preview routing; each server retains its startup, HTTP and draft behavior."""
from pathlib import Path

from .asset_commands import asset_tool
from .errors import CommandError
from .project import locations
from .project_commands import check_project

def add_parsers(sub):
    q=sub.add_parser('preview',help='Serve a project, saved look or preparation workspace on localhost');q.add_argument('--port',type=int,default=8783)
    preview_kind=q.add_mutually_exclusive_group()
    preview_kind.add_argument('--look',type=Path,help='Serve a verified look-proof artifact without requiring a project')
    preview_kind.add_argument('--views-proof',type=Path,help='Serve a saved synchronized view proof with verified frame hashes')
    preview_kind.add_argument('--motion',type=Path,help='Inspect a motion proof and evaluate in-memory drafts')
    preview_kind.add_argument('--prepare',type=Path,help='Inspect and edit a verified preparation draft without writing project files')
    preview_kind.add_argument('--region',type=Path,help='Inspect and edit a saved art region without writing project files')


def is_artifact(args):
    return any(getattr(args, key) is not None for key in ['motion', 'look', 'views_proof', 'prepare', 'region'])


def run(args, project, root):
    if args.motion is not None:
        asset_tool()
        from .motion_server import serve
        serve(args.motion, args.port)
    elif args.look is not None:
        from .preview import serve_look
        serve_look(args.look, args.port)
    elif args.views_proof is not None:
        from .preview import serve_look
        serve_look(args.views_proof, args.port, kind='views-proof')
    elif args.prepare is not None:
        from .preparation_server import serve
        serve(args.prepare, args.port)
    elif args.region is not None:
        from .region_server import serve
        serve(args.region, args.port)
    else:
        locations(project)
        checked = check_project(project)
        if not checked['ok']:
            raise CommandError('Project checks failed. Run project check for details.', 'check_failed', 1)
        from .preview import serve
        serve(root, project, args.port)
    return None
