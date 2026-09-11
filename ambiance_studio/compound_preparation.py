"""Agent-authored compound separations over the existing mask/compiler/runtime APIs."""
import copy
import json
from pathlib import Path
import re

from . import asset_prep as ap, preparation as single
from .edge_quality import fresh_output, integer
from .generation_ledger import canonical, checked_ref, identifier

FORMAT = 'ambiance-compound-preparation'
RECEIPT = 'ambiance-preparation-receipt'


def subrecipe(recipe, part):
    return {'format': single.FORMAT, 'version': 1, 'path_base': 'project', 'title': recipe['title'],
            'source': part.get('source', recipe['source']), 'backing': recipe['backing'],
            'backing_to_source': recipe['backing_to_source'], 'resampling': recipe['resampling'],
            'masks': {'removal': recipe['removal'], 'cutout': part['mask'], 'occluder': {'polygons': []}},
            'motion': {'pivot': part['pivot'], 'delta': part.get('motion', {}).get('delta', [0, 0]),
                       'rotation_degrees': part.get('motion', {}).get('rotation_degrees', 0), 'seconds': recipe['seconds']}}


def validate(recipe):
    ap.fields(recipe, ['format', 'version', 'path_base', 'title', 'source', 'backing', 'backing_to_source',
                       'resampling', 'removal', 'parts', 'seconds', 'context'], 'compound preparation')
    if recipe.get('format') != FORMAT or type(recipe.get('version')) is not int or recipe['version'] != 1 or recipe.get('path_base') != 'project':
        raise ValueError(f'Expected {FORMAT} version 1, path_base project')
    parts = recipe.get('parts')
    if not isinstance(parts, list) or not 1 <= len(parts) <= 16: raise ValueError('Compound recipe needs 1–16 explicit parts')
    ids = {'backing', 'source', 'rest', 'removal-mask', 'difference', 'registered-backing'}
    for part in parts:
        ap.fields(part, ['id', 'kind', 'source', 'mask', 'pivot', 'motion', 'companions', 'binding'], 'compound part')
        id = identifier(part.get('id'), 'part ID')
        if id in ids: raise ValueError(f'Duplicate or reserved part ID: {id}')
        ids.add(id)
        if part.get('kind') not in ['cutout', 'occluder']: raise ValueError('Part kind must be cutout or fixed occluder')
        if part['kind'] == 'occluder' and 'motion' in part: raise ValueError('Fixed occluders cannot own proof motion')
        if 'motion' in part: ap.fields(part['motion'], ['delta', 'rotation_degrees'], 'part motion')
        single.validate(subrecipe(recipe, part))
        if [subrecipe(recipe, part)['source'][k] for k in ['width', 'height']] != [recipe['source'][k] for k in ['width', 'height']]:
            raise ValueError('Reconstructed part sources must retain the complete reference canvas')
        companions = part.get('companions', [])
        if not isinstance(companions, list) or len(companions) > 4: raise ValueError('Each part supports at most four registration companions')
        for companion in companions:
            ap.fields(companion, ['id', 'image'], 'registration companion')
            cid = identifier(companion.get('id'), 'companion ID')
            if cid in ids: raise ValueError(f'Duplicate companion/part ID: {cid}')
            ids.add(cid)
            # Validate a companion through the existing full-source grayscale-mask contract.
            test = subrecipe(recipe, part); test['masks']['cutout'] = {'polygons': [], 'image': companion.get('image')}
            single.validate(test)
        if part.get('binding') is not None:
            ap.fields(part['binding'], ['element_id', 'inventory_part'], 'part binding')
            identifier(part['binding'].get('element_id'), 'element_id')
            ap.fields(part['binding'].get('inventory_part'), ['item_id', 'part_id'], 'inventory part')
            for key in ['item_id', 'part_id']: identifier(part['binding']['inventory_part'].get(key), key)
    if recipe['source']['width'] * recipe['source']['height'] * len(ids) > 67_108_864:
        raise ValueError('Compound recipe exceeds the 64M aggregate pixel budget; split the preparation')
    if max(recipe['source']['width'], recipe['source']['height']) > 4092:
        raise ValueError('Compound source must leave two pixels of compiler padding per side (maximum 4092)')
    context = recipe.get('context')
    if context is not None:
        ap.fields(context, ['scene', 'views', 'source_to_scene', 'production_plan', 'inventory'], 'preparation context')
        for key in ['scene', 'production_plan', 'inventory']:
            ap.fields(context.get(key), ['file', 'sha256'], key+' identity')
        if not isinstance(context.get('views'), list) or not context['views'] or len(context['views']) > 8 or len(set(context['views'])) != len(context['views']):
            raise ValueError('Context views must list 1–8 distinct saved view IDs')
        for view in context['views']: identifier(view, 'view ID')
        ap.affine(context.get('source_to_scene'))
    return recipe


