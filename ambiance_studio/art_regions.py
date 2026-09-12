"""Source-bound regions, uniform generation frames and high-resolution returns."""
import copy
import io
import json
import math
from pathlib import Path
import re

from . import asset_prep as ap, masks
from .edge_quality import fresh_output, integer, number
from .scene_runtime import load_scene_json, scene_bridge

ROOT = Path(__file__).resolve().parents[1]
FORMAT = 'ambiance-art-region'
MAX_SIDE = 4092
MAX_PIXELS = 8_388_608


def read(path):
    return load_scene_json(Path(path).read_bytes())


def record(project, path):
    _, info = ap.decoded(path)
    return ap.identity(Path(project).resolve(), path, info)


def file_ref(project, path):
    return {'file': ap.relative(Path(project).resolve(), path), 'sha256': ap.sha(Path(path).read_bytes())}


def initial(project, source, id):
    return {'format': FORMAT, 'version': 1, 'path_base': 'project', 'id': id, 'title': id,
            'source': record(project, source), 'intent': {'brief': '', 'preserve': '', 'asset_id': None},
            'visible_mask': {'polygons': []}, 'paint_coverage': {'bleed': [0,0,0,0], 'reveal_xyxy': None},
            'frame': {'aspect': 'tight', 'padding': [0,0,0,0], 'rect_xyxy': None},
            'sizing': {'mode': 'manual', 'display_size': None, 'quality_multiplier': 1.5,
                       'export_size': None, 'allowed_sizes': [], 'allow_under_target': False},
            'context': None, 'raster': {'supersample': 2, 'resampling': 'bicubic'}}


def vector(value, name, count=4, low=0, high=32768):
    if not isinstance(value, list) or len(value) != count:
        raise ValueError(f'{name} needs {count} numbers')
    return [number(v, name, low, high) for v in value]


def rectangle(value, name, w=None, h=None):
    l,t,r,b = vector(value, name, low=-32768)
    if r<=l or b<=t or (w is not None and not (0<=l<r<=w and 0<=t<b<=h)):
        raise ValueError(f'{name} must be a nonempty rectangle'+(' inside the source' if w is not None else ''))
    return value


def size(value, name):
    if not isinstance(value,list) or len(value)!=2:
        raise ValueError(f'{name} needs two integer dimensions')
    for n in value: integer(n,name,1,MAX_SIDE)
    if value[0]*value[1]>MAX_PIXELS: raise ValueError(f'{name} exceeds the pixel budget')
    return value


def reference(ref, image=False):
    ap.fields(ref, ['file','sha256','width','height'] if image else ['file','sha256'], 'reference')
    if not isinstance(ref.get('file'), str) or not ref['file'] or Path(ref['file']).is_absolute() or '..' in Path(ref['file']).parts:
        raise ValueError('References must be project-relative without parent traversal')
    if not re.fullmatch('[a-f0-9]{64}',ref.get('sha256','')): raise ValueError('Reference needs a SHA-256')
    if image: size([ref.get('width'),ref.get('height')],'source image')


def references(recipe):
    yield 'source', recipe['source']
    if recipe['visible_mask'].get('image'): yield 'mask', recipe['visible_mask']['image']
    if recipe['context']:
        for role in ('scene','catalog','scope'):
            yield role, recipe['context'][role]


