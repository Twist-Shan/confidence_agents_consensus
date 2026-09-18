import copy
import itertools
import json
import unittest
from fractions import Fraction

from confidence_agents.signal_visibility import (
    HIGH, LOW, advice_reference, bank, messages, posterior, root_design, scores, summarize,
)


class SignalVisibilityTests(unittest.TestCase):
    def test_new_bank_seed_preserves_original_and_changes_only_instance_generation(self):
        original = bank()
        new = bank(20260920)
        self.assertEqual(original, bank(20260919))
        self.assertEqual(new, bank(20260920))
        self.assertNotEqual(original, new)
        self.assertEqual([x['id'] for x in original], [x['id'] for x in new])
        self.assertEqual(sum(x['state'] == 'high' for x in new), 8)
        self.assertEqual(bank(), original)
        for item in new:
            self.assertEqual(item['posterior_full_exact'], str(posterior(sum(item['signals'], []))))

    def root(self, item):
        initial = [{'answer': 'B' if p > .5 else 'A', 'p_B': p, 'reason': 'DO NOT PROPAGATE'}
                   for p in item['posterior_private']]
        return root_design(item, initial)

    def test_exact_probability_against_likelihood_enumeration(self):
        self.assertEqual(sum(x['state'] == 'high' for x in bank()), 8)
        for n in (3, 18):
            for h in range(n + 1):
                lh = Fraction(3, 5)**h * Fraction(2, 5)**(n-h)
                ll = Fraction(2, 5)**h * Fraction(3, 5)**(n-h)
                self.assertEqual(posterior(['high'] * h + ['low'] * (n-h)), lh / (lh + ll))
        self.assertEqual(posterior(['high'] * 3), Fraction(27, 35))
        self.assertEqual(posterior(['high', 'high', 'low']), Fraction(3, 5))

    def test_swap_and_visibility_change_only_intended_fields(self):
        for item in bank():
            root = self.root(item)
            if root is None:
                continue
            for j in root['targets']:
                self.assertNotIn(j, root['pair_A_B'])
                for visibility in ('full', 'advice'):
                    a, b = [json.loads(messages(item, j, root, visibility, arm)[1]['content'])
                            for arm in ('A_high', 'B_high')]
                    self.assertEqual(sorted(x['confidence'] for x in a['peer_reports']),
                                     sorted(x['confidence'] for x in b['peer_reports']))
                    for obj in (a, b):
                        for peer in obj['peer_reports']:
                            peer.pop('confidence')
                            self.assertNotIn('reason', peer)
                            self.assertNotIn('p_B', peer)
                    self.assertEqual(a, b)
                full, advice = [json.loads(messages(item, j, root, v, 'B_high')[1]['content'])
                                for v in ('full', 'advice')]
                cards = full['your_surveys'][:]
                for peer in full['peer_reports']:
                    cards.extend(peer.pop('surveys'))
                self.assertEqual(full, advice)
                self.assertEqual(len({x['source_id'] for x in cards}), 18)
                changed = copy.deepcopy(item)
                changed['state'] = 'low' if item['state'] == 'high' else 'high'
                changed['posterior_full'] = -100
                self.assertEqual(messages(item, j, root, 'full', 'B_high'), messages(changed, j, root, 'full', 'B_high'))

    def test_advice_reference_and_initial_privacy(self):
        reliability = sum(Fraction(3, 5)**sum(x) * Fraction(2, 5)**(3-sum(x))
                          for x in itertools.product((0, 1), repeat=3) if sum(x) >= 2)
        self.assertEqual(reliability, Fraction(81, 125))
        for item in bank():
            for j in range(6):
                body = json.loads(messages(item, j)[1]['content'])
                self.assertEqual(len(body['your_surveys']), 3)
                self.assertNotIn('peer_reports', body)
                self.assertNotIn('state', body)
            root = self.root(item)
            if root:
                for j in root['targets']:
                    self.assertTrue(0 < advice_reference(item, j, root) < 1)
                a, b = root['pair_A_B']
                values = scores(root, 'B_high')
                self.assertEqual(values[a], LOW)
                self.assertEqual(values[b], HIGH)

    def test_interaction_and_common_complete_item_set(self):
        selected = [x for x in bank() if self.root(x) is not None][:2]
        roots = {x['id']: self.root(x) for x in selected}
        rows = []
        for item in selected:
            for j in roots[item['id']]['targets']:
                for v in ('full', 'advice'):
                    for arm in ('A_high', 'B_high', 'pair_equal', 'hidden'):
                        for rep in range(2):
                            shift = .01 if v == 'full' else .1
                            p = .5 + (-shift if arm == 'A_high' else shift if arm == 'B_high' else 0)
                            rows.append({'item_id': item['id'], 'member': j, 'visibility': v, 'arm': arm,
                                         'repeat': rep, 'parsed': {'answer': 'B' if p > .5 else 'A', 'p_B': p}})
        manifest = {'items': selected, 'backend': 'mock'}
        result = summarize(manifest, roots, [], rows, [])
        self.assertAlmostEqual(result['primary']['full']['mean_p_B_shift'], .02)
        self.assertAlmostEqual(result['primary']['advice']['mean_p_B_shift'], .2)
        self.assertAlmostEqual(result['primary']['interaction']['mean_p_B_shift'], .18)
        self.assertEqual(result['primary']['interaction']['n_items'], 2)
        rows[0]['parsed'] = None
        result = summarize(manifest, roots, [], rows, [])
        self.assertEqual(result['primary']['full']['n_items'], 1)
        self.assertEqual(result['primary']['advice']['n_items'], 1)
        self.assertAlmostEqual(result['primary']['interaction']['mean_p_B_shift'], .18)


if __name__ == '__main__':
    unittest.main()
