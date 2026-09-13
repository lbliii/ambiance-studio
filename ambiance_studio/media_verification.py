"""Decode actual media, retain contacts/provenance, and bind edition subjects."""
import json
import math
from pathlib import Path

from . import native_media, render_plan
from .errors import CommandError
from .native_sources import source_identity as native_source_identity
from .file_identity import digest
from .media_inputs import fresh_output, positive_integer, project_input
from .native_media import NATIVE_SOURCE
from .scene_runtime import load_scene_json


def verify_media(binary, source, out, width, height, fps, frames, audio_tracks, loop_frames, contact_times=None, contact_frames=None):
    """Decode to a fresh report directory, hashing input before and after decode.

    Technical failures return an unsuccessful report; invalid inputs/runtime
    transport raise CommandError. This does not record an edition or review.
    """
    source = Path(source).resolve()
    if not source.is_file():
        raise CommandError(f'Media file does not exist: {source}')
    for name, value in [('width', width), ('height', height), ('fps', fps), ('frames', frames), ('loop_frames', loop_frames)]:
        positive_integer(value, name)
    requests = requested_contacts(contact_times or [], contact_frames or [], fps, frames)
    out = fresh_output(out)
    out.mkdir(parents=True)
    contacts = out/'contacts'
    contacts.mkdir()
    report = out/'media-report.json'
    source_hash = digest(source)
    data = native_media.json_command([binary, 'verify', source, width, height, fps, frames, audio_tracks, report, contacts, loop_frames, ','.join(str(r['frame_index']) for r in requests)], allow_check_failure=True)
    after_hash = digest(source)
    data['input_unchanged'] = source_hash == after_hash
    if not data['input_unchanged']:
        data['ok'] = False
        data['error'] = 'Media input changed while it was being decoded; this report is not valid for either version.'
    data.update({'input_sha256': source_hash, 'input_sha256_after': after_hash,
                 'native_binary_sha256': digest(binary),
                 'native_source_sha256': digest(NATIVE_SOURCE),
                 'native_sources': native_source_identity(NATIVE_SOURCE.parent),
                 'report': str(report), 'contacts': str(contacts)})
    data['requested_contacts'] = []
    for request in requests:
        image = contacts/f"decoded-{request['frame_index']:04d}.png"
        if not image.is_file():
            data['ok'] = False
            data['error'] = 'A requested decoded contact was not produced.'
            continue
        data['requested_contacts'].append({**request, 'resolved_path':str(image), 'path_base':'absolute', 'sha256':digest(image)})
    data['contact_selection'] = 'CFR floor(time*fps), snapping values within 1e-7 frame of an integer boundary; valid times are [0,duration). No VFR support.'
    from .audio_measurements import decoded_measurement
    decoded_measurement(data, source, source_hash)
    report.write_text(json.dumps(data, indent=2, allow_nan=False)+'\n')
    return data


def requested_contacts(times, indices, fps, frames):
    """Map exact requested contacts independently of the backend's default contacts."""
    positive_integer(fps, 'fps'); positive_integer(frames, 'frames')
    result = []
    for time in times:
        if not isinstance(time, (float, int)) or isinstance(time, bool) or not math.isfinite(time) or time < 0 or time >= frames/fps:
            raise CommandError('Contact time must be finite and within [0, media duration).')
        position = time*fps
        nearest = round(position)
        index = nearest if abs(position-nearest) <= 1e-7 else math.floor(position)
        if index >= frames:
            index = frames-1  # Range was checked above; tolerance never invents an endpoint frame.
        result.append({'requested_time_seconds':time, 'frame_index':index, 'presentation_time_seconds':index/fps})
    for index in indices:
        if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < frames:
            raise CommandError('Contact frame index must be within 0..N-1.')
        result.append({'requested_frame':index, 'frame_index':index, 'presentation_time_seconds':index/fps})
    return result


def verify_command(args, project):
    """Resolve CLI expectations, decode, and recheck the exact revision/edition."""
    project = Path(project).resolve()
    context = render_plan.render_context(project, getattr(args, 'revision', None))
    scene = load_scene_json(Path(context['scene']).read_bytes())
    canvas = scene['canvas']
    loop_frames = canvas['fps'] * canvas['loop_seconds']
    out = fresh_output(args.out)
    source = args.file.resolve()
    if not source.is_file():
        raise CommandError(f'Media file does not exist: {source}')
    defaults={**canvas,'frames':int(loop_frames),'loop_frames':int(loop_frames),'audio_tracks':0};subject=None;edition_path=None
    if getattr(args,'edition',None):
        from . import editions
        if not args.revision:raise CommandError('--edition requires --revision')
        edition=editions.load_edition(project,args.revision,args.edition)
        if digest(source)!=edition['output']['sha256']:raise CommandError('Media bytes differ from the selected edition')
        view=editions.edition_view(project,edition)
        if args.view is not None and args.view!=view['id']:raise CommandError('Verification view differs from the selected edition')
        edition_path=editions.edition_path(project,args.revision,args.edition);edition_hash=digest(edition_path)
        if edition['schema_version']==2:defaults.update(edition['output_expectations'])
        else:
            verification_path=project_input(project,edition['verification']['path'])
            if digest(verification_path)!=edition['verification']['sha256']:raise CommandError('Selected edition verification receipt changed')
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
    result=verify_media(native_media.native_binary(project),source,out,**expected,contact_times=args.contact_time,contact_frames=args.contact_frame)
    if getattr(args,'revision',None):render_plan.render_context(project,args.revision)
    if edition_path and digest(edition_path)!=edition_hash:raise CommandError('Edition receipt changed during verification')
    if subject:
        result['subject']=subject;Path(result['report']).write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    return result
