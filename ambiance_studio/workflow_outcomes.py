"""Bounded optional outcome presentation, separate from all native artifacts."""
import json
from pathlib import Path

from .workflow_catalog import ROOT

FORMAT='ambiance-operation-guidance'
# Each binding names native operations, not inferred causes or gate verdicts.
ADAPTERS={
    ('project','init'):('Project initialized. Inspect preserved reference and author explicit intent.', ['workflow','stage','intent']),
    ('asset','build'):('Pack built. Inspect its technical contents before proof and admission.', ['asset','inspect']),
    ('asset','proof'):('Proof produced. Observe actual playback, registration and edges before recording a review.', None),
    ('scene','apply'):('Scene transaction completed. Check the changed scene and inspect its actual motion.', ['scene','check']),
    ('scene','check'):('Technical scene check completed. Raster, motion and observation evidence remain separate.', ['scene','timing']),
    ('review','record'):('Native review recorded for its exact subject. Its native status remains authoritative.', None),
    ('iteration','init'):('Native inputs initialized. Capture, rendering and presentation remain separate.', None),
    ('iteration','run'):('Iteration returned its native run and delivery state. Inspect the exact result before continuing.', ['iteration','inspect']),
    ('delivery','present'):('Exact delivery presented. Unperformed human checks remain open.', ['delivery','inspect']),
}
RECOVERY={
    'stale_input':'Reinspect the changed native input and rebase the explicit edit before retrying.',
    'stale_assessment':'Reinspect the same workflow subject and prepare a fresh packet.',
    'stale_action':'Reinspect the same subject; the old action is no longer applicable.',
    'output_exists':'Inspect the occupied destination; choose a fresh output only for new work.',
    'missing_dependency':'Restore the named native runtime, then retry the unchanged input.',
    'interrupted':'Inspect saved run/artifact state before resuming the unchanged recipe.',
    'project_locked':'Inspect the active writer before retrying; do not remove a live lock.',
    'stale_selection':'Inspect the current exact selection and saved delivery before explicitly presenting again.',
}


def local(args, payload, output):
    route=(args.command,getattr(args,'action',None));adapter=ADAPTERS.get(route)
    data=payload.get('data') if isinstance(payload.get('data'),dict) else {}
    error=payload.get('error',{})
    result={'format':FORMAT,'schema_version':1,'mode':args.guidance,'assessment':'operation-local',
            'operation':list(route),'supported':adapter is not None,'operation_ok':payload['ok'],
            'freshness':{'basis':'returned-native-outcome','reassessed':False},
            'output_ownership':output.value if output else 'native-return',
            'scope':'Only this invocation. No coverage, library scan, observation or gate acceptance is inferred.'}
    if getattr(args,'out',None):result['output_path']=str(args.out.absolute())
    result['native_facts']={key:data[key] for key in
                           ['status','pack','asset_id','source','source_sha256','html','sha256','previous_sha256','dry_run','recipe','selection']
                           if key in data}
    if not payload['ok']:
        code=error.get('code')
        result['recovery']={'code':code or 'native_result_not_ok','mapped':code in RECOVERY,
                            'action':RECOVERY.get(code,'Inspect the original native error/result and the input contract; no automatic retry or guessed repair.')}
        result['summary']='Native operation failed; original result and exit status are preserved.'
    elif adapter:
        result['summary']=adapter[0]
        if getattr(args,'dry_run',False):result['summary']='Native dry run completed; no mutation was requested.'
    else:result['summary']='No outcome adapter for this route; native output is unchanged.'
    # Do not resolve aliases or scan projects in auto mode. Use only paths/IDs
    # supplied or returned by this exact invocation; registry aliases stay argv.
    selected=data.get('project') if route==('project','init') else getattr(args,'project',None)
    prefix=[str(ROOT/'ambiance')]+(['--project',str(selected)] if selected else [])
    next_route=adapter[1] if adapter and payload['ok'] else None
    if route==('asset','build') and payload['ok']:
        result['next_argv']=[str(ROOT/'ambiance'),'asset','inspect',str(args.out.absolute())]
    elif route==('iteration','run') and payload['ok']:
        run=data.get('run',{})
        if run.get('id'):result['next_argv']=[*prefix,'iteration','inspect',run['id']]
    elif route==('delivery','present') and payload['ok']:
        result['next_argv']=[*prefix,'delivery','inspect',args.id]
        # Keep every returned selection identity; never flatten to a default view.
        result['subject']=data.get('selection',{})
    elif route==('review','record') and payload['ok']:
        result['subject']=data.get('subject',{})
    elif route==('iteration','init') and payload['ok'] and data.get('recipe'):
        result['next_argv']=[*prefix,'iteration','preflight',data['recipe']]
    elif next_route and selected:result['next_argv']=[*prefix,*next_route]
    if 'next_argv' not in result:
        result['inspect_argv']=[*prefix,*(list(route) if all(route) else [args.command]),'--help']
    result['compatibility']='No catalog criterion binding asserted by operation-local guidance.'
    return result


