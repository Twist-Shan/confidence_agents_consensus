import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from confidence_agents.balanced_bank import build
from confidence_agents.local_replay import ARMS, contexts, messages, run, summarize
from confidence_agents.runtime import save


class LocalReplayTests(unittest.TestCase):
    def test_context_balance_and_only_confidence_changes(self):
        bank=build(per_class=4,max_candidates=200)['tasks']
        fixed=contexts(bank,9)
        cells=Counter((c['semantic'],c['task']['truth'],c['own_correct']) for c in fixed)
        self.assertEqual(len(cells),8)
        self.assertEqual(set(cells.values()),{1})
        for c in fixed:
            stripped=[]
            for arm in ARMS:
                msg=messages(c,arm)
                body=json.loads(msg[1]['content'])
                self.assertEqual(set(body),{'question','own_previous_answer','peer_reports'})
                peers=body['peer_reports']
                self.assertEqual(Counter(p['answer'] for p in peers),{'A':2,'B':2})
                if arm=='hidden':
                    self.assertTrue(all('confidence' not in p for p in peers))
                elif arm=='equal':
                    self.assertEqual([p['confidence'] for p in peers],[.75]*4)
                else:
                    self.assertEqual(sorted(p['confidence'] for p in peers),[.55,.55,.95,.95])
                    for p in peers:
                        high=(p['answer']==c['task']['truth'])==(arm=='correct_high')
                        self.assertEqual(p['confidence'],.95 if high else .55)
                for p in peers:
                    p.pop('confidence',None)
                stripped.append((msg[0],body))
            self.assertTrue(all(x==stripped[0] for x in stripped))

    def test_primary_pairing_and_missing_bounds(self):
        rows=[]
        for item in ('one','two'):
            for arm in ARMS:
                for rep in range(3):
                    wrong=arm=='wrong_high'
                    rows.append(dict(item_id=item,arm=arm,repeat=rep,answer='B' if wrong else 'A',wrong=wrong,
                                     truth='A',semantic='Yes',own_correct=True))
        result=summarize(rows,3,'mock',1)
        self.assertEqual(result['primary_delta_wrong_high_minus_correct_high'],1)
        self.assertEqual(result['all_completed_item_missing_response_bounds'],[1,1])
        rows[3].update(answer=None,wrong=None)
        result=summarize(rows,3,'mock',1)
        self.assertEqual(result['primary_paired_items'],1)
        self.assertAlmostEqual(result['all_completed_item_missing_response_bounds'][0],5/6)
        self.assertEqual(result['arms']['wrong_high']['invalid'],1)

    def test_mock_run_and_resume(self):
        config=json.loads(Path('configs/luna-reliable.json').read_text())
        with tempfile.TemporaryDirectory() as folder:
            bank=Path(folder)/'bank.json'; save(bank,build(per_class=4,max_candidates=200))
            directory=Path(folder)/'run'
            result=run(config,bank,directory,repeats=1,cap=32)
            self.assertEqual(result['usage']['requests'],32)
            self.assertEqual(result['primary_paired_items'],8)
            self.assertEqual(result,run(config,bank,directory,repeats=1,cap=32))
            with self.assertRaises(ValueError):
                run(config,bank,directory,repeats=2,cap=64)


if __name__=='__main__':
    unittest.main()
