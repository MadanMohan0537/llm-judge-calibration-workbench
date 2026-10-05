import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from unittest.mock import patch
from verdictlens.core import DEFAULT_RUBRIC, digest, evaluate, kappa, reference, review_queue, validate_dataset, validate_rubric
from verdictlens.judges import ollama_judge
from verdictlens.review import ReviewStore
from verdictlens.web import make_server
from verdictlens.__main__ import main

DATA = json.loads((Path(__file__).parents[1]/'examples/synthetic_pairs.json').read_text())


class MetricsTests(unittest.TestCase):
    def test_perfect_kappa(self):
        self.assertEqual(kappa(['a','b','tie'], ['a','b','tie']), 1)

    def test_opposite_kappa(self):
        self.assertEqual(kappa(['a','b'], ['b','a']), -1)

    def test_degenerate_kappa(self):
        self.assertIsNone(kappa(['a','a'], ['a','a']))

    def test_plurality_is_not_majority(self):
        self.assertEqual(reference(['a','b','tie']), 'tie')

    def test_duplicate_rejected(self):
        data = copy.deepcopy(DATA)
        data['pairs'].append(data['pairs'][0])
        with self.assertRaises(ValueError): validate_dataset(data)

    def test_invalid_votes(self):
        data = copy.deepcopy(DATA)
        data['pairs'][0]['human_votes'] = ['A','a']
        with self.assertRaises(ValueError): validate_dataset(data)

    def test_unknown_split_rejected(self):
        data = copy.deepcopy(DATA)
        data['pairs'][0]['split'] = 'test'
        with self.assertRaises(ValueError): validate_dataset(data)

    def test_nonfinite_rubric_rejected(self):
        r = copy.deepcopy(DEFAULT_RUBRIC)
        r['terms']['bad'] = float('nan')
        with self.assertRaises(ValueError): validate_rubric(r)

    def test_unknown_rubric_keys_rejected(self):
        r = dict(DEFAULT_RUBRIC, extra=1)
        with self.assertRaises(ValueError): validate_rubric(r)

    def test_position_swap_canonicalization(self):
        report = evaluate(DATA, DEFAULT_RUBRIC, judge=lambda a,b,p:'a', draws=20)
        self.assertEqual(report['summary']['order_flip_rate'], 1)

    def test_length_probe_detects_fault(self):
        report = evaluate(DATA, DEFAULT_RUBRIC, 'mock-length', draws=20)
        self.assertEqual(report['summary']['padding_flip_rate'], .5)
        self.assertEqual(report['summary']['agreement'], .25)

    def test_reproducible_under_reordering(self):
        a = evaluate(DATA, DEFAULT_RUBRIC, draws=20)
        data = copy.deepcopy(DATA)
        data['pairs'].reverse()
        b = evaluate(data, DEFAULT_RUBRIC, draws=20)
        self.assertEqual(a['summary'], b['summary'])
        self.assertEqual(a['rows'], b['rows'])
        self.assertNotEqual(a['dataset_sha256'], b['dataset_sha256'])

    def test_invalid_model_label_aborts(self):
        with self.assertRaises(ValueError): evaluate(DATA, DEFAULT_RUBRIC, judge=lambda a,b,p:'invalid', draws=20)

    def test_run_identity_changes_with_rubric(self):
        a = evaluate(DATA, DEFAULT_RUBRIC, draws=20)
        r = copy.deepcopy(DEFAULT_RUBRIC)
        r['tie_margin'] = 2
        b = evaluate(DATA, r, draws=20)
        self.assertNotEqual(a['run_id'], b['run_id'])

    def test_holdout_excluded_from_queue(self):
        r = evaluate(DATA, DEFAULT_RUBRIC, draws=20)
        self.assertTrue(review_queue(DATA, r))
        self.assertTrue(all(p['split']=='development' for p in review_queue(DATA, r)))

    def test_mismatched_dataset_rejected(self):
        r = evaluate(DATA, DEFAULT_RUBRIC, draws=20)
        data = copy.deepcopy(DATA)
        data['pairs'][0]['a'] += ' altered'
        with self.assertRaises(ValueError): review_queue(data, r)


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)/'review.sqlite'
        self.store = ReviewStore(self.path)
        self.report = evaluate(DATA, DEFAULT_RUBRIC, draws=20)
        self.run = self.report['run_id']
        self.store.save_run(DATA, self.report)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_labels_hidden(self):
        assignment = self.store.assignment(self.run, 'reviewer-1')
        self.assertEqual(set(assignment), {'token','prompt','a','b'})

    def test_vote_persists_and_is_independent(self):
        assignment = self.store.assignment(self.run, 'reviewer-1')
        self.store.vote(self.run, 'reviewer-1', assignment['token'], 'a')
        self.store.vote(self.run, 'reviewer-2', assignment['token'], 'tie')
        self.store.close()
        self.store = ReviewStore(self.path)
        votes = self.store.export(self.run)
        self.assertEqual(len(votes), 2)
        self.assertNotEqual(votes[0]['reviewer_hash'], votes[1]['reviewer_hash'])
        self.assertNotEqual(self.store.assignment(self.run, 'reviewer-1')['token'], assignment['token'])

    def test_duplicate_vote_preserved(self):
        a = self.store.assignment(self.run, 'reviewer-1')
        self.store.vote(self.run, 'reviewer-1', a['token'], 'tie')
        with self.assertRaises(ValueError): self.store.vote(self.run, 'reviewer-1', a['token'], 'b')
        self.assertEqual(self.store.export(self.run)[0]['choice'], 'tie')

    def test_vote_mapping_restores_original_answer(self):
        a = self.store.assignment(self.run, 'reviewer-1')
        self.store.vote(self.run, 'reviewer-1', a['token'], 'a')
        vote = self.store.export(self.run)[0]
        original = next(p for p in DATA['pairs'] if p['id']==vote['pair_id'])
        self.assertEqual(original[vote['choice']], a['a'])

    def test_forged_token_rejected(self):
        with self.assertRaises(ValueError): self.store.vote(self.run, 'reviewer-1', 'fake', 'a')

    def test_unknown_run_rejected(self):
        with self.assertRaises(ValueError): self.store.assignment('fake', 'reviewer-1')