def full(args, payload, guidance):
    from . import cli, workflow, deliveries
    route=(args.command,getattr(args,'action',None))
    if not payload['ok'] or not guidance['supported']:
        guidance['reassessment']={'state':'not-applicable','reason':'Original failure/unsupported route retained; use explicit workflow inspection.'}
        return
    data=payload.get('data',{})
    selected=data.get('project') if route==('project','init') else getattr(args,'project',None)
    project=cli.optional_project_path(selected,getattr(args,'registry',None))
    if project is None:
        guidance['reassessment']={'state':'unavailable','reason':'No project subject; artifact-local continuation only.'}
        return
    selectors={};selection=None
    if route==('review','record'):
        subject=data.get('subject',{})
        if subject.get('revision'):
            selectors={k:subject[k] for k in ['revision','edition','view'] if subject.get(k)}
        elif subject.get('mode') != 'legacy-path-watches':
            guidance['reassessment']={'state':'unavailable','reason':'Native review has no compatible workflow subject.'};return
    elif route==('delivery','present'):
        selection=data.get('selection')
        channel=getattr(args,'channel','review')
        current=deliveries.current(project,channel)
        if not selection or not current or current['payload_sha256']!=selection['payload_sha256']:
            raise ValueError('Presented selection changed before guidance; no substitute selected')
        selectors={'subject':channel}
    elif route==('iteration','run'):
        guidance['reassessment']={'state':'unavailable','reason':'Run outcome may contain multiple entries without a selected workflow subject. Inspect its exact delivery explicitly.'};return
    report=workflow.inspect(project,limit=1,subject_limit=2,**selectors)
    if selection and deliveries.current(project,selectors['subject'])['payload_sha256']!=selection['payload_sha256']:
        raise ValueError('Presented selection changed during guidance')
    guidance['reassessment']={'state':'assessed','assessment':report['assessment'],'catalog':report['catalog'],
        'selection':report['selection'],'full_scope':report['full_scope'],'subjects':report['subjects'],
        'subject_count':report['subject_count'],'subjects_omitted':report['subjects_omitted'],
        'items':report['items'],'omitted':report['omitted'],'diagnostics':report['diagnostics'],
        'details_argv':report['details_argv']}
    guidance['freshness']={'basis':'fresh-scoped-workflow-assessment','reassessed':True,
                           'sha256':report['assessment']['sha256'],'complete':report['assessment']['complete']}


def unavailable(mode, payload, error):
    return {'format':FORMAT,'schema_version':1,'mode':mode,'state':'unavailable',
            'operation_ok':payload['ok'],'diagnostic':{'code':'guidance_unavailable','type':type(error).__name__,
                'message':str(error)[:400]},
            'meaning':'Native outcome and exit status are preserved. Do not repeat a successful mutation because guidance failed.'}


def attach(args, payload, output):
    try:
        guidance=local(args,payload,output)
        if args.guidance=='full':full(args,payload,guidance)
        # Guidance serialization must also be contained before touching the native
        # envelope. Bounded diagnostic fallback preserves completed mutations.
        if len(json.dumps(guidance,allow_nan=False).encode())>16384:
            raise ValueError('Guidance exceeded the 16 KiB bound; use explicit workflow inspection')
    except (Exception,KeyboardInterrupt,SystemExit) as error:
        guidance=unavailable(args.guidance,payload,error)
    return {**payload,'guidance':guidance}
