"""Fresh native input packets; no production execution or alternate evaluator."""
import copy
from pathlib import Path
import tempfile

import studio
from . import iteration_recipes, production_plan, project_references, record_contracts, revision_reviews, workflow
from .edge_quality import promote_exclusive
from .errors import CommandError
from .workflow_catalog import ROOT

FORMAT = 'ambiance-workflow-packet'
DRAFT = 'ambiance-workflow-input-draft'


def contained(project, value):
    """Reject escapes and symlinks before resolving away their identity."""
    path = Path(value).absolute()
    if '..' in path.parts or not path.is_relative_to(project):
        raise ValueError('Packet paths must stay inside the selected project: '+str(path))
    for part in [path, *path.parents]:
        if part == project: break
        if part.is_symlink(): raise ValueError('Packet paths cannot use symlinks: '+str(part))
    if not path.resolve().is_relative_to(project): raise ValueError('Packet path escaped project')
    return path


def unresolved(value, prefix=''):
    if prefix=='change.supersedes_sha256' or prefix.endswith('.scene_ref'): return []
    if value is None: return [prefix]
    if isinstance(value, dict):
        return [p for k,v in value.items() for p in unresolved(v, prefix+'.'+k if prefix else k)
                if p != 'change.supersedes_sha256']
    if isinstance(value, list):
        return [p for i,v in enumerate(value) for p in unresolved(v, f'{prefix}[{i}]')]
    return []


def fill(base, supplied):
    """Overlay authored fields, preserving unresolved native draft fields."""
    result=copy.deepcopy(base)
    for key,value in supplied.items():
        result[key]=fill(result[key],value) if isinstance(result.get(key),dict) and isinstance(value,dict) else copy.deepcopy(value)
    return result


def origins(value, origin, prefix=''):
    """An origin applies to every known leaf, including an explicitly empty list."""
    if isinstance(value, dict) and value:
        return [p for k,v in value.items() for p in origins(v, origin, prefix+'.'+k if prefix else k)]
    if isinstance(value, list) and value:
        return [p for i,v in enumerate(value) for p in origins(v, origin, f'{prefix}[{i}]')]
    if value is not None or prefix == 'change.supersedes_sha256':
        return [{'field':prefix, 'origin':origin}]
    return []


def native_paths(project, data):
    """Check native reference spellings before native validators resolve paths."""
    if isinstance(data, list):
        for row in data: native_paths(project,row)
    elif isinstance(data, dict):
        name=data.get('path',data.get('file'))
        if isinstance(name,str) and 'sha256' in data: contained(project,project/name)
        for value in data.values(): native_paths(project,value)


def assert_fresh(assessment, staging=None):
    result=assessment.query.finish()
    changed=[]
    for row in result['changed_inputs']:
        # Ignore only our private temporary directory in directory listings. File
        # fingerprints and every unrelated arrival/change still participate.
        if staging is not None and 'pattern' in row:
            key=(row['path'],row['pattern'])
            current=[str(p) for p in sorted(Path(row['path']).glob(row['pattern']))
                     if p != staging and not p.is_relative_to(staging)]
            if current == assessment.query.directories[key]: continue
        changed.append(row)
    if changed:
        raise CommandError('Packet inputs changed during preparation: '+str(changed),'stale_assessment',2)
    return {**result,'changed_inputs':changed,
            'complete':all(s['complete'] for s in result['snapshots']) and not changed}


