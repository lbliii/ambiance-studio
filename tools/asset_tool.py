#!/usr/bin/env python3
"""Compile transparent cels into an immutable, registered asset pack. Requires Pillow."""
import argparse
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import sys
from PIL import Image, ImageDraw, __version__ as PILLOW_VERSION

VERSION = '1.3.1'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')

def positive_int(n):
    return type(n) is int and n > 0

def pair(v):
    return isinstance(v, list) and len(v) == 2 and all(type(n) in (int, float) and math.isfinite(n) for n in v)

def invert_affine(matrix):
    if not isinstance(matrix,list) or len(matrix)!=6 or any(type(v) not in [int,float] or not math.isfinite(v) for v in matrix):
        raise ValueError('Source mapping needs a finite six-number image_to_reference affine')
    a,b,c,d,e,f=matrix;det=a*d-b*c
    if abs(det)<1e-12: raise ValueError('Source mapping affine must be invertible')
    return [d/det,-b/det,-c/det,a/det,(c*f-d*e)/det,(b*e-a*f)/det]


def multiply_affine(a,b):
    x,y,z,w,tx,ty=a;u,v,r,s,px,py=b
    return [x*u+z*v,y*u+w*v,x*r+z*s,y*r+w*s,x*px+z*py+tx,y*px+w*py+ty]


def resample_cel(frame, size, scale, offset):
    if scale == 1 and all(float(v).is_integer() for v in offset):
        output = Image.new('RGBA', tuple(size)); output.paste(frame.convert('RGBA'), tuple(map(int, offset))); return output
    # Shared by compilation and interactive draft evaluation; always raw input.
    return frame.convert('RGBa').transform(tuple(size), Image.Transform.AFFINE,
        (1/scale,0,-offset[0]/scale,0,1/scale,-offset[1]/scale), Image.Resampling.BICUBIC).convert('RGBA')


def build(recipe_path, out):
    recipe_path,out=Path(recipe_path).resolve(),Path(out).resolve()
    if any(json.loads(recipe_path.read_text()).get(k) for k in ['motion_preparation', 'preparation_receipt', 'cel_trim', 'region_receipt']) and not out.exists():
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
        from ambiance_studio.edge_quality import fresh_output
        with fresh_output(out) as stage:
            result=_build(recipe_path,stage,logical_out=out)
        return {**result,'pack':str(out)}
    return _build(recipe_path,out)


