"""Deterministic sprite-edge diagnostics and opt-in, reversible raster derivatives.

These operations measure pixels and produce review evidence. They do not infer a
matte, select an artistic repair, or certify a sprite's appearance.
"""
from contextlib import contextmanager
import ctypes
import html
import io
import json
import math
import os
from pathlib import Path
import sys
import tempfile

from . import asset_prep as prep


MAX_PROOF_PIXELS = 240_000_000


def pixels(image):
    return image.get_flattened_data() if hasattr(image, 'get_flattened_data') else image.getdata()


def promote_exclusive(stage, out):
    """Atomically publish a fresh directory without replacing a concurrent owner."""
    library = ctypes.CDLL(None, use_errno=True)
    if sys.platform == 'darwin':
        call = library.renamex_np
        call.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        call.restype = ctypes.c_int
        result = call(os.fsencode(stage), os.fsencode(out), 4)  # RENAME_EXCL
    elif sys.platform.startswith('linux') and hasattr(library, 'renameat2'):
        call = library.renameat2
        call.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        call.restype = ctypes.c_int
        result = call(-100, os.fsencode(stage), -100, os.fsencode(out), 1)  # AT_FDCWD, RENAME_NOREPLACE
    else:
        raise ValueError('Atomic edge publication requires macOS renamex_np or Linux renameat2')
    if result:
        error = ctypes.get_errno()
        raise ValueError(f'Cannot publish fresh edge output: {os.strerror(error)}: {out}')


@contextmanager
def fresh_output(out):
    out = Path(out).resolve()
    if out.exists():
        raise ValueError(f'Output exists; choose a fresh directory: {out}')
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.edge-quality-', dir=out.parent) as temporary:
        stage = Path(temporary)/'result'; stage.mkdir()
        yield stage
        promote_exclusive(stage, out)


def integer(value, name, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'{name} must be an integer in [{low}, {high}]')
    return value


def number(value, name, low, high):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{name} must be finite in [{low}, {high}]')
    return value


def alpha_facts(image):
    alpha = image.getchannel('A'); histogram = alpha.histogram()
    border = [alpha.getpixel((x, 0)) for x in range(alpha.width)]
    if alpha.height > 1:
        border += [alpha.getpixel((x, alpha.height-1)) for x in range(alpha.width)]
    for y in range(1, alpha.height-1):
        border.append(alpha.getpixel((0, y)))
        if alpha.width > 1:
            border.append(alpha.getpixel((alpha.width-1, y)))
    return {
        'alpha_min': next(i for i, n in enumerate(histogram) if n),
        'alpha_max': next(i for i in range(255, -1, -1) if histogram[i]),
        'transparent_pixels': histogram[0], 'partial_pixels': sum(histogram[1:255]),
        'opaque_pixels': histogram[255], 'alpha_content_bounds': alpha.getbbox(),
        'nonzero_border_pixels': sum(v > 0 for v in border),
        'alpha_mass_pixels': sum(i*n for i, n in enumerate(histogram))/255,
    }


def isolated_resize(image, size):
    """Filter an isolated cel in premultiplied space, never an adjacent atlas cell."""
    from PIL import Image
    if image.size == tuple(size):
        return image.copy()
    return image.convert('RGBa').resize(tuple(size), Image.Resampling.LANCZOS).convert('RGBA')


def padded_cell(image, padding):
    from PIL import Image
    padding = integer(padding, 'padding_px', 0, 256)
    if not padding:
        return image.copy()
    out = Image.new('RGBA', (image.width+2*padding, image.height+2*padding))
    out.paste(image, (padding, padding))  # Copy straight RGBA, including zero-alpha RGB.
    return out


