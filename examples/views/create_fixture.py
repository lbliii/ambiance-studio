"""Create local geometric artwork and exercise saved views through the CLI."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]


def command(*args):
    process = subprocess.run([sys.executable, str(ROOT/'ambiance'), *map(str, args)], capture_output=True, text=True)
    result = json.loads(process.stdout)
    if process.returncode:
        raise RuntimeError(json.dumps(result))
    return result['data']


def main(destination):
    project = destination.resolve()
    command('project', 'init', project, '--format', 'dual', '--title', 'Saved views — geometry pilot')
    plate = Image.new('RGB', (192, 192), '#263545'); draw = ImageDraw.Draw(plate)
    for i in range(0, 192, 24):
        draw.line([(i, 0), (i, 191)], fill='#657681', width=1)
        draw.line([(0, i), (191, i)], fill='#657681', width=1)
    draw.rectangle((0, 0, 22, 22), fill='#d29465')
    draw.rectangle((169, 169, 191, 191), fill='#669d91')
    plate.save(project/'assets/grid.png')
    subject = Image.new('RGBA', (96, 96)); draw = ImageDraw.Draw(subject)
    draw.ellipse((8, 8, 87, 87), fill='#e4be82', outline='#f6e5c9', width=4)
    draw.line([(48, 12), (48, 83)], fill='#795737', width=2)
    draw.line([(12, 48), (83, 48)], fill='#795737', width=2)
    subject.save(project/'assets/circle.png')
    assets = []
    for id, image in [('grid', plate), ('circle', subject)]:
        file = project/f'assets/{id}.png'
        assets.append({'id': id, 'kind': 'plate', 'file': f'assets/{id}.png', 'width': image.width,
                       'height': image.height, 'sha256': hashlib.sha256(file.read_bytes()).hexdigest(),
                       'provenance': {'source': 'examples/views/create_fixture.py', 'purpose': 'Local geometric test artwork'}})
    (project/'assets/catalog.json').write_text(json.dumps({'version': 1, 'assets': assets}, indent=2)+'\n')
    batch = project/'plans/fixture-batch.json'
    batch.write_text(json.dumps({'version': 1, 'operations': [
        {'op': 'add', 'asset': 'grid', 'id': 'grid', 'values': {'width': 1, 'depth': 0}},
        {'op': 'add', 'asset': 'circle', 'id': 'circle', 'values': {'width': .25, 'depth': 0,
         'motion': {'x_amplitude': .12, 'y_amplitude': .03, 'cycles': 2, 'phase': 0}}},
        {'op': 'coverage', 'layers': ['grid']}
    ]}, indent=2)+'\n')
    dry = command('--project', project, 'scene', 'apply', batch, '--dry-run')
    command('--project', project, 'scene', 'apply', batch, '--expect-sha256', dry['previous_sha256'])
    checked = command('--project', project, 'view', 'check', '--out', project/'reports/views.json')
    command('--project', project, 'project', 'check', '--out', project/'reports/project.json')
    rendered = command('--project', project, 'render', 'frame', '--time', '1', '--width', '320', '--out', project/'render/authored-frame')
    print(json.dumps({'project': str(project), 'views': list(checked['views']), 'frame': rendered['output'],
                      'scope': 'Saved framing and full authored-stage rendering; named-view export is pending.'}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('destination', type=Path)
    main(parser.parse_args().destination)
