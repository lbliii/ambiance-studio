"""Explicit local PCM arrangement and evidence; no synthesis or loudness normalization.

The versioned session contract is documented in docs/AUDIO-SESSION.md. Standard
library PCM WAV support keeps the commands usable without a provider or NumPy.
"""
from array import array
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import sys
import tempfile
import uuid
import wave

from .file_identity import digest

FORMAT = 'ambiance-audio-session'
LIMITS = ['Measurements are not listening, phone-speaker review, or artistic approval.',
          'Peak values are sample peaks, not oversampled true peaks; RMS is not LUFS.',
          'PCM WAV only; matching sample rates required. No resampling, EQ, reverb synthesis, limiter, or automatic normalization.',
          'Circular tails wrap existing source audio; room processing must be supplied as an explicitly identified source.']


def capabilities():
    from .audio_source_backend import capabilities as source_capabilities
    return {'audio_arrangement': True, 'audio_pcm_wav': True,
            'audio_source_hashes': True, 'audio_comparisons': True,
            'audio_normalization': False, 'audio_true_peak': bool(shutil.which('node')),
            'audio_lufs': bool(shutil.which('node')), 'level_measurement_scope': '48 kHz mono/stereo; explicit audio measure only',
            'source_preparation': source_capabilities()}


def add_parsers(sub):
    group = sub.add_parser('audio', help='Inspect, arrange and compare explicit PCM audio sessions').add_subparsers(dest='action', required=True)
    from . import audio_cues
    audio_cues.add_parsers(group)
    from . import audio_sources
    audio_sources.add_parsers(group)
    from . import audio_library
    audio_library.add_parsers(group)
    from .command_output import Output, add_output
    p = group.add_parser('measure', help='Measure 48 kHz PCM LUFS, 4x true peak and mono compatibility without changing levels')
    p.add_argument('path', type=Path); p.add_argument('--source-sha256')
    add_output(p, Output.REPORT, type=Path)
    p = group.add_parser('inspect'); p.add_argument('session', type=Path)
    p = group.add_parser('import-stems', help='Create a new unity-gain session from an existing session stem list')
    p.add_argument('legacy_session', type=Path); p.add_argument('--session-id', required=True)
    for command in ['mix', 'compare']:
        p = group.add_parser(command); p.add_argument('session', type=Path)
        p.add_argument('--run-id'); p.add_argument('--start', type=float, default=0)
        p.add_argument('--duration', type=float)
        if command == 'mix':
            p.add_argument('--solo', action='append', default=[]); p.add_argument('--mute', action='append', default=[])
            p.add_argument('--gain', action='append', default=[], metavar='STEM=DB')
        else:
            p.add_argument('--variant-b', type=Path, required=True, help='JSON containing solo, mute and/or gain_db_by_stem')
    p = group.add_parser('check'); p.add_argument('path', type=Path)


def read_json(path):
    with open(path) as f: return json.load(f)


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def identifier(value, label='id'):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,99}', value):
        raise ValueError(f'{label} must use letters, digits, dot, underscore or hyphen (1–100 characters)')
    return value


def inside(project, value):
    if not isinstance(value, str): raise ValueError('Source path must be a project-relative string')
    relative = Path(value)
    path = (project / relative).resolve()
    if relative.is_absolute() or not path.is_relative_to(project.resolve()): raise ValueError(f'Path must remain inside the project: {value}')
    return path


def argument_path(project, value):
    p = Path(value)
    return p.resolve() if p.is_absolute() or p.exists() else (project / p).resolve()


def finite(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value): raise ValueError(f'{label} must be a finite number')
    return value