def sheet_layout(spec, size):
    prep.fields(spec, ['columns', 'rows', 'cell_width', 'cell_height', 'frame_count'], 'sheet layout')
    columns = integer(spec.get('columns'), 'columns', 1, 512)
    rows = integer(spec.get('rows'), 'rows', 1, 512)
    width = integer(spec.get('cell_width'), 'cell_width', 1, 16384)
    height = integer(spec.get('cell_height'), 'cell_height', 1, 16384)
    count = integer(spec.get('frame_count'), 'frame_count', 1, min(512, columns*rows))
    if size != (columns*width, rows*height):
        raise ValueError('Explicit sheet layout must match the decoded source dimensions exactly')
    return columns, rows, width, height, count


def cel_rect(index, columns, width, height):
    x, y = index % columns * width, index // columns * height
    return (x, y, x+width, y+height)


def changed_pixels(before, after):
    return sum(a != b for a, b in zip(pixels(before), pixels(after)))


def repair_cell(image, spec):
    """Return a separate cel; neutral settings preserve every input RGBA byte."""
    from PIL import ImageFilter
    result = image.copy(); decontamination = spec['decontamination']
    strength = decontamination['strength']
    if strength:
        matte = decontamination['matte_rgb']; floor = decontamination['alpha_floor']
        colors = []
        for r, g, b, alpha in pixels(image):
            if 0 < alpha < 255:
                a = alpha/255; denominator = max(a, floor)
                # The declared model is foreground composited over matte in
                # encoded sRGB, then stored alongside the original alpha.
                foreground = [max(0, min(255, (c-(1-a)*m)/denominator)) for c, m in zip((r, g, b), matte)]
                r, g, b = [round(c+(f-c)*strength) for c, f in zip((r, g, b), foreground)]
            colors.append((r, g, b, alpha))
        result.putdata(colors)
    result = padded_cell(result, spec['padding_px'])
    alpha = result.getchannel('A')
    choke = spec['alpha']['choke_px']; feather = spec['alpha']['feather_px']
    if choke:
        # A temporary transparent guard makes outside-the-cell alpha zero.
        from PIL import Image
        guard = Image.new('L', (alpha.width+2*choke, alpha.height+2*choke))
        guard.paste(alpha, (choke, choke))
        alpha = guard.filter(ImageFilter.MinFilter(2*choke+1)).crop((choke, choke, choke+alpha.width, choke+alpha.height))
    if feather:
        # Blur only the alpha; expand the guard to prevent edge clamping from
        # implying opaque material outside the cel.
        from PIL import Image
        guard_size = math.ceil(feather*4)+1
        result.putalpha(alpha)
        guard = Image.new('RGBa', (alpha.width+2*guard_size, alpha.height+2*guard_size))
        guard.paste(result.convert('RGBa'), (guard_size, guard_size))
        blurred = guard.filter(ImageFilter.GaussianBlur(feather)).crop((guard_size, guard_size, guard_size+alpha.width, guard_size+alpha.height)).convert('RGBA')
        alpha = blurred.getchannel('A')
        # Only newly visible pixels borrow color from the premultiplied blur;
        # retained fur/paint keeps its RGB. Blurring alpha alone reveals black
        # or a stored matte color in transparent padding.
        result.putdata([(*((r, g, b) if a else (br, bg, bb)), ba)
                        for (r, g, b, a), (br, bg, bb, ba) in zip(pixels(result), pixels(blurred))])
    if choke or feather:
        result.putalpha(alpha)
    return result


