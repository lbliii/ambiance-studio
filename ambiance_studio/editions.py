"""Bind verified media editions to captured picture, view and audio inputs."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import studio
from . import audio
from .record_contracts import identifier, fields, seal, read_sealed
from .project_references import relative, ref, changed, unique
from .revision_dependencies import Collector
from .revision_capture import manifest_path, load, check, render_context

EDITION = 'ambiance-edition'


def edition_path(project, revision, edition):
    return studio.inside(project, f'revisions/{identifier(revision)}/editions/{identifier(edition)}.json')


def load_edition(project, revision, edition):
    data = read_sealed(edition_path(project, revision, edition), EDITION, versions=(1, 2))
    if data['revision'] != revision or data['id'] != edition: raise ValueError('Edition identity mismatch')
    if data['revision_sha256'] != studio.digest(manifest_path(project, revision)): raise ValueError('Edition refers to a different revision manifest')
    if data['schema_version'] == 2:
        if data.get('view') != captured_view(project, revision, data.get('view', {}).get('id')):
            raise ValueError('Edition view differs from the captured scene')
        expected=data.get('output_expectations', {})
        fields(expected, ['width','height','fps','frames','loop_frames','audio_tracks'], 'edition expectations')
        if set(expected) != {'width','height','fps','frames','loop_frames','audio_tracks'} or any(type(v) is not int or v < (0 if k=='audio_tracks' else 1) for k,v in expected.items()):
            raise ValueError('Edition requires exact integer output expectations')
        if expected['audio_tracks'] not in [0,1] or expected['frames'] % expected['loop_frames']:
            raise ValueError('Edition requires whole picture loops and zero or one audio track')
        dimensions=data['view']['definition']['output']
        if expected['width']*dimensions['height'] != expected['height']*dimensions['width']:
            raise ValueError('Edition dimensions differ from its view aspect ratio')
    return data


def captured_view(project, revision, id='authored'):
    """Resolve captured control documents without making stale art unreadable."""
    from . import scene_runtime
    if not isinstance(id,str):raise ValueError('A view ID is required')
    data=load(project, revision)
    scene=scene_runtime.load_scene_json(studio.inside(project,data['controls']['scene']).read_bytes())
    catalog=scene_runtime.load_scene_json(studio.inside(project,data['controls']['catalog']).read_bytes())
    row=scene_runtime.scene_bridge('view-inspect',scene,catalog,{'id':id})['views'][id]
    definition={key:row[key] for key in ['resolver_version','id','source_canvas','rect_scene_px','output']}
    return {'id':id,'sha256':row['view_sha256'],'definition':definition}


def edition_view(project, edition):
    return edition['view'] if edition['schema_version']==2 else captured_view(project,edition['revision'],'authored')


def report_view(project, revision, report):
    """A receipt may assert a view only when it matches captured geometry."""
    row=report.get('view')
    if row is None:return captured_view(project,revision,'authored')
    selected=captured_view(project,revision,row.get('view',{}).get('id'))
    if row.get('view')!=selected['definition'] or row.get('view_sha256')!=selected['sha256']:
        raise ValueError('Picture receipt view differs from the captured view')
    output=row.get('output',{});expected=selected['definition']['output']
    if any(type(output.get(k)) is not int or output[k]<=0 for k in ['width','height']) or output['width']*expected['height']!=output['height']*expected['width']:
        raise ValueError('Picture receipt dimensions differ from its view')
    return selected


def collect_edition_audio(project, data, args):
    """Validate selected PCM provenance for both job preflight and edition capture."""
    c = Collector(project)
    if getattr(args, 'audio_session', None): c.session(studio.inside(project, str(args.audio_session)))
    if getattr(args, 'audio_run', None): c.audio_run(studio.inside(project, str(args.audio_run)), 'edition')
    if getattr(args, 'audio_provenance', None): c.preparation(studio.inside(project, str(args.audio_provenance)), 'edition')
    pcm = getattr(args, 'audio', None); master = None
    if pcm:
        path = Path(pcm).resolve(); audio.wav_info(path); master = c.pin(path, 'mix', 'master')
        declared = set(data['sound_complete']) | c.sound_complete
        if master['path'] not in declared:
            raise ValueError('Edition PCM needs a selected revision master with complete provenance, --audio-run, or --audio-provenance identifying this output')
        # Include frozen sound roots when using the revision's selected master.
        if master['path'] in data['sound_complete']:
            c.refs += [r for r in data['dependencies'] if r['section'] in ['sound-design', 'mix']]
        c.sound_complete.add(master['path'])
    return c, master


def prepare_edition(project, args):
    """Freeze declared inputs before rendering; publication checks them again."""
    edition = getattr(args, 'edition', None)
    if not edition: return None
    if args.command=='media' and args.action=='verify':return None
    id = getattr(args, 'revision', None)
    if not id: raise ValueError('--edition requires --revision')
    identifier(edition); context = render_context(project, id); data = load(project, id)
    selected_view=captured_view(project,id,getattr(args,'view',None) or 'authored')
    if edition_path(project, id, edition).exists(): raise ValueError('Edition exists; choose a new ID')
    relative(project, args.out)
    c, master = collect_edition_audio(project, data, args)
    picture = None; picture_dimensions = None
    if args.command == 'media' and args.action == 'compose':
        picture = c.pin(Path(args.picture).resolve(), 'export', 'picture_input')
        proof = getattr(args, 'picture_receipt', None); bound = False
        if proof:
            proof_path = studio.inside(project, str(proof)); pinned = c.pin(proof_path, 'export', 'picture_receipt')
            raw = proof_path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != pinned['sha256']: raise ValueError('Picture receipt changed while reading')
            report = json.loads(raw)
            if report.get('mode') != 'video' or not report.get('ok'):
                raise ValueError('Picture receipt must be a successful saved render video report')
            for key in ['scene', 'catalog']:
                if report.get(key+'_sha256') != studio.digest(context[key]): raise ValueError('Picture receipt belongs to a different captured '+key)
            if picture['sha256'] not in [report.get('picture_sha256'), report.get('output_sha256')]: raise ValueError('Picture bytes differ from the render receipt')
            selected_view=report_view(project,id,report)
            if report.get('view'):picture_dimensions=report['view']['output']
            bound = True
        else:
            for previous in sorted((manifest_path(project, id).parent/'editions').glob('*.json')):
                ed = load_edition(project, id, previous.stem)
                if picture['sha256'] in [ed['picture']['sha256'], ed['output']['sha256']]:
                    dependencies = [r for r in ed['dependencies'] if r['section'] == 'export']
                    if changed(project, dependencies): raise ValueError('Selected prior picture edition dependencies changed')
                    c.refs += dependencies; c.pin(previous, 'export', 'picture_edition'); bound = True; break
            if bound:
                selected_view=edition_view(project,ed)
                if ed['schema_version']==2:picture_dimensions={k:ed['output_expectations'][k] for k in ['width','height']}
        if not bound: raise ValueError('Picture is not bound to this revision; supply --picture-receipt or reuse a recorded edition of this revision')
        if getattr(args,'view',None) is not None and args.view!=selected_view['id']:
            raise ValueError('Selected picture view differs from --view; composition cannot relabel its framing')
    return {'revision': id, 'id': edition, 'manifest_sha256': context['manifest_sha256'], 'collector': c, 'audio': master, 'picture': picture,
            'inputs': unique(c.refs+c.origins), 'view':selected_view, 'picture_dimensions':picture_dimensions}


def record_edition(project, prepared, result, args):
    """Register an actually verified render result, never a user-authored pass."""
    if prepared is None: return result
    from .project import project_lock
    if not result.get('ok', True): return result
    with project_lock(project):
        id = prepared['revision']; edition = prepared['id']; c = prepared['collector']
        if studio.digest(manifest_path(project, id)) != prepared['manifest_sha256'] or not check(project, id)['ok']:
            raise ValueError('Revision changed during media production; edition not registered')
        if changed(project, prepared['inputs']): raise ValueError('Selected media/audio inputs changed; edition not registered')
        path = edition_path(project, id, edition)
        if path.exists(): raise ValueError('Edition appeared during production; refusing replacement')
        verification = result.get('verification')
        if not isinstance(verification, dict) or not verification.get('ok'):
            raise ValueError('Edition requires successful actual media verification')
        view=prepared['view']; expectations=None
        if view['id']!='authored':
            if args.command=='render' and report_view(project,id,result)!=view:
                raise ValueError('Rendered view differs from the prepared edition view')
            expectations={key:verification.get(source) for key,source in [('width','width'),('height','height'),('fps','fps'),('frames','decoded_frames'),('loop_frames','loop_frames')]}
            if any(type(v) not in [int,float] or v<=0 or v!=int(v) for v in expectations.values()):
                raise ValueError('Named-view edition requires exact decoded output dimensions and timing')
            expectations={k:int(v) for k,v in expectations.items()}
            expectations['audio_tracks']=verification.get('audio',{}).get('tracks')
            if type(expectations['audio_tracks']) is not int or expectations['audio_tracks'] not in [0,1]:raise ValueError('Named-view edition requires verified audio-track identity')
            size={k:expectations[k] for k in ['width','height']}
            intended=view['definition']['output']
            if size['width']*intended['height']!=size['height']*intended['width']:raise ValueError('Decoded picture does not match its view aspect ratio')
            if prepared['picture_dimensions'] and size!=prepared['picture_dimensions']:raise ValueError('Composition changed the bound picture dimensions')
            if args.command=='render' and result['view']['output']!=size:raise ValueError('Render receipt and decoded dimensions differ')
            result['view']={**result.get('view',{}),'view':view['definition'],'view_sha256':view['sha256'],'output':size}
            result['output_expectations']=expectations
            production_report=Path(args.out).resolve()/('compose-report.json' if args.command=='media' else 'render-report.json')
            if not production_report.is_file():raise ValueError('Named-view edition needs its saved production report')
            studio.write(production_report,result)
        output_path = Path(result['output']).resolve()
        output = ref(project, output_path, 'export', 'edition_output', result.get('output_sha256'))
        refs = list(c.refs)
        refs += [output, {**output, 'section': 'release'}]
        report_path = verification.get('report')
        if not report_path: raise ValueError('Media verification did not provide its saved report')
        refs.append(ref(project, Path(report_path), 'export', 'media_verification'))
        # Audio-only evidence uses exact source/output identities from the existing
        # verifier; it does not infer listening or change picture expectations.
        measured = verification.get('audio', {}).get('level_measurement', {})
        audio_evidence = None
        if prepared['audio'] and result.get('audio_encoding'):
            from .audio_encoding import encoding_settings
            wanted = encoding_settings(getattr(args, 'audio_bitrate', None))
            if any(result['audio_encoding'].get(k) != v for k, v in wanted.items()):
                raise ValueError('Audio encoding differs from the requested edition settings')
            original = result.get('audio_source_measurement', {})
            if original.get('source', {}).get('sha256') != prepared['audio']['sha256']:
                raise ValueError('PCM level measurements differ from the edition source')
            if measured.get('encoded_source', {}).get('sha256') != output['sha256']:
                raise ValueError('Decoded audio measurements differ from the edition movie')
            decoded = measured['source']
            refs.append(ref(project, Path(decoded['path']), 'export', 'audio_presentation_float', decoded['sha256']))
            audio_evidence = {'encoding': result['audio_encoding'], 'source_measurement': original,
                              'decoded_measurement': measured}
        picture = prepared['picture']
        if picture is None:
            # The render run retains its original encoded picture separately.
            picture_path = Path(args.out).resolve()/'picture.mp4'
            picture = ref(project, picture_path, 'export', 'picture_input')
            refs.append(picture)
        out = Path(args.out).resolve()
        # Explicit named backend receipts, not an open-ended output-folder scan.
        for name in ['render-report.json', 'compose-report.json', 'composition-recipe.json', 'scene.snapshot.json', 'catalog.snapshot.json']:
            file = out/name
            if file.is_file(): refs.append(ref(project, file, 'export', 'production_record'))
        for name, source in [('selected-audio.wav', prepared['audio']), ('picture-input.mp4', prepared['picture'])]:
            if source and (out/name).is_file(): refs.append(ref(project, out/name, 'export', 'media_input_snapshot', source['sha256']))
        doc_dir = out/'edition-inputs'
        if doc_dir.exists(): raise ValueError('Edition input snapshot directory already exists')
        doc_dir.mkdir()
        for name, doc in c.documents.items():
            target = doc_dir/name; target.write_bytes(doc['bytes'])
            refs.append(ref(project, target, doc['section'], doc['role']))
        if changed(project, prepared['inputs']): raise ValueError('Inputs changed before edition publication')
        receipt = seal({'format': EDITION, 'schema_version': 2 if expectations else 1, 'id': edition, 'revision': id,
            'revision_sha256': prepared['manifest_sha256'], 'created_utc': datetime.now(timezone.utc).isoformat(),
            'picture': picture, 'audio': prepared['audio'], 'output': output, 'dependencies': unique(refs),
            'sound_complete': sorted(c.sound_complete), 'recipe': {'command': args.command, 'action': args.action,
            'repeats': getattr(args, 'repeats', 1), **({'audio_encoding':result['audio_encoding']} if audio_evidence else {})},
            **({'audio_evidence':audio_evidence} if audio_evidence else {}),
            'verification': {'path': relative(project, report_path), 'sha256': studio.digest(report_path)},
            'limits': ['Technical verification only. No creative verdict, listening, phone observation or publication is inferred.'],
            **({'view':view,'output_expectations':expectations} if expectations else {})})
        studio.write(path, receipt)
    return {**result, 'edition': {'id': edition, 'revision': id, 'receipt': str(path), 'sha256': studio.digest(path)}}
