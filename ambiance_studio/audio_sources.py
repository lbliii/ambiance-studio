"""Immutable source preparation with original, decoder and conversion identities.

Source preparations are reusable inputs. They are not full mixes, approved sounds,
provider entitlements or a claim that PCM24 restores lossy-source information.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
import wave

from . import audio, audio_source_backend as backend_api
from .audio_source_formats import inspect_structure
from .file_identity import digest
from .record_contracts import seal, read_sealed

FORMAT = 'ambiance-audio-preparation'
LIMITS = ['Working PCM24 does not recover detail lost before retrieval.',
          'Source preparation does not establish audition, entitlement, a complete mix, loudness or true peak.',
          'Structural validation and a full decode cannot detect every corruption in codecs without checksums.',
          'Only integer PCM WAV, declared little-endian raw PCM, MP3 and single-audio-track AAC/ALAC MP4 are supported.']


def add_parsers(group):
    for action in ['source-inspect','source-prepare']:
        p = group.add_parser(action, help='Inspect or preserve and prepare a local audio source')
        p.add_argument('source', type=Path); p.add_argument('--backend', choices=['pcm','macos-afconvert'], required=True)
        p.add_argument('--raw-format', choices=['u8','s16le','s24le','s32le']); p.add_argument('--raw-rate', type=int); p.add_argument('--raw-channels', type=int)
        if action == 'source-prepare':
            p.add_argument('--source-sha256', required=True); p.add_argument('--preparation-id', required=True)
            p.add_argument('--provenance', type=Path)
    p = group.add_parser('source-check', help='Validate a preparation receipt and its exact source/working identities')
    p.add_argument('receipt', type=Path)


def _reference(project, path):
    path = Path(path).resolve()
    if not path.is_relative_to(project): raise ValueError('Audio sources and preparation references must remain inside the project')
    if not path.is_file(): raise ValueError('Missing audio source or dependency: '+str(path))
    return {'path':str(path.relative_to(project)), 'sha256':digest(path), 'bytes':path.stat().st_size}


def _sha(value):
    if not isinstance(value,str) or not re.fullmatch('[a-f0-9]{64}', value): raise ValueError('Expected a lowercase SHA-256 source identity')
    return value


def _raw(args):
    values = [args.raw_format, args.raw_rate, args.raw_channels]
    if not any(v is not None for v in values): return None
    if any(v is None for v in values): raise ValueError('Raw PCM needs --raw-format, --raw-rate and --raw-channels together')
    return dict(zip(['format','sample_rate','channels'],values))


def _pcm_bytes(path, info):
    with path.open('rb') as f:
        f.seek(info['data_offset']); left = info['frames'] * info['channels'] * (info['bits']//8)
        while left:
            part = f.read(min(left, 65536 * info['channels'] * (info['bits']//8)))
            if not part: raise ValueError('Truncated PCM payload during decode')
            left -= len(part); yield part


def _pcm_hash(path, info):
    h = hashlib.sha256()
    for block in _pcm_bytes(path,info): h.update(block)
    return h.hexdigest()


def _pcm_write(path, destination, info, bits=24):
    if bits != 24 or info['bits'] > 24: raise ValueError('pcm backend supports exact 8/16/24-bit expansion; use macos-afconvert for 32-bit quantization')
    with wave.open(str(destination),'wb') as out:
        out.setnchannels(info['channels']); out.setsampwidth(3); out.setframerate(info['sample_rate'])
        width = info['bits']//8
        for block in _pcm_bytes(path,info):
            if width == 3: encoded = block
            else:
                encoded = bytearray()
                for offset in range(0,len(block),width):
                    n = ((block[offset]-128) if width == 1 else int.from_bytes(block[offset:offset+width],'little',signed=True)) << (24-info['bits'])
                    encoded.extend(n.to_bytes(3,'little',signed=True))
            out.writeframesraw(encoded)


def _wrap_raw(source, destination, info):
    with wave.open(str(destination),'wb') as out:
        out.setnchannels(info['channels']); out.setsampwidth(info['bits']//8); out.setframerate(info['sample_rate'])
        for block in _pcm_bytes(source,info): out.writeframesraw(block)


def _inspect(path, backend, raw, temp):
    before = digest(path); info = inspect_structure(path,raw)
    if info.get('frames') is not None and info['frames'] > 3600*info['sample_rate']: raise ValueError('Source duration exceeds one hour')
    tool = backend_api.identity(backend)
    decoded = None
    if backend == 'macos-afconvert':
        native_path = path
        if info['container'] == 'raw':
            native_path = temp/'raw-wrapper.wav'; _wrap_raw(path,native_path,info)
        metadata = backend_api.probe(native_path)
        for key in ['sample_rate','channels','codec']:
            if info.get(key) is not None and info[key] != metadata[key]: raise ValueError('Container/decoder source format mismatch: '+key)
        if info['container'] == 'mp4' and metadata['codec'] not in ('aac','alac'): raise ValueError('MP4 source requires AAC or ALAC audio')
        # Integer output at original rate provides exact decoded counts and a reusable conversion input.
        decoded = temp/'decoded.wav'; result = backend_api.convert(native_path, decoded, metadata['sample_rate'], 32)
        if result['channels'] != metadata['channels']: raise ValueError('Decoder changed source channel layout')
        claimed = info.get('frames')
        if metadata.get('packet_table'): claimed = metadata['packet_table'].get('valid_frames', claimed)
        if claimed is not None and result['frames'] != claimed: raise ValueError('Decoded sample count differs from declared source frames')
        info.update(metadata); info['frames'] = result['frames']
        decoded_hash = _pcm_hash(decoded,result); decoded_bits = 32
    else:
        if info['codec'] != 'pcm_integer': raise ValueError('pcm backend cannot decode compressed audio; select macos-afconvert')
        decoded_hash = _pcm_hash(path,info); decoded_bits = info['bits']
        info.update(channel_layout='mono' if info['channels']==1 else 'stereo', layout_basis='PCM mono/stereo order retained')
    if info['frames'] <= 0 or info['frames'] > 3600 * info['sample_rate']: raise ValueError('Source must contain a positive duration of at most one hour')
    if digest(path) != before: raise ValueError('Original source changed during inspection')
    info['duration_seconds'] = info['frames']/info['sample_rate']
    info['decoded'] = {'complete':True,'frames':info['frames'],'sample_rate':info['sample_rate'],'channels':info['channels'],
                       'pcm_sha256':decoded_hash,'representation':f'signed-integer-{decoded_bits}-little-endian' if decoded_bits!=8 else 'unsigned-integer-8'}
    return info, tool, decoded


def inspect_source(project, source, backend, raw=None):
    project = Path(project).resolve(); source = audio.inside(project,str(source))
    reference = _reference(project,source)
    with tempfile.TemporaryDirectory(prefix='ambiance-source-inspect-') as folder:
        info, tool, _ = _inspect(source,backend,raw,Path(folder))
    if digest(source) != reference['sha256']: raise ValueError('Source changed during inspection')
    return {'ok':True,'source':reference,'format':info,'backend':tool,'raw_declaration':raw,'limits':LIMITS}


def _provenance(data):
    data = {} if data is None else data
    allowed = ['origin_kind','provider','generation','retrieval','terms_reference','entitlement','audition','prior_processing']
    audio.fields(data,allowed,'source provenance')
    if data.get('origin_kind','unknown') not in ['unknown','generated','recorded','imported','synthesized','prepared']: raise ValueError('Unsupported source origin_kind')
    for group, keys in [('generation',['request_id','output_id','candidate_id','model','route']),('retrieval',['requested_format','returned_format','retrieved_at'])]:
        if group in data: audio.fields(data[group],keys,group)
    # Records contain identifiers and terms references, never credentials or signed URLs.
    for value in _strings(data):
        if re.search(r'(?i)(bearer\s|api[_-]?key|x-amz-|signature=|[?&](token|key|sig)=)',value): raise ValueError('Provenance must not contain credentials or signed download URLs')
    return {'origin_kind':'unknown','provider':None,'generation':{},'retrieval':{},'terms_reference':None,
            'entitlement':'unknown','audition':'unknown','prior_processing':'unknown',**data}


def _strings(data):
    if isinstance(data,dict):
        for k,v in data.items(): yield str(k); yield from _strings(v)
    elif isinstance(data,list):
        for v in data: yield from _strings(v)
    elif isinstance(data,str): yield data


def prepare_source(project, source, backend, expected_sha256, preparation_id, raw=None, provenance=None):
    from .project import project_lock
    project = Path(project).resolve(); source = audio.inside(project,str(source))
    audio.identifier(preparation_id,'preparation id'); _sha(expected_sha256)
    origin = _reference(project,source)
    if origin['sha256'] != expected_sha256: raise ValueError('Original source hash changed; inspect and explicitly select its new identity')
    provenance = _provenance(provenance)
    parent = audio.inside(project,'audio/preparations'); destination = audio.inside(project,f'audio/preparations/{preparation_id}')
    if destination.exists(): raise ValueError('Preparation ID already exists; use a new immutable version')
    # Validate sources and run conversion in a disposable directory before project publication.
    with tempfile.TemporaryDirectory(prefix='ambiance-source-prepare-') as folder:
        temp = Path(folder); original = temp/'original.source'; shutil.copyfile(source,original)
        if digest(original) != expected_sha256: raise ValueError('Original changed during preservation')
        info, tool, decoded = _inspect(original,backend,raw,temp)
        working = temp/'working.wav'
        if backend == 'pcm':
            if info['sample_rate'] != 48000: raise ValueError('pcm backend does not resample; explicitly select macos-afconvert for 48 kHz preparation')
            _pcm_write(original,working,info)
        else: backend_api.convert(decoded,working,48000,24)
        output_info = inspect_structure(working)
        numerator = info['frames']*48000; denominator = info['sample_rate']
        # A non-integral rational duration must quantize to a sample boundary, never invent exactness.
        lower = numerator//denominator; upper = (numerator+denominator-1)//denominator
        if output_info['sample_rate']!=48000 or output_info['bits']!=24 or output_info['channels']!=info['channels'] or not lower<=output_info['frames']<=upper:
            raise ValueError('Working output changed channel layout or has unexpected resampled duration')
        if digest(source) != expected_sha256: raise ValueError('Original changed during preparation')
        def ref(name):
            p=temp/name
            return {'path':str((destination/name).relative_to(project)),'sha256':digest(p),'bytes':p.stat().st_size}
        recipe={'format':'ambiance-audio-source-recipe','schema_version':1,'backend':tool,'raw_declaration':raw,
                'target':{'sample_rate':48000,'bits':24,'channel_policy':'preserve'},
                'processing': ['decode at original rate to signed PCM32','resample once with Core Audio bats quality 127; quantize to PCM24'] if backend!='pcm' else ['exact integer PCM expansion to PCM24; no resampling'],
                'implementation':{p.name:digest(p) for p in [Path(__file__),Path(backend_api.__file__),Path(__file__).with_name('audio_source_formats.py')]}}
        audio.write_json(temp/'recipe.json',recipe)
        receipt=seal({'format':FORMAT,'schema_version':1,'id':preparation_id,'created_utc':datetime.now(timezone.utc).isoformat(),
                      'kind':'prepared-source','origin':origin,'original':ref('original.source'),'working':ref('working.wav'),'recipe':ref('recipe.json'),
                      'source_format':info,'working_format':output_info,'provenance':provenance,
                      'conversion':{'backend':tool,'resampled':info['sample_rate']!=48000,'source_frames':info['frames'],
                                    'target_frames':output_info['frames'],'ideal_target_frames':{'numerator':numerator,'denominator':denominator},
                                    'rounding':'backend sample boundary within floor/ceil of exact rational duration','working_pcm_sha256':_pcm_hash(working,output_info)},'limits':LIMITS})
        audio.write_json(temp/'receipt.json',receipt)
        with project_lock(project):
            if digest(source)!=expected_sha256: raise ValueError('Original changed before publication')
            if destination.exists(): raise ValueError('Preparation ID already exists')
            parent.mkdir(parents=True,exist_ok=True)
            with tempfile.TemporaryDirectory(prefix='.prepare-',dir=parent) as staged:
                stage=Path(staged)/'result'; stage.mkdir()
                for name in ['original.source','working.wav','recipe.json','receipt.json']: shutil.copyfile(temp/name,stage/name)
                # Recheck copied bytes before an atomic directory promotion.
                for item in [receipt['original'],receipt['working'],receipt['recipe']]:
                    if digest(stage/Path(item['path']).name)!=item['sha256']: raise ValueError('Staged preparation bytes changed')
                stage.rename(destination)
    return {'ok':True,'receipt':str(destination/'receipt.json'),'receipt_sha256':digest(destination/'receipt.json'),
            'preparation_id':preparation_id,'working':receipt['working'],'original':receipt['original'],'conversion':receipt['conversion'],'limits':LIMITS}


def validate_preparation(project, path):
    """Read-only revision adapter. Returns typed dependencies; never complete masters."""
    project=Path(project).resolve(); path=Path(path)
    path=audio.inside(project,str(path.relative_to(project)) if path.is_absolute() else str(path))
    receipt=read_sealed(path,FORMAT)
    audio.fields(receipt,['format','schema_version','id','created_utc','kind','origin','original','working','recipe','source_format','working_format','provenance','conversion','limits','payload_sha256'],'audio preparation')
    if receipt.get('kind')!='prepared-source': raise ValueError('Expected a prepared-source receipt')
    audio.identifier(receipt['id']); _provenance(receipt['provenance'])
    dependencies=[dict(_reference(project,path),section='sound-design',role='audio_preparation')]
    for key,role in [('origin','audio_source_origin'),('original','audio_source_original'),('working','audio_prepared_source'),('recipe','audio_preparation_recipe')]:
        item=receipt[key]; audio.fields(item,['path','sha256','bytes'],key); _sha(item['sha256'])
        actual=_reference(project,audio.inside(project,item['path']))
        if actual!=item: raise ValueError('Preparation dependency changed: '+key)
        dependencies.append(dict(actual,section='sound-design',role=role))
    recipe=audio.read_json(audio.inside(project,receipt['recipe']['path']))
    if recipe.get('format')!='ambiance-audio-source-recipe' or recipe.get('schema_version')!=1: raise ValueError('Unsupported source recipe')
    audio.fields(recipe,['format','schema_version','backend','raw_declaration','target','processing','implementation'],'source recipe')
    if recipe['target'] != {'sample_rate':48000,'bits':24,'channel_policy':'preserve'}: raise ValueError('Unsupported source recipe target')
    original=inspect_structure(audio.inside(project,receipt['original']['path']),recipe.get('raw_declaration'))
    source_format=receipt['source_format']; conversion=receipt['conversion']
    for key in ['container','codec','sample_rate','channels','frames','bits']:
        if original.get(key) is not None and original[key]!=source_format.get(key): raise ValueError('Source format receipt mismatch: '+key)
    frames=audio.integer(source_format['frames'],'source frames',1); rate=audio.integer(source_format['sample_rate'],'source sample rate',1)
    if conversion['source_frames']!=frames or conversion['ideal_target_frames']!={'numerator':frames*48000,'denominator':rate}: raise ValueError('Conversion sample clock mismatch')
    if conversion['resampled']!=(rate!=48000): raise ValueError('Conversion resampling claim mismatch')
    output=inspect_structure(audio.inside(project,receipt['working']['path']))
    if output!=receipt['working_format'] or output['sample_rate']!=48000 or output['bits']!=24: raise ValueError('Working PCM format changed')
    if receipt['origin']['sha256']!=receipt['original']['sha256']: raise ValueError('Preserved original identity differs from origin')
    if output['channels']!=receipt['source_format']['channels'] or receipt['conversion']['target_frames']!=output['frames']: raise ValueError('Preparation timing/layout receipt mismatch')
    if not frames*48000//rate <= output['frames'] <= (frames*48000+rate-1)//rate: raise ValueError('Conversion duration mismatch')
    if recipe['backend']!=receipt['conversion']['backend']: raise ValueError('Preparation backend identity mismatch')
    if _pcm_hash(audio.inside(project,receipt['working']['path']),output)!=receipt['conversion']['working_pcm_sha256']: raise ValueError('Working decoded PCM hash mismatch')
    return {'ok':True,'kind':'prepared-source','receipt':_reference(project,path),'dependencies':dependencies,'working':receipt['working'],
            'source_format':receipt['source_format'],'working_format':output,'limits':LIMITS}


def run(args, project):
    if args.action=='source-check': return validate_preparation(project,args.receipt)
    raw=_raw(args)
    if args.action=='source-inspect': return inspect_source(project,args.source,args.backend,raw)
    provenance=audio.read_json(audio.inside(project,str(args.provenance))) if args.provenance else None
    return prepare_source(project,args.source,args.backend,args.source_sha256,args.preparation_id,raw,provenance)
