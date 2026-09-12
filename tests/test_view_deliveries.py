"""Exact view/role selection, legacy routes, and real resumable two-view production."""
import copy
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import studio
from ambiance_studio import cli, deliveries, production, registry, revisions, revision_reviews
import test_deliveries as legacy_fixtures
import test_view_editions as view_fixtures


class ViewDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.fixture=view_fixtures.ViewEditionTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.p=self.fixture.p
        self.http=legacy_fixtures.DeliveryTests();self.http.project=self.p
        self.http.registry=self.p/'addresses/registry.json';registry.register(self.http.registry,self.p,'film')

    def declaration(self):
        entries=[]
        for view in ['portrait','landscape']:
            self.fixture.synthetic(view,view,role='score')
            entries.append({'view':view,'role':'score','revision':'v1','edition':view})
        return {'format':deliveries.SELECTION,'schema_version':2,'id':'pair','entries':entries,
                'default':{'view':'portrait','role':'score'}}

    def recipe(self,id='pair'):
        return {'format':'ambiance-iteration','schema_version':2,'id':id,'revision':'v1',
                'views':['portrait','landscape'],'long_edge':160,'default':{'view':'portrait','role':'score'},
                'editions':[{'role':'silent'},{'role':'score','audio':'audio/master.wav','repeats':2}]}

    def test_pairs_posters_defaults_and_exact_feedback(self):
        declaration=self.declaration();deliveries.register(self.p,declaration)
        data=deliveries.inspect(self.p,'pair');self.assertEqual(set(data['entries']),{'portrait.score','landscape.score'})
        self.assertNotEqual(data['entries']['portrait.score']['poster'],data['entries']['landscape.score']['poster'])
        self.assertEqual(deliveries.resolve_entry(data,role='score')[0],'portrait.score')
        with self.assertRaisesRegex(ValueError,'unavailable'):deliveries.resolve_entry(data,'landscape','silent')
        with self.assertRaisesRegex(ValueError,'explicit view'):deliveries.feedback(self.p,'pair','score',1,'Test note','Fixture')
        feedback=deliveries.feedback(self.p,'pair','score',1,'Test note','Fixture','landscape')['feedback']
        self.assertEqual(feedback['entry'],'landscape.score');self.assertEqual(feedback['edition'],'landscape')
        self.assertEqual(feedback['movie'],data['entries']['landscape.score']['movie'])
        self.assertEqual(feedback['view_sha256'],data['entries']['landscape.score']['view_sha256'])
        changed=copy.deepcopy(declaration);changed['entries'].append(changed['entries'][0])
        with self.assertRaisesRegex(ValueError,'unique'):deliveries.prepare(self.p,changed)
        changed=copy.deepcopy(declaration);changed['entries'][0]['view']='landscape'
        with self.assertRaisesRegex(ValueError,'differs'):deliveries.prepare(self.p,changed)
        changed=copy.deepcopy(declaration);changed['default']['role']='effects'
        with self.assertRaisesRegex(ValueError,'Default'):deliveries.prepare(self.p,changed)

    def test_routes_pin_each_entry_and_legacy_movies_remain_readable(self):
        deliveries.register(self.p,self.declaration())
        for key in ['portrait.score','landscape.score']:
            data=deliveries.load(self.p,'pair')['entries'][key]
            header,body=self.http.request('/media/film/pair/'+key,headers={'Range':'bytes=0-12'})
            self.assertIn(b'206',header);self.assertEqual(body,(self.p/data['movie']['path']).read_bytes()[:13])
            header,body=self.http.request('/media/film/pair/poster?entry='+key)
            self.assertIn(b'200',header);self.assertEqual(body,(self.p/data['poster']['path']).read_bytes())
            header,_=self.http.request('/files/film/pair/'+key);self.assertIn(b'200',header)
        for key in ['score','landscape.silent']:
            header,_=self.http.request('/media/film/pair/'+key);self.assertIn(b'400',header)
        legacy=self.http.declaration('old');deliveries.register(self.p,legacy)
        raw=deliveries.record_path(self.p,'old').read_bytes()
        header,_=self.http.request('/media/film/old/score');self.assertIn(b'200',header)
        self.assertEqual(deliveries.record_path(self.p,'old').read_bytes(),raw)
        header,body=self.http.request('/api/projects/film/feedback','POST',
            {'delivery':'pair','view':'landscape','role':'score','seconds':1,'note':'Exact view test','observer':'Fixture'},
            {'Origin':'http://127.0.0.1:8783'})
        self.assertIn(b'201',header);self.assertEqual(json.loads(body)['feedback']['view'],'landscape')

    def test_overview_and_handoff_keep_each_view_review_separate(self):
        deliveries.register(self.p,self.declaration());deliveries.present(self.p,'pair','Fixture')
        result=production.overview(self.p,'film','http://127.0.0.1:8783',details=True)
        self.assertEqual(set(result['entry_checks']),{'portrait.score','landscape.score'})
        self.assertFalse(result['release_ready'])
        latest=cli.run(cli.parser().parse_args(['--registry',str(self.http.registry),'--project','film','project','latest']))
        self.assertEqual(latest['file'],str((self.p/result['current']['delivery']['entries']['portrait.score']['movie']['path']).resolve()))
        self.assertTrue(latest['watch_url'].endswith('?view=portrait&role=score'))
        self.assertTrue(latest['delivery']['entries']['landscape.score']['current_url'].endswith('?view=landscape&role=score'))
        for key,check in result['entry_checks'].items():
            self.assertEqual(check['subject']['view'],key.split('.')[0]);self.assertTrue(check['open_checks'])
        self.assertIn('?view=landscape&role=score',result['current']['delivery']['entries']['landscape.score']['watch_url'])
        production.handoff(self.p,'pair',self.p/'reports/handoff',alias='film')
        md=(self.p/'reports/handoff/handoff.md').read_text()
        self.assertIn('view=portrait&role=score',md);self.assertIn('view=landscape&role=score',md)
        with patch.object(revision_reviews,'status',side_effect=[{'release_ready':True}, {'release_ready':False,'gates':{'release':{'state':'pending'}}}]):
            self.assertFalse(deliveries.release_state(self.p,deliveries.load(self.p,'pair'))['approved'])

    def test_whole_job_preflight_rejects_bad_second_view_audio_and_foreign_destinations(self):
        recipes=[]
        bad=self.recipe('bad-view');bad['views'][1]='missing';recipes.append(bad)
        bad=self.recipe('bad-pcm');bad['editions'][1]['repeats']=3;recipes.append(bad)
        bad=self.recipe('odd-dimensions');bad['long_edge']=144;recipes.append(bad)
        for recipe in recipes:
            with patch.object(cli,'run') as encode:
                with self.assertRaises((ValueError,cli.CommandError)):production.iteration(self.p,recipe,'Fixture')
                encode.assert_not_called()
            state=studio.read(production.run_file(self.p,recipe['id']));self.assertEqual(state['state'],'failed');self.assertFalse(state['steps'])
        for field,value in [('title',[]),('notes',1),('supersample',2.0)]:
            bad=self.recipe('bad-metadata');bad[field]=value
            with self.assertRaises(ValueError):production.validate_recipe(bad)
        with self.assertRaisesRegex(ValueError,'--by'):production.iteration(self.p,self.recipe('no-actor'),' ')
        recipe=self.recipe('x'*80);production.validate_recipe(recipe)
        plan=production.view_job_plan(self.p,recipe,self.p/'runs/long',{'attempts':{}})
        self.assertEqual(len({job['edition'] for job in plan['jobs']}),4)
        self.assertTrue(all(len(job['edition'])<=100 for job in plan['jobs']))
        bad=copy.deepcopy(recipe);bad['views'].append('portrait')
        with self.assertRaisesRegex(ValueError,'unique'):production.validate_recipe(bad)

    @unittest.skipUnless(os.environ.get('AMBIANCE_TEST_NATIVE')=='1' and sys.platform=='darwin','Requires native encode/decode')
    def test_native_pair_recovers_after_receipt_save_and_reuses_both_soundtracks(self):
        from ambiance_studio.media_operations import execute_job
        recipe=self.recipe();calls=[]
        def interrupted(project, request, out):
            calls.append((request.command,request.view))
            result=execute_job(project, request, out)
            if len(calls)==2:raise KeyboardInterrupt('Fixture interruption after edition receipt')
            return result
        with patch.object(cli,'parser',side_effect=AssertionError('Production must not parse CLI arguments')):
            with self.assertRaises(KeyboardInterrupt):production.iteration(self.p,recipe,'Fixture',executor=interrupted)
        path=production.run_file(self.p,'pair');state=studio.read(path)
        self.assertEqual(len(state['steps']),1);self.assertIsNone(deliveries.current(self.p))
        before=state['steps']['portrait.picture.silent']['outputs']
        # A dead coordinator lock is recoverable; a live coordinator is not displaced.
        (path.parent/'active.lock').touch();state['pid']=os.getpid();studio.write(path,state)
        with self.assertRaisesRegex(ValueError,'Run owner is present or unverified'):production.iteration(self.p,recipe,'Fixture')
        from unittest.mock import Mock
        resumed=Mock(wraps=execute_job)
        with patch.object(production.os,'kill',side_effect=ProcessLookupError), patch.object(cli,'parser',side_effect=AssertionError('Production must not parse CLI arguments')):
            result=production.iteration(self.p,recipe,'Fixture',executor=resumed)
        self.assertTrue(result['ok']);self.assertEqual(resumed.call_count,2)
        self.assertEqual(studio.read(path)['steps']['portrait.picture.silent']['outputs'],before)
        data=deliveries.latest(self.p);self.assertTrue(data['ok']);self.assertEqual(len(data['delivery']['entries']),4)
        score_inputs=[]
        for key,entry in data['delivery']['entries'].items():
            self.assertEqual((entry['width'],entry['height']),(90,160) if entry['view']=='portrait' else (160,90))
            self.assertEqual(entry['frames'],24 if entry['role']=='score' else 12)
            bound=revisions.load_edition(self.p,'v1',entry['edition'])
            self.assertEqual(bound['view']['id'],entry['view'])
            if entry['role']=='score':score_inputs.append(bound['audio']['sha256'])
        self.assertEqual(score_inputs,[studio.digest(self.p/'audio/master.wav')]*2)
        token=data['selection']['payload_sha256'];self.assertTrue(production.iteration(self.p,recipe,'Fixture')['reused'])
        self.assertEqual(deliveries.current(self.p)['payload_sha256'],token)


if __name__=='__main__':unittest.main()
