"""Immutable reports about exact movies, with independently authored dispositions."""
import math
import uuid
from pathlib import Path

import studio
from . import deliveries, revisions
from .project import project_lock
from .errors import CommandError

FORMAT = 'ambiance-movie-feedback'
EVENT = 'ambiance-feedback-event'


def _text(value, label, maximum=10000):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f'{label} needs 1–{maximum} characters')
    return value.strip()


def _path(project, id):
    return studio.inside(project, f'feedback/movies/{revisions.identifier(id)}.json')


def _references(project, refs):
    if not isinstance(refs, list):
        raise ValueError('Feedback references must be a list')
    for ref in refs:
        revisions.fields(ref, {'kind', 'file', 'sha256', 'revision', 'element_ids', 'action_ids'}, 'feedback reference')
        if ref.get('kind') == 'source':
            if set(ref) != {'kind', 'file', 'sha256'}:
                raise ValueError('Source reference needs file and sha256')
            if studio.digest(studio.inside(project, ref['file'])) != ref['sha256']:
                raise ValueError('Feedback source changed')
        elif ref.get('kind') == 'plan':
            from . import production_plan
            if set(ref) != {'kind', 'revision', 'sha256', 'element_ids', 'action_ids'}:
                raise ValueError('Plan reference needs revision, sha256 and element/action IDs')
            context = production_plan.load_context(project, revision=ref['revision'])
            if not context or context.get('plan_sha256') != ref['sha256']:
                raise ValueError('Feedback plan identity differs')
            for key, collection in [('element_ids', 'elements'), ('action_ids', 'actions')]:
                if not isinstance(ref[key], list) or any(id not in {r['id'] for r in context['plan'][collection]} for id in ref[key]):
                    raise ValueError('Unknown feedback plan reference')
        else:
            raise ValueError('Unknown feedback reference kind')
    return refs


def add(project, delivery, note, reporter, *, scope='entry', view=None, role=None,
        seconds=None, start=None, end=None, observer=None, references=None, request_id=None):
    note = _text(note, 'Feedback'); reporter = _text(reporter, 'Reporter', 200)
    if observer is not None: observer = _text(observer, 'Observer', 200)
    if request_id is not None: revisions.identifier(request_id)
    with project_lock(project):
        data = deliveries.load(project, delivery)
        subject = {'kind': scope, 'delivery': delivery, 'delivery_sha256': data['payload_sha256']}
        timeline = None
        if scope == 'delivery':
            if any(v is not None for v in (view, role, seconds, start, end)):
                raise ValueError('Delivery-wide feedback cannot specify a view, role or time')
        elif scope == 'entry':
            candidates = [(k, e) for k, e in deliveries.entries(data).items() if (view is None or e.get('view', 'authored') == view) and (role is None or e['role'] == role)]
            if len(candidates) != 1: raise ValueError('Choose an explicit view and role identifying one feedback movie')
            key, entry = candidates[0]
            if not deliveries.intact(project, entry['movie'])['ok']:
                raise ValueError('Movie changed; cannot attach feedback to these bytes')
            subject.update(entry=key, movie=entry['movie'], role=entry['role'], view=entry.get('view', 'authored'))
            subject.update({k: entry[k] for k in ['view_sha256', 'revision', 'edition'] if entry.get(k) is not None})
            for v in (seconds, start, end):
                if v is not None and (type(v) not in (int, float) or not math.isfinite(v)):
                    raise ValueError('Feedback time must be finite')
            if seconds is not None:
                if start is not None or end is not None or not 0 <= seconds < entry['duration_seconds']:
                    raise ValueError('Feedback point must fall inside the selected movie and exclude a range')
                timeline = {'kind': 'point', 'seconds': seconds}
            elif start is not None or end is not None:
                if start is None or end is None or not 0 <= start < end <= entry['duration_seconds']:
                    raise ValueError('Feedback range must fall inside the selected movie')
                timeline = {'kind': 'range', 'start_seconds': start, 'end_seconds': end}
        else:
            raise ValueError('Feedback scope must be delivery or entry')
        content = dict(subject=subject, time=timeline, reporter=reporter, observer=observer,
                       note=note, references=_references(project, references or []), request_id=request_id)
        id = uuid.uuid5(uuid.NAMESPACE_URL, 'ambiance-feedback:'+request_id).hex if request_id else uuid.uuid4().hex
        path = _path(project, id)
        if path.exists():
            old = revisions.read_sealed(path, FORMAT, versions=(3,))
            if any(old.get(k) != v for k, v in content.items()):
                raise ValueError('Feedback request ID already has different content')
            return {'ok': True, 'reused': True, 'feedback': inspect(project, id), 'path': str(path)}
        record = revisions.seal(dict(format=FORMAT, schema_version=3, id=id, created_utc=deliveries.now(), **content))
        studio.write(path, record)
    return {'ok': True, 'reused': False, 'feedback': inspect(project, id), 'path': str(path)}