def repair_spec(recipe, size):
    prep.fields(recipe, ['format', 'version', 'layout', 'alpha', 'decontamination', 'padding_px'], 'edge repair recipe')
    if recipe.get('format') != 'ambiance-edge-repair' or recipe.get('version') != 1:
        raise ValueError('Expected ambiance-edge-repair version 1')
    layout = sheet_layout(recipe.get('layout'), size)
    alpha = recipe.get('alpha', {})
    prep.fields(alpha, ['feather_px', 'choke_px'], 'alpha operation')
    alpha = {'feather_px': number(alpha.get('feather_px', 0), 'feather_px', 0, 8),
             'choke_px': integer(alpha.get('choke_px', 0), 'choke_px', 0, 8)}
    decontamination = recipe.get('decontamination', {})
    prep.fields(decontamination, ['strength', 'matte_rgb', 'alpha_floor', 'color_space'], 'decontamination')
    strength = number(decontamination.get('strength', 0), 'decontamination strength', 0, 1)
    matte = decontamination.get('matte_rgb')
    if matte is not None and (not isinstance(matte, list) or len(matte) != 3 or any(type(c) is not int or not 0 <= c <= 255 for c in matte)):
        raise ValueError('matte_rgb must be three encoded sRGB integers in [0,255]')
    if strength and matte is None:
        raise ValueError('Nonzero decontamination requires an explicitly declared matte_rgb')
    if decontamination.get('color_space', 'srgb') != 'srgb':
        raise ValueError('Decontamination currently supports the encoded srgb matte model only')
    decontamination = {'strength': strength, 'matte_rgb': matte,
                      'alpha_floor': number(decontamination.get('alpha_floor', 1/255), 'alpha_floor', 1/255, 1),
                      'color_space': 'srgb'}
    padding = integer(recipe.get('padding_px', 0), 'padding_px', 0, 256)
    if (layout[2]+2*padding)*(layout[3]+2*padding)*layout[0]*layout[1] > 100_000_000:
        raise ValueError('Padded sheet exceeds 100 million pixels; split the sheet explicitly')
    return layout, {'alpha': alpha, 'decontamination': decontamination, 'padding_px': padding}


def fingerprint(path):
    path = Path(path).resolve()
    data = path.read_bytes()
    return {'resolved_path': str(path), 'path_base': 'shell', 'sha256': prep.sha(data), 'bytes': len(data)}


def check_inputs(records):
    for record in records:
        path = Path(record['resolved_path'])
        if not path.is_file() or prep.sha(path.read_bytes()) != record['sha256']:
            raise ValueError(f'Edge workflow input changed during preparation: {path}')


def validate_edge_preparation(report_path, expected_sha, input_paths=None):
    """Validate the explicit preparation chain shared by compiler and revisions.

    Dependency paths are returned as absolute Paths; manifest paths themselves
    are portable relative to the report. No filenames are inferred from prose.
    """
    from PIL import Image
    report_path = Path(report_path).resolve(); data = report_path.read_bytes()
    if not isinstance(expected_sha, str) or prep.sha(data) != expected_sha:
        raise ValueError('Edge preparation report changed or its hash is missing')
    report = json.loads(data)
    if report.get('format') != 'ambiance-edge-repair-result' or report.get('version') != 1:
        raise ValueError('Expected ambiance-edge-repair-result version 1')
    provenance = report.get('provenance')
    names = ['source', 'recipe', 'original_snapshot', 'recipe_snapshot', 'atlas']
    prep.fields(provenance, ['path_base', *names], 'edge preparation provenance')
    if provenance.get('path_base') != 'report' or any(name not in provenance for name in names):
        raise ValueError('Edge preparation needs explicit report-relative source, recipe, snapshot and atlas identities')
    dependencies = [{'path': report_path, 'sha256': expected_sha, 'role': 'edge-preparation-report'}]
    resolved = {}
    for name in names:
        record = provenance[name]; prep.fields(record, ['file', 'sha256'], f'edge preparation {name}')
        if not isinstance(record.get('file'), str) or Path(record['file']).is_absolute() or not record['file']:
            raise ValueError('Edge preparation identity files must be report-relative')
        path = (report_path.parent/record['file']).resolve()
        if not path.is_file() or not isinstance(record.get('sha256'), str) or prep.sha(path.read_bytes()) != record['sha256']:
            raise ValueError(f'Edge preparation {name} changed or is missing')
        dependencies.append({'path': path, 'sha256': record['sha256'], 'role': 'edge-preparation-'+name.replace('_', '-')})
        resolved[name] = path
    for original, snapshot in [('source', 'original_snapshot'), ('recipe', 'recipe_snapshot')]:
        if provenance[original]['sha256'] != provenance[snapshot]['sha256'] or report.get(original, {}).get('sha256') != provenance[original]['sha256']:
            raise ValueError(f'Edge preparation {original} and snapshot identities differ')
    if report.get('original_bytes_snapshot') != provenance['original_snapshot']['file']:
        raise ValueError('Edge preparation original snapshot declaration differs')
    outputs = report.get('outputs', {})
    for name in ['original_snapshot', 'recipe_snapshot', 'atlas']:
        if outputs.get(provenance[name]['file']) != provenance[name]['sha256']:
            raise ValueError(f'Edge preparation {name} is not bound by the output receipt')
    if input_paths is not None and [Path(p).resolve() for p in input_paths] != [resolved['atlas']]:
        raise ValueError('Edge preparation must identify the exact single compiler input atlas')
    with Image.open(resolved['original_snapshot']) as source:
        if getattr(source, 'n_frames', 1) != 1:
            raise ValueError('Edge preparation source snapshot must be still')
        layout, settings = repair_spec(json.loads(resolved['recipe_snapshot'].read_bytes()), source.size)
    columns, rows, width, height, count = layout; padding = settings['padding_px']
    expected_layout = {'columns': columns, 'rows': rows, 'cell_width': width+2*padding, 'cell_height': height+2*padding, 'frame_count': count}
    if report.get('output_layout') != expected_layout or report.get('settings') != settings:
        raise ValueError('Edge preparation output layout/settings differ from its stored recipe')
    with Image.open(resolved['atlas']) as atlas:
        if atlas.size != (columns*expected_layout['cell_width'], rows*expected_layout['cell_height']) or getattr(atlas, 'n_frames', 1) != 1:
            raise ValueError('Edge preparation atlas dimensions differ from its declared output')
    check_inputs([{'resolved_path': str(record['path']), 'sha256': record['sha256']} for record in dependencies])
    return {'report': report, 'dependencies': dependencies}


