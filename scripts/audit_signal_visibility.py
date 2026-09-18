"""Independent raw-request and probability audit, without importing experiment code."""
import argparse
import hashlib
import json
import random
from collections import Counter
from fractions import Fraction
from pathlib import Path
from statistics import mean


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def independent_posterior(signals):
    h = signals.count('high')
    l = len(signals) - h
    likelihood_h = Fraction(3, 5)**h * Fraction(2, 5)**l
    likelihood_l = Fraction(2, 5)**h * Fraction(3, 5)**l
    return float(likelihood_h / (likelihood_h + likelihood_l))


def audit(directory):
    directory = Path(directory)
    assert not (directory / '.running').exists(), 'Audit after the run finishes'
    manifest, roots, summary = [read(directory / n) for n in ('manifest.json', 'roots.json', 'summary.json')]
    items = {i['id']: i for i in manifest['items']}
    records = [read(p) for p in directory.glob('items/*/calls/*.json')]
    assert len(records) == summary['usage']['requests'] <= 608
    lookup = {r['call_id']: r for r in records}
    assert len(lookup) == len(records)
    decoded = {}
    for r in records:
        assert 'sk-or-' not in json.dumps(r)
        checksum = hashlib.sha256(json.dumps(r['request'], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        assert checksum == r['request_hash']
        assert r['request']['provider']['allow_fallbacks'] is False
        if r['status'] == 'complete':
            choice = r['response']['choices'][0]
            if choice.get('finish_reason') == 'stop':
                try:
                    obj = json.loads(choice['message']['content'])
                    if obj.get('answer') in ('A', 'B') and type(obj.get('p_B')) in (int, float) and 0 <= obj['p_B'] <= 1:
                        decoded[r['call_id']] = obj
                        assert r['parsed'] == obj
                except (ValueError, TypeError):
                    pass
    def body(call_id):
        return json.loads(lookup[call_id]['request']['messages'][1]['content'])
    initial_errors = []
    initial_majority_match = []
    swaps = visibility_pairs = repeat_pairs = 0
    for item_id, item in items.items():
        signals = sum(item['signals'], [])
        assert abs(independent_posterior(signals) - item['posterior_full']) < 1e-14
        for j in range(6):
            call_id = f'{item_id}/initial/{j}'
            b = body(call_id)
            assert [s['signal'] for s in b['your_surveys']] == item['signals'][j]
            assert 'peer_reports' not in b and 'state' not in b and 'posterior_full' not in b
            if call_id in decoded:
                actual = decoded[call_id]
                expected = independent_posterior(item['signals'][j])
                initial_errors.append(abs(actual['p_B'] - expected))
                initial_majority_match.append(actual['answer'] == ('B' if item['signals'][j].count('high') >= 2 else 'A'))
        if item_id not in roots:
            continue
        root = roots[item_id]
        a, b = root['pair_A_B']
        assert root['initial'][a]['answer'] == 'A' and root['initial'][b]['answer'] == 'B'
        for j in range(6):
            assert root['initial'][j] == decoded[f'{item_id}/initial/{j}']
        for j in root['targets']:
            assert j not in (a, b)
            for v in ('full', 'advice'):
                for rep in (0, 1):
                    pair = [body(f'{item_id}/update/{j}/{v}/{arm}/{rep}') for arm in ('A_high', 'B_high')]
                    assert sorted(p['confidence'] for p in pair[0]['peer_reports']) == sorted(p['confidence'] for p in pair[1]['peer_reports'])
                    for context, arm in zip(pair, ('A_high', 'B_high')):
                        for peer in context['peer_reports']:
                            k = int(peer['member_id'].split('-')[1])
                            expected = root['initial'][k]['p_B'] if root['initial'][k]['answer'] == 'B' else 1-root['initial'][k]['p_B']
                            if k in (a, b):
                                expected = manifest['high'] if (k == a) == (arm == 'A_high') else manifest['low']
                            assert peer['confidence'] == expected
                            peer.pop('confidence')
                    assert pair[0] == pair[1]
                    swaps += 1
            for arm in ('A_high', 'B_high', 'pair_equal', 'hidden'):
                for rep in (0, 1):
                    full, advice = [body(f'{item_id}/update/{j}/{v}/{arm}/{rep}') for v in ('full', 'advice')]
                    full_cards = full['your_surveys'][:]
                    for peer in full['peer_reports']:
                        k = int(peer['member_id'].split('-')[1])
                        assert peer['answer'] == root['initial'][k]['answer']
                        assert 'reason' not in peer and 'p_B' not in peer
                        cards = peer.pop('surveys')
                        assert [s['signal'] for s in cards] == item['signals'][k]
                        full_cards.extend(cards)
                    assert len(full_cards) == len({s['source_id'] for s in full_cards}) == 18
                    assert full == advice
                    assert full['your_previous_forecast'] == {k: root['initial'][j][k] for k in ('answer', 'p_B')}
                    visibility_pairs += 1
                for v in ('full', 'advice'):
                    left, right = [lookup[f'{item_id}/update/{j}/{v}/{arm}/{rep}']['request_hash'] for rep in (0, 1)]
                    assert left == right
                    repeat_pairs += 1
    effects = []
    for item_id, root in roots.items():
        entry = {'item_id': item_id}
        for v in ('full', 'advice'):
            comparisons = []
            for j in root['targets']:
                for rep in (0, 1):
                    a, b = [decoded.get(f'{item_id}/update/{j}/{v}/{arm}/{rep}') for arm in ('A_high', 'B_high')]
                    if a is not None and b is not None:
                        comparisons.append(b['p_B'] - a['p_B'])
            if len(comparisons) == 4:
                entry[v] = mean(comparisons)
        if 'full' in entry and 'advice' in entry:
            entry['interaction'] = entry['advice'] - entry['full']
            effects.append(entry)
    recomputed = {k: mean(r[k] for r in effects) if effects else None for k in ('full', 'advice', 'interaction')}
    for k, value in recomputed.items():
        assert value is None or abs(value - summary['primary'][k]['mean_p_B_shift']) < 1e-14
    independent_intervals = {}
    for key in ('full', 'advice', 'interaction'):
        expected = None
        if len(effects) >= 2:
            seed_bytes = json.dumps([manifest['seed'], 'bootstrap', key], sort_keys=True, ensure_ascii=False).encode()
            generator = random.Random(int(hashlib.sha256(seed_bytes).hexdigest(), 16))
            ordered = sorted(effects, key=lambda row: row['item_id'])
            strata = sorted({items[row['item_id']]['state'] for row in ordered})
            groups = [[row[key] for row in ordered if items[row['item_id']]['state'] == state] for state in strata]
            samples = []
            for _ in range(2000):
                sampled = []
                for group in groups:
                    sampled.extend(generator.choices(group, k=len(group)))
                samples.append(mean(sampled))
            samples.sort()
            expected = [samples[49], samples[1949]]
        assert expected == summary['primary'][key]['descriptive_item_bootstrap_95pct']
        independent_intervals[key] = expected
    sources = {n: (directory / 'frozen_source' / 'confidence_agents' / n).read_text(encoding='utf-8')
               for n in ('signal_visibility.py', 'runtime.py', 'design.py')}
    assert hashlib.sha256(json.dumps(sources, sort_keys=True, ensure_ascii=False).encode()).hexdigest() == manifest['source_hash']
    result = {'passed': True, 'records': len(records), 'status': dict(Counter(r['status'] for r in records)),
              'score_swap_pairs': swaps, 'visibility_pairs': visibility_pairs, 'identical_repeat_pairs': repeat_pairs,
              'initial_private_posterior_mean_absolute_error': mean(initial_errors) if initial_errors else None,
              'initial_majority_rule': {'valid': len(initial_majority_match), 'matches': sum(initial_majority_match)},
              'independent_effects': recomputed,
              'independent_intervals': independent_intervals,
              'returned_models': dict(Counter(r.get('response', {}).get('model') for r in records if r['status'] == 'complete')),
              'finish_reasons': dict(Counter(r.get('response', {}).get('choices', [{}])[0].get('finish_reason') for r in records if r['status'] == 'complete'))}
    (directory / 'independent_audit.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('directory')
    audit(parser.parse_args().directory)
