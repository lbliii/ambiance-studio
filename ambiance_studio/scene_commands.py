"""Scene/look command adapters over the evaluator and transaction service."""
from .command_output import Output, add_output
import re
from pathlib import Path

import studio
from .errors import CommandError
from .project import locations, project_lock
from . import finishing, scene_authoring, scene_runtime
from .scene_transactions import scene_transaction


def add_parsers(sub):
    group=sub.add_parser('scene').add_subparsers(dest='action',required=True)
    q=group.add_parser('clock');q.add_argument('--loop-seconds',type=float,required=True);q.add_argument('--dry-run',action='store_true');q.add_argument('--expect-sha256')
    q=group.add_parser('inspect');q.add_argument('--full',action='store_true');q=group.add_parser('sample');q.add_argument('--time',type=float,required=True)
    q=group.add_parser('apply');q.add_argument('file',type=Path);q.add_argument('--dry-run',action='store_true');q.add_argument('--expect-sha256')
    q=group.add_parser('track');q.add_argument('layer');q.add_argument('file',type=Path);q.add_argument('--dry-run',action='store_true');q.add_argument('--expect-sha256')
    from . import activity
    activity.add_parsers(group)
    q=group.add_parser('timing');q.add_argument('--layer');add_output(q, Output.REPORT, type=Path)
    q=group.add_parser('place');q.add_argument('file',type=Path);q.add_argument('--dry-run',action='store_true');q.add_argument('--expect-sha256')
    q=group.add_parser('reparent');q.add_argument('layer');q.add_argument('--to',required=True);q.add_argument('--socket',required=True)
    q.add_argument('--keep-world',action='store_true',required=True);q.add_argument('--at',type=float,required=True)
    q.add_argument('--dry-run',action='store_true');q.add_argument('--expect-sha256')
    q=group.add_parser('check');add_output(q, Output.REPORT, type=Path)
    q=group.add_parser('set');q.add_argument('layer')
    for name in ['x','y','scale','rotation-deg','opacity','depth','cycle-seconds']:q.add_argument('--'+name,type=float)
    q.add_argument('--phase-frames',type=int)
    q=group.add_parser('socket');q.add_argument('layer');q.add_argument('name');q.add_argument('--u',type=float,required=True);q.add_argument('--v',type=float,required=True)
    q=group.add_parser('attach');q.add_argument('layer');q.add_argument('--to',required=True);q.add_argument('--socket',required=True);q.add_argument('--offset-x',type=float,default=0);q.add_argument('--offset-y',type=float,default=0)
    q=group.add_parser('add');q.add_argument('asset');q.add_argument('--id',required=True);q.add_argument('--name')
    for name in ['x','y','width','depth']:q.add_argument('--'+name,type=float)
    group.add_parser('history');q=group.add_parser('restore');q.add_argument('sha256')


def run(args, project):
    if args.action == 'check':
        from .project_commands import check_project
        return check_project(project, include_views=False)
    if args.action in ['activity', 'activity-review']:
        from . import activity
        return activity.run(args, project)
    return run_scene(args, project)


def scene_batch(args, transaction):
    if args.action == 'clock':
        return {'version': 1, 'operations': [{'op': 'clock', 'values': {'loop_seconds': args.loop_seconds}}]}
    if args.action == 'reparent':
        return {'version': 1, 'operations': [{'op': 'reparent', 'layer': args.layer,
                'to': args.to, 'socket': args.socket, 'preserve': 'world_at_time', 'at_seconds': args.at}]}
    batch = transaction.read_json(args.file, 'scene-input')
    if args.action == 'place':
        return scene_authoring.placement_batch(batch)
    if args.action == 'track':
        if (not isinstance(batch, dict) or batch.get('version') != 1
                or not isinstance(batch.get('tracks'), dict) or set(batch)-{'version', 'tracks', 'track_loop'}):
            raise CommandError('Track file needs version 1, tracks and optional track_loop.')
        return {'version': 1, 'operations': [{'op': 'set', 'layer': args.layer,
                'values': {'tracks': batch['tracks'], 'track_loop': batch.get('track_loop', 'closed')}}]}
    return batch


