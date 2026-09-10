import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from ambiance_studio.preview import look_routes


class LookPreviewTests(unittest.TestCase):
    def test_only_receipt_files_are_served_and_changed_modules_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            def item(name,content):
                path=root/name;path.parent.mkdir(exist_ok=True,parents=True);path.write_bytes(content)
                return {'file':name,'sha256':hashlib.sha256(content).hexdigest()}
            html=item('index.html',b'<main>Proof</main>');css=item('workbench.css',b'body{}');data=item('workbench.json',b'{}')
            mod=item('modules/engine.mjs',b'export const version=1;');item('unrelated.txt',b'private')
            report={'mode':'look-proof','ok':True,'output_sha256':html['sha256'],'samples':[],
                    'workbench':{'sha256':data['sha256'],'stylesheet_sha256':css['sha256'],'modules':[mod],'asset_snapshots':[]}}
            (root/'render-report.json').write_text(json.dumps(report))
            routes=look_routes(root)
            self.assertEqual(routes['/'],b'<main>Proof</main>');self.assertNotIn('/unrelated.txt',routes)
            (root/'modules/engine.mjs').write_text('changed')
            self.assertEqual(routes['/modules/engine.mjs'],b'export const version=1;')
            with self.assertRaisesRegex(ValueError,'changed'):look_routes(root)

    def test_receipt_path_escape_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'artifact';root.mkdir();outside=Path(temp)/'outside';outside.write_text('private')
            for name in ['index.html','workbench.css','workbench.json']:(root/name).write_text('')
            digest=hashlib.sha256(b'').hexdigest()
            report={'mode':'look-proof','ok':True,'output_sha256':digest,'samples':[],
                    'workbench':{'sha256':digest,'stylesheet_sha256':digest,'modules':[{'file':'../outside','sha256':hashlib.sha256(b'private').hexdigest()}],'asset_snapshots':[]}}
            (root/'render-report.json').write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError,'escapes'):look_routes(root)
