"""JSON transport to the shared JavaScript scene evaluator."""
import json
from pathlib import Path
import shutil
import subprocess

from .errors import CommandError

ROOT = Path(__file__).resolve().parents[1]


def require_node():
    node = shutil.which('node')
    if not node:
        raise CommandError('Node is required for scene operations. Run ambiance doctor.', 'missing_dependency', 3)
    return node


def scene_bridge(action, scene, catalog, args):
    request = json.dumps({'action': action, 'scene': scene, 'catalog': catalog, 'args': args}, allow_nan=False)
    try:
        process = subprocess.run([require_node(), str(ROOT/'tools/scene-command.mjs')],
                                 input=request, text=True, capture_output=True)
    except OSError as error:
        raise CommandError(f'Scene evaluator failed: {error}', 'runtime_error', 3) from error
    try:
        result = json.loads(process.stdout)
        if not isinstance(result, dict) or type(result.get('ok')) is not bool:
            raise ValueError('Expected a JSON object with a boolean ok field')
        if result['ok'] and 'data' not in result:
            raise ValueError('Successful response is missing data')
        if not result['ok'] and not isinstance(result.get('error'), str):
            raise ValueError('Failed response is missing an error message')
    except ValueError as error:
        detail = process.stderr.strip() or str(error)
        raise CommandError('Scene evaluator failed: '+detail, 'runtime_error', 3) from error
    if not result['ok']:
        raise CommandError(result['error'])
    if process.returncode:
        raise CommandError('Scene evaluator failed: '+(process.stderr.strip() or f'exit {process.returncode}'),
                           'runtime_error', 3)
    return result['data']