def inspect(project, id):
    path = _path(project, id)
    raw = revisions.read_sealed(path, FORMAT, versions=(1, 2, 3))
    if raw['id'] != id: raise ValueError('Feedback identity mismatch')
    row = dict(raw)
    if raw['schema_version'] < 3:
        row.update(subject={k: raw[k] for k in ['delivery', 'entry', 'movie', 'role', 'view', 'view_sha256', 'revision', 'edition'] if k in raw},
                   time={'kind': 'point', 'seconds': raw['seconds']}, reporter=raw['observer'])
        row['subject'].update(kind='entry')
    subject = row['subject']; timeline = row.get('time')
    # Compatibility aliases are projections, never a rewrite of the observation.
    row.update({k: subject[k] for k in ['delivery', 'entry', 'movie', 'role', 'view', 'view_sha256', 'revision', 'edition'] if k in subject})
    row['seconds'] = timeline.get('seconds', timeline.get('start_seconds')) if timeline else None
    row.update(state='open', head=raw['payload_sha256'], events=[], path=str(path), integrity={'ok': True, 'errors': []})
    events = studio.inside(project, f'feedback/events/{revisions.identifier(id)}')
    for number, event_path in enumerate(sorted(events.glob('*.json')), 1):
        event = revisions.read_sealed(event_path, EVENT)
        if (event.get('feedback') != id or event.get('observation_sha256') != raw['payload_sha256'] or
                event.get('sequence') != number or event.get('previous_sha256') != row['head'] or
                event.get('from_state') != row['state'] or event.get('state') not in ['open', 'resolved'] or
                event.get('state') == row['state']):
            raise ValueError('Feedback event chain is invalid')
        row['state'] = event['state']; row['head'] = event['payload_sha256']; row['events'].append(event)
    try:
        delivery = deliveries.load(project, subject['delivery'])
        if subject.get('delivery_sha256') and delivery['payload_sha256'] != subject['delivery_sha256']:
            raise ValueError('Feedback delivery identity changed')
        if subject.get('movie') and not deliveries.intact(project, subject['movie'])['ok']:
            raise ValueError('Referenced movie is missing or changed')
        _references(project, row.get('references', []))
        for event in row['events']:
            for ref in event.get('evidence', []):
                if studio.digest(studio.inside(project, ref['path'])) != ref['sha256']:
                    raise ValueError('Resolution evidence is missing or changed')
    except (OSError, ValueError, KeyError, TypeError) as error:
        row['integrity'] = {'ok': False, 'errors': [str(error)]}
    return row


def listing(project, delivery=None, state=None, limit=1000, offset=0):
    if state not in (None, 'open', 'resolved') or type(limit) is not int or not 1 <= limit <= 1000 or type(offset) is not int or offset < 0:
        raise ValueError('Invalid feedback state or pagination')
    rows = [inspect(project, p.stem) for p in (project/'feedback/movies').glob('*.json')]
    rows = [r for r in rows if (delivery is None or r['delivery'] == delivery) and (state is None or r['state'] == state)]
    rows.sort(key=lambda r: (r['created_utc'], r['id']), reverse=True)
    return {'ok': True, 'feedback': rows[offset:offset+limit], 'total': len(rows),
            'next_offset': offset+limit if offset+limit < len(rows) else None}


