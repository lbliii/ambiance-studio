"""Deterministic synthetic inputs for pre-refactor persisted-record fixtures.

These text movie placeholders exercise record identity only, never decoding.
"""
from contextlib import ExitStack, chdir
from datetime import datetime, timezone
import inspect
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import studio


class FixedClock:
    @staticmethod
    def now(tz):
        return datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)


def build(project, api):
    project.mkdir()
    studio.write(project/'project.json', {'version': 1, 'title': 'Painted café 雨', 'reference': None})
    studio.write(project/'pipeline.json', {'version': 1, 'gates': [
        {'id': 'intent', 'name': 'Intent', 'depends': [], 'criteria': [{'id': 'brief', 'text': 'Describe the film'}], 'watch': ['brief.md']} ]})
    studio.write(project/'scene.json', {'version': 1,
        'canvas': {'width': 160, 'height': 160, 'fps': 6, 'loop_seconds': 2, 'background': '#1a1733'},
        'camera': {'overscan': 1.08, 'x_amplitude': 0, 'y_amplitude': 0, 'zoom_amplitude': 0}, 'groups': [], 'layers': [],
        'framing': {'version': 1, 'views': {'portrait': {'rect_scene_px': [35, 0, 90, 160], 'output': {'width': 90, 'height': 160}}}}})
    studio.write(project/'catalog.json', {'version': 1, 'assets': []})
    (project/'brief.md').write_bytes('Painted café 雨\r\nRetain source bytes.\n'.encode())
    studio.write(project/'selection.json', {'format': api.SELECTION, 'schema_version': 1,
        'scene': 'scene.json', 'catalog': 'catalog.json', 'documents': {'brief': 'brief.md'}})
    with ExitStack() as stack:
        for module in {inspect.getmodule(api.capture), inspect.getmodule(api.record_edition)}:
            stack.enter_context(patch.object(module, 'datetime', FixedClock))
        api.capture(project, 'fixture', project/'selection.json')
        # Relative result paths make these synthetic receipts independent of tmpdir.
        with chdir(project):
            for id, view, size in [('legacy', None, (160, 160)), ('portrait', 'portrait', (90, 160))]:
                out = Path('reports')/id
                args = SimpleNamespace(command='render', action='video', revision='fixture', edition=id, view=view, out=out, repeats=1)
                prepared = api.prepare_edition(project, args)
                out.mkdir(parents=True)
                picture = out/'picture.mp4'; picture.write_bytes(b'Synthetic contract fixture, not encoded media.\n')
                verification = {'ok': True, 'report': str(out/'verification.json'), 'width': size[0], 'height': size[1],
                    'fps': 6, 'decoded_frames': 12, 'loop_frames': 12, 'audio': {'tracks': 0}, 'synthetic_unit_fixture': True}
                studio.write(out/'verification.json', verification)
                result = {'ok': True, 'output': str(picture), 'output_sha256': studio.digest(picture), 'verification': verification}
                if view:
                    selected = api.captured_view(project, 'fixture', view)
                    result['view'] = {'view': selected['definition'], 'view_sha256': selected['sha256'],
                                      'output': {'width': size[0], 'height': size[1]}}
                studio.write(out/'render-report.json', result)
                api.record_edition(project, prepared, result, args)
    paths = ['revisions/fixture/manifest.json', 'revisions/fixture/editions/legacy.json', 'revisions/fixture/editions/portrait.json']
    return {Path(name).name: project/name for name in paths}
