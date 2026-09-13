"""Fixed native-operation adapters. Projection never runs a production operation."""
import importlib.util
from pathlib import Path
import shutil

import studio
from .errors import CommandError
from .workflow_subjects import ERRORS

ROOT = Path(__file__).resolve().parents[1]
ROUTES = {
    'reference.inspect':['project','status'], 'intent.author':['plan','spec','apply'],
    'inventory.inspect':['plan','inspect'], 'inventory.fulfill':['plan','fulfill'],
    'evidence.register':['plan','evidence'], 'scene.apply':['scene','apply'], 'view.apply':['view','apply'], 'view.inspect':['view','inspect'],
    'picture.proof':['render','views-proof'], 'scene.timing':['scene','timing'], 'scene.activity':['scene','activity'],
    'art.preflight':['asset','preflight'], **{'prepare.'+v:['asset','prepare'] for v in ['init','inspect','check','edit','build','proof','place']},
    'asset.build':['asset','build'], 'asset.proof':['asset','proof'],
    'audio.source-inspect':['audio','source-inspect'], 'audio.inspect':['audio','inspect'],
    'audio.mix':['audio','mix'], 'audio.check':['audio','check'], 'iteration.inspect':['iteration','inspect'],
    'iteration.init':['iteration','init'], 'feedback.inspect':['feedback','inspect'], 'media.verify':['media','verify'], 'delivery.inspect':['delivery','inspect'],
    'delivery.present':['delivery','present'], 'review.draft':['review','draft'],
    'delivery.handoff':['delivery','handoff'], 'revision.handoff':['revision','handoff'], 'library.find':['library','find'],
}


