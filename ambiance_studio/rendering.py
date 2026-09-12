"""Deterministic scene raster proofs and a native macOS delivery adapter.

All render outputs are fresh directories. This module never changes source art,
scene, catalog, or review records. Native encode/decode is an explicit capability.
"""
import hashlib
import io
import json
import math
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
import wave

from .file_identity import digest as _digest
from .native_sources import compilation_sources, source_identity as native_source_identity

ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / 'tools/render-scene.mjs'
NATIVE_SOURCE = ROOT / 'native/media/media.m'


def add_parsers(sub):
    group = sub.add_parser('render', help='Render saved scene frames, motion proofs, or video').add_subparsers(dest='action', required=True)
    q = group.add_parser('benchmark'); q.add_argument('file', type=Path); q.add_argument('--out', type=Path, required=True)
    for action in ['frame', 'proof', 'rig-proof', 'look-proof', 'video', 'views-proof']:
        q = group.add_parser(action)
        q.add_argument('--revision', help='Verified captured revision ID; never falls back to working scene')
        if action in ['rig-proof', 'look-proof']:
            q.add_argument('recipe', type=Path)
        q.add_argument('--out', type=Path, required=True, help='Fresh output directory; never overwrites')
        if action == 'views-proof':
            q.add_argument('--view', action='append', dest='views', required=True, help='Saved view ID; repeat for synchronized outputs')
            q.add_argument('--long-edge', type=int, default=640, help='Maximum preview side; preserve an integer aspect ratio')
        else:
            q.add_argument('--width', type=int, default=360 if action in ['rig-proof','look-proof'] else None)
            q.add_argument('--height', type=int, help='Defaults to the selected view or authored aspect ratio')
            if action in ['frame', 'proof', 'video']:
                q.add_argument('--view', help='Saved view ID; omission preserves the full authored canvas')
        if action != 'rig-proof':
            q.add_argument('--supersample', type=int, choices=[1, 2, 4], default=1, help='Render geometry at this scale then downsample once; internal dimensions must remain <=4096')
        if action == 'frame':
            q.add_argument('--time', type=float, default=0)
        elif action not in ['rig-proof', 'look-proof']:
            q.add_argument('--start', type=float, default=0)
            q.add_argument('--seconds', type=float, help='Integer frame duration within one loop; proof default 3 seconds')
        if action == 'proof':
            q.add_argument('--disable', action='append', default=[], metavar='LAYER', help='Add a synchronized comparison with this layer hidden; repeatable')
        if action == 'video':
            _edition_arguments(q)
            q.add_argument('--bitrate', type=int)
            q.add_argument('--repeats', type=int, default=1)
            q.add_argument('--audio', type=Path, help='Selected stereo 48 kHz PCM WAV matching the final duration exactly')
    group = sub.add_parser('media', help='Decode and inspect actual encoded deliverables').add_subparsers(dest='action', required=True)
    q = group.add_parser('verify')
    q.add_argument('file', type=Path)
    q.add_argument('--revision'); q.add_argument('--edition'); q.add_argument('--view')
    q.add_argument('--out', type=Path, required=True, help='Fresh report/contact directory')
    for field in ['width', 'height', 'fps', 'frames', 'loop-frames']:
        q.add_argument('--'+field, type=int, help='Defaults to the selected scene')
    q.add_argument('--audio-tracks', type=int, choices=[0, 1])
    q.add_argument('--contact-time', type=float, action='append', default=[])
    q.add_argument('--contact-frame', type=int, action='append', default=[])
    q = group.add_parser('compose', help='Reuse encoded CFR H.264 picture with selected PCM, then verify')
    q.add_argument('picture', type=Path)
    q.add_argument('--picture-receipt', help='Project-relative existing render report binding this picture to the selected revision')
    q.add_argument('--audio', type=Path, required=True)
    q.add_argument('--repeats', type=int, default=1)
    q.add_argument('--out', type=Path, required=True)
    q.add_argument('--revision')
    q.add_argument('--view', help='Assert the picture view when binding a revision edition')
    _edition_arguments(q)