def composite(image, background):
    from PIL import Image
    result = background.copy() if hasattr(background, 'size') else Image.new('RGBA', image.size, background)
    result.alpha_composite(image)
    return result.convert('RGB')


def contact_pages(stage, tiles, name, width, height):
    """Save contacts at actual tile resolution, split into bounded pages."""
    from PIL import Image, ImageDraw
    columns = max(1, min(4, 4096//width, len(tiles)))
    rows = max(1, 4096//(height+22)); capacity = columns*rows
    paths = []
    for offset in range(0, len(tiles), capacity):
        batch = tiles[offset:offset+capacity]
        sheet = Image.new('RGB', (columns*width, math.ceil(len(batch)/columns)*(height+22)), '#252934')
        draw = ImageDraw.Draw(sheet)
        for index, tile in enumerate(batch):
            with Image.open(stage/tile) as im:
                sheet.paste(im, (index % columns*width, index//columns*(height+22)))
            draw.text((index % columns*width+3, index//columns*(height+22)+height+3), f'Cel {offset+index}', fill='#ffffff')
        path = f'{name}-{len(paths):03d}.png'; sheet.save(stage/path); paths.append(path)
    return paths


def write_proofs(stage, frames, display_width, magnify, fps, context=None, context_rect=None, title='Sprite edges'):
    from PIL import Image
    width = integer(display_width, 'display_width', 1, 2048)
    magnify = integer(magnify, 'magnify', 2, 16)
    fps = number(fps, 'fps', .1, 60)
    height = max(1, round(frames[0].height*width/frames[0].width))
    if max(width*magnify, height*magnify) > 8192:
        raise ValueError('Magnified proof side exceeds 8192 pixels; reduce display width or magnification')
    pixels = len(frames)*width*height*(1+magnify*magnify)*(3 if context is not None else 2)
    if pixels > MAX_PROOF_PIXELS:
        raise ValueError('Proof exceeds 240 million pixels; reduce display width or magnification')
    backdrop = None
    if context is not None:
        x, y, w, h = context_rect
        backdrop = context.crop((x, y, x+w, y+h))
        if backdrop.size != (width, height):
            raise ValueError('context_rect width/height must equal displayed cel size; context pixels are never silently rescaled')
        context.save(stage/'context-source.png')
    kinds = ['light', 'dark']+(['context'] if backdrop is not None else [])
    contacts = {}; files = {kind: [] for kind in kinds}; magnified = {kind: [] for kind in kinds}
    for index, frame in enumerate(frames):
        small = isolated_resize(frame, (width, height))
        small.save(stage/f'cel-{index:03d}.png')
        for kind in kinds:
            background = backdrop if kind == 'context' else '#eee8dd' if kind == 'light' else '#202432'
            tile = composite(small, background)
            path = f'{kind}-{index:03d}.png'; tile.save(stage/path); files[kind].append(path)
            path = f'{kind}-magnified-{index:03d}.png'
            tile.resize((width*magnify, height*magnify), Image.Resampling.NEAREST).save(stage/path); magnified[kind].append(path)
    for kind in kinds:
        contacts[kind] = contact_pages(stage, files[kind], f'{kind}-contact', width, height)
        contacts[f'{kind}_magnified'] = contact_pages(stage, magnified[kind], f'{kind}-magnified-contact', width*magnify, height*magnify)
    if context is not None:
        placed = context.copy(); placed.alpha_composite(isolated_resize(frames[0], (width, height)), tuple(context_rect[:2]))
        placed.save(stage/'context-placement.png')
    data = json.dumps({'files': files, 'magnified': magnified, 'fps': fps, 'width': width, 'height': height, 'magnify': magnify}).replace('</', '<\\/')
    page = '''<!doctype html><meta charset="utf-8"><title>Sprite edge proof</title>
<style>body{background:#151a24;color:#eee;font:16px system-ui;margin:24px}button,input,select{margin:8px;padding:7px}.pair{display:flex;gap:24px;align-items:start}.scroll{overflow:auto;max-width:100%}img{flex:none;image-rendering:pixelated}a{color:#aad3ff}label{display:inline-block}</style>
<h1>'''+html.escape(title)+'''</h1><p>The small image is one CSS pixel per selected output pixel at 100% browser zoom. Magnification uses nearest-neighbor to expose the sampled pixels. It is not a quality score.</p>
<label>Background <select id="bg"></select></label><button id="play">Pause</button><label>Speed <select id="speed"><option value="1">1×</option><option value="0.5">½×</option><option value="0.25">¼×</option></select></label><label>Cel <input id="cel" type="range" min="0" value="0"></label><span id="position"></span>
<div class="scroll"><div class="pair"><img id="actual" alt="Displayed-size cel"><img id="zoom" alt="Magnified displayed pixels"></div></div>
<p>Playback is an explicitly selected uniform proof cadence, not the production scene's tracks, transform motion, or an encoded-video review.</p><h2>All-cel contacts</h2>'''
    for kind, paths in contacts.items():
        page += '<p>'+html.escape(kind)+': '+' '.join(f'<a href="{p}">Page {i+1}</a>' for i, p in enumerate(paths))+'</p>'
    if context is not None:
        page += '<p><a href="context-placement.png">Full context: first cel at the authored pixel rectangle</a></p>'
    page += '''<script>const D='''+data+''';const bg=document.querySelector('#bg'),cel=document.querySelector('#cel'),play=document.querySelector('#play');let running=true,index=0,last=0,elapsed=0;for(const name of Object.keys(D.files)){const o=document.createElement('option');o.value=name;o.textContent=name;bg.append(o)}cel.max=D.files.light.length-1;function paint(){cel.value=index;document.querySelector('#actual').src=D.files[bg.value][index];document.querySelector('#zoom').src=D.magnified[bg.value][index];document.querySelector('#position').textContent=`${index+1}/${D.files.light.length} · ${D.width}×${D.height} output pixels · ${D.fps} cels/s`}bg.onchange=paint;cel.oninput=()=>{index=Number(cel.value);running=false;play.textContent='Play';elapsed=0;paint()};play.onclick=()=>{running=!running;play.textContent=running?'Pause':'Play';elapsed=0};function tick(t){if(last&&running){elapsed+=(t-last)*Number(document.querySelector('#speed').value);const interval=1000/D.fps;if(elapsed>=interval){index=(index+Math.floor(elapsed/interval))%D.files.light.length;elapsed%=interval;paint()}}last=t;requestAnimationFrame(tick)}paint();requestAnimationFrame(tick);</script>'''
    (stage/'index.html').write_text(page)
    return {'display_size': [width, height], 'magnification': magnify, 'proof_fps': fps,
            'resampling': 'isolated-cell premultiplied-alpha Lanczos; nearest display-pixel magnification',
            'contacts': contacts, 'context_rect': context_rect}


def edge_repair(source, recipe_path, out):
    from PIL import Image
    from PIL import __version__ as pillow_version
    source = Path(source).resolve(); recipe_path = Path(recipe_path).resolve(); out = Path(out).resolve()
    source_bytes = source.read_bytes(); source_record = fingerprint(source)
    if source_record['sha256'] != prep.sha(source_bytes):
        raise ValueError('Source changed while being read')
    with Image.open(io.BytesIO(source_bytes)) as raw:
        if getattr(raw, 'n_frames', 1) != 1:
            raise ValueError('Edge repair requires a still source with explicit sheet layout')
        raw.load(); image = raw.convert('RGBA'); original_mode = raw.mode
    if original_mode not in ('RGBA', 'LA', 'P') or image.getchannel('A').getextrema() == (255, 255):
        raise ValueError('Edge repair requires actual transparency; it does not infer a matte from an opaque picture')
    recipe_bytes = recipe_path.read_bytes(); recipe_record = {'resolved_path': str(recipe_path), 'path_base': 'shell', 'sha256': prep.sha(recipe_bytes), 'bytes': len(recipe_bytes)}
    layout, settings = repair_spec(json.loads(recipe_bytes), image.size)
    columns, rows, width, height, count = layout; padding = settings['padding_px']
    new_width, new_height = width+2*padding, height+2*padding
    output = Image.new('RGBA', (columns*new_width, rows*new_height)); records = []; frames = []; before_frames = []
    for index in range(columns*rows):
        original = image.crop(cel_rect(index, columns, width, height))
        result = repair_cell(original, settings) if index < count else padded_cell(original, padding)
        output.paste(result, (index % columns*new_width, index//columns*new_height))
        if index < count:
            frames.append(result)
            before_frames.append(padded_cell(original, padding))
            records.append({'cel': index, 'before': alpha_facts(original), 'after': alpha_facts(result),
                            'changed_rgba_pixels': changed_pixels(padded_cell(original, padding), result),
                            'raw_cel_to_output_cell': [1, 0, 0, 1, padding, padding]})
    with fresh_output(out) as stage:
        output.save(stage/'atlas.png'); (stage/'source-original.bin').write_bytes(source_bytes)
        (stage/'recipe.json').write_bytes(recipe_bytes)
        proof_width = min(new_width, 192, max(1, round(384*new_width/new_height)))
        proofs = write_proofs(stage, frames, proof_width, 4, 6, title='Repaired sprite edges')
        (stage/'before').mkdir()
        before_proofs = write_proofs(stage/'before', before_frames, proof_width, 4, 6, title='Original edges at matching derivative geometry')
        page = (stage/'index.html').read_text()
        (stage/'index.html').write_text(page.replace('<h2>All-cel contacts</h2>', '<p><a href="before/index.html">Original edges at the same displayed size</a></p><h2>All-cel contacts</h2>'))
        report = {'ok': True, 'format': 'ambiance-edge-repair-result', 'version': 1, 'source': source_record,
                  'implementation': {'algorithm': 'isolated-edge-repair-v1', 'pillow': pillow_version, 'python': sys.version.split()[0]},
                  'recipe': recipe_record, 'source_mode': original_mode, 'settings': settings,
                  'input_layout': dict(zip(['columns', 'rows', 'cell_width', 'cell_height', 'frame_count'], layout)),
                  'output_layout': {'columns': columns, 'rows': rows, 'cell_width': new_width, 'cell_height': new_height, 'frame_count': count},
                  'cels': records, 'proof': proofs, 'before_proof': before_proofs,
                  'original_bytes_snapshot': 'source-original.bin', 'unused_slots': 'copied unmodified with the same explicit padding',
                  'limitations': ['No inferred segmentation, fringe detection, aesthetic approval, or lost-detail reconstruction.',
                                 'Nonzero choke can erase thin detail. Feather changes alpha and may soften or clip a silhouette; inspect every cel.',
                                 'Decontamination assumes the explicitly declared encoded-sRGB matte model; use only when appropriate to the source.',
                                 'Padding changes cell dimensions; recompile/register the derivative before scene use.']}
        report['provenance'] = {'path_base': 'report',
                                'source': {'file': os.path.relpath(source, out), 'sha256': source_record['sha256']},
                                'recipe': {'file': os.path.relpath(recipe_path, out), 'sha256': recipe_record['sha256']},
                                'original_snapshot': {'file': 'source-original.bin', 'sha256': source_record['sha256']},
                                'recipe_snapshot': {'file': 'recipe.json', 'sha256': recipe_record['sha256']},
                                'atlas': {'file': 'atlas.png', 'sha256': prep.sha((stage/'atlas.png').read_bytes())}}
        report['outputs'] = {str(p.relative_to(stage)): prep.sha(p.read_bytes()) for p in stage.rglob('*') if p.is_file()}
        prep.write(stage/'report.json', report); check_inputs([source_record, recipe_record])
    return {**report, 'directory': str(out), 'atlas': str(out/'atlas.png'), 'html': str(out/'index.html')}


def edges(identifier, out, project=None, catalog=None, display_width=None, background=None, context_rect=None, fps=6, magnify=4):
    from . import assets
    from PIL import Image
    records = []
    candidate = Path(identifier)
    # Pin metadata before lookup, so a proof cannot silently switch catalogs or packs.
    if candidate.is_dir():
        pack_candidate = candidate.resolve()
        for name in ['asset.json', 'report.json', 'recipe.json']:
            records.append(fingerprint(pack_candidate/name))
    else:
        if catalog:
            selected_catalog = Path(catalog).resolve()
        elif project:
            conf = Path(project).resolve()/'ambiance-project.json'; records.append(fingerprint(conf))
            selected_catalog = prep.project_file(Path(project).resolve(), json.loads(conf.read_bytes())['catalog'])
        else:
            selected_catalog = assets.ROOT/'assets/catalog.json'
        records.append(fingerprint(selected_catalog))
    asset, base, pack = assets.lookup(identifier, project, catalog)
    if pack and (pack/'asset.json').is_file() and (pack/'report.json').is_file():
        for name in ['asset.json', 'report.json', 'recipe.json']:
            records.append(fingerprint(pack/name))
        checked = assets.inspect_pack(pack)
        if not checked['ok']:
            raise ValueError('Prepared pack changed before edge proof')
        for key in ['id', 'sha256', 'width', 'height', 'atlas', 'registration_mapping']:
            if asset.get(key) != checked['asset'].get(key):
                raise ValueError(f'Catalog differs from prepared pack field: {key}')
        if asset.get('provenance', {}).get('edge_preparation') != checked['asset'].get('provenance', {}).get('edge_preparation'):
            raise ValueError('Catalog edge preparation differs from prepared pack')
        edge_ref = asset.get('provenance', {}).get('edge_preparation')
        if edge_ref:
            prep.fields(edge_ref, ['file', 'sha256'], 'edge preparation reference')
            if not isinstance(edge_ref.get('file'), str) or Path(edge_ref['file']).is_absolute():
                raise ValueError('Edge preparation reference must be recipe-relative')
            raw_paths = [(pack/source['file']).resolve() for source in checked['asset']['provenance']['sources']]
            prepared = validate_edge_preparation((pack/edge_ref['file']).resolve(), edge_ref.get('sha256'), raw_paths)
            records += [{'resolved_path': str(dep['path']), 'path_base': 'shell', 'sha256': dep['sha256'], 'role': dep['role']} for dep in prepared['dependencies']]
    source, frames = assets.read_asset(asset, base); records.append(fingerprint(source))
    if records[-1]['sha256'] != asset['sha256']:
        raise ValueError('Asset source changed while being decoded')
    if len(frames) > 512:
        raise ValueError('Edge proof supports up to 512 explicitly selected cels')
    context = None; context_info = None
    if (background is None) != (context_rect is None):
        raise ValueError('Use background and an explicit context_rect together')
    if background is not None:
        context, context_info = prep.decoded(background); records.append(context_info)
        if context_info['frames'] != 1:
            raise ValueError('Context must be a still image')
        if not isinstance(context_rect, (list, tuple)) or len(context_rect) != 4 or any(type(n) is not int for n in context_rect):
            raise ValueError('context_rect must be four integers [x,y,width,height] in unscaled context pixels')
        x, y, w, h = context_rect
        if not (x >= 0 and y >= 0 and w > 0 and h > 0 and x+w <= context.width and y+h <= context.height):
            raise ValueError('context_rect must stay within the decoded context image')
    registration = asset.get('registration_mapping'); source_scale = None
    if registration:
        # Compiler-owned registration is a measured scale, not a guessed crop.
        if not isinstance(registration, dict) or not isinstance(registration.get('cels'), list) or not isinstance(registration.get('input_sources'), list):
            raise ValueError('Malformed compiler registration mapping')
        source_scale = {'compiler_shared_scale': registration.get('shared_scale'),
                        'source_to_cell': [cel.get('source_to_cell') for cel in registration.get('cels', [])],
                        'raw_input_dimensions': [[s.get('width'), s.get('height')] for s in registration.get('input_sources', [])],
                        'status': 'compiler metadata; original source pixels are not shown by this command'}
    out = Path(out).resolve()
    with fresh_output(out) as stage:
        proofs = write_proofs(stage, frames, display_width, magnify, fps, context, context_rect, title=f'{asset["id"]}: sprite edges')
        prep.write(stage/'asset-snapshot.json', asset)
        report = {'ok': True, 'format': 'ambiance-edge-proof', 'version': 1, 'asset_id': asset['id'],
                  'inputs': records, 'source': str(source), 'cel_count': len(frames), 'cell_size': list(frames[0].size),
                  'proof': proofs, 'scale': {'cell_to_display': [proofs['display_size'][0]/frames[0].width, proofs['display_size'][1]/frames[0].height],
                                           'source_registration': source_scale},
                  'cels': [{'cel': i, 'source_alpha': alpha_facts(frame), 'display_alpha': alpha_facts(isolated_resize(frame, proofs['display_size']))} for i, frame in enumerate(frames)],
                  'context': context_info,
                  'limitations': ['Pixel facts do not detect a correct artistic edge or certify a clean matte.',
                                  'Uniform proof cadence is independent of production scene tracks and transform motion.',
                                  'Context is an explicit unscaled pixel crop; lighting, scene transforms and encoded-video changes are not simulated.',
                                  'Input atlas pixels are isolated before filtering; original compiler inputs and decoded video must be compared separately.']}
        report['outputs'] = {p.name: prep.sha(p.read_bytes()) for p in stage.iterdir()}
        prep.write(stage/'report.json', report); check_inputs(records)
    return {**report, 'directory': str(out), 'html': str(out/'index.html')}
