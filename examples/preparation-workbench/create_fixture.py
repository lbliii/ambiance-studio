#!/usr/bin/env python3
"""An independent local preparation exercise, using synthetic artwork, not a film pilot."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ambiance_studio import preparation as p
from ambiance_studio import asset_prep as prep


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    project = args.directory.resolve()
    subprocess.run([sys.executable, str(ROOT/'ambiance'), 'project', 'init', str(project),
                    '--title', 'The blue cabinet · preparation exercise'], check=True, capture_output=True)
    raw = project/'assets/raw'; raw.mkdir(exist_ok=True)
    w, h = 384, 512
    backing = Image.new('RGB', (w, h), '#142a36'); d = ImageDraw.Draw(backing)
    # A quiet cabinet backdrop with stable features for alignment and a fixed front rail.
    d.rounded_rectangle((38, 30, 346, 478), 110, fill='#223f4d', outline='#587079', width=3)
    d.rectangle((38, 210, 346, 478), fill='#223f4d')
    for x in range(60, 345, 48):
        d.line((x, 170, x, 390), fill='#2a4754', width=2)
    d.ellipse((83, 372, 306, 419), fill='#142b35')
    d.rectangle((30, 419, 354, 432), fill='#0d222c')
    d.rectangle((44, 432, 340, 442), fill='#53717d')
    d.rectangle((59, 442, 68, 488), fill='#344f5d')
    d.rectangle((316, 442, 325, 488), fill='#344f5d')
    backing.save(raw/'backing.png')
    source = backing.copy(); d = ImageDraw.Draw(source)
    # A brass botanical silhouette: polygons exercise concave boundaries and the narrow stem.
    body = [[172, 369], [162, 327], [134, 321], [108, 300], [101, 270], [125, 274],
            [152, 291], [168, 316], [172, 277], [151, 259], [141, 227], [150, 208],
            [171, 230], [179, 259], [182, 218], [171, 193], [178, 154], [196, 130],
            [211, 159], [209, 193], [193, 219], [191, 263], [209, 237], [232, 226],
            [251, 226], [244, 250], [221, 271], [190, 282], [186, 323], [207, 296],
            [235, 284], [261, 288], [248, 314], [223, 330], [184, 336], [182, 369]]
    d.polygon([tuple(v) for v in body], fill='#c4a462')
    d.line([(177, 374), (184, 260), (197, 153)], fill='#eed39a', width=3)
    d.rounded_rectangle((148, 362, 224, 395), radius=7, fill='#b28c4e')
    d.rectangle((140, 390, 232, 409), fill='#88683b')
    d.rectangle((144, 390, 228, 394), fill='#d2b474')
    # The foreground rail overlaps the pedestal and must remain fixed.
    d.rectangle((50, 402, 333, 407), fill='#92a9ac')
    d.rectangle((50, 408, 333, 414), fill='#456472')
    source.save(raw/'source.png')
    recipe = p.initial_recipe(project, raw/'source.png', raw/'backing.png')
    recipe['title'] = 'The blue cabinet'
    poly = lambda points: {'operation': 'add', 'points': points}
    rect = lambda x0, y0, x1, y1: poly([[x0, y0], [x1, y0], [x1, y1], [x0, y1]])
    recipe['masks']['removal']['polygons'] = [rect(95, 124, 266, 416)]
    recipe['masks']['cutout']['polygons'] = [poly(body), rect(148, 362, 224, 394), rect(140, 390, 232, 401)]
    recipe['masks']['occluder']['polygons'] = [rect(50, 402, 333, 414)]
    recipe['motion'] = {'pivot': [186, 401], 'delta': [0, -20], 'rotation_degrees': 2, 'seconds': 4}
    prep.write(project/'plans/preparation.json', recipe)
    result = subprocess.run([sys.executable, str(ROOT/'ambiance'), '--project', str(project),
                             'asset', 'prepare', '--recipe', str(project/'plans/preparation.json'),
                             '--out', str(project/'assets/prepared/cabinet-v1')], check=True, capture_output=True, text=True)
    print(result.stdout)


if __name__ == '__main__':
    main()