def validate(recipe):
    ap.fields(recipe,['format','version','path_base','id','title','source','intent','visible_mask',
                      'paint_coverage','frame','sizing','context','raster'],'region')
    if recipe.get('format')!=FORMAT or type(recipe.get('version')) is not int or recipe['version']!=1 or recipe.get('path_base')!='project':
        raise ValueError('Expected ambiance-art-region version 1 with project-relative references')
    if not re.fullmatch('[a-z][a-z0-9_-]{0,63}',recipe.get('id','')): raise ValueError('Invalid region ID')
    if not isinstance(recipe.get('title'),str) or not 1<=len(recipe['title'])<=160: raise ValueError('Region title needs 1–160 characters')
    reference(recipe['source'],True); w,h=recipe['source']['width'],recipe['source']['height']
    intent=recipe['intent'];ap.fields(intent,['brief','preserve','asset_id'],'intent')
    for key in ('brief','preserve'):
        if not isinstance(intent.get(key),str) or len(intent[key])>16000: raise ValueError('Intent must contain bounded text')
    if intent.get('asset_id') is not None and not re.fullmatch('[a-z][a-z0-9-]{0,63}',intent['asset_id']): raise ValueError('Invalid intended asset ID')
    spec=recipe['visible_mask'];ap.fields(spec,['polygons','image'],'visible mask')
    if spec.get('image'):
        reference(spec['image'],True)
        if [spec['image']['width'],spec['image']['height']]!=[w,h]: raise ValueError('Mask must have source dimensions')
    polys=spec.get('polygons')
    if not isinstance(polys,list) or len(polys)>128: raise ValueError('Mask supports at most 128 polygons')
    total=0
    for poly in polys:
        ap.fields(poly,['operation','points'],'polygon')
        if poly.get('operation') not in ('add','subtract'): raise ValueError('Polygon operation must be add or subtract')
        points=poly.get('points')
        if not isinstance(points,list) or not 3<=len(points)<=512: raise ValueError('Polygon needs 3–512 vertices')
        for p in points:
            vector(p,'vertex',2)
            if not (0<=p[0]<=w-1 and 0<=p[1]<=h-1): raise ValueError('Polygon vertex lies outside source pixel centers')
        area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(points,points[1:]+points[:1]))
        if abs(area)<1e-9: raise ValueError('Degenerate polygon')
        total+=len(points)
    if total>8192: raise ValueError('Mask exceeds 8192 vertices')
    coverage=recipe['paint_coverage'];ap.fields(coverage,['bleed','reveal_xyxy'],'paint coverage')
    vector(coverage['bleed'],'bleed')
    if coverage.get('reveal_xyxy') is not None: rectangle(coverage['reveal_xyxy'],'reveal',w,h)
    frame=recipe['frame'];ap.fields(frame,['aspect','padding','rect_xyxy'],'frame');vector(frame['padding'],'context padding')
    if isinstance(frame['aspect'],str) and frame['aspect'] not in ('tight','square'):
        raise ValueError('Aspect must be tight, square or [width,height]')
    if not isinstance(frame['aspect'],str):
        vector(frame['aspect'],'aspect',2,low=1,high=4096)
    if frame.get('rect_xyxy') is not None: rectangle(frame['rect_xyxy'],'frame')
    sizing=recipe['sizing'];ap.fields(sizing,['mode','display_size','quality_multiplier','export_size','allowed_sizes','allow_under_target'],'sizing')
    if sizing['mode'] not in ('manual','scene'): raise ValueError('Sizing mode must be manual or scene')
    if sizing.get('display_size') is not None: vector(sizing['display_size'],'display size',2,low=1,high=32768)
    number(sizing['quality_multiplier'],'quality multiplier',1,8)
    if sizing.get('export_size') is not None: size(sizing['export_size'],'export size')
    if not isinstance(sizing['allowed_sizes'],list) or len(sizing['allowed_sizes'])>64: raise ValueError('Supply at most 64 allowed sizes')
    for v in sizing['allowed_sizes']: size(v,'allowed size')
    if type(sizing['allow_under_target']) is not bool: raise ValueError('allow_under_target must be boolean')
    raster=recipe['raster'];ap.fields(raster,['supersample','resampling'],'raster policy')
    if type(raster['supersample']) is not int or raster['supersample'] not in (1,2,4): raise ValueError('Mask supersample must be 1, 2 or 4')
    if raster['resampling'] not in ('nearest','bicubic'): raise ValueError('Unsupported resampling')
    context=recipe['context']
    if context is not None:
        ap.fields(context,['scene','catalog','scope','base','views','start_frame','frames'],'context')
        for key in ('scene','catalog','scope'): reference(context[key])
        if not isinstance(context['base'],str) or not context['base']: raise ValueError('Context needs a base layer')
        if not isinstance(context['views'],list) or not 1<=len(context['views'])<=8 or any(not isinstance(v,str) for v in context['views']) or len(set(context['views']))!=len(context['views']): raise ValueError('Context needs 1–8 unique views')
        integer(context['start_frame'],'start frame',0,200000)
        if context['frames'] is not None: integer(context['frames'],'frames',1,200000)
    if sizing['mode']=='scene' and context is None: raise ValueError('Scene sizing requires a bound context')
    return recipe


