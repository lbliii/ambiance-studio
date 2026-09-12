"""Asset command adapters; the compiler and preparation services own artifacts."""
from .command_output import Output, add_output
import importlib.util
from pathlib import Path

import studio
from . import assets
from .errors import CommandError
from .project import locations, project_lock

def asset_tool():
    if importlib.util.find_spec('PIL') is None:raise CommandError('Install requirements-assets.txt with this Python to prepare assets.','missing_dependency',3)
    from tools import asset_tool as module
    return module

def add_parsers(sub):
    group=sub.add_parser('asset').add_subparsers(dest='action',required=True)
    group.add_parser('list')
    q=group.add_parser('build');q.add_argument('recipe',type=Path);add_output(q, Output.ARTIFACT, type=Path,required=True)
    q=group.add_parser('admit');q.add_argument('pack',type=Path)
    q=group.add_parser('inspect');q.add_argument('pack',type=Path)
    q=group.add_parser('proof');q.add_argument('asset');add_output(q, Output.ARTIFACT, type=Path,required=True);q.add_argument('--catalog',type=Path)
    q.add_argument('--fps',type=float,default=6);q.add_argument('--width',type=int,default=180);q.add_argument('--landmark',default='anchor')
    assets.add_preparation_parsers(group)
    from . import region_commands
    region_commands.add_parsers(group)
    from . import generation_ledger
    generation_ledger.add_parsers(group)
    from . import asset_motion
    asset_motion.add_parsers(group)


def run(args, project):
    action = args.action
    if action == 'build':
        return asset_tool().build(args.recipe, args.out)
    if action == 'inspect':
        asset_tool()
        return assets.inspect_pack(args.pack)
    if action == 'proof':
        return assets.proof(args.asset, args.out, project, args.catalog, args.fps, args.width, args.landmark)
    if action == 'region':
        asset_tool()
        from . import region_commands
        return region_commands.run(args, project)
    if action == 'motion':
        asset_tool()
        from . import asset_motion
        return asset_motion.run(args, project)
    if action == 'request':
        from . import generation_ledger
        return generation_ledger.run(args, project)
    if action in ['prepare', 'preflight', 'crop', 'return', 'edges', 'edge-repair', 'trim-cels']:
        return assets.run_preparation(args, project)
    _, catalog_path = locations(project)
    if action == 'list':
        return studio.read(catalog_path)
    if action == 'admit':
        with project_lock(project):
            return asset_tool().admit(args.pack, catalog_path)
    raise CommandError('Unsupported command')
