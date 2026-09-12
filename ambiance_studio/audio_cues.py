"""Explicit cue alignment snapshots; never retime or stretch selected PCM."""
from .command_output import Output, add_output
import hashlib
import json
from pathlib import Path
import wave

from . import activity


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def snapshot(path):
    path = Path(path).resolve()
    if path.is_dir(): path /= 'activity-report.json'
    report = activity.verify_receipt(path)
    clock = report['clock']
    if clock['start_frame'] != 0 or clock['stride'] != 1 or clock['frames'] != round(clock['fps']*clock['picture_seconds']):
        raise ValueError('Cue binding/checking requires a full-loop activity receipt at every production frame')
    state = json.loads((path.parent/'state.json').read_text())
    scene = json.loads((path.parent/'scene.snapshot.json').read_text())
    actions = {}
    for action in report['actions']:
        rows = [row for row in state['views'][0]['layers'] if row['layer'] in action['layers']]
        # Output crop is excluded; inherited/world travel remains picture action.
        signatures = {row['layer']: [{k: sample[k] for k in ['cell', 'painted_sha256', 'visible', 'opacity', 'local_matrix', 'world_matrix', 'channels', 'binding_values']}
                                      for sample in row['samples']] for row in rows}
        changes = [any(samples[i] != samples[i-1] for samples in signatures.values()) for i in range(clock['frames'])]
        onsets = [i for i, changed in enumerate(changes) if changed and not changes[i-1]]
        authored = {l['id']: {'cycle_seconds':l.get('cycle_seconds'), 'phase_frames':l.get('phase_frames'),
                    'motion_cycles':l.get('motion', {}).get('cycles') if l.get('motion') else None,
                    'motion_phase':l.get('motion', {}).get('phase') if l.get('motion') else None,
                    'track_times':{k:[v[0] for v in t['keys']] for k,t in l.get('tracks', {}).items()}}
                    for l in scene['layers'] if l['id'] in action['layers']}
        actions[action['id']] = {'state_sha256': canonical(signatures), 'onset_frames': onsets, 'layers': action['layers'], 'authored_cadence':authored}
    return {'receipt': str(path), 'receipt_sha256': activity.digest(path), 'clock': clock, 'actions': actions,
            'scene_sha256': report['scene_sha256'], 'catalog_sha256': report['catalog_sha256'], 'plan': report.get('plan')}


def validate_sync(sync, session):
    activity.fields(sync, ['version', 'picture', 'links', 'sources', 'selected_pcm'], 'picture_sync')
    if sync.get('version') != 1: raise ValueError('picture_sync requires version 1')
    activity.fields(sync['picture'], ['receipt', 'receipt_sha256', 'clock', 'actions', 'scene_sha256', 'catalog_sha256', 'plan'], 'picture identity')
    if not isinstance(sync.get('links'), list) or not sync['links']: raise ValueError('picture_sync requires explicit cue links')
    seen = set()
    for link in sync['links']:
        activity.fields(link, ['clip_id', 'action_id', 'picture_frames', 'offset_samples'], 'cue link')
        if not isinstance(link.get('clip_id'), str) or not link['clip_id'] or link['clip_id'] in seen: raise ValueError('Cue link requires a unique clip_id')
        seen.add(link['clip_id'])
        if link['action_id'] not in sync['picture']['actions']: raise ValueError('Cue link requires a measured action_id')
        if type(link['offset_samples']) is not int: raise ValueError('Cue offset_samples must be an explicit signed integer')
        if not isinstance(link['picture_frames'], list) or not link['picture_frames']:
            raise ValueError('Cue picture_frames must identify explicit picture anchors')
        if any(type(f) is not int or not 0 <= f < sync['picture']['clock']['frames'] for f in link['picture_frames']):
            raise ValueError('Cue picture_frames must lie on the measured picture clock')
        if link['picture_frames'] != sorted(set(link['picture_frames'])): raise ValueError('Cue picture_frames must be unique and increasing')


def pcm_identity(path):
    from .audio import wav_info
    info = wav_info(path)
    with wave.open(str(path), 'rb') as wav:
        pcm = wav.readframes(wav.getnframes())
    return {'path': str(Path(path).resolve()), 'sha256': activity.digest(path), 'pcm_sha256': hashlib.sha256(pcm).hexdigest(), **info}


def source_identities(project, session, infos):
    from .audio import inside
    return {s['id']: pcm_identity(inside(project, s['path'])) for s in session['sources'] if s['id'] in infos}


def alignment(session, picture, links):
    rows = []; clips = {c['id']: c for c in session['clips']}; fps = picture['clock']['fps']; rate = session['sample_rate']
    for link in links:
        clip = clips.get(link['clip_id'])
        if clip is None:
            rows.append({'clip_id':link['clip_id'], 'action_id':link['action_id'], 'aligned':False, 'missing_clip':True})
            continue
        starts = [clip['at_frame'] + i * clip.get('every_frames', clip['frames']) for i in range(clip.get('repeat', 1))]
        positions = [f*rate/fps + link['offset_samples'] for f in link['picture_frames']]
        if any(n != round(n) for n in positions): raise ValueError('Picture cue falls between PCM samples; choose explicit sample-aligned picture/offset timing')
        expected = list(map(round, positions))
        rows.append({'clip_id': link['clip_id'], 'action_id': link['action_id'], 'actual_start_samples': starts,
                     'picture_anchor_samples': expected, 'delta_samples': [a-b for a,b in zip(starts, expected)],
                     'unmapped_repeat_count':abs(len(starts)-len(expected)), 'aligned': starts == expected})
    return rows


