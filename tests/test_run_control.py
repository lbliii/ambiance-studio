import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import studio
from ambiance_studio import run_control, production
from ambiance_studio.cli import init_project
from ambiance_studio.errors import CommandError


class RunControlTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.project = (Path(self.tmp.name)/'film').resolve(); init_project(self.project, None, 'Run fixture', 'blank')

    def row(self):
        row = dict(id='owned', run_uuid='token', owner=run_control.identity(os.getpid()), pid=os.getpid(), state='running', steps={})
        studio.write(production.run_file(self.project, 'owned'), row); return row

    def test_process_identity_and_reused_pid_fail_closed(self):
        owner = run_control.identity(os.getpid())
        if owner is None: self.skipTest('No supported process identity adapter')
        row = self.row(); self.assertEqual(run_control.owner_state(row), 'verified')
        with patch('ambiance_studio.run_control.identity', return_value={**owner, 'start': 'other'}), patch('ambiance_studio.run_control.os.kill') as kill:
            self.assertEqual(run_control.owner_state(row), 'absent')
            with self.assertRaises(ValueError): run_control.cancel(self.project, 'owned', 'token')
            self.assertTrue(all(call.args[1] == 0 for call in kill.call_args_list))
        with self.assertRaises(CommandError): run_control.cancel(self.project, 'owned', 'old-token')

    def test_progress_is_separate_and_cancellation_reaps_owned_child(self):
        row = self.row(); directory = production.run_file(self.project, 'owned').parent
        with run_control.Tracker(self.project, row) as tracker:
            result = run_control.execute([sys.executable, '-c', "import os,json;os.write(int(os.environ['AMBIANCE_PROGRESS_FD']),b'{\"phase\":\"sample\",\"completed_frames\":2,\"expected_frames\":4}\\n');print(json.dumps({'ok':True}))"], None)
            self.assertTrue(json.loads(result.stdout)['ok']); tracker.write()
            progress = studio.read(directory/'progress.json'); self.assertEqual(progress['completed_frames'], 2)
            self.assertEqual(run_control.effective(row, self.project)['effective_state'], 'running')
            timer = threading.Timer(.3, lambda: studio.write(directory/'cancel.json', {'run_uuid': 'token'})); timer.start()
            try:
                with self.assertRaises(KeyboardInterrupt): run_control.execute([sys.executable, '-c', 'import time;time.sleep(30)'], None)
            finally: timer.join()
            self.assertEqual(tracker.children, {})

    def test_reconcile_absent_owner_preserves_completed_output_and_selection(self):
        row = self.row(); row['pid'] = 99999999; row['owner'] = None
        path = production.run_file(self.project, 'owned'); studio.write(path, row); (path.parent/'active.lock').write_text('')
        result = run_control.reconcile(self.project, 'owned')
        self.assertEqual(result['state'], 'interrupted'); self.assertFalse((path.parent/'active.lock').exists())
        self.assertFalse((self.project/'presentations').exists())


if __name__ == '__main__': unittest.main()