def references(recipe):
    yield 'source', recipe['source']
    yield 'backing', recipe['backing']
    if 'image' in recipe['removal']: yield 'removal-mask', recipe['removal']['image']
    for part in recipe['parts']:
        if 'source' in part: yield part['id']+'-source', part['source']
        if 'image' in part['mask']: yield part['id']+'-mask', part['mask']['image']
        for companion in part.get('companions', []): yield companion['id']+'-mask', companion['image']


def load_inputs(project, recipe):
    validate(recipe)
    inputs = {role: ap.project_file(project, ref['file']).read_bytes() for role, ref in references(recipe)}
    for role, ref in references(recipe):
        if ap.sha(inputs[role]) != ref['sha256']: raise ValueError(f'Preparation input changed: {ref["file"]}')
    return inputs


def evaluate(recipe, inputs):
    from PIL import Image, ImageChops
    import io
    validate(recipe)
    images = {}; facts = {}; warnings = []
    for index, part in enumerate(recipe['parts']):
        spec = subrecipe(recipe, part)
        local = {'source': inputs.get(part['id']+'-source', inputs['source']), 'backing': inputs['backing']}
        if 'removal-mask' in inputs: local['removal'] = inputs['removal-mask']
        if part['id']+'-mask' in inputs: local['cutout'] = inputs[part['id']+'-mask']
        result, info, messages = single.evaluate(spec, local)
        if index == 0:
            # Shared backing always repairs the original reference, even when this part has reconstructed paint.
            base = copy.deepcopy(spec); base['source'] = recipe['source']
            base_result, _, _ = single.evaluate(base, {**local, 'source': inputs['source']})
            images.update({key: base_result[key] for key in ['source', 'backing', 'removal-mask', 'registered-backing']})
        images[part['id']] = result['cutout']; images[part['id']+'-mask'] = result['cutout-mask']
        facts[part['id']] = info
        # Fixed occluders intentionally may lie outside the removal area.
        if part['kind'] == 'occluder': messages = [m for m in messages if 'outside the removal' not in m]
        warnings += [{'part': part['id'], 'message': m} for m in messages]
        for companion in part.get('companions', []):
            data = inputs[companion['id']+'-mask']
            if ap.sha(data) != companion['image']['sha256']: raise ValueError('Companion mask changed')
            with Image.open(io.BytesIO(data)) as mask:
                if mask.mode != 'L' or mask.size != images['source'].size or getattr(mask, 'n_frames', 1) != 1:
                    raise ValueError('Companion must be a still grayscale mask on the complete reference canvas')
                image = Image.new('RGBA', mask.size, 'white'); image.putalpha(mask)
                images[companion['id']] = image
    rest = images['backing'].copy()
    for kind in ['cutout', 'occluder']:
        for part in recipe['parts']:
            if part['kind'] == kind: rest = Image.alpha_composite(rest, images[part['id']])
    images['rest'] = rest
    difference = ImageChops.difference(rest, images['source'])
    channels = difference.split(); changed = channels[0]
    for channel in channels[1:]: changed = ImageChops.lighter(changed, channel)
    changed = changed.point(lambda n: 255 if n else 0)
    overlay = Image.new('RGBA', rest.size, '#ee508a'); overlay.putalpha(changed.point(lambda n: 190 if n else 0))
    images['difference'] = Image.alpha_composite(images['source'], overlay)
    overlaps = []
    for a in recipe['parts']:
        for b in recipe['parts']:
            if a['id'] >= b['id'] or {a['kind'], b['kind']} != {'cutout', 'occluder'}: continue
            overlap = ImageChops.multiply(images[a['id']].getchannel('A'), images[b['id']].getchannel('A'))
            count = sum(overlap.histogram()[1:])
            if count: overlaps.append({'parts': [a['id'], b['id']], 'pixels': count})
    if overlaps: warnings.append({'part': None, 'message': 'Cutout/occluder masks overlap. Inspect moving foreground fragments; declare/reconstruct hidden subject paint explicitly.'})
    return images, {'parts': facts, 'changed_rest_pixels': sum(changed.histogram()[1:]), 'cutout_occluder_overlaps': overlaps}, warnings


