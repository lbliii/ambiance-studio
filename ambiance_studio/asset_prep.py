"""Decoded raster facts and explicit crop/return derivatives; no image generation."""
from contextlib import contextmanager
import hashlib
import io
import json
import math
from pathlib import Path
import shutil
import tempfile


def sha(data): return hashlib.sha256(data).hexdigest()
def load(path): return json.loads(Path(path).read_text())
def write(path, data): Path(path).write_text(json.dumps(data, indent=2, allow_nan=False)+'\n')


def fields(value, allowed, name):
    if not isinstance(value, dict) or set(value)-set(allowed): raise ValueError(f'Unsupported {name} fields; expected {", ".join(allowed)}')


def project_file(project, relative):
    if not isinstance(relative, str) or Path(relative).is_absolute(): raise ValueError('Manifest file references must be project-relative')
    path=(project/relative).resolve()
    if not path.is_relative_to(project): raise ValueError(f'Manifest path must stay inside project: {relative}')
    return path


def relative(project, path):
    path=Path(path).resolve()
    if not path.is_relative_to(project): raise ValueError(f'Crop/return files must stay inside the selected project: {path}')
    return str(path.relative_to(project))


def decoded(path):
    from PIL import Image
    path=Path(path).resolve();data=path.read_bytes()
    with Image.open(io.BytesIO(data)) as raw:
        raw.load(); info={'resolved_path':str(path),'path_base':'shell','sha256':sha(data),'bytes':len(data),'format':raw.format,'width':raw.width,'height':raw.height,'mode':raw.mode,'frames':getattr(raw,'n_frames',1),'has_alpha_channel':'A' in raw.getbands(),'has_transparency_metadata':'transparency' in raw.info}
        image=raw.convert('RGBA')
    return image,info


def identity(project, path, info): return {'file':relative(project,path),'sha256':info['sha256'],'width':info['width'],'height':info['height']}


def checked_image(project, record):
    fields(record,['file','sha256','width','height'],'image identity')
    image,info=decoded(project_file(project,record['file']))
    if any(record.get(k)!=info[k] for k in ['sha256','width','height']): raise ValueError(f'Image identity changed: {record.get("file")}')
    if info['frames']!=1: raise ValueError('Crop/return requires a single-frame raster')
    return image,info


@contextmanager
def fresh(out):
    out=Path(out).resolve()
    if out.exists(): raise ValueError(f'Output exists; choose a fresh directory: {out}')
    out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.asset-prep-',dir=out.parent) as temp:
        stage=Path(temp)
        yield stage
        out.mkdir() # Exclusive reservation; never rename over an existing empty directory.
        try:
            for child in stage.iterdir(): shutil.move(str(child),out/child.name)
        except BaseException:
            shutil.rmtree(out);raise


def previews(stage,image):
    from PIL import Image
    size=image.size;scale=min(1,1024/max(size));small=image.resize((max(1,round(size[0]*scale)),max(1,round(size[1]*scale))),Image.Resampling.LANCZOS)
    for name,color in [('light','#eee8dd'),('dark','#202432')]:
        bg=Image.new('RGBA',small.size,color);bg.alpha_composite(small);bg.convert('RGB').save(stage/f'{name}.png')
    small.getchannel('A').save(stage/'alpha.png')


def preflight(source,out):
    image,info=decoded(source);hist=image.getchannel('A').histogram();pixels=image.width*image.height
    facts={'alpha_min':next(i for i,n in enumerate(hist) if n),'alpha_max':next(i for i in range(255,-1,-1) if hist[i]),'fully_transparent_pixels':hist[0],'partially_transparent_pixels':sum(hist[1:255]),'opaque_pixels':hist[255],'total_pixels':pixels,'alpha_content_bounds':image.getchannel('A').getbbox()}
    report={'ok':True,'type':'ambiance-asset-preflight','version':1,'source':info,'decoded_frame':0,'alpha':facts,'limits':['Measured decoded alpha facts do not certify a clean matte. Painted checkerboards remain opaque pixels.','Multi-frame inputs report frame zero only. Crop/return requires a still image.']}
    with fresh(out) as stage:
        previews(stage,image);report['outputs']={f.name:sha(f.read_bytes()) for f in stage.iterdir()};write(stage/'report.json',report)
        if sha(Path(source).read_bytes())!=info['sha256']: raise ValueError('Preflight source changed during preparation; no result published')
    return {**report,'resolved_path':str(Path(out).resolve()),'path_base':'shell'}


