import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from ambiance_studio.preview import handler_for

def run(*args,cwd=None):
    p=subprocess.run([sys.executable,str(ROOT/'ambiance'),*map(str,args)],capture_output=True,text=True,cwd=cwd)
    return p.returncode,json.loads(p.stdout)

class CLITests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.project=self.root/'film'
        code,data=run('project','init',self.project,'--template','last-lantern')
        self.assertEqual(code,0,data)
        self.scene=self.project/'scene/scene.json'
    def cli(self,*args):return run('--project',self.project,*args)
    def test_project_template_and_checks_use_local_catalog(self):
        code,data=self.cli('project','check');self.assertEqual(code,0,data)
        self.assertEqual(data['data']['state']['frame_count'],480)
        self.assertEqual(data['data']['state']['max_attachment_error_pixels'],0)
        code,data=self.cli('project','status');self.assertEqual(code,0)
        self.assertFalse(data['data']['release_ready'])
        self.assertTrue(all(g['state']!='passed' for g in data['data']['gates'].values()))
    def test_invalid_edit_never_replaces_scene(self):
        before=self.scene.read_bytes()
        code,data=self.cli('scene','set','cottage','--scale','0');self.assertEqual(code,2)
        self.assertEqual(self.scene.read_bytes(),before)
        self.assertFalse((self.project/'.ambiance/write.lock').exists())
    def test_edit_sample_history_restore_from_another_directory(self):
        original=self.scene.read_bytes();digest=hashlib.sha256(original).hexdigest()
        code,data=self.cli('scene','set','cottage','--scale','1.3','--rotation-deg','9');self.assertEqual(code,0,data)
        self.assertEqual(data['data']['previous_sha256'],digest)
        code,data=run('scene','sample','--time','2',cwd=self.project/'scene');self.assertEqual(code,0,data)
        states={s['id']:s for s in data['data']}
        self.assertEqual(states['chimney-smoke']['matrix'][4:6],states['cottage']['sockets']['chimney'])
        code,data=self.cli('scene','restore',digest);self.assertEqual(code,0,data)
        self.assertEqual(json.loads(self.scene.read_text()),json.loads(original))
    def test_missing_socket_and_cycle_rejected(self):
        before=self.scene.read_bytes()
        code,data=self.cli('scene','attach','cottage','--to','chimney-smoke','--socket','absent');self.assertEqual(code,2)
        self.assertEqual(self.scene.read_bytes(),before)
        code,data=self.cli('scene','socket','chimney-smoke','tip','--u','.5','--v','0');self.assertEqual(code,0,data)
        before=self.scene.read_bytes()
        code,data=self.cli('scene','attach','cottage','--to','chimney-smoke','--socket','tip');self.assertEqual(code,2)
        self.assertIn('cycle',data['error']['message'].lower());self.assertEqual(self.scene.read_bytes(),before)
    def test_asset_tamper_causes_nonzero_check(self):
        path=self.project/'assets/lantern/sky.png';path.write_bytes(path.read_bytes()+b'changed')
        code,data=self.cli('project','check');self.assertEqual(code,1);self.assertFalse(data['ok'])
    def test_blank_project_requires_assets_before_preview(self):
        blank=self.root/'blank';code,data=run('project','init',blank);self.assertEqual(code,0)
        code,data=run('--project',blank,'project','check');self.assertEqual(code,1)
        self.assertIn('Scene has no layers',str(data))
    def test_existing_destination_and_lock_protected(self):
        code,data=run('project','init',self.project);self.assertEqual(code,2)
        (self.project/'.ambiance').mkdir();(self.project/'.ambiance/write.lock').write_text('test writer')
        before=self.scene.read_bytes();code,data=self.cli('scene','set','cottage','--x','.2')
        self.assertEqual(code,2);self.assertEqual(data['error']['code'],'project_locked');self.assertEqual(before,self.scene.read_bytes())
    def test_project_config_cannot_escape(self):
        config=self.project/'ambiance-project.json';data=json.loads(config.read_text());data['catalog']='../outside.json';config.write_text(json.dumps(data))
        code,data=self.cli('asset','list');self.assertEqual(code,2);self.assertIn('inside',data['error']['message'])
    def test_scene_add_uses_catalog_pivot(self):
        code,data=self.cli('scene','add','smoke-registered-v1','--id','smoke-copy');self.assertEqual(code,0,data)
        s=json.loads(self.scene.read_text())['layers'][-1];self.assertEqual(s['anchor'],[.5,.96875])
        code,data=self.cli('scene','attach','smoke-copy','--to','cottage','--socket','chimney');self.assertEqual(code,0,data)
    def test_review_draft_uses_real_gate_and_does_not_pass(self):
        draft=self.project/'review-drafts/intent.json';code,data=self.cli('review','draft','intent','--out',draft);self.assertEqual(code,0,data)
        self.assertTrue(draft.is_file());self.assertTrue(all(c['result']=='not-run' for c in data['data']['review']['checks']))
        code,data=self.cli('review','record',draft);self.assertEqual(code,2)
    def test_preview_mounts_only_editor_and_selected_assets(self):
        class Socket:
            def __init__(self,path):self.request=io.BytesIO(f'GET {path} HTTP/1.0\r\n\r\n'.encode());self.response=bytearray()
            def makefile(self,*args):return self.request
            def sendall(self,data):self.response.extend(data)
        Handler=handler_for(ROOT,self.project);Handler.log_message=lambda *args:None
        def request(path):
            sock=Socket(path);Handler(sock,('127.0.0.1',1),object());return bytes(sock.response)
        self.assertIn(b'200 OK',request('/api/config'))
        self.assertIn(b'/media/sky',request('/api/catalog'))
        self.assertIn(b'200 OK',request('/media/sky'))
        self.assertIn(b'404 Not Found',request('/.git/config'))
        self.assertIn(b'404 Not Found',request('/editor/../studio.py'))
        self.assertIn(b'404 Not Found',request('/archive/session/outputs/README.md'))

class CLIEntryTests(unittest.TestCase):
    def test_unknown_command_is_json_and_nonzero(self):
        code,data=run('not-a-command');self.assertEqual(code,2);self.assertEqual(data['error']['code'],'invalid_input')
    def test_missing_project_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:code,data=run('scene','inspect',cwd=tmp)
        self.assertEqual(code,2);self.assertIn('--project',data['error']['message'])

if __name__=='__main__':unittest.main(verbosity=2)
