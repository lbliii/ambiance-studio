"""One persistence boundary for every scene and look mutation.

Callers prepare and validate candidates while the project lock is held. This
service pins the exact inputs, rechecks them, and preserves the captured scene
bytes before an atomic replacement. Direct file writers do not take this lock.
"""
from contextlib import contextmanager
import json
from pathlib import Path
import shlex

import studio
from .errors import CommandError
from .project import locations, project_lock
from . import scene_authoring


class SceneTransaction:
    def __init__(self, project, expected=None):
        self.project = Path(project).resolve()
        config_bytes, config_ref = scene_authoring.read_input(self.project/'ambiance-project.json', 'project configuration')
        config = json.loads(config_bytes)
        scene_path, catalog_path = locations(self.project, config)
        self.previous_bytes, scene_ref = scene_authoring.read_input(self.project/config['scene'], 'scene')
        catalog_bytes, catalog_ref = scene_authoring.read_input(self.project/config['catalog'], 'catalog')
        self.inputs = [config_ref, scene_ref, catalog_ref]
        if scene_ref['file'] != str(scene_path) or catalog_ref['file'] != str(catalog_path):
            raise CommandError('Project paths changed while reading inputs; no edit was saved.', 'stale_input', 2)
        self.scene_path = scene_path
        self.previous_sha256 = scene_ref['sha256']
        if expected and expected != self.previous_sha256:
            raise CommandError('Scene changed since expected SHA-256; inspect and rebase the edit.', 'stale_input', 2)
        self.scene = json.loads(self.previous_bytes)
        self.catalog = json.loads(catalog_bytes)
        self.dependencies = []

    def read_json(self, path, role):
        raw, record = scene_authoring.read_input(path, role)
        self.dependencies.append(record)
        return json.loads(raw)

    def _verify_inputs(self):
        try:
            scene_authoring.verify_dependencies(self.project, self.inputs)
        except (OSError, ValueError) as error:
            raise CommandError('Project changed during validation; no edit was saved.', 'stale_input', 2) from error

    def finish(self, candidate, operation, *, dry_run=False, dependencies=(), details=None):
        dependencies = [*dependencies, *self.dependencies]
        try:
            scene_authoring.verify_dependencies(self.project, dependencies)
        except (OSError, ValueError):
            # Placement can also pin the catalog/configuration. Preserve the
            # stale_input classification when a project input was changed.
            self._verify_inputs()
            raise
        self._verify_inputs()
        details = details or {}
        if dry_run:
            return {'dry_run': True, 'previous_sha256': self.previous_sha256, 'scene': candidate,
                    'dependencies': dependencies, **details}
        history = self.project/'.ambiance/scene-history'
        history.mkdir(parents=True, exist_ok=True)
        backup = history/f'{self.previous_sha256}.json'
        if backup.exists():
            if backup.read_bytes() != self.previous_bytes:
                raise CommandError(f'Scene history snapshot has changed: {backup}')
        else:
            with backup.open('xb') as file:
                file.write(self.previous_bytes)
        studio.write(self.scene_path, candidate)
        return {'scene': str(self.scene_path), 'operation': operation,
                'previous_sha256': self.previous_sha256, 'sha256': studio.digest(self.scene_path),
                'restore_command': shlex.join(['ambiance', '--project', str(self.project),
                                              'scene', 'restore', self.previous_sha256]),
                'dependencies': dependencies, **details}


@contextmanager
def scene_transaction(project, expected=None):
    with project_lock(project):
        yield SceneTransaction(project, expected)
