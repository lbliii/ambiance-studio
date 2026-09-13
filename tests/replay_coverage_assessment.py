"""Bounded WF-01 public CLI replay over disposable supplied-art fixtures.

This is an engineering replay, not a workflow adoption or artistic review trial.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import studio
from test_production_coverage import fixture


def snapshot(project):
    return {str(p.relative_to(project)): studio.digest(p) if p.is_file() else 'directory'
            for p in project.rglob('*')}


def replay(destination):
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    project = fixture(destination)
    records = []

    def run(name, *args, code=0, pure=False):
        argv = [str(ROOT/'ambiance'), '--project', str(project), *map(str, args)]
        before = snapshot(project) if pure else None
        started = time.monotonic()
        result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True)
        output = destination/(name+'.json'); output.write_text(result.stdout)
        if result.returncode != code:
            raise AssertionError(f'{name}: expected {code}, got {result.returncode}: {result.stderr} {result.stdout}')
        unchanged = before == snapshot(project) if pure else None
        if pure and not unchanged: raise AssertionError(name+': pure query changed project files')
        records.append({'name': name, 'argv': argv, 'exit_code': result.returncode,
                        'elapsed_seconds': round(time.monotonic()-started, 3), 'project_unchanged': unchanged,
                        'output': {'path': str(output), 'sha256': studio.digest(output), 'bytes': output.stat().st_size}})
        return json.loads(result.stdout)['data']

    initial = run('01-pure-layout', 'project', 'overview', '--stage', 'layout', '--details', pure=True)
    assert initial['production_readiness']['ready']
    assert not (project/'.ambiance/coverage').exists()
    saved = run('02-explicit-coverage', 'plan', 'coverage', '--stage', 'layout', '--details')
    assert Path(saved['report']).is_file()
    before = Path(saved['report']).read_bytes()
    repeated = run('03-repeat-coverage', 'plan', 'coverage', '--stage', 'layout')
    assert repeated['report'] == saved['report'] and Path(saved['report']).read_bytes() == before
    proof = run('04-portrait-proof', 'render', 'views-proof', '--view', 'portrait', '--seconds', '1',
                '--long-edge', '160', '--out', project/'render/proof')
    run('05-register-portrait', 'plan', 'evidence', 'pixels', '--view', 'portrait',
        '--receipt', Path(proof['report']).relative_to(project))
    portrait = run('06-pure-portrait', 'project', 'overview', '--view', 'portrait', '--details', pure=True)
    assert portrait['production_readiness']['ready']
    landscape = run('07-wrong-view', 'project', 'overview', '--view', 'landscape', '--details', pure=True)
    assert not landscape['production_readiness']['ready']
    # A held writer lock and filesystem write denial must not block inspection.
    (project/'.ambiance/write.lock').write_text('engineering replay writer')
    paths = [project, *project.rglob('*')]
    modes = {path: path.stat().st_mode & 0o777 for path in paths}
    for path in paths: path.chmod(0o555 if path.is_dir() else 0o444)
    try:
        run('08-readonly-overview', 'project', 'overview', '--details', pure=True)
        run('09-readonly-next', 'project', 'next', pure=True)
    finally:
        for path, mode in modes.items(): path.chmod(mode)
    (project/'.ambiance/write.lock').unlink()
    frame = Path(proof['report']).parent/'portrait/00000.png'
    frame.write_bytes(frame.read_bytes()+b'changed fixture')
    stale = run('10-stale-proof', 'project', 'overview', '--view', 'portrait', '--details', pure=True)
    assert not stale['production_readiness']['ready']
    (project/'scene/scene.json').write_text('{malformed working scene')
    partial = run('11-partial-inputs', 'project', 'overview', '--details', pure=True)
    assessment = partial['production_readiness']['assessment']
    assert assessment['components']['plan']['state'] == 'available'
    assert assessment['components']['scene']['state'] == 'unknown'
    assert not partial['release_ready']
    manifest = {'format': 'ambiance-wf01-replay', 'schema_version': 1, 'ok': True,
                'project': str(project), 'commands': records, 'project_files': snapshot(project),
                'limits': ['Synthetic supplied art and actual raster proof; no native movie or artistic approval.',
                           'Missing runtime and cold/warm decoder paths have separate focused tests.',
                           'This WF-01 replay does not implement WF-02–07.']}
    path = destination/'replay.json'; studio.write(path, manifest)
    return {'ok': True, 'commands': len(records), 'manifest': str(path), 'sha256': studio.digest(path)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path, help='Fresh disposable artifact directory')
    print(json.dumps(replay(parser.parse_args().out), indent=2))
