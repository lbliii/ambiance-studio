"""Compilation inputs and complete source identity for the AVFoundation backend."""
import hashlib
import json
from pathlib import Path

from .file_identity import digest

SOURCE_DIRECTORY = Path(__file__).resolve().parents[1] / 'native/media'


def source_paths(directory=SOURCE_DIRECTORY):
    """Include all translation units and local headers, in stable filename order."""
    return sorted(path for path in Path(directory).iterdir() if path.suffix in {'.m', '.h'})


def compilation_sources(directory=SOURCE_DIRECTORY):
    return [path for path in source_paths(directory) if path.suffix == '.m']


def source_identity(directory=SOURCE_DIRECTORY):
    """Keep filenames in the digest so additions, removals and renames invalidate it."""
    files = {path.name: digest(path) for path in source_paths(directory)}
    encoded = json.dumps(files, sort_keys=True, separators=(',', ':')).encode()
    return {'files': files, 'sha256': hashlib.sha256(encoded).hexdigest()}