def context_inputs(project, recipe):
    context = recipe.get('context')
    if context is None: return {}, None
    inputs = {key: checked_ref(project, context[key]).read_bytes() for key in ['scene', 'production_plan', 'inventory']}
    scene = json.loads(inputs['scene']); inventory = json.loads(inputs['inventory']); plan = json.loads(inputs['production_plan'])
    from .scene_runtime import scene_bridge
    info = scene_bridge('view-inspect', scene, {'version': 1, 'assets': []}, {})
    selected = {}
    for id in context['views']:
        if id not in info['views']: raise ValueError(f'Saved composition is missing: {id}')
        selected[id] = info['views'][id]
    from . import production_plan
    production_plan.validate(project, plan)
    for part in recipe['parts']:
        if not part.get('binding'): raise ValueError(f'Bound preparation requires element/inventory references for {part["id"]}')
        production_plan.validate_binding(project, part['binding'], plan)
    return inputs, {'views': selected, 'canvas': scene['canvas'], 'framing': scene.get('framing'),
                    'source_to_scene': context['source_to_scene']}


def inspect(project, path, check=False):
    project, path = Path(project).resolve(), Path(path).resolve()
    if path.is_dir(): path = path/'recipe.json'
    raw = path.read_bytes(); recipe = json.loads(raw)
    if recipe.get('format') == single.FORMAT:
        inputs = single.load_inputs(project, recipe); images, facts, warnings = single.evaluate(recipe, inputs)
        return {'ok': not warnings if check else True, 'recipe': str(path), 'sha256': ap.sha(raw), 'version': 1,
                'facts': facts, 'warnings': warnings, 'next_action': 'Use prepare init to capture a compound authoring recipe.'}
    inputs = load_inputs(project, recipe); _, context = context_inputs(project, recipe)
    _, facts, warnings = evaluate(recipe, inputs)
    return {'ok': not warnings if check else True, 'recipe': str(path), 'sha256': ap.sha(raw), 'format': FORMAT,
            'parts': [{'id': p['id'], 'kind': p['kind'], 'pivot_source_px': p['pivot'], 'binding': p.get('binding'),
                       'companions': [c['id'] for c in p.get('companions', [])]} for p in recipe['parts']],
            'source': recipe['source'], 'views': context['views'] if context else {}, 'facts': facts,
            'warnings': warnings, 'production_context': 'bound' if context else 'unbound study',
            'review_needed': ['Hidden, rest and extreme raster inspection; ordinary normal-speed playback in every intended view.'],
            'next_action': 'Repair identified paint/mask gaps; use prepare edit, build and proof. Motion reduction is not reconstruction.'}


def checkpoint(out, recipe, parent=None, batch=None):
    with fresh_output(out) as stage:
        ap.write(stage/'recipe.json', recipe)
        if parent is not None: (stage/'parent-recipe.json').write_bytes(parent)
        if batch is not None: (stage/'batch.json').write_bytes(batch)
        ap.write(stage/'edit-receipt.json', {'format': 'ambiance-preparation-edit', 'version': 1,
                  'recipe_sha256': ap.sha((stage/'recipe.json').read_bytes()),
                  'parent_sha256': ap.sha(parent) if parent else None, 'batch_sha256': ap.sha(batch) if batch else None})
    return {'ok': True, 'recipe': str(Path(out).resolve()/'recipe.json'), 'receipt': str(Path(out).resolve()/'edit-receipt.json'),
            'sha256': ap.sha((Path(out)/'recipe.json').read_bytes()), 'next_action': 'Inspect/check this immutable checkpoint; build it into a fresh directory.'}


def initialize(project, file, out, context_file=None):
    path = Path(file); path = path/'recipe.json' if path.is_dir() else path
    raw = path.read_bytes(); old = json.loads(raw)
    if old.get('format') == FORMAT: recipe = old
    else:
        single.load_inputs(project, old)
        recipe = {'format': FORMAT, 'version': 1, 'path_base': 'project', 'title': old['title'],
                  **{k: old[k] for k in ['source', 'backing', 'backing_to_source', 'resampling']},
                  'removal': old['masks']['removal'], 'seconds': old['motion']['seconds'], 'context': None,
                  'parts': [{'id': 'subject', 'kind': 'cutout', 'mask': old['masks']['cutout'], 'pivot': old['motion']['pivot'],
                             'motion': {k: old['motion'][k] for k in ['delta', 'rotation_degrees']}},
                            {'id': 'foreground', 'kind': 'occluder', 'mask': old['masks']['occluder'], 'pivot': [0, 0]}]}
    if context_file: recipe['context'] = ap.load(context_file)
    load_inputs(project, recipe)
    return checkpoint(out, recipe, raw)


