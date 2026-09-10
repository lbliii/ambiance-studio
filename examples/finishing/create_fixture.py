#!/usr/bin/env python3
"""Build independent finishing art and author its scene through the public CLI."""
import argparse
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import studio


def command(*args):
    process = subprocess.run([str(ROOT/'ambiance'), *map(str, args)], text=True, capture_output=True)
    payload = json.loads(process.stdout)
    if process.returncode or not payload.get('ok'): raise ValueError(payload.get('error', process.stderr))
    return payload['data']


def create(out):
    out = Path(out).resolve()
    if out.exists(): raise ValueError('Fixture output exists; choose a fresh directory')
    with tempfile.TemporaryDirectory(prefix='finishing-reference-') as temp:
        reference = Path(temp)/'reference.png'
        Image.new('RGB', (360, 640), '#162b3b').save(reference)
        command('project', 'init', out, '--reference', reference, '--title', 'Independent finishing engineering fixture')
    source = out/'assets/source'; source.mkdir(exist_ok=True)
    def save(name, image):
        path = source/f'{name}.png'; image.save(path); return path
    room = Image.new('RGBA', (360, 640), '#162b3b'); draw = ImageDraw.Draw(room)
    draw.rectangle((205, 50, 332, 380), fill='#28384a', outline='#64727b', width=6)
    for x in range(0, 361, 40): draw.line((x, 350, x, 640), fill='#26424a')
    for y in range(360, 641, 40): draw.line((0, y, 360, y), fill='#26424a')
    save('room', room)
    floor = Image.new('RGBA', (360, 640)); ImageDraw.Draw(floor).rectangle((0, 350, 359, 639), fill='#273b44'); save('floor', floor)
    casket = Image.new('RGBA', (80, 116)); draw = ImageDraw.Draw(casket)
    draw.rounded_rectangle((3, 3, 76, 112), radius=12, fill='#b78440', outline='#edd89a', width=4)
    draw.rounded_rectangle((13, 12, 66, 102), radius=8, fill='#4d3930'); save('casket', casket)
    rim = Image.new('RGBA', (80, 116)); ImageDraw.Draw(rim).line((3, 85, 3, 112, 76, 112, 76, 85), fill='#ffe2a5', width=6); save('rim', rim)
    rat_frames = []; flame_frames = []
    for i in range(4):
        rat = Image.new('RGBA', (56, 32)); draw = ImageDraw.Draw(rat)
        draw.ellipse((18, 8, 44, 23), fill='#c58d5d'); draw.ellipse((37, 7, 52, 19), fill='#e0ac71')
        draw.ellipse((37, 2, 43, 10), fill='#b87858'); draw.ellipse((47, 10, 49, 12), fill='#e8ffc9')
        draw.line((20, 20, 5, 23, 1, 16), fill='#ce9e80', width=2)
        for x, offset in [(23, i % 2*4), (37, (1-i % 2)*4)]: draw.line((x, 20, x-offset, 29), fill='#d6ab77', width=3)
        rat_frames.append(save(f'rat-{i}', rat))
        flame = Image.new('RGBA', (24, 40)); draw = ImageDraw.Draw(flame)
        draw.rectangle((7, 26, 17, 39), fill='#c9a25a')
        draw.polygon([(12, 1+i*2), (21-i, 19), (14, 29), (5, 20)], fill='#ffb746')
        draw.ellipse((9, 16, 15, 28), fill='#fff0ba'); flame_frames.append(save(f'flame-{i}', flame))
    mask = Image.new('RGBA', (48, 48))
    mask.putdata([(255, 255, 255, round(255*max(0, 1-math.hypot((x-23.5)/23.5, (y-23.5)/23.5)))) for y in range(48) for x in range(48)])
    save('soft-mask', mask)
    def compile(name, frames, size, opaque=False):
        recipe = {'version': 1, 'id': name, 'input': {'frames': [str(p.relative_to(out/'assets')) for p in frames], 'allow_opaque': opaque},
                  'registration': {'mode': 'fixed', 'point': [size[0]/2, size[1]/2], 'target': [.5, .5]},
                  'output': {'cell_size': [size[0]+4, size[1]+4], 'columns': min(4, len(frames)), 'padding': 2}}
        path = out/'assets'/f'{name}-recipe.json'; studio.write(path, recipe)
        pack = out/'assets/production'/name
        command('--project', out, 'asset', 'build', path, '--out', pack)
        command('--project', out, 'asset', 'admit', pack)
    for name, size in [('room', (360, 640)), ('floor', (360, 640)), ('casket', (80, 116)), ('rim', (80, 116)), ('soft-mask', (48, 48))]:
        compile(name, [source/f'{name}.png'], size, name == 'room')
    compile('rat', rat_frames, (56, 32)); compile('flame', flame_frames, (24, 40))
    def card(id, asset, **values):
        return {'op': 'add', 'id': id, 'asset': asset, 'values': {'x': .5, 'y': .5, 'width': 1, 'height': 1,
                'scale': 1, 'rotation': 0, 'opacity': 1, 'visible': True, 'blend': 'source-over', 'depth': 0,
                'anchor': [.5, .5], 'cycle_seconds': 4, 'phase_frames': 0, **values}}
    batch = {'version': 1, 'operations': [
        card('room', 'room', width=364/360, height=644/640),
        card('floor', 'floor', width=364/360, height=644/640),
        card('rat', 'rat', x=.14, y=.81, width=.19, height=.064, anchor=[.5, 1], cycle_seconds=.4,
             sockets={'ground': [.5, 1]}, tracks={'x': {'interpolation': 'smoothstep', 'keys': [[0, .14], [2, .83], [4, .14]]}}),
        card('casket', 'casket', x=.43, y=.69, width=.27, height=.207, sockets={'ground': [.5, 1], 'rim': [.5, .5]},
             tracks={'y': {'interpolation': 'smoothstep', 'keys': [[0, .69], [1, .69], [2, .63], [3, .69], [4, .69]]}}),
        card('rim', 'rim', x=.43, y=.69, width=.27, height=.207),
        card('lamp', 'flame', x=.19, y=.54, width=.055, height=.05, cycle_seconds=.5),
    ]}
    # Canvas is ordinary authoring data; the initial blank scene has no layers.
    scene_path = out/'scene/scene.json'; scene = studio.read(scene_path)
    scene['canvas'].update(width=360, height=640, fps=30, loop_seconds=4)
    scene['camera'] = {'overscan': 1, 'x_amplitude': 0, 'y_amplitude': 0, 'zoom_amplitude': 0}
    studio.write(scene_path, scene)
    studio.write(out/'assembly.json', batch); command('--project', out, 'scene', 'apply', out/'assembly.json')
    command('--project', out, 'scene', 'reparent', 'rim', '--to', 'casket', '--socket', 'rim', '--keep-world', '--at', 0)
    look = {'kind': 'ambiance-look', 'version': 1, 'finishing': {
        'version': 1, 'working_space': 'linear-srgb', 'output_space': 'srgb',
        'grade': {'exposure': -.12, 'saturation': .86},
        'layers': {'casket': {'balance': [1.12, .97, .78]}, 'rat': {'saturation': .8}},
        'signals': [{'id': 'lamp-flicker', 'layer': 'lamp', 'values': [.62, 1, .78, .92]}],
        'lights': [
            {'id': 'moonlight', 'receivers': ['floor', 'rat', 'casket', 'rim'], 'rect': [.54, .12, .39, .79], 'color': '#6b91ff', 'gain': .7, 'feather': .3},
            {'id': 'lamp-bounce', 'receivers': ['floor', 'casket', 'rat'], 'rect': [-2.5, -1.5, 7, 9], 'anchor_layer': 'lamp', 'mask_asset': 'soft-mask', 'color': '#ffa94d', 'gain': .8, 'feather': .25, 'signal': 'lamp-flicker'}],
        'shadows': [
            {'id': 'rat-contact', 'caster': 'rat', 'receiver': 'floor', 'offset': [0, .006], 'scale': [1.05, .22], 'opacity': .6, 'color': '#090c17', 'softness': .004},
            {'id': 'casket-contact', 'caster': 'casket', 'receiver': 'floor', 'offset': [0, .005], 'scale': [1, .2], 'opacity': .58, 'color': '#111320', 'softness': .003,
             'elevation': {'layer': 'casket', 'rest_y': .69, 'range': .06, 'offset': [.025, .018], 'softness': .018, 'opacity': .24, 'scale': [1.3, .36]}}],
        'reflections': [{'id': 'casket-floor', 'caster': 'casket', 'receiver': 'floor', 'offset': [0, .01], 'scale': [1, .28], 'opacity': .12, 'softness': .006}]
    }}
    studio.write(out/'look.json', look); command('--project', out, 'look', 'apply', out/'look.json')
    command('--project', out, 'look', 'check', '--out', out/'reports/finishing-check.json')
    package = command('--project', out, 'look', 'export', '--out', out/'looks/museum-engineering')
    rig_package = command('--project', out, 'look', 'export', '--include-rig', '--out', out/'looks/museum-engineering-rig')
    identity_bindings = studio.read(rig_package['bindings_template'])
    for scope in ['layers', 'groups', 'assets']: identity_bindings[scope] = {key: key for key in identity_bindings[scope]}
    studio.write(out/'rig-bindings.json', identity_bindings)
    import_preview = command('--project', out, 'look', 'import', rig_package['package'], '--bindings', out/'rig-bindings.json', '--include-rig', '--dry-run')
    studio.write(out/'reports/rig-import-dry-run.json', import_preview)
    return {'project': str(out), 'scene': str(scene_path), 'look': str(out/'look.json'), 'package': package['package'], 'rig_package': rig_package['package'],
            'scope': 'Independent geometric art; authored only through public scene/look transactions after initial canvas setup.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--out', type=Path, required=True)
    print(json.dumps(create(parser.parse_args().out), indent=2))
