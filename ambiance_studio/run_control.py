"""Owned local run lifecycle. No PID-only signaling and no background scheduler."""
import contextvars
import ctypes
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import threading
import time
import uuid

import studio
from .project import project_lock
from .errors import CommandError

ACTIVE = contextvars.ContextVar('ambiance_run', default=None)


def identity(pid):
    if type(pid) is not int or pid <= 0: return None
    try:
        host = platform.node()
        if platform.system() == 'Darwin':
            # sys/proc_info.h: PROC_PIDTBSDINFO, including microsecond start identity.
            class BSDInfo(ctypes.Structure):
                _fields_ = [('prefix', ctypes.c_uint32*12), ('comm', ctypes.c_char*16), ('name', ctypes.c_char*32),
                            ('fields', ctypes.c_uint32*6), ('start_sec', ctypes.c_uint64), ('start_usec', ctypes.c_uint64)]
            info = BSDInfo(); lib = ctypes.CDLL('/usr/lib/libproc.dylib', use_errno=True)
            lib.proc_pidinfo.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_int]
            count = lib.proc_pidinfo(pid, 3, 0, ctypes.byref(info), ctypes.sizeof(info))
            if count != ctypes.sizeof(info) or info.prefix[3] != pid: return None
            birth = f'{info.start_sec}.{info.start_usec:06d}'
        elif platform.system() == 'Linux':
            values = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
            birth = Path('/proc/sys/kernel/random/boot_id').read_text().strip()+':'+values[19]
        else: return None
        return {'host': host, 'pid': pid, 'start': birth}
    except (OSError, ValueError, IndexError, AttributeError): return None


def owner_state(row):
    owner = row.get('owner'); pid = row.get('pid')
    if owner and owner.get('host') != platform.node(): return 'unknown'
    try:
        if type(pid) is not int or pid <= 0: return 'unknown'
        os.kill(pid, 0)
    except ProcessLookupError: return 'absent'
    except PermissionError: return 'unknown'
    current = identity(pid)
    if owner and current:
        return 'verified' if owner == current else 'absent'
    return 'unknown'


def effective(row, project=None):
    raw = row.get('state', 'unknown')
    if raw != 'running': return {'effective_state': raw, 'state_reason': None}
    state = owner_state(row)
    if state == 'absent': return {'effective_state': 'interrupted', 'state_reason': 'Recorded owner is absent or PID has been reused.'}
    if state == 'unknown': return {'effective_state': 'unknown', 'state_reason': 'Owner identity cannot be verified.'}
    try:
        progress = studio.read(project/'runs'/row['id']/'progress.json')
        if progress['run_uuid'] != row['run_uuid']: raise ValueError('Old progress')
        age = time.time()-datetime.fromisoformat(progress['heartbeat_utc']).timestamp()
        state = 'running' if age <= 15 else 'unresponsive'
        result = {'effective_state': state, 'state_reason': None if state == 'running' else 'Owner heartbeat is stale.', 'progress': progress}
        if time.time()-progress.get('advanced_at', time.time()) > 15: result['state_reason'] = 'Owner present; no recent work advancement.'
        return result
    except (OSError, ValueError, KeyError, TypeError):
        return {'effective_state': 'unknown', 'state_reason': 'Verified owner has no matching heartbeat.'}


class Tracker:
    def __init__(self, project, state):
        self.project = project; self.state = state; self.directory = project/'runs'/state['id']
        self.stop = threading.Event(); self.lock = threading.RLock(); self.sequence = 0; self.children = {}
        self.data = dict(format='ambiance-run-progress', schema_version=1, run_uuid=state['run_uuid'], phase='starting',
                         advanced_at=time.time(), completed_frames=None, expected_frames=None, throughput_fps=None)
        self.last_sample = None; self.error = None

    def __enter__(self):
        self.write(); self.token = ACTIVE.set(self)
        self.thread = threading.Thread(target=self.heartbeat, daemon=True); self.thread.start(); return self

    def __exit__(self, *args):
        self.stop.set(); self.thread.join(timeout=2)
        try: self.write()
        finally: ACTIVE.reset(self.token)

    def heartbeat(self):
        while not self.stop.wait(1):
            try: self.write()
            except OSError as error: self.error = error; return

    def write(self):
        with self.lock:
            self.sequence += 1
            studio.write(self.directory/'progress.json', {**self.data, 'sequence': self.sequence,
                'heartbeat_utc': datetime.now(timezone.utc).isoformat(), 'children': list(self.children.values())})

    def update(self, event):
        with self.lock:
            allowed = ['phase', 'completed_frames', 'expected_frames', 'preroll_frames', 'encoded_frames']
            data = {k: event[k] for k in allowed if k in event}
            for k, value in data.items():
                if k == 'phase':
                    if not isinstance(value, str) or len(value) > 160: return
                elif value is not None and (type(value) is not int or value < 0): return
            current = data.get('completed_frames'); now = time.monotonic()
            phase_changed = data.get('phase', self.data['phase']) != self.data['phase']
            if phase_changed:
                for field in ['completed_frames', 'expected_frames', 'preroll_frames', 'encoded_frames', 'throughput_fps']: self.data[field] = None
                self.last_sample = None
            if current is not None:
                if self.last_sample and data.get('phase', self.data['phase']) == self.data['phase'] and current >= self.last_sample[1]:
                    self.data['throughput_fps'] = (current-self.last_sample[1])/max(.001, now-self.last_sample[0])
                self.last_sample = (now, current)
            if any(self.data.get(k) != v for k, v in data.items()): self.data['advanced_at'] = time.time()
            self.data.update(data)
        if phase_changed: self.write()

    def check_cancel(self):
        if self.error: raise self.error
        path = self.directory/'cancel.json'
        if path.exists() and studio.read(path).get('run_uuid') == self.state['run_uuid']:
            raise KeyboardInterrupt('Iteration cancelled')


