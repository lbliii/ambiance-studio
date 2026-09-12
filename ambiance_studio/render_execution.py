"""Execute planned raster work and compose verified immutable media artifacts.

Edition preparation/recording belongs to media_operations.MediaExecutor. This
service emits media reports only; it never selects or records an edition.
"""
import hashlib
import json
from pathlib import Path
import platform
import shutil

from . import native_media, render_plan
from .errors import CommandError
from .native_sources import source_identity as native_source_identity
from .file_identity import digest
from .media_inputs import fresh_output, positive_integer, input_identity, pcm_bytes
from .media_verification import verify_media
from .native_media import RENDERER, NATIVE_SOURCE
from .render_plan import RenderPlan
from .scene_runtime import require_node


def execute_render(plan: RenderPlan):
    """Consume resolved render options; perform runtime work and write receipts."""
    project, out, context = plan.project, plan.out, plan.context
    request = dict(plan.request)
    audio, audio_bytes = plan.audio, plan.audio_bytes
    mode = request['mode']
    if mode == 'video':
        request['native'] = str(native_media.native_binary(project))
    node = require_node()
    probe = native_media.json_command([node, RENDERER, '--probe'])
    if not probe.get('ok'):
        raise CommandError('Node Canvas unavailable; run ambiance doctor.', 'missing_dependency', 3)
    out.parent.mkdir(parents=True, exist_ok=True)
    data = native_media.json_command([node, RENDERER], request)
    data['resolved_path'] = data['output']
    data['path_base'] = 'absolute'
    data['revision'] = {k:context[k] for k in ['revision_id','manifest_sha256'] if k in context} or None
    if mode == 'video':
        binary = request['native']
        audio_snapshot = None
        if audio:
            audio_snapshot = out/'selected-audio.wav'
            with audio_snapshot.open('xb') as file:
                file.write(audio_bytes)
        if plan.repeats != 1 or audio:
            final = out/'video.mp4'
            data['composition'] = native_media.json_command([binary, 'compose', data['output'], audio_snapshot or '-', final, plan.repeats])
            if audio_snapshot and digest(audio_snapshot) != hashlib.sha256(audio_bytes).hexdigest():
                raise CommandError('Selected audio snapshot changed during mux; output identity is unverified.', 'check_failed', 1)
            data['output'] = str(final)
            data['output_sha256'] = digest(final)
        data['picture'] = str(out/'picture.mp4')
        data['picture_sha256'] = digest(out/'picture.mp4')
        data['repeats'] = plan.repeats
        data['final_frames'] = plan.frames*plan.repeats
        data['audio_source'] = {'path': str(audio), 'sha256': hashlib.sha256(audio_bytes).hexdigest(), 'snapshot': str(audio_snapshot)} if audio else None
        data['verification'] = verify_media(binary, data['output'], out/'verification', request['width'], request['height'],
                                       plan.fps, data['final_frames'], int(bool(audio)), plan.frames)
        data['ok'] = data['verification']['ok']
    if context.get('revision_id'):
        render_plan.render_context(project, context['revision_id'])
    data['resolved_path'] = data['output']
    data['report'] = str(out/'render-report.json')
    (out/'render-report.json').write_text(json.dumps(data, indent=2, allow_nan=False)+'\n')
    if mode == 'views-proof':
        return {key:data[key] for key in ['ok','mode','output','resolved_path','path_base','report','revision',
                'scene_sha256','catalog_sha256','views','frames','seconds','start_seconds',
                'review_needed','stage_frames_rendered','elapsed_seconds','peak_rss_bytes']}
    return data


