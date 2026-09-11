"""Bounded, deterministic patch proposals. Correlation is not a probability."""
import copy
import math
from pathlib import Path
import time
from PIL import Image
import studio
from . import asset_motion as motion
from .edge_quality import fresh_output, pixels

BACKEND='pillow-patch-ncc-v1'


def plane(frame):
    # Hidden RGB cannot make a transparent feature look trackable.
    rgb=frame.convert('RGBa'); values=[]
    for r,g,b,a in pixels(rgb): values.append((.299*r+.587*g+.114*b,))
    return frame.width,frame.height,values


def patch(data, center, radius):
    width,height,values=data;x,y=map(round,center)
    if x-radius<0 or y-radius<0 or x+radius>=width or y+radius>=height:return None
    out=[]
    for dy in range(-radius,radius+1):
        for dx in range(-radius,radius+1):
            out.extend(values[(y+dy)*width+x+dx])
    return out


def match(source,target,point,guess,settings,weights=None):
    p=settings['patch_radius'];radius=settings['radius'];seed=patch(source,point,p)
    if seed is None:return {'ok':False,'reason':'patch_outside_cell'}
    weights=[1]*len(seed) if weights is None else weights
    mass=sum(weights)
    if mass<=0:return {'ok':False,'reason':'insufficient_texture'}
    # A region boundary excludes samples; it must not become trackable texture.
    mean=sum(v*w for v,w in zip(seed,weights))/mass
    centered=[v-mean for v in seed];energy=sum(v*v*w for v,w in zip(centered,weights))
    if energy/mass<16:return {'ok':False,'reason':'insufficient_texture'}
    candidates=[];gx,gy=map(round,guess)
    for y in range(gy-radius,gy+radius+1):
        for x in range(gx-radius,gx+radius+1):
            candidate=patch(target,[x,y],p)
            if candidate is None:continue
            avg=sum(v*w for v,w in zip(candidate,weights))/mass
            e=sum((v-avg)**2*w for v,w in zip(candidate,weights))
            score=sum(a*(b-avg)*w for a,b,w in zip(centered,candidate,weights))/math.sqrt(energy*e) if e>1e-9 else -1
            candidates.append((score,x,y))
    if not candidates:return {'ok':False,'reason':'no_search_overlap'}
    candidates.sort(reverse=True);best,x,y=candidates[0]
    competitors=[v for v,cx,cy in candidates if math.hypot(cx-x,cy-y)>2]
    margin=best-max(competitors) if competitors else 0
    reason='low_correlation' if best<settings['min_correlation'] else 'ambiguous_match' if margin<settings['min_margin'] else None
    return {'ok':reason is None,'reason':reason,'point':[x,y],'correlation':best,'margin':margin}


def weights_for(context,cel,point,radius):
    regions=context['study']['regions'];size=context['frames'][0].size
    stable=[r for r in regions.values() if r['mode']=='stable' and cel in r['cels']]
    if not stable:return None
    from .motion_proof import effective_mask
    from PIL import ImageChops
    mask=Image.new('L',size)
    for r in stable:mask=ImageChops.lighter(mask,effective_mask(context,r,cel))
    x,y=map(round,point)
    return [v/255 for v in pixels(mask.crop((x-radius,y-radius,x+radius+1,y+radius+1)))]


