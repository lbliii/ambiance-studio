"""A common lossless crop of all atlas cels, preserving source coordinates."""
import copy
import json
import math
import os
from pathlib import Path
import tempfile
import studio
from . import assets, revisions
from .project import locations, project_lock


def settings(receipt):
    left, top, right, bottom = receipt['crop']; width, height = right-left, bottom-top
    return {'registration': {'mode': 'fixed', 'point': [width/2, height/2], 'target': [.5, .5]},
            'output': {'cell_size': [width+4, height+4], 'columns': receipt['columns'], 'padding': 2, 'allow_upscale': False}}


def validate(path, expected, source_paths, recipe):
    path = Path(path).resolve()
    if studio.digest(path) != expected: raise ValueError('Cel trim receipt changed')
    data = studio.read(path)
    if data.get('format') != 'ambiance-cel-trim' or data.get('schema_version') != 1: raise ValueError('Unsupported cel trim receipt')
    project = next((p for p in path.parents if (p/'ambiance-project.json').exists()), None)
    if project is None: raise ValueError('Cel trim requires its project source tree')
    _, frames = assets.read_asset(data['source_asset'], project)
    if len(source_paths) != len(frames) or len(data['frames']) != len(frames): raise ValueError('Trim cel count differs')
    expected_settings = settings(data)
    if any(recipe[k] != expected_settings[k] for k in expected_settings): raise ValueError('Compiler settings change trim registration or scale')
    from PIL import Image
    dependencies = [{'path': str(studio.inside(project, data['source_asset']['file'])), 'sha256': data['source_asset']['sha256'], 'role': 'trim-source'}]
    cw, ch = frames[0].size; left, top, right, bottom = data['crop']
    if any(type(v) is not int for v in data['crop']) or not 0 <= left < right <= cw or not 0 <= top < bottom <= ch: raise ValueError('Invalid trim crop')
    for source, original, ref in zip(source_paths, frames, data['frames']):
        file = studio.inside(project, ref['path'])
        if file != Path(source).resolve() or studio.digest(file) != ref['sha256']: raise ValueError('Trim source cel changed')
        bounds = original.getchannel('A').getbbox()
        if bounds and not (left <= bounds[0] and top <= bounds[1] and right >= bounds[2] and bottom >= bounds[3]): raise ValueError('Trim would remove painted pixels')
        with Image.open(file) as image:
            if image.convert('RGBA').tobytes() != original.crop(data['crop']).tobytes() or image.size != (right-left, bottom-top): raise ValueError('Trim cel pixels differ from the recorded source crop')
        dependencies.append({'path': str(file), 'sha256': ref['sha256'], 'role': 'trim-cel'})
    return {'receipt': data, 'dependencies': dependencies}


def prepare(project, layer_id, asset_id, out):
    project = project.resolve(); out = Path(out).resolve(); revisions.identifier(asset_id)
    if out.exists() or not out.is_relative_to(project): raise ValueError('Choose a fresh trim directory inside the project')
    with project_lock(project):
        scene_path, catalog_path = locations(project); scene = studio.read(scene_path); catalog = studio.read(catalog_path)
        inputs = {p: studio.digest(p) for p in [scene_path, catalog_path]}
        layers = [l for l in scene['layers'] if l['id'] == layer_id]
        if len(layers) != 1: raise ValueError('Choose one existing layer')
        layer = layers[0]; asset = next(a for a in catalog['assets'] if a['id'] == layer['asset'])
        from .finishing import relationship_ids
        finish = scene.get('finishing') or {}
        related = relationship_ids(finish, scene.get('bindings'))
        if layer_id in related['layers'] or asset['id'] in finish.get('assets', {}) or layer.get('group') in related['groups']:
            raise ValueError('Trim of a finishing/binding participant needs coordinated mask and companion registration; prepare that explicitly before trimming')
        if any(a['id'] == asset_id for a in catalog['assets']): raise ValueError('Use a new asset ID')
        if not asset.get('atlas'): raise ValueError('Cel trim requires an atlas')
        source, frames = assets.read_asset(asset, project); inputs[source] = asset['sha256']; cw, ch = frames[0].size
        sockets = {**asset.get('sockets', {}), **layer.get('sockets', {})}; anchor = layer.get('anchor', asset.get('pivot', [.5, .5]))
        points = [anchor]
        for value in sockets.values(): points.extend(value['frames'] if isinstance(value, dict) else [value])
        bounds = [b for f in frames if (b := f.getchannel('A').getbbox())]
        bounds += [(max(0, math.floor(u*cw)-1), max(0, math.floor(v*ch)-1), min(cw, math.ceil(u*cw)+1), min(ch, math.ceil(v*ch)+1)) for u, v in points]
        left, top = min(b[0] for b in bounds), min(b[1] for b in bounds)
        right, bottom = max(b[2] for b in bounds), max(b[3] for b in bounds)
        nw, nh = right-left+4, bottom-top+4
        remap = lambda uv: [(uv[0]*cw-left+2)/nw, (uv[1]*ch-top+2)/nh]
        mapped = {name: {'frames': [remap(uv) for uv in value['frames']]} if isinstance(value, dict) else remap(value) for name, value in sockets.items()}
        values = {'asset': asset_id, 'width': layer['width']*nw/cw, 'height': layer['height']*nh/ch, 'anchor': remap(anchor), 'sockets': mapped}
        out.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.cel-trim-', dir=out.parent) as temporary:
            bundle = Path(temporary)/'bundle'; bundle.mkdir(); (bundle/'frames').mkdir()
            refs = []
            for index, frame in enumerate(frames):
                relative = f'frames/{index:03d}.png'; file = bundle/relative; frame.crop((left, top, right, bottom)).save(file)
                refs.append({'path': str((out/relative).relative_to(project)), 'sha256': studio.digest(file)})
            receipt = dict(format='ambiance-cel-trim', schema_version=1, source_asset=asset, source_scene_sha256=inputs[scene_path],
                           layer=layer_id, crop=[left, top, right, bottom], columns=min(4, len(frames)), frames=refs,
                           source_cell_to_trim_cell=[1, 0, 0, 1, 2-left, 2-top], placement=values,
                           fidelity='Exact retained RGBA pixels with transparent padding; no per-cel scaling.')
            studio.write(bundle/'trim.json', receipt)
            recipe = dict(version=1, id=asset_id, input={'frames': [f'frames/{i:03d}.png' for i in range(len(frames))], 'allow_opaque': True},
                          **settings(receipt), cel_trim={'file': 'trim.json', 'sha256': studio.digest(bundle/'trim.json')})
            studio.write(bundle/'recipe.json', recipe)
            studio.write(bundle/'placement.json', {'version': 1, 'operations': [{'op': 'set', 'layer': layer_id, 'values': values}]})
            if any(studio.digest(p) != h for p, h in inputs.items()): raise ValueError('Trim source changed during preparation')
            bundle.rename(out)
    return {'ok': True, 'recipe': str(out/'recipe.json'), 'receipt': str(out/'trim.json'), 'placement': str(out/'placement.json'),
            'expected_scene_sha256': inputs[scene_path], 'old_cell': [cw, ch], 'new_cell': [nw, nh], 'area_ratio': nw*nh/(cw*ch),
            'next': 'Build and inspect the pack, admit it, then dry-run the placement batch with the recorded scene hash. No scene or catalog was changed.'}