def _edition_arguments(parser):
    parser.add_argument('--edition')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--audio-session', help='Project-relative executable session for edition dependency closure')
    group.add_argument('--audio-run', help='Project-relative existing CLI audio run for edition dependency closure')
    group.add_argument('--audio-provenance', help='Project-relative explicit external preparation declaration')


def capabilities():
    """Discovery only: availability is not a performed native encode/decode test."""
    node = shutil.which('node')
    canvas = {'ok': False, 'error': 'Node is unavailable'}
    if node:
        try:
            result = subprocess.run([node, str(RENDERER), '--probe'], capture_output=True, text=True, timeout=20)
            canvas = json.loads(result.stdout)
        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
            canvas = {'ok': False, 'error': str(error)}
    override = os.environ.get('AMBIANCE_MEDIA_BINARY')
    native = {'platform': platform.system(), 'supported_platform': platform.system() == 'Darwin',
              'compiler': shutil.which('xcrun'), 'override': override,
              'available': platform.system() == 'Darwin' and (bool(Path(override).is_file() and os.access(override, os.X_OK)) if override else bool(shutil.which('xcrun'))),
              'media_services_tested': False}
    return {'raster': canvas, 'native_media': native,
            'frame_render': bool(canvas.get('ok')), 'motion_proof': bool(canvas.get('ok')),
            'named_view_render': bool(canvas.get('ok')), 'views_proof': bool(canvas.get('ok')),
            'final_video_export': bool(canvas.get('ok') and native['available']),
            'media_verify': native['available'], 'media_compose': native['available'], 'rig_proof': bool(canvas.get('ok')), 'look_proof': bool(canvas.get('ok')), 'supersampled_render': bool(canvas.get('ok'))}


def _error(message, code='invalid_input', exit_code=2):
    from .errors import CommandError
    raise CommandError(message, code, exit_code)


def _json_command(command, request=None, allow_check_failure=False):
    from .run_control import execute, ACTIVE
    tracker = ACTIVE.get()
    if tracker and len(command) > 1 and str(command[1]) in ['compose', 'verify', 'probe']:
        tracker.update({'phase': 'media-'+str(command[1])})
    result = execute(list(map(str, command)), json.dumps(request, allow_nan=False) if request is not None else None)
    try:
        data = json.loads(result.stdout)
    except ValueError:
        _error('Renderer/media runtime failed: '+(result.stderr.strip() or result.stdout.strip()), 'runtime_error', 3)
    if (result.returncode or not data.get('ok', True)) and not allow_check_failure:
        _error(data.get('error') or result.stderr.strip() or 'Renderer/media operation failed', 'runtime_error', 3)
    return data


def _native_binary(project):
    if platform.system() != 'Darwin':
        _error('Native video encode/verify requires macOS AVFoundation. Raster frame and HTML proofs are available with Node Canvas.', 'missing_dependency', 3)
    override = os.environ.get('AMBIANCE_MEDIA_BINARY')
    if override:
        binary = Path(override).resolve()
        if not binary.is_file() or not os.access(binary, os.X_OK):
            _error('AMBIANCE_MEDIA_BINARY must point to an executable native media backend.', 'missing_dependency', 3)
        return binary
    compiler = shutil.which('xcrun')
    if not compiler:
        _error('Native media requires Xcode command-line tools (xcrun clang).', 'missing_dependency', 3)
    version = subprocess.run([compiler, 'clang', '--version'], capture_output=True).stdout
    sources = native_source_identity(NATIVE_SOURCE.parent)
    identity = hashlib.sha256(sources['sha256'].encode()+platform.platform().encode()+version).hexdigest()
    cache = project / '.ambiance/native' / identity
    binary = cache / 'media'
    if not binary.exists():
        cache.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='build-', dir=cache) as temp:
            output = Path(temp)/'media'
            command = [compiler, 'clang', '-O2', '-fobjc-arc', '-Wno-deprecated-declarations']
            for framework in ['Foundation', 'AVFoundation', 'CoreMedia', 'CoreVideo', 'ImageIO', 'CoreGraphics']:
                command += ['-framework', framework]
            command += [*map(str, compilation_sources(NATIVE_SOURCE.parent)), '-o', str(output)]
            result = subprocess.run(command, capture_output=True, text=True)
            if result.returncode:
                _error('Native media build failed: '+result.stderr.strip(), 'runtime_error', 3)
            try:
                os.link(output, binary)
            except FileExistsError:
                pass
    return binary


