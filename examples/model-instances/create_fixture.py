"""A contained engineering scene using existing mc/1 art, never a film edit."""
import importlib.util
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import studio
from ambiance_studio.project_commands import init_project


def create(project):
    project = Path(project).resolve()
    init_project(project, None, 'Independent model engineering fixture', 'blank')
    data = studio.read(ROOT/'tests/fixtures/model-contract/runtime.json')
    scene = data['scene']
    scene['layers'] = [l for l in scene['layers'] if l['id'] in ['ground', 'ground-a-light', 'unrelated-light']]
    scene['finishing']['signals'] = [{'id': 'unrelated-source', 'layer': 'ground', 'values': [.8]}]
    scene['bindings']['links'][0].update(id='unrelated-binding', source={'signal': 'unrelated-source', 'range': [0, 1]}, target={'layer': 'unrelated-light', 'channel': 'opacity', 'range': [0, 1]})
    from ambiance_studio.scene_runtime import scene_bridge
    catalog = {'version': 1, 'assets': []}
    for asset in data['catalog']['assets']:
        if asset['id'] not in ['ground-v1', 'light-v1']: continue
        asset['kind'] = 'image'; asset['file'] = 'assets/'+Path(asset['file']).name
        shutil.copyfile(ROOT/'tests/fixtures/model-contract/art'/Path(asset['file']).name, project/asset['file'])
        catalog['assets'].append(asset)
    scene_bridge('inspect', scene, catalog, {'full': True})
    studio.write(project/'scene/scene.json', scene); studio.write(project/'assets/catalog.json', catalog)
    return project


def model_source(out):
    spec = importlib.util.spec_from_file_location('construction_fixture', ROOT/'examples/model-construction/create_fixture.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module.create(out)
