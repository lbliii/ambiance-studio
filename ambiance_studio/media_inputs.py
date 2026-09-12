"""Media-specific preflight: fresh output paths, input identity and exact PCM.

These path/identity rules deliberately retain rendering's original semantics;
they are not interchangeable with revision references or audio session paths.
"""
import io
from pathlib import Path
import wave

from .errors import CommandError
from .file_identity import digest


def fresh_output(path):
    path = Path(path).resolve()
    if path.exists():
        raise CommandError(f'Output already exists; choose a fresh directory: {path}')
    return path


def positive_integer(value, name):
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise CommandError(f'{name} must be a positive integer')
    return value


def input_identity(path, path_base='absolute'):
    path = Path(path).resolve()
    return {'resolved_path':str(path), 'path_base':path_base, 'bytes':path.stat().st_size, 'sha256':digest(path)}


def project_input(project, value):
    path = (project/value).resolve()
    if Path(value).is_absolute() or not path.is_relative_to(project) or not path.is_file():
        raise CommandError(f'Expected an existing project-relative input inside {project}: {value}')
    return path


def pcm_bytes(source, seconds):
    source = Path(source).resolve()
    data = source.read_bytes()
    try:
        with wave.open(io.BytesIO(data), 'rb') as file:
            if file.getcomptype() != 'NONE' or file.getnchannels() != 2 or file.getframerate() != 48000:
                raise CommandError('Selected audio must be stereo 48 kHz PCM WAV.')
            if abs(file.getnframes() - seconds*48000) > 1:
                raise CommandError('Selected PCM audio must exactly match the final repeated picture duration.')
            expected = file.getnframes()*file.getnchannels()*file.getsampwidth()
            if len(file.readframes(file.getnframes())) != expected:
                raise CommandError('Selected PCM WAV is truncated.')
    except (wave.Error, EOFError) as error:
        raise CommandError(f'Selected audio must be an existing PCM WAV, not pre-encoded AAC: {error}')
    return data