def _fresh(path):
    path = Path(path).resolve()
    if path.exists():
        _error(f'Output already exists; choose a fresh directory: {path}')
    return path


def _positive_integer(value, name):
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        _error(f'{name} must be a positive integer')
    return value


def _context(project, revision=None):
    if revision:
        from . import revisions
        return revisions.render_context(project, revision)
    from .project import locations
    scene, catalog = locations(project)
    return {'scene':scene, 'catalog':catalog}


def _scene(project):
    return json.loads(_context(project)['scene'].read_text())


def _verify(project, binary, source, out, width, height, fps, frames, audio_tracks, loop_frames, contact_times=None, contact_frames=None):
    source = Path(source).resolve()
    if not source.is_file():
        _error(f'Media file does not exist: {source}')
    for name, value in [('width', width), ('height', height), ('fps', fps), ('frames', frames), ('loop_frames', loop_frames)]:
        _positive_integer(value, name)
    requests = requested_contacts(contact_times or [], contact_frames or [], fps, frames)
    out = _fresh(out)
    out.mkdir(parents=True)
    contacts = out/'contacts'
    contacts.mkdir()
    report = out/'media-report.json'
    source_hash = _digest(source)
    data = _json_command([binary, 'verify', source, width, height, fps, frames, audio_tracks, report, contacts, loop_frames, ','.join(str(r['frame_index']) for r in requests)], allow_check_failure=True)
    after_hash = _digest(source)
    data['input_unchanged'] = source_hash == after_hash
    if not data['input_unchanged']:
        data['ok'] = False
        data['error'] = 'Media input changed while it was being decoded; this report is not valid for either version.'
    data.update({'input_sha256': source_hash, 'input_sha256_after': after_hash,
                 'native_binary_sha256': _digest(binary),
                 'native_source_sha256': _digest(NATIVE_SOURCE),
                 'native_sources': native_source_identity(NATIVE_SOURCE.parent),
                 'report': str(report), 'contacts': str(contacts)})
    data['requested_contacts'] = []
    for request in requests:
        image = contacts/f"decoded-{request['frame_index']:04d}.png"
        if not image.is_file():
            data['ok'] = False
            data['error'] = 'A requested decoded contact was not produced.'
            continue
        data['requested_contacts'].append({**request, 'resolved_path':str(image), 'path_base':'absolute', 'sha256':_digest(image)})
    data['contact_selection'] = 'CFR floor(time*fps), snapping values within 1e-7 frame of an integer boundary; valid times are [0,duration). No VFR support.'
    report.write_text(json.dumps(data, indent=2, allow_nan=False)+'\n')
    return data