def edit(project, file, batch_file, out, expected):
    path = Path(file); path = path/'recipe.json' if path.is_dir() else path
    raw = path.read_bytes(); recipe = json.loads(raw); validate(recipe)
    if not expected or ap.sha(raw) != expected: raise ValueError('Preparation recipe changed; inspect and supply its exact --expect-sha256')
    batch_raw = Path(batch_file).read_bytes(); batch = json.loads(batch_raw)
    ap.fields(batch, ['version', 'operations'], 'preparation batch')
    if type(batch.get('version')) is not int or batch['version'] != 1 or not isinstance(batch.get('operations'), list) or not 1 <= len(batch['operations']) <= 64:
        raise ValueError('A preparation batch needs 1–64 operations')
    recipe = copy.deepcopy(recipe)
    for op in batch['operations']:
        ap.fields(op, ['op', 'part', 'value', 'mask'], 'preparation operation')
        action = op.get('op')
        part = next((p for p in recipe['parts'] if p['id'] == op.get('part')), None)
        if action in ['set-mask', 'append-polygon']:
            if op.get('mask') == 'removal' and 'part' not in op: target = recipe; key = 'removal'
            elif part and op.get('mask') == 'cutout': target = part; key = 'mask'
            else: raise ValueError('Mask operation needs mask=removal, or an existing part and mask=cutout')
            if action == 'set-mask': target[key] = op['value']
            else: target[key]['polygons'].append(op['value'])
        elif action in ['set-motion', 'set-pivot', 'set-binding', 'set-companions', 'set-source']:
            if not part: raise ValueError('Preparation operation names an unknown part')
            part[action.removeprefix('set-')] = op['value']
        elif action == 'add-part': recipe['parts'].append(op['value'])
        elif action == 'remove-part':
            if not part: raise ValueError('Cannot remove an unknown part')
            recipe['parts'].remove(part)
        elif action in ['set-alignment', 'set-context', 'set-seconds']:
            recipe[{'set-alignment': 'backing_to_source', 'set-context': 'context', 'set-seconds': 'seconds'}[action]] = op['value']
        else: raise ValueError(f'Unsupported preparation operation: {action}')
    load_inputs(project, recipe)
    if recipe.get('context'): context_inputs(project, recipe)
    if path.read_bytes() != raw or Path(batch_file).read_bytes() != batch_raw: raise ValueError('Preparation edit input changed before publication')
    return checkpoint(out, recipe, raw, batch_raw)


def scene_for(recipe, assets, context=None):
    from math import atan2, hypot, radians
    w, h = recipe['source']['width'], recipe['source']['height']
    canvas = {'width': w, 'height': h, 'fps': 30, 'loop_seconds': recipe['seconds'], 'background': '#18232c'}
    matrix = [1, 0, 0, 1, 0, 0]
    if context:
        canvas.update(width=context['canvas']['width'], height=context['canvas']['height'])
        matrix = context['source_to_scene']
    a,b,c,d,e,f = matrix; sx, sy = hypot(a,b), hypot(c,d)
    if abs(a*c+b*d) > 1e-9*sx*sy or a*d-b*c <= 0: raise ValueError('Scene placement cannot represent sheared/reflected source maps; use supported source placement')
    W,H = canvas['width'],canvas['height']; layers = []
    for part in [{'id':'backing','kind':'occluder','pivot':[0,0]}, *sorted(recipe['parts'],key=lambda p:p['kind']=='occluder')]:
        px,py = part['pivot']; x,y = (a*px+c*py+e)/W,(b*px+d*py+f)/H
        layer = {'id':part['id'], 'asset':part['id'], 'x':x,'y':y,'width':w*sx/W,'height':h*sy/H,
                 'anchor':[px/w,py/h], 'scale':1,'rotation':atan2(b,a),'opacity':1,'visible':True,'blend':'source-over','depth':0}
        if part['kind']=='cutout':
            motion=part.get('motion',{}); dx,dy=motion.get('delta',[0,0]); sec=recipe['seconds']
            layer['tracks']={}
            for field,base,delta in [('x',x,(a*dx+c*dy)/W),('y',y,(b*dx+d*dy)/H),('rotation',layer['rotation'],radians(motion.get('rotation_degrees',0)))]:
                layer['tracks'][field]={'interpolation':'smoothstep','keys':[[0,base],[sec/4,base],[sec/2,base+delta],[sec*3/4,base],[sec,base]]}
        layers.append(layer)
    scene={'version':1,'id':'compound-preparation-proof','title':recipe['title'],'canvas':canvas,
           'camera':{'overscan':1,'x_amplitude':0,'y_amplitude':0,'zoom_amplitude':0},'groups':[],'layers':layers}
    if context and context['framing']: scene['framing']=context['framing']
    return scene, {'version':1,'assets':assets}


