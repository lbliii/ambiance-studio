import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from ambiance_studio import generation_ledger as g, asset_prep as p


class GenerationLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name).resolve()
        (self.root/'plans').mkdir();Image.new('RGB',(9,7),'blue').save(self.root/'source.png')
        Image.new('RGBA',(9,7),(255,0,0,90)).save(self.root/'returned.png')
        self.request={'format':g.FORMAT,'version':1,'local_request_id':'take-1','provider':None,'prompt':'Existing tool-returned fixture',
                      'references':[{'file':'source.png','sha256':p.sha((self.root/'source.png').read_bytes())}],
                      'settings':{},'authorized_scope':{'source':'local fake receipt test; no generation','cost_limit':None,'currency':None}}
        self.file=self.root/'request.json';p.write(self.file,self.request)
        self.output={'file':'returned.png','sha256':p.sha((self.root/'returned.png').read_bytes()),'provider_output_id':None}
    def event(self,id,state,**kw):
        file=self.root/'event.json';p.write(file,{'version':1,'event_id':id,'state':state,**kw});return g.reconcile(self.root,'take-1',file)
    def test_uncertain_timeout_never_becomes_new_submission(self):
        g.record(self.root,self.file);self.event('sent','submitted');row=self.event('timeout','uncertain')
        self.assertEqual(row['status'],'uncertain');self.assertIn('Reconcile',row['next_action'])
        with self.assertRaisesRegex(ValueError,'resubmitting'):self.event('retry','submitted')
        self.request['local_request_id']='take-2';p.write(self.file,self.request)
        with self.assertRaisesRegex(ValueError,'fingerprint'):g.record(self.root,self.file)
    def test_direct_tool_output_duplicate_receipts_and_resumed_selection(self):
        g.record(self.root,self.file);first=self.event('returned','retrieved',outputs=[self.output])
        self.assertIsNone(g.find(g.load(self.root),'take-1')['provider_request_id'])
        self.assertTrue(self.event('returned','retrieved',outputs=[self.output])['cached'])
        self.event('second-return-card','retrieved',outputs=[self.output]);self.assertEqual(len(g.find(g.load(self.root),'take-1')['outputs']),1)
        (self.root/'returned.png').unlink()
        selected=self.event('select','selected',selected_output_sha256=self.output['sha256'])
        self.assertTrue((self.root/selected['selected_output']['file']).is_file())
        self.assertTrue(self.event('select','selected',selected_output_sha256=self.output['sha256'])['cached'])
        self.assertIn('reported_cost',selected['unknowns']);self.assertFalse(selected['submits_requests'])
    def test_changed_source_and_changed_event_fail_without_ledger_change(self):
        g.record(self.root,self.file);self.event('returned','retrieved',outputs=[self.output]);before=g.ledger_path(self.root).read_bytes()
        with self.assertRaisesRegex(ValueError,'different content'):self.event('returned','retrieved',outputs=[self.output],note='different')
        self.assertEqual(before,g.ledger_path(self.root).read_bytes())
        (self.root/'source.png').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'Source identity changed'):self.event('select','selected',selected_output_sha256=self.output['sha256'])
        self.assertEqual(before,g.ledger_path(self.root).read_bytes());self.assertFalse(g.summary(self.root,g.find(g.load(self.root),'take-1'))['ok'])
    def test_interruption_after_snapshot_reuses_bytes_without_duplicate_selection(self):
        g.record(self.root,self.file)
        with patch.object(g.studio,'write',side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):self.event('retrieve','retrieved',outputs=[self.output])
        self.assertEqual(g.find(g.load(self.root),'take-1')['status'],'pending')
        self.assertEqual(len(list((self.root/'assets/raw/generation/take-1').glob('*'))),1)
        result=self.event('retrieve','retrieved',outputs=[self.output]);self.assertEqual(result['event_count'],1)
    def test_request_idempotence_legacy_preservation_and_validation(self):
        p.write(g.ledger_path(self.root),{'version':1,'requests':[{'local_request_id':'legacy','status':'unknown','notes':'preserve'}]})
        g.record(self.root,self.file);self.assertTrue(g.record(self.root,self.file)['cached'])
        self.assertEqual(g.load(self.root)['requests'][0]['notes'],'preserve')
        for change in [{'estimated_cost':True},{'provider':False},{'references':[{'file':'../escape','sha256':'a'*64}]}]:
            bad=copy.deepcopy(self.request);bad.update(change);p.write(self.file,bad)
            with self.assertRaises(ValueError):g.record(self.root,self.file)
    def test_invalid_output_and_foreign_selection_do_not_advance(self):
        g.record(self.root,self.file)
        with self.assertRaises(ValueError):self.event('bad','retrieved',outputs=[{**self.output,'sha256':'a'*64}])
        self.assertEqual(g.find(g.load(self.root),'take-1')['status'],'pending')
        self.event('good','retrieved',outputs=[self.output])
        with self.assertRaisesRegex(ValueError,'already retrieved'):self.event('bad-select','selected',selected_output_sha256='a'*64)


if __name__=='__main__':unittest.main()