def load_inputs(project, recipe):
    validate(recipe)
    result={}
    for role,ref in references(recipe):
        data=ap.project_file(Path(project).resolve(),ref['file']).read_bytes()
        if ap.sha(data)!=ref['sha256']: raise ValueError(f'Region input changed: {role} ({ref["file"]})')
        result[role]=data
    decode(recipe,result)
    return result


def decode(recipe, inputs):
    from PIL import Image
    images={}
    for role,ref in references(recipe):
        data=inputs[role]
        if ap.sha(data)!=ref['sha256']: raise ValueError(f'Captured {role} identity changed')
        if role not in ('source','mask'): continue
        with Image.open(io.BytesIO(data)) as im:
            im.load()
            if list(im.size)!=[ref['width'],ref['height']] or getattr(im,'n_frames',1)!=1: raise ValueError('Region needs still images matching recorded dimensions')
            if role=='mask' and im.mode!='L': raise ValueError('Imported mask must be grayscale L')
            images[role]=im.copy() if role=='mask' else im.convert('RGBA')
    return images


def expand_aspect(rect, ratio):
    l,t,r,b=rect; w,h=r-l,b-t
    nw,nh=max(w,h*ratio),max(h,w/ratio)
    return [(l+r-nw)/2,(t+b-nh)/2,(l+r+nw)/2,(t+b+nh)/2]


