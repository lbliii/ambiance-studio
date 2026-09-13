"""Subject-aware advisory inspection over native coverage, inventory and gate owners.

No scheduler, persisted cursor, scope census or review verdict lives here.
"""
from pathlib import Path

import studio
from . import planning, production_coverage, revision_reviews
from .errors import CommandError
from .workflow_catalog import ROOT, load as load_catalog, operation_details
from .workflow_operations import Operations
from .workflow_subjects import Query, ERRORS, resolve, selector_argv

FORMAT = 'ambiance-workflow'
VERSION = 1
KINDS = {'input','run','feedback','production','coverage','observation'}


def logical_subject(subject):
    keys = ['mode','revision','revision_sha256','edition','edition_sha256','view','role','delivery','entry']
    value = {k:subject[k] for k in keys if subject.get(k) is not None}
    if subject.get('movie'):value['movie_sha256']=subject['movie']['sha256']
    return value


def stage_gates(query, subject, ctx, gates):
    """Native gate_status is the only verdict evaluator; isolate unreadable branches."""
    if ctx is None:return {}, None
    project=query.project
    try:
        context=revision_reviews.review_context(project,ctx.revision,subject.get('edition'),subject.get('view')) if ctx.revision else None
        settings=context['settings'] if context else query.read(project/'project.json')
        review_dir=context['review_dir'] if context else project/'reviews'
        if context:
            manifest=ctx.get('revision')
            for ref in manifest['dependencies']:query.pin(studio.inside(project,ref['path']))
            query.pin(studio.inside(project,manifest['controls']['settings']))
        query.files(review_dir,'*.json')
    except ERRORS as error:
        return {g['id']:{'state':'unknown','reasons':[str(error)]} for g in gates}, None
    # Watch snapshots and receipts are native-owned inputs, including absent files.
    try:
        for gate in gates:
            path=review_dir/(gate['id']+'.json');query.pin(path)
            if path.is_file():query.watch.track_references(query.read(path),'evidence_index')
            if not context:
                for name in gate['watch']:
                    target=studio.inside(project,name)
                    if target.is_dir():query.files(target,'**/*')
                    else:query.pin(target)
        result=studio.gate_status(project,context)
        return result['gates'], context or {'subject':result['subject'],'review_dir':review_dir}
    except ERRORS as error:
        # Do not reimplement or partially pass the native gate graph after a failed
        # read. Actual criteria and independent material still remain inspectable.
        return {g['id']:{'state':'unknown','reasons':[str(error)]} for g in gates}, context


