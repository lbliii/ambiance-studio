"""Streaming file identity without loading production media into memory."""
from __future__ import annotations

import hashlib
from pathlib import Path


def digest(path: str | Path) -> str:
    checksum = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            checksum.update(chunk)
    return checksum.hexdigest()
