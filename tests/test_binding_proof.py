"""Replay the binding example entirely through the public production CLI."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]


class BindingProof(unittest.TestCase):
    def test_source_receiver_proof_captures_both_views_and_module_closure(self):
        with tempfile.TemporaryDirectory() as temp:
            project=Path(temp)/'fixture'
            result=subprocess.run(['node',str(ROOT/'examples/bindings/create_fixture.mjs'),str(project)],cwd=ROOT,text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            report=json.loads((project/'render/paired/render-report.json').read_text())
            self.assertEqual(set(report['views']),{'portrait','landscape'});self.assertTrue(report['rgba_endpoint_exact'])
            self.assertIn('bindings_engine_sha256',report)
            for name in ['portrait','landscape']:
                self.assertTrue(report['views'][name]['rgba_endpoint_exact'])
            # Native full-stage samples retain actual source/receiver low/high/off.
            rgb=[]
            for time in [0,1,2]:
                with Image.open(project/f'render/state-{time}/frame.png') as im:rgb.append(im.getpixel((60,55))[0])
            self.assertGreater(rgb[1],rgb[0]);self.assertGreater(rgb[0],rgb[2]);self.assertEqual(rgb[2],32)
            work=json.loads((project/'render/look/workbench.json').read_text())
            self.assertIn('modules/bindings.mjs',{m['file'] for m in work['modules']})
            packet=json.loads((project/'render/browser-parity/packet.json').read_text())
            self.assertEqual(len(packet['samples']),4)
            package=json.loads((project/'looks/painted-floor/look.json').read_text())
            self.assertEqual(len(package['scene_bindings']['links']),3)


if __name__=='__main__':unittest.main()
