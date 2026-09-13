"""Public local model construction, failure atomicity and exact proof freshness."""
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from ambiance_studio import cli, model_package
from ambiance_studio.file_identity import digest
from ambiance_studio.record_contracts import seal
import studio

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('model_fixture', ROOT/'examples/model-construction/create_fixture.py')
fixture = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixture)


def invoke(*argv):
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream): code = cli.main(list(map(str, argv)))
    return code, json.loads(stream.getvalue())


class ModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(); cls.base = Path(cls.temp.name)
        cls.source = fixture.create(cls.base/'source')
        cls.definition = cls.source/'models/lantern.json'
        cls.package = cls.base/'package'
        code, output = invoke('model','build',cls.definition,'--source-root',cls.source,'--out',cls.package)
        if code: raise AssertionError(output)

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def setUp(self):
        self.temp_case = tempfile.TemporaryDirectory(dir=self.base); self.work = Path(self.temp_case.name)
        self.addCleanup(self.temp_case.cleanup)

    def altered(self, fn):
        source = self.work/'source'; shutil.copytree(self.source, source)
        path = source/'models/lantern.json'; data = studio.read(path); fn(data); studio.write(path,data)
        return source,path

    def rejects(self, fn, match=None):
        source,path = self.altered(fn); out=self.work/'bad-package'
        code,payload=invoke('model','build',path,'--source-root',source,'--out',out)
        self.assertNotEqual(code,0,payload);self.assertFalse(out.exists())
        if match:self.assertIn(match,payload['error']['message'])

    def test_public_build_inspect_without_project(self):
        code,data=invoke('--project','missing','model','inspect',self.package)
        self.assertEqual(code,0,data);self.assertEqual(len(data['data']['members']),5)
        self.assertEqual(data['data']['model_count'],2);self.assertEqual(data['data']['acceptance'],'not established')
        self.assertTrue((self.package/'source/art/flame.png').exists())
        self.assertTrue((self.package/'source/packs/flame/recipe.json').exists())

    def test_reopens_materialized_closure_without_original(self):
        copied=self.work/'portable';shutil.copytree(self.package,copied)
        # No source pointer survives; use a renamed source independently of this class fixture.
        isolated=self.work/'source';shutil.copytree(self.source,isolated)
        built=self.work/'new';code,payload=invoke('model','build',isolated/'models/lantern.json','--source-root',isolated,'--out',built)
        self.assertEqual(code,0,payload);shutil.rmtree(isolated)
        code,payload=invoke('model','inspect',built);self.assertEqual(code,0,payload)
        for name,sha in studio.read(built/'model-package.json')['files'].items():self.assertEqual(digest(built/'source'/name),sha)

    def test_preserves_occupied_output(self):
        occupied=self.work/'occupied';occupied.mkdir();(occupied/'sentinel').write_bytes(b'preserve')
        code,_=invoke('model','build',self.definition,'--source-root',self.source,'--out',occupied)
        self.assertNotEqual(code,0);self.assertEqual((occupied/'sentinel').read_bytes(),b'preserve')
        self.assertEqual(list(occupied.iterdir()),[occupied/'sentinel'])

    def test_missing_and_changed_pins(self):
        for label,value in [('changed','0'*64),('missing',None)]:
            with self.subTest(label=label), tempfile.TemporaryDirectory(dir=self.work) as d:
                source=Path(d)/'source';shutil.copytree(self.source,source);p=source/'models/lantern.json';data=studio.read(p)
                if value:data['drawings'][0]['asset']['sha256']=value
                else:data['drawings'][0]['asset']['file']='missing.json'
                studio.write(p,data);code,_=invoke('model','build',p,'--source-root',source,'--out',Path(d)/'out');self.assertNotEqual(code,0)

    def test_unknown_fields_and_cycles_are_not_silently_frozen(self):
        self.rejects(lambda d:d.update(local_cycles=[]),'Unsupported model definition')

    def test_duplicate_ids(self):self.rejects(lambda d:d['parts'].append(copy.deepcopy(d['parts'][0])),'Duplicate part_id')
    def test_unmounted_nonroot(self):self.rejects(lambda d:d['parts'][1].pop('mount'),'nonroot')
    def test_nonpaint_root(self):self.rejects(lambda d:d.update(root_part_id='candle'),'drawing-bearing')
    def test_wrong_registration(self):self.rejects(lambda d:d['parts'][0]['cell_to_local'].__setitem__(4,20),'registration differs')
    def test_wrong_model_pivot(self):self.rejects(lambda d:d['local_frame']['pivot'].__setitem__(0,5),'root pivot differs')
    def test_shear_rejected(self):self.rejects(lambda d:d['parts'][0]['cell_to_local'].__setitem__(2,.2),'Unsupported shear')
    def test_wrong_socket(self):self.rejects(lambda d:d['parts'][1]['mount'].update(socket_id='missing'),'mount socket')
    def test_mount_cycle(self):
        def mutate(d):
            d['sockets'].append({'socket_id':'self','part_path':['front'],'cell_uv':[.5,.5]})
            d['parts'][-1]['mount']={'part_path':['front'],'socket_id':'self'}
        self.rejects(mutate,'Mount cycle')
    def test_competing_controls(self):
        def mutate(d):
            c=copy.deepcopy(d['controls'][-1]);c['control_id']='duplicate-visible';d['controls'].append(c)
        self.rejects(mutate,'Competing channel writers')
    def test_competing_forwarders(self):
        def mutate(d):
            c=copy.deepcopy(d['controls'][0]);c['control_id']='other-source';d['controls'].append(c)
        self.rejects(mutate,'Competing forwarded writers')
    def test_variant_registration(self):
        self.rejects(lambda d:d['drawings'][2]['source_to_local'].__setitem__(4,10),'Incompatible drawing')
    def test_variant_order_census(self):self.rejects(lambda d:d['paint_order'].pop(),'every owned drawing')

    def test_source_and_symlink_escape(self):
        source=self.work/'source';shutil.copytree(self.source,source)
        art=source/'art/housing.png';original=art.read_bytes();art.unlink();external=self.work/'outside.png';external.write_bytes(original);art.symlink_to(external)
        code,payload=invoke('model','build',source/'models/lantern.json','--source-root',source,'--out',self.work/'bad')
        self.assertNotEqual(code,0);self.assertIn('escapes',payload['error']['message'])

    def test_state_writers_and_unknown_overrides(self):
        cases=[{'model_path':[],'control_id':'arbitrary','value':1},{'model_path':[],'control_id':'sway','value':100}, {'model_path':['candle'],'control_id':'flame-on','value':False}]
        for row in cases:
            with self.subTest(row=row):
                state=studio.read(self.source/'rest.json');state['controls']=[row];p=self.work/'state.json';studio.write(p,state)
                code,_=invoke('model','lower',self.package,'--state',p,'--out',self.work/'bad');self.assertNotEqual(code,0);self.assertFalse((self.work/'bad').exists())

    def test_rebuild_geometry_and_atlas(self):
        from tools.asset_tool import build
        for name in ['housing','frame-square','frame-arched','flame']:
            packed=self.package/'source/packs'/name;out=self.work/name;build(packed/'recipe.json',out)
            self.assertEqual(digest(packed/'atlas.png'),digest(out/'atlas.png'))
            before=studio.read(packed/'asset.json');after=studio.read(out/'asset.json')
            for key in ['cell_size','shared_scale','padding','cels']:self.assertEqual(before['registration_mapping'][key],after['registration_mapping'][key])

    def test_public_lower_is_deterministic_and_engine_valid(self):
        for name in ['a','b']:
            code,payload=invoke('model','lower',self.package,'--state',self.source/'rest.json','--out',self.work/name);self.assertEqual(code,0,payload)
        for name in ['scene/scene.json','assets/catalog.json','mapping.json']:
            self.assertEqual((self.work/'a'/name).read_bytes(),(self.work/'b'/name).read_bytes())
        code,payload=invoke('--project',self.work/'a','scene','check');self.assertEqual(code,0,payload)
        mapping=studio.read(self.work/'a/mapping.json');self.assertEqual(len(mapping['mounts']),4)
        self.assertLess(max(m['max_world_corner_error_pixels'] for m in mapping['mounts']),1e-7)

    def test_immutable_package_detects_added_and_modified_sources(self):
        copied=self.work/'package';shutil.copytree(self.package,copied);(copied/'source/extra').write_text('extra')
        code,_=invoke('model','inspect',copied);self.assertNotEqual(code,0)
        (copied/'source/extra').unlink();(copied/'source/art/housing.png').write_bytes(b'changed')
        code,_=invoke('model','inspect',copied);self.assertNotEqual(code,0)

    def test_interrupted_materialization_publishes_nothing(self):
        out=self.work/'interrupted'
        with patch('ambiance_studio.model_package.copy_files',side_effect=KeyboardInterrupt):
            code,payload=invoke('model','build',self.definition,'--source-root',self.source,'--out',out)
        self.assertEqual(code,130,payload);self.assertFalse(out.exists())

    def test_concurrent_publisher_is_preserved(self):
        out=self.work/'raced';original=model_package.copy_files
        def race(*args):
            original(*args);out.mkdir();(out/'sentinel').write_bytes(b'other publisher')
        with patch('ambiance_studio.model_package.copy_files',side_effect=race):
            code,payload=invoke('model','build',self.definition,'--source-root',self.source,'--out',out)
        self.assertNotEqual(code,0,payload)
        self.assertEqual(list(out.iterdir()),[out/'sentinel']);self.assertEqual((out/'sentinel').read_bytes(),b'other publisher')

    def test_same_version_different_bytes_in_closure_rejects(self):
        source,path=self.altered(lambda d:None)
        second=source/'models/candle-other.json';candle=studio.read(source/'models/candle.json');candle['name']='changed bytes';studio.write(second,candle)
        lantern=studio.read(path);part=copy.deepcopy(next(p for p in lantern['parts'] if p['part_id']=='candle'));part['part_id']='other';part['definition'].update(file='candle-other.json',sha256=digest(second));lantern['parts'].append(part)
        lantern['paint_order'] += [['other','wax'],['other','flame']];studio.write(path,lantern)
        code,payload=invoke('model','build',path,'--source-root',source,'--out',self.work/'bad')
        self.assertNotEqual(code,0);self.assertIn('Changed bytes under model version',payload['error']['message'])

    def test_repeated_identical_nested_definition_has_distinct_tuples(self):
        def mutate(d):
            part=copy.deepcopy(next(p for p in d['parts'] if p['part_id']=='candle'));part['part_id']='other';d['parts'].append(part);d['paint_order'] += [['other','wax'],['other','flame']]
        source,path=self.altered(mutate);out=self.work/'repeated'
        code,payload=invoke('model','build',path,'--source-root',source,'--out',out);self.assertEqual(code,0,payload)
        code,payload=invoke('model','inspect',out);self.assertEqual(code,0,payload)
        members=payload['data']['members'];self.assertEqual(len(members),7);self.assertEqual(len({m['layer_id'] for m in members}),7)

    def test_proof_masks_stale_state_and_portable_entry(self):
        out=self.work/'proof';recipe=self.source/'proof.json'
        code,payload=invoke('model','proof',self.package,'--recipe',recipe,'--out',out);self.assertEqual(code,0,payload)
        report=studio.read(out/'model-proof.json');self.assertEqual(len(report['samples']),10)
        by_id={s['pose_id']:s for s in report['samples']}
        rest=by_id['square-rest'];hidden=by_id['square-hidden'];unlit=by_id['square-unlit']
        self.assertGreater(rest['roles']['glass']['partial_alpha_pixels'],0)
        self.assertEqual(len(rest['roles']['solid']['included_leaves']),3)
        self.assertEqual(hidden['roles']['composite']['covered_pixels'],0)
        self.assertEqual(unlit['roles']['flame']['covered_pixels'],0)
        self.assertNotEqual(rest['roles']['composite']['rgba']['sha256'],by_id['arched-rest']['roles']['composite']['rgba']['sha256'])
        for sample in report['samples']:self.assertTrue(sample['rgba_endpoint_exact'])
        code,payload=invoke('model','check',out,'--package',self.package,'--recipe',recipe);self.assertEqual(code,0,payload)
        entry=self.work/'entry';code,payload=invoke('model','admit',self.package,'--proof',out,'--recipe',recipe,'--out',entry);self.assertEqual(code,0,payload)
        shutil.rmtree(out)
        code,payload=invoke('model','check',entry/'proof','--package',entry/'package','--recipe',entry/'proof-recipe.json');self.assertEqual(code,0,payload)
        changed=self.work/'changed.json';data=studio.read(recipe);data['states'][0]['controls']=[{'model_path':[],'control_id':'sway','value':.02}];studio.write(changed,data)
        code,payload=invoke('model','check',entry/'proof','--package',entry/'package','--recipe',changed);self.assertNotEqual(code,0);self.assertIn('Stale',payload['error']['message'])
        (entry/'proof/square-rest/composite.png').write_bytes(b'changed')
        code,payload=invoke('model','check',entry/'proof','--package',entry/'package','--recipe',recipe);self.assertNotEqual(code,0)

if __name__=='__main__':unittest.main()
