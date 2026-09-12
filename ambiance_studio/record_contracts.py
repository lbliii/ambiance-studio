"""Validation and seals for the studio's persisted JSON records.

The seal uses studio.encoded_hash verbatim, including its Unicode/NaN policy.
Version acceptance belongs to each caller. These helpers do not write files or
change the caller's atomic/immutable publication semantics.
"""
import re

import studio


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}', value):
        raise ValueError('Revision/edition ID needs 1–100 letters, numbers, dots, underscores or hyphens')
    return value


def fields(value, allowed, label):
    if not isinstance(value, dict) or set(value) - set(allowed):
        raise ValueError(f'Unsupported {label} fields; expected {", ".join(allowed)}')


def seal(data):
    data = dict(data); data['payload_sha256'] = studio.encoded_hash(data); return data


def read_sealed(path, kind, versions=(1,)):
    data = studio.read(path)
    if not isinstance(data, dict) or data.get('format') != kind or type(data.get('schema_version')) is not int or data['schema_version'] not in versions: raise ValueError(f'Unsupported {kind} contract: {path}')
    if data.get('payload_sha256') != studio.encoded_hash({k: v for k, v in data.items() if k != 'payload_sha256'}):
        raise ValueError(f'Manifest integrity changed: {path}')
    return data