def track(context,file,out):
    started=time.monotonic();project=context['project'];out=Path(out).resolve();motion.relative(project,out)
    source_hash=studio.digest(file);s=copy.deepcopy(context['study']);settings=s['tracking'];count=len(context['frames'])
    # Bound work before decoding/search. No accidental minute-long 256x64 search.
    searches=sum(len(m['cels']) for m in s['landmarks'].values())*3
    budget=searches*(2*settings['radius']+1)**2*(2*settings['patch_radius']+1)**2
    if budget>80_000_000:raise ValueError('Tracking exceeds 80 million patch samples; narrow landmark cel intervals or search radii')
    if out.exists():
        report=studio.read(out/'report.json')
        if report.get('implementation_sha256')==studio.digest(Path(__file__)) and report.get('backend')==BACKEND and report.get('input_sha256')==source_hash and all(studio.digest(out/k)==v for k,v in report['outputs'].items()):return {**report['summary'],'cached':True}
        raise ValueError('Tracking output exists but differs')
    planes=[plane(f) for f in context['frames']];rows=[]
    for key,mark in s['landmarks'].items():
        ref=mark['reference_cel'];seed=motion.observation(context,mark,ref)
        if seed is None:
            rows.append({'landmark':key,'cel':ref,'state':'unresolved','reason':'select_visible_reference_patch'});continue
        weights=weights_for(context,ref,seed,settings['patch_radius'])
        for direction in [1,-1]:
            previous,previous_point=ref,seed
            for i in range(ref+direction,count if direction==1 else -1,direction):
                if i not in mark['cels']:previous=None;continue
                obs=mark['observations'][i]
                if obs is not None and (obs['state']=='rejected' or not obs['visible']):
                    previous=None;continue
                if obs is not None and obs['state']=='selected':
                    previous=i if obs['visible'] else None;previous_point=motion.mapped(context,i,obs['point']);continue
                direct=match(planes[ref],planes[i],seed,seed,settings,weights)
                neighbor=match(planes[previous],planes[i],previous_point,previous_point,settings,weights) if previous is not None else {'ok':False,'reason':'propagation_stopped'}
                backward=match(planes[i],planes[ref],direct['point'],seed,settings,weights) if direct['ok'] else {'ok':False,'reason':'reference_match_failed'}
                agreement=math.dist(direct['point'],neighbor['point']) if direct['ok'] and neighbor['ok'] else None
                reverse_error=math.dist(backward['point'],seed) if backward['ok'] else None
                good=all(x['ok'] for x in [direct,neighbor,backward]) and agreement<=settings['max_disagreement_px'] and reverse_error<=settings['max_disagreement_px']
                details={'reference':direct,'neighbor':neighbor,'backward':backward,'disagreement_px':agreement,'reverse_error_px':reverse_error}
                if good:
                    mark['observations'][i]={'point':motion.mapped(context,i,direct['point'],inverse=True),'visible':True,'origin':'tracked','state':'proposed','tracking':details}
                    previous,previous_point=i,direct['point']
                else:
                    # Never overwrite an explicit rejected/hidden observation or fabricate a coordinate.
                    if obs is None or obs['state']=='proposed':mark['observations'][i]=None
                    previous=None
                rows.append({'landmark':key,'cel':i,'state':'proposed' if good else 'unresolved','reason':None if good else next((x.get('reason') for x in [direct,neighbor,backward] if not x['ok']),'tracking_disagreement'),**details})
    motion.load(project,data=s)
    unresolved=[r for r in rows if r['state']=='unresolved'];proposed=sum(r['state']=='proposed' for r in rows)
    summary={'ok':not unresolved,'study':str(out/'study.json'),'report':str(out/'report.json'),'proposed':proposed,'unresolved_count':len(unresolved),'next':[{k:r[k] for k in ['landmark','cel','state','reason']} for r in unresolved[:5]],
             'elapsed_seconds':round(time.monotonic()-started,3),'backend':BACKEND,'selection_required':True}
    with fresh_output(out) as stage:
        (stage/'study.json').write_bytes(motion.encode(s))
        studio.write(stage/'report.json',{'version':1,'backend':BACKEND,'implementation_sha256':studio.digest(Path(__file__)),'input_sha256':source_hash,'observations':rows,'summary':summary,'outputs':{'study.json':studio.digest(stage/'study.json')},
              'limits':['Integer cell-pixel search; subpixel points remain available through manual edits.','Correlation is not calibrated visibility or confidence.','Repeated marks, occlusion and pose changes can remain unresolved; spot-check good proposals too.']})
        motion.load(project,file)
        if studio.digest(file)!=source_hash:raise ValueError('Study changed during tracking')
    return summary
