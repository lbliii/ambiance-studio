"""Typed sound identities and portable validation, independent of visual assets."""
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import tempfile

from . import audio, audio_sources
from .audio_source_formats import inspect_structure
from .file_identity import digest
from .record_contracts import read_sealed

VERSION = 'ambiance-audio-library-version'
CONFIG = 'ambiance-audio-library-config'
LIBRARY = 'ambiance-audio-library'
AUDITION = 'ambiance-audio-library-audition'
EVENT = 'ambiance-audio-library-event'
MATERIALIZATION = 'ambiance-audio-materialization'
KINDS = ['bed', 'event', 'music']
LIMITS = ['Library status records explicit operator observations; rendering an excerpt is not listening.',
          'No provider calls, source enhancement, loudness normalization or entitlement inference.',
          'Portable source use does not establish a finished mix or film approval.']


def now():
    return datetime.now(timezone.utc).isoformat()


def shape(value, required, optional=(), label='record'):
    audio.fields(value, list(required)+list(optional), label)
    missing = set(required)-set(value)
    if missing:
        raise ValueError(f'{label} missing fields: {", ".join(sorted(missing))}')


def text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(label+' must be nonempty text')
    return value


def timestamp(value):
    text(value, 'observed_utc')
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if dt.tzinfo is None or dt > datetime.now(timezone.utc):
            raise ValueError('Observation timestamp needs timezone and cannot be in the future')
    except (TypeError, ValueError) as e:
        raise ValueError('Invalid observation timestamp: '+value) from e
    return value


def reference(root, path):
    root = Path(root).resolve(); path = Path(path).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError('Missing or non-contained audio library dependency: '+str(path))
    return {'path': str(path.relative_to(root)), 'sha256': digest(path), 'bytes': path.stat().st_size}


def checked_ref(root, item):
    shape(item, ['path', 'sha256', 'bytes'], label='audio reference')
    audio_sources._sha(item['sha256']); audio.integer(item['bytes'], 'reference bytes', 1)
    path = audio.inside(Path(root), item['path'])
    if reference(root, path) != item:
        raise ValueError('Audio dependency changed: '+item['path'])
    return path


def metadata(data, frames=None):
    data = {} if data is None else data
    descriptions = ['role','family','material','intensity','tonal_character','distance','room_treatment',
                    'channel_behavior','pairing_notes','limitations']
    shape(data, [], descriptions+['loop','tail','measurements','suggested_gain_db'], 'audio metadata')
    for key in descriptions:
        if key in data: text(data[key], key)
    if 'suggested_gain_db' in data: audio.finite(data['suggested_gain_db'], 'suggested_gain_db')
    if 'loop' in data and 'tail' in data: raise ValueError('Choose loop or event tail metadata')
    if 'loop' in data:
        loop = data['loop']; shape(loop, ['start_frame','end_frame','closure_recipe'], label='loop')
        start = audio.integer(loop['start_frame'], 'loop start'); end = audio.integer(loop['end_frame'], 'loop end', 1)
        if start >= end or (frames is not None and end > frames): raise ValueError('Loop region exceeds source')
        text(loop['closure_recipe'], 'closure_recipe')
    if 'tail' in data:
        tail = data['tail']; shape(tail, ['tail_frames','silence_frames','notes'], label='tail')
        for key in ['tail_frames','silence_frames']:
            value = audio.integer(tail[key], key)
            if frames is not None and value > frames: raise ValueError('Tail metadata exceeds source')
        text(tail['notes'], 'tail notes')
    if 'measurements' in data:
        if not isinstance(data['measurements'], list): raise ValueError('measurements must be an array')
        for measurement in data['measurements']:
            shape(measurement, ['method','source_sha256','notes'], label='measurement')
            text(measurement['method'], 'measurement method'); text(measurement['notes'], 'measurement notes')
            audio_sources._sha(measurement['source_sha256'])
    return data