def integer(value, label, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum: raise ValueError(f'{label} must be an integer >= {minimum}')
    return value


def fields(obj, allowed, label):
    if not isinstance(obj, dict): raise ValueError(f'{label} must be an object')
    unknown = set(obj) - set(allowed)
    if unknown: raise ValueError(f'Unsupported {label} fields: {", ".join(sorted(unknown))}')


def wav_info(path):
    try:
        with wave.open(str(path), 'rb') as f:
            if f.getcomptype() != 'NONE' or f.getsampwidth() not in [1, 2, 3, 4] or f.getnchannels() not in [1, 2]:
                raise ValueError(f'Expected mono/stereo PCM integer WAV: {path}')
            info = {'sample_rate': f.getframerate(), 'channels': f.getnchannels(), 'frames': f.getnframes(), 'bits': f.getsampwidth() * 8}
            info['seconds'] = info['frames'] / info['sample_rate']
            if info['frames']:
                f.setpos(info['frames']-1)
                if len(f.readframes(1)) != info['channels']*(info['bits']//8): raise ValueError(f'Truncated WAV payload: {path}')
            return info
    except (wave.Error, EOFError) as e:
        raise ValueError(f'Cannot read PCM WAV {path}: {e}') from e


def read_wav(path, start=0, frames=None):
    info = wav_info(path)
    if start < 0 or start > info['frames']: raise ValueError('WAV region starts outside source')
    count = info['frames'] - start if frames is None else frames
    if count < 0 or start + count > info['frames']: raise ValueError('WAV region exceeds source')
    with wave.open(str(path), 'rb') as f:
        f.setpos(start); raw = f.readframes(count)
    width = info['bits'] // 8; channels = info['channels']
    if len(raw) != count * channels * width: raise ValueError(f'Truncated WAV payload: {path}')
    if width == 1: values = array('d', ((v - 128) / 128 for v in raw))
    elif width in [2, 4]:
        data = array('h' if width == 2 else 'i'); data.frombytes(raw)
        if sys.byteorder != 'little': data.byteswap()
        divisor = float(1 << (width * 8 - 1)); values = array('d', (v / divisor for v in data))
    else:
        values = array('d')
        for i in range(0, len(raw), 3):
            n = raw[i] | raw[i + 1] << 8 | raw[i + 2] << 16
            values.append((n - 0x1000000 if n & 0x800000 else n) / 8388608)
    if channels == 1: return values, values[:], info
    return values[0::2], values[1::2], info


def write_wav(path, left, right, rate):
    if len(left) != len(right): raise ValueError('Channel sample counts differ')
    # Never silently clip or restore a target loudness. The caller changes gain.
    with wave.open(str(path), 'wb') as f:
        f.setnchannels(2); f.setsampwidth(3); f.setframerate(rate)
        for start in range(0, len(left), 8192):
            out = bytearray()
            for l, r in zip(left[start:start + 8192], right[start:start + 8192]):
                for value in (l, r):
                    if not math.isfinite(value) or value < -1 or value > 8388607 / 8388608: raise ValueError('Mix would clip PCM24; lower an explicit gain and retry')
                    n = round(value * 8388608)
                    out.extend((n & 255, n >> 8 & 255, n >> 16 & 255))
            f.writeframesraw(out)


def load_session(project, path, *, session_data=None):
    session = read_json(path) if session_data is None else session_data
    fields(session, ['format', 'schema_version', 'id', 'sample_rate', 'frames', 'sources', 'stems', 'clips', 'master_gain_db', 'notes', 'imported_from', 'picture_events', 'picture_sync'], 'session')
    if session.get('format') != FORMAT or session.get('schema_version') != 1:
        raise ValueError('Expected ambiance-audio-session schema_version 1; use audio import-stems for a legacy session with rendered stems')
    identifier(session.get('id'), 'session id')
    integer(session.get('sample_rate'), 'sample_rate', 1); integer(session.get('frames'), 'frames', 1)
    finite(session.get('master_gain_db', 0), 'master_gain_db')
    source_map = {}; stem_map = {}; clip_ids = set(); infos = {}
    for source in session.get('sources', []):
        fields(source, ['id', 'path', 'sha256', 'origin', 'audition'], 'source')
        key = identifier(source.get('id'), 'source id')
        if key in source_map: raise ValueError(f'Duplicate source {key}')
        if not re.fullmatch('[a-f0-9]{64}', source.get('sha256', '')): raise ValueError(f'Source {key} requires sha256')
        source_map[key] = source
    for stem in session.get('stems', []):
        fields(stem, ['id', 'gain_db', 'role', 'notes'], 'stem')
        key = identifier(stem.get('id'), 'stem id')
        if key in stem_map: raise ValueError(f'Duplicate stem {key}')
        finite(stem.get('gain_db', 0), 'stem gain_db'); stem_map[key] = stem
    if not stem_map: raise ValueError('Session requires at least one stem')
    clips = session.get('clips', [])
    if not isinstance(clips, list): raise ValueError('clips must be an array')
    for clip in clips:
        fields(clip, ['id', 'source', 'stem', 'source_start_frame', 'frames', 'at_frame', 'repeat', 'every_frames', 'gain_db', 'fade_in_frames', 'fade_out_frames', 'circular_tail', 'pan', 'pan_points', 'picture_event', 'notes'], 'clip')
        key = identifier(clip.get('id'), 'clip id')
        if key in clip_ids: raise ValueError(f'Duplicate clip {key}')
        clip_ids.add(key)
        if clip.get('source') not in source_map: raise ValueError(f'Clip {key} references missing source')
        if clip.get('stem') not in stem_map: raise ValueError(f'Clip {key} references missing stem')
        integer(clip.get('source_start_frame', 0), 'source_start_frame'); integer(clip.get('frames'), 'clip frames', 1)
        integer(clip.get('at_frame'), 'at_frame'); integer(clip.get('repeat', 1), 'repeat', 1)
        integer(clip.get('every_frames', clip['frames']), 'every_frames', 1)
        if clip['at_frame'] >= session['frames']: raise ValueError(f'Clip {key} starts outside session')
        finite(clip.get('gain_db', 0), 'clip gain_db')
        for fade in ['fade_in_frames', 'fade_out_frames']:
            integer(clip.get(fade, 0), fade)
            if clip.get(fade, 0) > clip['frames']: raise ValueError(f'{fade} exceeds clip length')
        if 'circular_tail' in clip and not isinstance(clip['circular_tail'], bool): raise ValueError('circular_tail must be boolean')
        last_start = clip['at_frame'] + (clip.get('repeat', 1) - 1) * clip.get('every_frames', clip['frames'])
        if last_start >= session['frames']: raise ValueError(f'Repeated clip {key} starts outside session')
        if not clip.get('circular_tail', False) and last_start + clip['frames'] > session['frames']:
            raise ValueError(f'Clip {key} exceeds session; select source region or explicitly set circular_tail')
        if 'pan' in clip and 'pan_points' in clip: raise ValueError('Use pan or pan_points, not both')
        if 'pan' in clip and not -1 <= finite(clip['pan'], 'pan') <= 1: raise ValueError('pan must be between -1 and 1')
        if 'pan_points' in clip:
            pts = clip['pan_points']
            if not isinstance(pts, list) or len(pts) < 2: raise ValueError('pan_points requires at least two [clip_frame, pan] pairs')
            previous = -1
            for point in pts:
                if not isinstance(point, list) or len(point) != 2: raise ValueError('Invalid pan point')
                integer(point[0], 'pan point frame')
                if point[0] <= previous or not -1 <= finite(point[1], 'pan point') <= 1: raise ValueError('Pan frames must increase and values must be within -1..1')
                previous = point[0]
            if pts[0][0] != 0 or pts[-1][0] != clip['frames'] - 1: raise ValueError('Pan points must span first through last clip frame')
    # Hash every referenced source, including muted/solo-excluded stems. Selection never changes implicitly.
    for key in sorted({c['source'] for c in clips}):
        source = source_map[key]; source_path = inside(project, source['path'])
        if not source_path.is_file(): raise ValueError(f'Selected source missing: {key}: {source_path}')
        if digest(source_path) != source['sha256']: raise ValueError(f'Selected source changed: {key}; declare a new source version/hash deliberately')
        info = wav_info(source_path)
        if info['sample_rate'] != session['sample_rate']: raise ValueError(f'Sample rate mismatch for {key}; prepare and identify a resampled source explicitly')
        infos[key] = info
    for clip in clips:
        if clip.get('source_start_frame', 0) + clip['frames'] > infos[clip['source']]['frames']:
            raise ValueError(f'Clip {clip["id"]} region exceeds selected source')
    if 'picture_sync' in session:
        from .audio_cues import validate_sync
        validate_sync(session['picture_sync'], session)
    return session, infos


def db(value): return 20 * math.log10(value) if value > 0 else None


def levels(left, right, start=0, end=None):
    end = len(left) if end is None else min(end, len(left)); start = max(0, start)
    count = end - start
    if count <= 0: return {'frames': 0, 'rms_dbfs': None, 'mono_rms_dbfs': None, 'left_rms_dbfs': None, 'right_rms_dbfs': None}
    l2 = r2 = mono2 = 0.0; peak = 0.0; clipped = 0
    for i in range(start, end):
        l = left[i]; r = right[i]; l2 += l*l; r2 += r*r; mono2 += ((l+r)/2)**2
        peak = max(peak, abs(l), abs(r)); clipped += int(abs(l) >= 1) + int(abs(r) >= 1)
    rms = math.sqrt((l2+r2)/(2*count)); mono = math.sqrt(mono2/count)
    return {'frames': count, 'rms_dbfs': db(rms), 'mono_rms_dbfs': db(mono),
            'left_rms_dbfs': db(math.sqrt(l2/count)), 'right_rms_dbfs': db(math.sqrt(r2/count)),
            'sample_peak': peak, 'sample_peak_dbfs': db(peak), 'full_scale_samples': clipped,
            'mono_to_stereo_rms_db': db(mono/rms) if rms else None}


def measure(left, right, rate, windows=None):
    result = levels(left, right); result['sample_rate'] = rate; result['seconds'] = len(left)/rate
    result['rolling_1s'] = [dict(start_frame=i, **levels(left, right, i, i+rate)) for i in range(0, len(left), max(1, rate//2))]
    result['event_windows'] = [dict(w, **levels(left, right, w['start_frame'], w['end_frame'])) for w in windows or []]
    result['last_to_first_delta'] = max(abs(left[0]-left[-1]), abs(right[0]-right[-1])) if left else 0
    result['methods'] = {'peak': 'sample peak, no oversampling', 'level': 'unweighted RMS dBFS, not LUFS', 'mono': '(L+R)/2', 'rolling': 'one-second windows, half-second hop; last may be shorter', 'seam': 'adjacent last/first sample delta; not a listening pass'}
    return result


def validate_variant(session, variant):
    fields(variant, ['solo', 'mute', 'gain_db_by_stem'], 'comparison variant')
    known = {s['id'] for s in session['stems']}
    for name in ['solo', 'mute']:
        values = variant.get(name, [])
        if not isinstance(values, list) or any(not isinstance(v, str) for v in values): raise ValueError(f'{name} must be an array of stem IDs')
        if set(values)-known: raise ValueError(f'Unknown {name} stems: {sorted(set(values)-known)}')
    gains = variant.get('gain_db_by_stem', {})
    if not isinstance(gains, dict) or set(gains)-known: raise ValueError('gain_db_by_stem must map known stems to relative dB changes')
    for gain in gains.values(): finite(gain, 'variant gain')
    if set(variant.get('solo', [])) & set(variant.get('mute', [])): raise ValueError('A stem cannot be both soloed and muted')


def windows_for(session, excerpt_start, excerpt_frames):
    result = []
    for clip in session['clips']:
        for rep in range(clip.get('repeat', 1)):
            start = clip['at_frame'] + rep*clip.get('every_frames', clip['frames'])
            remaining = clip['frames']; offset = start
            part = 0
            while remaining:
                length = min(remaining, session['frames'] - offset)
                a = max(offset, excerpt_start); b = min(offset+length, excerpt_start+excerpt_frames)
                if b > a: result.append({'clip': clip['id'], 'stem': clip['stem'], 'repeat': rep, 'part': part, 'picture_event': clip.get('picture_event'), 'start_frame': a-excerpt_start, 'end_frame': b-excerpt_start})
                remaining -= length; offset = 0; part += 1
    return result


def amplitude(gain_db):
    try: value = 10**(gain_db/20)
    except OverflowError as e: raise ValueError('Gain is outside the supported numerical range') from e
    if not math.isfinite(value): raise ValueError('Gain is outside the supported numerical range')
    return value


def render_stem(project, session, stem, variant, excerpt_start, excerpt_frames):
    left = array('d', [0])*excerpt_frames; right = array('d', [0])*excerpt_frames
    key = stem['id']
    if key in variant.get('mute', []) or (variant.get('solo') and key not in variant['solo']): return left, right
    sources = {s['id']: s for s in session['sources']}
    gain = amplitude(session.get('master_gain_db', 0)+stem.get('gain_db', 0)+variant.get('gain_db_by_stem', {}).get(key, 0))
    for clip in (c for c in session['clips'] if c['stem'] == key):
        source = sources[clip['source']]; path = inside(project, source['path'])
        if digest(path) != source['sha256']: raise ValueError(f'Selected source changed during render: {source["id"]}')
        cgain = gain*amplitude(clip.get('gain_db', 0))
        points = clip.get('pan_points'); constant_pan = clip.get('pan')
        fade_in = clip.get('fade_in_frames', 0); fade_out = clip.get('fade_out_frames', 0)
        # Read only intersections with this proof. Source-relative envelopes and
        # automation keep their original time; an excerpt never restarts them.
        for rep in range(clip.get('repeat', 1)):
            offset = clip['at_frame']+rep*clip.get('every_frames', clip['frames'])
            source_offset = 0
            while source_offset < clip['frames']:
                length = min(clip['frames']-source_offset, session['frames']-offset)
                a = max(offset, excerpt_start); b = min(offset+length, excerpt_start+excerpt_frames)
                if b > a:
                    first = source_offset+a-offset
                    lsrc, rsrc, _ = read_wav(path, clip.get('source_start_frame', 0)+first, b-a)
                    cursor = 0
                    for local, (l, r) in enumerate(zip(lsrc, rsrc)):
                        i = first+local; envelope = 1.0; pan = constant_pan
                        if fade_in and i < fade_in: envelope *= i/max(1, fade_in-1)
                        if fade_out and i >= clip['frames']-fade_out: envelope *= (clip['frames']-1-i)/max(1, fade_out-1)
                        if points:
                            while cursor+1 < len(points)-1 and i > points[cursor+1][0]: cursor += 1
                            x, y = points[cursor:cursor+2]; t = (i-x[0])/(y[0]-x[0]); pan = x[1]+(y[1]-x[1])*t
                        if pan is not None:
                            mono = (l+r)*0.5; theta = (pan+1)*math.pi/4
                            l = mono*math.cos(theta); r = mono*math.sin(theta)
                        dest = a-excerpt_start+local
                        left[dest] += l*cgain*envelope; right[dest] += r*cgain*envelope
                source_offset += length; offset = 0
        if digest(path) != source['sha256']: raise ValueError(f'Selected source changed while reading: {source["id"]}')
    return left, right


def render_variant(project, session, variant, destination, start, frames):
    destination.mkdir()
    rate = session['sample_rate']; windows = windows_for(session, start, frames)
    master_l = array('d', [0])*frames; master_r = array('d', [0])*frames; stems = []
    for stem in session['stems']:
        left, right = render_stem(project, session, stem, variant, start, frames)
        metrics = measure(left, right, rate, windows)
        path = destination/f'stem-{stem["id"]}.wav'; write_wav(path, left, right, rate)
        stems.append({'id': stem['id'], 'path': path.name, 'sha256': digest(path), 'measurements': metrics})
        for i in range(frames): master_l[i] += left[i]; master_r[i] += right[i]
    measurements = measure(master_l, master_r, rate, windows)
    path = destination/'master.wav'; write_wav(path, master_l, master_r, rate)
    return {'variant': variant, 'master': {'path': path.name, 'sha256': digest(path), 'measurements': measurements}, 'stems': stems,
            'stem_reconstruction': 'All stems include master gain and variant settings; sum at unity within PCM24 rounding. No normalization or limiting.'}


def render_run(project, path, run_id=None, variants=None, start_seconds=0, duration_seconds=None):
    session_bytes = path.read_bytes(); source_hash = hashlib.sha256(session_bytes).hexdigest()
    session, infos = load_session(project, path)
    if digest(path) != source_hash: raise ValueError('Session changed during validation; retry using an immutable session version')
    rate = session['sample_rate']; finite(start_seconds, 'start')
    start = round(start_seconds*rate)
    if start_seconds < 0 or start >= session['frames']: raise ValueError('Excerpt start is outside session')
    if duration_seconds is not None:
        finite(duration_seconds, 'duration'); frames = round(duration_seconds*rate)
    else: frames = session['frames']-start
    if frames <= 0 or start+frames > session['frames']: raise ValueError('Excerpt duration must be positive and within the session')
    variants = variants or {'mix': {}}
    for name, variant in variants.items(): identifier(name, 'variant name'); validate_variant(session, variant)
    run_id = identifier(run_id or datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-')+uuid.uuid4().hex[:8], 'run id')
    base = project/'audio/runs'; base.mkdir(parents=True, exist_ok=True); final = base/run_id
    if final.exists(): raise ValueError(f'Audio run already exists; choose a new run ID: {final}')
    with tempfile.TemporaryDirectory(prefix='.render-', dir=base) as temp:
        work = Path(temp); (work/'session.json').write_bytes(session_bytes)
        outputs = {name: render_variant(project, session, variant, work/name, start, frames) for name, variant in variants.items()}
        if digest(path) != source_hash: raise ValueError('Session changed during render; no run was published')
        for source in session['sources']:
            if source['id'] in infos and digest(inside(project, source['path'])) != source['sha256']:
                raise ValueError(f'Selected source changed before publication: {source["id"]}')
        report = {'schema_version': 1, 'type': 'ambiance-audio-run', 'session_sha256': source_hash, 'source_session': str(path), 'source_info': infos,
                  'created_utc': datetime.now(timezone.utc).isoformat(),
                  'backend': {'name': 'python-stdlib-wave', 'python': sys.version.split()[0], 'module_sha256': digest(Path(__file__))},
                  'measurement_domain': 'floating-point mix before PCM24 quantization; audio check measures decoded PCM', 'sample_rate': rate, 'frames': frames,
                  'source_start_frame': start, 'pcm_bits': 24, 'variants': outputs, 'limits': LIMITS,
                  'listening': {'status': 'not-recorded', 'note': 'No listening observation is inferred from measurements.'}}
        write_json(work/'report.json', report)
        # Exclusive destination reservation prevents replacing a run, even with concurrent writers.
        final.mkdir()
        try:
            for child in work.iterdir(): shutil.move(str(child), final/child.name)
        except BaseException:
            shutil.rmtree(final); raise
    return {'ok': True, 'run': str(final.resolve()), 'report': str(final/'report.json'), **report}


def inspect_session(project, path):
    session, infos = load_session(project, path)
    selected = {c['source'] for c in session['clips']}
    sources = []
    for source in session['sources']:
        record = dict(source, selected=source['id'] in selected)
        if source['id'] in selected:
            left, right, info = read_wav(inside(project, source['path']))
            record['format'] = info; record['measurements'] = measure(left, right, info['sample_rate'])
        sources.append(record)
    return {'ok': True, 'session': str(path), 'session_sha256': digest(path), 'id': session['id'], 'frames': session['frames'],
            'sample_rate': session['sample_rate'], 'seconds': session['frames']/session['sample_rate'],
            'sources': sources, 'stems': session['stems'], 'timeline': session['clips'], 'limits': LIMITS}


def import_stems(project, path, session_id):
    identifier(session_id, 'session id'); original = read_json(path)
    sources = []; stems = []; clips = []; rate = frames = None
    for stem in original.get('stems', []):
        key = identifier(stem.get('id'), 'stem id')
        if key in {s['id'] for s in stems}: raise ValueError(f'Duplicate stem {key}')
        if stem.get('offset_samples', 0) != 0: raise ValueError('Legacy stem import requires offset_samples 0; use an explicit clip arrangement for offsets')
        source_path = inside(project, stem['path'])
        if not source_path.is_file(): raise ValueError(f'Selected rendered stem missing: {source_path}')
        info = wav_info(source_path)
        if rate is None: rate = info['sample_rate']; frames = info['frames']
        if info['sample_rate'] != rate or info['frames'] != frames: raise ValueError('Legacy stem import requires aligned rates and exact sample counts')
        sources.append({'id': key, 'path': stem['path'], 'sha256': digest(source_path), 'origin': f'Rendered stem from {path.name}; included processing remains baked into this explicitly selected source', 'audition': 'not-recorded by importer'})
        stems.append({'id': key, 'gain_db': 0})
        clips.append({'id': key, 'source': key, 'stem': key, 'at_frame': 0, 'source_start_frame': 0, 'frames': frames})
    if not stems: raise ValueError('Legacy session has no rendered stems')
    session = {'format': FORMAT, 'schema_version': 1, 'id': session_id, 'sample_rate': rate, 'frames': frames,
               'master_gain_db': 0, 'sources': sources, 'stems': stems, 'clips': clips,
               'imported_from': {'path': str(path), 'sha256': digest(path)},
               'notes': 'Explicit unity-gain stem arrangement for diagnosis. Existing stem processing/gain retained; source-level legacy processing is not reimplemented. No loudness normalization.'}
    folder = project/'audio/sessions'; folder.mkdir(parents=True, exist_ok=True); destination = folder/f'{session_id}.json'
    # Exclusive creation preserves earlier native and imported session versions.
    with destination.open('x') as f: json.dump(session, f, indent=2, allow_nan=False); f.write('\n')
    return {'ok': True, 'session': str(destination), 'sha256': digest(destination), 'source_session_unchanged': digest(path) == session['imported_from']['sha256'], 'stems': len(stems), 'frames': frames, 'sample_rate': rate, 'limits': LIMITS}


def check_audio(path):
    if path.is_file():
        left, right, info = read_wav(path); metrics = measure(left, right, info['sample_rate'])
        return {'ok': metrics['full_scale_samples'] == 0, 'file': str(path), 'sha256': digest(path), 'format': info, 'measurements': metrics, 'limits': LIMITS}
    report = read_json(path/'report.json')
    if report.get('type') != 'ambiance-audio-run' or report.get('schema_version') != 1: raise ValueError('Expected an audio run directory or PCM WAV file')
    errors = []; checked = {}
    if digest(path/'session.json') != report['session_sha256']: errors.append('Archived session hash mismatch')
    for name, variant in report['variants'].items():
        identifier(name); folder = path/name
        master_path = inside(folder, variant['master']['path'])
        if digest(master_path) != variant['master']['sha256']: errors.append(f'{name}: master hash mismatch')
        left, right, info = read_wav(master_path); frames = len(left)
        if frames != report['frames'] or info['sample_rate'] != report['sample_rate']: errors.append(f'{name}: master timing mismatch')
        metrics = measure(left, right, info['sample_rate'])
        sum_l = array('d', [0])*frames; sum_r = array('d', [0])*frames
        for stem in variant['stems']:
            source = inside(folder, stem['path'])
            if digest(source) != stem['sha256']: errors.append(f'{name}/{stem["id"]}: stem hash mismatch')
            sl, sr, si = read_wav(source)
            if len(sl) != frames or si['sample_rate'] != info['sample_rate']: errors.append(f'{name}/{stem["id"]}: stem timing mismatch'); continue
            for i in range(frames): sum_l[i] += sl[i]; sum_r[i] += sr[i]
        error = max((max(abs(a-b), abs(c-d)) for a,b,c,d in zip(left,sum_l,right,sum_r)), default=0)
        tolerance = (len(variant['stems'])+1)/8388608
        if error > tolerance: errors.append(f'{name}: stems do not reconstruct master')
        if metrics['full_scale_samples']: errors.append(f'{name}: full-scale samples require gain review')
        checked[name] = {'measurements': metrics, 'reconstruction_max_error': error, 'reconstruction_tolerance': tolerance}
    return {'ok': not errors, 'run': str(path), 'errors': errors, 'variants': checked, 'limits': LIMITS}


def run(args, project):
    if args.action == 'library':
        from . import audio_library
        return audio_library.run(args, project)
    project = Path(project).resolve(); action = args.action
    if action in ['source-inspect', 'source-prepare', 'source-check']:
        from . import audio_sources
        return audio_sources.run(args, project)
    if action in ['cue-bind', 'cue-check']:
        from . import audio_cues
        return audio_cues.bind(args, project) if action == 'cue-bind' else audio_cues.check(args, project)
    if action == 'check': return check_audio(argument_path(project, args.path))
    if action == 'measure':
        from .audio_measurements import measure_file
        source = argument_path(project, args.path)
        if args.out is not None and args.out.resolve() == source.resolve():
            raise ValueError('Audio measurement report cannot overwrite its source')
        return measure_file(source, args.source_sha256)
    if action == 'import-stems': return import_stems(project, argument_path(project, args.legacy_session), args.session_id)
    path = argument_path(project, args.session)
    if action == 'inspect': return inspect_session(project, path)
    if action == 'mix':
        gains = {}
        for value in args.gain:
            key, sep, gain = value.partition('=')
            if not sep: raise ValueError('Use --gain STEM=DB')
            if key in gains: raise ValueError(f'Duplicate gain override {key}')
            gains[key] = float(gain)
        variants = {'mix': {'solo': args.solo, 'mute': args.mute, 'gain_db_by_stem': gains}}
    elif action == 'compare': variants = {'A': {}, 'B': read_json(argument_path(project, args.variant_b))}
    else: raise ValueError('Unsupported audio command')
    return render_run(project, path, args.run_id, variants, args.start, args.duration)
