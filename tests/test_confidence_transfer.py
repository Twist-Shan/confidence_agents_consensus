import copy
import json
import unittest

from confidence_agents.confidence_transfer import (
    allocation, bank, choose_pair, features, fit, messages, predict, state_distribution,
)


class TransferTests(unittest.TestCase):
    def test_truth_and_balancing(self):
        items = bank()
        self.assertEqual(len(items), 16)
        signatures = set()
        for item in items:
            cards = [item['public']] + item['private']
            total_a = sum(c['A_net_benefit'] for c in cards)
            total_b = sum(c['B_net_benefit'] for c in cards)
            self.assertEqual(total_a - total_b, item['net_A_minus_B'])
            self.assertEqual(item['truth'], 'A' if total_a > total_b else 'B')
            self.assertEqual(len({c['source_id'] for c in cards}), 7)
            self.assertNotIn((item['public_delta'], *sorted(item['private_deltas'])), signatures)
            signatures.add((item['public_delta'], *sorted(item['private_deltas'])))
        for split in ('train', 'test'):
            self.assertEqual(sum(x['truth'] == 'A' for x in items if x['split'] == split), 4)

    def test_pair_swap_excludes_self_and_preserves_facts(self):
        item = bank()[0]
        state = ['A', 'B', 'A', 'B', 'A', 'B']
        pair = choose_pair(item, state)
        aligned, misaligned = [allocation(pair, a) for a in ('aligned', 'misaligned')]
        self.assertEqual(sorted(aligned), sorted(misaligned))
        for member in range(6):
            bodies = [json.loads(messages(item, member, state, scores)[1]['content'])
                      for scores in (aligned, misaligned)]
            for body in bodies:
                self.assertEqual(body['your_previous_answer'], state[member])
                self.assertEqual(len(body['peer_reports']), 5)
                self.assertNotIn(f'member-{member}', [p['member_id'] for p in body['peer_reports']])
                self.assertNotIn('truth', body)
            if member not in pair:
                self.assertEqual(sorted(p['confidence'] for p in bodies[0]['peer_reports']),
                                 sorted(p['confidence'] for p in bodies[1]['peer_reports']))
            for body in bodies:
                for peer in body['peer_reports']:
                    peer.pop('confidence')
            self.assertEqual(bodies[0], bodies[1])
        # The truth field affects neither prompt nor features; ground truth is not serialized.
        changed = copy.deepcopy(item)
        changed['truth'] = 'B' if item['truth'] == 'A' else 'A'
        self.assertEqual(messages(changed, 0, state, aligned), messages(item, 0, state, aligned))
        self.assertEqual(features(changed, 0, state, aligned), features(item, 0, state, aligned))

    def test_private_initial_information(self):
        item = bank()[0]
        body = json.loads(messages(item, 2)[1]['content'])
        self.assertEqual(body['your_private_record'], item['private'][2])
        self.assertNotIn('peer_reports', body)
        self.assertNotIn('all_other_records', body)
        self.assertIsNone(choose_pair(item, ['A'] * 6))

    def test_exact_rollout_mass_and_no_conf_baseline(self):
        dist = state_distribution([.2, .3, .4, .5, .6, .7])
        self.assertAlmostEqual(sum(dist.values()), 1.)
        item, state = bank()[0], ['A', 'B', 'A', 'B', 'A', 'B']
        pair = choose_pair(item, state)
        model = {'weights': [0.] * 5, 'with_confidence': False}
        a = predict(item, state, pair, 'aligned', model)
        b = predict(item, state, pair, 'misaligned', model)
        self.assertEqual(a, b)
        for row in a:
            self.assertAlmostEqual(row['wrong_fraction'], .5)
            self.assertAlmostEqual(row['wrong_consensus'], 1 / 64)

    def test_fit_independent_of_worker_completion_order(self):
        item = bank()[0]
        state = ['A', 'B', 'A', 'B', 'A', 'B']
        roots = {item['id']: {'state': state, 'pair': choose_pair(item, state)}}
        rows = [{'id': f'{arm}/{j}', 'item_id': item['id'], 'member': j, 'arm': arm, 'answer': state[j]}
                for arm in ('aligned', 'misaligned', 'hidden') for j in range(6)]
        self.assertEqual(fit(rows, {item['id']: item}, roots, True),
                         fit(list(reversed(rows)), {item['id']: item}, roots, True))


if __name__ == '__main__':
    unittest.main()