class AdapterTests(unittest.TestCase):
    def test_ollama_contract_without_live_model(self):
        from io import BytesIO
        payload = json.dumps({'message': {'content':'{"winner":"b"}'}}).encode()
        with patch('verdictlens.judges.urlopen', return_value=BytesIO(payload)) as mock:
            self.assertEqual(ollama_judge('installed-model', DEFAULT_RUBRIC)('x','y','question'), 'b')
            request = mock.call_args.args[0]
            self.assertEqual(request.full_url, 'http://127.0.0.1:11434/api/chat')
            self.assertFalse(json.loads(request.data)['stream'])

    def test_ollama_failure_does_not_fallback(self):
        with patch('verdictlens.judges.urlopen', side_effect=OSError('offline')):
            with self.assertRaises(OSError): ollama_judge('model', DEFAULT_RUBRIC)('x','y','p')

    def test_cli_requires_model(self):
        self.assertEqual(main(['evaluate','--data',str(Path(__file__).parents[1]/'examples/synthetic_pairs.json'),'--judge','ollama']), 2)


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.server = make_server(DATA, Path(self.tmp.name)/'db.sqlite', 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()
        self.server.store.close()
        self.tmp.cleanup()

    def test_workbench_and_full_vote_flow(self):
        with urlopen(self.url) as r: self.assertIn(b'VerdictLens', r.read())
        request = Request(self.url+'/api/evaluate', data=b'{}', headers={'Content-Type':'application/json'})
        with urlopen(request) as r: reports = json.load(r)
        self.assertEqual(len(reports), 2)
        run = reports[0]['run_id']
        with urlopen(self.url+'/api/assignment?run='+run+'&reviewer=alice') as r: a=json.load(r)
        vote = {'run':run,'reviewer':'alice','token':a['token'],'choice':'tie'}
        with urlopen(Request(self.url+'/api/vote', data=json.dumps(vote).encode(), headers={'Content-Type':'application/json'})) as r: self.assertTrue(json.load(r)['saved'])
        with urlopen(self.url+'/api/votes?run='+run) as r: self.assertEqual(len(json.load(r)), 1)

    def test_cross_origin_rejected(self):
        req=Request(self.url+'/api/evaluate', data=b'{}', headers={'Content-Type':'application/json','Origin':'https://evil.invalid'})
        with self.assertRaises(HTTPError) as caught: urlopen(req)
        self.assertEqual(caught.exception.code, 403)

    def test_invalid_json_rejected(self):
        req=Request(self.url+'/api/evaluate', data=b'{', headers={'Content-Type':'application/json'})
        with self.assertRaises(HTTPError) as caught: urlopen(req)
        self.assertEqual(caught.exception.code, 400)


if __name__ == '__main__':
    unittest.main()