def affine(matrix):
    if not isinstance(matrix,list) or len(matrix)!=6 or any(type(v) not in [int,float] or not math.isfinite(v) for v in matrix): raise ValueError('Supply an explicit finite six-number affine [a,b,c,d,e,f]')
    a,b,c,d,e,f=matrix
    if abs(a*d-b*c)<1e-12: raise ValueError('Registration affine must be invertible')
    return matrix


def inverse(m):
    a,b,c,d,e,f=affine(m);det=a*d-b*c
    return [d/det,-b/det,-c/det,a/det,(c*f-d*e)/det,(b*e-a*f)/det]


def multiply(a,b):
    x,y,z,w,tx,ty=a;u,v,r,s,px,py=b
    return [x*u+z*v,y*u+w*v,x*r+z*s,y*r+w*s,x*px+z*py+tx,y*px+w*py+ty]


def resample(image,size,forward,method):
    from PIL import Image
    modes={'nearest':Image.Resampling.NEAREST,'bicubic':Image.Resampling.BICUBIC}
    if method not in modes: raise ValueError('Affine resampling must be nearest or bicubic')
    a,b,c,d,e,f=inverse(forward)
    return image.convert('RGBa').transform(size,Image.Transform.AFFINE,(a,c,e,b,d,f),modes[method]).convert('RGBA')


def crop(project,source,recipe_path,out):
    from PIL import Image
    project=Path(project).resolve();out=Path(out).resolve();relative(project,out)
    source=Path(source).resolve();image,info=decoded(source)
    if info['frames']!=1: raise ValueError('Crop requires a single-frame raster')
    recipe_bytes=Path(recipe_path).read_bytes();recipe=json.loads(recipe_bytes)
    fields(recipe,['version','crop_xyxy','export_size','resampling'],'crop recipe')
    if recipe.get('version')!=1: raise ValueError('Expected crop recipe version 1')
    rect=recipe.get('crop_xyxy');size=recipe.get('export_size')
    if not isinstance(rect,list) or len(rect)!=4 or any(type(x) is not int for x in rect) or not (0<=rect[0]<rect[2]<=image.width and 0<=rect[1]<rect[3]<=image.height): raise ValueError('crop_xyxy must be integer source bounds inside the image')
    if not isinstance(size,list) or len(size)!=2 or any(type(x) is not int or not 1<=x<=8192 for x in size): raise ValueError('export_size must be two positive integers <=8192')
    method=recipe.get('resampling','bicubic')
    if method not in ['nearest','bicubic']: raise ValueError('Crop resampling must be nearest or bicubic')
    native=image.crop(rect);nw,nh=native.size
    exported=resample(native,tuple(size),[size[0]/nw,0,0,size[1]/nh,0,0],method)
    reference=identity(project,source,info)
    mapping={'format':'ambiance-asset-source-mapping','version':1,'path_base':'project','reference':reference,'image_to_reference':[nw/size[0],0,0,nh/size[1],rect[0],rect[1]],'native_crop_xyxy':rect,'export_size':size,'registration':'native crop; no generated return inferred','resampling':method}
    with fresh(out) as stage:
        exported.save(stage/'crop.png');crop_info=decoded(stage/'crop.png')[1];mapping['image']=identity(project,out/'crop.png',crop_info)
        write(stage/'source-mapping.json',mapping);(stage/'recipe.json').write_bytes(recipe_bytes)
        manifest={'format':'ambiance-asset-crop','version':1,'path_base':'project','source':reference,'crop':mapping['image'],'crop_xyxy':rect,'export_size':size,'export_to_reference':mapping['image_to_reference'],'resampling':method,'recipe_sha256':sha(recipe_bytes)}
        write(stage/'crop-manifest.json',manifest)
        template={'format':'ambiance-asset-return','version':1,'path_base':'project','crop_manifest':{'file':relative(project,out/'crop-manifest.json'),'sha256':sha((stage/'crop-manifest.json').read_bytes())},'expected_edit_size':size,'registration':{'edit_to_export':None,'note':'Author an explicit registration after inspecting the returned art; matching dimensions do not prove alignment.'},'blend_mask':{'kind':'full'},'resampling':method}
        write(stage/'return-template.json',template);previews(stage,exported)
        report={'ok':True,'operation':'crop','source':info,'recipe_sha256':sha(recipe_bytes),'outputs':{f.name:sha(f.read_bytes()) for f in stage.iterdir()}}
        write(stage/'report.json',report)
        if sha(source.read_bytes())!=info['sha256'] or sha(Path(recipe_path).read_bytes())!=sha(recipe_bytes): raise ValueError('Crop source/recipe changed during preparation')
    return {**report,'resolved_path':str(out),'path_base':'shell','mapping':str(out/'source-mapping.json'),'return_template':str(out/'return-template.json')}


