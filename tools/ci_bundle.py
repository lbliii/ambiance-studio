#!/usr/bin/env python3
"""Publish only bounded diagnostics and named synthetic replay proofs, never projects wholesale."""
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ambiance_studio.checks import digest, write

MAX_FILES = 256
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 20 * 1024 * 1024


def bundle(run, replay, out):
    run, replay, out = Path(run).resolve(), Path(replay).resolve(), Path(out).resolve()
    if out.exists():
        raise ValueError('Bundle output must be fresh')
    entries = []
    def select(root, relative, destination):
        source = root / relative
        if source.is_symlink() or not source.resolve().is_relative_to(root):
            raise ValueError('Symlink/escaped artifact is not publishable: ' + str(relative))
        if not source.is_file():
            return
        size = source.stat().st_size
        if size > MAX_FILE_BYTES:
            raise ValueError('Artifact exceeds file limit: ' + str(relative))
        entries.append((source, destination, size))
    for name in ['run.json', 'inputs.json', 'python.json', 'junit.xml']:
        select(run, Path(name), Path('checks') / name)
    for pattern in ['CI-*.stdout.txt', 'CI-*.stderr.txt']:
        for source in sorted(run.glob(pattern)):
            select(run, source.relative_to(run), Path('checks') / source.name)
    for source in sorted((run / 'failure-probe').rglob('*')):
        if source.suffix in {'.json', '.xml', '.txt', '.py'}:
            select(run, source.relative_to(run), Path('checks') / source.relative_to(run))
    select(replay, Path('replay.json'), Path('replay/replay.json'))
    for source in sorted((replay / 'commands').glob('*.json')):
        select(replay, source.relative_to(replay), Path('replay') / source.relative_to(replay))
    # Deliberate fixed allowlist: adding a feature proof is reviewed as code.
    for name in ['paired-proof', 'narrow-backing']:
        prefix = Path('synthetic-project/render') / name
        for source in sorted((replay / prefix).rglob('*')):
            if source.suffix not in {'.png', '.json', '.html', '.mjs', '.css'}:
                continue
            select(replay, source.relative_to(replay), Path('replay') / source.relative_to(replay))
    if len(entries) > MAX_FILES or sum(size for _, _, size in entries) > MAX_TOTAL_BYTES:
        raise ValueError('Artifact bundle exceeds bounded file/byte allowance')
    if not entries:
        raise ValueError('No attributable reports or synthetic proofs exist')
    out.mkdir(parents=True)
    manifest = []
    for source, target, size in entries:
        dest = out / target
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
        manifest.append({'path': str(target), 'bytes': size, 'sha256': digest(dest)})
    report = {'format': 'ambiance-ci-bundle', 'schema_version': 1, 'files': manifest,
              'bytes': sum(x['bytes'] for x in manifest), 'synthetic_only': True,
              'selection': 'Fixed test-report and repository-generated replay-proof allowlist; no project/film glob.',
              'limits': {'files': MAX_FILES, 'file_bytes': MAX_FILE_BYTES, 'total_bytes': MAX_TOTAL_BYTES}}
    write(out / 'manifest.json', report)
    return {'ok': True, 'files': len(manifest), 'bytes': report['bytes'], 'manifest': str(out / 'manifest.json')}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', type=Path, required=True); p.add_argument('--replay', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    try:
        print(json.dumps(bundle(args.run, args.replay, args.out), indent=2)); return 0
    except (OSError, ValueError) as error:
        print(json.dumps({'ok': False, 'error': str(error)})); return 1


if __name__ == '__main__':
    sys.exit(main())
