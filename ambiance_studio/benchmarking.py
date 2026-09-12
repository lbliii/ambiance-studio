"""Bounded measurements of the actual iteration raster plan; estimates state limits."""
import json
import math
from pathlib import Path
import statistics
import time
from types import SimpleNamespace
import studio
from . import production, rendering, scene_runtime, project_references, record_contracts, revision_capture
from .render_plan import render_context
from .media_inputs import fresh_output


def benchmark(project, request, out):
    record_contracts.fields(request, {'format', 'schema_version', 'recipe', 'sample_count', 'encode_sample_seconds'}, 'benchmark')
    if request.get('format') != 'ambiance-render-benchmark' or request.get('schema_version') != 1: raise ValueError('Expected ambiance-render-benchmark schema_version 1')
    recipe_path = studio.inside(project, request['recipe']); recipe = studio.read(recipe_path); production.validate_recipe(recipe)
    count = request.get('sample_count', 5); encode_seconds = request.get('encode_sample_seconds', 0)
    if type(count) is not int or not 3 <= count <= 20: raise ValueError('Benchmark sample count must be 3–20')
    if type(encode_seconds) not in (int, float) or not math.isfinite(encode_seconds) or not 0 <= encode_seconds <= 5: raise ValueError('Encode sample must be 0–5 seconds')
    revision = recipe['revision'] if revision_capture.manifest_path(project, recipe['revision']).exists() else None
    context = render_context(project, revision); scene = studio.read(context['scene']); catalog = studio.read(context['catalog'])
    T = scene['canvas']['loop_seconds']; fps = scene['canvas']['fps']; frames = round(T*fps)
    if encode_seconds > T or encode_seconds*fps != round(encode_seconds*fps): raise ValueError('Encode sample must fit an integer number of frames inside the picture loop')
    plan = scene_runtime.scene_bridge('view-plan', scene, catalog, {'requests': [{'id': v} for v in recipe.get('views', ['authored'])],
        'options': {k: recipe[k] for k in ['long_edge', 'supersample'] if k in recipe}})
    if encode_seconds and any(v['output'][axis] % 2 for v in plan['views'] for axis in ['width', 'height']): raise ValueError('Encoded sample dimensions must be even')
    out = fresh_output(Path(out)); records = []
    for view in plan['views']:
        args = dict(command='render', action='benchmark', revision=revision, view=view['view']['id'], width=view['output']['width'], height=view['output']['height'],
                    supersample=recipe.get('supersample', 1), start=0, seconds=T, out=out/view['view']['id'],
                    sample_times=[round(i*(frames-1)/(count-1))/fps for i in range(count)])
        report = rendering.run(SimpleNamespace(**args), project)
        sample = report['benchmark']; render_times = [r['render_seconds'] for r in sample['samples']]
        median = statistics.median(render_times); native = None
        if encode_seconds:
            started = time.monotonic()
            native_args = {**args, 'action': 'video', 'out': out/(view['view']['id']+'-encode'), 'seconds': encode_seconds,
                           'repeats': 1, 'bitrate': None, 'audio': None, 'edition': None}
            encoded = rendering.run(SimpleNamespace(**native_args), project)
            native = {'wall_seconds': time.monotonic()-started, 'output_frames': round(encode_seconds*fps),
                      'preroll_frames': frames, 'verification': encoded['verification']['report'], 'report': encoded['report'],
                      'meaning': 'Measured render, native encoding, trimming and full sample verification together.'}
        records.append(dict(view=view['view']['id'], output=view['output'], report=report['report'], initialization_seconds=sample['initialization_seconds'],
                            median_frame_seconds=median, frame_seconds_range=[min(render_times), max(render_times)],
                            picture_render_frames=2*frames, picture_render_estimate_seconds=sample['initialization_seconds']+median*2*frames,
                            peak_rss_bytes=report.get('peak_rss_bytes'), native_sample=native))
    data = dict(format='ambiance-render-benchmark', schema_version=1, ok=True,
        recipe=project_references.ref(project, recipe_path, 'benchmark', 'recipe'), revision=revision,
        subject='captured' if revision else 'working', views=plan, samples=records,
        roles=[{'role': e['role'], 'repeats': e.get('repeats', 1), 'compose_estimate_seconds': None if e['role'] != 'silent' else 0} for e in recipe['editions']],
        picture_render_estimate_seconds=sum(r['picture_render_estimate_seconds'] for r in records), total_estimate_seconds=None,
        uncertainty=['Sample range describes measured source times, not a statistical confidence interval.',
                     'Full run total is unknown: native throughput is coupled to rendering; role composition/verification is not extrapolated from picture-only samples.',
                     'Every view is redrawn and one full preroll loop per picture is included. No settings were changed automatically.'])
    studio.write(out/'benchmark.json', data)
    return {'ok': True, 'report': str(out/'benchmark.json'), 'picture_render_estimate_seconds': data['picture_render_estimate_seconds'],
            'total_estimate_seconds': None, 'views': records, 'uncertainty': data['uncertainty']}
