#!/usr/bin/env python3
"""Portable project scaffolding and evidence-based review records. Python 3.9+."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import uuid

from ambiance_studio.file_identity import digest

ROOT = Path(__file__).resolve().parent

def read(path):
    return json.loads(Path(path).read_text())


def encoded_hash(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def write(path,value):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        temp.write_text(json.dumps(value,indent=2)+'\n')
        temp.replace(path)
    finally:
        if temp.exists(): temp.unlink()

def inside(project,relative):
    if not isinstance(relative,str) or not relative: raise ValueError('Expected a nonempty project-relative path')
    p=Path(relative)
    if p.is_absolute() or '..' in p.parts: raise ValueError(f'Path must stay inside the project: {relative}')
    target=(project/p).resolve()
    if not target.is_relative_to(project.resolve()): raise ValueError(f'Path escapes the project: {relative}')
    return target

def pipeline(project,context=None):
    data=context['pipeline'] if context else read(project/'pipeline.json')
    if data.get('version')!=1: raise ValueError('Unsupported pipeline version')
    gates=data['gates']; seen=set()
    for g in gates:
        if g['id'] in seen or any(d not in seen for d in g['depends']):
            raise ValueError('Pipeline gates must have unique IDs in dependency order')
        seen.add(g['id'])
        if not g['criteria'] or len({c['id'] for c in g['criteria']})!=len(g['criteria']):
            raise ValueError('Gate criteria must be nonempty and unique')
    return gates

def watch_state(project,gate):
    snapshot={}
    for relative in gate['watch']:
        p=inside(project,relative)
        if p.is_dir():
            for f in sorted(p.rglob('*')):
                if f.is_file():
                    rel=str(f.relative_to(project))
                    checked=inside(project,rel)
                    snapshot[rel]=digest(checked)
        elif p.is_file(): snapshot[relative]=digest(p)
        else: snapshot[relative]=None
    from ambiance_studio.review_watches import selected_picture
    selected,issues=selected_picture(project,gate)
    snapshot.update(selected)
    return snapshot,issues

def watch_snapshot(project,gate):
    return watch_state(project,gate)[0]

def scoped_watch(project,gate,context=None):
    return (context['snapshot'](gate['id']),context['issues'](gate['id'])) if context else watch_state(project,gate)

def scoped_snapshot(project,gate,context=None):
    return context['snapshot'](gate['id']) if context else watch_snapshot(project,gate)

def gate_status(project,context=None):
    project=Path(project).resolve()
    settings=context['settings'] if context else read(project/'project.json')
    if settings.get('version')!=1: raise ValueError('Unsupported project version')
    gates=pipeline(project,context); results={}
    review_dir=context['review_dir'] if context else project/'reviews'
    for g in gates:
        id=g['id']; path=review_dir/f'{id}.json'
        deps={d:results[d] for d in g['depends']}
        unavailable=[d for d,v in deps.items() if v['state']!='passed']
        record=read(path) if path.is_file() else None
        state='blocked' if unavailable else 'pending'
        reasons=[f'Dependency {d}: {results[d]["state"]}' for d in unavailable]
        current_snapshot,scope_issues=scoped_watch(project,g,context)
        if scope_issues:state='blocked';reasons=scope_issues+reasons
        if record:
            stale=[]
            payload={k:v for k,v in record.items() if k!='payload_sha256'}
            if record.get('payload_sha256')!=encoded_hash(payload): stale.append('Receipt content changed or lacks an integrity digest')
            if record.get('project_digest')!=encoded_hash(settings): stale.append('Project settings changed')
            if record.get('gate_digest')!=encoded_hash(g): stale.append('Gate criteria changed')
            if record.get('watch_snapshot')!=current_snapshot: stale.append('Watched inputs or outputs changed')
            if context and (record.get('version')!=2 or record.get('subject')!=context['subject']):stale.append('Review subject changed')
            stale.extend(scope_issues)
            for d in g['depends']:
                if record.get('dependencies',{}).get(d)!=results[d].get('receipt_digest'): stale.append(f'Dependency receipt changed: {d}')
            for check in record.get('checks',[]):
                for ev in check.get('evidence',[]):
                    ep=inside(project,ev['path'])
                    if not ep.is_file() or digest(ep)!=ev['sha256']: stale.append(f'Evidence changed: {ev["path"]}')
            for check in record.get('expectations', []):
                for ev in check.get('evidence', []):
                    ep=inside(project,ev['path'])
                    if not ep.is_file() or digest(ep)!=ev['sha256']: stale.append(f'Expectation evidence changed: {ev["path"]}')
            if stale: state='stale'; reasons=stale+reasons
            elif unavailable: state='blocked'
            else: state='passed' if record['verdict']=='pass' else 'revise'
        results[id]=dict(state=state,name=g['name'],reasons=reasons,
                         receipt_digest=digest(path) if path.is_file() else None)
    return dict(project=settings['id'],subject=context['subject'] if context else {'mode':'legacy-path-watches'},gates=results,
                release_ready=results.get('release',{}).get('state')=='passed',
                archived=all(v['state']=='passed' for v in results.values()),
                meaning='Passed means recorded checks and evidence are current. It is not independent certification or permission to publish.')

def new_project(destination,reference=None,title=None):
    destination=Path(destination).resolve()
    if destination.exists(): raise ValueError('Choose a new project directory; existing folders are never overwritten')
    if reference:
        reference=Path(reference).resolve()
        if not reference.is_file() or reference.stat().st_size==0: raise ValueError('Reference image is missing or empty')
        if reference.suffix.lower() not in ['.png','.jpg','.jpeg','.webp']: raise ValueError('Use a PNG, JPEG, or WebP reference')
    id=destination.name
    if not re.fullmatch('[a-z0-9][a-z0-9-]*',id): raise ValueError('Project folder name must use lowercase letters, numbers, and hyphens')
    destination.mkdir(parents=True)
    folders=['inputs','plans','assets/raw','assets/production','scene','audio/sources','audio/masters','audio/stems',
             'reports/assets','reports/animation','reports/sound-design','reports/mix','reports/export',
             'deliverables/picture','deliverables/final','feedback','reviews/history','review-drafts','library']
    for f in folders: (destination/f).mkdir(parents=True,exist_ok=True)
    ref=None
    if reference:
        target=destination/'inputs'/('reference'+reference.suffix.lower());shutil.copy2(reference,target)
        ref=dict(path=str(target.relative_to(destination)),sha256=digest(target),original_filename=reference.name)
    write(destination/'project.json',dict(version=1,id=id,title=title or id.replace('-',' ').title(),reference=ref,
          output=dict(width=1080,height=1920,fps=30,picture_seconds=16,master_seconds=48),
          generation_budget=dict(currency=None,limit=None,authorization_note=None),
          review_mode='collaborative',studio_version='0.3.0'))
    shutil.copy2(ROOT/'templates/pipeline.json',destination/'pipeline.json')
    shutil.copy2(ROOT/'docs/BRIEF-TEMPLATE.md',destination/'plans/brief.md')
    write(destination/'plans/layer-plan.json',dict(version=1,objects=[],clean_plates=[],rigs=[],camera_limits={},open_questions=[]))
    write(destination/'plans/generation-ledger.json',dict(version=1,requests=[]))
    (destination/'plans/layout-notes.md').write_text('# Layout observations\n\nRecord visible facts, proposed additions, occlusion problems, and depth decisions.\n')
    (destination/'plans/sound-brief.md').write_text('# Sound identity\n\nDefine the emotional idea, near/middle/distant sounds, quiet spaces, and listening targets.\n')
    (destination/'handoff.md').write_text('# Project handoff\n\nCurrent stage: reference and brief. No quality gates have passed yet.\n\nRecord next actions, final paths, blockers, and reusable pieces here.\n')
    return dict(project=str(destination),next='Inspect the reference; complete the brief and tool/budget record. No gate is pre-approved.')

def review_template(project,gate_id,context=None):
    gate=next((g for g in pipeline(project,context) if g['id']==gate_id),None)
    if not gate: raise ValueError(f'Unknown gate: {gate_id}')
    result=dict(version=2 if context else 1,gate=gate_id,verdict='revise',recorder='',
                checks=[dict(id=c['id'],result='not-run',observed_by=dict(kind='agent',name=''),
                             note='',evidence=[]) for c in gate['criteria']])
    if context:result['subject']=context['subject']
    if context and context.get('plan_context'):
        from ambiance_studio.production_coverage import observation_drafts
        result['expectations']=observation_drafts(context['plan_context'],gate_id,context['subject'].get('view','authored'))
    return result

def record_review(project,source,context=None):
    project=Path(project).resolve(); review=read(source)
    if review.get('version')!=(2 if context else 1):raise ValueError('Unsupported review version or missing revision context')
    if context and review.get('subject')!=context['subject']:raise ValueError('Review subject differs from the selected revision/edition')
    gate=next((g for g in pipeline(project,context) if g['id']==review.get('gate')),None)
    if not gate: raise ValueError('Unknown gate in review')
    status=gate_status(project,context)['gates']
    initial_snapshot,initial_issues=scoped_watch(project,gate,context)
    if review.get('verdict') not in ['pass','revise']: raise ValueError('Verdict must be pass or revise')
    if not isinstance(review.get('recorder'),str) or not review['recorder'].strip(): raise ValueError('Name the person or agent recording this review')
    checks=review.get('checks',[])
    if not isinstance(checks,list) or len(checks)!=len(gate['criteria']) or {c.get('id') for c in checks}!={c['id'] for c in gate['criteria']}:
        raise ValueError('Supply exactly one result for every gate criterion')
    specs={c['id']:c for c in gate['criteria']}
    normalized=[]
    for c in checks:
        spec=specs[c['id']]
        if c.get('result') not in ['pass','fail','not-run']: raise ValueError('Check result must be pass, fail, or not-run')
        observer=c.get('observed_by',{})
        if observer.get('kind') not in ['agent','human','tool']: raise ValueError('Observer kind must be agent, human, or tool')
        if review['verdict']=='pass' and c['result']!='pass': raise ValueError(f'Unpassed criterion: {c["id"]}')
        if c['result']=='pass':
            if not observer.get('name','').strip() or not c.get('note','').strip(): raise ValueError('Passing checks need a named observer and specific observations')
            if spec['kind']=='human' and observer['kind']!='human': raise ValueError(f'Human observation required for {c["id"]}; do not substitute a technical check')
            if not c.get('evidence'): raise ValueError('Passing checks need actual evidence files')
        evidence=[]
        if not isinstance(c.get('evidence',[]),list): raise ValueError('Evidence must be a list of project-relative paths')
        for rel in c.get('evidence',[]):
            p=inside(project,rel)
            if not p.is_file() or p.stat().st_size==0: raise ValueError(f'Missing or empty evidence: {rel}')
            evidence.append(dict(path=rel,sha256=digest(p),bytes=p.stat().st_size))
        if c['result']=='pass' and spec['kind']=='human':
            if not any(e['path'].startswith('feedback/') for e in evidence): raise ValueError('Human review needs a feedback record quoting or identifying the actual observation')
            if context:
                if not any(e['path'] in context['final_files'] for e in evidence):raise ValueError('Human release review must identify the exact selected edition file')
            elif not any(e['path'].startswith('deliverables/final/') for e in evidence): raise ValueError('Human release review must identify the exact final file')
        normalized.append(dict(id=c['id'],result=c['result'],observed_by=observer,note=c.get('note',''),evidence=evidence))
    if review['verdict']=='pass':
        if initial_issues:raise ValueError('Review inputs are unavailable or changed: '+'; '.join(initial_issues))
        blocked=[d for d in gate['depends'] if status[d]['state']!='passed']
        if blocked: raise ValueError('Unpassed or stale dependencies: '+', '.join(blocked))
    from ambiance_studio.production_coverage import normalize_observations
    observations=normalize_observations(project,review,context)
    receipt=dict(version=2 if context else 1,gate=gate['id'],verdict=review['verdict'],recorder=review['recorder'],
                 recorded_at=datetime.now(timezone.utc).isoformat(),checks=normalized,
                 project_digest=encoded_hash(context['settings'] if context else read(project/'project.json')),gate_digest=encoded_hash(gate),
                 watch_snapshot=initial_snapshot,
                 dependencies={d:status[d]['receipt_digest'] for d in gate['depends']})
    if context:
        receipt['subject']=context['subject']
        if context.get('plan_context'): receipt['expectations']=observations
        for check in normalized:
            for ev in check['evidence']:
                if digest(inside(project,ev['path']))!=ev['sha256']:raise ValueError('Evidence changed during review recording')
        for check in observations:
            for ev in check.get('evidence',[]):
                if digest(inside(project,ev['path']))!=ev['sha256']:raise ValueError('Expectation evidence changed during review recording')
    if scoped_watch(project,gate,context)!=(initial_snapshot,initial_issues):raise ValueError('Review inputs changed during review recording')
    receipt['payload_sha256']=encoded_hash(receipt)
    review_dir=context['review_dir'] if context else project/'reviews'
    path=review_dir/f'{gate["id"]}.json'
    if path.exists():
        old_digest=digest(path)
        history=review_dir/'history'/f'{gate["id"]}-{old_digest}.json'
        history.parent.mkdir(parents=True,exist_ok=True)
        if not history.exists(): shutil.copy2(path,history)
    write(path,receipt)
    return gate_status(project,context)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('init');p.add_argument('destination',type=Path);p.add_argument('--reference',type=Path);p.add_argument('--title')
    p=sub.add_parser('status');p.add_argument('project',type=Path)
    p=sub.add_parser('review-template');p.add_argument('project',type=Path);p.add_argument('gate');p.add_argument('--out',type=Path)
    p=sub.add_parser('record');p.add_argument('project',type=Path);p.add_argument('review',type=Path)
    args=parser.parse_args()
    try:
        if args.command=='init': result=new_project(args.destination,args.reference,args.title)
        elif args.command=='status': result=gate_status(args.project)
        elif args.command=='record': result=record_review(args.project,args.review)
        else:
            result=review_template(args.project,args.gate)
            if args.out:
                if args.out.exists(): raise ValueError('Refusing to overwrite an existing review draft')
                write(args.out,result)
        print(json.dumps(result,indent=2))
        return 0
    except (ValueError,KeyError,TypeError,OSError) as e:
        print(json.dumps(dict(ok=False,error=str(e)),indent=2),file=sys.stderr)
        return 2

if __name__=='__main__': sys.exit(main())
