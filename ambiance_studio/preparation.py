"""One source-coordinate separation recipe for CLI builds and interactive drafts."""
import base64
import io
import json
import math
from pathlib import Path
import re

from . import asset_prep as prep
from .edge_quality import fresh_output, integer, number

ROOT = Path(__file__).resolve().parents[1]
FORMAT = 'ambiance-asset-preparation'
MASKS = ('removal', 'cutout', 'occluder')
MAX_PIXELS = 8_388_608


def png(image):
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    return buffer.getvalue()


def image_record(project, path):
    project = Path(project).resolve()
    _, info = prep.decoded(path)
    return prep.identity(project, path, info)


def initial_recipe(project, source, backing, alignment=None):
    source_ref = image_record(project, source)
    return {
        'format': FORMAT, 'version': 1, 'path_base': 'project',
        'title': 'Prepare a movable part',
        'source': source_ref, 'backing': image_record(project, backing),
        'backing_to_source': alignment or [1, 0, 0, 1, 0, 0],
        'resampling': 'bicubic',
        'masks': {name: {'polygons': []} for name in MASKS},
        'motion': {'pivot': [source_ref['width']/2, source_ref['height']/2],
                   'delta': [0, -source_ref['height']*.025],
                   'rotation_degrees': 0, 'seconds': 4},
    }


def vector(value, name, bounds):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f'{name} needs two source-pixel coordinates')
    return [number(v, name, *bound) for v, bound in zip(value, bounds)]


def references(recipe):
    yield 'source', recipe['source']
    yield 'backing', recipe['backing']
    for name in MASKS:
        if 'image' in recipe['masks'][name]:
            yield name, recipe['masks'][name]['image']


def validate(recipe):
    prep.fields(recipe, ['format', 'version', 'path_base', 'title', 'source', 'backing',
                         'backing_to_source', 'resampling', 'masks', 'motion'], 'preparation recipe')
    if recipe.get('format') != FORMAT or type(recipe.get('version')) is not int or recipe['version'] != 1 or recipe.get('path_base') != 'project':
        raise ValueError('Expected ambiance-asset-preparation version 1 with project-relative inputs')
    if not isinstance(recipe.get('title'), str) or not 1 <= len(recipe['title']) <= 160:
        raise ValueError('Preparation title must contain 1–160 characters')
    prep.fields(recipe.get('masks'), MASKS, 'masks')
    if set(recipe['masks']) != set(MASKS):
        raise ValueError('Keep removal, cutout and occluder masks explicit and separate')
    for name in MASKS:
        prep.fields(recipe['masks'][name], ['image', 'polygons'], name+' mask')
    for role, ref in references(recipe):
        prep.fields(ref, ['file', 'sha256', 'width', 'height'], role+' identity')
        if not isinstance(ref.get('file'), str) or not ref['file'] or Path(ref['file']).is_absolute() or '..' in Path(ref['file']).parts:
            raise ValueError('Input files must be project-relative without parent traversal')
        digest = ref.get('sha256')
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
            raise ValueError('Input identities require a SHA-256')
        w = integer(ref.get('width'), role+' width', 1, 4096)
        h = integer(ref.get('height'), role+' height', 1, 4096)
        if w*h > MAX_PIXELS:
            raise ValueError('Preparation input exceeds the pixel budget')
    w, h = recipe['source']['width'], recipe['source']['height']
    matrix = prep.affine(recipe.get('backing_to_source'))
    if any(abs(v) > 32768 for v in matrix):
        raise ValueError('Backing registration coefficients exceed 32768')
    if recipe.get('resampling') not in ('nearest', 'bicubic'):
        raise ValueError('Preparation resampling must be nearest or bicubic')
    total = 0
    for name in MASKS:
        spec = recipe['masks'][name]
        if 'image' in spec and [spec['image']['width'], spec['image']['height']] != [w, h]:
            raise ValueError('Imported masks must have full source dimensions')
        polygons = spec.get('polygons')
        if not isinstance(polygons, list) or len(polygons) > 128:
            raise ValueError('Each mask supports at most 128 polygons')
        for poly in polygons:
            prep.fields(poly, ['operation', 'points'], 'mask polygon')
            if poly.get('operation') not in ('add', 'subtract'):
                raise ValueError('Mask polygon operation must be add or subtract')
            points = poly.get('points')
            if not isinstance(points, list) or not 3 <= len(points) <= 512:
                raise ValueError('A polygon needs 3–512 vertices')
            for point in points:
                vector(point, 'Polygon vertex', [(0, w-1), (0, h-1)])
            total += len(points)
    if total > 8192:
        raise ValueError('Preparation supports at most 8192 polygon vertices')
    motion = recipe.get('motion')
    prep.fields(motion, ['pivot', 'delta', 'rotation_degrees', 'seconds'], 'proof motion')
    vector(motion.get('pivot'), 'Pivot', [(0, w), (0, h)])
    vector(motion.get('delta'), 'Movement', [(-w, w), (-h, h)])
    number(motion.get('rotation_degrees'), 'Rotation', -180, 180)
    seconds = number(motion.get('seconds'), 'Loop seconds', 1, 30)
    if not float(seconds*30).is_integer() or int(seconds*30) % 2:
        raise ValueError('Proof duration needs an even whole number of 30 fps frames so maximum movement lands on a frame')
    return recipe


