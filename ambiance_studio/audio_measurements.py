"""Identity-bound 48 kHz level measurements; no gain changes or acceptance verdicts."""
from pathlib import Path

from .audio_source_formats import inspect_structure
from .file_identity import digest
from .native_media import json_command
from .scene_runtime import require_node

METER = Path(__file__).resolve().parents[1] / 'tools/audio-measure.mjs'


def measure_file(path, expected_sha256=None, *, decoded_format=None):
    """Measure integer source WAV or internally declared presentation float PCM.

    The latter is exclusively the existing native verifier's timestamp-trimmed
    decode, not a second compressed-media decoder or a public raw-format guess.
    """
    path = Path(path).resolve()
    before = digest(path)
    if expected_sha256 is not None and before != expected_sha256:
        raise ValueError('Audio measurement source hash changed')
    info = dict(decoded_format) if decoded_format else inspect_structure(path)
    if info.get('sample_rate') != 48000 or info.get('channels') not in (1, 2):
        raise ValueError('Level measurement supports 48 kHz mono/stereo only; prepare an explicit derivative first')
    if info.get('codec') not in ('pcm_integer', 'pcm_float') or info.get('frames') is None:
        raise ValueError('Level measurement requires PCM WAV; compressed sources need explicit source preparation or media verify')
    if not 0 < info['frames'] <= 48000 * 3600:
        raise ValueError('Level measurement supports positive intervals up to one hour')
    if info['codec'] == 'pcm_float' and (info.get('bits') != 32 or info['frames']*info['channels']*4 != path.stat().st_size):
        raise ValueError('Incomplete presentation float PCM')
    method_hash = digest(METER)
    result = json_command([require_node(), METER], {'path': str(path), **info})
    if digest(path) != before or digest(METER) != method_hash:
        raise ValueError('Audio measurement input or implementation changed during measurement')
    return {'format': 'ambiance-audio-measurement', 'schema_version': 1, 'ok': True,
            'source': {'path': str(path), 'sha256': before, 'bytes': path.stat().st_size, 'format': info},
            'interval': {'start_sample': 0, 'frames': info['frames'], 'sample_rate': 48000,
                         'seconds': {'numerator': info['frames'], 'denominator': 48000}},
            **result, 'implementation': {'meter_sha256': method_hash, 'adapter_sha256': digest(Path(__file__))},
            'listening': {'status': 'unperformed'},
            'limits': ['No normalization or universal loudness target.',
                       'Numerical measurements do not establish listening comfort or artistic acceptance.',
                       'Integrated LUFS and 4x true peak only; no EBU Mode certification, LRA, surround or non-48 kHz metering.']}


def decoded_measurement(data, source, source_hash):
    """Attach audio facts without changing native verification/timing verdicts."""
    audio = data.get('audio', {})
    if not audio.get('tracks'):
        return
    path = audio.get('decoded_float')
    if not path or not audio.get('fully_decoded') or not audio.get('contiguous_presented_samples') or not audio.get('monotonic_timestamps'):
        audio['level_measurement'] = {'status': 'unavailable', 'reason': 'Complete contiguous float presentation decode unavailable'}
        return
    info = {'container': 'raw', 'codec': 'pcm_float', 'bits': 32, 'data_offset': 0,
            'frames': audio['presented_samples'], 'channels': audio['channels'], 'sample_rate': audio['sample_rate']}
    try:
        measured = measure_file(path, decoded_format=info)
    except ValueError as error:
        audio['level_measurement'] = {'status': 'unsupported', 'reason': str(error)}
        return
    measured['encoded_source'] = {'path': str(source), 'sha256': source_hash}
    measured['domain'] = 'Unclipped float32 audio decode within the native verified presentation interval; priming/padding outside it excluded'
    measured['encoded_source']['codec_fourcc'] = audio.get('source_codec_fourcc')
    measured['presentation'] = {k: audio.get(k) for k in ['presentation_method', 'presented_samples', 'raw_decoded_samples', 'first_decoded_pts', 'last_decoded_end', 'track_segments', 'presented_end_seconds']}
    peak = measured['true_peak']['dbtp']
    measured['provisional_headroom'] = {'ceiling_dbtp': -1.0, 'status': 'silent' if peak is None else 'within' if peak <= -1 else 'exceeds',
                                      'meaning': 'Provisional engineering headroom only; no automatic level adjustment or delivery approval'}
    audio['level_measurement'] = measured
