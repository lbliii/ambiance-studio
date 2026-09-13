"""Immutable local construction, lowering and source-bound technical proof records."""
from pathlib import Path
import html
import shutil

import studio
from .edge_quality import fresh_output
from .file_identity import digest
from .record_contracts import seal, read_sealed, fields, identifier
from .model_definition import DefinitionClosure, ROLES
from .native_media import json_command, ROOT


def implementation():
    names = ['ambiance_studio/model_definition.py', 'ambiance_studio/model_package.py',
             'ambiance_studio/record_contracts.py', 'ambiance_studio/file_identity.py',
             'ambiance_studio/assets.py', 'ambiance_studio/edge_quality.py', 'tools/asset_tool.py',
             'tools/rig-proof.mjs', 'editor/source-placement.mjs']
    names += [p.relative_to(ROOT).as_posix() for folder in ['editor', 'tools/render', 'tools/model'] for p in (ROOT/folder).glob('*.mjs')]
    return {name: digest(ROOT/name) for name in sorted(set(names))}


def bridge(closure, root, action='lower', **kwargs):
    node = shutil.which('node')
    if not node: raise ValueError('Node is required for model lowering')
    return json_command([node, ROOT/'tools/model/bridge.mjs'], {'action': action, 'root': root,
        'models': closure.models, 'source_root': str(closure.root), **kwargs})


def copy_files(source, target, files):
    for name, sha in files.items():
        destination = target/name; destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source/name, destination)
        if digest(destination) != sha: raise ValueError('Input changed while materializing model package')


def tree_hashes(root, exclude=()):
    entries = sorted(root.rglob('*'))
    if any(p.is_symlink() for p in entries): raise ValueError('Package/proof files cannot use symlinks')
    return {p.relative_to(root).as_posix(): digest(p) for p in entries if p.is_file() and p.relative_to(root).as_posix() not in exclude}


def build(definition, source_root, out):
    closure = DefinitionClosure(source_root)
    root = closure.model(Path(definition).resolve(strict=True))
    # Shared evaluator validates registration, all control writers and every compatible replacement.
    bridge(closure, root)
    with fresh_output(out) as stage:
        copy_files(closure.root, stage/'source', closure.files)
        reopened = DefinitionClosure(stage/'source'); reopened_root = reopened.model(stage/'source'/root)
        bridge(reopened, reopened_root)
        manifest = seal({'format': 'ambiance-model-package', 'schema_version': 1,
            'definition': {'file': root, 'sha256': closure.files[root], 'model_id': closure.models[root]['model_id'], 'version': closure.models[root]['version']},
            'path_base': 'package/source', 'files': dict(sorted(closure.files.items())),
            'implementation': implementation(), 'status': 'technical-candidate',
            'limitations': ['Static named poses only; no scene instance/adoption or artistic acceptance.']})
        studio.write(stage/'model-package.json', manifest)
        closure.verify()
    return {'ok': True, 'package': str(Path(out).resolve()), 'manifest_sha256': digest(Path(out)/'model-package.json'), 'definition': manifest['definition'], 'file_count': len(closure.files), 'status': manifest['status']}


def open_package(package):
    package = Path(package).resolve(strict=True)
    manifest = read_sealed(package/'model-package.json', 'ambiance-model-package')
    closure = DefinitionClosure(package/'source')
    root = closure.model(closure.file(closure.root, manifest['definition']['file'], manifest['definition']['sha256']), manifest['definition'])
    if closure.files != manifest['files']: raise ValueError('Package transitive closure differs from manifest')
    if tree_hashes(package/'source') != manifest['files']: raise ValueError('Unlisted or changed package sources')
    return package, manifest, closure, root