def geometry(recipe, inputs):
    validate(recipe);images=decode(recipe,inputs)
    mask=masks.rasterize(recipe['visible_mask'],images['source'].size,images.get('mask'))
    bounds=mask.getbbox()
    if bounds is None: return {'ready':False,'issues':['Visible shape is empty.'], 'source_size':list(images['source'].size)}, images,mask
    l,t,r,b=bounds; bleed=recipe['paint_coverage']['bleed']; coverage=[l-bleed[0],t-bleed[1],r+bleed[2],b+bleed[3]]
    reveal=recipe['paint_coverage'].get('reveal_xyxy')
    if reveal: coverage=[min(coverage[0],reveal[0]),min(coverage[1],reveal[1]),max(coverage[2],reveal[2]),max(coverage[3],reveal[3])]
    rectangle(coverage,'Required paint coverage',*images['source'].size)
    padding=recipe['frame']['padding']; frame=[coverage[0]-padding[0],coverage[1]-padding[1],coverage[2]+padding[2],coverage[3]+padding[3]]
    aspect=recipe['frame']['aspect']
    if aspect!='tight': frame=expand_aspect(frame,1 if aspect=='square' else aspect[0]/aspect[1])
    explicit=recipe['frame'].get('rect_xyxy')
    if explicit:
        if not (explicit[0]<=frame[0] and explicit[1]<=frame[1] and explicit[2]>=frame[2] and explicit[3]>=frame[3]): raise ValueError('Explicit frame clips required paint or context padding')
        frame=explicit[:]
        if aspect!='tight' and not math.isclose((frame[2]-frame[0])/(frame[3]-frame[1]),1 if aspect=='square' else aspect[0]/aspect[1],rel_tol=1e-9): raise ValueError('Explicit frame conflicts with aspect lock')
    sizing=recipe['sizing']; context=recipe['context']; assumptions=[]; measured=None
    if sizing['mode']=='scene':
        scope=load_scene_json(inputs['scope'])
        intended=[o['view_id'] for o in scope['outputs']] if scope.get('format')=='ambiance-production-plan' else scope.get('intended_views')
        if not intended: intended=context['views']
        if set(context['views'])!=set(intended): raise ValueError('Region context must cover every intended output view')
        measured=scene_bridge('region-demand',load_scene_json(inputs['scene']),load_scene_json(inputs['catalog']),
                              {k:context[k] for k in ('base','views','start_frame','frames')}|{'reference':recipe['source'],'bounds':list(bounds)})
        density=measured['max_density']
    elif sizing.get('display_size'):
        density=max(sizing['display_size'][0]/(r-l),sizing['display_size'][1]/(b-t));assumptions.append('Manual intended display size.')
    else:
        density=1;assumptions.append('Native source density; final display demand is unspecified.')
    required=density*sizing['quality_multiplier']; fw,fh=frame[2]-frame[0],frame[3]-frame[1]
    ideal=[math.ceil(fw*required),math.ceil(fh*required)]
    sizes=sizing['allowed_sizes']; selected=sizing.get('export_size')
    if selected and sizes and selected not in sizes: raise ValueError('Explicit export size is absent from the allowed sizes')
    if not selected and sizes:
        fitting=[v for v in sizes if min(v[0]/fw,v[1]/fh)>=required-1e-9]
        selected=min(fitting,key=lambda v:v[0]*v[1]) if fitting else max(sizes,key=lambda v:min(v[0]/fw,v[1]/fh))
    selected=selected or ideal
    size(selected,'Requested export size')
    if selected[0]*selected[1]*recipe['raster']['supersample']**2>64_000_000: raise ValueError('Supersampled mask exceeds 64M pixels; choose explicit smaller dimensions or supersampling')
    frame=expand_aspect(frame,selected[0]/selected[1]);fw,fh=frame[2]-frame[0],frame[3]-frame[1]
    effective=selected[0]/fw; adequate=effective+1e-9>=required
    issues=[]
    if not adequate: issues.append('Selected image size is below the required pixel density.')
    for view in (measured or {}).get('views',[]):
        if not view['intersects_view']: issues.append(f'The region is outside view {view["id"]} throughout the sampled interval.')
        elif not view['fully_contained_every_frame']: issues.append(f'View {view["id"]} crops part of the region during the sampled interval; inspect its framing.')
    return {'ready':adequate or sizing['allow_under_target'],'issues':issues,'study':not adequate,
            'bounds':list(bounds),'coverage_xyxy':coverage,'frame_xyxy':frame,'export_size':selected,
            'source_size':list(images['source'].size),'required_density':required,'effective_density':effective,
            'meets_demand':adequate,'ideal_size':ideal,'assumptions':assumptions,'measurement':measured,
            'provider_compatibility':'caller-supplied sizes' if sizes else 'unchecked',
            'source_to_export':[effective,0,0,effective,-frame[0]*effective,-frame[1]*effective],
            'export_to_source':[1/effective,0,0,1/effective,frame[0],frame[1]]},images,mask


def pictures(recipe, inputs, info=None):
    from PIL import Image, ImageChops, ImageDraw
    info,images,native=geometry(recipe,inputs) if info is None else info
    source=images['source']; overlay=Image.new('RGBA',source.size,'#54d6cd');overlay.putalpha(native.point(lambda v:round(v*.35)))
    context=Image.alpha_composite(source,overlay)
    result={'source':source,'context':context,'visible-native':native}
    if 'export_size' not in info: return info,result
    sz=tuple(info['export_size']);m=info['source_to_export']; method=recipe['raster']['resampling']
    visible=masks.projected(recipe['visible_mask'],sz,m,images.get('mask'),recipe['raster']['supersample'])
    coverage=Image.new('L',source.size)
    if recipe['paint_coverage']=={'bleed':[0,0,0,0],'reveal_xyxy':None}: coverage=native.copy()
    else:
        l,t,r,b=info['coverage_xyxy'];ImageDraw.Draw(coverage).rectangle([math.floor(l),math.floor(t),math.ceil(r)-1,math.ceil(b)-1],fill=255)
    cov_image=Image.new('RGBA',source.size,'white');cov_image.putalpha(coverage)
    coverage_export=ap.resample(cov_image,sz,m,method).getchannel('A')
    ref=ap.resample(source,sz,m,method)
    available=ap.resample(Image.new('RGBA',source.size,'white'),sz,m,method).getchannel('A')
    guide=ref.copy();tint=Image.new('RGBA',sz,'#54d6cd');tint.putalpha(visible.point(lambda v:round(v*.4)));guide=Image.alpha_composite(guide,tint)
    isolated=ref.copy();isolated.putalpha(ImageChops.multiply(ref.getchannel('A'),visible))
    result.update({'reference':ref,'guide':guide,'source-availability':available,'visible-export':visible,
                   'coverage-native':coverage,'coverage-export':coverage_export,'isolated':isolated})
    for view in (info.get('measurement') or {}).get('views',[]):
        ow,oh=view['output']['width'],view['output']['height'];scale=min(1,1200/max(ow,oh))
        width,height=max(1,round(ow*scale)),max(1,round(oh*scale))
        m=ap.multiply([width/ow,0,0,height/oh,0,0],view['source_to_output'])
        result['view-'+view['id']]=ap.resample(context,(width,height),m,method)
    return info,result


