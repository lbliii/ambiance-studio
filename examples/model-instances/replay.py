"""Actual argv replay with retained receipts, packages, observations and hashes."""
import argparse
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys

from create_fixture import create, model_source, ROOT
import studio
from ambiance_studio.file_identity import digest
from ambiance_studio.project import locations
from ambiance_studio.model_instances import RECIPE


def replay(out):
    out = Path(out).resolve(); out.mkdir(parents=True, exist_ok=False)
    source = model_source(out/'source'); project = create(out/'scene-project')
    steps = []; facts = {}; frames = {}
    def run(argv, expected=0):
        argv = [str(ROOT/'ambiance'), *map(str, argv)]
        result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True)
        data = json.loads(result.stdout)
        step = {'argv': argv, 'returncode': result.returncode, 'expected_returncode': expected, 'result': data, 'stderr': result.stderr}
        steps.append(step); studio.write(out/'replay.json', {'steps': steps})
        if result.returncode != expected: raise RuntimeError(step)
        return data.get('data', data)
    def cli(*argv, expected=0): return run(['--project', project, *argv], expected)
    def scene(): return studio.read(locations(project)[0])
    def recipe(name, operations):
        path = out/(name+'.json')
        studio.write(path, {'format': RECIPE, 'schema_version': 1, 'expected_scene_sha256': digest(locations(project)[0]), 'operations': operations})
        return path
    def update(id='a', **values):
        old = next(r for r in scene()['model_instances']['instances'] if r['instance_id'] == id)
        return {'op': 'update', 'instance_id': id, 'expected_pin': old['pin'], 'expected_managed_sha256': old['managed_sha256'], **values}
    def apply(name, operations): return cli('model', 'instance', 'apply', recipe(name, operations))
    def raster(name, **extra):
        argv = ['render', 'frame', '--view', 'authored', '--out', project/'renders'/name]
        if extra.get('revision'): argv += ['--revision', extra['revision']]
        result = cli(*argv); frames[name] = {'file': result['output'], 'sha256': digest(result['output']), 'report': result['report']}
        return result
    package = out/'package'; package2 = out/'package-v2'
    run(['model', 'build', source/'models/lantern.json', '--source-root', source, '--out', package])
    run(['model', 'lower', package, '--state', source/'rest.json', '--out', out/'local-probe'])
    run(['--project', out/'local-probe', 'scene', 'check'])
    source2 = out/'source-v2'; shutil.copytree(source, source2)
    definition = studio.read(source2/'models/lantern.json'); definition.update(version='2', name='Label-only lantern revision')
    studio.write(source2/'models/lantern.json', definition)
    run(['model', 'build', source2/'models/lantern.json', '--source-root', source2, '--out', package2])
    operations = [{'op': 'place', 'instance_id': id, 'package': str(package), 'package_sha256': digest(package/'model-package.json'),
                   'placement': {'position': [x, 100], 'scale': 1.5, 'rotation': 0, 'depth': 0}} for id, x in [('a', 60), ('b', 180)]]
    operations[0]['receivers'] = [{'id': 'floor', 'source_part_path': ['candle', 'flame'], 'illumination': 'a-floor',
                                  'values': [.4, .7, 1, .6], 'valid_bounds': [20, 60, 110, 120]}]
    place_recipe = recipe('place-two', operations)
    before = digest(project/'ambiance-project.json')
    dry = cli('model', 'instance', 'apply', place_recipe, '--dry-run')
    assert digest(project/'ambiance-project.json') == before and not (project/'.ambiance/model-generations').exists()
    cli('model', 'instance', 'apply', place_recipe)
    assert dry['scene'] == scene()
    cli('model', 'instance', 'inspect'); cli('scene', 'check')
    cli('model', 'instance', 'apply', place_recipe, expected=2)
    cli('model', 'instance', 'apply', recipe('duplicate', [operations[0]]), expected=2)
    baseline = raster('two-square')
    wrapper = project/'evidence/two-models.json'
    cli('model', 'instance', 'evidence', '--receipt', baseline['report'], '--instance', 'a', '--instance', 'b', '--out', wrapper)
    config = studio.read(project/'ambiance-project.json')
    selection = project/'plans/selection.json'; studio.write(selection, {'format': 'ambiance-revision-selection', 'schema_version': 1, 'scene': config['scene'], 'catalog': config['catalog']})
    cli('revision', 'capture', 'before', '--selection', selection)
    unchanged_b = copy.deepcopy(scene()['model_instances']['instances'][1])
    mount = apply('move-mount', [update(placement={'position': [85, 100], 'scale': 1.3, 'rotation': .12, 'depth': 0}, mount={'layer': 'ground', 'socket': 'light', 'at_seconds': .375})])
    facts['mount_corner_error_pixels'] = mount['previews'][0]['mount']['max_world_corner_error_pixels']
    raster('moved-mounted')
    arched = studio.read(source/'rest.json'); arched['variants'][0]['variant_id'] = 'arched'
    apply('vary-a', [update(state=arched)]); raster('a-arched')
    hidden = copy.deepcopy(arched); hidden['pose_id'] = 'hidden'; hidden['controls'] = [{'model_path': [], 'control_id': 'visible', 'value': False}]
    apply('hide-a', [update(state=hidden)]); raster('a-hidden')
    state = cli('scene', 'sample', '--time', .5)
    facts['hidden_source_receiver_opacity'] = next(r['opacity'] for r in state if r['id'] == 'ground-a-light')
    facts['unrelated_receiver_opacity'] = next(r['opacity'] for r in state if r['id'] == 'unrelated-light')
    assert scene()['model_instances']['instances'][1] == unchanged_b
    apply('reveal-a', [update(state=arched)]); raster('a-revealed')
    old_scene_sha = digest(locations(project)[0]); old_record = copy.deepcopy(scene()['model_instances']['instances'][0])
    adoption = update(); adoption.update(op='adopt', package=str(package2), package_sha256=digest(package2/'model-package.json'))
    adopt_recipe = recipe('adopt-v2', [adoption]); cli('model', 'instance', 'apply', adopt_recipe, '--dry-run')
    cli('model', 'instance', 'apply', adopt_recipe); raster('adopted-v2')
    assert scene()['model_instances']['instances'][0]['pin']['definition']['version'] == '2'
    cli('scene', 'restore', old_scene_sha); cli('model', 'instance', 'inspect')
    assert scene()['model_instances']['instances'][0] == old_record
    # A valid first operation followed by an impossible mount publishes nothing.
    before = digest(project/'ambiance-project.json')
    late = recipe('late-invalid', [update(placement={'position': [90, 100], 'scale': 1.3, 'rotation': .12, 'depth': 0}), update('b', mount={'layer': 'missing', 'socket': 'missing', 'at_seconds': 0})])
    cli('model', 'instance', 'apply', late, expected=2)
    assert digest(project/'ambiance-project.json') == before
    # Existing ordinary edit and exact restore still operate on the selected generation.
    current_sha = digest(locations(project)[0]); cli('scene', 'set', 'unrelated-light', '--x', .3)
    cli('scene', 'restore', current_sha); assert digest(locations(project)[0]) == current_sha
    (out/'unavailable').mkdir()
    for path in [source, source2, package, package2]: shutil.move(path, out/'unavailable'/path.name)
    cli('model', 'instance', 'inspect'); cli('scene', 'check')
    raster('captured-old', revision='before')
    portable = out/'portable'; shutil.copytree(project, portable)
    shutil.move(project, out/'unavailable'/project.name); project = portable
    cli('model', 'instance', 'inspect'); cli('scene', 'check'); raster('portable-reopened')
    from PIL import Image, ImageChops
    # Retain paths after the original project itself becomes unavailable.
    for item in frames.values():
        p = Path(item['file'])
        if not p.exists(): item['file'] = str(out/'unavailable/scene-project'/p.relative_to(out/'scene-project'))
    with Image.open(frames['two-square']['file']) as base:
        base = base.convert('RGB')
        for name in ['moved-mounted', 'a-arched', 'a-hidden']:
            with Image.open(frames[name]['file']) as other:
                other = other.convert('RGB')
                facts[name] = {'different_pixels': sum(p != (0, 0, 0) for p in ImageChops.difference(base, other).getdata()),
                    'second_instance_crop_unchanged': ImageChops.difference(base.crop((130, 0, 240, 160)), other.crop((130, 0, 240, 160))).getbbox() is None}
    index = '<!doctype html><meta charset="utf-8"><title>Independent model instance replay</title><style>body{background:#202938;color:white;font:16px system-ui}figure{display:inline-block}img{width:480px;image-rendering:pixelated}</style><h1>Static instance engineering proof</h1>'
    for name, item in frames.items(): index += '<figure><figcaption>'+name+'</figcaption><img src="'+Path(item['file']).relative_to(out).as_posix()+'"></figure>'
    (out/'index.html').write_text(index)
    evidence = {'format': 'model-instance-public-replay', 'schema_version': 1, 'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'source_files': {str(p.relative_to(ROOT)): digest(p) for p in [ROOT/'ambiance_studio/model_instances.py', ROOT/'ambiance_studio/model_evidence.py', ROOT/'tools/model/instance.mjs', ROOT/'ambiance_studio/scene_transactions.py']},
        'steps': steps, 'facts': facts, 'frames': frames, 'observations': [],
        'files': {p.relative_to(out).as_posix(): digest(p) for p in sorted(out.rglob('*')) if p.is_file()},
        'limitations': ['Static geometric engineering art, no whole-scene or artistic acceptance.', 'Receiver contribution stays on receiver within authored bounds; no automatic light transport.']}
    studio.write(out/'evidence.json', evidence)
    return {'evidence': str(out/'evidence.json'), 'sha256': digest(out/'evidence.json'), 'html': str(out/'index.html'), 'facts': facts}


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--out', type=Path, required=True)
    print(json.dumps(replay(p.parse_args().out), indent=2))