def _build(recipe_path, out, logical_out=None):
    recipe_path, out = Path(recipe_path).resolve(), Path(out).resolve()
    destination=Path(logical_out).resolve() if logical_out else out
    recipe_bytes = recipe_path.read_bytes()
    recipe = json.loads(recipe_bytes)
    if recipe.get('version') != 1 or not re.fullmatch(r'[a-z0-9][a-z0-9-]*', recipe.get('id', '')):
        raise ValueError('Use recipe version 1 and a lowercase asset id.')
    inputs = recipe['input']
    frames, sources, source_paths, source_rects, source_sizes = [], [], [], [], []
    if 'sheet' in inputs:
        path = (recipe_path.parent / inputs['sheet']).resolve()
        source_bytes = path.read_bytes()
        with Image.open(io.BytesIO(source_bytes)) as raw:
            raw.load()
            image = raw.convert('RGBA')
        source_sizes.append(list(image.size))
        columns, rows, count = (inputs[k] for k in ['columns', 'rows', 'frame_count'])
        if not all(positive_int(n) for n in [columns, rows, count]) or count > columns * rows or image.width % columns or image.height % rows:
            raise ValueError('Input must have exact whole cells, and frame_count must fit the grid.')
        w, h = image.width // columns, image.height // rows
        frames = [image.crop((i % columns*w, i//columns*h, (i % columns+1)*w, (i//columns+1)*h)) for i in range(count)]
        sources.append({'file': inputs['sheet'], 'sha256': hashlib.sha256(source_bytes).hexdigest()})
        source_paths.append(path)
        source_rects = [(0,[i % columns*w,i//columns*h,(i % columns+1)*w,(i//columns+1)*h]) for i in range(count)]
    else:
        for name in inputs['frames']:
            path = (recipe_path.parent / name).resolve()
            source_bytes = path.read_bytes()
            with Image.open(io.BytesIO(source_bytes)) as raw:
                raw.load()
                frames.append(raw.convert('RGBA'))
            source_sizes.append(list(frames[-1].size))
            sources.append({'file': name, 'sha256': hashlib.sha256(source_bytes).hexdigest()})
            source_paths.append(path)
            source_rects.append((len(source_paths)-1,[0,0,frames[-1].width,frames[-1].height]))
    if not frames or len(frames) > 256:
        raise ValueError('Supply 1–256 explicitly ordered frames.')
    region = None
    if recipe.get('region_receipt') is not None:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from ambiance_studio.art_regions import validate_region_receipt
        ref = recipe['region_receipt']
        if not isinstance(ref, dict) or set(ref) != {'file', 'sha256'} or not isinstance(ref['file'], str) or Path(ref['file']).is_absolute():
            raise ValueError('region_receipt needs recipe-relative file and sha256')
        region_path = (recipe_path.parent/ref['file']).resolve()
        region = validate_region_receipt(region_path, ref['sha256'], source_paths, recipe)
        recipe['region_receipt'] = {'file': os.path.relpath(region_path, destination), 'sha256': ref['sha256']}
    compound = None
    if recipe.get('preparation_receipt') is not None:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from ambiance_studio.compound_preparation import validate_preparation_receipt
        ref = recipe['preparation_receipt']
        if not isinstance(ref, dict) or set(ref) != {'file', 'sha256'} or not isinstance(ref['file'], str) or Path(ref['file']).is_absolute():
            raise ValueError('preparation_receipt needs recipe-relative file and sha256')
        compound_path = (recipe_path.parent/ref['file']).resolve()
        compound = validate_preparation_receipt(compound_path, ref['sha256'], source_paths, recipe)
        recipe['preparation_receipt'] = {'file': os.path.relpath(compound_path, destination), 'sha256': ref['sha256']}
    edge_source = None
    edge_dependencies = []
    if recipe.get('edge_preparation') is not None:
        edge_ref = recipe['edge_preparation']
        if not isinstance(edge_ref, dict) or set(edge_ref) != {'file', 'sha256'} or not isinstance(edge_ref['file'], str) or Path(edge_ref['file']).is_absolute():
            raise ValueError('edge_preparation needs an explicit recipe-relative file and sha256')
        # Shared typed verifier also serves revision/scene authoring. This lazy
        # import keeps legacy standalone compiler calls independent of CLI setup.
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from ambiance_studio.edge_quality import validate_edge_preparation
        edge_path = (recipe_path.parent/edge_ref['file']).resolve()
        checked_edge = validate_edge_preparation(edge_path, edge_ref['sha256'], source_paths)
        edge_layout = checked_edge['report']['output_layout']
        if 'sheet' not in inputs or any(inputs.get(key) != edge_layout[key] for key in ['columns', 'rows', 'frame_count']):
            raise ValueError('Compiler sheet selection must match the edge preparation layout exactly')
        edge_dependencies = checked_edge['dependencies']
        edge_source = {'file': os.path.relpath(edge_path, destination), 'sha256': edge_ref['sha256']}
    mapping_source = None
    source_mapping = None
    if recipe.get('source_mapping'):
        mapping_ref = recipe['source_mapping']
        mapping_path = (recipe_path.parent / mapping_ref['file']).resolve()
        if not mapping_path.is_file() or sha(mapping_path) != mapping_ref['sha256']:
            raise ValueError('Source placement mapping changed or is missing')
        source_mapping = json.loads(mapping_path.read_text())
        if source_mapping.get('format') != 'ambiance-asset-source-mapping' or source_mapping.get('version') != 1 or source_mapping.get('path_base') != 'project':
            raise ValueError('Expected project-relative ambiance-asset-source-mapping version 1')
        project = next((p for p in [recipe_path.parent,*recipe_path.parents] if (p/'ambiance-project.json').is_file()),None)
        if project is None: raise ValueError('Mapped builds require an ambiance-project.json ancestor for project-relative source identities')
        for key in ['reference','image']:
            record = source_mapping[key]
            file = (project/record['file']).resolve()
            if Path(record['file']).is_absolute() or not file.is_relative_to(project) or not file.is_file() or sha(file)!=record['sha256']:
                raise ValueError(f'Source mapping {key} identity changed or escapes the project')
            with Image.open(file) as mapped:
                if mapped.size!=(record['width'],record['height']): raise ValueError(f'Source mapping {key} dimensions differ')
            if key=='image' and (len(source_paths)!=1 or file!=source_paths[0]):
                raise ValueError('Source mapping must identify the exact single compiler input image')
        invert_affine(source_mapping['image_to_reference'])
        mapping_source={'file':os.path.relpath(mapping_path,destination),'sha256':sha(mapping_path)}
    if recipe.get('cel_trim'):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
        from ambiance_studio.cel_trim import validate as validate_trim
        trim_ref=recipe['cel_trim'];trim_path=(recipe_path.parent/trim_ref['file']).resolve()
        validate_trim(trim_path,trim_ref['sha256'],source_paths,recipe)
        recipe['cel_trim']={'file':os.path.relpath(trim_path,destination),'sha256':trim_ref['sha256']}
    spec, registration = recipe['output'], recipe['registration']
    landmark_source = None
    if recipe.get('registration_source'):
        prior = recipe['registration_source']
        prior_path = (recipe_path.parent / prior['file']).resolve()
        if not prior_path.is_file() or sha(prior_path) != prior['sha256']:
            raise ValueError('Recorded landmark source changed or is missing.')
        prior_data = json.loads(prior_path.read_text())
        if prior_data.get('version') != 1 or prior_data.get('landmarks', {}).get(prior.get('name')) != registration.get('points'):
            raise ValueError('Embedded registration points differ from the recorded named landmark source; author a new landmark file.')
        landmark_source = {**prior, 'file': os.path.relpath(prior_path, destination)}
    if 'landmarks_file' in registration:
        if registration.get('mode') != 'landmarks' or 'points' in registration:
            raise ValueError('A named landmark file requires landmarks mode and no inline points.')
        landmark_path = (recipe_path.parent / registration['landmarks_file']).resolve()
        landmark_data = json.loads(landmark_path.read_text())
        name = registration.get('landmark')
        if landmark_data.get('version') != 1 or not isinstance(name, str) or name not in landmark_data.get('landmarks', {}):
            raise ValueError('Named landmark file must contain version 1 and the selected landmark.')
        landmark_source = {'file': os.path.relpath(landmark_path, destination), 'sha256': sha(landmark_path), 'name': name}
        # Embed the resolved points in the portable recipe; retain the source identity
        # in provenance so the authoring file is not silently forgotten.
        registration = {k:v for k,v in registration.items() if k not in ['landmarks_file', 'landmark']}
        registration['points'] = landmark_data['landmarks'][name]
        recipe['registration'] = registration
    if landmark_source:
        recipe['registration_source'] = landmark_source
    cw, ch = spec['cell_size']
    columns = spec['columns']
    pad = spec.get('padding', 2)
    target = registration['target']
    mode = registration['mode']
    if not all(positive_int(n) for n in [cw, ch, columns, pad]) or pad < 2 or min(cw, ch) <= pad*2 or max(cw, ch) > 4096:
        raise ValueError('Invalid output geometry; require at least 2 pixels of padding.')
    if not pair(target) or any(n <= 0 or n >= 1 for n in target):
        raise ValueError('Target pivot must be strictly inside the cell, in normalized coordinates.')
    if mode not in ['fixed', 'landmarks', 'bottom-center']:
        raise ValueError('Registration mode must be fixed, landmarks, or bottom-center.')
    threshold = registration.get('alpha_threshold', 20)
    if type(threshold) is not int or not 1 <= threshold <= 254:
        raise ValueError('alpha_threshold must be 1–254.')
    if mode == 'landmarks' and len(registration['points']) != len(frames):
        raise ValueError('Provide one source-pixel landmark per cel.')
    rows = math.ceil(len(frames)/columns)
    if cw*columns > 16384 or ch*rows > 16384 or cw*columns*ch*rows > 64_000_000:
        raise ValueError('Atlas exceeds the compiler memory budget; use smaller cells or split the pack.')
    motion = None
    if recipe.get('motion_preparation') is not None:
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
        from ambiance_studio.asset_motion import validate_preparation, compiler_settings
        ref=recipe['motion_preparation']
        if not isinstance(ref,dict) or set(ref)!={'file','sha256'} or Path(ref['file']).is_absolute(): raise ValueError('motion_preparation needs a recipe-relative file and sha256')
        motion_path=(recipe_path.parent/ref['file']).resolve()
        motion=validate_preparation(motion_path,ref['sha256'],source_paths)
        compiler_settings(motion,recipe)
        recipe['motion_preparation']={'file':os.path.relpath(motion_path,destination),'sha256':ref['sha256']}
    # Input locations are portable; order, bytes, settings, code and Pillow determine the build.
    canonical = json.loads(json.dumps(recipe))
    if 'region_receipt' in canonical: canonical['region_receipt']['file']='region-receipt'
    if 'preparation_receipt' in canonical: canonical['preparation_receipt']['file']='preparation-receipt'
    if 'motion_preparation' in canonical: canonical['motion_preparation']['file']='motion-preparation'
    if 'edge_preparation' in canonical:
        canonical['edge_preparation']['file'] = 'edge-preparation'
    if 'source_mapping' in canonical:
        canonical['source_mapping']['file'] = 'source-mapping'
    if 'registration_source' in canonical:
        canonical['registration_source']['file'] = 'registration-source'
    if 'sheet' in canonical['input']: canonical['input']['sheet'] = 'source-0'
    else: canonical['input']['frames'] = [f'source-{i}' for i in range(len(sources))]
    key_data = {'recipe': canonical, 'sources': [s['sha256'] for s in sources], 'compiler': sha(Path(__file__)), 'pillow': PILLOW_VERSION}
    cache_key = hashlib.sha256(json.dumps(key_data, sort_keys=True).encode()).hexdigest()
    if out.exists() and logical_out is None:
        report_file = out/'report.json'
        if report_file.is_file():
            report = json.loads(report_file.read_text())
            if report['cache_key'] == cache_key and all((out/f).is_file() and sha(out/f) == h for f, h in report['outputs'].items()):
                if region:
                    validate_region_receipt(region_path,recipe['region_receipt']['sha256'],source_paths,recipe)
                    if recipe_path.read_bytes()!=recipe_bytes: raise ValueError('Recipe changed during region cache lookup')
                if compound:
                    validate_preparation_receipt(compound_path,recipe['preparation_receipt']['sha256'],source_paths,recipe)
                    if recipe_path.read_bytes()!=recipe_bytes: raise ValueError('Recipe changed during preparation cache lookup')
                if motion:
                    validate_preparation(motion_path,recipe['motion_preparation']['sha256'],source_paths)
                    if recipe_path.read_bytes()!=recipe_bytes: raise ValueError('Recipe changed during motion cache lookup')
                return {'status': 'cached', 'pack': str(out), 'cache_key': cache_key}
        raise ValueError('Output exists but differs. Choose a new version directory; accepted packs are immutable.')
    tx, ty = target[0]*cw, target[1]*ch
    records, limits, warnings = [], [1.0] if not spec.get('allow_upscale', False) else [], []
    for i, frame in enumerate(frames):
        alpha = frame.getchannel('A')
        bounds = alpha.getbbox()  # Preserve even faint detail when fitting the sequence.
        measured = alpha.point(lambda n: 255 if n >= threshold else 0).getbbox()
        if not bounds or not measured:
            raise ValueError(f'Cel {i}: empty or below alpha threshold. Repair it explicitly.')
        if alpha.getextrema()[0] == 255 and not inputs.get('allow_opaque', False):
            raise ValueError(f'Cel {i}: fully opaque. Real alpha is required; proofing grids are not transparency.')
        if mode == 'fixed':
            pivot = registration['point']
        elif mode == 'landmarks':
            pivot = registration['points'][i]
        else:
            pivot = [(measured[0]+measured[2])/2, measured[3]]
        if not pair(pivot) or not (0 <= pivot[0] <= frame.width and 0 <= pivot[1] <= frame.height):
            raise ValueError(f'Cel {i}: pivot must be a finite source-pixel point within its cell.')
        px, py = pivot
        for extent, available in [(px-bounds[0], tx-pad), (bounds[2]-px, cw-pad-tx), (py-bounds[1], ty-pad), (bounds[3]-py, ch-pad-ty)]:
            if extent > 0:
                limits.append(available/extent)
        if bounds[0] == 0 or bounds[1] == 0 or bounds[2] == frame.width or bounds[3] == frame.height:
            warnings.append(f'Cel {i}: source alpha touches a cell edge; inspect for pre-existing clipping.')
        records.append({'index': i, 'source_size': list(frame.size), 'alpha_bounds': list(bounds), 'measured_bounds': list(measured), 'source_pivot': list(pivot)})
    scale = motion['geometry']['scale'] if motion else min(limits)
    if scale <= 0:
        raise ValueError('The target pivot leaves insufficient padding.')
    if mode == 'bottom-center':
        warnings.append('Bottom-center is a silhouette estimate, not a tracked anatomical or architectural landmark. Review base stability; use explicit landmarks for asymmetric/deforming subjects.')
    if recipe_path.read_bytes()!=recipe_bytes or any(sha(p)!=record['sha256'] for p,record in zip(source_paths,sources)):
        raise ValueError('Recipe/source changed during asset preparation')
    if any(not record['path'].is_file() or sha(record['path']) != record['sha256'] for record in edge_dependencies):
        raise ValueError('Edge preparation dependency changed during asset preparation')
    out.mkdir(parents=True,exist_ok=logical_out is not None)
    atlas = Image.new('RGBA', (cw*columns, ch*rows))
    normalized = []
    for frame, record in zip(frames, records):
        px, py = record['source_pivot']
        offset = motion['geometry']['offsets'][record['index']] if motion else [tx-px*scale, ty-py*scale]
        # Resample premultiplied color to avoid halos from transparent RGB.
        cel = resample_cel(frame,(cw,ch),scale,offset)
        i = record['index']
        atlas.paste(cel, (i%columns*cw, i//columns*ch))
        normalized.append(cel)
        record.update(offset_pixels=offset, output_pivot=[tx,ty], output_alpha_bounds=cel.getchannel('A').getbbox())
    atlas.save(out/'atlas.png')
    # Small diagnostic proofs: actual alpha on light and dark, plus a fixed pivot cross.
    pw, ph = min(200,cw), max(1, round(ch*min(200,cw)/cw))
    proof = Image.new('RGB', (pw*columns, (ph+24)*rows*2), '#202432')
    draw = ImageDraw.Draw(proof)
    previews = []
    for i, cel in enumerate(normalized):
        thumb = cel.resize((pw,ph), Image.Resampling.LANCZOS)
        for side, bg in enumerate(['#e8e3d8','#202432']):
            x, y = i%columns*pw, (i//columns+side*rows)*(ph+24)
            tile = Image.new('RGBA', (pw,ph), bg);tile.alpha_composite(thumb)
            proof.paste(tile.convert('RGB'),(x,y))
            cx, cy = x+target[0]*pw, y+target[1]*ph
            draw.line((cx-6,cy,cx+6,cy), fill='#ff66bb', width=1)
            draw.line((cx,cy-6,cx,cy+6), fill='#ff66bb', width=1)
            draw.text((x+4,y+ph+4), f'Cel {i+1}', fill='#c58d62' if side == 0 else '#eeeeee')
        tile = Image.new('RGBA', (pw,ph), '#202432');tile.alpha_composite(thumb)
        previews.append(tile.convert('RGB'))
    proof.save(out/'contact-sheet.png')
    previews[0].save(out/'preview.gif',save_all=True,append_images=previews[1:],duration=120,loop=0,disposal=2)
    packed_recipe = json.loads(json.dumps(recipe))
    if edge_source:
        packed_recipe['edge_preparation'] = edge_source
    references = [os.path.relpath(p, destination) for p in source_paths]
    if 'sheet' in inputs: packed_recipe['input']['sheet'] = references[0]
    else: packed_recipe['input']['frames'] = references
    packed_sources = [{'file':f,'sha256':s['sha256']} for f,s in zip(references,sources)]
    input_sources=[]
    for size,record in zip(source_sizes,packed_sources):
        input_sources.append({**record,'width':size[0],'height':size[1]})
    mapping={'version':1,'input_path_base':'recipe','input_sources':input_sources,'cell_size':[cw,ch],'shared_scale':scale,'padding':pad,'cels':[]}
    if source_mapping:
        mapping['reference']=source_mapping['reference'];mapping['reference_path_base']='project'
        mapping['source_mapping']=mapping_source
        packed_recipe['source_mapping']=mapping_source
    for record,(source_index,rect) in zip(records,source_rects):
        ox,oy=record['offset_pixels']
        raw_to_cell=[scale,0,0,scale,ox,oy]
        source_to_cell=[scale,0,0,scale,ox-rect[0]*scale,oy-rect[1]*scale]
        cel_mapping={'index':record['index'],'source_index':source_index,'source_rect':rect,'source_pivot':record['source_pivot'],'raw_cel_to_cell':raw_to_cell,'source_to_cell':source_to_cell}
        if source_mapping: cel_mapping['reference_to_cell']=multiply_affine(source_to_cell,invert_affine(source_mapping['image_to_reference']))
        mapping['cels'].append(cel_mapping)
    asset = {'id': recipe['id'], 'kind': 'atlas', 'file': 'atlas.png', 'width': atlas.width, 'height': atlas.height,
        'sha256': sha(out/'atlas.png'), 'atlas': {'columns': columns,'rows':rows,'cell_width':cw,'cell_height':ch,'frame_count':len(frames)},
        'registration_mapping':mapping, 'pivot':target, 'sockets':recipe.get('sockets',{}), 'provenance': {'recipe':'recipe.json','cache_key':cache_key,'sources':packed_sources},
        'rights':recipe.get('rights','Unspecified; inherits source restrictions.')}
    if recipe.get('cel_trim', 'region_receipt'): asset['provenance']['cel_trim', 'region_receipt']=recipe['cel_trim', 'region_receipt']
    if compound: asset['provenance']['preparation_receipt']=recipe['preparation_receipt']
    if motion: asset['provenance']['motion_preparation']=recipe['motion_preparation']
    if mapping_source:
        asset['provenance']['source_mapping'] = mapping_source
    if edge_source:
        asset['provenance']['edge_preparation'] = edge_source
    if landmark_source:
        asset['provenance']['registration_source'] = landmark_source
    write(out/'asset.json',asset);write(out/'recipe.json',packed_recipe)
    outputs = {p.name:sha(p) for p in out.iterdir() if p.is_file()}
    report = {'version':VERSION,'cache_key':cache_key,'pillow':PILLOW_VERSION,'frame_count':len(frames),'mode':mode,
        'registration_mapping':mapping,'shared_scale':scale,'frames':records,'warnings':warnings,'outputs':outputs,
        'limits':['Does not remove backgrounds, track moving features, infer fake checkerboards, or judge the closing gesture.','Preview GIF timing is for inspection; the scene owns production timing.']}
    write(out/'report.json',report)
    if region:
        validate_region_receipt(region_path,recipe['region_receipt']['sha256'],source_paths,recipe)
        if recipe_path.read_bytes()!=recipe_bytes: raise ValueError('Recipe changed before region publication')
    if compound:
        validate_preparation_receipt(compound_path,recipe['preparation_receipt']['sha256'],source_paths,recipe)
        if recipe_path.read_bytes()!=recipe_bytes: raise ValueError('Recipe changed before preparation publication')
    if motion:
        validate_preparation(motion_path,recipe['motion_preparation']['sha256'],source_paths)
        if recipe_path.read_bytes()!=recipe_bytes: raise ValueError('Recipe changed before motion publication')
    return {'status':'built','pack':str(out),'frames':len(frames),'shared_scale':scale,'warnings':warnings}

def admit(pack, catalog_path):
    pack, catalog_path = Path(pack).resolve(), Path(catalog_path).resolve()
    root = catalog_path.parent.parent
    report = json.loads((pack/'report.json').read_text())
    if not all((pack/f).is_file() and sha(pack/f) == h for f,h in report['outputs'].items()):
        raise ValueError('Pack bytes no longer match its build report.')
    asset = json.loads((pack/'asset.json').read_text())
    if any(asset.get('provenance',{}).get(k) for k in ['motion_preparation', 'preparation_receipt', 'cel_trim', 'region_receipt']):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
        from ambiance_studio.assets import inspect_pack
        inspect_pack(pack)
    asset['file'] = str((pack/'atlas.png').relative_to(root))
    asset['provenance']['recipe'] = str((pack/'recipe.json').relative_to(root))
    catalog = json.loads(catalog_path.read_text())
    existing = next((a for a in catalog['assets'] if a['id'] == asset['id']),None)
    if existing:
        if existing == asset: return {'status':'already admitted','id':asset['id']}
        raise ValueError('Asset id already exists; use a new version id.')
    catalog['assets'].append(asset)
    temp = catalog_path.with_suffix('.tmp');write(temp,catalog);temp.replace(catalog_path)
    return {'status':'admitted','id':asset['id']}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('build');p.add_argument('recipe',type=Path);p.add_argument('--out',required=True,type=Path)
    p=sub.add_parser('admit');p.add_argument('pack',type=Path);p.add_argument('--catalog',required=True,type=Path)
    args=parser.parse_args()
    try:
        result=build(args.recipe,args.out) if args.command=='build' else admit(args.pack,args.catalog)
        print(json.dumps(result,indent=2));return 0
    except (ValueError,KeyError,TypeError,OSError) as e:
        print(json.dumps({'ok':False,'error':str(e)}));return 1

if __name__=='__main__': sys.exit(main())
