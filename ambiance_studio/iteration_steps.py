"""Durable step checkpoints and recovery of already-recorded media editions."""
import time

import studio
from . import deliveries, editions, project_references, record_contracts
from .media_operations import MediaExecutor, MediaRequest, request_argv
from .production_queries import saved_step_result


def run_file(project, id):
    return studio.inside(project, f'runs/{record_contracts.identifier(id)}/run.json')


class IterationProgress:
    def __init__(self, project, state, tracker, executor: MediaExecutor):
        self.project = project
        self.state = state
        self.tracker = tracker
        self.executor = executor
        self.path = run_file(project, state['id'])
        self.directory = self.path.parent
        self.started = time.monotonic()

    def save(self, stage):
        self.tracker.update({'phase': stage})
        if stage not in ['interrupted', 'failed', 'complete']:
            self.tracker.check_cancel()
        self.state.update(stage=stage, updated_utc=deliveries.now(), elapsed_seconds=time.monotonic()-self.started)
        studio.write(self.path, self.state)

    def record(self, name, result, elapsed=None):
        files = [result['output'], result['report'], result['verification']['report']]
        if result.get('edition'):
            files.append(result['edition']['receipt'])
        outputs = [deliveries.reference(self.project, project_references.relative(self.project, file)) for file in files]
        record = {'result': saved_step_result(result), 'outputs': outputs}
        if elapsed is not None:
            record['elapsed_seconds'] = elapsed
        self.state['steps'][name] = record
        self.save(name)
        return result

    def recover(self, request: MediaRequest):
        """An edition may have been committed just before the last checkpoint."""
        path = editions.edition_path(self.project, request.revision, request.edition)
        if not path.exists():
            return None
        receipt = editions.load_edition(self.project, request.revision, request.edition)
        output_dir = studio.inside(self.project, receipt['output']['path']).parent
        if output_dir.parent != self.directory:
            raise ValueError('Existing edition belongs to a different production run')
        report = output_dir/request.report_name
        result = studio.read(report)
        result.update(report=str(report), edition={'id': request.edition, 'revision': request.revision, 'receipt': str(path)})
        if not result.get('ok'):
            raise ValueError('Recorded edition has no completed production report')
        for item in receipt['dependencies']:
            if not deliveries.intact(self.project, item)['ok']:
                raise ValueError('Recorded edition changed while the run was interrupted')
        return result

    def step(self, name, request: MediaRequest):
        self.save(name)
        completed = self.state['steps'].get(name)
        if completed:
            for item in completed['outputs']:
                if not deliveries.intact(self.project, item)['ok']:
                    raise ValueError(f'Completed {name} output changed; use a new iteration ID')
            return completed['result']
        recovered = self.recover(request)
        if recovered is not None:
            return self.record(name, recovered)
        attempt = self.state['attempts'].get(name, 0)+1
        self.state['attempts'][name] = attempt
        out = self.directory/f'{name}-{attempt}'
        self.state['active_command'] = request_argv(self.project, request, out)
        self.save(name)
        started = time.monotonic()
        result = self.executor(self.project, request, out)
        if not result.get('ok', True):
            raise ValueError(f'{name} failed; inspect {out}')
        return self.record(name, result, time.monotonic()-started)
