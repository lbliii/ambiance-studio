"""Strict local audio container checks before a decoder can conceal truncation.

This is structural validation, not a codec-quality or listening assessment.
Supported containers deliberately form a small subset of Core Audio's formats.
"""
import struct
from pathlib import Path

RAW_FORMATS = {'u8': 1, 's16le': 2, 's24le': 3, 's32le': 4}
MAX_BYTES = 2_000_000_000


def _layout(rate, channels):
    if type(rate) is not int or not 8000 <= rate <= 192000:
        raise ValueError('Source rate must be an integer from 8000 to 192000 Hz')
    if type(channels) is not int or channels not in (1, 2):
        raise ValueError('Only mono or stereo source layouts are supported')


def _wav(path, size):
    fmt = data = None
    with path.open('rb') as f:
        header = f.read(12)
        if struct.unpack('<I', header[4:8])[0] + 8 != size:
            raise ValueError('Truncated or inconsistent RIFF WAV length')
        offset = 12
        while offset < size:
            f.seek(offset); header = f.read(8)
            if len(header) != 8: raise ValueError('Truncated WAV chunk header')
            kind, length = struct.unpack('<4sI', header)
            end = offset + 8 + length
            if end > size: raise ValueError('Truncated WAV chunk payload')
            if kind == b'fmt ':
                if fmt is not None or length < 16 or length > 4096: raise ValueError('Invalid WAV format chunk')
                value = f.read(length)
                code, channels, rate, byte_rate, align, bits = struct.unpack('<HHIIHH', value[:16])
                if code == 65534:
                    if length < 40 or struct.unpack('<H', value[16:18])[0] != 22: raise ValueError('Malformed extensible WAV')
                    valid, mask = struct.unpack('<HI', value[18:24])
                    if valid != bits or mask not in ({0, 4} if channels == 1 else {0, 3}): raise ValueError('Unsupported WAV valid bits or channel layout')
                    if value[24:40] != bytes.fromhex('0100000000001000800000aa00389b71'): raise ValueError('Only integer PCM WAV is supported')
                    code = 1
                if code != 1 or bits not in (8, 16, 24, 32): raise ValueError('Only integer PCM WAV 8/16/24/32 is supported')
                _layout(rate, channels)
                if align != channels * (bits // 8) or byte_rate != rate * align: raise ValueError('Inconsistent PCM WAV format')
                fmt = {'container': 'wav', 'codec': 'pcm_integer', 'sample_rate': rate, 'channels': channels,
                       'bits': bits, 'bitrate_bps': byte_rate * 8, 'block_align': align}
            if kind == b'data':
                if data is not None: raise ValueError('Multiple WAV data chunks are unsupported')
                data = (offset + 8, length)
            offset = end + length % 2
            # Some existing encoders omit the final odd data pad; no payload is lost.
            if offset > size and end != size: raise ValueError('Truncated WAV padding')
    if not fmt or not data or not data[1] or data[1] % fmt['block_align']: raise ValueError('Missing or incomplete PCM sample frame')
    fmt.update(frames=data[1] // fmt.pop('block_align'), data_offset=data[0], data_bytes=data[1])
    return fmt


def _mp3(path, size):
    # Walk every MPEG Layer III frame rather than trusting a tolerant decoder's EOF.
    offset = 0; count = 0; first = None; declared_frames = None; rates = set(); channels_seen = set(); bitrates = set(); samples = 0
    with path.open('rb') as f:
        header = f.read(10)
        if header[:3] == b'ID3':
            if header[3] not in (2, 3, 4) or any(n & 128 for n in header[6:10]): raise ValueError('Malformed ID3 header')
            offset = 10 + sum(n << (7 * (3-i)) for i, n in enumerate(header[6:10]))
            if header[3] == 4 and header[5] & 16: offset += 10
            if offset > size: raise ValueError('Truncated ID3 payload')
        while offset < size:
            f.seek(offset); h = f.read(4)
            if size - offset == 128 and h[:3] == b'TAG': offset = size; break
            if len(h) < 4: raise ValueError('Truncated MPEG frame header')
            n = int.from_bytes(h, 'big'); version = (n >> 19) & 3; layer = (n >> 17) & 3
            bi, ri, pad = (n >> 12) & 15, (n >> 10) & 3, (n >> 9) & 1
            if n >> 21 != 2047 or version == 1 or layer != 1 or bi in (0, 15) or ri == 3: raise ValueError('Malformed or unsupported MPEG Layer III frame')
            rate = [44100, 48000, 32000][ri] // (1 if version == 3 else 2 if version == 2 else 4)
            kbps = ([0,32,40,48,56,64,80,96,112,128,160,192,224,256,320] if version == 3 else [0,8,16,24,32,40,48,56,64,80,96,112,128,144,160])[bi]
            length = (144000 if version == 3 else 72000) * kbps // rate + pad
            if offset + length > size: raise ValueError('Truncated MPEG frame payload')
            channels = 1 if (n >> 6) & 3 == 3 else 2
            rates.add(rate); channels_seen.add(channels); bitrates.add(kbps * 1000)
            if first is None:
                first = offset
                f.seek(offset); first_frame = f.read(length)
                side = (17 if channels == 1 else 32) if version == 3 else (9 if channels == 1 else 17)
                tag_offset = 4 + side + (0 if (n >> 16) & 1 else 2)
                if first_frame[tag_offset:tag_offset+4] in (b'Xing', b'Info'):
                    flags = int.from_bytes(first_frame[tag_offset+4:tag_offset+8], 'big')
                    if flags & 1: declared_frames = int.from_bytes(first_frame[tag_offset+8:tag_offset+12], 'big') + 1
                if first_frame[36:40] == b'VBRI': declared_frames = int.from_bytes(first_frame[50:54], 'big')
            count += 1; samples += 1152 if version == 3 else 576; offset += length
    if declared_frames is not None and count != declared_frames: raise ValueError('Truncated or inconsistent MP3 declared frame count')
    if not count or len(rates) != 1 or len(channels_seen) != 1: raise ValueError('Empty MP3 or changing stream rate/layout is unsupported')
    return {'container': 'mp3', 'codec': 'mp3', 'sample_rate': rates.pop(), 'channels': channels_seen.pop(),
            'bits': None, 'bitrate_bps': next(iter(bitrates)) if len(bitrates) == 1 else None,
            'mpeg_frames': count, 'coded_sample_frames': samples, 'frames': None, 'data_offset': first}


def _mp4(path, size):
    kinds = []
    with path.open('rb') as f:
        offset = 0
        while offset < size:
            f.seek(offset); h = f.read(8)
            if len(h) != 8: raise ValueError('Truncated ISO media box header')
            length, kind = struct.unpack('>I4s', h); header = 8
            if length == 1:
                b = f.read(8)
                if len(b) != 8: raise ValueError('Truncated ISO media extended length')
                length = int.from_bytes(b, 'big'); header = 16
            if length == 0: length = size - offset
            if length < header or offset + length > size: raise ValueError('Truncated or malformed ISO media box')
            kinds.append(kind); offset += length
    if not all(k in kinds for k in [b'ftyp', b'moov', b'mdat']): raise ValueError('Unsupported ISO audio container structure')
    return {'container': 'mp4', 'codec': None, 'frames': None}


def inspect_structure(path, raw=None):
    path = Path(path); size = path.stat().st_size
    if not 0 < size <= MAX_BYTES: raise ValueError('Source must contain 1 to 2000000000 bytes; long-file preparation is unsupported')
    with path.open('rb') as f: h = f.read(12)
    known = h[:4] == b'RIFF' and h[8:12] == b'WAVE' or h[:3] == b'ID3' or h[:2] in [b'\xff\xfb', b'\xff\xfa', b'\xff\xf3', b'\xff\xf2', b'\xff\xe3', b'\xff\xe2'] or h[4:8] == b'ftyp'
    if raw is not None:
        if known: raise ValueError('Raw PCM declarations cannot override an identified container')
        if set(raw) != {'format','sample_rate','channels'} or raw['format'] not in RAW_FORMATS: raise ValueError('Raw PCM requires declared format, sample_rate and channels')
        _layout(raw['sample_rate'], raw['channels']); width = RAW_FORMATS[raw['format']]
        if size % (width * raw['channels']): raise ValueError('Truncated raw PCM sample frame')
        return {'container':'raw','codec':'pcm_integer','sample_rate':raw['sample_rate'],'channels':raw['channels'],'bits':width*8,
                'frames':size//(width*raw['channels']),'data_offset':0,'data_bytes':size,'bitrate_bps':raw['sample_rate']*raw['channels']*width*8}
    if h[:4] == b'RIFF' and h[8:12] == b'WAVE': return _wav(path, size)
    if h[:3] == b'ID3' or h[:1] == b'\xff': return _mp3(path, size)
    if h[4:8] == b'ftyp': return _mp4(path, size)
    raise ValueError('Unsupported or malformed source; raw PCM requires an explicit format/rate/channel declaration')
