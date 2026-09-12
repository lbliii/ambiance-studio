"""Scene/look command adapters over the evaluator and transaction service."""
import re

import studio
from .errors import CommandError
from .project import locations, project_lock
from . import finishing, scene_authoring, scene_runtime
from .scene_transactions import scene_transaction


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
