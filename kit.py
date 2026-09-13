#!/usr/bin/env python3
"""Local validation entry point; scene semantics are evaluated by the shared Node engine."""
import argparse
import functools
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parent

def read(path):
    return json.loads(path.read_text())

def validate(scene_path, catalog_path=None, project_root=None):
    errors = []
    scene = read(scene_path)
    catalog_path = Path(catalog_path) if catalog_path else ROOT/'assets/catalog.json'
    asset_root = Path(project_root).resolve(strict=True) if project_root is not None else catalog_path.resolve().parent.parent
    if not asset_root.is_dir(): raise ValueError('Project asset root must be a directory')
    catalog = read(catalog_path)
    def require(ok, message):
        if not ok: errors.append(message)
    def number(value):
        return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)
    def positive(value):
        return number(value) and value > 0
    assets = {}
    for asset in catalog['assets']:
        id = asset['id']
        require(id not in assets, f'Duplicate asset: {id}')
        assets[id] = asset
        path = (asset_root/asset['file']).resolve()
        if not path.is_relative_to(asset_root) or not path.is_file():
            errors.append(f'Asset missing or outside kit: {id}')
            continue
        data = path.read_bytes()
        require(hashlib.sha256(data).hexdigest() == asset['sha256'], f'Asset changed: {id}')
        if data[:8] != b'\x89PNG\r\n\x1a\n' or len(data) < 24:
            errors.append(f'Invalid PNG header: {id}')
            continue
        size = struct.unpack('>II', data[16:24])
        require(size == (asset['width'],asset['height']), f'Dimension mismatch: {id}')
        if asset['kind'] == 'atlas':
            a = asset['atlas']
            require(size == (a['columns']*a['cell_width'],a['rows']*a['cell_height']), f'Atlas grid mismatch: {id}')
            require(0 < a['frame_count'] <= a['columns']*a['rows'], f'Atlas frame count: {id}')
    c = scene['canvas']
    duration = c['loop_seconds']
    require(scene['version'] == 1, 'Unsupported scene version')
    for key in ['width','height','fps','loop_seconds']:
        require(positive(c[key]), f'Canvas {key} must be positive')
    if not all(positive(c[k]) for k in ['width','height','fps','loop_seconds']):
        return dict(ok=False, errors=errors)
    require(float(duration*c['fps']).is_integer(), 'Loop must contain a whole number of output frames')
    for key in ['width','height','fps']:
        require(float(c[key]).is_integer(), f'Canvas {key} must be an integer')
    camera = scene['camera']
    require(positive(camera['overscan']) and camera['overscan'] >= 1, 'Overscan must be at least 1')
    for key in ['x_amplitude','y_amplitude','zoom_amplitude']:
        require(number(camera[key]), f'Camera {key} must be finite')
    groups = {}
    for group in scene['groups']:
        id = group['id']
        require(id not in groups, f'Duplicate group: {id}')
        groups[id] = group
        for key in ['depth','x','y','scale']:
            require(number(group[key]), f'{id}: {key} must be finite')
        require(positive(group['scale']), f'{id}: scale must be positive')
        require(len(group['pivot']) == 2 and all(number(n) for n in group['pivot']), f'{id}: invalid pivot')
    ids = set()
    cycles = []
    for layer in scene['layers']:
        id = layer['id']
        require(id not in ids, f'Duplicate layer: {id}')
        ids.add(id)
        require(layer['asset'] in assets, f'{id}: unknown asset')
        if 'attach' in layer:
            require('group' not in layer and 'depth' not in layer, f'{id}: attached layer inherits group and depth')
        elif 'group' in layer:
            require(layer['group'] in groups, f'{id}: unknown group')
            require('depth' not in layer, f'{id}: grouped layer must inherit depth')
        else:
            require(number(layer.get('depth')), f'{id}: missing depth')
        for key in ['x','y','width','height','scale','rotation','opacity']:
            require(number(layer[key]), f'{id}: {key} must be finite')
        require(all(positive(layer[k]) for k in ['width','height','scale']), f'{id}: dimensions/scale must be positive')
        require(number(layer['opacity']) and 0 <= layer['opacity'] <= 1, f'{id}: opacity out of range')
        require(isinstance(layer['visible'],bool), f'{id}: visible must be boolean')
        require(layer['blend'] in ['source-over','screen','multiply'], f'{id}: unsupported blend')
        require(len(layer['anchor']) == 2 and all(number(n) and 0 <= n <= 1 for n in layer['anchor']), f'{id}: invalid anchor')
        if 'motion' in layer:
            motion = layer['motion']
            require(positive(motion['cycles']) and float(motion['cycles']).is_integer(), f'{id}: motion cycles must be positive whole cycles')
            for key in ['x_amplitude','y_amplitude','phase']:
                require(number(motion[key]), f'{id}: motion {key} must be finite')
            require(number(motion.get('rotation_amplitude',0)), f'{id}: invalid rotation motion')
        asset = assets.get(layer['asset'])
        if asset and asset['kind'] == 'atlas':
            cycle = layer.get('cycle_seconds')
            require(positive(cycle), f'{id}: missing positive cel cycle')
            if positive(cycle):
                if scene.get('clock', {}).get('mode') != 'finite' and 'local_cycle' not in layer:
                    require(abs(duration/cycle-round(duration/cycle)) < 1e-8, f'{id}: cel cycle must divide visual loop')
                cycles.append(dict(layer=id, seconds=cycle))
            phase = layer.get('phase_frames',0)
            require(number(phase) and float(phase).is_integer() and phase >= 0, f'{id}: phase must be a non-negative integer')
    if 'audio' in scene:
        a = scene['audio']['loop_seconds']
        require(positive(a) and abs(a/duration-round(a/duration)) < 1e-8, 'Audio duration must be a whole number of picture loops')
    timing = None
    if not errors:
        node = shutil.which('node')
        require(node is not None, 'Node is required for shared scene timing validation.')
        if node:
            process = subprocess.run([node, str(ROOT/'tools/scene-command.mjs')],
                input=json.dumps({'action':'timing','scene':scene,'catalog':catalog}), capture_output=True, text=True)
            try:
                result=json.loads(process.stdout)
                require(process.returncode == 0 and result.get('ok'), 'Scene timing validation failed: '+str(result.get('error','unknown error')))
                if result.get('ok'):
                    timing=result['data'];by_layer={r['layer']:r for r in timing['layers']}
                    for entry in cycles:
                        row=by_layer[entry['layer']];fallback=row['fallback_cycle']
                        entry.update(cel_fps=fallback['nominal_cel_fps'] if row['timing_driver']=='cycle' else None,
                            timing_driver=row['timing_driver'],fallback_cycle=fallback,
                            timing_summary={'authored_rate_segments':row['authored']['rate_segments'],
                                'sampled_cel_transitions':row['sampled']['cel_transitions'],
                                'unpresented_authored_holds':len(row['sampled']['unpresented_authored_holds'])})
            except (ValueError,KeyError,TypeError):
                errors.append('Scene timing runtime returned an invalid result: '+process.stderr.strip())
    if any('attach' in l or 'sockets' in l for l in scene['layers']):
        node = shutil.which('node')
        require(node is not None, 'Node is required to validate attachment graphs.')
        if node:
            result = subprocess.run([node, str(ROOT/'tools/check-scene.mjs'), str(scene_path.resolve()), '--catalog', str(catalog_path.resolve()), '--project-root', str(asset_root)], capture_output=True, text=True)
            require(result.returncode == 0, 'Attachment/scene audit failed: '+result.stdout if result.returncode else '')
    return dict(ok=not errors, scene=scene['id'], asset_count=len(assets), layer_count=len(ids),
                export_frame_count=round(duration*c['fps']), cycles=cycles, timing=timing, errors=errors,
                limits=['PNG headers and hashes checked; no pixel alpha/edge analysis.',
                        'No rendered video, audio, or aesthetic validation performed by this command.'])

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command',required=True)
    sub.add_parser('doctor',help='Report available local runtimes; never installs anything')
    check = sub.add_parser('check',help='Check assets, atlas geometry, references, and loop timing')
    check.add_argument('scene',nargs='?',default=str(ROOT/'scenes/last-lantern.json'))
    check.add_argument('--report',type=Path)
    serve = sub.add_parser('serve',help='Serve the local editor, read-only, on localhost')
    serve.add_argument('--port',type=int,default=8781)
    args = parser.parse_args()
    if args.command == 'doctor':
        print(json.dumps(dict(python=platform.python_version(),platform=platform.system(),
                              node=shutil.which('node'),ffmpeg=shutil.which('ffmpeg'),
                              ffprobe=shutil.which('ffprobe'),
                              prototype_requirements='Python 3.9+ and a modern browser',
                              note='Node is used only for engine verification. FFmpeg is a future export dependency.'),indent=2))
    elif args.command == 'check':
        try: report = validate(Path(args.scene))
        except (KeyError,TypeError,ValueError,OSError) as error:
            report = dict(ok=False,errors=[f'Malformed or unreadable input: {error}'])
        result = json.dumps(report,indent=2)+'\n'
        print(result,end='')
        if args.report:
            args.report.parent.mkdir(parents=True,exist_ok=True)
            args.report.write_text(result)
        return 0 if report['ok'] else 1
    else:
        handler = functools.partial(SimpleHTTPRequestHandler,directory=str(ROOT))
        server = ThreadingHTTPServer(('127.0.0.1',args.port),handler)
        print(f'Open http://127.0.0.1:{args.port}/editor/ — Ctrl-C stops the server.',flush=True)
        try: server.serve_forever()
        except KeyboardInterrupt: pass
        finally: server.server_close()
    return 0

if __name__ == '__main__': sys.exit(main())
