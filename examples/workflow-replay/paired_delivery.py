#!/usr/bin/env python3
"""Interrupt a real public-CLI paired encode after the first view, then prove recovery."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ambiance_studio.checks import digest, scrub, write


def replay(out):
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    project = out / 'synthetic-project'
    state = {'format': 'ambiance-paired-recovery-replay', 'schema_version': 1, 'ok': False,
             'kind': 'actual-cli-interruption-and-resume', 'agent_trial_performed': False, 'commands': []}
    report = out / 'recovery.json'
    write(report, state)
    base = [str(ROOT / 'ambiance'), '--registry', str(out / 'registry.json'), '--project', str(project)]

    def record(argv, result):
        receipt = out / 'commands' / f'{len(state["commands"]):03d}.json'
        payload = json.loads(result.stdout)
        write(receipt, payload)
        state['commands'].append({'command': [scrub(str(x)) for x in argv], 'exit_code': result.returncode,
                                  'receipt': str(receipt.relative_to(out)), 'sha256': digest(receipt)})
        write(report, state)
        return payload

    def command(*args, env=None):
        argv = base + list(map(str, args))
        result = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True, text=True, timeout=180)
        payload = record(argv, result)
        if result.returncode:
            raise ValueError(str(payload))
        return payload['data']

    try:
        fixture = subprocess.run(['node', str(ROOT / 'examples/views/create_motion_fixture.mjs'), str(project)], cwd=ROOT, capture_output=True, text=True, timeout=180)
        if fixture.returncode:
            raise ValueError(fixture.stderr)
        # Public render both establishes real native capability and creates the exact
        # backend binary that the test wrapper delegates to. It creates no edition.
        command('render', 'video', '--view', 'portrait', '--width', 90, '--seconds', .125, '--out', project / 'render/native-probe')
        binaries = list((project / '.ambiance/native').glob('*/media'))
        if len(binaries) != 1:
            raise ValueError('Expected exactly one backend built by the public native probe')
        backend = binaries[0]
        selection = project / 'plans/recovery-selection.json'
        write(selection, {'format': 'ambiance-revision-selection', 'schema_version': 1, 'scene': 'scene/scene.json', 'catalog': 'assets/catalog.json'})
        recipe = project / 'plans/recovery-iteration.json'
        write(recipe, {'format': 'ambiance-iteration', 'schema_version': 2, 'id': 'recovery-pair', 'revision': 'recovery-r1',
                       'capture_selection': 'plans/recovery-selection.json', 'views': ['portrait', 'landscape'], 'long_edge': 160,
                       'default': {'view': 'portrait', 'role': 'silent'}, 'editions': [{'role': 'silent'}],
                       'title': 'Synthetic interruption recovery', 'notes': 'Engineering replay only; artistic and human checks unperformed.'})
        marker, counter, wrapper = out / 'second-encode-started', out / 'encode-count', out / 'interruptible-media.py'
        wrapper.write_text('#!' + sys.executable + '\n' + f'''import os, sys, time
from pathlib import Path
counter = Path({str(counter)!r})
if sys.argv[1] == 'encode':
    count = int(counter.read_text()) + 1 if counter.exists() else 1
    counter.write_text(str(count))
    if count == 2:
        Path({str(marker)!r}).write_text('Synthetic second encode is waiting for a real process interruption.')
        while True: time.sleep(1)
os.execv({str(backend)!r}, [{str(backend)!r}] + sys.argv[1:])
''')
        wrapper.chmod(0o755)
        env = os.environ.copy(); env['AMBIANCE_MEDIA_BINARY'] = str(wrapper)
        argv = base + ['iteration', 'run', str(recipe), '--by', 'CI synthetic replay']
        process = subprocess.Popen(argv, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
        deadline = time.monotonic() + 120
        while not marker.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(.05)
        if not marker.exists():
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate(timeout=15)
            raise ValueError('Second encode did not reach the interruption point: ' + scrub((stdout + stderr)[-4096:]))
        # Signal only the subprocess group created by this fixture, never a user process.
        os.killpg(process.pid, signal.SIGINT)
        stdout, stderr = process.communicate(timeout=30)
        interrupted = subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)
        record(argv, interrupted)
        if process.returncode != 130:
            raise ValueError('CLI did not report the injected interruption as exit 130')
        run_path = project / 'runs/recovery-pair/run.json'
        partial = json.loads(run_path.read_text())
        if partial['state'] != 'interrupted' or set(partial['steps']) != {'portrait.picture.silent'}:
            raise ValueError('Interrupted pair did not preserve only its completed portrait step')
        first = partial['steps']['portrait.picture.silent']['outputs']
        if command('delivery', 'list')['current'] is not None:
            raise ValueError('An incomplete pair became the current delivery')
        state.update(interruption={'exit_code': 130, 'run_state': partial['state'], 'completed_outputs': first,
                                   'selected_incomplete_pair': False})
        write(out / 'interrupted-run.json', partial)
        write(report, state)
        command('iteration', 'run', recipe, '--by', 'CI synthetic replay', env=env)
        complete = json.loads(run_path.read_text())
        if complete['state'] != 'complete' or complete['steps']['portrait.picture.silent']['outputs'] != first:
            raise ValueError('Resume changed the retained portrait identities')
        for ref in first:
            if digest(project / ref['path']) != ref['sha256']:
                raise ValueError('Retained portrait media/receipt changed')
        if int(counter.read_text()) != 3:
            raise ValueError('Resume repainted a completed view instead of encoding only the remaining one')
        delivery = command('delivery', 'inspect', 'recovery-pair')
        if set(delivery['entries']) != {'portrait.silent', 'landscape.silent'}:
            raise ValueError('Resume did not produce the exact requested view/role pairs')
        state.update(ok=True, resume={'run_state': 'complete', 'encode_attempts': 3, 'retained_portrait_unchanged': True,
                                     'entries': {key: value['movie'] for key, value in delivery['entries'].items()}},
                     limits=['Real native encoding/decoding and CLI recovery were exercised on generated geometric art.',
                             'No autonomous agent, artistic, listening or phone review was performed.'])
    except BaseException as error:
        state['error'] = scrub(str(error)); write(report, state); raise
    write(report, state)
    return {'ok': True, 'report': str(report), 'project': str(project), 'kind': state['kind']}


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(replay(args.out), indent=2)); return 0
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(json.dumps({'ok': False, 'error': scrub(str(error))})); return 1


if __name__ == '__main__':
    sys.exit(main())
