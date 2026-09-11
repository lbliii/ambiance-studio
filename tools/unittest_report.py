#!/usr/bin/env python3
"""Run existing unittest discovery with bounded, attributable JSON case records."""
import argparse
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ambiance_studio.checks import scrub, write


class Result(unittest.TextTestResult):
    def __init__(self, *args):
        super().__init__(*args)
        self.cases = []
        self.started = time.monotonic()

    def startTest(self, test):
        super().startTest(test)
        self.started = time.monotonic()

    def record(self, test, status, detail=''):
        self.cases.append({'id': scrub(test.id()), 'status': status,
                           'seconds': round(time.monotonic() - self.started, 4),
                           'detail': scrub(detail)[-4096:]})

    def addSuccess(self, test):
        super().addSuccess(test); self.record(test, 'passed')

    def addError(self, test, err):
        super().addError(test, err); self.record(test, 'error', self._exc_info_to_string(err, test))

    def addFailure(self, test, err):
        super().addFailure(test, err); self.record(test, 'failed', self._exc_info_to_string(err, test))

    def addSkip(self, test, reason):
        super().addSkip(test, reason); self.record(test, 'skipped', reason)

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err); self.record(test, 'expected-failure', self._exc_info_to_string(err, test))

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test); self.record(test, 'unexpected-success')

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err:
            self.record(subtest, 'failed', self._exc_info_to_string(err, test))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--directory', type=Path, default=ROOT / 'tests')
    args = parser.parse_args()
    suite = unittest.defaultTestLoader.discover(str(args.directory), pattern='test_*.py')
    result = unittest.TextTestRunner(stream=sys.stderr, resultclass=Result, verbosity=1).run(suite)
    report = {'ok': result.wasSuccessful(), 'tests_run': result.testsRun, 'skipped': len(result.skipped),
              'cases': result.cases}
    write(args.out, report)
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
