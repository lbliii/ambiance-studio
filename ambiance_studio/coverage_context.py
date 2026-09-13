"""Exact production inputs and evidence subject identities.

These helpers retain the production plan, revision and project path authorities;
no readiness decisions or evidence writes belong here.
"""
from pathlib import Path
import hashlib

import studio
from . import production_plan as spec, project_references, revision_capture, scene_runtime
from .project import locations
from .errors import CommandError


class AssessmentUnavailable(ValueError):
    """A required input cannot currently be assessed (not a failed proof)."""


class AssessmentInputs:
    """Lazy, query-local inputs. Reading one component never loads all the others.

    Values use the existing native validators. A missing runtime, malformed
    component or stale pin is unknown; callers can still request independent
    components. No locks, directories, caches or reports are created. Reuse only
    within one assessment, then call finish() to detect concurrent edits.
    """

    COMPONENTS = {
        'configuration', 'revision', 'revision_dependencies', 'plan', 'plan_dependencies', 'scene', 'catalog',
        'views', 'asset_dependencies', 'inventory', 'evidence_index', 'pipeline',
    }

    def __init__(self, project, revision=None):
        self.project = Path(project).resolve()
        self.revision = revision
        self.values = {}
        self.components = {}
        self.files = {}
        self.dependencies = {}
        self._stack = []

    def track(self, path, component=None):
        """Record the first bytes seen, including absent inputs and symlink targets."""
        path = Path(path).absolute()
        # Validate containment without discarding the requested symlink identity.
        relative_file(self.project, path)
        owner = component or (self._stack[-1] if self._stack else 'evidence_index')
        key = str(path)
        if key not in self.files:
            self.files[key] = {**self._fingerprint(path), 'components': set()}
        self.files[key]['components'].add(owner)
        return self.files[key]

    @staticmethod
    def _fingerprint(path):
        try:
            return {'sha256': studio.digest(path), 'resolved': str(path.resolve())}
        except OSError as error:
            return {'sha256': None, 'resolved': str(path.resolve()), 'error': type(error).__name__}

    def read(self, path):
        before = self.track(path)
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != before['sha256']:
            raise AssessmentUnavailable('Input changed while reading: '+str(path))
        return scene_runtime.load_scene_json(raw)

    def track_references(self, value, component):
        """Watch declared file identities before a native validator consumes them."""
        if isinstance(value, list):
            for row in value: self.track_references(row, component)
        elif isinstance(value, dict):
            name = value.get('path', value.get('file'))
            if isinstance(name, str) and 'sha256' in value:
                self.track(studio.inside(self.project, name), component)
            for row in value.values(): self.track_references(row, component)

    def get(self, name):
        if name not in self.COMPONENTS: raise ValueError('Unknown assessment component: '+str(name))
        if self._stack:
            self.dependencies.setdefault(self._stack[-1], set()).add(name)
        if name not in self.components:
            self._stack.append(name)
            try:
                self.values[name] = self._load(name)
                self.components[name] = {'state': 'available'}
            except (OSError, ValueError, KeyError, TypeError, ImportError, CommandError) as error:
                self.values[name] = None
                self.components[name] = {'state': 'unknown', 'diagnostics': [str(error)],
                                         'code': getattr(error, 'code', 'input_unavailable')}
            finally:
                self._stack.pop()
        return self.values[name]

    def require(self, name):
        value = self.get(name)
        if self.components[name]['state'] != 'available':
            raise AssessmentUnavailable(name+': '+'; '.join(self.components[name]['diagnostics']))
        return value

    def path(self, name):
        if self.revision:
            manifest = self.require('revision')
            role = 'production_plan' if name == 'plan' else name
            selected = manifest['controls'].get(role)
            if not selected:
                raise AssessmentUnavailable('Revision has no captured '+role+'; legacy records are unchanged')
            path = studio.inside(self.project, selected)
            self.track(path, name)
            pin = next((r for r in manifest['dependencies'] if r['path'] == selected), None)
            if pin is None: raise ValueError('Captured control has no dependency pin: '+selected)
            spec.file_ref(self.project, {'path': selected, 'sha256': pin['sha256']})
            return path
        if name in ['scene', 'catalog']:
            conf = self.require('configuration')
            return studio.inside(self.project, conf[name])
        return studio.inside(self.project, {'plan': spec.PATH, 'inventory': 'plans/asset-inventory.json',
                                           'pipeline': 'pipeline.json'}[name])

    def _load(self, name):
        if name == 'configuration':
            value = self.read(self.project/'ambiance-project.json')
            locations(self.project, value)
            return value
        if name == 'revision':
            if not self.revision: return None
            self.track(revision_capture.manifest_path(self.project, self.revision))
            return revision_capture.load(self.project, self.revision)
        if name == 'revision_dependencies':
            manifest = self.require('revision')
            if manifest is None: return []
            refs = manifest['dependencies']
            self.track_references(refs, name)
            changed = project_references.changed(self.project, refs)
            if changed: raise AssessmentUnavailable('Captured revision dependencies changed: '+str(changed))
            return refs
        if name == 'plan':
            return spec.validate(self.project, self.read(self.path(name)), verify_sources=False)
        if name in ['scene', 'catalog']:
            value = self.read(self.path(name))
            spec.rows(value['layers' if name == 'scene' else 'assets'], name)
            return value
        if name in ['inventory', 'evidence_index']:
            path = self.project/'plans/asset-inventory.json' if name == 'evidence_index' else self.path(name)
            value = self.read(path)
            if not isinstance(value, dict) or value.get('version') != 1 or not isinstance(value.get('items'), list):
                raise ValueError('Expected inventory version 1 with items.')
            if name == 'evidence_index' and not isinstance(value.get('expectation_evidence', []), list):
                raise ValueError('Inventory expectation_evidence must be an array')
            return value
        if name == 'pipeline':
            value = self.read(self.path(name))
            if not isinstance(value, dict): raise ValueError('Expected a pipeline object')
            return studio.pipeline(self.project, {'pipeline': value})
        if name == 'views':
            scene, catalog = self.require('scene'), self.require('catalog')
            info = scene_runtime.scene_bridge('view-inspect', scene, catalog, {})
            return {id: {'view': {k: v for k, v in row.items() if k not in ['projection', 'view_sha256']},
                         'output': row['output'], 'view_sha256': row['view_sha256']}
                    for id, row in info['views'].items()}
        if name == 'plan_dependencies':
            plan = self.require('plan')
            refs = plan['sources'] + [r for relation in plan['relations'] for r in relation['dependencies']]
            refs += plan.get('migration', {}).get('originals', [])
            for ref in refs:
                self.track(studio.inside(self.project, ref['path']))
                spec.file_ref(self.project, {'path': ref['path'], 'sha256': ref['sha256']})
            return refs
        if name == 'asset_dependencies':
            from .assets import read_asset
            refs = []
            for asset in self.require('catalog')['assets']:
                self.track(studio.inside(self.project, asset['file']))
                read_asset(asset, self.project)
                refs.append({'path': asset['file'], 'sha256': asset['sha256']})
            return refs
        raise AssertionError(name)

    def finish(self, names=None):
        """Describe selected components and invalidate only their changed dependencies."""
        selected = set(self.components if names is None else names)
        for name in list(selected): self.get(name)
        while True:
            expanded = selected | {dep for name in selected for dep in self.dependencies.get(name, [])}
            if expanded == selected: break
            selected = expanded
        changed = []
        invalid = set()
        for path, before in sorted(self.files.items()):
            owners = before['components'] & selected
            if not owners: continue
            after = self._fingerprint(Path(path))
            if after != {k: v for k, v in before.items() if k != 'components'}:
                invalid.update(owners)
                changed.append({'path': path, 'before_sha256': before['sha256'], 'after_sha256': after['sha256'],
                                'components': sorted(owners), 'code': 'inputs_changed'})
        while True:
            expanded = invalid | {name for name in selected if self.dependencies.get(name, set()) & invalid}
            if expanded == invalid: break
            invalid = expanded
        components = {name: dict(self.components[name]) for name in sorted(selected)}
        for name in invalid:
            components[name] = {'state': 'unknown', 'code': 'inputs_changed', 'diagnostics': ['Input changed during assessment']}
        fingerprints = [{'path': path, **{k: v for k, v in row.items() if k != 'components'},
                         'components': sorted(row['components'] & selected)}
                        for path, row in sorted(self.files.items()) if row['components'] & selected]
        return {'components': components, 'changed_inputs': changed, 'input_files': fingerprints,
                'complete': all(row['state'] == 'available' for row in components.values())}