def load_inputs(project, recipe):
    project = Path(project).resolve()
    validate(recipe)
    result = {}
    for role, ref in references(recipe):
        path = prep.project_file(project, ref['file'])
        result[role] = path.read_bytes()
    decode_inputs(recipe, result)
    return result


def decode_inputs(recipe, inputs):
    from PIL import Image
    decoded = {}
    for role, ref in references(recipe):
        data = inputs[role]
        if prep.sha(data) != ref['sha256']:
            raise ValueError(f'Preparation input changed: {ref["file"]}')
        with Image.open(io.BytesIO(data)) as image:
            if image.size != (ref['width'], ref['height']) or getattr(image, 'n_frames', 1) != 1:
                raise ValueError('Preparation requires still images matching recorded dimensions')
            if role in MASKS and image.mode != 'L':
                raise ValueError('Imported masks must be grayscale L images')
            decoded[role] = image.convert('RGBA') if role not in MASKS else image.copy()
    return decoded


def evaluate(recipe, inputs):
    """Rasterize both saved builds and browser drafts through this one implementation."""
    from PIL import Image, ImageChops, ImageDraw
    validate(recipe)
    decoded = decode_inputs(recipe, inputs)
    original = decoded['source']
    masks = {}
    for name in MASKS:
        from .masks import rasterize
        masks[name] = rasterize(recipe['masks'][name], original.size, decoded.get(name))
    registered = prep.resample(decoded['backing'], original.size, recipe['backing_to_source'], recipe['resampling'])
    patch = registered.copy()
    patch.putalpha(ImageChops.multiply(patch.getchannel('A'), masks['removal']))
    background = Image.alpha_composite(original, patch)
    parts = {}
    for name in ('cutout', 'occluder'):
        part = original.copy()
        part.putalpha(ImageChops.multiply(original.getchannel('A'), masks[name]))
        parts[name] = part
    rest = Image.alpha_composite(Image.alpha_composite(background, parts['cutout']), parts['occluder'])
    diff = ImageChops.difference(rest, original)
    channels = diff.split()
    change = channels[0]
    for channel in channels[1:]:
        change = ImageChops.lighter(change, channel)
    change = change.point(lambda n: 255 if n else 0)
    overlay = Image.new('RGBA', original.size, '#ee508a')
    overlay.putalpha(change.point(lambda n: 190 if n else 0))
    uncovered = ImageChops.subtract(masks['cutout'], masks['removal'])
    missing = ImageChops.multiply(masks['removal'], ImageChops.invert(registered.getchannel('A')))
    count = lambda mask: sum(mask.histogram()[1:])
    facts = {'changed_rest_pixels': count(change), 'cutout_outside_removal_pixels': count(uncovered),
             'removal_without_opaque_backing_pixels': count(missing),
             'mask_pixels': {name: count(mask) for name, mask in masks.items()}}
    warnings = []
    if not facts['mask_pixels']['cutout']:
        warnings.append('The cutout is empty. Draw or import its retained-object mask.')
    if not facts['mask_pixels']['removal']:
        warnings.append('The removal mask is empty; the original painted object remains in the background.')
    if facts['cutout_outside_removal_pixels']:
        warnings.append('Some cutout pixels lie outside the removal mask. Inspect the object-hidden view for old paint.')
    if facts['removal_without_opaque_backing_pixels']:
        warnings.append('The registered backing does not fully cover the removal region. Inspect alignment and alpha.')
    images = {'source': original, 'registered-backing': registered, 'backing': background,
              **parts, 'rest': rest, 'difference': Image.alpha_composite(original, overlay),
              **{name+'-mask': mask for name, mask in masks.items()}}
    return images, facts, warnings


