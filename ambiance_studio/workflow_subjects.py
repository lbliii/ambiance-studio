"""Resolve exact workflow subjects without borrowing mutable working controls."""
from pathlib import Path

import studio
from . import deliveries, editions, record_contracts, revision_capture
from .coverage_context import AssessmentInputs
from .errors import CommandError

ERRORS = (OSError, ValueError, KeyError, TypeError, ImportError, CommandError)


class Query:
    def __init__(self, project):
        self.project = Path(project).resolve()
        self.inputs = {}
        self.watch = AssessmentInputs(self.project)
        self.directories = {}
        self.diagnostics = []

    def context(self, revision=None):
        if revision not in self.inputs:
            self.inputs[revision] = AssessmentInputs(self.project, revision)
        return self.inputs[revision]

    def files(self, directory, pattern):
        key = (str(directory), pattern)
        paths = sorted(directory.glob(pattern))
        self.directories.setdefault(key, [str(p) for p in paths])
        for p in paths: self.watch.track(p, 'evidence_index')
        return paths

    def read(self, path):
        return self.watch.read(path)

    def pin(self, path):
        record = self.watch.track(path, 'evidence_index')
        return {'path': str(path), 'sha256': record['sha256']}

    def finish(self):
        # Custom file owners need an available component to participate in finish.
        self.watch.components['evidence_index'] = {'state':'available'}
        self.watch.values['evidence_index'] = None
        snapshots = [ctx.finish() for ctx in self.inputs.values()] + [self.watch.finish(['evidence_index'])]
        changed = [r for s in snapshots for r in s['changed_inputs']]
        for (directory, pattern), before in self.directories.items():
            after = [str(p) for p in sorted(Path(directory).glob(pattern))]
            if before != after: changed.append({'path':directory,'pattern':pattern,'code':'inputs_changed'})
        return {'complete': all(s['complete'] for s in snapshots) and not changed,
                'changed_inputs':changed, 'snapshots':snapshots,
                'directories':[{'path':p,'pattern':pattern,'entries':entries} for (p,pattern),entries in sorted(self.directories.items())]}


def outputs(ctx, query):
    plan = ctx.get('plan')
    if plan is not None:
        return plan['outputs'], 'production-plan'
    if ctx.revision:
        manifest = ctx.get('revision')
        settings_path = manifest and manifest['controls'].get('settings')
        try:settings = query.read(studio.inside(query.project, settings_path)) if settings_path else {}
        except ERRORS as error:
            query.diagnostics.append({'component':'settings','message':str(error)});return [], 'unknown'
    else:
        try:settings = query.read(query.project/'project.json')
        except ERRORS as error:
            query.diagnostics.append({'component':'settings','message':str(error)});return [], 'unknown'
    chosen = settings.get('intended_views')
    if chosen is not None:
        if not isinstance(chosen,list) or any(not isinstance(v,str) for v in chosen):raise ValueError('Malformed intended_views')
        return [{'view_id':v,'roles':[]} for v in chosen], 'legacy-settings; roles undeclared'
    scene = ctx.get('scene')
    if scene is None: return [], 'unknown'
    # Native omission means authored canvas. Named views are not automatically chosen scope.
    return [{'view_id':'authored','roles':[]}], 'legacy authored canvas; roles undeclared'


