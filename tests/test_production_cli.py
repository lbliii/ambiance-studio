import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from ambiance_studio import planning,assets,scene_runtime
from tools import asset_tool


def cli(*args,cwd=None):
    p=subprocess.run([sys.executable,str(ROOT/'ambiance'),*map(str,args)],capture_output=True,text=True,cwd=cwd)
    return p.returncode,json.loads(p.stdout)


class ProductionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.p=self.root/'film'
        code,result=cli('project','init',self.p);self.assertEqual(code,0,result)
        self.img=self.p/'assets/source.png';Image.new('RGBA',(12,12),(250,220,120,255)).save(self.img)
        self.catalog={'version':1,'assets':[{'id':'paint','kind':'plate','file':'assets/source.png','width':12,'height':12,'sha256':hashlib.sha256(self.img.read_bytes()).hexdigest()}]}
        (self.p/'assets/catalog.json').write_text(json.dumps(self.catalog))
        code,result=self.run_cli('scene','add','paint','--id','base','--width','1');self.assertEqual(code,0,result)
        self.scene=self.p/'scene/scene.json'
    def run_cli(self,*args):return cli('--project',self.p,*args)
    def plan(self,items):
        path=self.p/'plans/asset-inventory.json';path.write_text(json.dumps({'version':1,'items':items}));return path
    def test_missing_work_is_visible_but_not_integrity_failure(self):
        self.plan([{'id':'room','state':'static-support','existing_asset_ids':['paint']},{'id':'rat','state':'not-produced','required_parts':['gait'],'dependencies':['floor']},{'id':'floor','state':'not-produced','required_parts':['repair']}])
        code,data=self.run_cli('plan','next');self.assertEqual(code,0,data)
        self.assertEqual([r['id'] for r in data['data']['ready']],['floor'])
        self.assertEqual(data['data']['blocked'],[{'id':'rat','dependencies':['floor']}])
    def test_transitive_dependencies_and_missing_source_evidence(self):
        evidence={'file':'assets/source.png','sha256':self.catalog['assets'][0]['sha256']}
        part={'id':'cut','stage':'placed','files':[evidence],'asset_id':'paint','layer_ids':['base']}
        self.plan([{'id':'a','required_parts':[part],'dependencies':['b']},{'id':'b','required_parts':[part],'dependencies':['c']},{'id':'c','required_parts':['missing']}])
        result=planning.inspect(self.p);self.assertTrue(result['ok']);self.assertTrue(all(not x['complete_for_scope'] for x in result['items']))
        self.img.write_bytes(b'changed')
        result=planning.inspect(self.p);self.assertFalse(result['ok']);self.assertTrue(any('changed' in e for e in result['errors']))
        self.assertTrue(all(not x['complete_for_scope'] for x in result['items']))
    def test_review_requesting_revision_remains_actionable(self):
        evidence={'file':'assets/source.png','sha256':self.catalog['assets'][0]['sha256']}
        self.plan([{'id':'prop','required_parts':[{'id':'cut','stage':'placed','files':[evidence],'asset_id':'paint','layer_ids':['base'],'review':{'state':'needs-revision','evidence':[evidence]}}]}])
        result=planning.inspect(self.p);self.assertTrue(result['ok'])
        part=result['items'][0]['required_parts'][0]
        self.assertTrue(part['production_complete']);self.assertFalse(result['items'][0]['complete_for_scope'])
    def test_cycles_unknown_assets_and_fake_completion_fail(self):
        self.plan([{'id':'a','state':'complete','dependencies':['b'],'existing_asset_ids':['imaginary']},{'id':'b','dependencies':['a']}])
        code,result=self.run_cli('plan','check');self.assertEqual(code,1,result)
        self.assertTrue(any('cycle' in e for e in result['data']['errors']))
    def test_deferring_a_backing_does_not_fulfill_another_objects_dependency(self):
        self.plan([{'id':'floor','state':'static-deferred'},{'id':'rat','required_parts':['gait'],'dependencies':['floor']}])
        result=planning.inspect(self.p);self.assertTrue(result['ok'])
        self.assertEqual(result['items'][1]['blocked_by'],['floor'])
    def test_batch_dry_run_stale_hash_atomic_failure_and_restore(self):
        before=self.scene.read_bytes();sha=hashlib.sha256(before).hexdigest();batch=self.root/'batch.json'
        batch.write_text(json.dumps({'version':1,'operations':[{'op':'set','layer':'base','values':{'x':.3}},{'op':'set','layer':'absent','values':{'x':.4}}]}))
        code,data=self.run_cli('scene','apply',batch);self.assertEqual(code,2,data);self.assertEqual(before,self.scene.read_bytes())
        batch.write_text(json.dumps({'version':1,'operations':[{'op':'set','layer':'base','values':{'x':.3}}]}))
        code,data=self.run_cli('scene','apply',batch,'--dry-run','--expect-sha256',sha);self.assertEqual(code,0,data);self.assertEqual(before,self.scene.read_bytes())
        self.assertEqual(data['data']['scene']['layers'][0]['x'],.3)
        code,data=self.run_cli('scene','apply',batch,'--expect-sha256','0'*64);self.assertEqual(data['error']['code'],'stale_input')
        code,data=self.run_cli('scene','apply',batch,'--expect-sha256',sha);self.assertEqual(code,0,data)
        code,data=self.run_cli('scene','restore',sha);self.assertEqual(code,0,data);self.assertEqual(json.loads(before),json.loads(self.scene.read_text()))
    def test_track_and_full_inspection(self):
        track=self.root/'track.json';track.write_text(json.dumps({'version':1,'tracks':{'x':{'interpolation':'linear','keys':[[0,.5],[8,.9],[16,.5]]}}}))
        code,data=self.run_cli('scene','track','base',track);self.assertEqual(code,0,data)
        code,data=self.run_cli('scene','inspect','--full');self.assertEqual(code,0,data);self.assertIn('camera',data['data'])
        code,data=self.run_cli('scene','sample','--time','4');self.assertEqual(code,0,data)
        self.assertAlmostEqual(data['data'][0]['matrix'][4],(.7*1080-540)*1.08+540)
    def test_direct_scene_change_during_batch_validation_is_not_overwritten(self):
        from ambiance_studio import cli as module
        batch=self.root/'batch.json';batch.write_text(json.dumps({'version':1,'operations':[{'op':'set','layer':'base','values':{'x':.3}}]}))
        original_bridge=scene_runtime.scene_bridge
        external=json.loads(self.scene.read_text());external['title']='Changed by another writer'
        def edit_during_validation(*args):
            candidate=original_bridge(*args);self.scene.write_text(json.dumps(external));return candidate
        args=module.parser().parse_args(['--project',str(self.p),'scene','apply',str(batch)])
        with patch.object(scene_runtime,'scene_bridge',side_effect=edit_during_validation):
            with self.assertRaises(module.CommandError) as error:module.run(args)
        self.assertEqual(error.exception.code,'stale_input');self.assertEqual(json.loads(self.scene.read_text()),external)
    def test_asset_proof_keeps_original_and_exposes_actual_pixels(self):
        before=self.img.read_bytes();out=self.root/'proof'
        code,data=self.run_cli('asset','proof','paint','--out',out,'--landmark','wick')
        self.assertEqual(code,0,data);self.assertTrue((out/'index.html').is_file());self.assertTrue((out/'onion-skin.png').is_file())
        self.assertEqual(data['data']['cel_analysis']['distinct_decoded_cels'],1);self.assertEqual(before,self.img.read_bytes())
        code,data=self.run_cli('asset','proof','paint','--out',out);self.assertEqual(code,2,data)
    def test_asset_and_library_inspection_discover_the_current_project(self):
        conf_path=self.p/'ambiance-project.json';conf=json.loads(conf_path.read_text())
        nested=self.p/'nested/catalog/store.json';nested.parent.mkdir(parents=True);nested.write_text(json.dumps(self.catalog))
        conf['catalog']='nested/catalog/store.json';conf_path.write_text(json.dumps(conf))
        code,data=cli('library','inspect','paint',cwd=self.p/'scene');self.assertEqual(code,0,data)
        code,data=cli('asset','proof','paint','--out',self.root/'nested-proof',cwd=self.p/'scene');self.assertEqual(code,0,data)
    def test_named_landmark_compilation_portable_cache_and_source_change(self):
        frame=self.root/'cel.png';im=Image.new('RGBA',(20,20));ImageDraw.Draw(im).rectangle((5,5,12,17),fill='orange');im.save(frame)
        landmarks=self.root/'landmarks.json';landmarks.write_text(json.dumps({'version':1,'landmarks':{'wick':[[8,17]]}}))
        recipe=self.root/'recipe.json';recipe.write_text(json.dumps({'version':1,'id':'wick','input':{'frames':['cel.png']},'registration':{'mode':'landmarks','landmarks_file':'landmarks.json','landmark':'wick','target':[.5,.8]},'output':{'cell_size':[24,24],'columns':1}}))
        out=self.root/'pack';asset_tool.build(recipe,out)
        data=json.loads((out/'asset.json').read_text());self.assertEqual(data['provenance']['registration_source']['name'],'wick')
        self.assertEqual(asset_tool.build(out/'recipe.json',out)['status'],'cached')
        self.assertTrue(assets.inspect_pack(out)['ok'])
        portable=json.loads((out/'recipe.json').read_text());portable['registration']['points']=[[9,17]]
        (out/'edited-recipe.json').write_text(json.dumps(portable))
        with self.assertRaisesRegex(ValueError,'differ from'):asset_tool.build(out/'edited-recipe.json',self.root/'altered-pack')
        landmarks.write_text(landmarks.read_text()+' ')
        with self.assertRaisesRegex(ValueError,'landmark source changed'):asset_tool.build(out/'recipe.json',self.root/'new-pack')
    def test_library_search_exposes_flame_study(self):
        code,data=cli('library','find','flame','--directory',self.root)
        self.assertEqual(code,0,data)
        self.assertTrue(any(r['id']=='flame-cels' for r in data['data']['matches']))

if __name__=='__main__':unittest.main(verbosity=2)
