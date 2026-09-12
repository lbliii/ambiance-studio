"""Project-contained file identities, grouped by production section and role.

Paths are resolved with studio's project containment rules. This contract is
separate from audio-relative paths and other artifact-specific reference shapes.
"""
from pathlib import Path

import studio


def relative(project, path):
    path = Path(path).resolve()
    if not path.is_relative_to(project.resolve()): raise ValueError(f'Path must stay inside the project: {path}')
    return path.relative_to(project.resolve()).as_posix()


def ref(project, path, section, role, expected=None):
    path = Path(path).resolve(); name = relative(project, path)
    if not path.is_file() or not path.stat().st_size: raise ValueError(f'Missing or empty {role}: {name}')
    result = {'path': name, 'sha256': studio.digest(path), 'bytes': path.stat().st_size,
              'section': section, 'role': role, 'path_base': 'project'}
    if expected is not None and result['sha256'] != expected: raise ValueError(f'Changed {role}: {name}')
    return result


def changed(project, refs):
    result = []
    for item in refs:
        path = studio.inside(project, item['path'])
        actual = studio.digest(path) if path.is_file() else None
        if actual != item['sha256'] or (path.is_file() and path.stat().st_size != item['bytes']):
            result.append({'path': item['path'], 'section': item['section'], 'role': item['role'],
                           'expected_sha256': item['sha256'], 'actual_sha256': actual})
    return result


def unique(refs):
    return list({(r['path'], r['section'], r['role']): r for r in refs}.values())