def captured(query, revision, edition=None, view=None):
    ctx = query.context(revision)
    manifest = ctx.get('revision')
    if manifest is None:raise ValueError('Cannot resolve revision '+revision+': '+str(ctx.components['revision']))
    subject = {'mode':'revision','revision':revision, 'revision_sha256':query.pin(revision_capture.manifest_path(query.project,revision))['sha256'], 'edition':edition}
    if edition:
        path = editions.edition_path(query.project, revision, edition)
        query.pin(path)
        # The sealed declaration remains inspectable without a renderer. Full native
        # edition validation is performed below; an unavailable runtime stays unknown.
        ed = record_contracts.read_sealed(path, editions.EDITION, versions=(1,2))
        if ed['id'] != edition or ed['revision'] != revision or ed['revision_sha256'] != subject['revision_sha256']:
            raise ValueError('Edition identity mismatch')
        inherited = ed['view']['id'] if ed['schema_version']==2 else 'authored'
        if view is not None and view != inherited:raise ValueError('View differs from selected edition')
        subject.update(edition_sha256=studio.digest(path), view=inherited, role=ed.get('role'), movie={k:ed['output'][k] for k in ['path','sha256','bytes']})
        query.watch.track_references(ed.get('dependencies',[]),'evidence_index')
        query.pin(studio.inside(query.project,ed['output']['path']))
        try:
            editions.load_edition(query.project,revision,edition)
            subject['edition_validation']='current'
        except ERRORS as error:
            subject['edition_validation']='unknown'
            query.diagnostics.append({'subject':dict(subject),'code':'edition_unavailable','message':str(error)})
        return subject, ctx, ed
    pairs, origin = outputs(ctx,query)
    if view is not None and view not in {r['view_id'] for r in pairs}:
        raise ValueError('View is not declared in selected revision: '+view)
    subject.update(view=view, outputs=[r for r in pairs if view is None or r['view_id']==view], scope_origin=origin)
    return subject, ctx, None


def resolve(query, subject=None, revision=None, edition=None, view=None):
    if revision and subject:raise ValueError('--subject and --revision are mutually exclusive')
    if edition and not revision:raise ValueError('--edition requires --revision')
    if subject not in [None,'working','review','release']:raise ValueError('Unknown workflow subject')
    if revision:
        value,ctx,ed = captured(query,revision,edition,view)
        return [(value,ctx,ed)], {'revision':revision,'edition':edition,'view':view}
    mode = subject or 'working'
    if mode == 'working':
        ctx = query.context()
        pairs, origin = outputs(ctx,query)
        if view is not None and view not in {r['view_id'] for r in pairs}:
            raise ValueError('View is not declared in working scope: '+view)
        value = {'mode':'working','view':view,'outputs':[r for r in pairs if view is None or r['view_id']==view], 'scope_origin':origin}
        return [(value,ctx,None)], {'subject':'working','view':view}
    query.files(query.project/'presentations'/mode,'*.json')
    selected = deliveries.current(query.project,mode)
    if selected is None:raise ValueError('No selected '+mode+' delivery; no working fallback')
    path = deliveries.record_path(query.project,selected['delivery']); query.pin(path)
    data = deliveries.load(query.project,selected['delivery'])
    if studio.digest(path) != selected['delivery_sha256']:
        raise ValueError('Selected delivery identity changed')
    result=[]
    for key, entry in deliveries.entries(data).items():
        if view is not None and entry['view'] != view:continue
        base={'mode':mode,'delivery':data['id'],'delivery_sha256':data['payload_sha256'],'entry':key,
              'revision':entry.get('revision'),'edition':entry.get('edition'),'view':entry['view'],'role':entry['role'],'movie':entry['movie']}
        query.pin(studio.inside(query.project,entry['movie']['path']))
        if entry.get('revision') and entry.get('edition'):
            try:
                value,ctx,ed = captured(query,entry['revision'],entry['edition'],entry['view'])
                if value['movie'] != entry['movie']:
                    raise ValueError('Delivery entry movie differs from edition')
                # A delivery assigns soundtrack roles; an edition need not name a role.
                base={**value,**base}
            except ERRORS as error:
                ctx=query.context(entry['revision']);ed=None
                query.diagnostics.append({'subject':base,'code':'entry_unavailable','message':str(error)})
        else:
            ctx,ed=None,None
            query.diagnostics.append({'subject':base,'code':'unbound_legacy_entry','message':'Entry has no captured revision/edition pipeline; working reviews are not substituted.'})
        result.append((base,ctx,ed))
    if not result:raise ValueError('View has no selected delivery entries: '+str(view))
    return result, {'subject':mode,'view':view,'selection_sha256':selected['payload_sha256']}


def selector_argv(selector):
    result=[]
    for key in ['subject','revision','edition','view']:
        if selector.get(key) is not None:result += ['--'+key,str(selector[key])]
    return result
