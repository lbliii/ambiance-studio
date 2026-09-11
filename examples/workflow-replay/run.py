#!/usr/bin/env python3
"""Replay bounded public CLI operations on repository-generated art; never an agent trial."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ambiance_studio.checks import digest, scrub, source_identity, write


def replay(directory, resume=False):
    directory = Path(directory).resolve()
    state_file = directory / 'replay.json'
    identity = source_identity()
    if directory.exists():
        if not resume or not state_file.is_file():
            raise ValueError('Replay output must be fresh, or use --resume with its saved replay.json')
        state = json.loads(state_file.read_text())
        if state['source_sha256'] != identity['tracked_tree_sha256']:
            raise ValueError('Replay code changed; use a fresh output directory')
    else:
        directory.mkdir(parents=True)
        state = {'format': 'ambiance-workflow-replay', 'schema_version': 1,
                 'source_sha256': identity['tracked_tree_sha256'], 'commit': identity['commit'],
                 'kind': 'artifact-only-public-cli-replay', 'agent_trial_performed': False,
                 'artistic_review_performed': False, 'state': 'running', 'steps': {}, 'commands': []}
        write(state_file, state)
    project = directory / 'synthetic-project'

    def command(*args, expected=0):
        argv = [str(ROOT / 'ambiance'), '--registry', str(directory / 'registry.json'), '--project', str(project), *map(str, args)]
        result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, timeout=180)
        payload = json.loads(result.stdout)
        index = len(state['commands'])
        receipt = directory / 'commands' / f'{index:03d}.json'
        write(receipt, payload)
        state['commands'].append({'argv': [scrub(a) for a in argv], 'expected_exit': expected,
                                  'exit_code': result.returncode, 'receipt': str(receipt.relative_to(directory)), 'sha256': digest(receipt)})
        write(state_file, state)
        if result.returncode != expected:
            raise ValueError(f'Unexpected exit {result.returncode}, expected {expected}: {receipt}')
        return payload.get('data', payload)

    def step(name, operation):
        if name in state['steps']:
            return state['steps'][name]
        state['active_step'] = name
        write(state_file, state)
        result = operation()
        state['steps'][name] = result
        state.pop('active_step', None)
        write(state_file, state)
        return result

    def fixture():
        if project.exists():
            raise ValueError('Fixture initialization was interrupted. Preserve its diagnostics and start a fresh replay directory.')
        result = subprocess.run(['node', str(ROOT / 'examples/views/create_motion_fixture.mjs'), str(project)],
                                cwd=ROOT, capture_output=True, text=True, timeout=180)
        if result.returncode:
            raise ValueError(scrub(result.stderr[-4096:]))
        return {'scene_sha256': digest(project / 'scene/scene.json'),
                'proof': 'synthetic-project/render/paired-proof/index.html',
                'source': 'examples/views/moving-fixture.mjs', 'provenance': 'locally drawn geometric fixture',
                'files': {str(p.relative_to(directory)): digest(p) for base in [project / 'assets', project / 'render/paired-proof'] for p in sorted(base.rglob('*')) if p.is_file()}}

    try:
        baseline = step('REPLAY-FIXTURE', fixture)
        step('REPLAY-VIEWS', lambda: {'views': command('view', 'check')['views']})
        step('REPLAY-INCOMPLETE-SCOPE', lambda: {'expected_failure': command('plan', 'check', '--require-complete', expected=1)})

        def per_view_failure():
            # Persist restore identity before mutation so a replay interrupted here
            # can restore the exact baseline through the normal transaction history.
            if digest(project / 'scene/scene.json') != baseline['scene_sha256']:
                command('scene', 'restore', baseline['scene_sha256'])
            batch = project / 'plans/narrow-backing.json'
            write(batch, {'version': 1, 'operations': [{'op': 'set', 'layer': 'room', 'values': {'width': .8}}]})
            command('scene', 'apply', batch)
            report = command('view', 'check', expected=1)
            if not report['views']['portrait']['ok'] or report['views']['landscape']['ok']:
                raise ValueError('Injected narrow backing must fail landscape coverage only')
            proof = project / 'render/narrow-backing'
            if not proof.exists():
                command('render', 'views-proof', '--view', 'portrait', '--view', 'landscape', '--seconds', 1, '--long-edge', 160, '--out', proof)
            command('scene', 'restore', baseline['scene_sha256'])
            return {'issue_id': 'REPLAY-VIEW-BACKING', 'affected_view': 'landscape',
                    'unaffected_view': 'portrait', 'evidence_kind': 'geometry-and-raster',
                    'proof': 'synthetic-project/render/narrow-backing/index.html',
                    'files': {str(p.relative_to(directory)): digest(p) for p in sorted(proof.rglob('*')) if p.is_file()}}

        step('REPLAY-VIEW-BACKING', per_view_failure)
        step('REPLAY-RESTORED', lambda: {'views': command('view', 'check')['views']})
        if digest(project / 'scene/scene.json') != baseline['scene_sha256']:
            raise ValueError('Replay scene differs from the restored baseline')
        for saved in state['steps'].values():
            for relative, sha in saved.get('files', {}).items():
                if digest(directory / relative) != sha:
                    raise ValueError('Replay artifact changed: ' + relative)
        for row in state['commands']:
            if digest(directory / row['receipt']) != row['sha256']:
                raise ValueError('Saved command receipt changed: ' + row['receipt'])
        state['state'] = 'passed'
        state['ok'] = True
        state['unperformed'] = ['autonomous unfamiliar-seed agent trial', 'normal-speed artistic review', 'human/phone checks',
                                'feature-owned semantic, light binding, activity and interrupted paired-delivery replay (integration pending)']
    except BaseException as error:
        state['state'] = 'interrupted' if isinstance(error, KeyboardInterrupt) else 'failed'
        state['ok'] = False
        state['error'] = scrub(str(error))
        write(state_file, state)
        raise
    write(state_file, state)
    return {'ok': True, 'kind': state['kind'], 'report': str(state_file), 'steps': list(state['steps']),
            'proof': str(directory / baseline['proof']), 'unperformed': state['unperformed']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    try:
        result = replay(args.out, args.resume)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(json.dumps({'ok': False, 'error': scrub(str(error))})); return 1
    print(json.dumps(result, indent=2)); return 0


if __name__ == '__main__':
    sys.exit(main())
