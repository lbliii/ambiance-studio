#!/usr/bin/env python3
"""Local public-CLI replay. Synthetic media verifies mechanics, not a film verdict."""
import argparse
import importlib.util
import json
import math
from pathlib import Path
import shutil
import struct
import subprocess
import time
import wave

ROOT = Path(__file__).resolve().parents[2]


def fixture(out):
    spec = importlib.util.spec_from_file_location('activity_fixture', ROOT/'examples/activity/create_fixture.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    project = module.create(out, fps=12)
    master = project/'audio/master.wav'
    with wave.open(str(master), 'wb') as target:
        target.setnchannels(2); target.setsampwidth(2); target.setframerate(48000)
        target.writeframes(b''.join(struct.pack('<hh', value, value) for i in range(4*48000)
                                   for value in [round(600*math.sin(2*math.pi*220*i/48000))]))
    shutil.copyfile(master, project/'audio/source.wav')
    (project/'audio/identity.txt').write_text('Engineering audition: 4-second quiet 220 Hz reference tone copied unchanged. No artistic soundtrack claim.')
    import hashlib
    def ref(name): return {'path': 'audio/'+name, 'sha256': hashlib.sha256((project/'audio'/name).read_bytes()).hexdigest()}
    (project/'audio/preparation.json').write_text(json.dumps({'format': 'ambiance-external-preparation', 'schema_version': 1,
        'sources': [ref('source.wav')], 'recipes': [ref('identity.txt')], 'outputs': [ref('master.wav')]}))
    return project


def packet_request(id='first-review'):
    return {'format': 'ambiance-review-packet-request', 'schema_version': 1, 'audible_role': 'score', 'interval': [0, 4],
            'auditions': ['audio/source.wav'], 'questions': ['Do the two formats play the same four seconds with only one audible movie?',
                                                         'Does the source audition pause both movies?'],
            'iteration': {'format': 'ambiance-iteration-request', 'schema_version': 1, 'id': id, 'revision': id,
                'title': 'Synthetic paired review — mechanics only', 'scope': 'proof', 'long_edge': 128,
                'views': ['portrait', 'landscape'], 'default': {'view': 'portrait', 'role': 'score'},
                'editions': [{'role': 'silent'}, {'role': 'score', 'audio': 'audio/master.wav', 'audio_provenance': 'audio/preparation.json'}],
                'audio_selection': {'preparations': ['audio/preparation.json']}}}


def replay(out):
    started = time.monotonic(); project = fixture(out); records = []; evidence = project/'replay'; evidence.mkdir()
    def cli(*args):
        before = time.monotonic(); command = [str(ROOT/'ambiance'), '--project', str(project), *map(str, args)]
        result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
        path = evidence/f'{len(records):02d}.json'; path.write_text(result.stdout)
        records.append({'argv': command, 'seconds': time.monotonic()-before, 'stdout_bytes': len(result.stdout.encode()),
                        'exit_code': result.returncode, 'evidence': str(path.relative_to(project))})
        if result.returncode: raise ValueError(result.stdout or result.stderr)
        return json.loads(result.stdout)['data']
    request = project/'plans/packet.json'; request.write_text(json.dumps(packet_request()))
    initialized = cli('review', 'packet', 'init', request, '--out', project/'recipes/first-review')
    completed = cli('review', 'packet', 'run', initialized['request'], '--by', 'CLI replay')
    first_movie = time.monotonic()-started
    cli('review', 'packet', 'run', initialized['request'], '--by', 'CLI replay')
    cli('review', 'packet', 'inspect', completed['packet'])
    feedback = cli('feedback', 'add', 'first-review', '--scope', 'delivery', '--note', 'Synthetic untimed report: preserve uncertainty.', '--by', 'CLI replay', '--request-id', 'untimed')
    note = feedback.get('feedback', feedback)
    cli('project', 'next', '--kind', 'feedback')
    disposition = project/'plans/disposition.json'
    disposition.write_text(json.dumps({'outcome': 'withdrawn', 'note': 'Synthetic report withdrawn after exercising its lifecycle, not an artistic approval.'}))
    resolved = cli('feedback', 'resolve', note['id'], '--resolution', disposition, '--by', 'CLI replay', '--expect-head', note['head'])
    resolved = resolved.get('feedback', resolved)
    cli('feedback', 'reopen', note['id'], '--note', 'Keep this engineering example open for browser inspection.', '--by', 'CLI replay', '--expect-head', resolved['head'])
    overview = cli('project', 'overview')
    assert overview['current']['selection'] is None, 'Packet must not select the current review'
    report = {'format': 'ambiance-midnight-replay', 'schema_version': 1, 'kind': 'synthetic-public-cli', 'ok': True,
              'first_paired_movie_seconds': first_movie, 'elapsed_seconds': time.monotonic()-started,
              'commands': records, 'player': completed['player'], 'packet': completed['packet'],
              'unnecessary_questions': 0, 'paid_generations': 0, 'canonical_file_surgery_after_fixture_setup': 0,
              'limits': ['The supplied synthetic fixture is not a sheltered, open-window or haunted film.',
                         'No autonomous unfamiliar-seed trial, human listening or artistic approval is implied.']}
    (evidence/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(); result = replay(args.out)
    print(json.dumps({key: value for key, value in result.items() if key != 'commands'}, indent=2))
