"""Source-bound cel studies and bounded corrections. No scene mutation or art generation."""
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile

import studio
from . import assets
from .edge_quality import fresh_output, promote_exclusive
from .project import locations, project_lock
from .scene_runtime import scene_bridge

FORMAT = 'ambiance-asset-motion'
PREPARATION = 'ambiance-motion-preparation'
VERSION = '1.0.0'
ROOT = Path(__file__).resolve().parents[1]


def fields(value, allowed, label, required=()):
    if not isinstance(value, dict) or set(value)-set(allowed) or set(required)-set(value):
        raise ValueError(f'Invalid {label} fields; allowed: {", ".join(allowed)}')


def number(value, label, low=None, high=None):
    if type(value) not in (int, float) or not math.isfinite(value) or (low is not None and value < low) or (high is not None and value > high):
        raise ValueError(f'Invalid {label}: {value}')
    return value


def point(value, label, size=None):
    if not isinstance(value, list) or len(value) != 2: raise ValueError(f'{label} needs [x,y]')
    for axis, v in enumerate(value): number(v, label, 0 if size else None, size[axis] if size else None)
    return value


def name(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_-]{0,63}', value): raise ValueError('Use a simple named landmark/region')
    return value


def path(project, value):
    project=Path(project).resolve()
    if not isinstance(value, str) or Path(value).is_absolute(): raise ValueError('Motion references must be project-relative')
    result = (project/value).resolve()
    if not result.is_relative_to(project): raise ValueError('Motion reference escapes project')
    return result


def relative(project, value):
    project=Path(project).resolve()
    result = Path(value).resolve()
    if not result.is_relative_to(project): raise ValueError('Motion files must stay inside the project')
    return result.relative_to(project).as_posix()


def identity(project, value):
    return {'file': relative(project, value), 'sha256': studio.digest(value)}


def checked(project, ref):
    fields(ref, ['file', 'sha256'], 'identity', ['file', 'sha256'])
    target = path(project, ref['file'])
    if not re.fullmatch('[a-f0-9]{64}', str(ref['sha256'])) or studio.digest(target) != ref['sha256']:
        raise ValueError(f'Motion input changed: {ref["file"]}')
    return target


def encode(data): return (json.dumps(data, indent=2, allow_nan=False)+'\n').encode()


