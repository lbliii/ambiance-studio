"""Destination-contained audio source packages; prior paths are archival data only."""
from pathlib import Path
import shutil
import tempfile

from . import audio, audio_library as library
from .audio_library_records import (MATERIALIZATION, LIMITS, now, shape, reference, checked_ref, validate_version)
from .file_identity import digest
from .project import project_lock
from .record_contracts import read_sealed, seal


def selected_files(folder, value):
    """Only explicitly typed files, never recursive path-looking provenance fields."""
    paths = {'version.json': 'audio_library_version'}
    roles = {'original':'audio_source_original', 'working':'audio_prepared_source',
             'recipe':'audio_preparation_recipe', 'source_receipt':'audio_prior_preparation'}
    for key, item in value['files'].items():
        if key not in roles: raise ValueError('Materialization needs a prepared source')
        checked_ref(folder, item); paths[item['path']] = roles[key]
    review = library.state(folder, value)
    for event, path in review['events']:
        paths[str(path.relative_to(folder))] = 'audio_library_observation' if event['type'] == 'observation' else 'audio_library_decision'
        audition = event['body'].get('audition') if event['type'] == 'observation' else None
        if audition:
            record, receipt = library.validate_audition(folder, value, audition['id'], audition['sha256'])
            paths[str(receipt.relative_to(folder))] = 'audio_library_audition'
            paths[str((receipt.parent/record['excerpt']['path']).relative_to(folder))] = 'audio_library_excerpt'
    return paths, review


def validate_materialization(project, path):
    project = Path(project).resolve(); path = Path(path)
    if path.is_absolute():
        if not path.resolve().is_relative_to(project): raise ValueError('Materialization receipt must remain inside the project')
        path = path.resolve()
    else: path = audio.inside(project, str(path))
    receipt = read_sealed(path, MATERIALIZATION)
    shape(receipt, ['format','schema_version','kind','id','created_utc','library_pin','source_version','files',
                    'review','dependencies','limits','payload_sha256'], label='audio materialization')
    audio.identifier(receipt['id'])
    if receipt['kind'] != 'library-source': raise ValueError('Unsupported audio materialization kind')
    expected_path = audio.inside(project, f'audio/library/{receipt["id"]}/receipt.json')
    if path != expected_path: raise ValueError('Materialization ID/path mismatch')
    version_path = checked_ref(project, receipt['source_version']); folder = version_path.parent
    if folder != path.parent/'source' or version_path.name != 'version.json': raise ValueError('Materialization source version must be destination-contained')
    value = validate_version(folder)
    if receipt['library_pin'] != library.version_pin(folder, value): raise ValueError('Materialized version pin changed')
    if 'working' not in value['files']: raise ValueError('Only prepared sources can be materialized')
    shape(receipt['files'], ['original','working','recipe','source_receipt'], label='materialized files')
    for key, item in receipt['files'].items():
        expected = reference(project, checked_ref(folder, value['files'][key]))
        if item != expected: raise ValueError('Materialization file identity mismatch: '+key)
        checked_ref(project, item)
    paths, review = selected_files(folder, value)
    if receipt['review'] != {'state': review['state'], 'state_sha256': review['state_sha256']}:
        raise ValueError('Materialized review identity changed')
    expected = [dict(reference(project, audio.inside(folder, name)), section='sound-design', role=role)
                for name, role in sorted(paths.items())]
    if receipt['dependencies'] != expected: raise ValueError('Materialization dependencies differ from typed contained files')
    return {'ok': True, 'kind': 'library-source', 'receipt': reference(project, path),
            'dependencies': [dict(reference(project, path), section='sound-design', role='audio_materialization'), *expected],
            'working': receipt['files']['working'], 'original': receipt['files']['original'],
            'source_format': value['source_format'], 'working_format': value['working_format'],
            'library_pin': receipt['library_pin'], 'review': receipt['review'], 'limits': LIMITS}


def materialize(config, project, asset_id, version, expected_version, expected_state, materialization_id, allow_unaccepted=False):
    root, header = library.load_config(config); project = Path(project).resolve(); audio.identifier(materialization_id)
    library.audio_sources._sha(expected_version); library.audio_sources._sha(expected_state)
    if project == root or project.is_relative_to(root): raise ValueError('Destination project must be independent of the library')
    destination = audio.inside(project, f'audio/library/{materialization_id}')
    if destination.exists(): raise ValueError('Materialization ID already exists')
    with project_lock(root):
        value, folder = library.load_version(root, header, asset_id, version)
        if digest(folder/'version.json') != expected_version: raise ValueError('Stale selected library version')
        paths, review = selected_files(folder, value)
        if review['state_sha256'] != expected_state: raise ValueError('Stale selected library review state')
        if review['state'] != 'accepted' and not allow_unaccepted: raise ValueError('Source is not accepted; explicit --allow-unaccepted preserves its current state')
        # Validate under the final project-relative namespace before publishing.
        with tempfile.TemporaryDirectory(prefix='ambiance-materialization-') as temporary:
            projection = Path(temporary).resolve(); relative = destination.relative_to(project)
            package = projection/relative; local = package/'source'; local.mkdir(parents=True)
            for name in paths:
                source = audio.inside(folder, name); target = audio.inside(local, name); target.parent.mkdir(parents=True, exist_ok=True)
                before = digest(source); shutil.copyfile(source, target)
                if digest(target) != before or digest(source) != before: raise ValueError('Source changed during materialization')
            local_value = validate_version(local); local_paths, local_review = selected_files(local, local_value)
            if local_paths != paths or local_review['state_sha256'] != expected_state: raise ValueError('Review changed during materialization')
            receipt = seal({'format': MATERIALIZATION, 'schema_version': 1, 'kind': 'library-source', 'id': materialization_id,
                'created_utc': now(), 'library_pin': library.version_pin(local, local_value),
                'source_version': reference(projection, local/'version.json'),
                'files': {key: reference(projection, checked_ref(local, item)) for key, item in local_value['files'].items()},
                'review': {'state': review['state'], 'state_sha256': review['state_sha256']},
                'dependencies': [dict(reference(projection, audio.inside(local, name)), section='sound-design', role=role)
                                 for name, role in sorted(paths.items())], 'limits': LIMITS})
            audio.write_json(package/'receipt.json', receipt); validate_materialization(projection, package/'receipt.json')
            with project_lock(project):
                if destination.exists(): raise ValueError('Materialization ID already exists')
                destination.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.TemporaryDirectory(prefix='.materialize-', dir=destination.parent) as publication:
                    stage_root = Path(publication); copied = stage_root/relative; copied.parent.mkdir(parents=True)
                    shutil.copytree(package, copied); validate_materialization(stage_root, copied/'receipt.json')
                    copied.rename(destination)
    checked = validate_materialization(project, destination/'receipt.json')
    return {**checked, 'receipt_path': str(destination/'receipt.json'),
            'source': {'id': asset_id, 'path': checked['working']['path'], 'sha256': checked['working']['sha256'],
                       'origin': f'Library {header["id"]} / {asset_id} / {version}', 'audition': review['state']}}
