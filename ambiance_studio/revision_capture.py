"""Publish immutable revision snapshots and verify their captured identities."""
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile

import studio
from .record_contracts import identifier, seal, read_sealed
from .project_references import relative, changed, unique
from .revision_dependencies import collect

FORMAT = 'ambiance-revision'


def capture(project, id, selection_path, dry_run=False, expected=None):
    from .project import project_lock
    identifier(id); selection_path = Path(selection_path).resolve(); destination = studio.inside(project, f'revisions/{id}')
    with project_lock(project):
        if destination.exists(): raise ValueError('Revision exists; choose a new ID')
        selection_bytes = selection_path.read_bytes(); selection = json.loads(selection_bytes)
        c = collect(project, selection)
        identities = unique(c.origins+c.refs)
        fingerprint = studio.encoded_hash({'selection': selection, 'inputs': identities})
        if expected and expected != fingerprint: raise ValueError('Selection inputs changed since dry run; capture was not saved')
        if changed(project, identities) or selection_path.read_bytes() != selection_bytes: raise ValueError('Inputs changed during revision capture')
        if dry_run: return {'ok': True, 'dry_run': True, 'id': id, 'selection_sha256': fingerprint, 'dependencies': identities,
                            'captured_documents': list(c.documents), 'destination': str(destination), 'path_base': 'project'}
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.capture-', dir=destination.parent) as temp:
            stage = Path(temp)/'revision'; (stage/'controls').mkdir(parents=True)
            refs = list(c.refs); controls = {}
            for name, doc in c.documents.items():
                target = stage/'controls'/name; target.write_bytes(doc['bytes'])
                name_in_project = relative(project, destination/'controls'/name)
                controls[doc['role']] = name_in_project
                refs.append({'path': name_in_project, 'sha256': studio.digest(target), 'bytes': target.stat().st_size,
                             'section': doc['section'], 'role': doc['role'], 'path_base': 'project'})
            manifest = seal({'format': FORMAT, 'schema_version': 1, 'id': id, 'created_utc': datetime.now(timezone.utc).isoformat(),
                'selection': selection, 'selection_sha256': fingerprint, 'origins': c.origins, 'controls': controls,
                'dependencies': unique(refs), 'masters': c.masters, 'sound_complete': sorted(c.sound_complete), 'notes': c.notes,
                'meaning': 'Captured inputs, not approval. Binary dependencies remain pinned to their project paths.'})
            studio.write(stage/'manifest.json', manifest)
            if changed(project, identities) or selection_path.read_bytes() != selection_bytes: raise ValueError('Inputs changed before revision publication')
            if destination.exists(): raise ValueError('Revision appeared during capture; no replacement')
            stage.rename(destination)
    return {'ok': True, 'id': id, 'manifest': str(destination/'manifest.json'), 'manifest_sha256': studio.digest(destination/'manifest.json'),
            'selection_sha256': fingerprint, 'dependencies': len(refs), 'review': 'not-recorded'}


def manifest_path(project, id):
    return studio.inside(project, f'revisions/{identifier(id)}/manifest.json')


def load(project, id):
    data = read_sealed(manifest_path(project, id), FORMAT)
    if data['id'] != id: raise ValueError('Revision ID does not match its directory')
    for item in data['dependencies']: studio.inside(project, item['path'])
    return data


def check(project, id):
    try:
        data = load(project, id); differences = changed(project, data['dependencies'])
        return {'ok': not differences, 'id': id, 'manifest_sha256': studio.digest(manifest_path(project, id)), 'changed': differences,
                'dependencies': len(data['dependencies']), 'notes': data['notes'], 'review_performed': False}
    except (OSError, ValueError, KeyError, TypeError) as error:
        return {'ok': False, 'id': id, 'errors': [str(error)], 'changed': []}


def compare(project, id):
    data = load(project, id)
    differences = changed(project, data['origins'])
    configuration = project/'ambiance-project.json'
    if configuration.exists():
        from .project import locations
        selected_scene, selected_catalog = locations(project)
        # This also covers historical manifests captured before the selector
        # became a typed origin. An invalid/missing current selection is an
        # error, not evidence that working state is unchanged.
        for role, selected in [('scene', selected_scene), ('catalog', selected_catalog)]:
            if not selected.is_file(): raise ValueError('Current configured '+role+' is missing: '+str(selected))
            current = relative(project, selected)
            previous = relative(project, studio.inside(project, data['selection'][role]))
            if current != previous:
                differences.append({'path': 'ambiance-project.json', 'section': 'animation' if role == 'scene' else 'assets',
                                    'role': 'active_'+role, 'reason': 'active selection changed',
                                    'before_path': previous, 'after_path': current,
                                    'expected_sha256': next((r['sha256'] for r in data['dependencies'] if r['path'] == data['controls'][role]), None),
                                    'actual_sha256': studio.digest(selected)})
    return {'ok': True, 'id': id, 'working_diverged': bool(differences), 'working_changes': differences, 'integrity': check(project, id),
            'meaning': 'Working divergence does not replace the captured revision or transfer its review.'}


def render_context(project, id):
    result = check(project, id)
    if not result['ok']: raise ValueError('Revision integrity failed: '+json.dumps(result.get('errors') or result['changed']))
    data = load(project, id)
    return {'scene': studio.inside(project, data['controls']['scene']), 'catalog': studio.inside(project, data['controls']['catalog']),
            'revision_id': id, 'manifest_sha256': result['manifest_sha256']}