def run(args, project):
    from .scene_runtime import require_node, load_scene_json, scene_bridge
    project = Path(project).resolve()
    if args.command == 'media' and args.action == 'compose':
        return compose(args, project)
    context = _context(project, getattr(args, 'revision', None))
    scene_bytes = Path(context['scene']).read_bytes()
    scene = load_scene_json(scene_bytes)
    canvas = scene['canvas']
    loop_frames = canvas['fps'] * canvas['loop_seconds']
    if args.command == 'media':
        out = _fresh(args.out)
        source = args.file.resolve()
        if not source.is_file():
            _error(f'Media file does not exist: {source}')
        defaults={**canvas,'frames':int(loop_frames),'loop_frames':int(loop_frames),'audio_tracks':0};subject=None;edition_path=None
        if getattr(args,'edition',None):
            from . import revisions
            if not args.revision:_error('--edition requires --revision')
            edition=revisions.load_edition(project,args.revision,args.edition)
            if _digest(source)!=edition['output']['sha256']:_error('Media bytes differ from the selected edition')
            view=revisions.edition_view(project,edition)
            if args.view is not None and args.view!=view['id']:_error('Verification view differs from the selected edition')
            edition_path=revisions.edition_path(project,args.revision,args.edition);edition_hash=_digest(edition_path)
            if edition['schema_version']==2:defaults.update(edition['output_expectations'])
            else:
                verification_path=_project_input(project,edition['verification']['path'])
                if _digest(verification_path)!=edition['verification']['sha256']:_error('Selected edition verification receipt changed')
                verified=json.loads(verification_path.read_text())
                for key,source_key in [('width','width'),('height','height'),('fps','fps'),('frames','decoded_frames'),('loop_frames','loop_frames')]:
                    if source_key in verified:defaults[key]=int(verified[source_key])
                defaults['audio_tracks']=verified.get('audio',{}).get('tracks',0)
            subject={'revision':args.revision,'revision_sha256':context['manifest_sha256'],'edition':args.edition,'edition_sha256':edition_hash,'view':view['id'],'view_sha256':view['sha256']}
        elif getattr(args,'view',None):
            from . import views
            row=views.inspect(project,args.view,getattr(args,'revision',None))['views'][args.view]
            defaults.update(row['output']);subject={'revision':getattr(args,'revision',None),'view':args.view,'view_sha256':row['view_sha256']}
        expected={field:getattr(args,field) if getattr(args,field,None) is not None else defaults[field] for field in ['width','height','fps','frames','loop_frames','audio_tracks']}
        result=_verify(project,_native_binary(project),source,out,**expected,contact_times=args.contact_time,contact_frames=args.contact_frame)
        if getattr(args,'revision',None):_context(project,args.revision)
        if edition_path and _digest(edition_path)!=edition_hash:_error('Edition receipt changed during verification')
        if subject:
            result['subject']=subject;Path(result['report']).write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
        return result
    out = _fresh(args.out)
    supersample = getattr(args, 'supersample', 1)
    selected = getattr(args, 'views', None) or ([args.view] if getattr(args, 'view', None) else None)
    view_requests = None
    if selected:
        catalog_bytes = Path(context['catalog']).read_bytes()
        view_requests = [{'id': id} for id in selected]
        view_options = {'supersample': supersample}
        if args.action == 'views-proof':
            view_options['long_edge'] = args.long_edge
        elif args.action == 'proof' and args.width is None and args.height is None:
            view_options['long_edge'] = 640
        else:
            view_requests[0].update(width=args.width, height=args.height)
        plan = scene_bridge('view-plan', scene, load_scene_json(catalog_bytes), {'requests': view_requests, 'options': view_options})
        width, height = (plan['views'][0]['output'][key] for key in ['width', 'height'])
    else:
        width = args.width if args.width is not None else (360 if args.action == 'proof' else canvas['width'])
        height = args.height if args.height is not None else width * canvas['height'] / canvas['width']
    if not isinstance(height, (int, float)) or not math.isfinite(height) or height != int(height):
        _error('Width must permit integer dimensions at the authored aspect ratio; provide a matching width and height.')
    height = int(height)
    _positive_integer(width, 'width'); _positive_integer(height, 'height')
    if not selected and width*canvas['height'] != height*canvas['width']:
        _error('Render dimensions must preserve the authored aspect ratio.')
    if width > 4096 or height > 4096:
        _error('Render dimensions cannot exceed the shared engine limit of 4096 pixels per side.')
    if supersample not in [1, 2, 4] or isinstance(supersample, bool) or width*supersample > 4096 or height*supersample > 4096:
        _error('Supersample must be 1, 2, or 4, with internal dimensions no larger than 4096 pixels per side.')
    start = getattr(args, 'time', getattr(args, 'start', 0))
    seconds = getattr(args, 'seconds', None)
    if seconds is None:
        seconds = min(3, canvas['loop_seconds']) if args.action in ['proof', 'views-proof'] else canvas['loop_seconds']
    if not math.isfinite(start) or start < 0 or not math.isfinite(seconds) or seconds <= 0:
        _error('Render time/duration must be finite and nonnegative, with positive duration.')
    frames = seconds * canvas['fps']
    if frames != int(frames) or frames > loop_frames:
        _error('Duration must contain an integer frame count within one authored loop.')
    disable = getattr(args, 'disable', [])
    if any(layer not in {row['id'] for row in scene['layers']} for layer in disable):
        _error('Every --disable layer must exist in the selected scene.')
    request = {'project': str(project), 'out': str(out), 'mode': args.action, 'width': width, 'height': height,
               'start': start, 'seconds': seconds, 'disable': disable, 'supersample': supersample,
               'scene_path':str(context['scene']), 'catalog_path':str(context['catalog'])}
    if selected:
        request.update(views=view_requests, view_options=view_options,
                       expected_scene_sha256=hashlib.sha256(scene_bytes).hexdigest(),
                       expected_catalog_sha256=hashlib.sha256(catalog_bytes).hexdigest())
    if args.action == 'benchmark': request['sample_times'] = args.sample_times
    if args.action == 'rig-proof':
        recipe_path = args.recipe.resolve()
        recipe_bytes = recipe_path.read_bytes()
        recipe = json.loads(recipe_bytes)
        request.update({'rig_recipe':recipe, 'rig_recipe_path':str(recipe_path), 'rig_recipe_sha256':hashlib.sha256(recipe_bytes).hexdigest()})
        if recipe.get('inventory'):
            inventory_path = _project_input(project, recipe['inventory'])
            inventory = json.loads(inventory_path.read_text())
            if inventory.get('version') != 1:
                _error('Unsupported rig-proof inventory version; expected version 1.')
            part_ids = {item['id'] for item in inventory.get('items', [])}
            requested_parts = set(recipe.get('part_ids', []))
            if not requested_parts <= part_ids:
                _error('Rig proof part_ids must name entries in the selected existing inventory.')
            request['inventory_identity'] = _identity(inventory_path, 'project')
        elif recipe.get('part_ids'):
            _error('Rig proof part_ids require an existing project-relative inventory.')
    if args.action == 'look-proof':
        recipe_path = args.recipe.resolve()
        recipe_bytes = recipe_path.read_bytes()
        request.update({'look_recipe':json.loads(recipe_bytes), 'look_recipe_path':str(recipe_path),
                        'look_recipe_sha256':hashlib.sha256(recipe_bytes).hexdigest()})
    audio = None
    audio_bytes = None
    if args.action == 'video':
        if width % 2 or height % 2:
            _error('Native H.264 dimensions must be even.')
        _positive_integer(args.repeats, 'repeats')
        if args.bitrate is not None:
            _positive_integer(args.bitrate, 'bitrate')
            if args.bitrate < 1000:
                _error('Bitrate must be at least 1000 bits per second.')
            request['bitrate'] = args.bitrate
        if args.audio:
            audio = args.audio.resolve()
            audio_bytes = _pcm_bytes(audio, seconds * args.repeats)
        request['native'] = str(_native_binary(project))
    node = require_node()
    probe = _json_command([node, RENDERER, '--probe'])
    if not probe.get('ok'):
        _error('Node Canvas unavailable; run ambiance doctor.', 'missing_dependency', 3)
    out.parent.mkdir(parents=True, exist_ok=True)
    data = _json_command([node, RENDERER], request)
    data['resolved_path'] = data['output']
    data['path_base'] = 'absolute'
    data['revision'] = {k:context[k] for k in ['revision_id','manifest_sha256'] if k in context} or None
    if args.action == 'video':
        binary = request['native']
        audio_snapshot = None
        if audio:
            audio_snapshot = out/'selected-audio.wav'
            with audio_snapshot.open('xb') as file:
                file.write(audio_bytes)
        if args.repeats != 1 or audio:
            final = out/'video.mp4'
            data['composition'] = _json_command([binary, 'compose', data['output'], audio_snapshot or '-', final, args.repeats])
            if audio_snapshot and _digest(audio_snapshot) != hashlib.sha256(audio_bytes).hexdigest():
                _error('Selected audio snapshot changed during mux; output identity is unverified.', 'check_failed', 1)
            data['output'] = str(final)
            data['output_sha256'] = _digest(final)
        data['picture'] = str(out/'picture.mp4')
        data['picture_sha256'] = _digest(out/'picture.mp4')
        data['repeats'] = args.repeats
        data['final_frames'] = int(frames)*args.repeats
        data['audio_source'] = {'path': str(audio), 'sha256': hashlib.sha256(audio_bytes).hexdigest(), 'snapshot': str(audio_snapshot)} if audio else None
        data['verification'] = _verify(project, binary, data['output'], out/'verification', width, height,
                                       canvas['fps'], data['final_frames'], int(bool(audio)), int(frames))
        data['ok'] = data['verification']['ok']
    if getattr(args, 'revision', None):
        _context(project, args.revision)
    data['resolved_path'] = data['output']
    data['report'] = str(out/'render-report.json')
    (out/'render-report.json').write_text(json.dumps(data, indent=2, allow_nan=False)+'\n')
    if args.action == 'views-proof':
        return {key:data[key] for key in ['ok','mode','output','resolved_path','path_base','report','revision',
                'scene_sha256','catalog_sha256','views','frames','seconds','start_seconds',
                'review_needed','stage_frames_rendered','elapsed_seconds','peak_rss_bytes']}
    return data


