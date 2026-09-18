import unittest
from collections import Counter

from confidence_agents.balanced_bank import build
from confidence_agents.calibration import candidates, solve, render


class BalancedBankTests(unittest.TestCase):
    def test_exact_balance_and_truth(self):
        bank=build(20260921,4,200)
        cells=Counter()
        for task in bank['tasks']:
            yes,_=solve(task['problem'])
            semantic='Yes' if yes else 'No'
            self.assertEqual(task['options']['AB'.index(task['truth'])],semantic)
            self.assertEqual(task['question'],render(task['problem'])+f"\nA: {task['options'][0]}\nB: {task['options'][1]}")
            cells[semantic,task['truth']]+=1
        self.assertEqual(set(cells.values()),{2})
        self.assertEqual(len(cells),4)
        self.assertEqual(len({x['id'] for x in bank['tasks']}),8)
        self.assertEqual(bank,build(20260921,4,200))
        self.assertEqual(sum(x['selected'] for x in bank['construction']['audit']),8)

    def test_filtered_generator_preserves_old_questions(self):
        old=[x for x in candidates() if x['family']=='logic' and x['level']==2]
        self.assertEqual(old,candidates(families=('logic',),levels=(2,)))

    def test_quota_failure_no_silent_shortfall(self):
        with self.assertRaises(ValueError):
            build(per_class=3)
        with self.assertRaises(ValueError):
            build(per_class=20,max_candidates=2)


if __name__ == '__main__':
    unittest.main()
