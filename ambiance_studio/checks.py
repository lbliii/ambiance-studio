"""Bounded regression diagnostics. Only explicitly selected synthetic proofs are publishable."""
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import signal
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

from .file_identity import digest
from .errors import CommandError

ROOT = Path(__file__).resolve().parents[1]
LOG_LIMIT = 32768


def scrub(text):
    # Test diagnostics may identify a local checkout or fixture directory; never upload
    # a user's absolute home/private project address as an artifact.
    for path, label in [(str(ROOT), '$REPO'), (str(Path.home()), '$HOME'), (tempfile.gettempdir(), '$TMP')]:
        text = text.replace(path, label)
    return re.sub(r'/(?:private/)?(?:tmp|var/folders)/[^\s\"\'<>]+', '$TMP', text)


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


def source_identity():
    result = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True)
    files = subprocess.run(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT, capture_output=True).stdout.split(b'\0')
    records = {}
    for name in files:
        if not name:
            continue
        p = ROOT / os.fsdecode(name)
        if p.is_file() and not p.is_symlink():
            records[os.fsdecode(name)] = digest(p)
    return {'commit': result.stdout.strip() or None,
            'tracked_tree_sha256': hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest(),
            'files': records}


def execute(check_id, command, directory, *, timeout=600, env=None):
    """Capture to temporary files; only bounded, scrubbed tails enter retained artifacts."""
    start = time.monotonic()
    timed_out = False
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        try:
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=stdout, stderr=stderr,
                                       start_new_session=True)
            try:
                code = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                os.killpg(process.pid, signal.SIGKILL)
                code = process.wait()
        except OSError as error:
            stderr.write(str(error).encode()); code = 127
        outputs = {}
        for name, stream in [('stdout', stdout), ('stderr', stderr)]:
            size = stream.tell()
            stream.seek(max(0, size - LOG_LIMIT))
            encoded = scrub(stream.read().decode('utf-8', errors='replace')).encode('utf-8')
            content = encoded[-LOG_LIMIT:].decode('utf-8', errors='ignore')
            path = directory / (check_id + '.' + name + '.txt')
            path.write_text(content, encoding='utf-8')
            outputs[name] = {'path': path.name, 'captured_bytes': path.stat().st_size,
                             'original_bytes': size, 'truncated': size > LOG_LIMIT or len(encoded) > LOG_LIMIT, 'sha256': digest(path)}
    return {'id': check_id, 'command': [scrub(str(c)) for c in command], 'exit_code': code,
            'ok': code == 0 and not timed_out, 'timed_out': timed_out,
            'elapsed_seconds': round(time.monotonic() - start, 3), 'logs': outputs}


def native_requirement(required, capabilities):
    if not required:
        return {'id': 'CI-NATIVE-CAPABILITY', 'ok': True, 'state': 'not-required', 'executed': False}
    available = bool(capabilities.get('final_video_export') and capabilities.get('media_verify'))
    return {'id': 'CI-NATIVE-CAPABILITY', 'ok': available,
            'state': 'available-unexercised' if available else 'unavailable', 'executed': False,
            'issue_id': None if available else 'CI-NATIVE-UNAVAILABLE',
            'next_action': None if available else 'Run the required lane on macOS with Node Canvas, xcrun and working AVFoundation media services; a skipped test is not native validation.'}


def junit(report, path):
    cases = report.get('cases', [])
    suite = ET.Element('testsuite', name='ambiance', tests=str(len(cases)))
    for row in cases:
        case = ET.SubElement(suite, 'testcase', name=row['id'], time=str(row.get('seconds', 0)))
        if row['status'] in ['skipped', 'expected-failure']:
            ET.SubElement(case, 'skipped', message=row.get('detail', ''))
        elif row['status'] != 'passed':
            ET.SubElement(case, 'failure', message=row['status']).text = row.get('detail', '')
    ET.ElementTree(suite).write(path, encoding='utf-8', xml_declaration=True)


