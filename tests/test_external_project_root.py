"""External default project roots remain discoverable without registration."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


class ExternalProjectRootTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.home=self.root/'home';self.home.mkdir()
        self.cwd=self.root/'unrelated-checkout';self.cwd.mkdir()
        self.env=os.environ.copy()
        self.env.pop('AMBIANCE_PROJECTS_DIR',None)
        self.env['HOME']=str(self.home)
        self.env['AMBIANCE_REGISTRY']=str(self.home/'.ambiance-studio/registry.json')

    def cli(self,*args):
        return subprocess.run([sys.executable,str(ROOT/'ambiance'),*map(str,args)],cwd=self.cwd,
                              env=self.env,capture_output=True,text=True)

    def test_title_only_init_uses_home_default_and_slug_resolves_without_registry_write(self):
        init=self.cli('project','init','--title','  Autumn Library  ')
        self.assertEqual(init.returncode,0,init.stdout+init.stderr)
        created=json.loads(init.stdout)['data']['project']
        expected=self.home/'Ambiance Projects'/'autumn-library'
        self.assertEqual(Path(created),expected.resolve())
        self.assertTrue((expected/'ambiance-project.json').is_file())

        listing=self.cli('project','list')
        self.assertEqual(listing.returncode,0,listing.stdout+listing.stderr)
        project=next(p for p in json.loads(listing.stdout)['data']['projects'] if p['id']=='autumn-library')
        self.assertEqual(project['path'],str(expected.resolve()))
        self.assertFalse(project['registered'])

        status=self.cli('--project','autumn-library','project','status')
        self.assertEqual(status.returncode,0,status.stdout+status.stderr)
        self.assertEqual(json.loads(status.stdout)['data']['project'],'autumn-library')
        self.assertFalse(Path(self.env['AMBIANCE_REGISTRY']).exists())

    def test_environment_override_is_used_for_creation_and_discovery(self):
        override=self.root/'separate projects root'
        self.env['AMBIANCE_PROJECTS_DIR']=str(override)
        init=self.cli('project','init','--title','Crème & Snow')
        self.assertEqual(init.returncode,0,init.stdout+init.stderr)
        expected=override/'creme-snow'
        self.assertTrue((expected/'ambiance-project.json').is_file())
        self.assertFalse((self.home/'Ambiance Projects'/'creme-snow').exists())
        listing=self.cli('project','list')
        self.assertEqual(listing.returncode,0,listing.stdout+listing.stderr)
        self.assertEqual(next(p for p in json.loads(listing.stdout)['data']['projects']
                              if p['id']=='creme-snow')['path'],str(expected.resolve()))

    def test_existing_default_path_is_never_overwritten(self):
        first=self.cli('project','init','--title','Autumn Library')
        self.assertEqual(first.returncode,0,first.stdout+first.stderr)
        project=self.home/'Ambiance Projects'/'autumn-library'
        scene=project/'scene/scene.json';before=scene.read_bytes()
        again=self.cli('project','init','--title','Autumn Library')
        self.assertEqual(again.returncode,2,again.stdout+again.stderr)
        self.assertIn('already exists',json.loads(again.stdout)['error']['message'])
        self.assertEqual(scene.read_bytes(),before)

    def test_default_slug_refuses_registry_collision_without_mutating_registry(self):
        elsewhere=self.root/'elsewhere'/'autumn-library'
        explicit=self.cli('project','init',elsewhere,'--title','Existing Film')
        self.assertEqual(explicit.returncode,0,explicit.stdout+explicit.stderr)
        registered=self.cli('studio','register',elsewhere,'--id','autumn-library')
        self.assertEqual(registered.returncode,0,registered.stdout+registered.stderr)
        registry=Path(self.env['AMBIANCE_REGISTRY']);before=registry.read_bytes()

        collision=self.cli('project','init','--title','Autumn Library')
        self.assertEqual(collision.returncode,2,collision.stdout+collision.stderr)
        self.assertIn('already registered or discoverable',json.loads(collision.stdout)['error']['message'])
        self.assertEqual(registry.read_bytes(),before)
        self.assertFalse((self.home/'Ambiance Projects'/'autumn-library').exists())

    def test_default_slug_refuses_unregistered_checkout_collision(self):
        from ambiance_studio import project_commands
        from ambiance_studio.errors import CommandError
        source_root=self.root/'tool-checkout'
        legacy=source_root/'projects'/'autumn-library'
        created=project_commands.init_project(legacy,None,'Legacy location','blank')
        self.assertEqual(Path(created['project']),legacy.resolve())
        with self.assertRaisesRegex(CommandError,'already registered or discoverable'):
            project_commands.init_project(None,None,'Autumn Library','blank',root=source_root)
        self.assertFalse((self.home/'Ambiance Projects'/'autumn-library').exists())

    def test_omitting_destination_requires_title_but_explicit_path_still_works(self):
        missing=self.cli('project','init')
        self.assertEqual(missing.returncode,2,missing.stdout+missing.stderr)
        self.assertIn('requires a non-empty --title',json.loads(missing.stdout)['error']['message'])
        explicit=self.root/'explicit'/'my-project'
        created=self.cli('project','init',explicit)
        self.assertEqual(created.returncode,0,created.stdout+created.stderr)
        self.assertEqual(Path(json.loads(created.stdout)['data']['project']),explicit.resolve())


if __name__=='__main__':
    unittest.main(verbosity=2)
