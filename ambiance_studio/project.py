"""Project configuration and writer coordination, independent of command parsing."""
from contextlib import contextmanager
import os
from pathlib import Path

import studio
from .errors import CommandError


def locations(project, config=None):
    project = Path(project).resolve()
    config = studio.read(project/'ambiance-project.json') if config is None else config
    if not isinstance(config, dict) or config.get('version') != 1:
        raise CommandError('Unsupported project configuration version')
    return studio.inside(project, config['scene']), studio.inside(project, config['catalog'])


@contextmanager
def project_lock(project):
    directory = Path(project)/'.ambiance'
    directory.mkdir(exist_ok=True)
    lock = directory/'write.lock'
    try:
        fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise CommandError(f'Project is locked: {lock}. Check for an active writer before removing a stale lock.',
                           'project_locked', 2) from None
    try:
        with os.fdopen(fd, 'w') as file:
            file.write(str(os.getpid()))
        yield
    finally:
        lock.unlink(missing_ok=True)
