"""Small declarative iteration layers, resolved before existing validation/run paths."""
import copy
import json
from pathlib import Path
import re

import studio
from . import revisions

FORMAT = 'ambiance-iteration-config'
LAYER = 'ambiance-iteration-layer'


def read(path):
    path = Path(path)
    if path.stat().st_size > 1024*1024: raise ValueError('Configuration file exceeds 1 MiB')
    if path.suffix in ['.yaml', '.yml']:
        import yaml
        class Loader(yaml.SafeLoader): pass
        def mapping(loader, node):
            result = {}
            for key_node, value_node in node.value:
                key = loader.construct_object(key_node)
                if not isinstance(key, str) or key in result: raise ValueError('Config keys must be unique strings')
                result[key] = loader.construct_object(value_node)
            return result
        Loader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)
        value = yaml.load(path.read_text(), Loader=Loader)
    else:
        from .production_plan import read as read_json
        value = read_json(path)
    try: json.dumps(value, allow_nan=False)
    except (ValueError, TypeError, RecursionError): raise ValueError('Configuration must contain finite JSON-compatible values')
    return value


def merge(base, override, origins, source, prefix=''):
    if not isinstance(base, dict) or not isinstance(override, dict): raise ValueError('Config recipe and values must be objects')
    result = copy.deepcopy(base)
    for key, value in override.items():
        if not isinstance(key, str): raise ValueError('Config keys must be strings')
        name = prefix+key
        if value is None:
            result.pop(key, None)
        elif isinstance(value, dict) and '$value' not in value:
            result[key] = merge(result.get(key, {}) if isinstance(result.get(key), dict) else {}, value, origins, source, name+'.')
        else: result[key] = copy.deepcopy(value)
        origins[name] = source
    return result


def resolve(project, config):
    revisions.fields(config, {'format', 'schema_version', 'layers', 'values', 'overrides'}, 'iteration config')
    if config.get('format') != FORMAT or config.get('schema_version') != 1: raise ValueError('Expected ambiance-iteration-config schema_version 1')
    project = project.resolve(); files = config.get('layers', [])
    if (not isinstance(files, list) or len(files) > 20 or any(not isinstance(value, str) for value in files)
            or len(set(files)) != len(files)): raise ValueError('Choose at most 20 distinct ordered layer paths')
    recipe = {}; values = {}; origins = {}; value_origins = {}; inputs = []
    for relative in files:
        path = studio.inside(project, relative); source = revisions.ref(project, path, 'configuration', 'layer')
        layer = read(path)
        revisions.fields(layer, {'format', 'schema_version', 'recipe', 'values'}, 'iteration layer')
        if layer.get('format') != LAYER or layer.get('schema_version') != 1: raise ValueError('Expected ambiance-iteration-layer schema_version 1')
        recipe = merge(recipe, layer.get('recipe', {}), origins, relative)
        values = merge(values, layer.get('values', {}), value_origins, relative)
        inputs.append(source)
    values = merge(values, config.get('values', {}), value_origins, 'request.values')
    recipe = merge(recipe, config.get('overrides', {}), origins, 'request.overrides')
    used = set()
    def variable(name):
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*', name): raise ValueError('Invalid value name')
        value = values
        for key in name.split('.'):
            if not isinstance(value, dict) or key not in value: raise ValueError('Unresolved value: '+name)
            value = value[key]
        used.add(name); return copy.deepcopy(value)
    def expand(value, depth=0):
        if depth > 40: raise ValueError('Configuration nesting exceeds 40 levels')
        if isinstance(value, dict):
            if '$value' in value:
                if set(value) != {'$value'}: raise ValueError('$value must be the entire mapping')
                result = variable(value['$value'])
                # Values are literal; recursive substitution is deliberately absent.
                return result
            return {key: expand(child, depth+1) for key, child in value.items()}
        if isinstance(value, list): return [expand(child, depth+1) for child in value]
        return value
    request = expand(recipe)
    if request.get('format') != 'ambiance-iteration-request' or request.get('schema_version') != 1:
        raise ValueError('Layers must resolve to ambiance-iteration-request schema_version 1')
    from .iteration_plan import validate_recipe
    validate_recipe({**{key: value for key, value in request.items() if key not in ['documents', 'audio_selection']},
                     'format': 'ambiance-iteration', 'schema_version': 2})
    if revisions.changed(project, inputs): raise ValueError('Config layers changed during resolution')
    return {'format': 'ambiance-iteration-resolution', 'schema_version': 1, 'ok': True, 'request': request, 'inputs': inputs,
            'recipe_origins': origins, 'value_origins': value_origins, 'used_values': sorted(used), 'values': values,
            'merge_policy': 'Ordered object merge; later values win, arrays replace in full, null removes a key; values are literal typed substitutions.'}


def expanded(project, request):
    return resolve(project, request)['request'] if request.get('format') == FORMAT else request
