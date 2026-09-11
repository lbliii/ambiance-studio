#!/usr/bin/env python3
"""Join feature-owned synthetic public-CLI replays; no autonomous trial is implied."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ambiance_studio.checks import digest, scrub, source_identity, write

FEATURES = {
    'intent': {'script': 'examples/production-intent/replay.py', 'engine': 'python', 'position': True, 'native_option': True},
    'assets-tea': {'script': 'examples/agent-preparation/create_fixture.py', 'engine': 'python', 'position': True, 'extra': ['--subject', 'tea']},
    'assets-cabinet': {'script': 'examples/agent-preparation/create_fixture.py', 'engine': 'python', 'position': True, 'extra': ['--subject', 'cabinet']},
    'bindings': {'script': 'examples/bindings/create_fixture.mjs', 'engine': 'node', 'position': True},
    'activity': {'script': 'examples/activity/replay.py', 'engine': 'python'},
    'paired-recovery': {'script': 'examples/workflow-replay/paired_delivery.py', 'engine': 'python', 'native_only': True},
}


def invoke(argv, timeout=900):
    """Stop the fixture and its render descendants on timeout/interruption."""
    process = subprocess.Popen(argv, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except BaseException as error:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        stdout, stderr = process.communicate()
        error.stdout = stdout
        error.stderr = stderr
        raise
    return subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)


def checked_file(root, relative):
    path = root / relative
    if path.is_symlink() or not path.resolve().is_relative_to(root):
        raise ValueError('Synthetic fixture output contains an escaped file: ' + str(relative))
    return path


def replay(out, selected, native=False, resume=False):
    out = Path(out).resolve()
    identity = source_identity()
    config = {'features': selected, 'native': native, 'source_sha256': identity['tracked_tree_sha256']}
    state_file = out / 'combined.json'
    if out.exists():
        if not resume or not state_file.is_file():
            raise ValueError('Use a fresh output directory or --resume with combined.json')
        state = json.loads(state_file.read_text())
        if state['config'] != config:
            raise ValueError('Selected features/native policy/source changed; start a fresh replay')
    else:
        out.mkdir(parents=True)
        state = {'format': 'ambiance-combined-replay', 'schema_version': 1, 'ok': False, 'state': 'running',
                 'kind': 'feature-owned-artifact-replays', 'agent_trial_performed': False, 'artistic_review_performed': False,
                 'commit': identity['commit'], 'config': config, 'cases': {}, 'attempts': {},
                 'unselected': sorted(set(FEATURES)-set(selected)),
                 'limits': ['Fixture assertions establish specific structure/state/raster/native behavior only.',
                            'Synthetic source paint and declared scenarios do not complete an unfamiliar-seed agent trial or film.',
                            'No provider, account, private project or recurring task is used.']}
        write(state_file, state)
    try:
        state.update(ok=False, state='running')
        state.pop('error', None)
        for name in selected:
            spec = FEATURES[name]
            if spec.get('native_only') and not native:
                state['cases'][name] = {'state': 'not-run', 'reason': 'Native replay was not requested in this lane'}
                continue
            prior = state['cases'].get(name)
            if prior and prior['state'] == 'passed':
                for file in prior['files']:
                    if digest(checked_file(out, file['path'])) != file['sha256']:
                        raise ValueError('Completed fixture changed: ' + file['path'])
                continue
            script = ROOT / spec['script']
            if not script.is_file():
                raise ValueError('Feature is not integrated: ' + spec['script'] + '; fetch its merged implementation before replay')
            attempt = state['attempts'].get(name, 0) + 1
            state['attempts'][name] = attempt
            parent = out / name; parent.mkdir(exist_ok=True)
            destination = parent / f'attempt-{attempt:03d}'
            executable = sys.executable if spec['engine'] == 'python' else 'node'
            argv = [executable, str(script), *([] if spec.get('position') else ['--out']), str(destination), *spec.get('extra', [])]
            if native and spec.get('native_option'):
                argv.append('--native')
            state['active_case'] = name
            state['cases'][name] = {'state': 'running', 'attempt': attempt, 'directory': str(destination.relative_to(out)),
                                     'source': spec['script'], 'source_sha256': digest(script)}
            write(state_file, state)
            stdout = parent / f'attempt-{attempt:03d}.stdout.json'
            stderr = parent / f'attempt-{attempt:03d}.stderr.txt'
            row = state['cases'][name]
            row.update(result=str(stdout.relative_to(out)), stderr=str(stderr.relative_to(out)))
            try:
                result = invoke(argv)
            except BaseException as error:
                write(stdout, {'ok': False, 'interrupted_stdout_tail': scrub(getattr(error, 'stdout', '') or '')[-8192:]})
                stderr.write_text(scrub(getattr(error, 'stderr', '') or '')[-32768:])
                row['timed_out'] = isinstance(error, subprocess.TimeoutExpired)
                raise
            try:
                payload = json.loads(result.stdout)
            except ValueError:
                payload = {'ok': False, 'unparsed_stdout_tail': scrub(result.stdout[-8192:])}
            write(stdout, payload); stderr.write_text(scrub(result.stderr[-32768:]))
            row.update(exit_code=result.returncode, result=str(stdout.relative_to(out)), stderr=str(stderr.relative_to(out)))
            if result.returncode or payload.get('ok') is False:
                row['state'] = 'failed'
                raise ValueError(f'{name} attempt {attempt} failed; inspect {stdout}. --resume preserves it and starts a fresh attempt.')
            files = [stdout, stderr] + [p for p in sorted(destination.rglob('*')) if p.is_file()]
            if any(p.is_symlink() or not p.resolve().is_relative_to(out) for p in files):
                raise ValueError('Synthetic fixture output contains an escaped file')
            row.update(state='passed', files=[{'path': str(p.relative_to(out)), 'sha256': digest(p), 'bytes': p.stat().st_size} for p in files])
            state.pop('active_case', None)
            write(state_file, state)
        if source_identity()['tracked_tree_sha256'] != config['source_sha256']:
            raise ValueError('Code changed during combined replay; rerun against the final tree')
        state.update(ok=True, state='passed')
    except BaseException as error:
        active = state.get('active_case')
        if active:
            state['cases'][active]['state'] = 'interrupted' if isinstance(error, KeyboardInterrupt) else 'failed'
        state.update(ok=False, state='interrupted' if isinstance(error, KeyboardInterrupt) else 'failed', error=scrub(str(error)))
        write(state_file, state)
        raise
    write(state_file, state)
    return {'ok': True, 'kind': state['kind'], 'report': str(state_file),
            'cases': {name: row['state'] for name, row in state['cases'].items()},
            'unperformed': ['autonomous unfamiliar-seed trials', 'normal-speed artistic observations', 'human/phone reviews'] + state['unselected'] + [name for name, row in state['cases'].items() if row['state'] == 'not-run']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True); parser.add_argument('--resume', action='store_true')
    parser.add_argument('--native', action='store_true'); parser.add_argument('--feature', action='append', choices=list(FEATURES))
    args = parser.parse_args()
    selected = args.feature or list(FEATURES)
    if len(selected) != len(set(selected)):
        parser.error('Feature IDs must be unique')
    try:
        print(json.dumps(replay(args.out, selected, args.native, args.resume), indent=2)); return 0
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(json.dumps({'ok': False, 'error': scrub(str(error))})); return 1


if __name__ == '__main__':
    sys.exit(main())
