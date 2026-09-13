"""Explicit, bounded Apple Core Audio source decode/resampling adapter."""
import platform
import re
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

from .file_identity import digest
from .errors import CommandError
from .audio_source_formats import inspect_structure, _layout

AFINFO = Path('/usr/bin/afinfo')
AFCONVERT = Path('/usr/bin/afconvert')


def capabilities():
    return {'pcm': {'available': True, 'resampling': False},
            'macos-afconvert': {'available': platform.system() == 'Darwin' and AFINFO.is_file() and AFCONVERT.is_file(),
                               'decode_resample_tested': False, 'permission_context': 'Core Audio execution can fail in a sandbox; no fallback is selected'}}


def identity(backend):
    if backend == 'pcm':
        return {'id': 'pcm', 'version': 1, 'python': platform.python_version()}
    if backend != 'macos-afconvert': raise ValueError('Select backend pcm or macos-afconvert explicitly')
    if not capabilities()[backend]['available']: raise CommandError('macos-afconvert requires installed macOS afinfo and afconvert', 'missing_dependency', 3)
    # Tool file hashes plus the OS version identify the implementation behind Apple's 2.0 label.
    tools = []
    for path in [AFINFO, AFCONVERT]:
        help_result = subprocess.run([str(path), '-h'], capture_output=True, text=True, timeout=10)
        match = re.search(r'Version:\s*([^\n]+)', help_result.stdout + help_result.stderr)
        tools.append({'path': str(path), 'sha256': digest(path), 'version': match.group(1).strip() if match else None})
    return {'id': backend, 'adapter_version': 1, 'os': platform.platform(), 'macos_version': platform.mac_ver()[0],
            'tools': tools}


def execute(argv):
    from .run_control import execute as tracked_execute
    result = tracked_execute(list(map(str, argv)), None)
    if result.returncode:
        raise CommandError('Core Audio source operation failed: '+(result.stderr.strip() or result.stdout.strip())[:2000]+
                           '; no fallback or output was published', 'runtime_error', 3)
    return result.stdout


def probe(path):
    try:
        value = ET.fromstring(execute([AFINFO, '-x', '-r', path]))
    except ET.ParseError as error:
        raise ValueError('Core Audio returned malformed source metadata') from error
    for item in value.iter(): item.tag = item.tag.split('}')[-1]
    tracks = value.findall('.//track')
    if len(tracks) != 1: raise ValueError('Source must have exactly one audio track')
    track = tracks[0]
    rate = float(track.findtext('sample_rate', '0')); channels = int(track.findtext('num_channels', '0'))
    if rate != int(rate): raise ValueError('Non-integer source rate is unsupported')
    _layout(int(rate), channels)
    codec = track.findtext('format_type'); layout = track.findtext('channel_layout')
    # NA means no explicit speaker map: retain interleaved mono/stereo order.
    if layout not in ('NA', 'Mono', 'Stereo', 'kAudioChannelLayoutTag_Mono', 'kAudioChannelLayoutTag_Stereo'):
        raise ValueError('Unsupported explicit source channel layout: '+str(layout))
    if codec not in ('lpcm', '.mp3', 'aac ', 'aac', 'alac'): raise ValueError('Unsupported source codec: '+str(codec))
    packet = track.find('packet_table_info')
    duration = float(track.findtext('duration', '0'))
    if not 0 < duration <= 3600: raise ValueError('Source duration must be positive and at most one hour')
    info = {'codec': {'lpcm':'pcm_integer','.mp3':'mp3','aac ':'aac'}.get(codec,codec), 'sample_rate':int(rate),
            'channels':channels, 'channel_layout': 'mono' if channels == 1 else 'stereo',
            'layout_basis':'explicit' if layout != 'NA' else 'channel order retained; absent map interpreted as mono/stereo',
            'bits':(int(track.findtext('source_info/bit_depth','0')) or int(track.findtext('bit_depth','0')) or {1:16,2:20,3:24,4:32}.get(int(track.findtext('format_flags','0'),0))) if codec=='alac' else (int(track.findtext('bit_depth','0')) or None),
            'bitrate_bps':int(track.findtext('bit_rate','0')) or None,
            'packet_table':{e.tag:int(e.text) for e in packet} if packet is not None else None}
    return info


def convert(source, destination, rate, bits):
    # No channel-count/map/downmix, gain, normalization, priming overrides or dither flags.
    argv = [AFCONVERT, '-f', 'WAVE', '-d', f'LEI{bits}@{rate}', '-r', '127', '--src-complexity', 'bats', source, destination]
    execute(argv)
    actual = inspect_structure(destination)
    if actual['sample_rate'] != rate or actual['bits'] != bits: raise ValueError('Core Audio returned an unexpected working format')
    return actual
