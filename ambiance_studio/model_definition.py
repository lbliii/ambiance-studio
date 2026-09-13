"""Strict local model definitions and exact, contained compiler/source closure."""
from pathlib import Path
import math
import re

import studio
from .record_contracts import fields, identifier
from .file_identity import digest
from .assets import inspect_pack, read_asset

ROLES = ('solid', 'glass', 'flame', 'smoke', 'glow')


def number(value, label):
    if type(value) not in (float, int) or not math.isfinite(value):
        raise ValueError(f'{label} must be finite')
    return value


def vector(value, count, label):
    if not isinstance(value, list) or len(value) != count:
        raise ValueError(f'{label} needs {count} numbers')
    return [number(v, label) for v in value]


def affine(value):
    a, b, c, d, e, f = vector(value, 6, 'affine')
    scale = math.hypot(a, b)
    if scale <= 0 or a*d-b*c <= 0 or abs(c+b) > 1e-9*scale or abs(d-a) > 1e-9*scale:
        raise ValueError('Unsupported shear/reflection/nonuniform or singular model transform')
    return value


def ids(rows, key):
    if not isinstance(rows, list): raise ValueError(f'{key} collection must be an array')
    result = {}
    for row in rows:
        name = identifier(row[key])
        if name in result: raise ValueError(f'Duplicate {key}: {name}')
        result[name] = row
    return result


def part_path(value, empty=False):
    if not isinstance(value, list) or (not value and not empty): raise ValueError('Invalid part path')
    for name in value: identifier(name)
    return value


def control_value(control, value):
    kind = control['type']
    if kind == 'boolean':
        if type(value) is not bool: raise ValueError('Boolean control needs true/false')
    elif kind == 'number':
        number(value, 'control value')
        if not control['min'] <= value <= control['max']: raise ValueError('Control value out of range')
    elif kind == 'drawing':
        if value not in control['drawings']: raise ValueError('Undeclared control drawing')
    else: raise ValueError('Unsupported control type')
    return value


