"""Local library command adapters over registry and server services."""
from pathlib import Path

from . import registry, studio_server
from .errors import CommandError

def add_parsers(sub):
    group=sub.add_parser('studio',help='Open the shared local film library').add_subparsers(dest='action',required=True)
    q=group.add_parser('register');q.add_argument('path',type=Path);q.add_argument('--id');q.add_argument('--relocate',action='store_true')
    q=group.add_parser('open');q.add_argument('--port',type=int,default=8783);q.add_argument('--no-browser',action='store_true')
    q=group.add_parser('serve');q.add_argument('--port',type=int,default=8783)
    group.add_parser('status');group.add_parser('stop')


def run(args, root, registry_file):
    if args.action == 'register':
        return registry.register(registry_file, args.path, args.id, args.relocate)
    if args.action == 'open':
        return studio_server.open_studio(root, registry_file, args.port, not args.no_browser)
    if args.action == 'serve':
        return studio_server.serve(root, registry_file, args.port)
    if args.action == 'status':
        return studio_server.status(registry_file)
    if args.action == 'stop':
        return studio_server.stop(registry_file)
    raise CommandError('Unsupported command')
