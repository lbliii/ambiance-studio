"""Current picture dependencies for legacy scene/assets folder watches.

This observes selected files; it does not render, re-lower models or establish
artistic readiness. Captured revision reviews have their own immutable scope.
"""
from pathlib import Path

import studio
from .project import locations
from .errors import CommandError


def selected_picture(project, gate):
    scopes = {'scene': 'scene', 'scene/scene.json': 'scene',
              'assets': 'assets', 'assets/catalog.json': 'assets'}
    watches = {scopes.get(Path(name).as_posix()) for name in gate['watch']}
    if not watches.intersection({'scene', 'assets'}):
        return {}, []
    configuration = project/'ambiance-project.json'
    if not configuration.exists() and not configuration.is_symlink():
        return {}, []
    snapshot, issues = {}, []

    def file(path, expected=None):
        relative = Path(path).relative_to(project).as_posix()
        path = studio.inside(project, relative)
        snapshot[relative] = studio.digest(path) if path.is_file() else None
        if snapshot[relative] is None:
            raise ValueError('Missing selected picture input: '+relative)
        if expected is not None and snapshot[relative] != expected:
            raise ValueError('Changed selected picture input: '+relative)

    try:
        studio.inside(project, 'ambiance-project.json')
        scene_path, catalog_path = locations(project)
        if 'scene' in watches:
            file(scene_path)
        file(catalog_path)
        scene, catalog = studio.read(scene_path), studio.read(catalog_path)
        if not isinstance(scene, dict) or not isinstance(catalog, dict):
            raise ValueError('Selected scene/catalog must be objects')
        for asset in catalog['assets']:
            file(project/asset['file'], asset.get('sha256'))
        # The existing package reader verifies its complete contained closure
        # without invoking the JS lowerer. Do not scan historical generations.
        from .model_instances import records, open_pin, dependencies
        seen = set()
        for record in records(scene):
            pin = record['pin']
            file(project/pin['package'], pin['sha256'])
            key = (pin['package'], pin['sha256'])
            if key in seen:
                continue
            package, manifest, _, _ = open_pin(project, pin)
            for item in dependencies(package, manifest):
                file(Path(item['file']), item['sha256'])
            seen.add(key)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, CommandError) as error:
        issues.append('Selected picture inputs unavailable: '+str(error))
    return snapshot, issues
