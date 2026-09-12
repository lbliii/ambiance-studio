"""Portable early movie reviews over the existing iteration and edition services."""
import html
import json
import math
from pathlib import Path
import shutil
import tempfile
from urllib.parse import quote
import studio
from . import deliveries, revisions, iteration_recipes, production
from .project import project_lock, locations

REQUEST = 'ambiance-review-packet-request'
FORMAT = 'ambiance-review-packet'


def add_parsers(group):
    sub = group.add_parser('packet').add_subparsers(dest='packet_action', required=True)
    q = sub.add_parser('init'); q.add_argument('file', type=Path); q.add_argument('--out', type=Path, required=True)
    q = sub.add_parser('run'); q.add_argument('file', type=Path); q.add_argument('--by', required=True)
    q = sub.add_parser('inspect'); q.add_argument('file', type=Path)


def initialize(project, request, out):
    revisions.fields(request, {'format', 'schema_version', 'iteration', 'audible_role', 'interval', 'auditions', 'questions', 'feedback_ids'}, 'packet request')
    if request.get('format') != REQUEST or request.get('schema_version') != 1: raise ValueError('Expected ambiance-review-packet-request schema_version 1')
    out = Path(out).resolve(); project = project.resolve()
    if out.exists() or not out.is_relative_to(project): raise ValueError('Choose a fresh packet bundle inside the project')
    from .recipe_config import expanded
    iteration = expanded(project, request['iteration']); role = request.get('audible_role')
    if role not in [e['role'] for e in iteration.get('editions', [])]: raise ValueError('Packet audible role must be an explicit iteration role')
    interval = request.get('interval'); questions = request.get('questions', [])
    if not isinstance(questions, list) or len(questions) > 20 or any(not isinstance(q, str) or not q.strip() or len(q) > 1000 for q in questions):
        raise ValueError('Packet questions must be bounded nonempty text')
    from . import feedback
    feedback_ids = request.get('feedback_ids', [])
    if not isinstance(feedback_ids, list) or len(feedback_ids) > 20: raise ValueError('Packet feedback IDs must be a bounded list')
    for id in feedback_ids: feedback.inspect(project, id)
    auditions = request.get('auditions', [])
    if not isinstance(auditions, list) or len(auditions) > 20: raise ValueError('Packet auditions must be a bounded list')
    sources = [revisions.ref(project, studio.inside(project, name), 'review-packet', 'audition') for name in auditions]
    scene, _ = locations(project)
    duration = studio.read(scene)['canvas']['loop_seconds']*next(e.get('repeats', 1) for e in iteration['editions'] if e['role'] == role)
    interval = interval if interval is not None else [0, duration]
    if not isinstance(interval, list) or len(interval) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) for v in interval) or not 0 <= interval[0] < interval[1] <= duration:
        raise ValueError('Packet review interval must fall inside the selected movie')
    # Publish the complete packet request and recipe bundle in one rename.
    def complete_bundle(bundle, built):
        def ref(name, role):
            value = revisions.ref(bundle, bundle/name, 'review-packet', role)
            value['path'] = str((out/name).relative_to(project))
            return value
        if revisions.changed(project, sources): raise ValueError('Audition sources changed during initialization')
        document = revisions.seal(dict(format=REQUEST, schema_version=1, recipe=ref('iteration.json', 'recipe'),
            inputs=ref('inputs.json', 'inputs'), selection=ref('capture-selection.json', 'selection'),
            interval=interval, audible_role=role, auditions=sources, questions=questions, feedback_ids=feedback_ids))
        studio.write(bundle/'packet-request.json', document)
    result = iteration_recipes.initialize(project, request['iteration'], out, complete_bundle=complete_bundle)
    return {'ok': True, 'request': str(out/'packet-request.json'), **result}


def verify(project, path):
    path = Path(path).resolve(); data = revisions.read_sealed(path, FORMAT)
    for ref in data['artifacts']:
        relative = ref['path']; target = studio.inside(path.parent, relative)
        if studio.digest(target) != ref['sha256'] or target.stat().st_size != ref['bytes']: raise ValueError('Packet artifact changed: '+relative)
    delivery = deliveries.load(project, data['delivery'])
    if delivery['payload_sha256'] != data['delivery_sha256']: raise ValueError('Packet delivery changed')
    return data


