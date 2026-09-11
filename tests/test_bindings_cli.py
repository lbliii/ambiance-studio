"""Public CLI transactions, exact package relationships, and captured dependencies."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from PIL import Image
import studio
from ambiance_studio import finishing, revisions
from ambiance_studio.cli import init_project, parser, run

ROOT = Path(__file__).resolve().parents[1]


class BindingCLI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.p = Path(self.temp.name)/'project'; init_project(self.p, None, 'Binding fixture', 'blank')
        script = """import {bindingFixture} from './tests/fixtures/binding-scene.mjs';
const f=bindingFixture((width,height)=>({width,height,getContext:()=>({fillRect(){},clearRect(){}})}));
console.log(JSON.stringify({scene:f.scene,catalog:f.catalog}));"""
        data = json.loads(subprocess.check_output(['node', '--input-type=module', '-e', script], cwd=ROOT))
        self.scene, self.catalog = data['scene'], data['catalog']
        for a in self.catalog['assets']:
            file=self.p/a['file']; Image.new('RGBA', (a['width'],a['height']), 'white').save(file)
            a['sha256']=studio.digest(file)
        self.scene_path=self.p/'scene/scene.json'; studio.write(self.scene_path,self.scene); studio.write(self.p/'assets/catalog.json',self.catalog)
        self.input=self.p/'bindings.json'; studio.write(self.input,{'kind':'ambiance-bindings','version':1,'bindings':self.scene['bindings']})

    def cli(self,*args):return run(parser().parse_args(['--project',str(self.p),*map(str,args)]))

    def test_inspect_transaction_dry_run_invalid_atomic_and_restore(self):
        result=self.cli('binding','inspect','--time',1); self.assertEqual(result['samples'][0]['value'],1)
        before=self.scene_path.read_bytes(); draft=self.cli('binding','apply',self.input,'--dry-run'); self.assertEqual(before,self.scene_path.read_bytes())
        self.cli('binding','apply',self.input,'--expect-sha256',draft['previous_sha256'])
        with self.assertRaisesRegex(Exception,'changed since expected'):self.cli('binding','apply',self.input,'--expect-sha256','0'*64)
        bad=studio.read(self.input); bad['bindings']['links'][0]['target']['layer']='missing';studio.write(self.input,bad)
        before=self.scene_path.read_bytes()
        with self.assertRaisesRegex(Exception,'endpoint'):self.cli('binding','apply',self.input)
        self.assertEqual(before,self.scene_path.read_bytes())
        self.cli('scene','restore',draft['previous_sha256'])
        self.assertEqual(studio.read(self.scene_path)['bindings'],self.scene['bindings'])

    def test_look_and_rig_package_roundtrip_keep_links_receivers_masks_and_actual_values(self):
        for rig in [False,True]:
            out=self.p/('rig' if rig else 'look'); package=self.cli('look','export','--out',out,*(['--include-rig'] if rig else []))
            doc=studio.read(package['package']); self.assertEqual(doc['scene_bindings'],self.scene['bindings'])
            remap={'kind':finishing.BINDINGS,'version':1,'layers':{x:'new-'+x for x in doc['requires']['layers']},'groups':{},'assets':{x['id']:x['id'] for x in doc['requires']['assets']}}
            mapping=self.p/'map.json';studio.write(mapping,remap)
            target=copy.deepcopy(self.scene);target.pop('bindings');target.pop('finishing')
            # Change the complete dependency graph; the package must rebind every edge.
            for layer in target['layers']:
                if layer['id'] in remap['layers']:layer['id']=remap['layers'][layer['id']]
                if layer.get('attach') and layer['attach']['layer'] in remap['layers']:layer['attach']['layer']=remap['layers'][layer['attach']['layer']]
            studio.write(self.scene_path,target)
            self.cli('look','import',out,'--bindings',mapping,*(['--include-rig'] if rig else []))
            actual=studio.read(self.scene_path)
            self.assertEqual(actual['bindings']['links'][0]['target']['layer'],'new-floor-paint')
            self.assertEqual(actual['finishing']['illuminations'][0]['receiver'],'new-floor')
            self.assertEqual(actual['finishing']['signals'][0]['layer'],'new-flame')
            self.assertEqual(self.cli('binding','check','--time',1)['samples'][0]['value'],1)
            studio.write(self.scene_path,self.scene)

    def test_captured_mask_and_source_driver_divergence_are_separate(self):
        selection=self.p/'selection.json';studio.write(selection,{'format':revisions.SELECTION,'schema_version':1,'scene':'scene/scene.json','catalog':'assets/catalog.json'})
        revisions.capture(self.p,'bound-v1',selection)
        manifest=revisions.load(self.p,'bound-v1')
        self.assertTrue(any(x['role']=='finishing-illuminations-mask' for x in manifest['dependencies']))
        self.scene['bindings']['links'][0]['map']['keys'][1][1]=.5;studio.write(self.scene_path,self.scene)
        self.assertTrue(revisions.check(self.p,'bound-v1')['ok'])
        self.assertTrue(revisions.compare(self.p,'bound-v1')['working_diverged'])
        (self.p/'assets/mask.png').write_bytes(b'changed')
        self.assertFalse(revisions.check(self.p,'bound-v1')['ok'])
        with self.assertRaises(Exception):self.cli('binding','check')

    def test_compiler_companion_registration_correction_and_package_identity(self):
        from tools import asset_tool
        # Both masks are prepared from the same source coordinate basis. Only a
        # deliberately matching registration correction may move the receiver.
        reference=self.p/'assets/reference.png';Image.new('RGBA',(16,16),'#242424').save(reference)
        ref={'file':'assets/reference.png','sha256':studio.digest(reference),'width':16,'height':16}
        def build(aid, source, point):
            mapping=self.p/'assets'/f'{aid}-mapping.json'
            studio.write(mapping,{'format':'ambiance-asset-source-mapping','version':1,'path_base':'project',
                'reference':ref,'image':{'file':source['file'],'sha256':source['sha256'],'width':16,'height':16},'image_to_reference':[1,0,0,1,0,0]})
            recipe=self.p/'assets'/f'{aid}-recipe.json'
            studio.write(recipe,{'version':1,'id':aid,'input':{'sheet':Path(source['file']).name,'columns':1,'rows':1,'frame_count':1},
                'source_mapping':{'file':mapping.name,'sha256':studio.digest(mapping)},
                'registration':{'mode':'fixed','point':point,'target':[.5,.5]},'output':{'cell_size':[24,24],'columns':1,'padding':2}})
            out=self.p/'assets/compiled'/aid;asset_tool.build(recipe,out);asset_tool.admit(out,self.p/'assets/catalog.json')
        byid={a['id']:a for a in self.catalog['assets']}
        for aid in ['base','mask']:
            im=Image.new('RGBA',(16,16),(0,0,0,0));im.paste('white',(2,2,14,14));im.save(self.p/byid[aid]['file']);byid[aid]['sha256']=studio.digest(self.p/byid[aid]['file'])
        studio.write(self.p/'assets/catalog.json',self.catalog)
        build('floor-v1',byid['base'],[8,8]);build('mask-v1',byid['mask'],[8,8])
        scene=copy.deepcopy(self.scene);scene['layers'][0].update(asset='floor-v1',cycle_seconds=4,phase_frames=0)
        scene['finishing']['illuminations'][0]['mask_asset']='mask-v1';studio.write(self.scene_path,scene)
        self.cli('binding','check')
        build('floor-v2',byid['base'],[7,8]);build('mask-v2',byid['mask'],[7,8])
        batch=self.p/'correct.json';studio.write(batch,{'version':1,'operations':[{'op':'set','layer':'floor','values':{'asset':'floor-v2'}}]})
        before=self.scene_path.read_bytes()
        with self.assertRaisesRegex(Exception,'companion correction'):self.cli('scene','apply',batch)
        self.assertEqual(before,self.scene_path.read_bytes())
        finish=copy.deepcopy(scene['finishing']);finish['illuminations'][0]['mask_asset']='mask-v2'
        operations=studio.read(batch);operations['operations'].append({'op':'finishing','value':finish});studio.write(batch,operations)
        self.cli('scene','apply',batch)
        out=self.p/'registered-look';self.cli('look','export','--out',out,'--include-rig')
        package=studio.read(out/'look.json');self.assertTrue(any('registration' in a for a in package['requires']['assets']))
        bindings={'kind':finishing.BINDINGS,'version':1,'layers':{x:x for x in package['requires']['layers']},'groups':{},'assets':{a['id']:a['id'] for a in package['requires']['assets']}}
        path=self.p/'registered-bindings.json';studio.write(path,bindings)
        self.cli('look','import',out,'--bindings',path,'--include-rig')
        bindings['assets']['mask-v2']='mask-v1';studio.write(path,bindings)
        with self.assertRaisesRegex(Exception,'Mask version differs'):self.cli('look','import',out,'--bindings',path,'--include-rig')

    def test_binding_timing_and_reparent_cannot_silently_replace_drivers(self):
        timing=self.cli('scene','timing','--layer','floor-paint')['layers'][0]
        self.assertEqual(timing['timing_driver'],'binding');self.assertFalse(timing['fallback_cycle']['active'])
        self.assertFalse(timing['authored']['available']);self.assertEqual(timing['authored']['holds'],[])
        self.assertGreater(timing['sampled']['cel_transitions'],0)
        with self.assertRaisesRegex(Exception,'bound child channels'):
            self.cli('scene','reparent','floor-paint','--to','pumpkin','--socket','wick','--keep-world','--at',0)

    def test_changed_source_asset_or_mask_fails_before_mutation(self):
        before=self.scene_path.read_bytes();(self.p/'assets/flame.png').write_bytes(b'changed source')
        with self.assertRaises(Exception):self.cli('binding','apply',self.input)
        self.assertEqual(before,self.scene_path.read_bytes())


if __name__=='__main__':unittest.main()
