"""Build revision/edition review contexts, status and explicit handoffs.

The studio gate validator remains the verdict authority. Captured identities,
working divergence and performed reviews are separate parts of the context.
"""
from pathlib import Path
import tempfile

import studio
from .record_contracts import identifier
from .project_references import relative, changed, unique
from .revision_capture import manifest_path, load, check, compare
from .editions import edition_path, load_edition, captured_view


def review_context(project, id, edition=None, view=None):
    data = load(project, id)
    controls = data['controls']; refs = list(data['dependencies']); final_files = []
    subject = {'mode': 'revision', 'revision': id, 'revision_sha256': studio.digest(manifest_path(project, id)),
               'edition': edition, 'dependency_policy': 1}
    if edition:
        ed = load_edition(project, id, edition); refs += ed['dependencies']; final_files = [ed['output']['path']]
        subject['edition_sha256'] = studio.digest(edition_path(project, id, edition))
        inherited=ed['view']['id'] if ed['schema_version']==2 else 'authored'
        if view is not None and view!=inherited:raise ValueError('Review view differs from the selected edition')
        view=inherited
    selected=captured_view(project,id,view) if view not in [None,'authored'] else None
    if selected:subject.update(view=selected['id'],view_sha256=selected['sha256'])
    plan_context = None
    if 'production_plan' in controls:
        from . import production_plan
        plan_context = production_plan.load_context(project, id, verify=False)
        subject['production_plan'] = {'schema_version': 1, 'plan_sha256': plan_context['plan_sha256'],
                                      'expectation_sha256': plan_context['expectation_sha256']}
    gates = studio.read(studio.inside(project, controls['pipeline']))
    settings = studio.read(studio.inside(project, controls['settings']))
    all_roles = {r['role'] for r in refs}
    required = {'intent': {'reference', 'brief'}, 'layout': {'layer_plan'}, 'assets': {'image'}, 'animation': {'scene'},
                'sound-design': {'sound_plan', 'audio_source'}, 'mix': {'master'}, 'export': {'edition_output'}, 'release': {'edition_output'}}
    if plan_context: required['layout'] = {'production_plan'}
    def relevant(gate): return unique([r for r in refs if r['section'] in [gate, 'policy'] or
                                      (plan_context and r['role'] in ['production_plan', 'production_source', 'production_driver'])])
    def snapshot(gate):
        return {r['path']: studio.digest(studio.inside(project, r['path'])) if studio.inside(project, r['path']).is_file() else None for r in relevant(gate)}
    def issues(gate):
        errors = [f'Selected {r["role"]} changed: {r["path"]}' for r in changed(project, relevant(gate))]
        errors += [f'Selected revision lacks {role}' for role in sorted(required.get(gate, set())-all_roles)]
        if studio.digest(manifest_path(project, id)) != subject['revision_sha256']: errors.append('Revision manifest changed')
        if edition and studio.digest(edition_path(project, id, edition)) != subject['edition_sha256']: errors.append('Edition manifest changed')
        if gate == 'mix':
            complete = set(data['sound_complete']) | (set(ed.get('sound_complete', [])) if edition else set())
            chosen = ([ed['audio']['path']] if ed.get('audio') else []) if edition else [m['path'] for m in data['masters']]
            if not chosen or any(path not in complete for path in chosen): errors.append('Selected master lacks an explicit audio-run or external-preparation dependency record')
        return errors
    return {'settings': settings, 'pipeline': gates, 'subject': subject, 'plan_context': plan_context,
            'review_dir': studio.inside(project, f'reviews/revisions/{id}/'+(f'editions/{identifier(edition)}' if edition else f'views/{selected["id"]}/picture' if selected else 'picture')),
            'snapshot': snapshot, 'issues': issues, 'final_files': final_files}


def status(project, id, edition=None, view=None):
    return studio.gate_status(project, review_context(project, id, edition, view))


def project_status(project):
    result = studio.gate_status(project); result['revisions'] = []
    for path in sorted((project/'revisions').glob('*/manifest.json')):
        id = path.parent.name; item = {'id': id, 'integrity': check(project, id)}
        try:
            item['working'] = compare(project, id); item['reviews'] = status(project, id); item['editions'] = []
            manifest=load(project,id);scene=studio.read(studio.inside(project,manifest['controls']['scene']))
            item['views']=[]
            for view_id in scene.get('framing',{}).get('views',{}):
                try:item['views'].append({'id':view_id,'reviews':status(project,id,view=view_id)})
                except (OSError,ValueError,KeyError,TypeError) as error:item['views'].append({'id':view_id,'ok':False,'error':str(error)})
            for ed in sorted((path.parent/'editions').glob('*.json')):
                try: item['editions'].append({'id': ed.stem, 'reviews': status(project, id, ed.stem)})
                except (OSError, ValueError, KeyError, TypeError) as error: item['editions'].append({'id': ed.stem, 'ok': False, 'error': str(error)})
        except (OSError, ValueError, KeyError, TypeError) as error: item['error'] = str(error)
        result['revisions'].append(item)
    return result


def handoff(project, id, edition, out):
    out = Path(out).resolve()
    if out.exists(): raise ValueError('Handoff output exists; choose a fresh directory')
    data = load(project, id); review = status(project, id, edition)
    payload = {'revision': id, 'edition': edition, 'integrity': check(project, id), 'working': compare(project, id), 'reviews': review,
               'manifest': relative(project, manifest_path(project, id)), 'masters': data['masters'],
               'edition_record': load_edition(project, id, edition) if edition else None}
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.handoff-', dir=out.parent) as temp:
        stage = Path(temp)/'result'; stage.mkdir(); studio.write(stage/'handoff.json', payload)
        lines = [f'# Revision {id}', '', f'Edition: {edition or "none selected"}', f'Release ready: {review["release_ready"]}', '',
                 'Captured inputs and review evidence are distinct from current working changes.', '', '## Gate status', '']
        lines += [f'- {gate}: {state["state"]}'+(' — '+'; '.join(state['reasons']) if state['reasons'] else '') for gate, state in review['gates'].items()]
        lines += ['', 'Exact paths and hashes are in handoff.json. No publishing or new creative review was performed.']
        (stage/'handoff.md').write_text('\n'.join(lines)+'\n')
        if out.exists(): raise ValueError('Handoff destination appeared; refusing replacement')
        stage.rename(out)
    return {'ok': True, 'directory': str(out), 'handoff': str(out/'handoff.md'), 'release_ready': review['release_ready']}