def player_page(data):
    escape = html.escape
    videos = ''.join(f'<section><h2>{escape(e["view"])}</h2><video controls playsinline preload="metadata" src="{quote(e["file"])}" muted></video></section>' for e in data['movies'])
    auditions = ''.join(f'<li>{escape(a["label"])} <audio controls preload="none" src="{quote(a["file"])}"></audio></li>' for a in data['auditions'])
    questions = ''.join(f'<li>{escape(q)}</li>' for q in data['questions'])
    # Media paths are generated locally; no JSON fetch is required under file://.
    return f'''<!doctype html><meta charset="utf-8"><title>{escape(data['delivery'])} — review packet</title>
<style>body{{background:#18171b;color:#eee;font:17px system-ui;margin:2rem}}main{{display:flex;gap:1rem}}section{{flex:1;min-width:0}}video{{width:100%;max-height:70vh;background:#000}}button,input{{font:inherit;margin:.5rem}}audio{{display:block}}a{{color:#ddd}}</style>
<h1>{escape(data['delivery'])}</h1><p>Paired movie review · Approximate playback synchronization · Sound from the first view. Observations are recorded separately.</p>
<main>{videos}</main><button id="play">Play both</button><label><input id="loop" type="checkbox" checked>Loop review range</label>
<input id="seek" aria-label="Review time" type="range" min="{data['interval'][0]}" max="{data['interval'][1]}" step=".033" value="{data['interval'][0]}">
<p id="playback-status" role="status"></p>
<h2>Review questions</h2><ul>{questions}</ul><h2>Source auditions</h2><ul>{auditions}</ul>
<script>
const players=[...document.querySelectorAll('video')],auditions=[...document.querySelectorAll('audio')],lead=players[0],button=document.querySelector('#play'),seek=document.querySelector('#seek'),loop=document.querySelector('#loop');
lead.muted=false;const start=Number(seek.min),end=Number(seek.max);
function pauseAll(){{players.forEach(p=>p.pause());button.textContent='Play both';}}
async function playAll(){{auditions.forEach(p=>p.pause());players.slice(1).forEach(p=>{{p.muted=true;p.currentTime=lead.currentTime;}});try{{await Promise.all(players.map(p=>p.play()));button.textContent='Pause both';}}catch(e){{pauseAll();button.textContent=e.message;}}}}
players.forEach(p=>p.addEventListener('loadedmetadata',()=>{{p.currentTime=start;}}));
button.onclick=()=>lead.paused?playAll():pauseAll();seek.oninput=()=>{{players.forEach(p=>p.currentTime=Number(seek.value));}};
lead.addEventListener('play',()=>{{if(players.slice(1).some(p=>p.paused))playAll();}});lead.addEventListener('pause',()=>{{players.slice(1).forEach(p=>p.pause());}});
lead.addEventListener('seeking',()=>{{players.slice(1).forEach(p=>p.currentTime=lead.currentTime);}});
lead.addEventListener('timeupdate',()=>{{seek.value=lead.currentTime;players.slice(1).forEach(p=>{{if(Math.abs(p.currentTime-lead.currentTime)>.15)p.currentTime=lead.currentTime;}});if(lead.currentTime>=end-.02){{if(loop.checked){{players.forEach(p=>p.currentTime=start);playAll();}}else pauseAll();}}}});
players.slice(1).forEach(p=>{{p.controls=false;p.addEventListener('volumechange',()=>{{if(!p.muted)p.muted=true;}});}});
auditions.forEach(a=>a.addEventListener('play',()=>{{pauseAll();auditions.filter(p=>p!==a).forEach(p=>p.pause());}}));
let lastTime=0,advanced=performance.now();const playbackStatus=document.querySelector('#playback-status');
setInterval(()=>{{const now=performance.now();if(lead.paused||lead.currentTime!==lastTime)advanced=now;lastTime=lead.currentTime;
if(!lead.paused)players.slice(1).forEach(p=>{{if(Math.abs(p.currentTime-lead.currentTime)>.15)p.currentTime=lead.currentTime;}});
playbackStatus.textContent=!lead.paused&&now-advanced>2000?'Playback is waiting for the first movie. Check its play or sound controls.':'';}},250);
</script>'''


