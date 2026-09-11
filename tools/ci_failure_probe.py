#!/usr/bin/env python3
"""Retain actual injected subprocess/test failures as expected CI contract evidence."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ambiance_studio.checks import execute, native_requirement, write, junit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(); directory = args.out.resolve()
    directory.mkdir(parents=True, exist_ok=False)
    test_dir = directory / 'inputs'; test_dir.mkdir()
    (test_dir / 'test_failure.py').write_text("import unittest\nclass Failure(unittest.TestCase):\n def test_injected_encoder_error(self): raise RuntimeError('Synthetic encoder service unavailable')\n")
    failure = execute('CI-INJECTED-ASSERTION', [sys.executable, 'tools/unittest_report.py', '--directory', str(test_dir), '--out', str(directory / 'cases.json')], directory)
    timeout = execute('CI-INJECTED-TIMEOUT', [sys.executable, '-c', 'import time; time.sleep(20)'], directory, timeout=.1)
    missing = execute('CI-INJECTED-RUNTIME', [str(directory / 'absent-runtime')], directory)
    capability = native_requirement(True, {})
    cases = json.loads((directory / 'cases.json').read_text())
    junit(cases, directory / 'junit.xml')
    ok = failure['exit_code'] != 0 and timeout['timed_out'] and missing['exit_code'] == 127 and not capability['ok'] and not cases['ok']
    report = {'format': 'ambiance-failure-probe', 'schema_version': 1, 'ok': ok,
              'kind': 'expected-injected-failures', 'checks': [failure, timeout, missing, capability],
              'note': 'The failures above are deliberately triggered; this probe passes only when they remain nonzero and attributable.'}
    write(directory / 'probe.json', report)
    print(json.dumps({'ok': ok, 'report': str(directory / 'probe.json')}))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
