"""CLI boundary: parsing, project selection, dispatch and JSON/error envelopes."""
import argparse
from functools import partial
import json
from pathlib import Path
import sys

from . import __version__
from . import planning, assets, revisions, views
from . import asset_commands, diagnostic_commands, preview_commands
from . import production_commands, project_commands, review_commands, scene_commands, studio_commands
from .command_output import Output, selected_output
from .errors import CommandError
# Compatibility imports for existing Python callers.
from .asset_commands import asset_tool
from .project_commands import init_project, check_project
from .scene_runtime import scene_bridge

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import studio

class Parser(argparse.ArgumentParser):
    def error(self,message):raise CommandError(message)

def emit(command,data,ok=True):
    print(json.dumps({'ok':ok,'schema_version':1,'command':command,'data':data},indent=2,allow_nan=False))

def project_path(value, registry_file=None):
    if value:
        p=Path(value).resolve()
        if not (p/'ambiance-project.json').is_file():
            if len(Path(value).parts)==1 and not Path(value).is_absolute():
                from . import registry
                return registry.resolve(ROOT, registry.registry_path(registry_file), str(value))
            raise CommandError(f'No ambiance-project.json in {p}')
        return p
    for p in [Path.cwd(),*Path.cwd().parents]:
        if (p/'ambiance-project.json').is_file():return p.resolve()
    raise CommandError('Choose --project PATH, or run inside an initialized project.')

def optional_project_path(value, registry_file=None):
    if value:return project_path(value,registry_file)
    for p in [Path.cwd(),*Path.cwd().parents]:
        if (p/'ambiance-project.json').is_file():return p.resolve()
    return None

def parser():
    p = Parser(prog='ambiance', description='Ambiance Studio — local projects, assets, rigs, checks and reviews. Commands emit JSON.')
    p.add_argument('--version', action='version', version=f'Ambiance Studio {__version__}')
    p.add_argument('--project', type=Path, help='Project directory; otherwise discover it from the working directory')
    p.add_argument('--registry', type=Path, help='Shared local registry; defaults to AMBIANCE_REGISTRY or ~/.ambiance-studio/registry.json')
    sub = p.add_subparsers(dest='command', required=True)
    sub.add_parser('doctor', help='Inspect runtimes and implemented capabilities')
    for module in [project_commands, studio_commands, asset_commands, scene_commands,
                   review_commands, preview_commands, diagnostic_commands, planning]:
        module.add_parsers(sub)
    assets.add_library_parsers(sub)
    revisions.add_parsers(sub)
    views.add_parsers(sub)
    from . import rendering, audio, finishing, production, bindings
    for module in [rendering, audio, finishing, bindings, production]:
        module.add_parsers(sub)
    return p


# Commands not requiring a project are explicit; all others select a project.
PROJECT_FREE = {('project', 'init'), ('project', 'list'), ('asset', 'build'), ('asset', 'inspect')}
PROJECT_OPTIONAL = {('asset', 'proof')}


def command_project(args):
    command, action = args.command, getattr(args, 'action', None)
    route = (command, action)
    if route == ('audio', 'library') and args.library_action not in ['import', 'materialize', 'check']:
        return None
    if command in ['studio', 'doctor', 'test'] or route in PROJECT_FREE:
        return None
    if command == 'preview' and preview_commands.is_artifact(args):
        return None
    if route == ('asset', 'proof'):
        # The compiler dependency was always checked before optional selection.
        asset_tool()
    if command == 'library' or route in PROJECT_OPTIONAL:
        return optional_project_path(args.project, args.registry)
    return project_path(args.project, args.registry)


def run_render(args, project):
    if args.action == 'benchmark':
        from .benchmarking import benchmark
        return benchmark(project, studio.read(args.file), args.out)
    from .media_operations import execute_media
    return execute_media(args, project)


def run(args):
    from . import audio, bindings, registry
    from .media_operations import execute_media
    registry_file = registry.registry_path(getattr(args, 'registry', None))
    project = command_project(args)
    if args.command == 'doctor':
        return diagnostic_commands.doctor(ROOT)
    if args.command == 'test':
        return diagnostic_commands.test(args)
    if args.command == 'studio':
        return studio_commands.run(args, ROOT, registry_file)
    production = partial(production_commands.run, root=ROOT, registry_file=registry_file)
    handlers = {
        'project': partial(project_commands.run, root=ROOT, registry_file=registry_file),
        'asset': asset_commands.run,
        'library': assets.library,
        'delivery': production, 'iteration': production, 'feedback': production,
        'binding': bindings.run, 'revision': revisions.run, 'view': views.run,
        'plan': planning.run, 'render': run_render, 'media': execute_media,
        'audio': audio.run, 'scene': scene_commands.run, 'look': scene_commands.run_look,
        'preview': partial(preview_commands.run, root=ROOT), 'review': review_commands.run,
    }
    handler = handlers.get(args.command)
    if handler is None:
        raise CommandError('Unsupported command')
    return handler(args, project)


def main(argv=None):
    try:
        command_parser=parser()
        args=command_parser.parse_args(argv)
        output=selected_output(command_parser,args)
        result=run(args)
        if result is None:return 0
        command=' '.join(filter(None,[args.command,getattr(args,'action',None),getattr(args,'motion_action',None)]))
        ok=result.get('ok',True) if isinstance(result,dict) else True
        payload={'ok':ok,'schema_version':1,'command':command,'data':result}
        if output is Output.REPORT and getattr(args,'out',None):
            studio.write(args.out,payload)
        emit(command,result,ok)
        return 0 if ok else 1
    except CommandError as e:
        print(json.dumps({'ok':False,'schema_version':1,'error':{'code':e.code,'message':str(e)}},indent=2));return e.exit_code
    except (OSError,ValueError,TypeError,KeyError) as e:
        print(json.dumps({'ok':False,'schema_version':1,'error':{'code':'invalid_input','message':str(e)}},indent=2));return 2
    except KeyboardInterrupt:
        print(json.dumps({'ok':False,'schema_version':1,'error':{'code':'interrupted','message':'Operation interrupted. Inspect saved run/artifact state and resume the unchanged recipe where supported.'}}));return 130