def proof_scene(recipe, assets):
    w, h = recipe['source']['width'], recipe['source']['height']
    motion = recipe['motion']; seconds = motion['seconds']
    layers = []
    for name in ('backing', 'cutout', 'occluder'):
        pivot = motion['pivot'] if name == 'cutout' else [0, 0]
        layer = {'id': name, 'asset': name, 'x': pivot[0]/w, 'y': pivot[1]/h,
                 'width': 1, 'height': 1, 'anchor': [pivot[0]/w, pivot[1]/h],
                 'scale': 1, 'rotation': 0, 'opacity': 1, 'visible': True,
                 'blend': 'source-over', 'depth': 0}
        if name == 'cutout':
            layer['tracks'] = {}
            for field, base, delta in [('x', layer['x'], motion['delta'][0]/w),
                                        ('y', layer['y'], motion['delta'][1]/h),
                                        ('rotation', 0, math.radians(motion['rotation_degrees']))]:
                layer['tracks'][field] = {'interpolation': 'smoothstep',
                    'keys': [[0, base], [seconds/4, base], [seconds/2, base+delta],
                             [seconds*3/4, base], [seconds, base]]}
        layers.append(layer)
    scene = {'version': 1, 'id': 'preparation-proof', 'title': recipe['title'],
             'canvas': {'width': w, 'height': h, 'fps': 30, 'loop_seconds': seconds, 'background': '#18232c'},
             'camera': {'overscan': 1, 'x_amplitude': 0, 'y_amplitude': 0, 'zoom_amplitude': 0},
             'groups': [], 'layers': layers}
    return scene, {'version': 1, 'assets': assets}


def encoded_result(recipe, inputs):
    images, facts, warnings = evaluate(recipe, inputs)
    binaries = {name: png(image) for name, image in images.items()}
    assets = [{'id': name, 'kind': 'plate', 'file': f'images/{name}.png',
               'width': images[name].width, 'height': images[name].height,
               'bytes': len(binaries[name]), 'sha256': prep.sha(binaries[name])}
              for name in ('backing', 'cutout', 'occluder')]
    scene, catalog = proof_scene(recipe, assets)
    return binaries, {'scene': scene, 'catalog': catalog, 'facts': facts, 'warnings': warnings}


def build(project, out, recipe_path=None, source=None, backing=None, alignment=None):
    project, out = Path(project).resolve(), Path(out).resolve()
    prep.relative(project, out)
    if out.exists():
        raise ValueError(f'Output exists; choose a fresh directory: {out}')
    if recipe_path is not None:
        if source is not None or backing is not None or alignment is not None:
            raise ValueError('Use an exported recipe, or source/backing inputs, not both')
        recipe_path = Path(recipe_path)
        recipe_bytes = recipe_path.read_bytes()
        recipe = json.loads(recipe_bytes)
    else:
        if source is None or backing is None:
            raise ValueError('Supply SOURCE and --backing FILE, or --recipe FILE')
        recipe = initial_recipe(project, source, backing, alignment)
        recipe_bytes = (json.dumps(recipe, indent=2, allow_nan=False)+'\n').encode()
    inputs = load_inputs(project, recipe)
    binaries, result = encoded_result(recipe, inputs)
    with fresh_output(out) as stage:
        (stage/'images').mkdir(); (stage/'snapshots').mkdir(); (stage/'compiler').mkdir()
        (stage/'recipe.json').write_bytes(recipe_bytes)
        for role, data in inputs.items():
            (stage/'snapshots'/f'{role}.bin').write_bytes(data)
        for name, data in binaries.items():
            (stage/'images'/f'{name}.png').write_bytes(data)
        # A self-contained scene preview project uses exactly these derivative bytes.
        preview = stage/'preview-project'; preview.mkdir()
        (preview/'images').mkdir()
        for name in ('backing', 'cutout', 'occluder'):
            (preview/'images'/f'{name}.png').write_bytes(binaries[name])
        prep.write(preview/'scene.json', result['scene'])
        prep.write(preview/'catalog.json', result['catalog'])
        prep.write(preview/'ambiance-project.json', {'version': 1, 'scene': 'scene.json', 'catalog': 'catalog.json'})
        from .scene_runtime import scene_bridge
        scene_bridge('inspect', result['scene'], result['catalog'], {'full': False})
        w, h = recipe['source']['width'], recipe['source']['height']
        for name in ('backing', 'cutout', 'occluder'):
            mapping = {'format': 'ambiance-asset-source-mapping', 'version': 1, 'path_base': 'project',
                       'reference': recipe['source'], 'image': {
                           'file': prep.relative(project, out/'images'/f'{name}.png'),
                           'sha256': prep.sha(binaries[name]), 'width': w, 'height': h},
                       'image_to_reference': [1, 0, 0, 1, 0, 0],
                       'registration': 'Full reference canvas retained; preparation receipt owns the rebuild inputs.'}
            prep.write(stage/'compiler'/f'{name}-mapping.json', mapping)
            prep.write(stage/'compiler'/f'{name}.json', {
                'version': 1, 'id': f'{re.sub(r"[^a-z0-9-]+", "-", out.name.lower()).strip("-") or "prepared"}-{name}',
                'input': {'frames': [f'../images/{name}.png'], 'allow_opaque': True},
                'source_mapping': {'file': f'{name}-mapping.json',
                                   'sha256': prep.sha((stage/'compiler'/f'{name}-mapping.json').read_bytes())},
                'registration': {'mode': 'fixed', 'point': [w/2, h/2], 'target': [.5, .5]},
                'output': {'cell_size': [min(4096, w+4), min(4096, h+4)], 'columns': 1, 'padding': 2}})
        # Capture the shared renderer and UI, so an artifact never uses a later engine silently.
        for name in ('engine.mjs', 'finishing.mjs', 'bindings.mjs', 'views.mjs', 'preparation-workbench.mjs', 'preparation-workbench.css'):
            (stage/name).write_bytes((ROOT/'editor'/name).read_bytes())
        (stage/'index.html').write_bytes((ROOT/'editor/preparation-workbench.html').read_bytes())
        prep.write(stage/'workbench.json', {'recipe': recipe, **result})
        report = {'ok': True, 'format': FORMAT+'-artifact', 'version': 1,
                  'recipe_sha256': prep.sha(recipe_bytes), 'facts': result['facts'], 'warnings': result['warnings'],
                  'implementation': {'python': __import__('sys').version.split()[0],
                                     'pillow': __import__('PIL').__version__,
                                     'modules': {name: prep.sha((ROOT/'ambiance_studio'/name).read_bytes())
                                                 for name in ('preparation.py', 'asset_prep.py')}},
                  'inputs': {role: {'file': f'snapshots/{role}.bin', **{'sha256': prep.sha(data)}} for role, data in inputs.items()},
                  'outputs': {str(path.relative_to(stage)): prep.sha(path.read_bytes()) for path in sorted(stage.rglob('*')) if path.is_file()},
                  'limits': ['One rigid part and fixed foreground; proof motion is independent of any production scene.',
                             'No new paint, inferred segmentation, registration or artistic approval.',
                             'Compiler source mappings pin source and derivative; keep this complete artifact for preparation provenance.']}
        prep.write(stage/'preparation-report.json', report)
        # Re-resolve every project reference to catch concurrent writes or symlink retargets.
        for role, ref in references(recipe):
            if prep.project_file(project, ref['file']).read_bytes() != inputs[role]:
                raise ValueError('Preparation input changed during the build')
        if recipe_path is not None and recipe_path.read_bytes() != recipe_bytes:
            raise ValueError('Preparation recipe changed during the build')
    return {'ok': True, 'directory': str(out), 'recipe': str(out/'recipe.json'),
            'report': str(out/'preparation-report.json'), 'preview_project': str(out/'preview-project'),
            'facts': result['facts'], 'warnings': result['warnings'],
            'next': f'./ambiance preview --prepare {out} --port 8785'}