def compose(args, project):
    """Compose encoded picture without invoking Canvas or the raster renderer."""
    if getattr(args,'view',None) is not None and not getattr(args,'edition',None):
        raise CommandError('--view on composition requires --revision and --edition so the picture identity can be checked')
    out = fresh_output(args.out)
    picture = args.picture.resolve(); audio = args.audio.resolve()
    for source in [picture, audio]:
        if not source.is_file():
            raise CommandError(f'Selected input does not exist (shell-relative command path): {source}')
    positive_integer(args.repeats, 'repeats')
    context = render_plan.render_context(project, args.revision) if getattr(args, 'revision', None) else {}
    binary = native_media.native_binary(project)
    picture_identity = input_identity(picture)
    probe = native_media.json_command([binary, 'probe-picture', picture])
    if not probe['supported_cfr_h264']:
        raise CommandError('Unsupported picture: '+'; '.join(probe['errors']))
    if digest(picture) != picture_identity['sha256']:
        raise CommandError('Selected picture changed during compressed-sample inspection.', 'check_failed', 1)
    pcm = pcm_bytes(audio, probe['duration_seconds']*args.repeats)
    audio_identity = {'resolved_path':str(audio), 'path_base':'absolute', 'bytes':len(pcm), 'sha256':hashlib.sha256(pcm).hexdigest()}
    if digest(audio) != audio_identity['sha256']:
        raise CommandError('Selected audio changed while being captured.', 'check_failed', 1)
    out.mkdir(parents=True)
    picture_snapshot = out/'picture-input.mp4'; audio_snapshot = out/'selected-audio.wav'
    shutil.copyfile(picture, picture_snapshot)
    audio_snapshot.write_bytes(pcm)
    if digest(picture_snapshot) != picture_identity['sha256']:
        raise CommandError('Selected picture changed while being copied.', 'check_failed', 1)
    recipe = {'version':1, 'operation':'media compose', 'picture':picture_identity, 'audio':audio_identity,
              'repeats':args.repeats, 'input_video_tracks':probe['video_tracks'], 'input_audio_tracks':probe['audio_tracks'],
              'input_audio_policy':'The selected PCM replaces any input movie audio.',
              'native_binary':input_identity(binary), 'native_source':input_identity(NATIVE_SOURCE),
              'native_sources':native_source_identity(NATIVE_SOURCE.parent),
              'backend':'macOS AVFoundation', 'host_platform':platform.platform(), 'adapter_sha256':digest(Path(__file__).with_name('rendering.py')),
              'revision':{k:context[k] for k in ['revision_id','manifest_sha256'] if k in context} or None}
    (out/'composition-recipe.json').write_text(json.dumps(recipe,indent=2)+'\n')
    output = out/'video.mp4'
    native = native_media.json_command([binary, 'compose', picture_snapshot, audio_snapshot, output, args.repeats])
    expected_frames = probe['frames']*args.repeats
    verification = verify_media(binary, output, out/'verification', int(probe['width']), int(probe['height']),
                           probe['fps'], expected_frames, 1, probe['frames'])
    output_probe = native_media.json_command([binary, 'probe-picture', output])
    original_samples = [sample['sha256'] for sample in probe['samples']]
    final_samples = [sample['sha256'] for sample in output_probe['samples']]
    payloads_preserved = final_samples == original_samples*args.repeats
    inputs_unchanged = digest(picture) == picture_identity['sha256'] and digest(audio) == audio_identity['sha256']
    snapshots_unchanged = digest(picture_snapshot) == picture_identity['sha256'] and digest(audio_snapshot) == audio_identity['sha256']
    if context:
        render_plan.render_context(project, context['revision_id'])
    result = {'ok':bool(verification['ok'] and output_probe['supported_cfr_h264'] and payloads_preserved and inputs_unchanged and snapshots_unchanged),
              'operation':'media compose','recipe':str(out/'composition-recipe.json'), 'revision':recipe['revision'],
              'picture':str(picture), 'picture_sha256':picture_identity['sha256'], 'picture_identity':picture_identity,
              'picture_snapshot':str(picture_snapshot), 'audio_source':{'path':str(audio), 'snapshot':str(audio_snapshot), 'sha256':audio_identity['sha256']},
              'output':str(output), 'output_sha256':digest(output), 'resolved_path':str(output), 'path_base':'absolute',
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