def prepare(project, action_id, out, *, inputs=None, expected=None, **selectors):
    project=Path(project).resolve();out=contained(project,out)
    if out.exists(): raise CommandError('Packet destination already exists; choose a fresh directory.','output_exists',2)
    if not out.parent.is_dir(): raise ValueError('Packet parent must already exist inside the project')
    assessment=workflow.Assessment(project,**selectors)
    if expected and expected != assessment.assessment_hash:
        raise CommandError('Assessment inputs or selected subject changed; reinspect explicitly. Current assessment: '+assessment.assessment_hash,'stale_assessment',2)
    action=assessment.actions.get(action_id)
    if action is None: raise CommandError('Action is no longer applicable to this exact subject; reinspect.','stale_action',2)
    bundle=next((b for b in assessment.bundles if b['id']==action['subject'].get('subject_id')),None)
    subject=copy.deepcopy(action.get('feedback_subject') or (bundle['subject'] if bundle else action['subject']))
    query=assessment.query
    supplied=None;input_origin=None
    if inputs is not None:
        path=contained(project,inputs);input_origin=query.pin(path)
        if path.stat().st_size>1024*1024: raise ValueError('Native packet input exceeds 1 MiB')
        supplied=query.read(path)
        if not isinstance(supplied,dict): raise ValueError('Native inputs must be an object')
        if supplied.get('format')==DRAFT:
            record_contracts.fields(supplied,{'format','schema_version','native_format','values','missing_inputs'},'workflow input draft')
            if supplied.get('schema_version')!=1: raise ValueError('Unsupported draft version')
            supplied=supplied['values']
        if not isinstance(supplied,dict): raise ValueError('Native inputs must be an object')
        native_paths(project,supplied)
    op=action['operation'];files={};missing=[];known=[];argv=None;validation=None
    base=[str(ROOT/'ambiance'),'--project',str(project)]
    if op=='intent.author':
        if subject['mode']!='working': raise ValueError('Intent authoring requires a working subject')
        base_values=production_plan.draft(project,outputs=subject.get('outputs',[]))
        values=fill(base_values,supplied or {})
        known=origins(base_values,{'owner':'production_plan.draft','assessment_sha256':assessment.assessment_hash})
        for row in known:
            if row['field'].startswith('outputs'): row['origin']={'owner':subject['scope_origin'],'subject':subject}
            elif row['field']=='change.supersedes_sha256': row['origin']=query.pin(project/production_plan.PATH)
        if supplied is not None:
            authored=origins(supplied,input_origin)
            known=[r for r in known if r['field'] not in {a['field'] for a in authored}]+authored
        missing=unresolved(values)
        if not missing:
            query.watch.track_references(values,'evidence_index')
            production_plan.validate(project,values)
            current=query.pin(project/production_plan.PATH)['sha256']
            if values['change']['supersedes_sha256']!=current:
                raise CommandError('Plan supersedes_sha256 differs from current plan.','stale_input',2)
            conflicts=production_plan.contradictions(project,values)
            if conflicts: raise ValueError('Native plan contradictions: '+str(conflicts))
            files['production-plan.json']=values
            argv=[*base,'plan','spec','apply',str(out/'production-plan.json'),'--expect-sha256',current or 'absent']
            validation={'owner':'production_plan.validate/contradictions','state':'validated'}
        else: files['intent.draft.json']=draft(values,missing)
    elif op=='review.draft':
        if supplied is not None: raise ValueError('Review preparation accepts no observations; edit a derivative and use review record explicitly')
        ctx=revision_reviews.review_context(project,subject['revision'],subject.get('edition'),subject.get('view')) if subject.get('revision') else None
        if subject['mode']!='working' and ctx is None: raise ValueError('No exact captured review context')
        values=studio.review_template(project,action['stage'],ctx)
        files['review.draft.json']=values
        known=origins(values,{'owner':'studio.review_template','subject':subject,'assessment_sha256':assessment.assessment_hash})
        missing=['actual observations and evidence','recorder','explicit review verdict']
        validation={'owner':'studio.review_template','state':'unperformed-native-draft',
                    'subject':(bundle.get('review_context') or {}).get('subject'),
                    'scope':'exact captured gate' if ctx else 'whole working project gate; a view filter does not narrow a legacy review'}
        # A native draft is consumable only after actual review; never emit a
        # runnable record command with invented identity or observations.
    elif op=='iteration.init':
        if subject['mode']!='working': raise ValueError('Iteration initialization needs working inputs and a fresh revision; captured subjects are not substituted')
        base_values={
            'format':'ambiance-iteration-request','schema_version':1,'id':None,'revision':None,
            'views':[o['view_id'] for o in subject.get('outputs',[])] or None,
            'editions':None,'default':{'view':None,'role':None},'scope':None}
        values=fill(base_values,supplied or {})
        known=origins(base_values,{'owner':'iteration_recipes','assessment_sha256':assessment.assessment_hash})
        for row in known:
            if row['field'].startswith('views'): row['origin']={'owner':subject.get('scope_origin'),'subject':subject}
        if supplied is not None:
            authored=origins(supplied,input_origin)
            known=[r for r in known if r['field'] not in {a['field'] for a in authored}]+authored
        missing=unresolved(values)
        if not missing:
            for e in values.get('editions',[]):
                if e.get('audio'): contained(project,project/e['audio'])
            for names in values.get('documents',{}).values():
                for name in names if isinstance(names,list) else [names]: contained(project,project/name)
            built=iteration_recipes.build(project,values,out)
            for ref in built['inputs']:
                path=contained(project,project/ref['path']);query.pin(path)
            if project_references.changed(project,built['inputs']): raise ValueError('Native iteration inputs changed')
            files.update({'iteration.json':built['recipe'],'capture-selection.json':built['selection'],
                          'inputs.json':built['inputs'],'job-plan.json':built['plan']})
            if built['resolution']:files['config-resolution.json']=built['resolution']
            # Native execution still requires an explicit recorder identity.
            files['iteration-request.json']=values
            argv=[*base,'iteration','preflight',str(out/'iteration.json')]
            validation={'owner':'iteration_recipes.build/iteration_plan.validate_recipe','state':'validated',
                        'execution_missing_inputs':['iteration run --by (actual recorder identity)']}
        else:files['iteration.draft.json']=draft(values,missing)
    else:
        if supplied is not None: raise ValueError('This direct-argument operation has no native input-file adapter')
        missing=list(action.get('missing_inputs',[]))
        if action.get('state')=='ready' and action.get('argv'):
            argv=action['argv'];validation={'owner':'workflow_operations.Operations.resolve','state':'resolved-native-arguments'}
        elif not missing:missing=[action['state']]
        known=origins({'argv':argv} if argv else {},{'owner':'workflow_operations.Operations.resolve','assessment_sha256':assessment.assessment_hash})
    if argv:
        from .cli import parser
        parser().parse_args(argv[1:])
    # Authored array replacements can remove default rows. Keep provenance only
    # for leaves that are actually present in the emitted native values.
    if op in ['intent.author','iteration.init']:
        fields={r['field'] for r in origins(values,{})}
        known=[r for r in known if r['field'] in fields]
    assert_fresh(assessment)
    # Every pinned native reference is also constrained by packet path rules.
    for ctx in [query.watch,*query.inputs.values()]:
        for path in ctx.files: contained(project,path)
    if argv:
        for flag in ['--out']:
            if flag in argv and Path(argv[argv.index(flag)+1]).exists():
                raise CommandError('Native output destination is occupied; reinspect.','output_exists',2)
    packet=dict(format=FORMAT,schema_version=1,action_id=action_id,operation=op,subject=subject,
        applies_to_subjects=[b['subject'] for b in assessment.bundles if b['id'] in action.get('applies_to_subject_ids',[])],
        assessment_sha256=assessment.assessment_hash,catalog_sha256=assessment.catalog['sha256'],
        ready_to_run=argv is not None and not missing,missing_inputs=missing,origins=known,
        validation=validation,effects=action['effects'],expected_outputs=action['expected_outputs'],
        native_file_origins={name:{'owner':validation['owner'] if validation else op,'request_origin':input_origin,
                                  'assessment_sha256':assessment.assessment_hash} for name in files},
        argv=argv,cwd=str(ROOT),preparation_effects=['artifact-write'],observations_performed=False,
        limits=['Preparation executes no production action and reserves no future output.',
                'Native commands revalidate on consumption. A proof is not an observation or gate verdict.'])
    with tempfile.TemporaryDirectory(prefix='.workflow-packet-',dir=out.parent) as temporary:
        stage=Path(temporary);candidate=stage/'packet';candidate.mkdir()
        for name,value in files.items(): studio.write(candidate/name,value)
        (candidate/'README.md').write_text(readme(packet))
        snapshot=assert_fresh(assessment,stage)
        studio.write(candidate/'assessment-inputs.json',snapshot)
        packet['files']=[{'path':str(p.relative_to(candidate)),'sha256':studio.digest(p),'bytes':p.stat().st_size}
                         for p in sorted(candidate.iterdir()) if p.is_file()]
        packet['implementation']={name:studio.digest(ROOT/'ambiance_studio'/name) for name in
                                  ['workflow_packets.py','production_plan.py','iteration_recipes.py','review_commands.py']}
        studio.write(candidate/'packet.json',record_contracts.seal(packet))
        assert_fresh(assessment,stage)
        contained(project,out)
        promote_exclusive(candidate,out)
    return {'ok':True,'packet':str(out/'packet.json'),'sha256':studio.digest(out/'packet.json'),
            'ready_to_run':packet['ready_to_run'],'missing_inputs':missing,'argv':argv,
            'native_files':[str(out/name) for name in files],'observations_performed':False}


def draft(values, missing):
    return {'format':DRAFT,'schema_version':1,'native_format':values.get('format'),
            'values':values,'missing_inputs':missing}


def readme(packet):
    return ('# Native input packet\n\nOperation: '+packet['operation']+'\n\n'
            +'Ready for the listed native command: '+str(packet['ready_to_run']).lower()+'.\n\n'
            +'Open inputs: '+(', '.join(packet['missing_inputs']) or 'none for the listed command')+'.\n\n'
            +'Complete draft values and pass the draft or a native input file to workflow prepare --inputs in a fresh directory. '
            +'Review drafts require actual observations in a derivative before review record. Iteration preflight is the next validated command; '
            +'iteration run additionally requires an explicit --by identity. No capture, rendering, admission, selection change or provider call occurred.\n')
