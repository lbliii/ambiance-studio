"""Resolve source-placement identities before the shared JavaScript transaction.

No scene is saved here. The CLI owns project locking, scene snapshots and its
expected-scene check; verify_dependencies must run again immediately before save.
"""
import copy
import hashlib
import io
import json
from pathlib import Path


def _path(project, relative):
    if not isinstance(relative,str) or not relative or Path(relative).is_absolute():
        raise ValueError('Placement manifest references must be project-relative')
    target=(project/relative).resolve()
    if not target.is_relative_to(project):raise ValueError(f'Placement reference escapes project: {relative}')
    return target


def placement_batch(manifest):
    if not isinstance(manifest,dict) or set(manifest)-{'version','kind','placements'} or manifest.get('version')!=1 or manifest.get('kind')!='ambiance-source-placement' or not isinstance(manifest.get('placements'),list) or not manifest['placements']:
        raise ValueError('Expected ambiance-source-placement version 1 with nonempty placements')
    if any(not isinstance(row,dict) or 'op' in row for row in manifest['placements']):
        raise ValueError('Placement records contain operation fields without an op name')
    return {'version':1,'operations':[{'op':'place_from_source',**copy.deepcopy(row)} for row in manifest['placements']]}


def resolve_batch(project,scene,catalog,batch):
    project=Path(project).resolve();batch=copy.deepcopy(batch);dependencies={}
    if not isinstance(batch,dict) or batch.get('version')!=1 or not isinstance(batch.get('operations'),list):
        raise ValueError('Expected a version 1 scene batch')
    assets={a['id']:a for a in catalog['assets']};layers={l['id']:l['asset'] for l in scene['layers']}

    def pin(relative,expected,role,dimensions=None):
        target=_path(project,relative);data=target.read_bytes();digest=hashlib.sha256(data).hexdigest()
        if expected is not None and digest!=expected:raise ValueError(f'Placement dependency changed: {relative}')
        key=str(target.relative_to(project))
        prior=dependencies.get(key)
        if prior and prior['sha256']!=digest:raise ValueError(f'Placement dependency changed during resolution: {relative}')
        if dimensions is not None:
            from PIL import Image
            with Image.open(io.BytesIO(data)) as image:
                if image.size!=tuple(dimensions):raise ValueError(f'Placement image dimensions differ: {relative}')
        if not prior:dependencies[key]={'file':key,'sha256':digest,'bytes':len(data),'resolved_path':str(target),'path_base':'project','roles':[]}
        if role not in dependencies[key]['roles']:dependencies[key]['roles'].append(role)
        return data

    def image(record,role):
        if not isinstance(record,dict) or any(k not in record for k in ['file','sha256','width','height']):raise ValueError(f'{role} needs image identity')
        if not isinstance(record['sha256'],str) or len(record['sha256'])!=64 or any(c not in '0123456789abcdef' for c in record['sha256']) or any(type(record[k]) is not int or record[k]<=0 for k in ['width','height']):
            raise ValueError(f'{role} needs SHA-256 and positive integer dimensions')
        return pin(record['file'],record['sha256'],role,[record['width'],record['height']])

    def recipe_relative(recipe,relative):
        if not isinstance(relative,str) or Path(relative).is_absolute():raise ValueError('Compiler source references must be recipe-relative')
        target=(recipe.parent/relative).resolve()
        if not target.is_relative_to(project):raise ValueError(f'Compiler source escapes placement project: {relative}')
        return str(target.relative_to(project))

    def check_asset(aid):
        if aid not in assets:raise ValueError(f'Unknown placement asset: {aid}')
        asset=assets[aid];image(asset,f'placement asset {aid}')
        provenance=asset.get('provenance',{});recipe_ref=provenance.get('recipe')
        if recipe_ref:
            recipe_file=_path(project,recipe_ref)
            if recipe_file.name!='recipe.json':raise ValueError(f'Catalog recipe must identify the compiled pack recipe.json: {aid}')
            recipe=json.loads(pin(recipe_ref,None,f'compiler recipe {aid}'))
            # Reuse the pack integrity policy, then pin its current records.
            from .assets import inspect_pack
            checked=inspect_pack(recipe_file.parent)
            if not checked['ok']:raise ValueError(f'Placement pack changed: {aid}')
            packed=checked['asset']
            for key in ['id','sha256','width','height','atlas','pivot','registration_mapping']:
                if packed.get(key)!=asset.get(key):raise ValueError(f'Catalog/pack placement metadata differs: {aid} ({key})')
            packed_provenance=packed.get('provenance',{})
            for key in ['sources','registration_source','source_mapping','edge_preparation']:
                if provenance.get(key)!=packed_provenance.get(key):raise ValueError(f'Catalog/pack source provenance differs: {aid} ({key})')
            for name in ['asset.json','report.json']:
                pin(str((recipe_file.parent/name).relative_to(project)),None,f'compiler record {aid}')
            spec=recipe['input'];source_names=[spec['sheet']] if 'sheet' in spec else spec['frames']
            refs=packed_provenance.get('sources',[])
            if len(source_names)!=len(refs):raise ValueError(f'Recipe input/source provenance count differs: {aid}')
            for name,ref in zip(source_names,refs):
                if recipe_relative(recipe_file,name)!=recipe_relative(recipe_file,ref['file']):raise ValueError(f'Recipe input/source provenance path differs: {aid}')
                pin(recipe_relative(recipe_file,ref['file']),ref['sha256'],f'prepared source {aid}')
            for label in ['registration_source','source_mapping','edge_preparation']:
                ref=packed_provenance.get(label)
                if recipe.get(label)!=ref:raise ValueError(f'Recipe/pack {label} provenance differs: {aid}')
                if ref:
                    relative=recipe_relative(recipe_file,ref['file'])
                    pin(relative,ref['sha256'],f'{label} {aid}')
                    if label=='edge_preparation':
                        from .edge_quality import validate_edge_preparation
                        checked_edge=validate_edge_preparation(_path(project,relative),ref['sha256'],
                            [_path(project,recipe_relative(recipe_file,name)) for name in source_names])
                        for dependency in checked_edge['dependencies']:
                            path=Path(dependency['path']).resolve()
                            if not path.is_relative_to(project):raise ValueError('Edge-preparation dependency must be inside the scene project')
                            pin(str(path.relative_to(project)),dependency['sha256'],dependency['role'])
            mapping=asset.get('registration_mapping',{})
            for source in mapping.get('input_sources',[]):
                pin(recipe_relative(recipe_file,source['file']),source['sha256'],f'mapped input {aid}',[source['width'],source['height']])
            if mapping.get('reference'):image(mapping['reference'],f'mapped reference {aid}')
        elif asset.get('registration_mapping'):
            raise ValueError(f'Compiler registration mapping needs its verifiable recipe/pack: {aid}')

    has_placement=False
    finishing_config=scene.get('finishing');has_finishing=finishing_config is not None
    for op in batch['operations']:
        if not isinstance(op,dict):raise ValueError('Each operation must be an object')
        action=op.get('op')
        if action=='place_from_source':
            has_placement=True
            if op.get('base') not in layers:raise ValueError(f'Placement base must exist before operation: {op.get("base")}')
            image(op.get('reference'),f'reference for {op.get("id")}')
            for aid in [layers[op['base']],op.get('asset')]:check_asset(aid)
            for name in ['mapping','base_mapping']:
                value=op.get(name)
                if isinstance(value,dict) and set(value)=={'file','sha256'}:
                    op[name]=json.loads(pin(value['file'],value['sha256'],f'explicit {name} for {op.get("id")}'))
                value=op.get(name)
                if isinstance(value,dict) and value.get('reference'):image(value['reference'],f'explicit {name} reference')
            layers[op['id']]=op['asset']
        elif action=='add':layers[op['id']]=op.get('values',{}).get('asset',op.get('asset'))
        elif action=='replace':layers[op['layer']]=op['value']['asset']
        elif action=='set' and 'asset' in op.get('values',{}):layers[op['layer']]=op['values']['asset']
        elif action=='remove':layers.pop(op.get('layer'),None)
        elif action=='finishing':finishing_config=op.get('value');has_finishing=True
    if has_finishing:
        from .finishing import dependency_roles
        for aid,roles in dependency_roles({'layers':[{'asset':aid} for aid in layers.values()], 'finishing':finishing_config}).items():
            check_asset(aid)
            image(assets[aid],', '.join(roles))
    if has_placement or has_finishing:
        conf_file=project/'ambiance-project.json'
        if conf_file.is_file():
            conf=json.loads(pin('ambiance-project.json',None,'project configuration'))
            if conf.get('catalog'):
                current=json.loads(pin(conf['catalog'],None,'placement catalog'))
                if current!=catalog:raise ValueError('Placement catalog changed during resolution')
    records=list(dependencies.values());verify_dependencies(project,records)
    return batch,records


def verify_dependencies(project,records):
    project=Path(project).resolve()
    for record in records:
        if record.get('path_base')=='absolute':
            path=Path(record['file'])
            if not path.is_absolute() or str(path.resolve())!=record.get('resolved_path'):raise ValueError('Invalid absolute command-input dependency')
            if record.get('requested_path') and Path(record['requested_path']).resolve()!=path.resolve():raise ValueError('Command-input dependency target changed before save')
        else:path=_path(project,record['file'])
        data=path.read_bytes()
        if len(data)!=record['bytes'] or hashlib.sha256(data).hexdigest()!=record['sha256']:
            raise ValueError(f'Placement dependency changed before save: {record["file"]}')
    return True
