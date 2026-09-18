import json
import unittest
from confidence_agents.balanced_bank import build
from confidence_agents.local_replay import contexts
from confidence_agents.confidence_sweep import ARMS, GAPS, messages, summarize


class SweepTests(unittest.TestCase):
    def test_treatment_invariance(self):
        for context in contexts(build(per_class=4,max_candidates=200)['tasks'],20260922):
            stripped=[]
            for arm in ARMS:
                msg=messages(context,arm)
                body=json.loads(msg[1]['content'])
                peers=body['peer_reports']
                if arm not in ('equal','hidden'):
                    side,gap=arm.rsplit('_',1)
                    self.assertAlmostEqual(sum(p['confidence'] for p in peers)/4,.75)
                    for p in peers:
                        high=(p['answer']==context['task']['truth'])==(side=='correct_high')
                        self.assertEqual(p['confidence'],GAPS[gap][0 if high else 1])
                for p in peers:
                    p.pop('confidence',None)
                stripped.append((msg[0],body))
            self.assertTrue(all(v==stripped[0] for v in stripped))

    def test_known_slope_and_missing(self):
        rows=[]
        for arm in ARMS:
            count=int(arm.rsplit('_',1)[1])//10 if arm.startswith('wrong_high') else 0
            for rep in range(10):
                wrong=rep<count
                rows.append(dict(item_id='one',arm=arm,repeat=rep,answer='B' if wrong else 'A',
                                 wrong=wrong,truth='A',semantic='Yes',own_correct=True))
        result=summarize(rows,10,'mock',1)
        self.assertAlmostEqual(result['primary_slope'],1)
        rows[0].update(answer=None,wrong=None)
        self.assertEqual(summarize(rows,10,'mock',1)['primary_complete_items'],0)