class DefinitionClosure:
    def __init__(self, root):
        self.root = Path(root).resolve(strict=True)
        self.files = {}
        self.models = {}
        self.versions = {}
        self.active = set()

    def file(self, base, name, pin=None):
        if not isinstance(name, str) or not name or Path(name).is_absolute():
            raise ValueError('Model paths must be relative to their document')
        candidate = base / name
        path = candidate.resolve(strict=True)
        if not path.is_relative_to(self.root): raise ValueError('Model dependency escapes source root')
        # Reject even internal symlinks: preserved lexical layout must be unambiguous.
        for entry in [candidate, *candidate.parents]:
            if entry == self.root.parent: break
            if entry.is_symlink(): raise ValueError('Model dependencies cannot use symlinks')
        if not path.is_file(): raise ValueError('Expected model dependency file')
        sha = digest(path)
        if pin is not None and (not re.fullmatch('[a-f0-9]{64}', str(pin)) or sha != pin):
            raise ValueError(f'Changed dependency pin: {name}')
        relative = path.relative_to(self.root).as_posix()
        if relative in self.files and self.files[relative] != sha: raise ValueError('Dependency changed during collection')
        if len(self.files) >= 4096 and relative not in self.files: raise ValueError('Local model dependency budget exceeded')
        self.files[relative] = sha
        return path

    def pack(self, base, pin):
        fields(pin, ['file', 'sha256', 'report_sha256'], 'drawing asset pin')
        asset_path = self.file(base, pin['file'], pin['sha256'])
        if asset_path.name != 'asset.json': raise ValueError('Drawing must pin compiler asset.json')
        folder = asset_path.parent
        self.file(folder, 'report.json', pin['report_sha256'])
        checked = inspect_pack(folder)
        if not checked['ok']: raise ValueError('Changed compiler outputs')
        asset, report = checked['asset'], checked['build']
        _, cels = read_asset(asset, folder)
        if any(cel.getchannel('A').getbbox() is None for cel in cels): raise ValueError('Model drawings need nonempty paint; transparent carriers are unsupported')
        recipe = studio.read(folder/'recipe.json')
        # These require typed project/receipt materialization beyond the local C1 slice.
        unsupported = set(recipe) & {'source_mapping', 'region_receipt', 'preparation_receipt', 'motion_preparation', 'cel_trim', 'edge_preparation'}
        if unsupported: raise ValueError(f'Unsupported local model compiler provenance: {sorted(unsupported)}')
        for name, sha in report['outputs'].items(): self.file(folder, name, sha)
        mapping = asset['registration_mapping']
        if mapping != report.get('registration_mapping'): raise ValueError('Compiler registration/report differ')
        inputs = recipe['input']
        names = [inputs['sheet']] if 'sheet' in inputs else inputs['frames']
        sources = asset['provenance']['sources']
        if len(names) != len(sources) or names != [s['file'] for s in sources]: raise ValueError('Compiler input order differs')
        for name, source in zip(names, sources): self.file(folder, name, source['sha256'])
        if recipe.get('registration_source'):
            ref = recipe['registration_source']; self.file(folder, ref['file'], ref['sha256'])
        if len(mapping['input_sources']) != len(sources): raise ValueError('Compiler source registration differs')
        from PIL import Image
        for source, mapped in zip(sources, mapping['input_sources']):
            if any(mapped[k] != source[k] for k in ['file', 'sha256']): raise ValueError('Compiler mapped source differs')
            with Image.open(folder/source['file']) as image:
                if image.size != (mapped['width'], mapped['height']): raise ValueError('Compiler source size differs')
        result = dict(asset)
        result['file'] = (folder/asset['file']).relative_to(self.root).as_posix()
        result['provenance'] = {**asset['provenance'], 'recipe': (folder/'recipe.json').relative_to(self.root).as_posix()}
        return result

    def model(self, path, expected=None):
        path = self.file(Path(path).parent, Path(path).name, expected and expected['sha256'])
        key = path.relative_to(self.root).as_posix()
        if key in self.active: raise ValueError('Definition cycle')
        raw = studio.read(path)
        if expected and any(raw[k] != expected[k] for k in ['model_id', 'version']): raise ValueError('Nested model identity differs')
        if key in self.models: return key
        if len(self.active) >= 32 or len(self.models) >= 128: raise ValueError('Local definition nesting/count budget exceeded')
        self.active.add(key)
        fields(raw, ['format', 'schema_version', 'model_id', 'version', 'kind', 'name', 'path_base', 'local_frame', 'root_part_id', 'drawings', 'parts', 'sockets', 'controls', 'variant_sets', 'paint_order', 'notes'], 'model definition')
        if raw['format'] != 'ambiance-model-definition' or type(raw['schema_version']) is not int or raw['schema_version'] != 1 or raw['path_base'] != 'document': raise ValueError('Unsupported model definition contract')
        identifier(raw['model_id']); identifier(raw['version'])
        if raw['kind'] not in ['prop', 'environment', 'character']: raise ValueError('Unsupported model kind')
        family = (raw['model_id'], raw['version'])
        if family in self.versions and self.versions[family] != self.files[key]: raise ValueError('Changed bytes under model version')
        self.versions[family] = self.files[key]
        frame = raw['local_frame']; fields(frame, ['size', 'pivot', 'clip'], 'local frame')
        if any(v <= 0 or v > 4096 for v in vector(frame['size'], 2, 'frame size')) or frame['clip'] != 'none': raise ValueError('Invalid local frame or unsupported clipping')
        vector(frame['pivot'], 2, 'frame pivot')
        drawings = ids(raw['drawings'], 'drawing_id')
        for drawing in drawings.values():
            fields(drawing, ['drawing_id', 'asset', 'cel_index', 'material_role', 'source_to_local'], 'drawing')
            if drawing['material_role'] not in ROLES: raise ValueError('Unknown material role')
            affine(drawing['source_to_local'])
            asset = self.pack(path.parent, drawing['asset'])
            cel = drawing['cel_index']
            if type(cel) is not int or not 0 <= cel < asset['atlas']['frame_count']: raise ValueError('Invalid drawing cel index')
            drawing['_asset'] = asset
        parts = ids(raw['parts'], 'part_id')
        for part in parts.values():
            nested = 'definition' in part
            allowed = ['part_id', 'definition', 'local_to_parent', 'mount'] if nested else ['part_id', 'drawing_id', 'cell_to_local', 'mount']
            fields(part, allowed, 'part')
            affine(part['local_to_parent' if nested else 'cell_to_local'])
            if nested:
                ref = part['definition']; fields(ref, ['model_id', 'version', 'file', 'sha256'], 'nested pin')
                part['_model'] = self.model(self.file(path.parent, ref['file'], ref['sha256']), ref)
            elif part['drawing_id'] not in drawings: raise ValueError('Unknown drawing ID')
            if 'mount' in part:
                fields(part['mount'], ['part_path', 'socket_id'], 'mount')
                part_path(part['mount']['part_path']); identifier(part['mount']['socket_id'])
        root = parts.get(raw['root_part_id'])
        if not root or 'drawing_id' not in root or 'mount' in root: raise ValueError('Model requires a drawing-bearing unmounted root')
        if any('mount' not in p for p in parts.values() if p is not root): raise ValueError('Every nonroot part needs a mount')
        sockets = ids(raw.get('sockets', []), 'socket_id')
        for sock in sockets.values():
            fields(sock, ['socket_id', 'part_path', 'cell_uv'], 'socket')
            part_path(sock['part_path'])
            if any(v < 0 or v > 1 for v in vector(sock['cell_uv'], 2, 'socket UV')): raise ValueError('Socket outside full cell')
        controls = ids(raw.get('controls', []), 'control_id')
        for control in controls.values():
            fields(control, ['control_id', 'type', 'unit', 'default', 'min', 'max', 'drawings', 'target'], 'control')
            target = control['target']; fields(target, ['part_path', 'channel', 'control_id'], 'control target')
            part_path(target['part_path'], empty='control_id' in target)
            if ('channel' in target) == ('control_id' in target): raise ValueError('Control needs one channel or forwarded control')
            if control['type'] == 'number':
                number(control['min'], 'minimum'); number(control['max'], 'maximum')
                if control['min'] > control['max']: raise ValueError('Invalid control range')
            if control['type'] == 'drawing':
                if not control['drawings'] or len(set(control['drawings'])) != len(control['drawings']): raise ValueError('Drawing control IDs must be unique')
            control_value(control, control['default'])
        sets = ids(raw.get('variant_sets', []), 'variant_set_id')
        for variants in sets.values():
            fields(variants, ['variant_set_id', 'default', 'variants'], 'variant set')
            variants_by_id = ids(variants['variants'], 'variant_id')
            if variants['default'] not in variants_by_id: raise ValueError('Invalid default variant')
            for variant in variants['variants']:
                fields(variant, ['variant_id', 'replacements'], 'variant')
                for replacement in variant['replacements']:
                    fields(replacement, ['part_path', 'drawing_id'], 'replacement')
                    part_path(replacement['part_path']); identifier(replacement['drawing_id'])
        if not isinstance(raw['paint_order'], list): raise ValueError('Paint order must be a list')
        for member in raw['paint_order']: part_path(member)
        self.models[key] = raw
        self.active.remove(key)
        return key

    def verify(self):
        for name, sha in self.files.items(): self.file(self.root, name, sha)
