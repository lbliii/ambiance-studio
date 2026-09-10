#!/usr/bin/env python3
"""Exercise public CLI workflows in a new synthetic project; never approve a film."""
import argparse
from array import array
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import wave

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import studio


def main(out, native=False):
    out = out.resolve()
    spec = importlib.util.spec_from_file_location('fixture', ROOT/'examples/source-placement/create_fixture.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); module.create(out)
    receipts = []
    def cli(*arguments, expected=0):
        command = [str(ROOT/'ambiance'), '--project', str(out), *map(str, arguments)]
        process = subprocess.run(command, text=True, capture_output=True)
        data = json.loads(process.stdout); receipts.append({'arguments': list(map(str, arguments)), 'exit_code': process.returncode, 'result': data})
        studio.write(out/'pilot-receipts.json', receipts)
        if process.returncode != expected: raise RuntimeError(f'CLI pilot failed: {arguments}: {process.stdout} {process.stderr}')
        return data['data']
    # Reset this disposable fixture to its reference plane. Placement/reparent
    # then run only through public commands and the saved authored manifests.
    placed = studio.read(out/'scene/before-reparent.json'); base = placed['layers'][0]
    base.pop('sockets', None); placed['layers'] = [base]; studio.write(out/'scene/scene.json', placed)
    dry = cli('scene', 'place', out/'placement.json', '--dry-run')
    cli('scene', 'place', out/'placement.json', '--expect-sha256', dry['previous_sha256'])
    cli('render', 'frame', '--time', 0, '--width', 180, '--out', out/'reports/before')
    dry = cli('scene', 'apply', out/'reparent-batch.json', '--dry-run')
    cli('scene', 'apply', out/'reparent-batch.json', '--expect-sha256', dry['previous_sha256'])
    cli('scene', 'timing', '--layer', 'gesture', '--out', out/'reports/timing.json')
    cli('render', 'frame', '--time', 0, '--width', 180, '--out', out/'reports/after')
    from PIL import Image
    with Image.open(out/'reports/before/frame.png') as before, Image.open(out/'reports/after/frame.png') as after:
        equal = before.tobytes() == after.tobytes()
    if not equal: raise RuntimeError('Reparent changed reference-pose raster pixels')
    proof = {'version': 1, 'samples': [
        {'id': 'rest', 'time': 0}, {'id': 'lift', 'time': 2},
        {'id': 'body-hidden', 'time': 2, 'overrides': {'body': {'visible': False}}},
        {'id': 'glass-hidden', 'time': 2, 'overrides': {'fixed-glass': {'visible': False}}}],
        'regions': [{'id': 'object', 'rect': [.2, .3, .6, .55]}],
        'comparisons': [{'id': 'lift-comparison', 'left': 'rest', 'right': 'lift', 'difference': True}], 'playback_seconds': 1}
    studio.write(out/'rig-proof.json', proof)
    cli('render', 'rig-proof', out/'rig-proof.json', '--width', 180, '--out', out/'reports/rig-proof')
    # Explicit tiny diagnostic soundtrack: no provider, no artistic music claim.
    rate = 48000; frames = rate*8
    samples = array('h')
    for i in range(frames):
        sample = round(300*math.sin(2*math.pi*220*i/rate)); samples.extend([sample, sample])
    if sys.byteorder != 'little': samples.byteswap()
    with wave.open(str(out/'audio/source.wav'), 'wb') as file:
        file.setnchannels(2); file.setsampwidth(2); file.setframerate(rate); file.writeframes(samples.tobytes())
    session = {'format': 'ambiance-audio-session', 'schema_version': 1, 'id': 'pilot', 'sample_rate': rate, 'frames': frames,
        'sources': [{'id': 'tone', 'path': 'audio/source.wav', 'sha256': studio.digest(out/'audio/source.wav')}],
        'stems': [{'id': 'tone', 'gain_db': 0}], 'clips': [{'id': 'tone', 'source': 'tone', 'stem': 'tone', 'at_frame': 0, 'frames': frames}]}
    studio.write(out/'audio/session-v1.json', session)
    mix = cli('audio', 'mix', 'audio/session-v1.json', '--run-id', 'first')
    alt = cli('audio', 'mix', 'audio/session-v1.json', '--run-id', 'second', '--gain', 'tone=-6')
    selection = {'format': 'ambiance-revision-selection', 'schema_version': 1, 'scene': 'scene/scene.json', 'catalog': 'assets/catalog.json',
        'documents': {'brief': 'plans/brief.md', 'layer_plan': 'plans/layer-plan.json', 'sound_plan': 'plans/sound-brief.md'},
        'audio': {'runs': ['audio/runs/first']}}
    studio.write(out/'selection.json', selection)
    dry = cli('revision', 'capture', 'v1', '--selection', out/'selection.json', '--dry-run')
    cli('revision', 'capture', 'v1', '--selection', out/'selection.json', '--expect-selection-sha256', dry['selection_sha256'])
    if native:
        picture = cli('render', 'video', '--revision', 'v1', '--width', 180, '--out', out/'reports/picture')
        for name, run_path in [('first', mix['run']), ('second', alt['run'])]:
            cli('media', 'compose', picture['picture'], '--picture-receipt', 'reports/picture/render-report.json', '--revision', 'v1',
                '--edition', name, '--audio', Path(run_path)/'mix/master.wav', '--audio-run', f'audio/runs/{name}', '--repeats', 2,
                '--out', out/f'deliverables/{name}')
        cli('media', 'verify', out/'deliverables/first/video.mp4', '--width', 180, '--height', 320, '--fps', 30, '--frames', 240,
            '--loop-frames', 120, '--audio-tracks', 1, '--contact-time', 3.67, '--out', out/'reports/contact')
    cli('revision', 'check', 'v1')
    control = studio.read(out/'scene/scene.json'); control['title'] += ' — working next pass'; studio.write(out/'scene/scene.json', control)
    divergence = cli('revision', 'compare', 'v1', '--working')
    cli('revision', 'check', 'v1')
    source = out/'assets/production/body-cutout/atlas.png'; original = source.read_bytes()
    try:
        source.write_bytes(original+b'changed dependency probe')
        stale = cli('revision', 'check', 'v1', expected=1)
    finally: source.write_bytes(original)
    cli('revision', 'check', 'v1')
    summary = {'ok': True, 'project': str(out), 'reference_pose_rgba_equal': equal, 'working_divergence_reported': divergence['working_diverged'],
        'changed_dependency': stale['changed'], 'native_editions_performed': native, 'browser_playback_performed': False,
        'creative_review_performed': False, 'commands': len(receipts), 'proof': str(out/'reports/rig-proof/index.html')}
    studio.write(out/'pilot-summary.json', summary); return summary


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--out', type=Path, required=True); p.add_argument('--native', action='store_true')
    args = p.parse_args(); print(json.dumps(main(args.out, args.native), indent=2))