def context(project, revision=None):
    project = Path(project).resolve(); result = spec.load_context(project, revision)
    if revision:
        captured = revision_capture.render_context(project, revision)
        scene_path, catalog_path = captured['scene'], captured['catalog']
        result['revision_sha256'] = captured['manifest_sha256']
        result['inventory_path'] = studio.inside(project, revision_capture.load(project, revision)['controls']['inventory'])
    else:
        scene_path, catalog_path = locations(project)
        result['revision_sha256'] = None
        result['inventory_path'] = project/'plans/asset-inventory.json'
    scene_bytes, catalog_bytes = scene_path.read_bytes(), catalog_path.read_bytes()
    result.update(scene_path=scene_path, catalog_path=catalog_path,
                  scene=scene_runtime.load_scene_json(scene_bytes), catalog=scene_runtime.load_scene_json(catalog_bytes),
                  scene_sha256=hashlib.sha256(scene_bytes).hexdigest(), catalog_sha256=hashlib.sha256(catalog_bytes).hexdigest())
    info = scene_runtime.scene_bridge('view-inspect', result['scene'], result['catalog'], {})
    result['views'] = {id: {'view': {k: v for k, v in row.items() if k not in ['projection', 'view_sha256']},
                            'output': row['output'], 'view_sha256': row['view_sha256']}
                       for id, row in info['views'].items()}
    from .assets import read_asset
    result['asset_references'] = []
    for asset in result['catalog']['assets']:
        read_asset(asset, project)
        result['asset_references'].append({'path': asset['file'], 'sha256': asset['sha256']})
    return result


def subject(ctx, expectation, view):
    row = ctx['views'].get(view)
    if row is None: raise ValueError('Expected view is absent from scene: '+str(view))
    return {key: ctx[key] for key in ['plan_sha256', 'scene_sha256', 'catalog_sha256', 'revision', 'revision_sha256']} | {
        'expectation_id': expectation['id'], 'expectation_sha256': ctx['expectation_sha256'][expectation['id']],
        'view_id': view, 'view_sha256': row['view_sha256'],
        'dependencies': ctx['plan']['sources'] + [d for r in ctx['plan']['relations'] for d in r['dependencies']]}


def expectation(ctx, id):
    value = next((e for e in ctx['plan']['expectations'] if e['id'] == id), None)
    if value is None: raise ValueError('Unknown expectation: '+str(id))
    return value


def relative_file(project, path):
    return project_references.relative(Path(project).resolve(), path)


def pinned(project, path):
    path = Path(path).resolve()
    return {'path': relative_file(project, path), 'sha256': studio.digest(path)}