def _identity(path, path_base='absolute'):
    path = Path(path).resolve()
    return {'resolved_path':str(path), 'path_base':path_base, 'bytes':path.stat().st_size, 'sha256':_digest(path)}


def _project_input(project, value):
    path = (project/value).resolve()
    if Path(value).is_absolute() or not path.is_relative_to(project) or not path.is_file():
        _error(f'Expected an existing project-relative input inside {project}: {value}')
    return path


def requested_contacts(times, indices, fps, frames):
    """Map exact requested contacts independently of the backend's default contacts."""
    _positive_integer(fps, 'fps'); _positive_integer(frames, 'frames')
    result = []
    for time in times:
        if not isinstance(time, (float, int)) or isinstance(time, bool) or not math.isfinite(time) or time < 0 or time >= frames/fps:
            _error('Contact time must be finite and within [0, media duration).')
        position = time*fps
        nearest = round(position)
        index = nearest if abs(position-nearest) <= 1e-7 else math.floor(position)
        if index >= frames:
            index = frames-1  # Range was checked above; tolerance never invents an endpoint frame.
        result.append({'requested_time_seconds':time, 'frame_index':index, 'presentation_time_seconds':index/fps})
    for index in indices:
        if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < frames:
            _error('Contact frame index must be within 0..N-1.')
        result.append({'requested_frame':index, 'frame_index':index, 'presentation_time_seconds':index/fps})
    return result