class Operations:
    def __init__(self, query, catalog):
        self.query, self.catalog = query, catalog
        self.runtime = {}

    def available(self, runtime):
        if runtime not in self.runtime:
            try:
                if runtime is None: value = True
                elif runtime == 'node': value = bool(shutil.which('node'))
                elif runtime == 'pillow': value = importlib.util.find_spec('PIL') is not None
                elif runtime == 'audio-source': value = True  # backend is an explicit input
                else:
                    from .native_media import capabilities
                    if 'media' not in self.runtime:self.runtime['media']=capabilities()
                    value = self.runtime['media']['frame_render' if runtime=='renderer' else 'media_verify']
                self.runtime[runtime] = {'available':value}
            except ERRORS as error:self.runtime[runtime]={'available':False,'diagnostic':str(error)}
        return self.runtime[runtime]

    def resolve(self, op, subject, ctx, bindings, output_key):
        guide = self.catalog['operations'][op]
        missing=[]; refs=[]; args=[]; limitations=[]
        def need(key):
            value = bindings.get(key)
            if value is None:missing.append(key)
            return value
        def path(key):
            value=need(key)
            if value is None:return None
            p=Path(value).resolve()
            if not p.is_relative_to(self.query.project):
                raise ValueError('Workflow native inputs must remain in selected project: '+str(p))
            ref=self.query.pin(p); refs.append(ref)
            if ref['sha256'] is None:missing.append(key+': file unavailable')
            return str(p)
        def output(file=False):
            target=studio.inside(self.query.project,'reports/workflow/'+output_key+('.json' if file else ''))
            if target.exists():missing.append('fresh output path: suggested destination is occupied')
            return str(target)
        def picture():
            if ctx is None:missing.append('captured scene/catalog');return
            for key in ['scene','catalog','views','asset_dependencies']:
                value=ctx.get(key)
                if value is None:missing.append(key)
            if ctx.revision:
                if ctx.get('revision_dependencies') is None:missing.append('revision_dependencies')
                args.extend(['--revision',ctx.revision])
            selected=need('view')
            if selected is not None:
                if selected not in (ctx.get('views') or {}):missing.append('valid saved view')
                args.extend(['--view',selected])
        if op == 'reference.inspect':
            path('reference'); missing.append('actual visual inspection and observations')
        elif op == 'intent.author':
            path('authored_plan')
            missing.extend(['story.premise','story.direction','sources','elements','actions','outputs','relations','expectations','change'])
            limitations.append('Author these creative choices in native production-plan JSON. No default expands existing scope.')
        elif op in ['inventory.fulfill','scene.apply','view.apply']:
            path('native_input')
            missing.append('authored native input validated by '+ ' '.join(guide['route']))
            if op=='inventory.fulfill':need('expected_inventory_sha256')
        elif op == 'evidence.register':
            need('expectation_id');need('view');path('provider_receipt')
            limitations.append('Use the existing exact provider validator after proof creation; no receipt is invented.')
        elif op == 'inventory.inspect':
            if ctx is None or ctx.revision:missing.append('working inventory subject; inspect captured inventory via workflow stage layout --details')
            elif any(ctx.get(key) is None for key in ['scene','catalog','inventory']):missing.append('readable inventory/scene/catalog')
        elif op in ['picture.proof','scene.activity']:
            picture(); args += ['--out',output()]
            limitations.append('Native bounded proof duration; inspect scene timing and actual full-cycle motion separately.')
        elif op == 'view.inspect':
            if ctx is None:missing.append('captured scene/catalog')
            else:
                if ctx.get('scene') is None or ctx.get('catalog') is None:missing.append('readable scene/catalog')
                view=bindings.get('view',subject.get('view'))
                if view is not None:
                    if view not in (ctx.get('views') or {}):missing.append('valid saved view')
                    args.append(view)
                if ctx.revision:
                    if ctx.get('revision_dependencies') is None:missing.append('revision_dependencies')
                    args += ['--revision',ctx.revision]
        elif op == 'scene.timing':
            if ctx is None:missing.append('captured scene/catalog')
            elif ctx.revision:
                # This existing timing route lacks a captured-context selector.
                missing.append('native route lacks --revision; captured material is available through workflow stage details')
            elif ctx.get('scene') is None or ctx.get('catalog') is None:missing.append('readable scene/catalog')
        elif op == 'art.preflight':
            p=path('source')
            if p:args.append(p)
            args += ['--out',output()]
        elif op.startswith('prepare.'):
            verb=op.split('.')[1];args.append(verb)
            p=path('recipe')
            if p:args.append(p)
            if verb in ['init','edit','build','proof']:args += ['--out',output()]
            if verb=='edit':
                batch=path('batch')
                if batch:args += ['--batch',batch]
                need('expected_recipe_hash')
            if verb=='place':
                for key,flag in [('base','--base'),('prefix','--prefix'),('expected_scene_hash','--expect-sha256')]:
                    value=need(key)
                    if value:args += [flag,value]
            if verb=='build' and p and not missing:
                from . import compound_preparation as cp, preparation
                recipe=self.query.read(Path(p))
                ctx_refs = list(cp.references(recipe)) if recipe.get('format')==cp.FORMAT else list(preparation.references(recipe))
                for _,ref in ctx_refs:
                    name=ref.get('file',ref.get('path'))
                    if name:self.query.pin(studio.inside(self.query.project,name))
                if recipe.get('format')==cp.FORMAT:
                    # Existing pure native check validates source pins and context.
                    checked=cp.inspect(self.query.project,Path(p),check=True)
                    if not checked.get('ok',True):missing.append('native preparation check failed')
                else:
                    preparation.validate(recipe);preparation.load_inputs(self.query.project,recipe)
                    args=['--recipe',p,'--out',output()]
        elif op == 'asset.build':
            p=path('compiler_recipe')
            if p and not missing:
                recipe=self.query.read(Path(p))
                spec=recipe.get('input',{})
                sources=spec.get('frames',[]) or ([spec['sheet']] if spec.get('sheet') else [])
                if not sources:missing.append('native compiler source frames or sheet')
                for name in sources:
                    source=(Path(p).parent/name).resolve()
                    if not source.is_relative_to(self.query.project):raise ValueError('Compiler source escapes selected project')
                    ref=self.query.pin(source);refs.append(ref)
                    if ref['sha256'] is None:missing.append('compiler source: '+str(source))
                for key in ['version','id','registration','output']:
                    if key not in recipe:missing.append('compiler recipe '+key)
                args += [p,'--out',output()]
            limitations.append('Already-isolated art goes directly to the native compiler. The compiler validates authored registration and output choices on execution; no build or editable-model admission was performed.')
        elif op == 'asset.proof':
            aid=need('asset_id')
            if aid:args.append(aid)
            if ctx is None:missing.append('catalog')
            else:
                cat=ctx.get('catalog')
                row=next((r for r in (cat or {}).get('assets',[]) if r['id']==aid),None)
                if row is None:missing.append('catalog asset')
                else:
                    from .assets import read_asset
                    self.query.pin(studio.inside(self.query.project,row['file']));read_asset(row,self.query.project)
                if cat:args += ['--catalog',str(ctx.path('catalog'))]
            args += ['--out',output()]
        elif op in ['audio.inspect','audio.mix','audio.check','audio.source-inspect']:
            key='source' if op=='audio.source-inspect' else 'master' if op=='audio.check' else 'session'
            p=path(key)
            if p:args.append(p)
            if op=='audio.source-inspect':
                backend=need('backend')
                if backend:args += ['--backend',backend]
            if op=='audio.mix':missing.append('explicit mix run ID and reviewed session choices')
        elif op in ['iteration.inspect','feedback.inspect']:
            run=need('run_id' if op=='iteration.inspect' else 'feedback_id')
            if run:args.append(run)
        elif op == 'iteration.init':
            p=path('iteration_input')
            if p:args.append(p)
            args += ['--out',output()]
        elif op == 'media.verify':
            p=path('movie')
            if p:args.append(p)
            expected=need('output_expectations')
            if expected:
                for key,value in expected.items():args += ['--'+key.replace('_','-'),str(value)]
            if subject.get('revision'):args += ['--revision',subject['revision']]
            if subject.get('edition'):args += ['--edition',subject['edition']]
            if subject.get('view'):args += ['--view',subject['view']]
            args += ['--out',output()]
        elif op.startswith('delivery.'):
            id=subject.get('delivery') or need('delivery_id')
            if id:args.append(id)
            if op=='delivery.present':
                need('recorder');need('channel')
                limitations.append('Selection is explicit and requires actual recorder identity; workflow grants no publishing authority.')
            if op=='delivery.handoff':args += ['--out',output()]
        elif op == 'revision.handoff':
            id=subject.get('revision') or need('revision')
            if id:args.append(id)
            if subject.get('edition'):args += ['--edition',subject['edition']]
            args += ['--out',output()]
        elif op == 'review.draft':
            gate=need('gate')
            if gate:args.append(gate)
            if subject.get('revision'):
                args += ['--revision',subject['revision']]
                if subject.get('edition'):args += ['--edition',subject['edition']]
                elif subject.get('view'):args += ['--view',subject['view']]
            elif subject['mode']!='working':missing.append('captured review subject')
            if bindings.get('review_unavailable'):missing.append('readable native review context')
            args += ['--out',output(True)]
            limitations.append('Draft checks remain not-run. Actual observations and native review record are separate work.')
        elif op == 'library.find':pass
        else:raise ValueError('Unbound native operation '+op)
        result={'operation':op,'effects':guide['effects'],'inputs':refs,'missing_inputs':list(dict.fromkeys(missing)),
                'expected_outputs':guide['outputs'],'limits':limitations,'help_argv':[str(ROOT/'ambiance'),*guide['route'],'--help']}
        available=self.available(guide['runtime'])
        if not available['available']:
            result.update(state='unavailable',runtime={'name':guide['runtime'],**available})
        elif missing:result['state']='needs-input'
        else:
            result['state']='ready'
            result['argv']=[str(ROOT/'ambiance'),'--project',str(self.query.project),*guide['route'],*args]
            from .cli import parser
            parser().parse_args(result['argv'][1:])
            result['cwd']=str(ROOT)
        return result