def runtime():
    files=['ambiance_studio/art_regions.py','ambiance_studio/masks.py','ambiance_studio/asset_prep.py',
           'editor/region-sizing.mjs','editor/source-placement.mjs','editor/engine.mjs','editor/views.mjs','tools/scene-command.mjs']
    from PIL import __version__
    return {'files':{name:ap.sha((ROOT/name).read_bytes()) for name in files},'pillow':__version__}


def write_receipt(stage, kind, dependencies, extra=None):
    receipt={'format':'ambiance-region-artifact','version':1,'kind':kind,'runtime':runtime(),
             'dependencies':dependencies,'files':{str(p.relative_to(stage)):ap.sha(p.read_bytes()) for p in stage.rglob('*') if p.is_file()},**(extra or {})}
    ap.write(stage/'region-receipt.json',receipt)
    return receipt


def verify(directory, project=None):
    directory=Path(directory).resolve();receipt=read(directory/'region-receipt.json')
    if receipt.get('format')!='ambiance-region-artifact' or receipt.get('version')!=1: raise ValueError('Expected a region artifact receipt')
    if not isinstance(receipt.get('files'),dict) or 'recipe.json' not in receipt['files']: raise ValueError('Region receipt lacks its recipe')
    for name,digest in receipt['files'].items():
        if ap.sha(ap.project_file(directory,name).read_bytes())!=digest: raise ValueError(f'Region artifact changed: {name}')
    if project is None:
        project=next((p for p in directory.parents if (p/'ambiance-project.json').is_file()),None)
    if project is None: raise ValueError('Region artifact needs an initialized project ancestor')
    project=Path(project).resolve()
    for ref in receipt['dependencies']:
        if ap.sha(ap.project_file(project,ref['file']).read_bytes())!=ref['sha256']: raise ValueError(f'Region dependency changed: {ref["file"]}')
    recipe=read(directory/'recipe.json');validate(recipe)
    inputs={role:(directory/'inputs'/role).read_bytes() for role,_ in references(recipe)}
    decode(recipe,inputs)
    return recipe,inputs,receipt


def dependencies(project, recipe):
    # Scene/scope snapshots preserve historical sizing after the scene is edited.
    return [{'file':ref['file'],'sha256':ref['sha256']} for role,ref in references(recipe) if role in ('source','mask')]


def snapshot(stage, recipe, inputs):
    ap.write(stage/'recipe.json',recipe);(stage/'inputs').mkdir()
    for role,data in inputs.items(): (stage/'inputs'/role).write_bytes(data)


def save_draft(project, recipe, out, parent=None, batch=None):
    project=Path(project).resolve();out=Path(out).resolve();ap.relative(project,out)
    inputs=load_inputs(project,recipe)
    with fresh_output(out) as stage:
        snapshot(stage,recipe,inputs)
        if parent is not None: ap.write(stage/'parent-recipe.json',parent)
        if batch is not None: ap.write(stage/'edit-batch.json',batch)
        info,images=pictures(recipe,inputs)
        for name in ('source','context'): images[name].save(stage/(name+'.png'))
        ap.write(stage/'report.json',info)
        write_receipt(stage,'draft',dependencies(project,recipe))
        if load_inputs(project,recipe)!=inputs: raise ValueError('Inputs changed while saving region')
    return inspect(project,out)