def run_suite(artifacts=None, require_native=False):
    from . import rendering
    required = require_native or os.environ.get('AMBIANCE_TEST_NATIVE') == '1'
    # A fresh immutable directory retains checkpoints even when a command fails.
    directory = Path(artifacts).resolve() if artifacts else Path(tempfile.mkdtemp(prefix='ambiance-checks-'))
    if artifacts:
        if directory.exists():
            raise CommandError('Test artifact directory must be fresh: ' + str(directory))
        directory.mkdir(parents=True)
    native = native_requirement(required, rendering.capabilities())
    env = os.environ.copy()
    if required:
        env['AMBIANCE_TEST_NATIVE'] = '1'
    identity = source_identity()
    write(directory / 'inputs.json', identity)
    report = {'format': 'ambiance-test-run', 'schema_version': 1, 'ok': False, 'state': 'running',
              'runtime': {'python': platform.python_version(), 'node': subprocess.run(['node', '--version'], capture_output=True, text=True).stdout.strip(), 'platform': platform.system()},
              'source': {'commit': identity['commit'], 'tracked_tree_sha256': identity['tracked_tree_sha256'], 'manifest': 'inputs.json'},
              'native_required': required, 'checks': [native], 'cases': [],
              'ci': {key: os.environ.get(env) for key, env in [('run_id', 'GITHUB_RUN_ID'), ('attempt', 'GITHUB_RUN_ATTEMPT'), ('event', 'GITHUB_EVENT_NAME'), ('head_sha', 'AMBIANCE_CI_HEAD_SHA'), ('checkout_sha', 'GITHUB_SHA')]},
              'limits': ['Regression checks and artifact replay are not autonomous agent trials or artistic reviews.',
                         'Retained logs are scrubbed bounded tails; detailed synthetic proofs require an explicit allowlist.']}
    if not native['ok']:
        report['cases'].append({'id': native['issue_id'], 'status': 'failed', 'detail': native['next_action']})
    write(directory / 'run.json', report)
    commands = [('CI-PYTHON', [sys.executable, 'tools/unittest_report.py', '--out', str(directory / 'python.json')])]
    commands += [('CI-ENGINE', ['node', 'editor/verify-engine.mjs'])]
    commands += [('CI-' + p.stem.removeprefix('test-').upper(), ['node', str(p.relative_to(ROOT))])
                 for p in sorted((ROOT / 'tests').glob('test-*.mjs'))]
    commands += [('CI-PACKAGE', [sys.executable, 'tools/package_audit.py']),
                 ('CI-FAILURE-CONTRACT', [sys.executable, 'tools/ci_failure_probe.py', '--out', str(directory / 'failure-probe')])]
    for check_id, command in commands:
        row = execute(check_id, command, directory, env=env)
        report['checks'].append(row)
        if check_id == 'CI-PYTHON' and (directory / 'python.json').exists():
            python = json.loads((directory / 'python.json').read_text())
            row['ok'] = row['ok'] and python.get('state') == 'completed' and python.get('tests_run', 0) > 0
            report['cases'].extend(python['cases'])
            if required and python['skipped']:
                report['cases'].append({'id': 'CI-REQUIRED-TEST-SKIPPED', 'status': 'failed', 'detail': 'Required native/raster lane skipped tests; see python.json'})
                report['checks'].append({'id': 'CI-REQUIRED-SKIP', 'ok': False,
                                         'issue_id': 'CI-REQUIRED-TEST-SKIPPED', 'count': python['skipped'],
                                         'next_action': 'Restore the missing native/raster capability; required-lane skips cannot pass.'})
        else:
            report['cases'].append({'id': check_id, 'status': 'passed' if row['ok'] else 'failed',
                                    'seconds': row['elapsed_seconds'], 'detail': row['logs']['stderr']['path']})
        write(directory / 'run.json', report)
    if source_identity()['tracked_tree_sha256'] != identity['tracked_tree_sha256']:
        report['checks'].append({'id': 'CI-SOURCE-CHANGED', 'ok': False, 'issue_id': 'CI-SOURCE-CHANGED', 'next_action': 'Source changed during validation; rerun against the final tree.'})
        report['cases'].append({'id': 'CI-SOURCE-CHANGED', 'status': 'failed', 'detail': 'Source changed during validation'})
    report['ok'] = all(row['ok'] for row in report['checks'])
    report['state'] = 'passed' if report['ok'] else 'failed'
    write(directory / 'run.json', report)
    junit(report, directory / 'junit.xml')
    return {'ok': report['ok'], 'checks': [{k: r[k] for k in ['id', 'ok', 'exit_code', 'issue_id', 'state', 'next_action'] if k in r} for r in report['checks']],
            'cases': len(report['cases']), 'native_required': required,
            'artifacts': str(directory), 'report': str(directory / 'run.json'), 'junit': str(directory / 'junit.xml'),
            'source': report['source']}