def artifact(directory):
    directory = Path(directory).resolve()
    report = prep.load(directory/'preparation-report.json')
    if report.get('format') != FORMAT+'-artifact' or report.get('version') != 1 or report.get('ok') is not True:
        raise ValueError('Expected a completed preparation artifact')
    files = {}
    for name, digest in report['outputs'].items():
        path = prep.project_file(directory, name)
        data = path.read_bytes()
        if prep.sha(data) != digest:
            raise ValueError(f'Preparation artifact changed: {name}')
        files[name] = data
    recipe = json.loads(files['recipe.json']); validate(recipe)
    if prep.sha(files['recipe.json']) != report['recipe_sha256']:
        raise ValueError('Preparation recipe identity differs from receipt')
    inputs = {}
    for role, ref in references(recipe):
        record = report['inputs'][role]
        data = files[record['file']]
        if prep.sha(data) != record['sha256'] or record['sha256'] != ref['sha256']:
            raise ValueError('Preparation snapshot identity differs from recipe')
        inputs[role] = data
    decode_inputs(recipe, inputs)
    # Live edits must use the exact saved rasterizer; static evidence stays accessible on disk.
    for name, digest in report['implementation']['modules'].items():
        if name not in ('preparation.py', 'asset_prep.py') or prep.sha((ROOT/'ambiance_studio'/name).read_bytes()) != digest:
            raise ValueError('Preparation implementation changed; rebuild a fresh workbench before live editing')
    if report['implementation']['pillow'] != __import__('PIL').__version__:
        raise ValueError('Preparation Pillow version changed; rebuild before live editing')
    return recipe, inputs, files


def preview_result(recipe, original_recipe, inputs):
    validate(recipe)
    if dict(references(recipe)) != dict(references(original_recipe)):
        raise ValueError('Live drafts must retain captured input identities; use the CLI for different sources or mask files')
    binaries, result = encoded_result(recipe, inputs)
    return {**result, 'recipe': recipe,
            'images': {name: 'data:image/png;base64,'+base64.b64encode(data).decode() for name, data in binaries.items()}}