def build(project, file, out):
    project, out = Path(project).resolve(), Path(out).resolve(); ap.relative(project,out)
    path = Path(file); path = path/'recipe.json' if path.is_dir() else path
    raw=path.read_bytes();recipe=json.loads(raw);inputs=load_inputs(project,recipe);controls,context=context_inputs(project,recipe)
    images,facts,warnings=evaluate(recipe,inputs)
    with fresh_output(out) as stage:
        for directory in ['images','snapshots','compiler','preview-project/images']: (stage/directory).mkdir(parents=True,exist_ok=True)
        (stage/'recipe.json').write_bytes(raw)
        for role,data in {**inputs,**controls}.items(): (stage/'snapshots'/f'{role}.bin').write_bytes(data)
        for id,image in images.items(): image.save(stage/'images'/f'{id}.png')
        w,h=images['source'].size
        outputs={};assets=[]; owners={c['id']:part['id'] for part in recipe['parts'] for c in part.get('companions',[])}
        for id in ['backing',*[part['id'] for part in recipe['parts']],*owners]:
            data=(stage/'images'/f'{id}.png').read_bytes(); image_ref={'file':ap.relative(project,out/'images'/f'{id}.png'),'sha256':ap.sha(data),'width':w,'height':h}
            mapping={'format':'ambiance-asset-source-mapping','version':1,'path_base':'project','reference':recipe['source'],
                     'image':image_ref,'image_to_reference':[1,0,0,1,0,0], 'registration':'Complete source canvas; shared companion registration and padding.'}
            ap.write(stage/'compiler'/f'{id}-mapping.json',mapping)
            outputs[id]={'image':image_ref,'owner':owners.get(id), 'mapping':{'file':ap.relative(project,out/'compiler'/f'{id}-mapping.json'),'sha256':ap.sha((stage/'compiler'/f'{id}-mapping.json').read_bytes())}}
            (stage/'preview-project/images'/f'{id}.png').write_bytes(data)
            assets.append({'id':id,'kind':'plate','file':f'images/{id}.png','width':w,'height':h,'bytes':len(data),'sha256':ap.sha(data)})
        scene,catalog=scene_for(recipe,assets,context)
        from .scene_runtime import scene_bridge
        scene_bridge('inspect',scene,catalog,{'full':False})
        ap.write(stage/'preview-project/scene.json',scene);ap.write(stage/'preview-project/catalog.json',catalog)
        ap.write(stage/'preview-project/ambiance-project.json',{'version':1,'scene':'scene.json','catalog':'catalog.json'})
        dependencies=[{'file':ref['file'],'sha256':ref['sha256'],'role':role} for role,ref in references(recipe)]
        if recipe.get('context'): dependencies += [{'file':recipe['context'][role]['file'],'sha256':ap.sha(data),'role':role} for role,data in controls.items()]
        dependencies += [{'file':ap.relative(project,out/'recipe.json'),'sha256':ap.sha(raw),'role':'preparation recipe'}]
        receipt={'format':RECEIPT,'version':1,'project_root_relative':__import__('os').path.relpath(project,out),
                 'recipe_sha256':ap.sha(raw),'outputs':outputs,'dependencies':dependencies,
                 'bindings':{part['id']:part.get('binding') for part in recipe['parts']},'views':context['views'] if context else {},
                 'compiler_contract':{'cell_size':[min(4096,w+4),min(4096,h+4)],'padding':2,'point':[w/2,h/2],'target':[.5,.5]},
                 'facts':facts,'warnings':warnings,'review_status':'unreviewed',
                 'limits':['Raster diagnostics are not paint or artistic approval.','Companions preserve registration; independent corrections require a new compound recipe.','No segmentation, generation or hidden-paint inference.']}
        ap.write(stage/'preparation-receipt.json',receipt);receipt_hash=ap.sha((stage/'preparation-receipt.json').read_bytes())
        for id in outputs:
            ap.write(stage/'compiler'/f'{id}.json',{'version':1,'id':f'{identifier(out.name,"output directory name")}-{id}',
                'input':{'frames':[f'../images/{id}.png'],'allow_opaque':True},
                'source_mapping':{'file':f'{id}-mapping.json','sha256':outputs[id]['mapping']['sha256']},
                'preparation_receipt':{'file':'../preparation-receipt.json','sha256':receipt_hash},
                'registration':{'mode':'fixed','point':[w/2,h/2],'target':[.5,.5]},
                'output':{'cell_size':[min(4096,w+4),min(4096,h+4)],'columns':1,'padding':2}})
        ap.write(stage/'artifact.json',{'format':FORMAT+'-artifact','version':1,
             'files':{str(f.relative_to(stage)):ap.sha(f.read_bytes()) for f in sorted(stage.rglob('*')) if f.is_file()}})
        if path.read_bytes()!=raw or load_inputs(project,recipe)!=inputs or context_inputs(project,recipe)[0]!=controls:
            raise ValueError('Preparation inputs changed during build')
    return {'ok':True,'directory':str(out),'recipe':str(out/'recipe.json'),'receipt':str(out/'preparation-receipt.json'),
            'preview_project':str(out/'preview-project'),'compiler_directory':str(out/'compiler'),
            'parts':list(outputs),'views':list(receipt['views']),'warnings':warnings,'review_status':'unreviewed',
            'next_action':'Run prepare proof for paired hidden/rest/extreme and normal-speed evidence; build/admit the generated compiler recipes.'}