def inspect(project,directory):
    project=Path(project).resolve()
    recipe,inputs,receipt=verify(directory,project)
    info=read(Path(directory)/'report.json')
    changed=[role for role,ref in references(recipe) if not ap.project_file(Path(project),ref['file']).is_file() or ap.sha(ap.project_file(Path(project),ref['file']).read_bytes())!=ref['sha256']]
    request=None
    if receipt['kind'] in ('packet','return'):
        from . import generation_ledger as ledger
        request_id=read(Path(directory)/('request-draft.json' if receipt['kind']=='packet' else 'return-recipe.json')).get('local_request_id' if receipt['kind']=='packet' else 'request_id')
        if request_id:
            saved=ledger.load(project)
            request=ledger.summary(project,ledger.find(saved,request_id)) if any(r.get('local_request_id')==request_id for r in saved['requests']) else {
                'local_request_id':request_id,'status':'not-recorded','next_action':'Inspect existing art, then record the request draft before an authorized generation.'}
    return {'ok':True,'directory':str(Path(directory).resolve()),'kind':receipt['kind'],'id':recipe['id'],
            'recipe':str(Path(directory).resolve()/'recipe.json'),'recipe_sha256':ap.sha((Path(directory)/'recipe.json').read_bytes()),
            'ready':info.get('ready',False),'sizing':info,'changed_working_inputs':changed,
            'previews':{p.stem:str(p.resolve()) for p in Path(directory).glob('*.png')},
            'request':request,'review_status':'unreviewed'}


def build(project, directory, out):
    directory=Path(directory).resolve();project=Path(project).resolve();out=Path(out).resolve();ap.relative(project,out)
    if directory.is_file(): recipe=read(directory)
    else: recipe,_,_=verify(directory,project)
    inputs=load_inputs(project,recipe);info,images=pictures(recipe,inputs)
    if not info['ready']: raise ValueError('; '.join(info['issues']))
    with fresh_output(out) as stage:
        snapshot(stage,recipe,inputs)
        for name,im in images.items(): im.save(stage/(name+'.png'))
        ap.previews(stage,images['isolated'])
        ap.write(stage/'report.json',info);ap.write(stage/'sizing.json',info)
        manifest={'format':'ambiance-region-packet','version':1,'source':recipe['source'],'region_id':recipe['id'],
                  'export_size':info['export_size'],'frame_xyxy':info['frame_xyxy'],
                  'source_to_export':info['source_to_export'],'export_to_source':info['export_to_source']}
        ap.write(stage/'region-manifest.json',manifest)
        prompt=recipe['intent']['brief']+'\n\nPreserve: '+recipe['intent']['preserve']+'\n\nPaint the requested scene within the supplied framing. The separate guide identifies the visible opening; do not paint guide strokes. Required hidden paint is recorded in the coverage mask.\n'
        (stage/'prompt.md').write_text(prompt)
        ref={'file':ap.relative(project,out/'reference.png'),'sha256':ap.sha((stage/'reference.png').read_bytes())}
        request=read(ROOT/'templates/generation-request.json')
        request.update(local_request_id=recipe['id']+'-'+ap.sha((stage/'recipe.json').read_bytes())[:12],
                       intended_asset_id=recipe['intent']['asset_id'],prompt=prompt,references=[ref])
        request['settings']={'region_packet':ap.relative(project,out/'region-manifest.json'),
                             'region_manifest_sha256':ap.sha((stage/'region-manifest.json').read_bytes()),'desired_size':info['export_size']}
        ap.write(stage/'request-draft.json',request)
        ap.write(stage/'return-template.json',{'format':'ambiance-region-return','version':1,
                  'packet_manifest_sha256':ap.sha((stage/'region-manifest.json').read_bytes()),'expected_edit_size':info['export_size'],
                  'registration':{'edit_to_export':None,'note':'Inspect the returned art and supply its alignment.'},'request_id':None})
        write_receipt(stage,'packet',dependencies(project,recipe))
        if load_inputs(project,recipe)!=inputs: raise ValueError('Region inputs changed during packet build')
    return inspect(project,out)


