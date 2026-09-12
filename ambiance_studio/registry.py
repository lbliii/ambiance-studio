"""Machine-local project addresses, shared by source checkouts and worktrees."""
from contextlib import contextmanager
import os
from pathlib import Path
import subprocess

import studio
from .record_contracts import identifier


def registry_path(value=None):
    return Path(value or os.environ.get('AMBIANCE_REGISTRY') or
                Path.home()/'.ambiance-studio/registry.json').expanduser().resolve()


@contextmanager
def registry_lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_suffix('.lock')
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError(f'Registry is locked: {lock}. Check for an active studio writer.')
    try:
        with os.fdopen(fd, 'w') as file:
            file.write(str(os.getpid()))
        yield
    finally:
        lock.unlink(missing_ok=True)


def read(path):
    if not path.exists():
        return {'version': 1, 'projects': {}}
    data = studio.read(path)
    if data.get('version') != 1 or not isinstance(data.get('projects'), dict):
        raise ValueError(f'Unsupported studio registry: {path}')
    for key, value in data['projects'].items():
        identifier(key)
        if not isinstance(value, str) or not Path(value).is_absolute():
            raise ValueError('Registered projects require absolute local paths')
    return data


def describe(project, alias=None):
    project = Path(project).resolve()
    result = {'id': alias or project.name, 'path': str(project), 'available': False}
    try:
        conf = studio.read(project/'ambiance-project.json')
        settings = studio.read(project/'project.json')
        if conf.get('version') != 1 or settings.get('version') != 1:
            raise ValueError('Unsupported project configuration')
        result.update(title=settings['title'], project_id=settings['id'], available=True)
    except (OSError, ValueError, KeyError, TypeError) as error:
        result.update(title=alias or project.name, error=str(error))
    return result


def register(path, project, alias=None, relocate=False):
    project = Path(project).resolve()
    info = describe(project, alias)
    if not info['available']:
        raise ValueError(f'Cannot register project: {info.get("error")}')
    alias = identifier(alias or info['project_id'])
    with registry_lock(path):
        data = read(path)
        old = data['projects'].get(alias)
        if old and Path(old).resolve() != project and not relocate:
            raise ValueError(f'Project ID {alias} already points to {old}; use --relocate explicitly')
        duplicates = [key for key, value in data['projects'].items()
                      if Path(value).resolve() == project and key != alias]
        if duplicates:
            raise ValueError(f'Project is already registered as {duplicates[0]}')
        data['projects'][alias] = str(project)
        studio.write(path, data)
    return {**describe(project, alias), 'registry': str(path)}


def project_roots(root):
    """Discover the main checkout without copying or registering its media."""
    roots = [Path(root)/'projects']
    try:
        result = subprocess.run(['git', '-C', str(root), 'rev-parse', '--git-common-dir'],
                                capture_output=True, text=True, timeout=3)
        if result.returncode == 0:
            common = Path(result.stdout.strip())
            if not common.is_absolute():
                common = Path(root)/common
            if common.resolve().name == '.git':
                roots.append(common.resolve().parent/'projects')
    except (OSError, subprocess.TimeoutExpired):
        pass
    return list(dict.fromkeys(p.resolve() for p in roots))


def projects(root, path, directory=None):
    registered = {} if directory is not None else read(path)['projects']
    result = [dict(describe(Path(value), key), registered=True)
              for key, value in registered.items()]
    seen = {item['path'] for item in result}
    ids = {item['id'] for item in result}
    for parent in ([Path(directory)] if directory is not None else project_roots(root)):
        for config in sorted(parent.glob('*/ambiance-project.json')):
            info = describe(config.parent)
            if info['path'] in seen:
                continue
            # Conflicting names stay visible, but cannot silently replace a registry ID.
            base = info.get('project_id', info['id'])
            info['id'] = base
            if base in ids:
                import hashlib
                info['id'] = base+'-'+hashlib.sha256(info['path'].encode()).hexdigest()[:8]
            identifier(info['id'])
            result.append(dict(info, registered=False))
            seen.add(info['path']); ids.add(info['id'])
    return sorted(result, key=lambda item: (item['title'].casefold(), item['id']))


def resolve(root, path, alias):
    matches = [item for item in projects(root, path) if item['id'] == alias]
    if not matches:
        raise ValueError(f'Unknown project {alias}; run ambiance project list or studio register PATH')
    if not matches[0]['available']:
        raise ValueError(f'Registered project is unavailable: {matches[0]["path"]}')
    return Path(matches[0]['path'])