class Assessment:
    def __init__(self, project, *, subject=None, revision=None, edition=None, view=None, stage=None):
        self.query=Query(project);self.catalog=load_catalog();self.operations=Operations(self.query,self.catalog)
        self.subjects,self.selector=resolve(self.query,subject,revision,edition,view)
        self.stage=stage;self.actions={};self.bundles=[];self.coverage_calls=0
        self.diagnostics=self.query.diagnostics
        self._inspect()

    def add(self, bundle, issue, op, reason, stage, kind='production', bindings=None, dependencies=(), state=None, **extra):
        subject=bundle['subject']; logical=logical_subject(subject)
        id='wf1.'+studio.encoded_hash({'subject':logical,'issue':issue,'operation':op})
        if id in self.actions:
            old=self.actions[id];old['dependencies']=sorted(set(old['dependencies'])|set(dependencies));return id
        source_identity=studio.encoded_hash({str(p):r['sha256'] for ctx in self.query.inputs.values() for p,r in ctx.files.items()})
        try:
            result=self.operations.resolve(op,subject,bundle['ctx'],bindings or {},id[4:20]+'-'+source_identity[:16])
        except ERRORS as error:
            result={'operation':op,'state':'unavailable','effects':self.catalog['operations'][op]['effects'],
                    'inputs':[],'missing_inputs':[str(error)],'expected_outputs':self.catalog['operations'][op]['outputs'],
                    'limits':['Native input resolution failed; no replacement script is prescribed.']}
        if state:
            result['state']=state
            if state in ['blocked','needs-input','unavailable']:result.pop('argv',None);result.pop('cwd',None)
        row={**result,'id':id,'stage':stage,'kind':kind,'subject':{**logical,'subject_id':bundle['id']},
             'reason':reason,'issue_ids':[issue],'dependencies':list(dependencies),
             'gate_dependencies':list(bundle['gate_map'].get(stage,{}).get('depends',[])),
             'blocked_by':[], 'completion':'Native artifacts and actual observations retain separate authority.', **extra}
        self.actions[id]=row
        return id

    def _inspect(self):
        for subject,ctx,ed in self.subjects:
            id='subject.'+studio.encoded_hash(logical_subject(subject))
            gates=ctx.get('pipeline') if ctx else None
            gates=gates or []
            if self.stage and self.stage not in {g['id'] for g in gates}:
                # A missing pipeline is inspectable; a known pipeline with no such gate
                # is an invalid selector, including catalog-only default gate names.
                if ctx and ctx.components['pipeline']['state']=='available':raise ValueError('Unknown gate in selected pipeline: '+self.stage)
            bundle={'id':id,'subject':subject,'ctx':ctx,'edition':ed,'gates':gates,
                    'gate_map':{g['id']:g for g in gates},'coverage':{},'inventory':None,'materials':{}}
            self.bundles.append(bundle)
            if ctx:
                for key in ['plan','inventory','scene','catalog']:
                    ctx.get(key)
                bundle['gate_states'],bundle['review_context']=stage_gates(self.query,subject,ctx,gates)
                for gate_id,state in bundle['gate_states'].items():
                    if state['state']=='unknown':self.diagnostics.append({'subject_id':id,'gate':gate_id,'code':'review_unavailable','reasons':state['reasons']})
                self._materials(bundle)
                self._inventory(bundle)
                wanted=[g['id'] for g in gates if g['id'] in ['layout','assets','animation','export'] and (not self.stage or self.stage==g['id'])]
                if ctx.get('plan') is not None:
                    for stage in wanted:
                        bundle['coverage'][stage]=production_coverage.assess(self.query.project,stage,subject.get('view'),ctx.revision,details=True,assessment=ctx)
                        self.coverage_calls+=1
                self._work(bundle)
            else:
                bundle.update(gate_states={},review_context=None)
            self._reviews(bundle)
            if subject.get('delivery'):
                self.add(bundle,'delivery.handoff','delivery.handoff','Prepare a handoff for the exact selected entries while observations remain open.','library')
            elif subject.get('revision'):
                self.add(bundle,'revision.handoff','revision.handoff','Package captured inputs and their open checks.','library')
        self._operational_work()
        self.selected_pointers=self._selected_pointers()
        snapshot=self.query.finish()
        for bundle in self.bundles:
            ctx=bundle['ctx']
            if ctx:
                for key,row in ctx.components.items():
                    if row['state']=='unknown':self.diagnostics.append({'subject_id':bundle['id'],'component':key,**row})
        if snapshot['changed_inputs']:
            self.diagnostics.append({'code':'inputs_changed','changes':snapshot['changed_inputs']})
            for row in self.actions.values():
                row['state']='unavailable';row.pop('argv',None);row.pop('cwd',None)
                row['blocked_by'].append({'code':'inputs_changed','reason':'Reinspect one coherent input set.'})
            for bundle in self.bundles:
                for row in bundle['gate_states'].values():row.update(state='unknown',reasons=['Inputs changed during assessment'])
                for row in bundle['coverage'].values():row['ready']=None
        code_paths=['workflow.py','workflow_catalog.py','workflow_subjects.py','workflow_operations.py','production_coverage.py','coverage_context.py','coverage_evidence.py','coverage_records.py','planning.py','revision_reviews.py','workflow_commands.py','cli.py','editions.py','revision_capture.py','project_references.py','record_contracts.py','scene_runtime.py']
        engine={name:studio.digest(ROOT/'ambiance_studio'/name) for name in code_paths};engine['studio.py']=studio.digest(ROOT/'studio.py')
        engine['editor/engine.mjs']=studio.digest(ROOT/'editor/engine.mjs')
        self.snapshot=snapshot
        self.ordered=self._order()
        self.assessment_hash=studio.encoded_hash({'version':VERSION,'catalog':self.catalog['sha256'],'selector':self.selector,'stage':self.stage,
                'subjects':[s for s,_,_ in self.subjects],'snapshot':snapshot,'engine':engine,'actions':self.actions,'selected_pointers':self.selected_pointers,'diagnostics':self.diagnostics})

    def _materials(self,bundle):
        ctx=bundle['ctx'];manifest=ctx.get('revision') if ctx.revision else None
        paths={key:ctx.path(key) for key in ['plan','inventory','scene','catalog','pipeline'] if ctx.get(key) is not None}
        if manifest:
            for ref in manifest['dependencies']:
                if ref['role'] in ['reference','brief','sound_plan','audio_session','master','audio_source']:
                    paths.setdefault(ref['role'],studio.inside(self.query.project,ref['path']))
        else:
            try:settings=self.query.read(self.query.project/'project.json')
            except ERRORS as error:
                settings={};self.diagnostics.append({'subject_id':bundle['id'],'component':'settings','message':str(error)})
            if settings.get('reference'):paths['reference']=studio.inside(self.query.project,settings['reference']['path'])
            for key,name in [('brief','plans/brief.md'),('sound_plan','plans/sound-brief.md'),('audio_session','audio/session.json'),('handoff','handoff.md')]:
                paths[key]=studio.inside(self.query.project,name)
        bundle['materials']={key:self.query.pin(path) for key,path in paths.items()}
        bundle['subject']['controls']={key:ref for key,ref in bundle['materials'].items() if key in ['plan','scene','catalog','pipeline','inventory']}

    def _inventory(self,bundle):
        ctx=bundle['ctx']
        if any(ctx.get(key) is None for key in ['inventory','scene','catalog']):return
        try:
            inventory=ctx.get('inventory');ctx.track_references(inventory,'inventory')
            bundle['inventory']=planning.evaluate(self.query.project,inventory,ctx.get('catalog'),ctx.get('scene'),ctx.path('inventory'),{})
        except ERRORS as error:
            self.diagnostics.append({'subject_id':bundle['id'],'component':'inventory','message':str(error)})

    def _work(self,bundle):
        ctx=bundle['ctx'];subject=bundle['subject'];plan=ctx.get('plan');working=subject['mode']=='working'
        if working and plan is None:
            self.add(bundle,'intent.reference','reference.inspect','Inspect the preserved reference; record observed features and distinguish proposed additions.','intent','input',{'reference':bundle['materials'].get('reference',{}).get('path')})
            self.add(bundle,'intent.author','intent.author','Author missing native intent fields; preserve any existing brief, inventory and explicit scope.','intent','input')
        if working:
            for key,row in ctx.components.items():
                if row['state']=='unknown' and key not in ['plan','views','asset_dependencies','plan_dependencies']:
                    self.add(bundle,'input.'+key,'inventory.inspect','Restore readable '+key+' before depending on it.','layout','input',state='unavailable',diagnostic=row)
        if plan:
            self.add(bundle,'view.inspect','view.inspect','Inspect saved framing for this exact working or captured subject.','layout',bindings={'view':subject.get('view')})
        inventory=bundle['inventory']
        item_actions={}
        if working and inventory:
            if not inventory['ok']:
                self.add(bundle,'inventory.invalid','inventory.inspect','Inspect native inventory errors before changing fulfillment.','layout','input',native_errors=inventory['errors'])
            raw={r['id']:r for r in ctx.get('inventory')['items'] if isinstance(r,dict) and isinstance(r.get('id'),str)}
            for item in inventory['items']:
                if item['complete_for_scope']:continue
                aid=self.add(bundle,'inventory.'+item['id'],'inventory.fulfill',item['next_action'],'assets',item_id=item['id'])
                item_actions[item['id']]=aid
                for part in raw.get(item['id'],{}).get('required_parts',[]):
                    if not isinstance(part,dict) or part.get('stage') in ['compiled','placed']:continue
                    refs=part.get('files',[])
                    for ref in refs:
                        try:
                            p=studio.inside(self.query.project,ref['file']);self.query.pin(p)
                            if studio.digest(p)!=ref['sha256']:raise ValueError('Declared part source changed: '+ref['file'])
                            if p.suffix=='.json':
                                recipe=self.query.read(p)
                                if recipe.get('format') in ['ambiance-compound-preparation','ambiance-asset-preparation']:
                                    self.add(bundle,'part.'+item['id']+'.'+str(part.get('id')),'prepare.build','Build the declared source separation with the native preparation operation.','assets',bindings={'recipe':str(p)},dependencies=[])
                                elif recipe.get('input'):
                                    self.add(bundle,'part.'+item['id']+'.'+str(part.get('id')),'asset.build','Compile the declared already-isolated art through its native recipe.','assets',bindings={'compiler_recipe':str(p)},dependencies=[])
                            elif p.suffix.lower() in ['.png','.jpg','.jpeg','.webp']:
                                self.add(bundle,'source.'+ref['file'],'art.preflight','Inspect decoded alpha before choosing direct compilation or explicit source separation.','assets',bindings={'source':str(p)})
                                if part.get('stage')=='prepared':
                                    self.add(bundle,'part.'+item['id']+'.'+str(part.get('id')),'asset.build','This part is declared prepared: supply its native compiler recipe directly.','assets',dependencies=[])
                        except ERRORS as error:
                            self.add(bundle,'part.input.'+item['id']+'.'+str(part.get('id')),'inventory.inspect',str(error),'assets','input',state='unavailable')
            for item in inventory['items']:
                if item['id'] not in item_actions:continue
                row=self.actions[item_actions[item['id']]]
                row['dependencies']=[item_actions[d] for d in item['blocked_by'] if d in item_actions]
                part_actions=[r['id'] for r in self.actions.values() if r['subject']['subject_id']==bundle['id'] and any(i.startswith('part.'+item['id']+'.') for i in r['issue_ids'])]
                row['dependencies']+=part_actions
                for pid in part_actions:
                    self.actions[pid]['dependencies']=[item_actions[d] for d in item['blocked_by'] if d in item_actions]
                row['blocked_by']=[{'item_id':d,'reason':'Native inventory prerequisite incomplete'} for d in item['blocked_by']]
                if row['blocked_by']:row['state']='blocked';row.pop('argv',None);row.pop('cwd',None)
        # A pending gate does not prevent independent proof work on usable existing art.
        if ctx.get('catalog'):
            for asset in ctx.get('catalog')['assets']:
                if bundle['gate_states'].get('assets',{}).get('state')!='passed':
                    self.add(bundle,'asset.proof.'+asset['id'],'asset.proof','Inspect cel registration for the exact available catalog asset.','assets',bindings={'asset_id':asset['id']})
        for stage,coverage in bundle['coverage'].items():
            for issue in coverage['blocked']:
                exp=next((e for e in plan['expectations'] if e['id']==issue.get('expectation_id')),None)
                if exp:
                    check=exp['requirement']['check'];view=issue.get('view_id');dependencies=[]
                    if check in ['raster','activity']:
                        op='picture.proof' if check=='raster' else 'scene.activity'
                        dependencies.append(self.add(bundle,op+'.'+str(view),op,'Produce the exact '+str(view)+' evidence needed by these expectations.',exp['stage'],bindings={'view':view}))
                    op='review.draft' if exp['requirement']['type']=='observed' else 'evidence.register'
                    if check=='art':
                        op='inventory.fulfill'
                        elements=[e for e in plan['elements'] if e['id'] in exp['element_ids']]
                        required={ref['item_id'] for e in elements for ref in e['realization']['inventory_parts']+[a['inventory_part'] for a in e['required_art']]}
                        dependencies.extend(item_actions[id] for id in sorted(required) if id in item_actions)
                    elif check in ['independent-control','relation']:op='scene.apply'
                    elif check=='view':op='view.apply'
                    elif check=='movie':
                        movie=subject.get('movie');ed=bundle['edition']
                        if movie and ed:
                            dependencies.append(self.add(bundle,'movie.verify','media.verify','Decode this exact selected movie against its edition expectations.','export',bindings={'movie':str(studio.inside(self.query.project,movie['path'])),'output_expectations':ed.get('output_expectations')}))
                        else:op='iteration.init'
                    self.add(bundle,issue['id'],op,issue['action'],exp['stage'],'coverage',
                             bindings={'gate':exp['stage'],'review_unavailable':not bundle['review_context'],'expectation_id':exp['id'],'view':view},
                             dependencies=dependencies,state='needs-observation' if exp['requirement']['type']=='observed' else 'needs-input',
                             expectation={'id':exp['id'],'view':view,'requirement':exp['requirement']},native_issue=issue,required_for_stage=self.stage)
                else:
                    self.add(bundle,issue['id'],'intent.author',issue['action'],stage,'coverage',state='needs-input',native_issue=issue)
        session=bundle['materials'].get('audio_session',{})
        if session.get('sha256'):
            self.add(bundle,'audio.session','audio.inspect','Inspect the exact selected session and pinned PCM inputs.','mix',bindings={'session':session['path']})
        elif working:
            self.add(bundle,'audio.intent','audio.source-inspect','Choose a source and explicit backend from the sound brief; audition remains an actual observation.','sound-design')
        if working and plan:
            self.add(bundle,'scene.clock','scene.timing','Inspect the clock that actually drives the scene before timing picture or sound.','animation')

    def _reviews(self,bundle):
        for gate in bundle['gates']:
            status=bundle['gate_states'].get(gate['id'],{'state':'unknown'})
            if status['state']=='passed':continue
            self.add(bundle,'gate.'+gate['id'],'review.draft','Prepare an unperformed review of the actual '+gate['id']+' criteria. Gate dependencies govern passage, not independent production.',gate['id'],'observation',
                     bindings={'gate':gate['id'],'review_unavailable':not bundle['review_context']},
                     criteria=[{'gate':gate['id'],'id':c['id'],'kind':c.get('kind','unknown')} for c in gate['criteria']],
                     observation_state='needs-observation',gate_state=status['state'])

    def _operational_work(self):
        from . import feedback, run_control
        selected={}
        for b in self.bundles:
            if b['subject'].get('delivery'):selected.setdefault(b['subject']['delivery'],[]).append(b)
        working=next((b for b in self.bundles if b['subject']['mode']=='working'),None)
        if working:
            for path in self.query.files(self.query.project/'runs','*/run.json'):
                try:
                    row=self.query.read(path);effective=run_control.effective(row,self.query.project)
                    if effective['effective_state'] in ['interrupted','unknown','unreadable','failed']:
                        self.add(working,'run.'+path.parent.name,'iteration.inspect',effective.get('state_reason') or effective['effective_state'],'export','run',{'run_id':path.parent.name})
                except ERRORS as error:self.diagnostics.append({'component':'run','path':str(path),'message':str(error)})
        for path in self.query.files(self.query.project/'feedback/movies','*.json'):
            try:
                self.query.files(self.query.project/'feedback/events'/path.stem,'*.json')
                row=feedback.inspect(self.query.project,path.stem)
                # Historical feedback never becomes working-revision instructions.
                matches=selected.get(row['delivery'],[])
                if row['subject'].get('kind')=='entry':
                    matches=[b for b in matches if b['subject'].get('entry')==row['subject'].get('entry')]
                if matches and row['state']=='open':
                    aid=self.add(matches[0],'feedback.'+row['id'],'feedback.inspect',row['note'],'release','feedback',bindings={'feedback_id':row['id']},feedback_id=row['id'],feedback_subject=row['subject'])
                    action=self.actions.pop(aid)
                    # Feedback keeps its own immutable entry or delivery-wide subject;
                    # a default delivery entry is never substituted for it.
                    action['subject']={'mode':matches[0]['subject']['mode'],'feedback':row['id'],**row['subject']}
                    action['applies_to_subject_ids']=[b['id'] for b in matches]
                    action['id']='wf1.'+studio.encoded_hash({'feedback_subject':row['subject'],'feedback':row['id'],'operation':'feedback.inspect'})
                    action['argv']=[str(ROOT/'ambiance'),'--project',str(self.query.project),'feedback','inspect',row['id']]
                    action['cwd']=str(ROOT);self.actions[action['id']]=action
            except ERRORS as error:self.diagnostics.append({'component':'feedback','path':str(path),'message':str(error)})

    def _selected_pointers(self):
        from . import deliveries
        result={}
        if not any(b['subject']['mode']=='working' for b in self.bundles):return result
        for channel in ['review','release']:
            try:
                self.query.files(self.query.project/'presentations'/channel,'*.json')
                selection=deliveries.current(self.query.project,channel)
                if selection:
                    path=deliveries.record_path(self.query.project,selection['delivery']);self.query.pin(path)
                    data=deliveries.load(self.query.project,selection['delivery'])
                    result[channel]={'delivery':data['id'],'selection_sha256':selection['payload_sha256'],
                                     'entry_count':len(deliveries.entries(data)),
                                     'inspect_argv':[str(ROOT/'ambiance'),'--project',str(self.query.project),'workflow','inspect','--subject',channel],
                                     'meaning':'Selected captured movies; no verdict is transferred to working production.'}
                else:result[channel]=None
            except ERRORS as error:result[channel]={'state':'unknown','message':str(error)}
        return result

    def _order(self):
        priority={'input':0,'run':1,'feedback':2,'production':3,'coverage':4,'observation':5}
        order={id:i for i,id in enumerate(self.catalog['stages'])};result=[];seen=set();active=set()
        def visit(id):
            if id in seen:return
            if id in active:
                self.actions[id]['state']='blocked';self.actions[id]['blocked_by'].append({'code':'dependency_cycle'});return
            active.add(id)
            for dep in self.actions[id]['dependencies']:
                if dep in self.actions:visit(dep)
            active.remove(id);seen.add(id);result.append(self.actions[id])
        for row in sorted(self.actions.values(),key=lambda r:(priority[r['kind']],order.get(r['stage'],99),{'reference.inspect':0,'intent.author':1}.get(r['operation'],2),r['id'])):visit(row['id'])
        return result

    def project(self, *, limit=3, offset=0, kind=None, details=False, subject_limit=6, subject_offset=0):
        if type(limit) is not int or not 1<=limit<=1000 or type(offset) is not int or offset<0:raise ValueError('Workflow limit must be 1–1000 and offset nonnegative')
        if not 1<=subject_limit<=1000 or subject_offset<0:raise ValueError('Invalid subject pagination')
        if kind is not None and kind not in KINDS:raise ValueError('Unknown next-work kind')
        base=[str(ROOT/'ambiance'),'--project',str(self.query.project),'workflow']
        selection=selector_argv(self.selector)
        visible=self.bundles[subject_offset:subject_offset+subject_limit];ids={b['id'] for b in visible}
        rows=[r for r in self.ordered if (r['subject'].get('subject_id') in ids or ids.intersection(r.get('applies_to_subject_ids',[]))) and (kind is None or r['kind']==kind)]
        if self.stage:
            wanted={r['id'] for r in rows if r['stage']==self.stage or r.get('required_for_stage')==self.stage}
            def add_deps(id):
                for dep in self.actions[id]['dependencies']:
                    if dep not in wanted:wanted.add(dep);add_deps(dep)
            for id in list(wanted):add_deps(id)
            rows=[r for r in rows if r['id'] in wanted]
        def action(row, full=False):
            value=dict(row)
            value['assessment_sha256']=self.assessment_hash
            value['explain_argv']=[*base,'explain',row['id'],*selection,*(['--stage',self.stage] if self.stage else []),'--expect-assessment',self.assessment_hash]
            if not full:
                keep=['id','stage','kind','state','subject','reason','dependencies','gate_dependencies','blocked_by','operation','argv','cwd','missing_inputs','observation_state','required_for_stage','applies_to_subject_ids']
                value={k:v for k,v in value.items() if k in keep}
                value['subject']={k:v for k,v in value['subject'].items() if k not in ['revision_sha256','edition_sha256','movie_sha256','delivery']}
                # The common assessment/explain template lives once in the envelope.
                value['reason']=str(value['reason'])[:180]
                if len(value.get('missing_inputs',[]))>5:
                    value['missing_input_count']=len(value['missing_inputs']);value['missing_inputs']=value['missing_inputs'][:5]
            return value
        stage_rows=[]
        for id in dict.fromkeys(g['id'] for b in visible for g in b['gates']):
            if self.stage and id!=self.stage:continue
            guide=self.catalog['stages'].get(id)
            subjects=[]
            for b in visible:
                gate=b['gate_map'].get(id)
                if gate is None:continue
                bindings=guide['criterion_bindings'] if guide else {}
                compatibility={c['id']:('compatible' if bindings.get(c['id'])==studio.encoded_hash(c) else 'custom-or-altered') for c in gate['criteria']}
                cov=b['coverage'].get(id)
                coverage={'state':'unsupported'} if id not in ['layout','assets','animation','export'] else {'state':'unavailable','ready':None} if cov is None else {'state':'assessed','ready':cov['ready'],'counts':cov['counts']}
                state=b['gate_states'].get(id,{'state':'unknown','reasons':['Captured pipeline review is unavailable']})
                entry={'subject_id':b['id'],'gate':state,'criterion_count':len(gate['criteria']),
                       'custom_criteria':[k for k,v in compatibility.items() if v!='compatible'], 'coverage':coverage,
                       'work':{'actions':sum(r['stage']==id and r['subject'].get('subject_id')==b['id'] for r in self.ordered)}}
                if not details:entry['gate']={'state':state['state']}
                entry['gate_scope']=(b['review_context'] or {}).get('subject',{}).get('mode','unknown')
                if self.stage or details:
                    entry.update(criteria=gate['criteria'],criterion_bindings=compatibility,gate_dependencies=gate['depends'],watch=gate['watch'],
                                 review_subject=(b['review_context'] or {}).get('subject'),materials=b['materials'])
                    if cov:entry['coverage']=cov if details else {**coverage,'blocked':cov['blocked'][:5],'blocked_omitted':max(0,len(cov['blocked'])-5)}
                if not self.stage and not details:
                    entry={'subject_id':b['id'],'gate_state':state['state'],'gate_scope':entry['gate_scope'],
                           'criteria':len(gate['criteria']),'custom_criteria':entry['custom_criteria'],
                           'coverage_state':coverage['state'],**({'coverage_ready':coverage['ready']} if 'ready' in coverage else {})}
                subjects.append(entry)
            row={'id':id,'purpose':guide['purpose'] if guide else 'Custom pipeline gate; use its actual criteria and native review draft.','subjects':subjects}
            if self.stage or details:
                row['guidance']={k:guide[k] for k in ['inputs','outputs','references','operations']} if guide else {'operations':['review.draft'],'limits':['No catalog-specific completion binding.']}
                if details:row['operations']=[operation_details(self.catalog['operations'][op]) for op in row['guidance']['operations']]
            stage_rows.append(row)
        subjects=[{'id':b['id'],**b['subject']} for b in visible]
        if not details:
            for subject in subjects:
                controls=subject.pop('controls',{})
                subject['control_hashes']={k:v['sha256'] for k,v in controls.items()}
        retrieval=[*base,'inspect',*selection,'--details']+(['--stage',self.stage] if self.stage else [])
        result={'ok':True,'format':FORMAT,'schema_version':VERSION,'project':str(self.query.project),
                'catalog':{k:self.catalog[k] for k in ['id','schema_version','sha256','path']},
                'assessment':{'sha256':self.assessment_hash,'complete':self.snapshot['complete'] and not self.diagnostics,
                              'changed_inputs':self.snapshot['changed_inputs'],'coverage_calls':self.coverage_calls},
                'selection':self.selector,'selected_movies':self.selected_pointers,'full_scope':self.selector.get('view') is None,
                'subjects':subjects,'subject_count':len(self.bundles),'subjects_omitted':max(0,len(self.bundles)-subject_offset-len(visible)),
                'next_subject_offset':subject_offset+subject_limit if subject_offset+subject_limit<len(self.bundles) else None,
                'stages':stage_rows,'items':[action(r,details) for r in rows[offset:offset+limit]],'total':len(rows),
                'omitted':max(0,len(rows)-offset-limit),'next_offset':offset+limit if offset+limit<len(rows) else None,
                'diagnostics':self.diagnostics if details else self.diagnostics[:4],'diagnostic_count':len(self.diagnostics),
                'details_argv':retrieval,'explain':{'route':'workflow explain ACTION_ID','selectors':selection,'expect_assessment':self.assessment_hash},
                'limits':['Advisory operations only. Actual pipeline and native coverage retain their separate verdicts.',
                          'No generation, publication, selection change, observation or project mutation was performed.']}
        if result['next_offset'] is not None:
            result['next_argv']=[*base,'inspect',*selection,'--offset',str(result['next_offset']),'--limit',str(limit),*(['--stage',self.stage] if self.stage else []),*(['--kind',kind] if kind else [])]
        if result['next_subject_offset'] is not None:
            result['next_subjects_argv']=[*base,'inspect',*selection,'--subject-offset',str(result['next_subject_offset']),'--subject-limit',str(subject_limit),*(['--stage',self.stage] if self.stage else [])]
        if details:result['inputs']=self.snapshot
        return result


def inspect(project, **options):
    selectors={k:options.pop(k,None) for k in ['subject','revision','edition','view','stage']}
    return Assessment(project,**selectors).project(**options)


def explain(project, id, expected=None, **selectors):
    assessment=Assessment(project,**selectors)
    if expected and expected!=assessment.assessment_hash:
        raise CommandError('Assessment inputs or selected subject changed; reinspect explicitly. Current assessment: '+assessment.assessment_hash,'stale_assessment',2)
    row=assessment.actions.get(id)
    if row is None:raise CommandError('Action is no longer applicable to this exact subject; reinspect. No substitute action was selected.','stale_action',2)
    return {'ok':True,'format':'ambiance-workflow-action','schema_version':VERSION,'assessment_sha256':assessment.assessment_hash,
            'catalog_sha256':assessment.catalog['sha256'],'action':row,'subject':row.get('feedback_subject') or next(b['subject'] for b in assessment.bundles if b['id']==row['subject']['subject_id']),
            'operation':operation_details(assessment.catalog['operations'][row['operation']]),'diagnostics':assessment.diagnostics}