def return_art(project, directory, returned, recipe_path, out):
    from PIL import Image, ImageChops
    project=Path(project).resolve();directory=Path(directory).resolve();out=Path(out).resolve();ap.relative(project,out)
    recipe,inputs,packet=verify(directory,project)
    if packet['kind']!='packet': raise ValueError('Return needs a built region packet')
    if load_inputs(project,recipe)!=inputs: raise ValueError('Sizing context changed; rebuild the packet explicitly')
    spec_bytes=Path(recipe_path).read_bytes();spec=load_scene_json(spec_bytes)
    ap.fields(spec,['format','version','packet_manifest_sha256','expected_edit_size','registration','request_id'],'region return')
    if spec.get('format')!='ambiance-region-return' or spec.get('version')!=1: raise ValueError('Expected ambiance-region-return version 1')
    if spec['packet_manifest_sha256']!=ap.sha((directory/'region-manifest.json').read_bytes()): raise ValueError('Return targets a different packet manifest')
    edited,edit_info=ap.decoded(returned);size(spec['expected_edit_size'],'returned size')
    if edit_info['frames']!=1 or list(edited.size)!=spec['expected_edit_size']: raise ValueError('Unexpected returned dimensions; author expected size and registration explicitly')
    ap.fields(spec['registration'],['edit_to_export','note'],'registration')
    matrix=ap.affine(spec['registration']['edit_to_export'])
    if not isinstance(spec['registration'].get('note'),str) or not spec['registration']['note'].strip(): raise ValueError('Record the alignment observation')
    request_snapshot=None
    if spec['request_id'] is not None:
        from . import generation_ledger as ledger
        selected=ledger.summary(project,ledger.find(ledger.load(project),spec['request_id']))
        if not selected['ok'] or edit_info['sha256'] not in [o['sha256'] for o in selected['outputs']]: raise ValueError('Returned image is not recorded on the specified request')
        request_snapshot=selected
    info=read(directory/'report.json');sz=tuple(info['export_size']);method=recipe['raster']['resampling']
    paint=ap.resample(edited,sz,matrix,method)
    def load_image(name):
        with Image.open(directory/(name+'.png')) as im: return im.copy()
    visible=load_image('visible-export');coverage=load_image('coverage-export');native_mask=load_image('visible-native')
    patch=paint.copy();patch.putalpha(ImageChops.multiply(paint.getchannel('A'),visible))
    missing=ImageChops.multiply(coverage,ImageChops.invert(paint.getchannel('A')))
    missing_pixels=sum(missing.histogram()[1:])
    source=decode(recipe,inputs)['source'];native=ap.resample(paint,source.size,info['export_to_source'],method)
    native.putalpha(ImageChops.multiply(native.getchannel('A'),native_mask))
    composite=Image.alpha_composite(source,native)
    deps=dependencies(project,recipe)+[file_ref(project,directory/'region-receipt.json')]
    deps += [file_ref(project,directory/name) for name in packet['files']]
    id=recipe['intent']['asset_id'] or recipe['id'].replace('_','-')+'-'+edit_info['sha256'][:10]
    with fresh_output(out) as stage:
        snapshot(stage,recipe,inputs);(stage/'returned-original.bin').write_bytes(Path(returned).read_bytes())
        (stage/'return-recipe.json').write_bytes(spec_bytes)
        if request_snapshot is not None: ap.write(stage/'request-snapshot.json',request_snapshot)
        for name,im in {'paint':paint,'patch':patch,'composite':composite,'visible-mask':visible,'coverage-mask':coverage,
                        'missing-paint':missing,'source':source,'alignment-reference':load_image('reference')}.items(): im.save(stage/(name+'.png'))
        ap.previews(stage,patch)
        mapping={'format':'ambiance-asset-source-mapping','version':1,'path_base':'project',
                 'reference':recipe['source'],'image':ap.identity(project,out/'patch.png',ap.decoded(stage/'patch.png')[1]),
                 'image_to_reference':info['export_to_source'],'registration':'Region return; typed region receipt owns the exact inputs.'}
        ap.write(stage/'source-mapping.json',mapping)
        # The original returned pixels per source pixel can be lower than the output grid.
        a,b,c,d,_,_=matrix;xx=a*a+b*b;yy=c*c+d*d;zz=a*c+b*d
        magnification=math.sqrt((xx+yy+math.hypot(xx-yy,2*zz))/2)
        actual_density=info['effective_density']/magnification
        report={**info,'ready':info['ready'] and not missing_pixels,'missing_paint_pixels':missing_pixels,
                'returned_density':actual_density,'meets_demand':info['meets_demand'] and actual_density+1e-9>=info['required_density'],
                'returned_sha256':edit_info['sha256'],'edit_to_source':ap.multiply(info['export_to_source'],matrix),'request_id':spec['request_id'],
                'issues':info['issues']+(['Required coverage contains transparent or missing returned paint.'] if missing_pixels else [])}
        if actual_density+1e-9<info['required_density']:
            report['issues'].append('Returned art is below required density despite its resampled output grid.');report['ready']=False
        ap.write(stage/'report.json',report)
        receipt=write_receipt(stage,'return',deps,{'production_image':'patch.png','compiler_geometry':{'cell_size':[sz[0]+4,sz[1]+4],'padding':2}})
        compiler={'version':1,'id':id,'input':{'frames':['patch.png'],'allow_opaque':True},
                  'registration':{'mode':'fixed','point':[sz[0]/2,sz[1]/2],'target':[.5,.5]},
                  'output':{'cell_size':[sz[0]+4,sz[1]+4],'columns':1,'padding':2},
                  'source_mapping':{'file':'source-mapping.json','sha256':ap.sha((stage/'source-mapping.json').read_bytes())},
                  'region_receipt':{'file':'region-receipt.json','sha256':ap.sha((stage/'region-receipt.json').read_bytes())}}
        ap.write(stage/'compiler.json',compiler)
        # Compiler recipe refers to the receipt, so it is intentionally outside that receipt's file hashes.
        verify(directory,project)
        if ap.sha(Path(returned).read_bytes())!=edit_info['sha256'] or Path(recipe_path).read_bytes()!=spec_bytes: raise ValueError('Return inputs changed during preparation')
    return {**inspect(project,out),'compiler_recipe':str(out/'compiler.json'),'source_mapping':str(out/'source-mapping.json')}