def artifact(out):
    out=Path(out).resolve(); manifest=ap.load(out/'artifact.json')
    if manifest.get('format')!=FORMAT+'-artifact' or manifest.get('version')!=1: raise ValueError('Expected completed compound preparation artifact')
    for file,digest in manifest['files'].items():
        if ap.sha(ap.project_file(out,file).read_bytes())!=digest: raise ValueError(f'Preparation artifact changed: {file}')
    recipe=ap.load(out/'recipe.json');validate(recipe)
    return recipe,ap.load(out/'preparation-receipt.json')


def validate_preparation_receipt(path, expected, source_paths, recipe=None):
    path=Path(path).resolve()
    if ap.sha(path.read_bytes())!=expected: raise ValueError('Preparation receipt changed')
    receipt=ap.load(path)
    if receipt.get('format')!=RECEIPT or receipt.get('version')!=1: raise ValueError('Unsupported preparation receipt')
    root=(path.parent/receipt['project_root_relative']).resolve(); dependencies=[]
    for ref in receipt['dependencies']:
        target=checked_ref(root,{k:ref[k] for k in ['file','sha256']});dependencies.append({'path':target,'sha256':ref['sha256'],'role':ref['role']})
    matched=[]
    for source in source_paths:
        matches=[(id,output) for id,output in receipt['outputs'].items() if ap.project_file(root,output['image']['file'])==Path(source).resolve()]
        if len(matches)!=1: raise ValueError('Compiler input is not an output of this preparation receipt')
        matched.append(matches[0][0])
    for output in receipt['outputs'].values():
        for key in ['image','mapping']:
            ref=output[key];target=checked_ref(root,{k:ref[k] for k in ['file','sha256']})
            dependencies.append({'path':target,'sha256':ref['sha256'],'role':'prepared '+key})
    if recipe is not None:
        contract=receipt['compiler_contract'];reg=recipe.get('registration',{});out=recipe.get('output',{})
        if reg!={'mode':'fixed','point':contract['point'],'target':contract['target']} or out.get('cell_size')!=contract['cell_size'] or out.get('padding')!=contract['padding']:
            raise ValueError('Preparation parts and companions require their recorded fixed registration, cell size and padding')
        if recipe.get('motion_preparation') or recipe.get('edge_preparation'):
            raise ValueError('Independent corrections cannot preserve compound companions; rebuild explicit corrected source/masks together')
    return {'dependencies':dependencies,'outputs':matched,'receipt':receipt}
