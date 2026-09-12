"""Binding commands use the shared evaluator and ordinary scene transactions."""
from .command_output import Output, add_output
from pathlib import Path

import studio
from .project import locations, project_lock
from .scene_transactions import scene_transaction
from . import scene_runtime, scene_authoring
from .finishing import fields


def add_parsers(sub):
    group = sub.add_parser('binding', help='Inspect and apply explicit source/follower mappings').add_subparsers(dest='action', required=True)
    for action in ['inspect', 'check']:
        q = group.add_parser(action); q.add_argument('--time', type=float, default=0); add_output(q, Output.REPORT, type=Path)
    q = group.add_parser('apply'); q.add_argument('file', type=Path)
    q.add_argument('--dry-run', action='store_true'); q.add_argument('--expect-sha256')


def run(args, project):
    if args.action in ['inspect', 'check']:
        with project_lock(project):
            scene_path, catalog_path = locations(project)
            scene, catalog = studio.read(scene_path), studio.read(catalog_path)
            result = scene_runtime.scene_bridge('binding-check', scene, catalog, {'time': args.time})
            _, dependencies = scene_authoring.resolve_batch(project, scene, catalog,
                {'version': 1, 'operations': [{'op': 'bindings', 'value': scene.get('bindings')}]})
            return {'ok': True, **result, 'dependencies': dependencies,
                    'limits': ['State and dependency checks are not raster or normal-speed artistic observations.']}
    from .scene_commands import apply_batch
    with scene_transaction(project, args.expect_sha256) as transaction:
        doc = transaction.read_json(args.file, 'binding-input')
        fields(doc, ['kind', 'version', 'bindings'], 'binding document')
        if doc.get('kind') != 'ambiance-bindings' or doc.get('version') != 1 or 'bindings' not in doc:
            raise ValueError('Expected ambiance-bindings version 1 with bindings (or null to remove)')
        return apply_batch(transaction, {'version': 1, 'operations': [{'op': 'bindings', 'value': doc['bindings']}]},
                           'binding-apply', dry_run=args.dry_run)
