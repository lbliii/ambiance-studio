"""Advisory guidance validation; actual pipeline criteria remain in studio."""
import argparse
from pathlib import Path
import re

import studio
from .scene_runtime import load_scene_json

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT/'templates/workflows/painted-film.v1.json'


def native_parser(route):
    from .cli import parser
    current = parser()
    for word in route:
        sub = next((a for a in current._actions if isinstance(a, argparse._SubParsersAction)), None)
        if sub is None or word not in sub.choices:
            raise ValueError('Workflow operation has no native route: '+' '.join(route))
        current = sub.choices[word]
    return current


def load(path=CATALOG):
    from .workflow_operations import ROUTES
    data = load_scene_json(Path(path).read_bytes())
    if set(data) != {'format', 'schema_version', 'id', 'stages', 'operations'} or data['format'] != 'ambiance-workflow-catalog' or data['schema_version'] != 1:
        raise ValueError('Expected workflow catalog version 1')
    def rows(values, label):
        if not isinstance(values, list) or not values: raise ValueError(label+' must be a nonempty array')
        result = {}
        for row in values:
            if not isinstance(row, dict) or not re.fullmatch(r'[a-z][a-z0-9.-]*', row.get('id', '')) or row['id'] in result:
                raise ValueError('Invalid or duplicate '+label+' ID')
            result[row['id']] = row
        return result
    def docs(paths):
        for ref in paths:
            if not isinstance(ref, str) or not studio.inside(ROOT, ref).is_file():
                raise ValueError('Missing workflow reference: '+str(ref))
    operations = rows(data['operations'], 'operation')
    for id, row in operations.items():
        if set(row) - {'id','resolver','route','inputs','outputs','effects','runtime','contract','syntax'}:
            raise ValueError('Unknown operation fields: '+id)
        if row['resolver'] != id or id not in ROUTES or row['route'] != ROUTES[id]:
            raise ValueError('Unknown/incompatible native resolver: '+id)
        native_parser(row['route'])
        if row['runtime'] not in [None, 'node', 'pillow', 'renderer', 'native', 'audio-source']:
            raise ValueError('Unknown runtime binding')
        if not row['effects'] or set(row['effects']) - {'read','artifact-write','project-write'}:
            raise ValueError('Invalid operation effects')
        for key in ['inputs','outputs']:
            if not row[key] or not all(isinstance(v,str) and v.strip() for v in row[key]): raise ValueError('Invalid operation '+key)
        docs([row['contract']])
    stages = rows(data['stages'], 'stage')
    for row in stages.values():
        if set(row) != {'id','purpose','inputs','outputs','references','operations','criterion_bindings','coverage_stage'}:
            raise ValueError('Invalid workflow stage fields')
        if not row['operations'] or len(row['operations']) != len(set(row['operations'])) or any(id not in operations for id in row['operations']):
            raise ValueError('Stage references unknown/duplicate operation')
        if row['coverage_stage'] not in [None, 'layout','assets','animation','export'] or row['coverage_stage'] not in [None,row['id']]:
            raise ValueError('Unsupported coverage stage binding')
        if not isinstance(row['criterion_bindings'],dict) or any(not isinstance(v,str) or not re.fullmatch('[0-9a-f]{64}',v) for v in row['criterion_bindings'].values()):
            raise ValueError('Invalid criterion compatibility signatures')
        for key in ['inputs','outputs','references']:
            if not row[key] or not all(isinstance(v,str) and v.strip() for v in row[key]):raise ValueError('Invalid stage '+key)
        docs(row['references'])
    return {'id': data['id'], 'schema_version': 1, 'sha256': studio.digest(path), 'path': str(Path(path).resolve()),
            'stages': stages, 'operations': operations}


def operation_details(row):
    result = dict(row)
    result['help_argv'] = [str(ROOT/'ambiance'), *row['route'], '--help']
    result['native_help'] = native_parser(row['route']).format_help()
    if row['id'].startswith('prepare.'):
        result['native_suboperation'] = row['id'].split('.')[1]
        result['note'] = 'The native parser accepts the verb in the source positional. This is an existing operation, not a proposed route.'
    return result