def save_new(project, out, data):
    out = Path(out).resolve(); relative(project, out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.motion-', dir=out.parent) as temporary:
        staged = Path(temporary)/'file'; staged.write_bytes(encode(data))
        promote_exclusive(staged, out)
    return identity(project, out)


def snapshot(project, value):
    raw = encode(value); digest = hashlib.sha256(raw).hexdigest()
    target = project/'.ambiance/motion-inputs'/f'{digest}.json'
    if not target.exists(): save_new(project, target, value)
    if studio.digest(target) != digest: raise ValueError('Captured motion input changed')
    return identity(project, target)


def project_asset(project, pack):
    inspected=assets.inspect_pack(pack)
    if not inspected['ok']: raise ValueError('Baseline pack outputs changed')
    data = copy.deepcopy(inspected['asset'])
    data['file'] = relative(project, pack/data['file'])
    data['provenance']['recipe'] = relative(project, pack/'recipe.json')
    return data


def dependencies(project, asset, scene=None, catalog=None):
    from .revision_dependencies import Collector
    collector = Collector(project)
    for item in catalog['assets'] if scene is not None else [asset]: collector.asset(item)
    return list({r['path']: {'file': r['path'], 'sha256': r['sha256']} for r in collector.refs}.values())


def initialize(project, identifier=None, layer=None, display_width=None, fps=6):
    project = Path(project).resolve(); binding = None
    if bool(identifier) == bool(layer): raise ValueError('Choose exactly one pack/asset or --layer')
    scene = catalog = None
    if layer:
        scene_path, catalog_path = locations(project)
        scene, catalog = studio.read(scene_path), studio.read(catalog_path)
        selected = next((x for x in scene['layers'] if x['id'] == layer), None)
        if selected is None: raise ValueError(f'Unknown layer: {layer}')
        identifier = selected['asset']
    asset, base, pack = assets.lookup(str(identifier), project)
    if pack is None or not asset.get('registration_mapping'):
        raise ValueError('Source mapping unavailable; use asset proof for inspection or compile a source-backed pack first')
    relative(project, pack)
    if asset.get('provenance', {}).get('motion_preparation'):
        raise ValueError('Revise the original motion study instead of chaining corrected packs')
    asset = project_asset(project, pack)
    deps = dependencies(project, asset, scene, catalog)
    mapping = asset['registration_mapping']; count = asset['atlas']['frame_count']
    if scene:
        sample = scene_bridge('sample', scene, catalog, {'time': 0})
        # Full-cell width includes parent/camera scale and rotation from the real evaluator.
        state = next(x for x in sample if x['id'] == layer)
        matrix = state['matrix']
        if display_width is None: display_width = max(1, round(selected['width']*scene['canvas']['width']*math.hypot(matrix[0], matrix[1])))
        binding = {'scene': snapshot(project, scene), 'catalog': snapshot(project, catalog), 'layer': layer,
                   'working_scene': relative(project, scene_path), 'expected_scene_sha256': studio.digest(scene_path)}
    study = {'format': FORMAT, 'schema_version': 1,
             'baseline': {'asset': identity(project, pack/'asset.json'), 'dependencies': deps, 'mapping': mapping},
             'landmarks': {}, 'regions': {},
             'solve': {'mode': 'translation', 'reference_cel': 0, 'cels': list(range(count)), 'unchanged': [],
                       'max_shift_px': 8, 'socket_policies': {k: 'unresolved' for k in asset.get('sockets', {})}, 'layer_socket_policies': {k:'unresolved' for k in selected.get('sockets',{})} if scene else {}},
             'view': {'display_width': display_width or 180, 'fps': fps, 'wrap': True, 'scene': binding},
             'tracking': {'radius': 12, 'patch_radius': 4, 'min_correlation': .9, 'min_margin': .025, 'max_disagreement_px': 1.5},
             'notes': []}
    load(project, data=study)
    return study


def indices(value, count, label):
    if not isinstance(value, list) or len(set(value)) != len(value) or any(type(x) is not int or not 0 <= x < count for x in value):
        raise ValueError(f'{label} needs unique valid cel indices')


def load(project, file=None, data=None):
    from PIL import Image
    project = Path(project).resolve()
    if data is None: data = studio.read(file)
    fields(data, ['format','schema_version','baseline','landmarks','regions','solve','view','tracking','notes'], 'motion study',
           ['format','schema_version','baseline','landmarks','regions','solve','view','tracking','notes'])
    if data['format'] != FORMAT or type(data['schema_version']) is not int or data['schema_version'] != 1: raise ValueError('Unsupported motion study')
    baseline = data['baseline']; fields(baseline, ['asset','dependencies','mapping'], 'baseline', ['asset','dependencies','mapping'])
    pack = checked(project, baseline['asset']).parent
    for ref in baseline['dependencies']: checked(project, ref)
    asset = project_asset(project, pack)
    if asset['provenance'].get('motion_preparation'): raise ValueError('Use the original motion study, not a corrected baseline')
    actual_dependencies = dependencies(project, asset)
    expected = {r['file']: r['sha256'] for r in baseline['dependencies']}
    if any(expected.get(r['file']) != r['sha256'] for r in actual_dependencies): raise ValueError('Motion baseline dependency set is incomplete')
    mapping = asset['registration_mapping']
    if mapping != baseline['mapping']: raise ValueError('Motion baseline mapping differs from compiler')
    _, frames = assets.read_asset(asset, project)
    count = len(frames); size = frames[0].size
    recipe = studio.read(pack/'recipe.json'); spec = recipe['input']; originals = []
    source_names = [spec['sheet']] if 'sheet' in spec else spec['frames']
    sources = [(pack/f).resolve() for f in source_names]
    for m in mapping['cels']:
        with Image.open(sources[m['source_index']]) as image: originals.append(image.convert('RGBA').crop(tuple(m['source_rect'])))
    if len(originals) != count: raise ValueError('Source cel order/count differs')
    if not isinstance(data['landmarks'], dict) or len(data['landmarks']) > 64: raise ValueError('At most 64 named landmarks')
    for key, mark in data['landmarks'].items():
        name(key); fields(mark, ['role','mode','reference_cel','cels','tolerance_px','weight','observations'], 'landmark', ['role','mode','reference_cel','cels','tolerance_px','weight','observations'])
        if mark['role'] not in ['fit','check'] or mark['mode'] not in ['fixed','observe']: raise ValueError('Invalid landmark role/mode')
        indices(mark['cels'], count, 'Landmark cels'); indices([mark['reference_cel']], count, 'Reference cel')
        number(mark['tolerance_px'], 'tolerance', 0, 100); number(mark['weight'], 'weight', .0001, 1000)
        if not isinstance(mark['observations'], list) or len(mark['observations']) != count: raise ValueError('One observation slot per source cel')
        for i, obs in enumerate(mark['observations']):
            if obs is None: continue
            fields(obs, ['point','visible','origin','state','tracking'], 'observation', ['point','visible','origin','state'])
            point(obs['point'], 'Source landmark', originals[i].size)
            if type(obs['visible']) is not bool or obs['origin'] not in ['manual','tracked'] or obs['state'] not in ['selected','proposed','rejected']: raise ValueError('Invalid observation state')
    if not isinstance(data['regions'], dict) or len(data['regions']) > 32: raise ValueError('At most 32 regions')
    for key, region in data['regions'].items():
        name(key); fields(region, ['mode','points','mask','cels','reference_cel','alpha_threshold','color_threshold'], 'region', ['mode','cels','reference_cel','alpha_threshold','color_threshold'])
        if region['mode'] not in ['stable','observe','ignore'] or ('points' in region) == ('mask' in region): raise ValueError('Region needs a mode and exactly one polygon/mask')
        indices(region['cels'], count, 'Region cels'); indices([region['reference_cel']], count, 'Region reference')
        for k in ['alpha_threshold','color_threshold']: number(region[k], k, 0, 255)
        if 'points' in region:
            if not isinstance(region['points'], list) or not 3 <= len(region['points']) <= 1000: raise ValueError('Region polygon needs 3–1000 points')
            for p in region['points']: point(p, 'Region point', size)
        else:
            with Image.open(checked(project, region['mask'])) as im:
                if im.mode != 'L' or im.size != size: raise ValueError('Region mask needs full-cell grayscale geometry')
    solve = data['solve']; fields(solve, ['mode','reference_cel','cels','unchanged','max_shift_px','socket_policies','layer_socket_policies'], 'solve', ['mode','reference_cel','cels','unchanged','max_shift_px','socket_policies','layer_socket_policies'])
    if solve['mode'] != 'translation': raise ValueError('Only translation correction is implemented')
    indices([solve['reference_cel']], count, 'Solve reference'); indices(solve['cels'], count, 'Solve cels'); indices(solve['unchanged'], count, 'Unchanged cels')
    if set(solve['cels']) & set(solve['unchanged']) or set(solve['cels']+solve['unchanged']) != set(range(count)): raise ValueError('Solve and unchanged cels must partition the sequence')
    number(solve['max_shift_px'], 'maximum shift', 0, 100)
    for policies in [solve['socket_policies'], solve['layer_socket_policies']]:
        if not isinstance(policies, dict) or any(v not in ['fixed_mount','follow_art','unresolved'] for v in policies.values()): raise ValueError('Invalid socket policies')
    if set(solve['socket_policies']) != set(asset.get('sockets', {})): raise ValueError('Declare a policy for every asset socket')
    for mark in data['landmarks'].values():
        if mark['mode']=='fixed' and mark['reference_cel']!=solve['reference_cel']: raise ValueError('Fixed landmarks must share the solve reference cel')
    view = data['view']; fields(view, ['display_width','fps','wrap','scene'], 'view', ['display_width','fps','wrap','scene'])
    number(view['display_width'], 'display width', 1, 2048); number(view['fps'], 'proof fps', .1, 60)
    if type(view['display_width']) is not int or type(view['wrap']) is not bool: raise ValueError('View requires integer width and boolean wrap')
    timing = None
    if view['scene']:
        b = view['scene']; fields(b, ['scene','catalog','layer','working_scene','expected_scene_sha256'], 'scene binding', ['scene','catalog','layer','working_scene','expected_scene_sha256'])
        scene = studio.read(checked(project,b['scene'])); catalog = studio.read(checked(project,b['catalog']))
        timing = scene_bridge('timing', scene, catalog, {'layer': b['layer']})
        if timing['layers'][0]['asset'] != asset['id']: raise ValueError('Scene layer does not use the baseline asset')
        for ref in dependencies(project, asset, scene, catalog):
            if expected.get(ref['file']) != ref['sha256']: raise ValueError('Scene asset dependency set is incomplete')
    track = data['tracking']; fields(track, ['radius','patch_radius','min_correlation','min_margin','max_disagreement_px'], 'tracking', ['radius','patch_radius','min_correlation','min_margin','max_disagreement_px'])
    for k,lo,hi in [('radius',1,24),('patch_radius',2,10),('min_correlation',0,1),('min_margin',0,1),('max_disagreement_px',0,10)]: number(track[k], k, lo, hi)
    if any(type(track[k]) is not int for k in ['radius','patch_radius']): raise ValueError('Tracking radii must be integers')
    if not isinstance(data['notes'],list) or len(data['notes'])>100 or any(not isinstance(x,str) or len(x)>2000 for x in data['notes']): raise ValueError('Notes must be a bounded list of strings')
    return {'study':data,'asset':asset,'pack':pack,'recipe':recipe,'frames':frames,'originals':originals,'timing':timing,'project':project}


def mapped(context, cel, p, inverse=False):
    from tools.asset_tool import invert_affine
    m = context['asset']['registration_mapping']['cels'][cel]['raw_cel_to_cell']
    if inverse: m = invert_affine(m)
    x,y = p; a,b,c,d,e,f = m
    return [a*x+c*y+e, b*x+d*y+f]


def observation(context, landmark, cel):
    obs = landmark['observations'][cel]
    if obs is None or not obs['visible'] or obs['state'] != 'selected': return None
    return mapped(context, cel, obs['point'])


def solution(context):
    s = context['study']; count = len(context['frames']); ratio = s['view']['display_width']/context['frames'][0].width
    shifts = []; unresolved = []; residuals = []
    for i in range(count):
        terms = []
        for key, mark in s['landmarks'].items():
            if mark['mode'] != 'fixed' or i not in mark['cels']: continue
            p = observation(context, mark, i); target = observation(context, mark, mark['reference_cel'])
            if p is None or target is None:
                unresolved.append({'cel':i,'landmark':key,'reason':'missing_selected_observation','next':'Select a visible observation or revise the constraint interval'})
            elif mark['role'] == 'fit': terms.append((mark['weight'], [target[a]-p[a] for a in range(2)]))
        delta = [0.,0.]
        if i in s['solve']['cels']:
            if not terms: unresolved.append({'cel':i,'reason':'no_fit_landmark','next':'Add a fixed fit landmark or explicitly leave this cel unchanged'})
            elif i != s['solve']['reference_cel']: delta = [sum(w*d[a] for w,d in terms)/sum(w for w,d in terms) for a in range(2)]
        if math.hypot(*delta)*ratio > s['solve']['max_shift_px']:
            unresolved.append({'cel':i,'reason':'correction_exceeds_bound','next':'Inspect correspondence; revise the bound only if intended'})
        shifts.append(delta)
        for key, mark in s['landmarks'].items():
            if mark['mode'] != 'fixed' or i not in mark['cels']: continue
            p = observation(context, mark, i); target = observation(context, mark, mark['reference_cel'])
            if p is None or target is None: continue
            before = math.dist(p,target)*ratio; after = math.dist([p[a]+delta[a] for a in range(2)],target)*ratio
            row = {'cel':i,'landmark':key,'role':mark['role'],'before_px':before,'after_px':after,'tolerance_px':mark['tolerance_px']}
            residuals.append(row)
            if after > mark['tolerance_px']+1e-9: unresolved.append({**row,'reason':'constraint_conflict','next':'Inspect the independent check or split/repair the changing part'})
    for key,policy in {**s['solve']['socket_policies'],**{f'layer:{k}':v for k,v in s['solve']['layer_socket_policies'].items()}}.items():
        if policy == 'unresolved': unresolved.append({'socket':key,'reason':'socket_policy_required','next':'Choose fixed_mount or follow_art'})
    return {'ok':not unresolved,'translations_cell_px':shifts,'residuals':residuals,'unresolved':unresolved}


def sockets(values, policies, shifts, size):
    result = {}
    if set(values) != set(policies): raise ValueError('Declare every socket policy')
    for key,value in values.items():
        policy = policies[key]
        if policy == 'fixed_mount': result[key] = value
        elif policy == 'follow_art':
            points = value['frames'] if isinstance(value,dict) else [value]*len(shifts)
            result[key] = {'frames': [[p[a]+d[a]/size[a] for a in range(2)] for p,d in zip(points,shifts)]}
        else: raise ValueError('Unresolved socket policy')
    return result


def summary(context, file=None):
    s=context['study']; sol=solution(context)
    return {'ok':True,'study':str(file) if file else None,'study_sha256':studio.digest(file) if file else None,
            'asset':context['asset']['id'],'cel_count':len(context['frames']),'landmarks':list(s['landmarks']),
            'regions':list(s['regions']),'ready_to_solve':sol['ok'],'unresolved_count':len(sol['unresolved']),
            'next':sol['unresolved'][:5],'notes':s['notes'][-5:],'timing_driver':context['timing']['layers'][0]['timing_driver'] if context['timing'] else 'explicit_proof_cadence'}


def edited(context, batch):
    fields(batch, ['version','operations'], 'edit batch', ['version','operations'])
    if batch['version'] != 1 or not isinstance(batch['operations'],list) or not 1<=len(batch['operations'])<=2048: raise ValueError('Expected 1–2048 study operations')
    s=copy.deepcopy(context['study']); count=len(context['frames'])
    for op in batch['operations']:
        kind=op.get('op')
        if kind in ['landmark','region']:
            fields(op,['op','name','value'],kind,['op','name','value']); name(op['name'])
            collection=s['landmarks' if kind=='landmark' else 'regions']
            if op['value'] is None: collection.pop(op['name'],None)
            else: collection[op['name']]=copy.deepcopy(op['value'])
        elif kind=='observe':
            fields(op,['op','name','cel','value','view'],kind,['op','name','cel','value'])
            indices([op['cel']],count,'Observation cel'); value=copy.deepcopy(op['value'])
            if op.get('view'):
                fields(op['view'],['packet','id'], 'view reference', ['packet','id'])
                packet=studio.read(checked(context['project'],op['view']['packet']))
                if packet['study'] != context['study']: raise ValueError('Stale observation view; inspect the current study')
                view=packet['views'].get(op['view']['id'])
                if not view or view['cel']!=op['cel']: raise ValueError('View cel mismatch')
                p=point(value['point'],'View point',view['size']); m=view['view_to_source']
                value['point']=[m[0]*p[0]+m[2]*p[1]+m[4],m[1]*p[0]+m[3]*p[1]+m[5]]
            s['landmarks'][op['name']]['observations'][op['cel']]=value
        elif kind in ['solve','view','tracking']:
            fields(op,['op','values'],kind,['op','values'])
            s[kind].update(op['values'])
        elif kind=='note':
            fields(op,['op','text'],kind,['op','text']); s['notes'].append(op['text'])
        else: raise ValueError(f'Unknown study operation: {kind}')
    return load(context['project'],data=s)


def proposal(project, file, out, asset_id):
    project=Path(project).resolve()
    if not re.fullmatch('[a-z0-9][a-z0-9-]*',asset_id): raise ValueError('Candidate ID needs lowercase letters/numbers/hyphens')
    original_hash=studio.digest(file); c=load(project,file); sol=solution(c); out=Path(out).resolve(); relative(project,out)
    with fresh_output(out) as stage:
        (stage/'study.json').write_bytes(encode(c['study']))
        report={'format':PREPARATION,'schema_version':1,'algorithm':VERSION,'study':{'file':relative(project,out/'study.json'),'sha256':studio.digest(stage/'study.json')},
                'solution':sol,'baseline':c['study']['baseline']}
        # Final references are explicit; a staged receipt is sufficient for geometry preflight below.
        (stage/'report.json').write_bytes(encode(report))
        if sol['ok']:
            recipe=copy.deepcopy(c['recipe']); recipe['id']=asset_id
            for key in ['sheet'] if 'sheet' in recipe['input'] else ['frames']:
                v=recipe['input'][key]
                recipe['input'][key]=os.path.relpath(c['pack']/v,out) if isinstance(v,str) else [os.path.relpath(c['pack']/x,out) for x in v]
            for key in ['source_mapping','edge_preparation','registration_source']:
                if recipe.get(key): recipe[key]['file']=os.path.relpath(c['pack']/recipe[key]['file'],out)
            recipe['motion_preparation']={'file':'report.json','sha256':studio.digest(stage/'report.json')}
            recipe['sockets']=sockets(c['asset'].get('sockets',{}),c['study']['solve']['socket_policies'],sol['translations_cell_px'],c['frames'][0].size)
            # Check actual raw alpha against fixed output bounds, before giving the operator a recipe.
            geometry(c,sol)
            (stage/'compiler.json').write_bytes(encode(recipe))
        load(project,file)
        if studio.digest(file)!=original_hash: raise ValueError('Study changed during solve')
    return {'ok':sol['ok'],'directory':str(out),'report':str(out/'report.json'),'compiler_recipe':str(out/'compiler.json') if sol['ok'] else None,
            'unresolved':sol['unresolved'][:5],'unresolved_count':len(sol['unresolved'])}


def geometry(context, sol):
    mapping=context['asset']['registration_mapping']; cw,ch=mapping['cell_size']; pad=mapping['padding']; offsets=[]
    for i,(raw,delta) in enumerate(zip(context['originals'],sol['translations_cell_px'])):
        m=mapping['cels'][i]['raw_cel_to_cell']; scale=mapping['shared_scale']
        if m[:4]!=[scale,0,0,scale]: raise ValueError('Only uniformly registered baseline geometry is supported')
        ox,oy=m[4]+delta[0],m[5]+delta[1]; bounds=raw.getchannel('A').getbbox()
        if bounds is None: raise ValueError('Empty source cel')
        left,top,right,bottom=[bounds[0]*scale+ox,bounds[1]*scale+oy,bounds[2]*scale+ox,bounds[3]*scale+oy]
        extra=[max(0,pad-left),max(0,pad-top),max(0,right-(cw-pad)),max(0,bottom-(ch-pad))]
        if max(extra)>1e-7: raise ValueError(f'Cel {i}: correction needs extra left/top/right/bottom padding {extra}; fixed geometry cannot clip or shrink')
        offsets.append([ox,oy])
    return {'scale':mapping['shared_scale'],'offsets':offsets,'cell_size':[cw,ch]}


def validate_preparation(report_path, expected_sha, input_paths=None):
    report_path=Path(report_path).resolve()
    if studio.digest(report_path)!=expected_sha: raise ValueError('Motion preparation report changed')
    project=next((p for p in report_path.parents if (p/'ambiance-project.json').is_file()),None)
    if project is None: raise ValueError('Motion preparation requires its project')
    report=studio.read(report_path)
    fields(report,['format','schema_version','algorithm','study','solution','baseline'],'motion preparation',['format','schema_version','algorithm','study','solution','baseline'])
    if report['format']!=PREPARATION or report['schema_version']!=1 or report['algorithm']!=VERSION: raise ValueError('Unsupported motion preparation')
    study_file=checked(project,report['study']); c=load(project,study_file)
    sol=solution(c)
    if not sol['ok'] or sol!=report['solution'] or c['study']['baseline']!=report['baseline']: raise ValueError('Motion proposal does not reproduce its selected constraints')
    spec=c['recipe']['input']; source_paths=[(c['pack']/v).resolve() for v in ([spec['sheet']] if 'sheet' in spec else spec['frames'])]
    if input_paths is not None and list(map(Path,input_paths))!=source_paths: raise ValueError('Motion compiler input order differs from baseline')
    refs=[report['study'],*c['study']['baseline']['dependencies'],c['study']['baseline']['asset']]
    for region in c['study']['regions'].values():
        if region.get('mask'): refs.append(region['mask'])
    if c['study']['view']['scene']: refs.extend(c['study']['view']['scene'][k] for k in ['scene','catalog'])
    return {'context':c,'report':report,'geometry':geometry(c,sol),
            'dependencies':[{'path':checked(project,r),'sha256':r['sha256'],'role':'motion_preparation'} for r in refs]}


def add_parsers(group):
    sub=group.add_parser('motion',help='Inspect, track and stabilize source-backed cels').add_subparsers(dest='motion_action',required=True)
    q=sub.add_parser('init');q.add_argument('asset',nargs='?');q.add_argument('--layer');q.add_argument('--display-width',type=int);q.add_argument('--fps',type=float,default=6);q.add_argument('--out',type=Path,required=True)
    for action in ['inspect','check','edit','analyze','solve','track','proof']:
        q=sub.add_parser(action);q.add_argument('file',type=Path)
        if action not in ['inspect','check']: q.add_argument('--out',type=Path,required=True)
        if action=='edit': q.add_argument('--changes',type=Path,required=True);q.add_argument('--expect-study',required=True)
        if action=='solve': q.add_argument('--id',required=True)
        if action in ['analyze','proof']: q.add_argument('--finding');q.add_argument('--region');q.add_argument('--offset',type=int,default=0);q.add_argument('--limit',type=int,default=5)
        if action=='proof': q.add_argument('--candidate',type=Path,required=True);q.add_argument('--context-seconds',type=float,default=3)


def run(args,project):
    project=Path(project).resolve(); action=args.motion_action
    if action=='init':
        with project_lock(project):
            s=initialize(project,args.asset,args.layer,args.display_width,args.fps);save_new(project,args.out,s)
        return summary(load(project,args.out),args.out.resolve())
    c=load(project,args.file)
    if action in ['inspect','check']:
        result=summary(c,args.file.resolve())
        if action=='check': result['ok']=result['ready_to_solve']
        return result
    if action=='edit':
        with project_lock(project):
            if studio.digest(args.file)!=args.expect_study: raise ValueError('Stale study; inspect before editing')
            c=load(project,args.file)
            updated=edited(c,studio.read(args.changes)); load(project,args.file)
            if studio.digest(args.file)!=args.expect_study: raise ValueError('Study changed during edit')
            save_new(project,args.out,updated['study'])
        result=summary(updated,args.out.resolve())
        old,new=c['study'],updated['study']
        affected=set()
        for key in set(old['landmarks'])|set(new['landmarks']):
            a,b=old['landmarks'].get(key),new['landmarks'].get(key)
            if a!=b:
                if a is None or b is None or {k:v for k,v in a.items() if k!='observations'}!={k:v for k,v in b.items() if k!='observations'}:affected.update(range(len(c['frames'])))
                else:affected.update(i for i,(x,y) in enumerate(zip(a['observations'],b['observations'])) if x!=y)
        if old['solve']!=new['solve'] or old['view']!=new['view']:affected.update(range(len(c['frames'])))
        result['affected_cels']=sorted(affected);result['affected_regions']=[k for k in set(old['regions'])|set(new['regions']) if old['regions'].get(k)!=new['regions'].get(k)]
        return result
    if action=='solve': return proposal(project,args.file,args.out,args.id)
    if action=='track':
        from .motion_tracking import track
        return track(c,args.file,args.out)
    from .motion_proof import proof
    return proof(c,args.file,args.out,getattr(args,'candidate',None),args.finding,args.region,args.offset,args.limit,getattr(args,'context_seconds',3))


def compiler_settings(checked_motion, recipe):
    """The correction may change ID and socket positions, never source selection or fitting."""
    c=checked_motion['context']; baseline=c['recipe']
    for key in ['registration','output','rights']:
        if recipe.get(key)!=baseline.get(key): raise ValueError(f'Motion compiler must preserve baseline {key}')
    selection=lambda spec:{k:v for k,v in spec.items() if k not in ['sheet','frames']}
    if selection(recipe['input'])!=selection(baseline['input']) or ('sheet' in recipe['input'])!=('sheet' in baseline['input']): raise ValueError('Motion compiler must preserve source rectangles and order')
    desired=sockets(c['asset'].get('sockets',{}),c['study']['solve']['socket_policies'],checked_motion['report']['solution']['translations_cell_px'],c['frames'][0].size)
    if recipe.get('sockets',{})!=desired: raise ValueError('Motion compiler sockets differ from declared policies')
    for key in ['registration_source','source_mapping','edge_preparation']:
        if (recipe.get(key) or {}).get('sha256')!=(baseline.get(key) or {}).get('sha256'): raise ValueError(f'Motion compiler must preserve {key}')


def raster(context, sol=None):
    from tools.asset_tool import resample_cel
    sol=solution(context) if sol is None else sol
    if not sol['ok']: raise ValueError('Unresolved study has no ready candidate')
    g=geometry(context,sol)
    return [resample_cel(raw,g['cell_size'],g['scale'],offset) for raw,offset in zip(context['originals'],g['offsets'])]
