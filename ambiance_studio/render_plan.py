"""Validate raster requests before runtime discovery or output creation.

The shared scene evaluator remains the view-sizing authority. A plan holds the
captured PCM bytes and exact view preflight identities consumed by execution;
no command namespace is needed once planning has completed.
"""
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path

from .errors import CommandError
from .media_inputs import fresh_output, positive_integer, project_input, input_identity, pcm_bytes
from .scene_runtime import load_scene_json, scene_bridge


@dataclass(frozen=True)
class RenderPlan:
    project: Path
    out: Path
    context: dict
    request: dict
    fps: int
    frames: int
    repeats: int
    audio: Path | None
    audio_bytes: bytes | None


def render_context(project, revision=None):
    if revision:
        from . import revision_capture
        return revision_capture.render_context(project, revision)
    from .project import locations
    scene, catalog = locations(project)
    return {'scene':scene, 'catalog':catalog}


def plan_render(args, project):
    """Resolve command options into a validated request without rendering media."""
    project = Path(project).resolve()
    context = render_context(project, getattr(args, 'revision', None))
    scene_bytes = Path(context['scene']).read_bytes()
    scene = load_scene_json(scene_bytes)
    canvas = scene['canvas']
    from .timebase import scene_frame_count
    try:
        loop_frames = scene_frame_count(scene)
    except ValueError as error:
        raise CommandError(str(error)) from error
    out = fresh_output(args.out)
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
        raise CommandError('Width must permit integer dimensions at the authored aspect ratio; provide a matching width and height.')
    height = int(height)
    positive_integer(width, 'width'); positive_integer(height, 'height')
    if not selected and width*canvas['height'] != height*canvas['width']:
        raise CommandError('Render dimensions must preserve the authored aspect ratio.')
    if width > 4096 or height > 4096:
        raise CommandError('Render dimensions cannot exceed the shared engine limit of 4096 pixels per side.')
    if supersample not in [1, 2, 4] or isinstance(supersample, bool) or width*supersample > 4096 or height*supersample > 4096:
        raise CommandError('Supersample must be 1, 2, or 4, with internal dimensions no larger than 4096 pixels per side.')
    start = getattr(args, 'time', getattr(args, 'start', 0))
    source_start_frame = getattr(args, 'start_frame', None)
    finite_shot = scene.get('clock', {}).get('mode') == 'finite'
    if source_start_frame is not None:
        from .timebase import integer
        try:
            integer(source_start_frame)
        except ValueError as error:
            raise CommandError(str(error)) from error
        if source_start_frame < 0:
            raise CommandError('Source start frame must be nonnegative.')
        start = source_start_frame / canvas['fps']
    elif finite_shot and args.action in ['video', 'proof', 'views-proof']:
        from .timebase import seconds_to_frames
        try:
            source_start_frame = seconds_to_frames(start, canvas['fps'])['value']
        except ValueError as error:
            raise CommandError(str(error) + '; use --start-frame for an exact frame selection.') from error
    seconds = getattr(args, 'seconds', None)
    if seconds is None and finite_shot and source_start_frame is not None:
        frames = loop_frames - source_start_frame
        if args.action in ['proof', 'views-proof']:
            frames = min(frames, 3 * canvas['fps'])
        seconds = frames / canvas['fps']
    else:
        if seconds is None and 'clock' in scene:
            frames = min(3 * canvas['fps'], loop_frames) if args.action in ['proof', 'views-proof'] else loop_frames
            seconds = frames / canvas['fps']
        else:
            if seconds is None:
                seconds = min(3, canvas['loop_seconds']) if args.action in ['proof', 'views-proof'] else canvas['loop_seconds']
            frames = seconds * canvas['fps']
    if not math.isfinite(start) or start < 0 or not math.isfinite(seconds) or seconds <= 0:
        raise CommandError('Render time/duration must be finite and nonnegative, with positive duration.')
    if frames != int(frames) or frames > loop_frames:
        raise CommandError('Duration must contain an integer frame count within one authored loop.')
    if finite_shot and args.action in ['video', 'proof', 'views-proof']:
        if source_start_frame + frames > loop_frames:
            raise CommandError('Finite render range must stay within [0,N); endpoint inspection is frame-only.')
        if getattr(args, 'repeats', 1) != 1:
            raise CommandError('Finite video cannot repeat the shot.')
        if source_start_frame and getattr(args, 'audio', None):
            raise CommandError('Audio conformance for a nonzero finite source range is not supported; render the picture range separately.')
    disable = getattr(args, 'disable', [])
    if any(layer not in {row['id'] for row in scene['layers']} for layer in disable):
        raise CommandError('Every --disable layer must exist in the selected scene.')
    request = {'project': str(project), 'out': str(out), 'mode': args.action, 'width': width, 'height': height,
               'start': start, 'seconds': seconds, 'disable': disable, 'supersample': supersample,
               'scene_path':str(context['scene']), 'catalog_path':str(context['catalog'])}
    if source_start_frame is not None:
        request['start_frame'] = source_start_frame
    if args.action != 'frame' and (source_start_frame is not None or 'clock' in scene):
        request['frame_count'] = int(frames)
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
            inventory_path = project_input(project, recipe['inventory'])
            inventory = json.loads(inventory_path.read_text())
            if inventory.get('version') != 1:
                raise CommandError('Unsupported rig-proof inventory version; expected version 1.')
            part_ids = {item['id'] for item in inventory.get('items', [])}
            requested_parts = set(recipe.get('part_ids', []))
            if not requested_parts <= part_ids:
                raise CommandError('Rig proof part_ids must name entries in the selected existing inventory.')
            request['inventory_identity'] = input_identity(inventory_path, 'project')
        elif recipe.get('part_ids'):
            raise CommandError('Rig proof part_ids require an existing project-relative inventory.')
    if args.action == 'look-proof':
        recipe_path = args.recipe.resolve()
        recipe_bytes = recipe_path.read_bytes()
        request.update({'look_recipe':json.loads(recipe_bytes), 'look_recipe_path':str(recipe_path),
                        'look_recipe_sha256':hashlib.sha256(recipe_bytes).hexdigest()})
    audio = None
    audio_bytes = None
    if args.action == 'video':
        from .audio_encoding import encoding_settings
        request['audio_encoding'] = encoding_settings(getattr(args, 'audio_bitrate', None), has_audio=bool(args.audio))
        if width % 2 or height % 2:
            raise CommandError('Native H.264 dimensions must be even.')
        positive_integer(args.repeats, 'repeats')
        if args.bitrate is not None:
            positive_integer(args.bitrate, 'bitrate')
            if args.bitrate < 1000:
                raise CommandError('Bitrate must be at least 1000 bits per second.')
            request['bitrate'] = args.bitrate
        if args.audio:
            audio = args.audio.resolve()
            audio_bytes = pcm_bytes(audio, seconds * args.repeats)
    return RenderPlan(project, out, context, request, canvas['fps'], int(frames),
                      getattr(args, 'repeats', 1), audio, audio_bytes)