def validate_region_receipt(path, expected, source_paths, compiler=None):
    path=Path(path).resolve()
    if ap.sha(path.read_bytes())!=expected: raise ValueError('Region receipt changed')
    recipe,inputs,receipt=verify(path.parent)
    if receipt['kind']!='return': raise ValueError('Compiler needs a region return receipt')
    project=next(p for p in path.parents if (p/'ambiance-project.json').is_file())
    if [Path(p).resolve() for p in source_paths]!=[path.parent/receipt['production_image']]: raise ValueError('Region receipt must identify the exact compiler input')
    sz=read(path.parent/'report.json')['export_size']
    if compiler is not None:
        if compiler['output']!=dict(receipt['compiler_geometry'],columns=1) or compiler['registration']!={'mode':'fixed','point':[sz[0]/2,sz[1]/2],'target':[.5,.5]}:
            raise ValueError('Region compilation must preserve fixed geometry and density')
        ref=compiler.get('source_mapping',{})
        if ref.get('sha256')!=receipt['files']['source-mapping.json']: raise ValueError('Region compiler mapping differs')
    deps=[{'path':path,'sha256':expected,'role':'region_receipt'}]
    deps += [{'path':ap.project_file(path.parent,name),'sha256':digest,'role':'region_output'} for name,digest in receipt['files'].items()]
    deps += [{'path':ap.project_file(project,ref['file']),'sha256':ref['sha256'],'role':'region_input'} for ref in receipt['dependencies']]
    return {'dependencies':deps,'receipt':receipt}
