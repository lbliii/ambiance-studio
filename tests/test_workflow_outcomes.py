"""Outcome guidance cannot change native results, ownership or retry semantics."""
import argparse
import contextlib
import io
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import studio
from ambiance_studio import cli, workflow, workflow_outcomes as outcomes, production_coverage
from ambiance_studio.command_output import Output
from ambiance_studio.errors import CommandError
from test_cli_contract import invoke
from test_production_coverage import fixture


class OutcomeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.p=fixture(self.root)
    def run_cli(self,*argv,mode='auto'):
        return invoke(['--project',self.p,'--guidance',mode,*argv])

    def test_off_is_exact_legacy_envelope_and_native_report_has_no_guidance(self):
        native=invoke(['--project',self.p,'scene','check'])
        self.assertEqual(native,self.run_cli('scene','check',mode='off'))
        out=self.root/'check.json';code,data=self.run_cli('scene','check','--out',out)
        self.assertEqual(code,native[0]);self.assertEqual(data['data'],native[1]['data'])
        saved=studio.read(out);self.assertNotIn('guidance',saved)
        self.assertEqual(saved,{k:v for k,v in data.items() if k!='guidance'})
        self.assertEqual(data['guidance']['output_ownership'],'result-envelope')

    def test_auto_does_not_assess_coverage_read_catalog_or_scan_library(self):
        with patch.object(workflow,'inspect',side_effect=AssertionError('Full workflow assessment')), \
                patch.object(production_coverage,'assess',side_effect=AssertionError('Coverage assessment')), \
                patch('ambiance_studio.workflow_catalog.load',side_effect=AssertionError('Catalog read')), \
                patch('ambiance_studio.registry.projects',side_effect=AssertionError('Library scan')):
            code,data=self.run_cli('scene','check')
        self.assertEqual(code,0,data);self.assertEqual(data['guidance']['assessment'],'operation-local')
        self.assertNotEqual(data['guidance'].get('state'),'unavailable')

    def test_real_successful_scene_mutation_survives_full_guidance_failure(self):
        # The native scene transaction does not read project.json. The requested
        # full workflow assessment does. No production fault-injection flag needed.
        settings=studio.read(self.p/'project.json');settings['intended_views']='invalid selector fixture'
        studio.write(self.p/'project.json',settings)
        (self.p/'plans/production-plan.json').write_text('{ unavailable intent for guidance only')
        batch={'version':1,'operations':[{'op':'set','layer':'plate','values':{'x':0.4}}]}
        studio.write(self.p/'change.json',batch)
        before=studio.digest(self.p/'scene/scene.json')
        code,data=self.run_cli('scene','apply',self.p/'change.json',mode='full')
        self.assertEqual(code,0,data);self.assertTrue(data['ok'])
        self.assertNotEqual(before,studio.digest(self.p/'scene/scene.json'))
        self.assertEqual(data['data']['sha256'],studio.digest(self.p/'scene/scene.json'))
        self.assertEqual(data['guidance']['diagnostic']['code'],'guidance_unavailable')
        self.assertTrue((self.p/f'.ambiance/scene-history/{before}.json').is_file())

    def test_guidance_exceptions_and_nonserializable_values_preserve_success(self):
        for failure in [RuntimeError('adapter failed'),KeyboardInterrupt(),SystemExit(1)]:
            with self.subTest(failure=failure),patch.object(outcomes,'local',side_effect=failure):
                code,data=self.run_cli('scene','check')
            self.assertEqual(code,0,data);self.assertTrue(data['ok'])
            self.assertEqual(data['guidance']['state'],'unavailable')
        with patch.object(outcomes,'local',return_value={'bad':object()}):
            code,data=self.run_cli('scene','check')
        self.assertEqual(code,0);self.assertEqual(data['guidance']['state'],'unavailable')

    def test_structured_failure_mapping_preserves_native_error_exit_and_report(self):
        out=self.root/'error.json'
        for error,exit_code in [(CommandError('source changed','stale_input',2),2),
                                (CommandError('Native diagnostic','new_native_error',7),7),
                                (KeyboardInterrupt(),130)]:
            with self.subTest(error=error),patch.object(cli,'run',side_effect=error):
                code,data=self.run_cli('scene','check','--out',out)
            self.assertEqual(code,exit_code);self.assertFalse(out.exists())
            self.assertEqual(data['guidance']['operation_ok'],False)
            self.assertEqual(data['guidance']['recovery']['code'],data['error']['code'])
            self.assertEqual(data['guidance']['recovery']['mapped'],data['error']['code'] in outcomes.RECOVERY)
            if isinstance(error,CommandError):self.assertEqual(data['error'],{'code':error.code,'message':str(error)})

    def test_native_non_ok_result_remains_failure_without_guessed_cause(self):
        with patch.object(cli,'run',return_value={'ok':False,'errors':['opaque native finding']}):
            code,data=self.run_cli('scene','check')
        self.assertEqual(code,1);self.assertFalse(data['guidance']['recovery']['mapped'])
        self.assertEqual(data['data']['errors'],['opaque native finding'])

    def test_full_has_fresh_exact_scope_and_bounded_size(self):
        code,data=self.run_cli('scene','check',mode='full')
        self.assertEqual(code,0,data)
        guide=data['guidance'];self.assertTrue(guide['freshness']['reassessed'])
        self.assertEqual(guide['reassessment']['selection']['subject'],'working')
        self.assertEqual(guide['freshness']['sha256'],guide['reassessment']['assessment']['sha256'])
        self.assertLessEqual(len(json.dumps(guide).encode()),16384)

    def test_full_legacy_review_uses_actual_native_scope(self):
        value=studio.review_template(self.p,'intent');value['recorder']='Engineering unperformed review fixture'
        studio.write(self.p/'review.json',value)
        code,data=self.run_cli('review','record',self.p/'review.json',mode='full')
        self.assertEqual(code,0,data)
        self.assertEqual(data['data']['subject']['mode'],'legacy-path-watches')
        self.assertEqual(data['guidance']['reassessment']['selection']['subject'],'working')
        self.assertTrue(data['guidance']['freshness']['reassessed'])

    def test_unsupported_route_and_no_project_do_not_infer_gate_criteria(self):
        code,data=self.run_cli('scene','inspect')
        self.assertEqual(code,0);self.assertFalse(data['guidance']['supported'])
        self.assertEqual(data['guidance']['inspect_argv'][-3:],['scene','inspect','--help'])
        args=cli.parser().parse_args(['--guidance','auto','asset','build','recipe.json','--out','pack'])
        payload={'ok':True,'data':{'cached':False,'pack':'pack'}}
        guide=outcomes.attach(args,payload,Output.ARTIFACT)['guidance']
        self.assertNotIn('--project',guide['next_argv']);self.assertNotIn('remaining',guide)
        self.assertEqual(guide['output_ownership'],'artifact-directory')

    def test_all_supported_auto_routes_preserve_payload_and_have_parseable_continuations(self):
        routes=[['project','init',str(self.root/'new')],['asset','build','r.json','--out','pack'],
                ['asset','proof','paint','--out','proof'],['scene','apply','batch.json'],['scene','check'],
                ['review','record','review.json'],['iteration','init','input.json','--out','bundle'],
                ['iteration','run','iteration.json','--by','Engineering fixture'],
                ['delivery','present','pair','--by','Engineering fixture']]
        for route in routes:
            with self.subTest(route=route):
                args=cli.parser().parse_args(['--project',str(self.p),'--guidance','auto',*route])
                payload={'ok':True,'schema_version':1,'data':{'project':str(self.p),'run':{'id':'run'},'selection':{'delivery':'pair'}}}
                before=copy.deepcopy(payload);guide=outcomes.attach(args,payload,None)['guidance']
                self.assertEqual(payload,before);self.assertTrue(guide['supported'])
                argv=guide.get('next_argv',guide.get('inspect_argv'))
                if '--help' in argv:
                    with contextlib.redirect_stdout(io.StringIO()),self.assertRaises(SystemExit) as done:
                        cli.parser().parse_args(argv[1:])
                    self.assertEqual(done.exception.code,0)
                else:cli.parser().parse_args(argv[1:])

    def test_global_option_does_not_reach_native_scene_namespace(self):
        from ambiance_studio import scene_commands
        args=cli.parser().parse_args(['--project',str(self.p),'--guidance','auto','scene','set','plate','--x','0.25'])
        with patch.object(scene_commands,'run',return_value={'ok':True}) as handler:
            cli.run(args)
        self.assertNotIn('guidance',vars(handler.call_args.args[0]));self.assertEqual(args.guidance,'auto')

    def test_dry_run_success_never_claims_completed_mutation(self):
        studio.write(self.p/'change.json',{'version':1,'operations':[{'op':'set','layer':'plate','values':{'x':0.25}}]})
        before=studio.digest(self.p/'scene/scene.json')
        code,data=self.run_cli('scene','apply',self.p/'change.json','--dry-run')
        self.assertEqual(code,0,data);self.assertIn('dry run',data['guidance']['summary'])
        self.assertEqual(before,studio.digest(self.p/'scene/scene.json'))


if __name__=='__main__':unittest.main()