def bind(args, project):
    from .audio import argument_path, load_session, write_json
    source = argument_path(project, args.session); session, infos = load_session(project, source)
    picture = snapshot(args.activity)
    links = json.loads(args.links.read_text())
    selected = pcm_identity(args.pcm) if args.pcm else None
    sync = {'version': 1, 'picture': picture, 'links': links, 'sources': source_identities(project, session, infos), 'selected_pcm': selected}
    validate_sync(sync, session)
    if session['frames']/session['sample_rate'] != picture['clock']['picture_seconds']: raise ValueError('Session and picture loop lengths must match for cue binding')
    aligned = alignment(session, picture, links)
    if not all(row['aligned'] for row in aligned): raise ValueError('Cue samples do not match explicit picture anchors/offsets; edit the session or links deliberately')
    if selected and (selected['sample_rate'] != session['sample_rate'] or selected['frames'] != session['frames']):
        raise ValueError('Selected PCM must match the exact session sample clock and length')
    out = args.out.resolve()
    if out.exists(): raise ValueError('Cue-bound session output exists; preserve the source and choose a fresh file')
    session['picture_sync'] = sync
    write_json(out, session)
    return {'ok': True, 'session': str(out), 'session_sha256': activity.digest(out), 'alignment': aligned,
            'selected_pcm': selected, 'listening_status': 'unreviewed', 'waveform_modified': False}


def check(args, project):
    from .audio import argument_path, load_session
    session, infos = load_session(project, argument_path(project, args.session))
    sync = session.get('picture_sync')
    if not sync: raise ValueError('Session has no explicit picture_sync; use audio cue-bind')
    current = snapshot(args.activity); old = sync['picture']; issues = []
    if current['clock']['picture_seconds'] != old['clock']['picture_seconds']:
        issues.append({'code': 'picture_loop_changed', 'before_seconds': old['clock']['picture_seconds'], 'after_seconds': current['clock']['picture_seconds']})
    if current['clock']['fps'] != old['clock']['fps']: issues.append({'code': 'picture_fps_changed'})
    for link in sync['links']:
        id = link['action_id']; before = old['actions'][id]; after = current['actions'].get(id)
        if after is None: code = 'picture_action_deleted'
        elif before == after: continue
        elif any(before['authored_cadence'].get(l, {}).get(k) != after['authored_cadence'].get(l, {}).get(k)
                 for l in set(before['layers']+after['layers']) for k in ['cycle_seconds', 'motion_cycles']): code = 'picture_action_repeated_or_removed'
        elif before['authored_cadence'] != after['authored_cadence']: code = 'picture_action_retimed'
        elif len(before['onset_frames']) != len(after['onset_frames']): code = 'picture_action_repeated_or_removed'
        elif before['onset_frames'] != after['onset_frames']: code = 'picture_action_retimed'
        else: code = 'picture_action_changed'
        issues.append({'code': code, 'action_id': id, 'clip_id': link['clip_id'], 'before': before, 'after': after,
                       'next_action': 'Review the chosen picture and explicitly edit cue anchors/session timing if required; no audio was retimed.'})
    aligned = alignment(session, old, sync['links'])
    for row in aligned:
        if not row['aligned']: issues.append({'code': 'cue_session_retimed', **row})
    sources = source_identities(project, session, infos)
    if sources != sync['sources']: issues.append({'code': 'cue_sources_changed'})
    pcm = pcm_identity(args.pcm) if args.pcm else None
    if pcm and sync['selected_pcm'] and {k:v for k,v in pcm.items() if k != 'path'} != {k:v for k,v in sync['selected_pcm'].items() if k != 'path'}:
        issues.append({'code': 'selected_pcm_changed'})
    if session['frames']/session['sample_rate'] != current['clock']['picture_seconds']: issues.append({'code': 'session_picture_length_mismatch'})
    return {'ok': not issues, 'kind': 'ambiance-cue-diagnostics', 'schema_version': 1, 'issues': issues, 'alignment': aligned,
            'current_picture': {'receipt': current['receipt'], 'receipt_sha256': current['receipt_sha256']},
            'source_identities': sources, 'selected_pcm': pcm, 'listening_status': 'unreviewed', 'waveform_modified': False,
            'view_policy': 'Identical action state and clock may reuse exact PCM across views; no audition is inferred.'}


def add_parsers(group):
    for name in ['cue-bind', 'cue-check']:
        p = group.add_parser(name); p.add_argument('session', type=Path); p.add_argument('--activity', type=Path, required=True)
        p.add_argument('--pcm', type=Path); add_output(p, Output.FILE if name == 'cue-bind' else Output.REPORT, type=Path, required=name == 'cue-bind')
        if name == 'cue-bind': p.add_argument('--links', type=Path, required=True)