def return_edit(project,edit,mapping_path,out):
    from PIL import Image,ImageChops
    project=Path(project).resolve();out=Path(out).resolve();relative(project,out)
    mapping_bytes=Path(mapping_path).read_bytes();spec=json.loads(mapping_bytes)
    fields(spec,['format','version','path_base','crop_manifest','expected_edit_size','registration','blend_mask','resampling'],'return mapping')
    if spec.get('format')!='ambiance-asset-return' or spec.get('version')!=1 or spec.get('path_base')!='project': raise ValueError('Expected ambiance-asset-return version1, project-relative manifest references')
    ref=spec['crop_manifest'];manifest_path=project_file(project,ref['file']);manifest_bytes=manifest_path.read_bytes()
    if sha(manifest_bytes)!=ref['sha256']: raise ValueError('Crop manifest changed')
    manifest=json.loads(manifest_bytes)
    if manifest.get('format')!='ambiance-asset-crop' or manifest.get('version')!=1 or manifest.get('path_base')!='project': raise ValueError('Unsupported crop manifest')
    original,original_info=checked_image(project,manifest['source']);checked_image(project,manifest['crop'])
    rect=manifest.get('crop_xyxy');export_size=manifest.get('export_size')
    if not isinstance(rect,list) or len(rect)!=4 or any(type(x) is not int for x in rect) or not (0<=rect[0]<rect[2]<=original.width and 0<=rect[1]<rect[3]<=original.height): raise ValueError('Crop manifest has invalid native geometry')
    if not isinstance(export_size,list) or len(export_size)!=2 or any(type(x) is not int or x<=0 for x in export_size) or export_size!=[manifest['crop']['width'],manifest['crop']['height']]: raise ValueError('Crop manifest export geometry differs from its image')
    expected_transform=[(rect[2]-rect[0])/export_size[0],0,0,(rect[3]-rect[1])/export_size[1],rect[0],rect[1]]
    if manifest.get('export_to_reference')!=expected_transform: raise ValueError('Crop manifest transform differs from its native crop/export geometry')
    edited,edit_info=decoded(edit)
    if not isinstance(spec['expected_edit_size'],list) or any(type(x) is not int for x in spec['expected_edit_size']) or edit_info['frames']!=1 or list(edited.size)!=spec['expected_edit_size']: raise ValueError('Unexpected returned geometry; author an updated expected_edit_size and registration explicitly')
    registration=spec['registration'];fields(registration,['edit_to_export','note'],'return registration')
    edit_to_export=affine(registration.get('edit_to_export'))
    rect=manifest['crop_xyxy'];native_size=(rect[2]-rect[0],rect[3]-rect[1])
    export_to_native=[native_size[0]/manifest['export_size'][0],0,0,native_size[1]/manifest['export_size'][1],0,0]
    method=spec.get('resampling','bicubic');native=resample(edited,native_size,multiply(export_to_native,edit_to_export),method)
    mask_spec=spec['blend_mask'];mask_identity=None
    if mask_spec=={'kind':'full'}: mask=Image.new('L',native_size,255)
    else:
        fields(mask_spec,['kind','file','sha256'],'blend mask')
        if mask_spec.get('kind')!='image': raise ValueError('blend_mask is {kind:full} or {kind:image,file,sha256}; image mask is native crop-sized grayscale')
        mask_path=project_file(project,mask_spec['file']);mask_bytes=mask_path.read_bytes()
        if sha(mask_bytes)!=mask_spec['sha256']: raise ValueError('Blend mask changed')
        with Image.open(io.BytesIO(mask_bytes)) as m:
            if m.mode!='L' or m.size!=native_size: raise ValueError('Blend mask must be grayscale L at native crop dimensions')
            mask=m.copy()
        mask_identity={'file':mask_spec['file'],'sha256':sha(mask_bytes),'width':mask.width,'height':mask.height}
    native.putalpha(ImageChops.multiply(native.getchannel('A'),mask))
    composite=original.copy();composite.alpha_composite(native,(rect[0],rect[1]))
    edit_identity=identity(project,edit,edit_info)
    with fresh(out) as stage:
        native.save(stage/'patch.png');composite.save(stage/'composite.png');mask.save(stage/'blend-mask.png');(stage/'return-recipe.json').write_bytes(mapping_bytes)
        patch_info=decoded(stage/'patch.png')[1]
        result_mapping={'format':'ambiance-asset-source-mapping','version':1,'path_base':'project','reference':manifest['source'],'image':identity(project,out/'patch.png',patch_info),'image_to_reference':[1,0,0,1,rect[0],rect[1]],'native_crop_xyxy':rect,'export_size':manifest['export_size'],'registration':{'edit':edit_identity,'edit_to_export':edit_to_export,'edit_to_reference':multiply(manifest['export_to_reference'],edit_to_export),'recipe':{'file':relative(project,Path(mapping_path)),'sha256':sha(mapping_bytes)},'crop_manifest':ref,'blend_mask':mask_identity or {'kind':'full'}},'resampling':method}
        write(stage/'source-mapping.json',result_mapping);previews(stage,native)
        report={'ok':True,'operation':'return','source':manifest['source'],'edit':edit_identity,'registration':result_mapping['registration'],'native_crop_xyxy':rect,'sampling_note':'nearest can preserve exact integer-grid round trips; bicubic is a resampled derivative','outputs':{f.name:sha(f.read_bytes()) for f in stage.iterdir()}}
        write(stage/'report.json',report)
        if mask_identity and sha(project_file(project,mask_identity['file']).read_bytes())!=mask_identity['sha256']: raise ValueError('Blend mask changed during preparation')
        if sha(project_file(project,manifest['crop']['file']).read_bytes())!=manifest['crop']['sha256']: raise ValueError('Exported crop changed during return preparation')
        if sha(Path(edit).read_bytes())!=edit_info['sha256'] or sha(Path(mapping_path).read_bytes())!=sha(mapping_bytes) or sha(manifest_path.read_bytes())!=ref['sha256'] or sha(project_file(project,manifest['source']['file']).read_bytes())!=original_info['sha256']: raise ValueError('Return inputs changed during preparation')
    return {**report,'resolved_path':str(out),'path_base':'shell','mapping':str(out/'source-mapping.json'),'patch':str(out/'patch.png'),'composite':str(out/'composite.png')}
