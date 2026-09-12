"""Saved observations, regional diagnostics and same-clock candidate comparisons."""
import copy
import math
from pathlib import Path
import time
from PIL import Image, ImageChops, ImageDraw, ImageStat
import studio
from . import asset_motion as motion, assets
from .edge_quality import fresh_output, isolated_resize, pixels
from .scene_runtime import scene_bridge, require_node

FORMAT='ambiance-motion-proof'


def region_mask(context,region):
    size=context['frames'][0].size
    if 'mask' in region:
        with Image.open(motion.checked(context['project'],region['mask'])) as im:return im.copy()
    mask=Image.new('L',size);ImageDraw.Draw(mask).polygon([tuple(p) for p in region['points']],fill=255);return mask


def effective_mask(context,region,cel):
    mask=region_mask(context,region)
    if region['mode']=='ignore':return mask
    for ignored in context['study']['regions'].values():
        if ignored['mode']=='ignore' and cel in ignored['cels']:
            mask=ImageChops.multiply(mask,ImageChops.invert(region_mask(context,ignored)))
    return mask


def metrics(a,b,mask):
    weights=list(pixels(mask));mass=sum(weights)
    if mass==0:return {'available':False,'reason':'empty_region'}
    aa,ba=a.getchannel('A'),b.getchannel('A')
    weighted=lambda im,ws,denom:sum(sum(v*w for v,w in zip(pixels(ch),ws)) for ch in im.split())/denom/len(im.getbands())
    alpha=ImageChops.difference(aa,ba)
    premult=Image.merge('RGB',ImageChops.difference(a.convert('RGBa'),b.convert('RGBa')).split()[:3])
    overlap=[min(x,y)*w/255 for x,y,w in zip(pixels(aa),pixels(ba),weights)]
    union=sum(max(x,y)*w/255 for x,y,w in zip(pixels(aa),pixels(ba),weights));overlap_mass=sum(overlap)
    fraction=overlap_mass/union if union else 0
    color_available=overlap_mass>=255 and fraction>=.05
    color=weighted(ImageChops.difference(a.convert('RGB'),b.convert('RGB')),overlap,overlap_mass) if color_available else None
    def shape(alpha):
        values=[v*w/255 for v,w in zip(pixels(alpha),weights)];total=sum(values);width=alpha.width
        support=[i for i,v in enumerate(values) if v>0]
        bounds=[min(i%width for i in support),min(i//width for i in support),max(i%width for i in support)+1,max(i//width for i in support)+1] if support else None
        return {'coverage_fraction':total/mass,'alpha_centroid': [sum((i%width+.5)*v for i,v in enumerate(values))/total,sum((i//width+.5)*v for i,v in enumerate(values))/total] if total else None,
                'alpha_bounds':bounds}
    return {'available':True,'alpha_mean_abs':weighted(alpha,weights,mass),'premultiplied_rgb_mean_abs':weighted(premult,weights,mass),
            'overlap_color_mean_abs':color,'color_available':color_available,'color_unavailable_reason':None if color_available else 'insufficient_alpha_overlap',
            'alpha_overlap_fraction':fraction,'minimum_color_overlap_fraction':.05,'reference_shape':shape(aa),'cel_shape':shape(ba)}


def timeline(context):
    if context['timing']:
        timing=context['timing'];fps=timing['output_fps'];rows=[]
        for r in timing['layers'][0]['sampled']['segments']:
            rows.append({**r,'start':r['start_frame']/fps,'end':r['end_frame_exclusive']/fps})
        return {'fps':fps,'seconds':timing['picture_seconds'],'driver':timing['layers'][0]['timing_driver'],'segments':rows,'source':timing}
    fps=context['study']['view']['fps'];n=len(context['frames'])
    return {'fps':fps,'seconds':n/fps,'driver':'explicit_proof_cadence','segments':[{'start':i/fps,'end':(i+1)/fps,'cell':i,'render_eligible':True} for i in range(n)]}


def scene_candidate(context,candidate):
    binding=context['study']['view']['scene']
    if not binding:return None
    scene=studio.read(motion.checked(context['project'],binding['scene']));catalog=studio.read(motion.checked(context['project'],binding['catalog']))
    selected=next(l for l in scene['layers'] if l['id']==binding['layer'])
    issues=[];policies=context['study']['solve']['layer_socket_policies']
    if set(policies)!=set(selected.get('sockets',{})) or 'unresolved' in policies.values():issues.append('Declare fixed_mount or follow_art for every layer socket override')
    # Object-bound companion pixels require a future explicit shared correction recipe.
    finish=scene.get('finishing',{})
    grades=[finish.get('assets',{}).get(selected['asset'],{}),finish.get('layers',{}).get(selected['id'],{}),finish.get('groups',{}).get(selected.get('group'),{})]
    if any(g.get('mask_asset') for g in grades):issues.append('Object-bound grade mask needs an explicit shared correction; author a companion revision first')
    for effect in [*finish.get('shadows',[]),*finish.get('reflections',[])]:
        if effect['caster']==selected['id'] and effect.get('mask_asset'):issues.append(f'Effect {effect["id"]}: caster mask needs a shared correction')
    for light in finish.get('lights',[]):
        if light.get('anchor_layer')==selected['id']:issues.append(f'Light {light["id"]}: art-bound light rectangle needs an explicit correction binding')
    for effect in finish.get('illuminations', []):
        if effect['layer']==selected['id'] or (effect['receiver']==selected['id'] and effect.get('mask_asset')):
            issues.append(f'Illumination {effect["id"]}: receiver/contribution registration needs an explicit companion correction')
    if issues:return {'ok':False,'unresolved':issues}
    catalog=copy.deepcopy(catalog)
    existing=next((a for a in catalog['assets'] if a['id']==candidate['id']),None)
    if existing and existing!=candidate:raise ValueError('Candidate catalog ID collision')
    if not existing:catalog['assets'].append(candidate)
    values={'asset':candidate['id']}
    if selected.get('sockets'):values['sockets']=motion.sockets(selected['sockets'],policies,motion.solution(context)['translations_cell_px'],context['frames'][0].size)
    batch={'version':1,'operations':[{'op':'set','layer':binding['layer'],'values':values}]}
    if selected['asset'] in finish.get('assets',{}):
        finish=copy.deepcopy(finish);finish['assets'][candidate['id']]=copy.deepcopy(finish['assets'][selected['asset']])
        batch['operations'].append({'op':'finishing','value':finish})
    # Same evaluator and whole-scene validation used by scene apply. No second renderer.
    result=scene_bridge('apply',scene,catalog,{'batch':batch})
    return {'ok':True,'scene':result,'catalog':catalog,'batch':batch,'expected_scene_sha256':binding['expected_scene_sha256']}


def context_render(context,candidate,stage,seconds):
    proposal=scene_candidate(context,candidate)
    if proposal is None or not proposal['ok']:return proposal
    from .native_media import json_command
    scene=proposal['scene'];fps=scene['canvas']['fps'];duration=scene['canvas']['loop_seconds']
    frames=max(1,min(round(seconds*fps),round(duration*fps)));seconds=frames/fps
    width,height=scene['canvas']['width'],scene['canvas']['height']
    # Scene proof is at authored pixel dimensions. Bound volume rather than silently reduce scale.
    if width*height*frames*2>160_000_000:raise ValueError('Context proof exceeds 160 million pixels; shorten --context-seconds')
    studio.write(stage/'candidate.scene.json',scene);studio.write(stage/'candidate.catalog.json',proposal['catalog']);studio.write(stage/'adoption.json',proposal['batch'])
    binding=context['study']['view']['scene'];start=max(0,round(duration*fps)-frames//2)/fps
    sides=[]
    for side,scene_path,catalog_path in [('original',motion.checked(context['project'],binding['scene']),motion.checked(context['project'],binding['catalog'])),('candidate',stage/'candidate.scene.json',stage/'candidate.catalog.json')]:
        out=stage/f'scene-{side}'
        json_command([require_node(),str(motion.ROOT/'tools/render-scene.mjs')],{'project':str(context['project']),'scene_path':str(scene_path),'catalog_path':str(catalog_path),
            'out':str(out),'mode':'proof','width':width,'height':height,'start':start,'seconds':seconds,'disable':[],'supersample':1})
        sides.append([f'scene-{side}/current/{i:05d}.png' for i in range(frames)])
    return {'ok':True,'frames':sides,'width':width,'height':height,'fps':fps,'start':start,'seconds':seconds,'loop_seconds':duration,
            'adoption':'adoption.json','expected_scene_sha256':proposal['expected_scene_sha256'],
            'limits':['Context frames straddle the join using the original absolute scene clock.','Global grades and rendered shadows retain the shared renderer; unsupported object-bound masks/lights block context/adoption.']}


def verify(directory):
    directory=Path(directory).resolve();report=studio.read(directory/'report.json')
    if report.get('format')!=FORMAT or report.get('version')!=1:raise ValueError('Unsupported motion proof')
    for file,sha in report['outputs'].items():
        p=(directory/file).resolve()
        if not p.is_relative_to(directory) or studio.digest(p)!=sha:raise ValueError(f'Motion proof output changed: {file}')
    if not {'packet.json','index.html','workbench.mjs'}.issubset(report['outputs']):raise ValueError('Incomplete motion proof')
    return report


def proof(context,file,out,candidate=None,finding=None,region=None,offset=0,limit=5,context_seconds=3):
    started=time.monotonic();out=Path(out).resolve();project=context['project'];motion.relative(project,out)
    if type(offset) is not int or offset<0 or type(limit) is not int or not 1<=limit<=20:raise ValueError('Use offset >=0 and limit 1–20')
    motion.number(context_seconds,'context seconds',.01,30)
    study_hash=studio.digest(file);candidate_asset=None;after=None
    if candidate:
        candidate=Path(candidate).resolve();motion.relative(project,candidate);candidate_asset=motion.project_asset(project,candidate)
        ref=candidate_asset.get('provenance',{}).get('motion_preparation')
        if not ref:raise ValueError('Candidate requires typed motion preparation')
        verified=motion.validate_preparation(candidate/ref['file'],ref['sha256'])
        if verified['context']['study']!=context['study']:raise ValueError('Candidate belongs to another study')
        _,after=assets.read_asset(candidate_asset,project)
        if [x.tobytes() for x in after]!=[x.tobytes() for x in motion.raster(context)]:raise ValueError('Candidate raster differs from same-runtime source correction')
    if region and region not in context['study']['regions']:raise ValueError('Unknown region')
    request={'implementation':{name:studio.digest(motion.ROOT/name) for name in ['ambiance_studio/asset_motion.py','ambiance_studio/motion_proof.py','tools/asset_tool.py','editor/motion-workbench.html','editor/motion-workbench.mjs','editor/engine.mjs','editor/finishing.mjs','editor/bindings.mjs']},'study_sha256':study_hash,'candidate':motion.identity(project,candidate/'asset.json') if candidate else None,'context_seconds':context_seconds}
    if out.exists():
        report=verify(out)
        if report['request']!=request:raise ValueError('Proof directory belongs to different inputs/settings')
        return compact(out,studio.read(out/'packet.json'),finding,region,offset,limit,True)
    s=context['study'];frames=context['frames'];cw,ch=frames[0].size;w=s['view']['display_width'];h=max(1,round(ch*w/cw));sol=motion.solution(context)
    if sum(f.width*f.height for f in context['originals'])+(w*h*len(frames)*(2+len(s['regions'])))>100_000_000:raise ValueError('Observation packet exceeds 100 million pixels; lower display width or narrow regions')
    if cw*ch*sum(len(r['cels']) for r in s['regions'].values())*2>100_000_000:raise ValueError('Regional analysis exceeds 100 million cell pixels; narrow region cel intervals or split the study')
    clock=timeline(context);findings=[];regional=[]
    for i,row in enumerate(sol['unresolved']):findings.append({'id':f'constraint-{i}','type':'constraint',**row})
    for key,r in s['regions'].items():
        for i in r['cels']:
            mask=ImageChops.darker(effective_mask(context,r,i),effective_mask(context,r,r['reference_cel']))
            ref=r['reference_cel'];before=metrics(frames[ref],frames[i],mask);later=metrics(after[ref],after[i],mask) if after else None
            row={'region':key,'cel':i,'reference_cel':ref,'mode':r['mode'],'before':before,'after':later};regional.append(row)
            for state,m in [('before',before),('after',later)]:
                if m and m['available'] and r['mode']=='stable' and (m['alpha_mean_abs']>r['alpha_threshold'] or (m['color_available'] and m['overlap_color_mean_abs']>r['color_threshold'])):
                    findings.append({'id':f'region-{key}-{i}-{state}','type':'appearance','region':key,'cel':i,'state':state,'metrics':m,'next':'Inspect alpha/color and intended drawing changes; appearance does not infer a translation'})
    for row in findings:
        row['presentation_windows']=[{'start':r['start'],'end':r['end'],'render_eligible':r['render_eligible']} for r in clock['segments'] if r['cell']==row.get('cel')]
    pairwise=[];marks=list(s['landmarks'].items())
    for x,(left,a) in enumerate(marks):
        for right,b in marks[x+1:]:
            distances=[]
            for i in range(len(frames)):
                pa,pb=motion.observation(context,a,i),motion.observation(context,b,i)
                distances.append(math.dist(pa,pb)*w/cw if pa is not None and pb is not None else None)
            pairwise.append({'landmarks':[left,right],'distance_display_px':distances,'correction_preserves_distance':True})
    segments=clock['segments'];transitions=[]
    for index,b in enumerate(segments):
        if index==0 and not s['view']['wrap']:continue
        a=segments[index-1]
        transitions.append({'id':f'transition-{index}','from':a['cell'],'to':b['cell'],'time':b['start'],'seam':index==0,
            'before_hold':a['end']-a['start'],'after_hold':b['end']-b['start'],'render_eligible':a['render_eligible'] and b['render_eligible'],
            'neighborhood':[segments[(index+j)%len(segments)]['cell'] for j in [-2,-1,0,1]]})
    with fresh_output(out) as stage:
        views={};images={'original':[],'candidate':[],'raw':[]};(stage/'images').mkdir()
        def view(im,key,cel,transform,kind):
            target=f'images/{key}.png';im.save(stage/target);views[key]={'file':target,'cel':cel,'size':list(im.size),'view_to_source':transform,'kind':kind};return target
        from tools.asset_tool import invert_affine,multiply_affine
        for i,frame in enumerate(frames):
            inv=invert_affine(context['asset']['registration_mapping']['cels'][i]['raw_cel_to_cell'])
            small=isolated_resize(frame,(w,h));transform=multiply_affine(inv,[cw/w,0,0,ch/h,0,0])
            images['original'].append(view(small,f'prepared-{i}',i,transform,'prepared baseline cel'))
            images['raw'].append(view(context['originals'][i],f'raw-{i}',i,[1,0,0,1,0,0],'original compiler input cel'))
            if after:
                images['candidate'].append(view(isolated_resize(after[i],(w,h)),f'candidate-{i}',i,multiply_affine(inv,[cw/w,0,0,ch/h,-sol['translations_cell_px'][i][0],-sol['translations_cell_px'][i][1]]),'saved corrected cel'))
                ImageChops.difference(frame.convert('RGBa'),after[i].convert('RGBa')).convert('RGB').save(stage/f'images/difference-{i}.png')
            for key,r in s['regions'].items():
                box=region_mask(context,r).getbbox()
                if not box or i not in r['cels']:continue
                crop=frame.crop(box);cw2,ch2=crop.size;scale=min(4,512/max(cw2,ch2));size=(max(1,round(cw2*scale)),max(1,round(ch2*scale)))
                view(isolated_resize(crop,size),f'region-{key}-{i}',i,multiply_affine(inv,[cw2/size[0],0,0,ch2/size[1],box[0],box[1]]),'magnified baseline region')
        # Paginated contacts preserve actual display size, including all cels on both grounds.
        contact_paths=[];per_page=max(1,min(12,4096//w));cols=min(4,per_page)
        for start in range(0,len(frames),per_page):
            subset=frames[start:start+per_page];rows=math.ceil(len(subset)/cols);board=Image.new('RGB',(cols*w,rows*(h+24)*2),'#202432');d=ImageDraw.Draw(board)
            for j,frame in enumerate(subset):
                for side,bg in enumerate(['#eee8dd','#202432']):
                    tile=Image.new('RGBA',(w,h),bg);tile.alpha_composite(isolated_resize(frame,(w,h)));x=j%cols*w;y=(j//cols+side*rows)*(h+24)
                    board.paste(tile.convert('RGB'),(x,y));d.text((x+3,y+h+4),f'Cel {start+j}',fill='#d69a68')
            name=f'contact-{start//per_page}.png';board.save(stage/name);contact_paths.append(name)
        transition_paths=[]
        for n,tr in enumerate(transitions[:4]):
            board=Image.new('RGB',(w*4,(h+24)*(2 if after else 1)),'#202432');draw=ImageDraw.Draw(board)
            for side,sequence in enumerate([frames,after] if after else [frames]):
                for j,i in enumerate(tr['neighborhood']):
                    tile=Image.new('RGBA',(w,h),'#202432');tile.alpha_composite(isolated_resize(sequence[i],(w,h)));board.paste(tile.convert('RGB'),(j*w,side*(h+24)))
                    draw.text((j*w+3,side*(h+24)+h+3),f'{"Original" if side==0 else "Candidate"} cel {i}',fill='#d69a68')
            name=f'transition-{n}.png';board.save(stage/name);tr['strip']=name;transition_paths.append(name)
        context_result=context_render(context,candidate_asset,stage,context_seconds) if candidate_asset and s['view']['scene'] else None
        packet={'format':FORMAT,'version':1,'study':s,'study_file':motion.identity(project,file),'project':str(project),'candidate':request['candidate'],
            'cell_size':[cw,ch],'display_size':[w,h],'images':images,'views':views,'clock':clock,'solution':sol,'findings':findings,'regional':regional,'pairwise_landmarks':pairwise,'transitions':transitions,
            'controls':transitions[1:4],'transition_strips':transition_paths,'contacts':contact_paths,'scene':context_result,
            'limits':['Asset-local tolerances use the declared display width; they are not world contact measurements.','Regional alpha/color differences are advisory, not anatomical correspondence or artistic approval.','Inspection alignment is temporary and excluded from candidate builds.','Proof replay uses captured PNGs; draft editing additionally requires the pinned project inputs.']}
        studio.write(stage/'packet.json',packet)
        (stage/'workbench.mjs').write_bytes((motion.ROOT/'editor/motion-workbench.mjs').read_bytes())
        (stage/'index.html').write_bytes((motion.ROOT/'editor/motion-workbench.html').read_bytes())
        motion.load(project,file)
        if studio.digest(file)!=study_hash:raise ValueError('Study changed during proof')
        outputs={p.relative_to(stage).as_posix():studio.digest(p) for p in stage.rglob('*') if p.is_file()}
        studio.write(stage/'report.json',{'format':FORMAT,'version':1,'request':request,'outputs':outputs,'elapsed_seconds':round(time.monotonic()-started,3),'output_bytes':sum(p.stat().st_size for p in stage.rglob('*') if p.is_file())})
    return compact(out,packet,finding,region,offset,limit)


def compact(out,packet,finding=None,region=None,offset=0,limit=5,cached=False):
    findings=[r for r in packet['findings'] if (not finding or r['id']==finding) and (not region or r.get('region')==region)]
    if finding and not findings:raise ValueError('Unknown finding ID')
    next_rows=[]
    for row in findings[offset:offset+limit]:
        cel=row.get('cel',0);next_rows.append({**row,'view_id':f'prepared-{cel}','image':str(out/packet['images']['original'][cel])})
    binding=packet['study']['view']['scene']
    scene_current=bool(binding and studio.digest(motion.path(Path(packet['project']),binding['working_scene']))==binding['expected_scene_sha256'])
    scene=packet['scene'];ready=packet['solution']['ok'] and (scene is None or scene['ok'])
    return {'ok':not (scene and not scene['ok']),'directory':str(out),'packet':str(out/'packet.json'),'packet_sha256':studio.digest(out/'packet.json'),'proof':str(out/'index.html'),
        'cached':cached,'ready_to_solve':packet['solution']['ok'],'candidate_present':packet['candidate'] is not None,
        'scene_adoption_ready':bool(scene and ready and scene_current),'working_scene_matches_expected':scene_current,'scene_issues':scene.get('unresolved',[]) if scene else [],'finding_count':len(findings),'findings':next_rows,
        'next_offset':offset+limit if offset+limit<len(findings) else None,'transition_strips':[str(out/x) for x in packet['transition_strips']],'contacts':[str(out/x) for x in packet['contacts']],'timing_driver':packet['clock']['driver'],
        'adoption':{'batch':str(out/scene['adoption']),'expect_sha256':scene['expected_scene_sha256']} if scene and scene['ok'] else None}
