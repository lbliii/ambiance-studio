"""Saved framing authoring, capture integrity and legacy raster compatibility."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import studio
from ambiance_studio import cli, rendering, revisions, scene_runtime, views, production
from ambiance_studio.errors import CommandError


class ViewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.project = self.root/'dual'
        cli.init_project(self.project, None, 'Dual fixture', 'blank', 'dual')
        self.scene_path = self.project/'scene/scene.json'
        self.scene = studio.read(self.scene_path)
        self.framing = self.root/'framing.json'; studio.write(self.framing, self.scene['framing'])

    def run_cli(self, *args):
        result = subprocess.run([sys.executable, str(ROOT/'ambiance'), '--project', str(self.project), *map(str, args)], capture_output=True, text=True)
        return result.returncode, json.loads(result.stdout)

    def add_art(self):
        file = self.project/'assets/pattern.png'
        image = Image.new('RGB', (32, 32))
        image.putdata([((x*17)%256,(y*29)%256,(x*13+y*7)%256) for y in range(32) for x in range(32)]); image.save(file)
        studio.write(self.project/'assets/catalog.json', {'version':1,'assets':[{'id':'paint','kind':'plate','file':'assets/pattern.png','width':32,'height':32,'sha256':studio.digest(file)}]})
        code, result = self.run_cli('scene', 'add', 'paint', '--id', 'plate', '--width', '1')
        self.assertEqual(code, 0, result)

    def test_dual_init_and_legacy_defaults(self):
        self.assertEqual(self.scene['canvas']['width'], 1920)
        info = views.inspect(self.project)
        self.assertEqual(set(info['views']), {'authored','portrait','landscape'})
        self.assertEqual(info['views']['portrait']['output'], {'width':1080,'height':1920})
        self.assertEqual(len(info['views']['portrait']['view_sha256']), 64)
        self.assertTrue(views.project_summary(self.project)['ok'])
        blank = self.root/'legacy'; cli.init_project(blank, None, None, 'blank')
        self.assertNotIn('framing', studio.read(blank/'scene/scene.json'))
        self.assertEqual(studio.read(blank/'scene/scene.json')['canvas']['width'],1080)
        self.assertEqual(list(views.inspect(blank)['views']), ['authored'])
        invalid = self.root/'invalid'
        with self.assertRaisesRegex(CommandError, 'blank template'):
            cli.init_project(invalid, None, None, 'last-lantern', 'dual')
        self.assertFalse(invalid.exists())

    def test_dry_run_stale_edit_and_history_restore(self):
        before = self.scene_path.read_bytes(); expected = hashlib.sha256(before).hexdigest()
        framing = copy.deepcopy(self.scene['framing']); framing['views']['portrait']['rect_scene_px'][0] = 300
        studio.write(self.framing, framing)
        code, dry = self.run_cli('view','apply',self.framing,'--dry-run','--expect-sha256',expected)
        self.assertEqual(code,0,dry); self.assertEqual(self.scene_path.read_bytes(),before)
        self.assertFalse((self.project/'.ambiance/scene-history').exists())
        code, stale = self.run_cli('view','apply',self.framing,'--expect-sha256','0'*64)
        self.assertEqual(code,2); self.assertEqual(stale['error']['code'],'stale_input')
        code, saved = self.run_cli('view','apply',self.framing,'--expect-sha256',expected)
        self.assertEqual(code,0,saved)
        self.assertEqual(studio.read(self.scene_path)['canvas'],self.scene['canvas'])
        self.assertEqual((self.project/'.ambiance/scene-history'/f'{expected}.json').read_bytes(),before)
        code, restored = self.run_cli('scene','restore',expected)
        self.assertEqual(code,0,restored); self.assertEqual(studio.read(self.scene_path),json.loads(before))

    def test_invalid_and_duplicate_fields_preserve_source(self):
        before = self.scene_path.read_bytes()
        for text in ['{"version":1,"views":{},"views":{}}', '{"version":1,"views":{"authored":{}}}', '{"version":1,"views":{},"typo":true}']:
            self.framing.write_text(text)
            code, result = self.run_cli('view','apply',self.framing)
            self.assertEqual(code,2,result); self.assertEqual(self.scene_path.read_bytes(),before)
        self.scene_path.write_text('{"version":1,"version":1}')
        code, result = self.run_cli('view','inspect')
        self.assertEqual(code,2); self.assertIn('Duplicate JSON field',result['error']['message'])

    def test_framing_file_change_during_validation_is_rejected(self):
        original = scene_runtime.scene_bridge; before = self.scene_path.read_bytes()
        def changed(*args):
            result = original(*args); self.framing.write_text(self.framing.read_text()+' '); return result
        args = cli.parser().parse_args(['--project',str(self.project),'view','apply',str(self.framing)])
        with patch.object(scene_runtime,'scene_bridge',side_effect=changed), self.assertRaisesRegex(ValueError,'changed'):
            cli.run(args)
        self.assertEqual(self.scene_path.read_bytes(),before)

    def test_view_checks_report_empty_scene_and_configuration_mismatch(self):
        report = self.root/'check.json'
        code, result = self.run_cli('view','check','--out',report)
        self.assertEqual(code,1,result); self.assertEqual(studio.read(report),result)
        self.assertFalse(result['data']['views']['portrait']['coverage_checked'])
        self.add_art()
        code, result = self.run_cli('project','check'); self.assertEqual(code,0,result)
        settings = studio.read(self.project/'project.json'); settings['intended_views']=['missing']; studio.write(self.project/'project.json',settings)
        code, result = self.run_cli('project','check'); self.assertEqual(code,1,result)
        self.assertIn('missing', result['data']['framing']['errors'][0])
        code, result = self.run_cli('scene','check'); self.assertEqual(code,0,result)

    def test_captured_view_does_not_follow_working_edits(self):
        self.add_art()
        selection = self.project/'selection.json'
        studio.write(selection, {'format':'ambiance-revision-selection','schema_version':1,'scene':'scene/scene.json','catalog':'assets/catalog.json'})
        revisions.capture(self.project,'v1',selection)
        before = views.inspect(self.project,'portrait','v1')
        scene = studio.read(self.scene_path); scene['framing']['views']['portrait']['rect_scene_px'][0]=300; studio.write(self.scene_path,scene)
        after = views.inspect(self.project,'portrait','v1')
        self.assertEqual(before['views'],after['views'])
        self.assertNotEqual(after['views'],views.inspect(self.project,'portrait')['views'])

    def test_library_overview_survives_invalid_working_framing(self):
        self.scene['framing']['views']['portrait']['rect_scene_px'][0]=-1
        studio.write(self.scene_path,self.scene)
        result=production.overview(self.project,'fixture','http://127.0.0.1:8783')
        self.assertTrue(result['ok']); self.assertFalse(result['framing']['ok'])

    @unittest.skipUnless(rendering.capabilities()['frame_render'], 'Requires Node Canvas')
    def test_existing_raster_resize_is_unchanged_by_framing(self):
        self.add_art()
        source = self.scene_path.read_bytes()
        def render(name):
            args=cli.parser().parse_args(['--project',str(self.project),'render','frame','--width','64','--supersample','2','--out',str(self.root/name)])
            return cli.run(args)
        with_views=render('framed')
        self.assertEqual(self.scene_path.read_bytes(),source)
        scene=studio.read(self.scene_path); del scene['framing']; studio.write(self.scene_path,scene)
        legacy=render('legacy')
        self.assertEqual(with_views['output_sha256'],legacy['output_sha256'])
        self.assertIn('views_module_sha256',with_views)


if __name__ == '__main__':
    unittest.main()
