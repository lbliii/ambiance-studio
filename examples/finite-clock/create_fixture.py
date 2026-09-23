"""Materialize a small native scene/clock transaction; no production artwork.

Run: python3 examples/finite-clock/create_fixture.py FRESH_DIRECTORY
Then replay the public argv in README.md. Source PNGs are deterministic test
patterns, preserved in the created project alongside editable native recipes.
"""
import hashlib
import json
from pathlib import Path
import struct
import sys
import zlib


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def png(path, colors):
    width, height = len(colors) * 32, 32
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    rows = b''.join(b'\0' + b''.join(bytes((*colors[x//32], 255)) for x in range(width)) for _ in range(height))
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b''))
    return {'width': width, 'height': height, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def create_fixture(out):
    out = Path(out); out.mkdir(parents=True, exist_ok=False)
    (out/'assets').mkdir()
    assets = []
    for id, colors in [('cels', [(235, 82, 61), (244, 202, 74), (64, 141, 210)]), ('floor', [(25, 34, 47)]), ('marker', [(237, 235, 221)])]:
        metadata = png(out/'assets'/f'{id}.png', colors)
        asset = {'id': id, 'kind': 'atlas' if id == 'cels' else 'image', 'file': f'assets/{id}.png', **metadata}
        if id == 'cels':
            asset['atlas'] = {'columns': 3, 'rows': 1, 'cell_width': 32, 'cell_height': 32, 'frame_count': 3}
        assets.append(asset)
    write(out/'assets/catalog.json', {'version': 1, 'assets': assets})
    def card(id, asset, x, y, width, height, **extra):
        return {'id': id, 'name': id, 'asset': asset, 'x': x, 'y': y, 'width': width, 'height': height, 'anchor': [0, 0], 'scale': 1, 'rotation': 0, 'opacity': 1, 'visible': True, 'blend': 'source-over', 'depth': 0, **extra}
    def track(keys, interpolation='hold'):
        return {'interpolation': interpolation, 'keys': keys}
    scene = {'version': 1, 'id': 'finite-clock-fixture', 'title': 'Finite clock — endpoint inspection',
             'canvas': {'width': 320, 'height': 180, 'fps': 24, 'loop_seconds': 2.5, 'background': '#19222f'},
             'camera': {'overscan': 1, 'x_amplitude': 0, 'y_amplitude': 0, 'zoom_amplitude': 0},
             'groups': [], 'layers': [card('floor', 'floor', 0, 0, 1, 1)], 'coverage_layers': ['floor']}
    write(out/'scene.json', scene)
    write(out/'project.json', {'id': 'finite-clock-fixture', 'title': 'Finite clock technical fixture'})
    write(out/'ambiance-project.json', {'version': 1, 'scene': 'scene.json', 'catalog': 'assets/catalog.json'})
    write(out/'clock.json', {'fps': 24, 'clock': {'version': 1, 'mode': 'finite', 'id': 'technical-shot-a', 'revision': 'fixture-a-v1', 'duration_frames': 60,
          'local_cycles': {'pulse': {'period_seconds': {'numerator': 1, 'denominator': 1}, 'phase_turns': {'numerator': 1, 'denominator': 4}}}}})
    root = card('root', 'cels', .1, .35, .2, .3, cycle_seconds=1, phase_frames=0,
                sockets={'tip': {'frames': [[.25, 1], [.5, 1], [.75, 1]]}},
                tracks={'x': track([[0, .1], [2.5, .7]], 'linear'), 'cell': track([[0, 0], [59/24, 1], [2.5, 2]])})
    child = card('socket-marker', 'marker', 0, 0, .025, .05, attach={'layer': 'root', 'socket': 'tip'}); del child['depth']
    local = card('local-cycle', 'cels', .45, .12, .08, .12, cycle_seconds=7, phase_frames=0, local_cycle='pulse')
    operations = [{'op': 'add', 'asset': row['asset'], 'id': row['id'], 'values': {k: v for k, v in row.items() if k != 'id'}} for row in [root, child, local]]
    write(out/'acting.json', {'version': 1, 'operations': operations})
    return out


if __name__ == '__main__':
    print(create_fixture(sys.argv[1]).resolve())