def _pcm_bytes(source, seconds):
    source = Path(source).resolve()
    data = source.read_bytes()
    try:
        with wave.open(io.BytesIO(data), 'rb') as file:
            if file.getcomptype() != 'NONE' or file.getnchannels() != 2 or file.getframerate() != 48000:
                _error('Selected audio must be stereo 48 kHz PCM WAV.')
            if abs(file.getnframes() - seconds*48000) > 1:
                _error('Selected PCM audio must exactly match the final repeated picture duration.')
            expected = file.getnframes()*file.getnchannels()*file.getsampwidth()
            if len(file.readframes(file.getnframes())) != expected:
                _error('Selected PCM WAV is truncated.')
    except (wave.Error, EOFError) as error:
        _error(f'Selected audio must be an existing PCM WAV, not pre-encoded AAC: {error}')
    return data


def compose(args, project):
    """Compose encoded picture without invoking Canvas or the raster renderer."""
    if getattr(args,'view',None) is not None and not getattr(args,'edition',None):
        _error('--view on composition requires --revision and --edition so the picture identity can be checked')
    out = _fresh(args.out)
    picture = args.picture.resolve(); audio = args.audio.resolve()
    for source in [picture, audio]:
        if not source.is_file():
            _error(f'Selected input does not exist (shell-relative command path): {source}')
    _positive_integer(args.repeats, 'repeats')
    context = _context(project, args.revision) if getattr(args, 'revision', None) else {}
    binary = _native_binary(project)
    picture_identity = _identity(picture)
    probe = _json_command([binary, 'probe-picture', picture])
    if not probe['supported_cfr_h264']:
        _error('Unsupported picture: '+'; '.join(probe['errors']))
    if _digest(picture) != picture_identity['sha256']:
        _error('Selected picture changed during compressed-sample inspection.', 'check_failed', 1)
    pcm = _pcm_bytes(audio, probe['duration_seconds']*args.repeats)
    audio_identity = {'resolved_path':str(audio), 'path_base':'absolute', 'bytes':len(pcm), 'sha256':hashlib.sha256(pcm).hexdigest()}
    if _digest(audio) != audio_identity['sha256']:
        _error('Selected audio changed while being captured.', 'check_failed', 1)
    out.mkdir(parents=True)
    picture_snapshot = out/'picture-input.mp4'; audio_snapshot = out/'selected-audio.wav'
    shutil.copyfile(picture, picture_snapshot)
    audio_snapshot.write_bytes(pcm)
    if _digest(picture_snapshot) != picture_identity['sha256']:
        _error('Selected picture changed while being copied.', 'check_failed', 1)
    recipe = {'version':1, 'operation':'media compose', 'picture':picture_identity, 'audio':audio_identity,
              'repeats':args.repeats, 'input_video_tracks':probe['video_tracks'], 'input_audio_tracks':probe['audio_tracks'],
              'input_audio_policy':'The selected PCM replaces any input movie audio.',
              'native_binary':_identity(binary), 'native_source':_identity(NATIVE_SOURCE),
              'native_sources':native_source_identity(NATIVE_SOURCE.parent),
              'backend':'macOS AVFoundation', 'host_platform':platform.platform(), 'adapter_sha256':_digest(Path(__file__)),
              'revision':{k:context[k] for k in ['revision_id','manifest_sha256'] if k in context} or None}
    (out/'composition-recipe.json').write_text(json.dumps(recipe,indent=2)+'\n')
    output = out/'video.mp4'
    native = _json_command([binary, 'compose', picture_snapshot, audio_snapshot, output, args.repeats])
    expected_frames = probe['frames']*args.repeats
    verification = _verify(project, binary, output, out/'verification', int(probe['width']), int(probe['height']),
                           probe['fps'], expected_frames, 1, probe['frames'])
    output_probe = _json_command([binary, 'probe-picture', output])
    original_samples = [sample['sha256'] for sample in probe['samples']]
    final_samples = [sample['sha256'] for sample in output_probe['samples']]
    payloads_preserved = final_samples == original_samples*args.repeats
    inputs_unchanged = _digest(picture) == picture_identity['sha256'] and _digest(audio) == audio_identity['sha256']
    snapshots_unchanged = _digest(picture_snapshot) == picture_identity['sha256'] and _digest(audio_snapshot) == audio_identity['sha256']
    if context:
        _context(project, context['revision_id'])
    result = {'ok':bool(verification['ok'] and output_probe['supported_cfr_h264'] and payloads_preserved and inputs_unchanged and snapshots_unchanged),
              'operation':'media compose','recipe':str(out/'composition-recipe.json'), 'revision':recipe['revision'],
              'picture':str(picture), 'picture_sha256':picture_identity['sha256'], 'picture_identity':picture_identity,
              'picture_snapshot':str(picture_snapshot), 'audio_source':{'path':str(audio), 'snapshot':str(audio_snapshot), 'sha256':audio_identity['sha256']},
              'output':str(output), 'output_sha256':_digest(output), 'resolved_path':str(output), 'path_base':'absolute',
              'repeats':args.repeats, 'final_frames':expected_frames, 'input_tracks':{'video':probe['video_tracks'],'audio':probe['audio_tracks']},
              'output_tracks':{'video':output_probe['video_tracks'],'audio':output_probe['audio_tracks']},
              'input_audio_policy':recipe['input_audio_policy'],'video_reencoded':False,'compressed_sample_payloads_preserved':payloads_preserved,
              'input_video_sample_sha256':original_samples,'output_video_sample_sha256':final_samples,
              'inputs_unchanged':inputs_unchanged,'snapshots_unchanged':snapshots_unchanged,'native_composition':native,'verification':verification,
              'report':str(out/'compose-report.json'), 'visual_review_performed':False,'human_listening_review_performed':False}
    if not result['ok']:
        result['error'] = 'Composition verification failed: inspect input identity, compressed sample sequence, and decode report.'
    (out/'compose-report.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