def execute(project, request_path, actor):
    project = project.resolve(); request_path = Path(request_path).resolve()
    if not request_path.is_relative_to(project): raise ValueError('Packet request must be inside the project')
    request = revisions.read_sealed(request_path, REQUEST)
    if revisions.changed(project, [request['recipe'], request['inputs'], request['selection'], *request['auditions']]): raise ValueError('Packet inputs changed')
    recipe = studio.read(studio.inside(project, request['recipe']['path'])); out = request_path.parent/'packet'
    if out.exists():
        verify(project, out/'packet.json'); return {'ok': True, 'reused': True, 'packet': str(out/'packet.json'), 'player': str(out/'index.html')}
    if not revisions.manifest_path(project, recipe['revision']).exists() and revisions.changed(project, studio.read(studio.inside(project, request['inputs']['path']))):
        raise ValueError('Working inputs changed since packet initialization; initialize a new packet')
    production.iteration(project, recipe, actor, present=False)
    delivery = deliveries.load(project, recipe['id'])
    selected = [(id, e) for id, e in deliveries.entries(delivery).items() if e['role'] == request['audible_role']]
    if {e.get('view', 'authored') for _, e in selected} != set(recipe['views']): raise ValueError('Packet is missing a requested view')
    with project_lock(project), tempfile.TemporaryDirectory(prefix='.packet-', dir=out.parent) as temporary:
        bundle = Path(temporary)/'packet'; bundle.mkdir(); (bundle/'movies').mkdir(); (bundle/'auditions').mkdir()
        movies = []; auditions = []
        for id, entry in selected:
            if not deliveries.intact(project, entry['movie'])['ok']: raise ValueError('Packet movie changed')
            relative = f'movies/{id}.mp4'; shutil.copyfile(studio.inside(project, entry['movie']['path']), bundle/relative)
            movies.append(dict(entry=id, view=entry.get('view', 'authored'), role=entry['role'], file=relative, revision=entry.get('revision'), edition=entry.get('edition'), source=entry['movie']))
        for index, source in enumerate(request['auditions']):
            file = studio.inside(project, source['path']); relative = f'auditions/{index:02d}{file.suffix}'
            shutil.copyfile(file, bundle/relative); auditions.append(dict(file=relative, label=file.name, source=source))
        data = dict(format=FORMAT, schema_version=1, delivery=delivery['id'], delivery_sha256=delivery['payload_sha256'],
                    movies=movies, auditions=auditions, interval=request['interval'], questions=request['questions'], feedback_ids=request['feedback_ids'],
                    synchronization='approximate-movie-playback', created_utc=deliveries.now(), observations_performed=False)
        (bundle/'index.html').write_text(player_page(data))
        data['artifacts'] = [dict(path=str(p.relative_to(bundle)), sha256=studio.digest(p), bytes=p.stat().st_size) for p in sorted(bundle.rglob('*')) if p.is_file()]
        for movie in movies:
            if studio.digest(bundle/movie['file']) != movie['source']['sha256']: raise ValueError('Movie changed while packaging')
        for audition in auditions:
            if studio.digest(bundle/audition['file']) != audition['source']['sha256']: raise ValueError('Audition source changed while packaging')
        studio.write(bundle/'packet.json', revisions.seal(data)); bundle.rename(out)
    return {'ok': True, 'packet': str(out/'packet.json'), 'player': str(out/'index.html'), 'delivery': delivery['id'],
            'movies': [str(out/m['file']) for m in movies], 'current_review_changed': False}


def run(args, project):
    if args.packet_action == 'init':
        from .recipe_config import read
        return initialize(project, read(args.file), args.out)
    if args.packet_action == 'inspect': return {'ok': True, 'packet': verify(project, args.file)}
    return execute(project, args.file, args.by)