def execute(command, request):
    tracker = ACTIVE.get()
    if tracker is None:
        return subprocess.run(command, input=request, capture_output=True, text=True)
    tracker.check_cancel(); read_fd, write_fd = os.pipe()
    env = {**os.environ, 'AMBIANCE_PROGRESS_FD': str(write_fd)}
    try:
        child = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 text=True, env=env, pass_fds=(write_fd,))
    except BaseException:
        os.close(read_fd); os.close(write_fd); raise
    os.close(write_fd); owner = identity(child.pid)
    if owner:
        with tracker.lock: tracker.children[child.pid] = owner
    def events():
        with os.fdopen(read_fd) as stream:
            while line := stream.readline(4097):
                if len(line) > 4096: continue
                try: tracker.update(json.loads(line))
                except (ValueError, TypeError, AttributeError): pass
    reader = threading.Thread(target=events, daemon=True); reader.start()
    first = True
    try:
        while True:
            tracker.check_cancel()
            try:
                stdout, stderr = child.communicate(input=request if first else None, timeout=.25)
                tracker.check_cancel()
                return subprocess.CompletedProcess(command, child.returncode, stdout, stderr)
            except subprocess.TimeoutExpired: first = False
    finally:
        if child.poll() is None and owner and identity(child.pid) == owner:
            child.terminate()
            try: child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                if identity(child.pid) == owner: child.kill(); child.wait(timeout=5)
        with tracker.lock: tracker.children.pop(child.pid, None)
        reader.join(timeout=1)
        for stream in [child.stdin, child.stdout, child.stderr]:
            if stream and not stream.closed: stream.close()


def live_children(project, row):
    path = project/'runs'/row['id']/'progress.json'
    if not path.exists(): return []
    progress = studio.read(path)
    if progress.get('run_uuid') != row.get('run_uuid'): return []
    return [owner for owner in progress.get('children', []) if owner.get('host') == platform.node() and identity(owner.get('pid')) == owner]


def cancel(project, id, expected):
    from .production import run_file
    path = run_file(project, id)
    with project_lock(project):
        row = studio.read(path)
        if row.get('run_uuid') != expected: raise CommandError('Run identity changed.', 'stale_run', 2)
        if row['state'] != 'running': return {'ok': True, 'state': row['state'], 'signalled': False}
        state = owner_state(row)
        children = live_children(project, row)
        if state == 'absent' and children:
            for owner in children:
                if identity(owner['pid']) == owner: os.kill(owner['pid'], signal.SIGTERM)
            return {'ok': True, 'state': 'orphan-cleanup-requested', 'signalled_children': len(children), 'next': 'Reconcile after owned children exit.'}
        if state != 'verified': raise ValueError('Run owner is unverified or absent; inspect/reconcile without signaling')
        studio.write(path.parent/'cancel.json', {'run_uuid': expected, 'requested_utc': datetime.now(timezone.utc).isoformat()})
    deadline = time.monotonic()+3
    while time.monotonic() < deadline:
        latest = studio.read(path)
        if latest.get('run_uuid') != expected or latest['state'] != 'running': return {'ok': True, 'requested': True, 'state': latest['state']}
        time.sleep(.1)
    latest = studio.read(path)
    signalled = False
    if latest.get('run_uuid') == expected and latest['state'] == 'running' and owner_state(latest) == 'verified':
        os.kill(latest['pid'], signal.SIGINT); signalled = True
    return {'ok': True, 'requested': True, 'signalled': signalled, 'state': 'cancellation-requested', 'inspect': str(path)}


def reconcile(project, id):
    from . import production, deliveries
    path = production.run_file(project, id)
    with project_lock(project):
        row = studio.read(path)
        if row['state'] != 'running': return {'ok': True, 'state': row['state'], 'changed': False}
        if live_children(project, row): raise ValueError('Owned children are still active; cancel the exact run before reconciliation')
        if owner_state(row) != 'absent': raise ValueError('Owner is not demonstrably absent; reconciliation refused')
        for step in row.get('steps', {}).values():
            if any(not deliveries.intact(project, ref)['ok'] for ref in step.get('outputs', [])):
                raise ValueError('Completed step evidence changed; preserved run requires inspection')
        lock = path.parent/'active.lock'
        if lock.exists() and lock.read_text().strip() and studio.read(lock).get('run_uuid') != row.get('run_uuid'):
            raise ValueError('Run lock identity differs')
        row.update(state='interrupted', error='Owner disappeared; completed output identities checked.', updated_utc=datetime.now(timezone.utc).isoformat())
        studio.write(path, row); lock.unlink(missing_ok=True)
    return {'ok': True, 'state': 'interrupted', 'changed': True, 'path': str(path)}