def apply_batch(transaction, batch, operation, *, dry_run=False, dependencies=(), details=None, diagnostics=False):
    batch, resolved = scene_authoring.resolve_batch(transaction.project, transaction.scene, transaction.catalog, batch)
    report = scene_runtime.scene_bridge('apply', transaction.scene, transaction.catalog, {'batch': batch, 'report': True})
    details = dict(details or {})
    if diagnostics:
        details['diagnostics'] = report['operations']
        if dry_run:
            details['operations'] = len(batch['operations'])
    return transaction.finish(report['scene'], operation, dry_run=dry_run,
                              dependencies=[*resolved, *dependencies], details=details)


def run_look(args, project):
    if args.action in ['inspect', 'check', 'export']:
        with project_lock(project):
            scene_path, catalog_path = locations(project)
            scene, catalog = studio.read(scene_path), studio.read(catalog_path)
            if args.action == 'export':
                return finishing.export_package(project, scene, catalog, args.out, include_rig=args.include_rig)
            return finishing.inspect(project, scene, catalog, args.time)
    with scene_transaction(project, args.expect_sha256) as transaction:
        dependencies, detail = [], {}
        if args.action == 'apply':
            batch = finishing.apply_batch(transaction.read_json(args.file, 'look-input'))
        else:
            batch, dependencies, detail = finishing.import_batch(project, transaction.scene, transaction.catalog,
                args.package, args.bindings, include_rig=args.include_rig)
        return apply_batch(transaction, batch, 'look-'+args.action, dry_run=args.dry_run,
                           dependencies=dependencies, details={'import': detail})


def run_scene(args, project):
    action = args.action
    if action in ['inspect', 'sample', 'timing']:
        scene_path, catalog_path = locations(project)
        return scene_runtime.scene_bridge(action, studio.read(scene_path), studio.read(catalog_path),
            {'time': getattr(args, 'time', None), 'full': getattr(args, 'full', False), 'layer': getattr(args, 'layer', None)})
    if action == 'history':
        return {'snapshots': [{'sha256': path.stem, 'path': str(path)}
                for path in sorted((project/'.ambiance/scene-history').glob('*.json'))]}
    with scene_transaction(project, getattr(args, 'expect_sha256', None)) as transaction:
        if action == 'clock':
            before = scene_runtime.scene_bridge('timing', transaction.scene, transaction.catalog, {})
            batch = scene_batch(args, transaction)
            report = scene_runtime.scene_bridge('apply', transaction.scene, transaction.catalog, {'batch': batch, 'report': True})
            after = scene_runtime.scene_bridge('timing', report['scene'], transaction.catalog, {})
            impact = {'before': before, 'after': after, 'audio': [], 'meaning': 'Existing audio and captured evidence are not retimed.'}
            from .audio import wav_info
            for path in sorted((project/'audio').glob('**/*.wav')):
                try:
                    info = wav_info(path)
                    impact['audio'].append({'path': str(path), 'duration_seconds': info['seconds'], 'picture_loop_seconds': args.loop_seconds, 'needs_cue_review': True})
                except (OSError, ValueError) as error: impact['audio'].append({'path': str(path), 'error': str(error)})
            return transaction.finish(report['scene'], 'clock', dry_run=args.dry_run, details={'timing_impact': impact})
        if action in ['apply', 'track', 'place', 'reparent']:
            return apply_batch(transaction, scene_batch(args, transaction), action,
                               dry_run=args.dry_run, diagnostics=True)
        # Only primitive scene arguments cross the JSON bridge.
        operation_args = {key: value for key, value in vars(args).items() if key not in ['project', 'registry']}
        if action == 'restore':
            if not re.fullmatch('[0-9a-f]{64}', args.sha256):
                raise CommandError('Provide a SHA-256 returned by scene history.')
            operation_args['snapshot'] = transaction.read_json(project/'.ambiance/scene-history'/f'{args.sha256}.json', 'scene snapshot')
            if transaction.dependencies[-1]['sha256'] != args.sha256:
                raise CommandError('Scene history snapshot has changed; refusing to restore it.')
        candidate = scene_runtime.scene_bridge(action, transaction.scene, transaction.catalog, operation_args)
        return transaction.finish(candidate, action)
