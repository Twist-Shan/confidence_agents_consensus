"""Independent audit from recorded requests/responses, without importing the runner."""
import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def audit(directory):
    directory = Path(directory)
    assert not (directory / '.running').exists(), 'Wait for the run to finish before auditing'
    summary = read(directory / 'summary.json')
    manifest = read(directory / 'manifest.json')
    roots = read(directory / 'roots.json')
    items = {i['id']: i for i in manifest['items']}
    records = [read(p) for p in directory.glob('items/*/calls/*.json')]
    assert summary['usage']['requests'] == len(records)
    assert len({r['call_id'] for r in records}) == len(records)
    assert len(records) <= manifest['maximum_requests']
    lookup = {r['call_id']: r for r in records}
    checked_pairs, group_count = 0, 0
    independently_decoded = {}
    finish = Counter()
    for r in records:
        assert r['request']['provider']['allow_fallbacks'] is False
        assert r['request']['model'] == manifest['model']['id']
        actual_hash = hashlib.sha256(json.dumps(r['request'], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        assert actual_hash == r['request_hash']
        if r['status'] == 'complete':
            choice = r['response']['choices'][0]
            finish[choice.get('finish_reason')] += 1
            try:
                parsed = json.loads(choice['message']['content'])
            except (ValueError, TypeError):
                parsed = {}
            if choice.get('finish_reason') == 'stop' and parsed.get('answer') in ('A', 'B'):
                independently_decoded[r['call_id']] = parsed['answer']
                assert r['parsed']['answer'] == parsed['answer']
        # Credentials must not be stored in any record.
        assert 'sk-or-' not in json.dumps(r)
    for item_id, item in items.items():
        cards = [item['public']] + item['private']
        difference = sum(c['A_net_benefit'] for c in cards) - sum(c['B_net_benefit'] for c in cards)
        assert item['truth'] == ('A' if difference > 0 else 'B')
        assert difference == item['net_A_minus_B'] != 0
        if item_id not in roots:
            continue
        root = roots[item_id]
        for j in range(6):
            assert root['state'][j] == independently_decoded[f'{item_id}/initial/{j}']
            initial = json.loads(lookup[f'{item_id}/initial/{j}']['request']['messages'][1]['content'])
            assert initial['your_private_record'] == item['private'][j]
            assert 'peer_reports' not in initial and 'all_other_records' not in initial
        if root['pair'] is None:
            continue
        c, w = root['pair']
        assert root['state'][c] == item['truth'] and root['state'][w] != item['truth']
        if item['split'] == 'train':
            for j in range(6):
                bodies = [json.loads(lookup[f'{item_id}/local/{arm}/{j}']['request']['messages'][1]['content'])
                          for arm in ('aligned', 'misaligned')]
                for body, expected in zip(bodies, ((.95, .55), (.55, .95))):
                    assert body['your_previous_answer'] == root['state'][j]
                    peers = {int(p['member_id'].split('-')[1]): p for p in body['peer_reports']}
                    assert set(peers) == set(range(6)) - {j}
                    for k, peer in peers.items():
                        assert peer['answer'] == root['state'][k]
                        assert peer['audit_record'] == item['private'][k]
                        assert peer['confidence'] == (expected[0] if k == c else expected[1] if k == w else .75)
                if j not in (c, w):
                    assert sorted(p['confidence'] for p in bodies[0]['peer_reports']) == sorted(p['confidence'] for p in bodies[1]['peer_reports'])
                    checked_pairs += 1
                for body in bodies:
                    for peer in body['peer_reports']:
                        peer.pop('confidence')
                assert bodies[0] == bodies[1]
        else:
            for arm in ('aligned', 'misaligned', 'hidden'):
                for t in (1, 2):
                    for j in range(6):
                        call_id = f'{item_id}/group/{arm}/{t}/{j}'
                        if call_id not in lookup:
                            continue
                        body = json.loads(lookup[call_id]['request']['messages'][1]['content'])
                        previous = root['state'] if t == 1 else [independently_decoded[f'{item_id}/group/{arm}/1/{k}'] for k in range(6)]
                        assert body['your_previous_answer'] == previous[j]
                        for peer in body['peer_reports']:
                            k = int(peer['member_id'].split('-')[1])
                            assert peer['answer'] == previous[k]
                            assert peer['audit_record'] == item['private'][k]
                            if t == 2 or arm == 'hidden':
                                assert 'confidence' not in peer
                            else:
                                high, low = ((.95, .55) if arm == 'aligned' else (.55, .95))
                                assert peer['confidence'] == (high if k == c else low if k == w else .75)
                        group_count += 1
    # File timestamp is checked against actual recorded API start timestamps.
    group_records = [r for r in records if '/group/' in r['call_id']]
    round2_triplets, identical_round2 = 0, 0
    for item in manifest['items']:
        if item['split'] != 'test':
            continue
        for j in range(6):
            triplet = [lookup.get(f"{item['id']}/group/{arm}/2/{j}") for arm in ('aligned', 'misaligned', 'hidden')]
            if all(triplet):
                round2_triplets += 1
                identical_round2 += len({r['request_hash'] for r in triplet}) == 1
    predated = ((directory / 'predictions_before_group.json').stat().st_mtime
                < min(r['started_at'] for r in group_records)) if group_records else None
    assert predated is not False
    summaries = defaultdict(list)
    initial_rule_matches, initial_expost_correct, oracle_correct = [], [], []
    for call_id, answer in independently_decoded.items():
        parts = call_id.split('/')
        item = items[parts[0]]
        if parts[1] == 'group':
            summaries[f'round{parts[3]}/{parts[2]}'].append(answer != item['truth'])
        elif parts[1] == 'initial':
            j = int(parts[2])
            a = item['public']['A_net_benefit'] + item['private'][j]['A_net_benefit']
            b = item['public']['B_net_benefit'] + item['private'][j]['B_net_benefit']
            initial_rule_matches.append(answer == ('A' if a > b else 'B'))
            initial_expost_correct.append(answer == item['truth'])
        elif parts[1] == 'oracle':
            oracle_correct.append(answer == item['truth'])
    result = {'passed': True, 'records': len(records), 'status': dict(Counter(r['status'] for r in records)),
              'finish_reasons': dict(finish), 'primary_local_pairs_checked': checked_pairs,
              'synchronous_group_inputs_checked': group_count, 'predictions_predate_group_calls': predated,
              'round2_condition_triplets': round2_triplets,
              'round2_identical_request_triplets': identical_round2,
              'independent_group_error_rates': {k: mean(v) for k, v in summaries.items()},
              'initial_matches_private_expected_utility_rule': {'n': len(initial_rule_matches), 'correct': sum(initial_rule_matches)},
              'initial_expost_accuracy': {'n': len(initial_expost_correct), 'correct': sum(initial_expost_correct)},
              'full_information_oracle': {'n': len(oracle_correct), 'correct': sum(oracle_correct)},
              'oracle_rule_Brier_for_group_choices': {k: mean(v) for k, v in summaries.items()},
              'returned_models': dict(Counter(r.get('response', {}).get('model') for r in records if r['status'] == 'complete')),
              'known_cost_usd': sum(r.get('response', {}).get('usage', {}).get('cost', 0) or 0 for r in records)}
    frozen = directory / 'frozen_source' / 'confidence_agents'
    if frozen.exists():
        sources = {name: (frozen / name).read_text(encoding='utf-8') for name in ('confidence_transfer.py', 'runtime.py', 'design.py')}
        archived_hash = hashlib.sha256(json.dumps(sources, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        assert archived_hash == manifest['source_hash']
        result['frozen_source_hash_verified'] = True
    (directory / 'independent_audit.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('directory')
    audit(parser.parse_args().directory)
