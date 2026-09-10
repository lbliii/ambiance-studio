#!/usr/bin/env python3
"""Public-CLI pilot with synthetic known-matte cels; no production writes."""
import json
from pathlib import Path
import subprocess
import sys

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ambiance_studio import asset_prep as prep
from ambiance_studio.edge_quality import pixels


def main():
    if len(sys.argv) != 2:
        raise ValueError('Pass a fresh output project directory')
    project = Path(sys.argv[1]).resolve()
    if project.exists():
        raise ValueError('Example destination already exists')
    receipts = []

    def cli(*args):
        command = [str(ROOT/'ambiance'), '--project', str(project), *map(str, args)]
        run = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
        receipt = json.loads(run.stdout)
        receipts.append({'arguments': command[1:], 'exit_code': run.returncode, 'receipt': receipt})
        if run.returncode or not receipt['ok']:
            raise ValueError(run.stdout+run.stderr)
        return receipt['data']

    # The init command creates the project itself; its --project value is only
    # used by later calls. Every fixture source stays inside this new project.
    cli('project', 'init', project, '--title', 'Edge quality calibration')
    sheet = Image.new('RGBA', (256, 64), (238, 238, 238, 0))
    foreground = [65, 85, 100]; matte = [238, 238, 238]
    for index in range(4):
        alpha_large = Image.new('L', (256, 256)); draw = ImageDraw.Draw(alpha_large)
        draw.ellipse((64, 72, 184, 180), fill=255)
        draw.polygon([(168, 100), (220, 124+index*4), (172, 148)], fill=255)
        draw.line([(72, 156), (30, 180-index*9), (16, 168-index*6)], fill=170, width=6)
        draw.line((190, 125, 240, 112+index*5), fill=80, width=2)
        alpha = alpha_large.resize((64, 64), Image.Resampling.LANCZOS)
        frame = Image.new('RGBA', (64, 64))
        frame.putdata([(*[round(a/255*f+(1-a/255)*m) for f, m in zip(foreground, matte)], a) for a in pixels(alpha)])
        sheet.paste(frame, (64*index, 0))
    source = project/'assets/known-matte.png'; sheet.save(source)
    source_hash = prep.sha(source.read_bytes())
    repair = project/'plans/repair.json'
    prep.write(repair, {'format': 'ambiance-edge-repair', 'version': 1,
                        'layout': {'columns': 4, 'rows': 1, 'cell_width': 64, 'cell_height': 64, 'frame_count': 4},
                        'decontamination': {'strength': 1, 'matte_rgb': matte},
                        'alpha': {'feather_px': 0, 'choke_px': 0}})
    cli('asset', 'edge-repair', source, '--recipe', repair, '--out', project/'assets/repaired')
    background = Image.new('RGB', (320, 240), '#173758'); draw = ImageDraw.Draw(background)
    for y in range(0, 240, 30):
        draw.line((0, y, 320, y), fill='#274d6f')
    background.save(project/'assets/context.png')
    for name, path in [('before', '../assets/known-matte.png'), ('after', '../assets/repaired/atlas.png')]:
        recipe = project/f'plans/{name}-compile.json'
        spec = {'version': 1, 'id': f'edge-{name}-v1',
                'input': {'sheet': path, 'columns': 4, 'rows': 1, 'frame_count': 4},
                'registration': {'mode': 'fixed', 'point': [32, 32], 'target': [.5, .5]},
                'output': {'cell_size': [64, 64], 'columns': 4, 'padding': 2}}
        if name == 'after':
            spec['edge_preparation'] = {'file': '../assets/repaired/report.json', 'sha256': prep.sha((project/'assets/repaired/report.json').read_bytes())}
        prep.write(recipe, spec)
        cli('asset', 'build', recipe, '--out', project/f'assets/{name}-pack')
        cli('asset', 'edges', project/f'assets/{name}-pack', '--display-width', 48,
            '--background', project/'assets/context.png', '--context-rect', 140, 100, 48, 48,
            '--out', project/f'reports/{name}-edges')
    if prep.sha(source.read_bytes()) != source_hash:
        raise AssertionError('Original source changed')
    prep.write(project/'edge-pilot-receipts.json', receipts)
    summary = {'ok': True, 'project': str(project), 'public_cli_calls': len(receipts),
               'original_preserved': True, 'before': str(project/'reports/before-edges/index.html'),
               'after': str(project/'reports/after-edges/index.html'),
               'scope': 'Synthetic known-matte calibration; no aesthetic, phone, scene-motion, or encoded-video approval.'}
    prep.write(project/'edge-pilot-summary.json', summary)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
