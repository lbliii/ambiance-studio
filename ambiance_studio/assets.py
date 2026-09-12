"""Inspect existing packs and render derivative proof artifacts; never alter source art."""
from .command_output import Output, add_output
import base64
import hashlib
import html
import io
import json
import math
from pathlib import Path
import tempfile
import studio

ROOT=Path(__file__).resolve().parents[1]


def add_library_parsers(sub):
    group=sub.add_parser('library',help='Find prepared assets and reference studies').add_subparsers(dest='action',required=True)
    q=group.add_parser('find');q.add_argument('query',nargs='?',default='');q.add_argument('--directory',type=Path)
    q=group.add_parser('inspect');q.add_argument('asset');q.add_argument('--catalog',type=Path)


def read_asset(asset,base):
    from PIL import Image
    path=studio.inside(base,asset['file'])
    if studio.digest(path)!=asset['sha256']:raise ValueError(f'Asset bytes changed: {asset["id"]}')
    image=Image.open(path).convert('RGBA');atlas=asset.get('atlas')
    dimensions=[asset.get('width'),asset.get('height')]
    if any(type(v) is not int or v<=0 for v in dimensions) or image.size!=tuple(dimensions):
        raise ValueError(f'Decoded image dimensions do not match asset metadata: {asset["id"]}')
    if atlas:
        cols,rows,cw,ch,count=(atlas[k] for k in ['columns','rows','cell_width','cell_height','frame_count'])
        if any(type(x) is not int or x<=0 for x in [cols,rows,cw,ch,count]) or count>cols*rows or image.size!=(cols*cw,rows*ch):raise ValueError('Invalid atlas geometry')
        frames=[image.crop((i%cols*cw,i//cols*ch,(i%cols+1)*cw,(i//cols+1)*ch)) for i in range(count)]
    else:frames=[image]
    return path,frames


def stats(frames):
    return {'cel_slots':len(frames),'distinct_decoded_cels':len({hashlib.sha256(f.tobytes()).digest() for f in frames}),
            'distinct_alpha_shapes':len({hashlib.sha256(f.getchannel('A').tobytes()).digest() for f in frames}),
            'limits':['Repeated holds are valid. Pixel uniqueness and alpha changes do not establish painted pose count or artistic quality.']}


def inspect_pack(pack):
    pack=Path(pack).resolve();report=studio.read(pack/'report.json');asset=studio.read(pack/'asset.json')
    if not isinstance(report.get('outputs'),dict) or not {'asset.json','recipe.json','atlas.png'}.issubset(report['outputs']):
        raise ValueError('Pack report needs hashed asset, recipe and atlas outputs')
    changed=[f for f,h in report['outputs'].items() if not studio.inside(pack,f).is_file() or studio.digest(studio.inside(pack,f))!=h]
    result={'ok':not changed,'asset':asset,'build':report,'changed_outputs':changed,
            'proofs':{f:str(pack/f) for f in ['contact-sheet.png','preview.gif'] if (pack/f).is_file()}}
    if not changed and asset.get('provenance',{}).get('region_receipt'):
        from .art_regions import validate_region_receipt
        ref=asset['provenance']['region_receipt'];recipe=studio.read(pack/'recipe.json')
        if ref!=recipe.get('region_receipt'): raise ValueError('Region recipe/provenance differ')
        spec=recipe['input'];paths=[(pack/f).resolve() for f in ([spec['sheet']] if 'sheet' in spec else spec['frames'])]
        validate_region_receipt(pack/ref['file'],ref['sha256'],paths,recipe)
        if asset['registration_mapping']['shared_scale']!=1: raise ValueError('Region pack changed the requested density')
    if not changed and asset.get('provenance',{}).get('preparation_receipt'):
        from .compound_preparation import validate_preparation_receipt
        ref=asset['provenance']['preparation_receipt'];recipe=studio.read(pack/'recipe.json')
        if ref!=recipe.get('preparation_receipt'): raise ValueError('Preparation recipe/provenance differ')
        spec=recipe['input'];paths=[(pack/f).resolve() for f in ([spec['sheet']] if 'sheet' in spec else spec['frames'])]
        validate_preparation_receipt(pack/ref['file'],ref['sha256'],paths,recipe)
    if not changed and asset.get('provenance',{}).get('motion_preparation'):
        from .asset_motion import validate_preparation, compiler_settings
        ref=asset['provenance']['motion_preparation'];recipe=studio.read(pack/'recipe.json')
        if ref!=recipe.get('motion_preparation'): raise ValueError('Motion recipe and asset provenance differ')
        spec=recipe['input'];paths=[(pack/f).resolve() for f in ([spec['sheet']] if 'sheet' in spec else spec['frames'])]
        verified=validate_preparation(pack/ref['file'],ref['sha256'],paths);compiler_settings(verified,recipe)
        baseline=verified['context']['asset'];g=verified['geometry']
        if any(asset[k]!=baseline[k] for k in ['width','height','atlas','pivot']): raise ValueError('Motion pack changed baseline geometry')
        if asset['sockets']!=recipe.get('sockets',{}): raise ValueError('Motion pack socket policies differ')
        mapping=asset['registration_mapping']
        if mapping['shared_scale']!=g['scale'] or len(mapping['cels'])!=len(g['offsets']): raise ValueError('Motion pack mapping differs')
        for cel,original,offset in zip(mapping['cels'],baseline['registration_mapping']['cels'],g['offsets']):
            if cel['raw_cel_to_cell']!=[g['scale'],0,0,g['scale'],*offset] or any(cel[k]!=original[k] for k in ['index','source_index','source_rect','source_pivot']): raise ValueError('Motion pack cel mapping differs')
    if not changed and asset.get('provenance',{}).get('cel_trim'):
        from .cel_trim import validate
        ref=asset['provenance']['cel_trim'];recipe=studio.read(pack/'recipe.json')
        if ref!=recipe.get('cel_trim'):raise ValueError('Trim recipe/provenance differ')
        validate(pack/ref['file'],ref['sha256'],[(pack/f).resolve() for f in recipe['input']['frames']],recipe)
    if not changed:
        _,frames=read_asset(asset,pack);result['cel_analysis']=stats(frames)
    return result


def lookup(identifier,project=None,catalog=None):
    candidate=Path(identifier)
    if candidate.is_dir():
        pack=candidate.resolve();checked=inspect_pack(pack)
        if not checked['ok']:raise ValueError('Pack changed; inspect its report before proofing')
        return checked['asset'],pack,pack
    catalog=Path(catalog).resolve() if catalog else studio.inside(project,studio.read(Path(project)/'ambiance-project.json')['catalog']) if project else ROOT/'assets/catalog.json'
    data=studio.read(catalog)
    base=Path(project).resolve() if project and catalog.is_relative_to(Path(project).resolve()) else catalog.parent.parent
    asset=next((a for a in data['assets'] if a['id']==identifier),None)
    if asset is None:raise ValueError(f'Unknown asset {identifier} in {catalog}')
    recipe=asset.get('provenance',{}).get('recipe');pack=studio.inside(base,recipe).parent if recipe else None
    return asset,base,pack


def library(args,project=None):
    if args.action=='inspect':
        asset,base,pack=lookup(args.asset,project=project,catalog=args.catalog);path,frames=read_asset(asset,base)
        return {'ok':True,'asset':asset,'path':str(path),'cel_analysis':stats(frames),'prepared_pack':str(pack) if pack else None,
                'catalog_registration_is_artistic_approval':False}
    catalogs=[(ROOT/'assets/catalog.json',ROOT)]
    if project:
        conf=studio.read(Path(project)/'ambiance-project.json');catalogs.append((studio.inside(project,conf['catalog']),Path(project)))
    directory=Path(args.directory).resolve() if args.directory else ROOT/'projects'
    for conf_path in sorted(directory.glob('*/ambiance-project.json')):
        conf=studio.read(conf_path);catalogs.append((studio.inside(conf_path.parent,conf['catalog']),conf_path.parent))
    results=[];warnings=[]
    for catalog,base in dict.fromkeys(catalogs):
        if not catalog.is_file():continue
        data=studio.read(catalog)
        for asset in data['assets']:
            if args.query.casefold() not in json.dumps(asset,ensure_ascii=False).casefold():continue
            path=studio.inside(base,asset['file']);recipe=asset.get('provenance',{}).get('recipe')
            proof=studio.inside(base,recipe).parent/'contact-sheet.png' if recipe else None
            results.append({'id':asset['id'],'catalog':str(catalog),'file':str(path),'kind':asset.get('kind'),
                'frame_count':asset.get('atlas',{}).get('frame_count',1),'contact_sheet':str(proof) if proof and proof.is_file() else str(path),
                'origin':asset.get('origin') or {k:v for k,v in asset.get('provenance',{}).items() if k!='sources'},
                'source_count':len(asset.get('provenance',{}).get('sources',[])),
                'tags':asset.get('tags',[]),'integrity':path.is_file() and studio.digest(path)==asset.get('sha256'),
                'review':'Catalog availability; inspect the owning project review for acceptance.'})
    return {'ok':all(r['integrity'] for r in results),'matches':results,'warnings':warnings}


def proof(identifier,out,project=None,catalog=None,fps=6,width=180,landmark='anchor'):
    from PIL import Image, ImageDraw
    if not math.isfinite(fps) or not 0<fps<=60:raise ValueError('Proof fps must be in (0,60]')
    if type(width) is not int or not 16<=width<=640:raise ValueError('Proof width must be 16–640')
    if not landmark or not landmark.replace('-','').replace('_','').isalnum():raise ValueError('Use a simple landmark name')
    out=Path(out).resolve()
    if out.exists():raise ValueError('Proof destination exists; choose a fresh directory')
    asset,base,pack=lookup(identifier,project,catalog);source,frames=read_asset(asset,base)
    pivot=asset.get('pivot',[.5,.5]);cw,ch=frames[0].size
    # Keep tall source plates bounded while preserving ratio.
    scale=min(width/cw,360/ch);w,h=max(1,round(cw*scale)),max(1,round(ch*scale));cols=min(8,len(frames));rows=math.ceil(len(frames)/cols)
    contact=Image.new('RGB',(w*cols,(h+20)*rows*2),'#202432');draw=ImageDraw.Draw(contact)
    pngs=[];previews=[];onion=Image.new('RGBA',(cw,ch))
    for i,frame in enumerate(frames):
        small=frame.resize((w,h),Image.Resampling.LANCZOS)
        buf=io.BytesIO();frame.save(buf,format='PNG');pngs.append(base64.b64encode(buf.getvalue()).decode())
        for side,bg in enumerate(['#eee8dd','#202432']):
            tile=Image.new('RGBA',(w,h),bg);tile.alpha_composite(small)
            x,y=i%cols*w,(i//cols+side*rows)*(h+20);contact.paste(tile.convert('RGB'),(x,y))
            px,py=x+pivot[0]*w,y+pivot[1]*h
            draw.line((px-5,py,px+5,py),fill='#ed4995');draw.line((px,py-5,px,py+5),fill='#ed4995')
            draw.text((x+3,y+h+2),str(i),fill='#bd9064')
        previews.append(tile.convert('RGB'))
    # Evenly select up to eight cels so an atlas with many holds stays useful.
    for i in sorted({round(j*(len(frames)-1)/max(1,min(8,len(frames))-1)) for j in range(min(8,len(frames)))}):
        ghost=frames[i].copy();ghost.putalpha(ghost.getchannel('A').point(lambda a:round(a*.18)));onion.alpha_composite(ghost)
    od=ImageDraw.Draw(onion);px,py=pivot[0]*cw,pivot[1]*ch;od.line((px-8,py,px+8,py),fill='#ff3399',width=2);od.line((px,py-8,px,py+8),fill='#ff3399',width=2)
    originals=frames;points=[[pivot[0]*cw,pivot[1]*ch] for _ in frames];input_kind='prepared cels (export anchors for a new recipe using this atlas)'
    # Expose original ordered source frames when a compiler recipe is available.
    if pack and (pack/'recipe.json').is_file():
        checked=inspect_pack(pack)
        if not checked['ok']:raise ValueError('Pack outputs changed; cannot label its source frames as original')
        packed_asset=checked['asset']
        if any(asset.get(key)!=packed_asset.get(key) for key in ['id','sha256','width','height','atlas','pivot']):
            raise ValueError('Catalog asset differs from the prepared pack; cannot use its source registration')
        if asset.get('provenance',{}).get('sources')!=packed_asset.get('provenance',{}).get('sources'):
            raise ValueError('Catalog source provenance differs from the prepared pack')
        recipe=studio.read(pack/'recipe.json');spec=recipe['input'];input_kind='original recipe input frames'
        source_paths=[(pack/spec['sheet']).resolve()] if 'sheet' in spec else [(pack/f).resolve() for f in spec['frames']]
        refs=packed_asset.get('provenance',{}).get('sources',[])
        if not isinstance(refs,list) or not refs or len(refs)!=len(source_paths):
            raise ValueError('Recipe inputs need matching ordered source provenance')
        for source_path,ref in zip(source_paths,refs):
            if not isinstance(ref,dict) or 'file' not in ref or (pack/ref['file']).resolve()!=source_path:
                raise ValueError('Recipe input order/path differs from its recorded source provenance')
            if not source_path.is_file() or studio.digest(source_path)!=ref.get('sha256'):
                raise ValueError('Recipe source changed; cannot show it as original proof')
        registration_source=packed_asset.get('provenance',{}).get('registration_source')
        if registration_source:
            path=(pack/registration_source['file']).resolve()
            if not path.is_file() or studio.digest(path)!=registration_source.get('sha256'):
                raise ValueError('Registration source changed; cannot show it as original proof')
        if 'sheet' in spec:
            rawpath=(pack/spec['sheet']).resolve();raw=Image.open(rawpath).convert('RGBA');rw,rh=raw.width//spec['columns'],raw.height//spec['rows']
            originals=[raw.crop((i%spec['columns']*rw,i//spec['columns']*rh,(i%spec['columns']+1)*rw,(i//spec['columns']+1)*rh)) for i in range(spec['frame_count'])]
        else:originals=[Image.open((pack/f).resolve()).convert('RGBA') for f in spec['frames']]
        report=studio.read(pack/'report.json');points=[f['source_pivot'] for f in report['frames']]
        if len(points)!=len(originals) or len(originals)!=len(frames):raise ValueError('Recipe/report/prepared frame count differs')
        registration=recipe['registration'];mode=registration['mode']
        if mode=='fixed':expected=[registration['point'] for _ in originals]
        elif mode=='landmarks':expected=registration['points']
        elif mode=='bottom-center':
            expected=[];threshold=registration.get('alpha_threshold',20)
            for frame in originals:
                bounds=frame.getchannel('A').point(lambda a:255 if a>=threshold else 0).getbbox()
                if not bounds:raise ValueError('Original cel is empty at the recorded registration threshold')
                expected.append([(bounds[0]+bounds[2])/2,bounds[3]])
        else:raise ValueError('Unknown registration mode in the prepared recipe')
        if points!=expected:raise ValueError('Reported source pivots differ from the recorded preparation recipe')
    raw_pngs=[]
    for frame in originals:
        buf=io.BytesIO();frame.save(buf,format='PNG');raw_pngs.append(base64.b64encode(buf.getvalue()).decode())
    report={'ok':True,'asset_id':asset['id'],'source':str(source),'source_sha256':studio.digest(source),'cel_analysis':stats(frames),
        'pivot':pivot,'fps':fps,'landmark':landmark,'anchor_input':input_kind,
        'limits':['Proof timing is explicitly selected, not automatically the production scene cadence.','Inspect the in-scene render proof for actual placement and overlap.','Anchor edits download a new landmark file; they never edit the accepted pack.']}
    data=json.dumps({'prepared':pngs,'originals':raw_pngs,'points':points,'name':landmark,'fps':fps}).replace('</','<\\/')
    page='''<!doctype html><meta charset="utf-8"><title>Asset proof</title><style>body{background:#151a24;color:#eee;font:16px system-ui;max-width:1000px;margin:32px auto;padding:20px}canvas{max-width:340px;max-height:460px;background:#303747;border:1px solid #626a7b;cursor:crosshair}img{max-width:100%}button,input{margin:8px;padding:7px}section{display:flex;gap:24px;flex-wrap:wrap}</style><h1>'''+html.escape(asset['id'])+'''</h1><p>Playback, original-source anchor authoring, and registered onion skin. Click the source image to place the named anchor; export for a new recipe.</p><section><div><h2>Prepared playback</h2><canvas id="play"></canvas><p><button id="pause">Pause</button></p></div><div><h2>Source anchor</h2><canvas id="source"></canvas><p><input id="cel" type="range" min="0" value="0"><span id="index"></span></p><button id="download">Export named landmarks</button></div></section><p>'''+html.escape(input_kind)+'''</p><h2>Registered onion skin</h2><img src="onion-skin.png"><h2>All cels on light and dark</h2><img src="contact-sheet.png"><script>const D='''+data+''';let prepared=[],originals=[],playing=true,step=0;const play=document.querySelector('#play'),source=document.querySelector('#source'),slider=document.querySelector('#cel');function image(s){return new Promise(r=>{const i=new Image;i.onload=()=>r(i);i.src='data:image/png;base64,'+s})}function paint(c,i,p){c.width=i.width;c.height=i.height;const x=c.getContext('2d');x.drawImage(i,0,0);if(p){x.strokeStyle='#ff4f9e';x.lineWidth=2;x.beginPath();x.moveTo(p[0]-8,p[1]);x.lineTo(p[0]+8,p[1]);x.moveTo(p[0],p[1]-8);x.lineTo(p[0],p[1]+8);x.stroke()}}function edit(){const n=Number(slider.value);paint(source,originals[n],D.points[n]);document.querySelector('#index').textContent=n}Promise.all([Promise.all(D.prepared.map(image)),Promise.all(D.originals.map(image))]).then(a=>{[prepared,originals]=a;slider.max=originals.length-1;edit();paint(play,prepared[0]);setInterval(()=>{if(playing)paint(play,prepared[(++step)%prepared.length])},1000/D.fps)});slider.oninput=edit;source.onclick=e=>{const b=source.getBoundingClientRect();D.points[Number(slider.value)]=[(e.clientX-b.left)/b.width*source.width,(e.clientY-b.top)/b.height*source.height];edit()};document.querySelector('#pause').onclick=e=>{playing=!playing;e.target.textContent=playing?'Pause':'Play'};document.querySelector('#download').onclick=()=>{const b=new Blob([JSON.stringify({version:1,landmarks:{[D.name]:D.points}},null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='landmarks.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)};</script>'''
    out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.asset-proof-',dir=out.parent) as temp:
        stage=Path(temp)/'result';stage.mkdir();contact.save(stage/'contact-sheet.png');onion.save(stage/'onion-skin.png')
        previews[0].save(stage/'preview.gif',save_all=True,append_images=previews[1:],duration=max(1,round(1000/fps)),loop=0,disposal=2)
        (stage/'index.html').write_text(page)
        report['outputs']={f.name:studio.digest(f) for f in stage.iterdir()};studio.write(stage/'report.json',report)
        if out.exists():raise ValueError('Proof destination appeared; refusing replacement')
        stage.rename(out)
    return {**report,'directory':str(out),'html':str(out/'index.html')}


def add_preparation_parsers(group):
    q=group.add_parser('prepare',help='Build a source-coordinate separation workbench and reproducible parts')
    q.add_argument('source',type=Path,nargs='?');q.add_argument('target',type=Path,nargs='?');q.add_argument('--backing',type=Path)
    q.add_argument('--batch',type=Path);q.add_argument('--expect-sha256');q.add_argument('--context',type=Path)
    q.add_argument('--base');q.add_argument('--prefix');q.add_argument('--dry-run',action='store_true')
    q.add_argument('--long-edge',type=int,default=640);q.add_argument('--resume',action='store_true')
    q.add_argument('--recipe',type=Path);q.add_argument('--backing-to-source',type=float,nargs=6)
    add_output(q, Output.ARTIFACT, type=Path)
    q=group.add_parser('preflight',help='Decode transparency facts and make light/dark previews');q.add_argument('source',type=Path);add_output(q, Output.ARTIFACT, type=Path,required=True)
    q=group.add_parser('trim-cels');q.add_argument('layer');q.add_argument('--id',required=True);add_output(q, Output.ARTIFACT, type=Path,required=True)
    q=group.add_parser('crop',help='Export a mapped source crop into a fresh directory');q.add_argument('source',type=Path);q.add_argument('--recipe',type=Path,required=True);add_output(q, Output.ARTIFACT, type=Path,required=True)
    q=group.add_parser('return',help='Register a returned edit and blend into a source derivative');q.add_argument('edit',type=Path);q.add_argument('--mapping',type=Path,required=True);add_output(q, Output.ARTIFACT, type=Path,required=True)
    q=group.add_parser('edges',help='Inspect all isolated cels at explicit display size and magnified');q.add_argument('asset');add_output(q, Output.ARTIFACT, type=Path,required=True);q.add_argument('--catalog',type=Path);q.add_argument('--display-width',type=int,required=True);q.add_argument('--background',type=Path);q.add_argument('--context-rect',type=int,nargs=4,metavar=('X','Y','W','H'));q.add_argument('--fps',type=float,default=6);q.add_argument('--magnify',type=int,default=4)
    q=group.add_parser('edge-repair',help='Derive a fresh sprite sheet with explicit edge operations');q.add_argument('source',type=Path);q.add_argument('--recipe',type=Path,required=True);add_output(q, Output.ARTIFACT, type=Path,required=True)


def run_preparation(args,project):
    from . import asset_prep
    if args.action=='prepare':
        from . import preparation
        from . import preparation_commands
        return preparation_commands.run(args,project)
    if args.action=='preflight': return asset_prep.preflight(args.source,args.out)
    if args.action=='trim-cels':
        from .cel_trim import prepare
        return prepare(project,args.layer,args.id,args.out)
    if args.action=='crop': return asset_prep.crop(project,args.source,args.recipe,args.out)
    if args.action=='return': return asset_prep.return_edit(project,args.edit,args.mapping,args.out)
    if args.action in ['edges','edge-repair']:
        from . import edge_quality
        if args.action=='edge-repair': return edge_quality.edge_repair(args.source,args.recipe,args.out)
        return edge_quality.edges(args.asset,args.out,project,args.catalog,args.display_width,args.background,args.context_rect,args.fps,args.magnify)
    raise ValueError('Unsupported asset preparation operation')