def inspect(package):
    package = Path(package).resolve(strict=True)
    entry = None
    if (package/'model-entry.json').is_file():
        entry = read_sealed(package/'model-entry.json', 'ambiance-local-model-entry')
        if tree_hashes(package, ['model-entry.json']) != entry['files']: raise ValueError('Local entry bytes changed')
        check(package/'proof', package/'package', package/'proof-recipe.json')
        package = package/'package'
    package, manifest, closure, root = open_package(package)
    lowered = bridge(closure, root)
    return {'ok': True, 'package': str(package), 'definition': manifest['definition'], 'file_count': len(closure.files),
            'status': manifest['status'], 'model_count': len(closure.models), 'members': lowered['mapping'],
            'controls': lowered['effective_controls'], 'variants': lowered['selected_variants'],
            'mounts': [{k:m[k] for k in ['part_path','parent_part_path','rest_offset_local_pixels','max_world_corner_error_pixels']} for m in lowered['mounts']],
            'acceptance': 'not established', 'local_entry': entry is not None}


def lower(package, state_file, out):
    package, manifest, closure, root = open_package(package)
    state_hash = digest(state_file); state = studio.read(state_file)
    sources = implementation()
    result = bridge(closure, root, state=state)
    with fresh_output(out) as stage:
        shutil.copytree(package, stage/'package')
        for asset in result['catalog']['assets']:
            asset['file'] = 'package/source/'+asset['file']
            asset['provenance']['recipe'] = 'package/source/'+asset['provenance']['recipe']
        studio.write(stage/'scene/scene.json', result['scene']); studio.write(stage/'assets/catalog.json', result['catalog'])
        studio.write(stage/'ambiance-project.json', {'version': 1, 'id': 'model-local', 'title': 'Local model proof', 'scene': 'scene/scene.json', 'catalog': 'assets/catalog.json'})
        studio.write(stage/'mapping.json', {k:v for k,v in result.items() if k not in ['scene','catalog']})
        studio.write(stage/'model-lowering.json', seal({'format': 'ambiance-model-lowering', 'schema_version': 1,
            'package_sha256': digest(package/'model-package.json'), 'state': state, 'state_sha256': state_hash, 'implementation': sources,
            'files': tree_hashes(stage)}))
        closure.verify()
        if digest(state_file) != state_hash or implementation() != sources: raise ValueError('Lowering inputs changed before publication')
    return {'ok': True, 'directory': str(Path(out).resolve()), 'scene': str(Path(out).resolve()/'scene/scene.json'),
            'mapping': str(Path(out).resolve()/'mapping.json'), 'report_sha256': digest(Path(out)/'model-lowering.json')}


def recipe_read(path):
    recipe = studio.read(path)
    fields(recipe, ['schema_version', 'states', 'roles', 'threshold'], 'model proof recipe')
    if recipe['schema_version'] != 1 or not isinstance(recipe['states'], list) or not 1 <= len(recipe['states']) <= 32: raise ValueError('Proof needs 1–32 named static states')
    ids = [identifier(s['pose_id']) for s in recipe['states']]
    if len(set(ids)) != len(ids): raise ValueError('Duplicate proof pose ID')
    if not isinstance(recipe['roles'], list) or len(set(recipe['roles'])) != len(recipe['roles']) or any(r not in ROLES for r in recipe['roles']): raise ValueError('Invalid proof roles')
    if type(recipe['threshold']) is not int or not 1 <= recipe['threshold'] <= 255: raise ValueError('Threshold must be in [1,255]')
    return recipe