def validate_archived_preparation(root, files):
    """Reconstruct AUDIO-01's original namespace only in a disposable projection.

    The sealed prior receipt is copied verbatim. Read-only hard links (copy fallback)
    avoid redundant media I/O; no link is published in a library or destination.
    The existing validator remains the sole source-preparation evaluator.
    """
    prior_path = checked_ref(root, files['source_receipt'])
    prior = read_sealed(prior_path, audio_sources.FORMAT)
    local = {key: checked_ref(root, files[key]) for key in ['original','working','recipe']}
    with tempfile.TemporaryDirectory(prefix='ambiance-audio-validate-') as folder:
        temp = Path(folder).resolve()
        targets = {}
        for key in ['origin','original','working','recipe']:
            item = prior[key]
            source = local['original' if key == 'origin' else key]
            shape(item, ['path','sha256','bytes'], label='archived preparation reference')
            audio_sources._sha(item['sha256']); audio.integer(item['bytes'], 'archived bytes', 1)
            if item['sha256'] != digest(source) or item['bytes'] != source.stat().st_size:
                raise ValueError('Archived preparation differs from portable '+key)
            target = audio.inside(temp, item['path'])
            if target == temp: raise ValueError('Archived dependency cannot be the projection root')
            if target in targets and digest(targets[target]) != item['sha256']:
                raise ValueError('Conflicting archived preparation paths')
            if any(target != other and (target.is_relative_to(other) or other.is_relative_to(target)) for other in targets):
                raise ValueError('Conflicting archived file/directory paths')
            targets[target] = source
        # Resolve/check the complete namespace before creating any links or copies.
        for target, source in targets.items():
            target.parent.mkdir(parents=True, exist_ok=True)
            try: os.link(source, target)
            except OSError: shutil.copyfile(source, target)
        # Pick a private path which cannot collide with an archived dependency.
        receipt_dir = Path(tempfile.mkdtemp(prefix='receipt-', dir=temp))
        projected = receipt_dir/'receipt.json'; shutil.copyfile(prior_path, projected)
        audio_sources.validate_preparation(temp, projected)
    return prior


def validate_version(folder):
    folder = Path(folder).resolve(); path = audio.inside(folder, 'version.json')
    value = read_sealed(path, VERSION)
    shape(value, ['format','schema_version','library_id','asset_id','version','kind','created_utc','parent',
                  'files','source_format','working_format','provenance','metadata','limits','payload_sha256'], label='audio version')
    for key in ['library_id','asset_id','version']: audio.identifier(value[key], key)
    if value['kind'] not in KINDS: raise ValueError('Unsupported audio kind')
    files = value['files']; prepared = 'working' in files
    shape(files, ['original']+(['working','recipe','source_receipt'] if prepared else ['inspection']), label='version files')
    for item in files.values(): checked_ref(folder, item)
    if prepared:
        prior = validate_archived_preparation(folder, files)
        for key in ['source_format','working_format','provenance']:
            if prior[key] != value[key]: raise ValueError('Version differs from source preparation: '+key)
    else:
        inspection = audio.read_json(checked_ref(folder, files['inspection']))
        shape(inspection, ['ok','source','format','backend','raw_declaration','limits'], label='source inspection')
        if inspection['source']['sha256'] != files['original']['sha256'] or inspection['format'] != value['source_format']:
            raise ValueError('Candidate source inspection identity changed')
        info = inspect_structure(checked_ref(folder, files['original']), inspection['raw_declaration'])
        for key in ['container','codec','frames','channels','bits','sample_rate']:
            if info.get(key) is not None and info[key] != value['source_format'].get(key): raise ValueError('Candidate format changed')
        if value['working_format'] is not None: raise ValueError('Candidate cannot claim a working format')
    audio_sources._provenance(value['provenance'])
    info = value['working_format'] if prepared else value['source_format']
    metadata(value['metadata'], info['frames'])
    for measurement in value['metadata'].get('measurements', []):
        if measurement['source_sha256'] not in [item['sha256'] for item in files.values()]:
            raise ValueError('Measurement does not identify this version')
    parent = value['parent']
    if parent is not None:
        shape(parent, ['version','sha256'], label='parent version')
        audio.identifier(parent['version']); audio_sources._sha(parent['sha256'])
        if parent['version'] == value['version']: raise ValueError('Version cannot parent itself')
    return value