def transition(project, id, state, reporter, reason, expected, resolution=None):
    reporter = _text(reporter, 'Reporter', 200); reason = _text(reason, 'Reason')
    if state not in ['open', 'resolved']: raise ValueError('Unknown feedback state')
    with project_lock(project):
        row = inspect(project, id)
        if row['head'] != expected: raise CommandError('Feedback changed; inspect its current head.', 'stale_feedback', 2)
        if row['state'] == state: raise ValueError('Feedback is already '+state)
        evidence = []
        if state == 'resolved':
            revisions.fields(resolution, {'outcome', 'note', 'revision', 'delivery', 'feedback'}, 'feedback resolution')
            outcome = resolution.get('outcome')
            if outcome not in ['addressed', 'withdrawn', 'superseded']: raise ValueError('Unknown feedback outcome')
            if outcome == 'addressed':
                if not resolution.get('revision') and not resolution.get('delivery'): raise ValueError('Addressed feedback needs a revision or delivery')
                for kind in ['revision', 'delivery']:
                    if resolution.get(kind):
                        target = resolution[kind]
                        if kind == 'revision':
                            revisions.load(project, target); path = revisions.manifest_path(project, target)
                        else:
                            data = deliveries.load(project, target); path = deliveries.record_path(project, target)
                            if any(not deliveries.intact(project, e['movie'])['ok'] for e in deliveries.entries(data).values()):
                                raise ValueError('Resolution delivery movie changed')
                        evidence.append(revisions.ref(project, path, 'feedback-resolution', kind))
            elif outcome == 'superseded':
                target = resolution.get('feedback')
                if target == id: raise ValueError('Feedback cannot supersede itself')
                inspect(project, target); evidence.append(revisions.ref(project, _path(project, target), 'feedback-resolution', 'feedback'))
            if not row['integrity']['ok']: raise ValueError('Feedback references need attention before resolution')
        event = revisions.seal(dict(format=EVENT, schema_version=1, id=uuid.uuid4().hex,
            feedback=id, observation_sha256=row['payload_sha256'], sequence=len(row['events'])+1,
            previous_sha256=row['head'], from_state=row['state'], state=state, reporter=reporter,
            created_utc=deliveries.now(), reason=reason, resolution=resolution, evidence=evidence))
        path = studio.inside(project, f'feedback/events/{id}/{event["sequence"]:08d}-{event["id"]}.json')
        studio.write(path, event)
    return {'ok': True, 'feedback': inspect(project, id), 'path': str(path)}


def add_parsers(group):
    q = group.add_parser('add'); q.add_argument('delivery'); q.add_argument('--scope', choices=['delivery', 'entry'])
    q.add_argument('--role', choices=list(deliveries.ROLES)); q.add_argument('--view'); q.add_argument('--time', type=float)
    q.add_argument('--from', dest='start', type=float); q.add_argument('--to', dest='end', type=float)
    note = q.add_mutually_exclusive_group(required=True); note.add_argument('--note'); note.add_argument('--note-file', type=Path)
    q.add_argument('--by', required=True); q.add_argument('--observed-by'); q.add_argument('--request-id'); q.add_argument('--references', type=Path)
    q = group.add_parser('list'); q.add_argument('delivery', nargs='?'); q.add_argument('--state', choices=['open', 'resolved'])
    q.add_argument('--limit', type=int, default=20); q.add_argument('--offset', type=int, default=0)
    q = group.add_parser('inspect'); q.add_argument('id')
    for name in ['resolve', 'reopen']:
        q = group.add_parser(name); q.add_argument('id'); q.add_argument('--by', required=True); q.add_argument('--expect-head', required=True)
        if name == 'resolve': q.add_argument('--resolution', type=Path, required=True)
        else: q.add_argument('--note', required=True)


def run(args, project):
    if args.action == 'add':
        refs = studio.read(args.references) if args.references else []
        note = args.note_file.read_text() if args.note_file else args.note
        if args.note_file:
            path = args.note_file.resolve()
            if path.is_relative_to(project.resolve()):
                refs = [*refs, {'kind': 'source', 'file': str(path.relative_to(project.resolve())), 'sha256': studio.digest(path)}]
        if args.scope is None and (args.role is None or args.time is None):
            raise ValueError('Choose --scope delivery/entry, or supply the legacy --role and --time')
        return add(project, args.delivery, note, args.by, scope=args.scope or 'entry', view=args.view, role=args.role,
                   seconds=args.time, start=args.start, end=args.end, observer=args.observed_by or (args.by if args.scope is None else None),
                   references=refs, request_id=args.request_id)
    if args.action == 'list': return listing(project, args.delivery, args.state, args.limit, args.offset)
    if args.action == 'inspect': return {'ok': True, 'feedback': inspect(project, args.id)}
    resolution = studio.read(args.resolution) if args.action == 'resolve' else None
    return transition(project, args.id, 'resolved' if resolution is not None else 'open', args.by,
                      resolution.get('note') if resolution is not None else args.note, args.expect_head, resolution)