def proof(package, recipe_file, out):
    package, manifest, closure, root = open_package(package)
    recipe_hash = digest(recipe_file); recipe = recipe_read(recipe_file); sources = implementation()
    for state in recipe['states']: bridge(closure, root, state=state)
    frame = closure.models[root]['local_frame']['size']
    if any(type(n) is not int for n in frame) or frame[0]*frame[1]*len(recipe['states'])*(len(recipe['roles'])+1) > 64_000_000: raise ValueError('Proof raster budget requires integer frame dimensions and <=64M role pixels')
    with fresh_output(out) as stage:
        result = bridge(closure, root, action='proof', recipe=recipe, out=str(stage))
        studio.write(stage/'recipe.json', recipe)
        cards = []
        for sample in result['samples']:
            name = sample['pose_id']
            cards.append('<section><h2>'+html.escape(name)+'</h2><figure><img src="'+name+'/source-versus-assembly.png"><figcaption>Original sources / compiled assembly</figcaption></figure>'+''.join(f'<figure><img src="{name}/{role}.png"><figcaption>{role}</figcaption></figure>' for role in ['composite',*recipe['roles']])+'</section>')
        page = '<!doctype html><meta charset="utf-8"><title>Local model proof</title><style>body{font:16px system-ui;background:#202530;color:#eee}section{border-top:1px solid #777}figure{display:inline-block}img{width:192px;background:repeating-conic-gradient(#bbb 0% 25%,#eee 0% 50%) 50%/16px 16px}figcaption{padding:8px}</style><h1>Local model technical proof</h1><p>Static samples, authored roles, exact package. Artistic acceptance and scene receiver/removal proof remain open.</p>'+''.join(cards)
        (stage/'index.html').write_text(page)
        report = seal({'format': 'ambiance-model-proof', 'schema_version': 1,
            'package_sha256': digest(package/'model-package.json'), 'definition': manifest['definition'], 'source_files': manifest['files'],
            'recipe_sha256': recipe_hash, 'recipe': recipe, 'implementation': sources, 'runtime': result['runtime'],
            'samples': result['samples'], 'files': tree_hashes(stage), 'acceptance': 'not established'})
        studio.write(stage/'model-proof.json', report)
        closure.verify()
        if digest(recipe_file) != recipe_hash or implementation() != sources: raise ValueError('Proof inputs changed before publication')
    return {'ok': True, 'directory': str(Path(out).resolve()), 'html': str(Path(out).resolve()/'index.html'),
            'report': str(Path(out).resolve()/'model-proof.json'), 'report_sha256': digest(Path(out)/'model-proof.json'), 'samples': len(result['samples']), 'acceptance': 'not established'}


def check(proof_dir, package, recipe_file):
    proof_dir = Path(proof_dir).resolve(strict=True)
    report = read_sealed(proof_dir/'model-proof.json', 'ambiance-model-proof')
    package, manifest, closure, root = open_package(package)
    recipe = recipe_read(recipe_file)
    if digest(package/'model-package.json') != report['package_sha256'] or manifest['files'] != report['source_files']: raise ValueError('Stale proof package/dependencies')
    if digest(recipe_file) != report['recipe_sha256'] or recipe != report['recipe']: raise ValueError('Stale proof state/role policy')
    if implementation() != report['implementation']: raise ValueError('Stale proof implementation')
    runtime = bridge(closure, root, action='runtime'); runtime.pop('ok', None)
    if runtime != report['runtime']: raise ValueError('Stale proof runtime')
    if tree_hashes(proof_dir, ['model-proof.json']) != report['files']: raise ValueError('Changed/unlisted proof artifacts')
    if len(report['samples']) != len(recipe['states']): raise ValueError('Proof sample count differs')
    for state, sample in zip(recipe['states'], report['samples']):
        current = bridge(closure, root, state=state); current.pop('ok', None)
        if current != sample['resolved']: raise ValueError('Stale resolved state')
    return {'ok': True, 'report': str(proof_dir/'model-proof.json'), 'report_sha256': digest(proof_dir/'model-proof.json'), 'status': 'current-technical-proof', 'acceptance': 'not established'}


def admit(package, proof_dir, recipe_file, out):
    checked = check(proof_dir, package, recipe_file)
    with fresh_output(out) as stage:
        shutil.copytree(package, stage/'package'); shutil.copytree(proof_dir, stage/'proof')
        shutil.copyfile(recipe_file, stage/'proof-recipe.json')
        check(stage/'proof', stage/'package', stage/'proof-recipe.json')
        manifest = read_sealed(stage/'package/model-package.json', 'ambiance-model-package')
        record = seal({'format': 'ambiance-local-model-entry', 'schema_version': 1, 'definition': manifest['definition'],
                       'package': 'package/model-package.json', 'proof': 'proof/model-proof.json',
                       'status': 'technical-candidate', 'acceptance': 'not established', 'files': tree_hashes(stage)})
        studio.write(stage/'model-entry.json', record)
    return {'ok': True, 'directory': str(Path(out).resolve()), 'entry_sha256': digest(Path(out)/'model-entry.json'), 'status': 'technical-candidate', 'proof_sha256': checked['report_sha256'], 'acceptance': 'not established'}
