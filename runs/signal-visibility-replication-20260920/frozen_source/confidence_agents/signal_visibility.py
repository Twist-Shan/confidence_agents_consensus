"""Paired confidence allocation under full evidence versus advice-only information."""
import argparse
import getpass
import itertools
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from fractions import Fraction
from pathlib import Path
from statistics import mean

from .design import digest, rng
from .runtime import Calls, catalog, save

SEED = 20260919
PROTOCOL = 'noisy-demand-visibility-v1'
ARMS = ('B_high', 'A_high', 'pair_equal', 'hidden')
VISIBILITY = ('full', 'advice')
LOW, HIGH = .6, round(27 / 35, 6)
SYSTEM = ('You are one of six equal analysts forecasting demand for a new product. '
          'A means LOW demand; B means HIGH demand. Report p_B, your probability of HIGH demand, '
          'between 0 and 1. Forecasts are evaluated by squared error against the eventual demand state. '
          'Choose B when p_B > 0.5; otherwise choose A. '
          'Use the information provided. Do not assume you know observations that are not shown. '
          "If displayed, confidence is an analyst's stated probability that their recommended "
          'demand state is correct, not a guarantee. '
          'Return only JSON with answer (A or B), p_B (number), and reason (one brief sentence).')


def posterior(signals, accuracy=Fraction(3, 5)):
    odds = Fraction(1)
    for signal in signals:
        odds *= accuracy / (1 - accuracy) if signal == 'high' else (1 - accuracy) / accuracy
    return odds / (1 + odds)


def bank(seed=SEED):
    result = []
    # Prebalanced demand strata; survey draws are never filtered by their values.
    states = ['low'] * 8 + ['high'] * 8
    rng(seed, 'demand-state-order').shuffle(states)
    for k in range(16):
        r = rng(seed, 'demand', k)
        state = states[k]
        signals = [[state if r.randrange(5) < 3 else ('low' if state == 'high' else 'high')
                    for _ in range(3)] for _ in range(6)]
        full = posterior(list(itertools.chain.from_iterable(signals)))
        result.append({'id': f'demand-{k:02d}', 'state': state, 'signals': signals,
                       'posterior_full': float(full), 'posterior_full_exact': str(full),
                       'posterior_private': [float(posterior(s)) for s in signals]})
    return result


def root_design(item, initial):
    a = [j for j, x in enumerate(initial) if x['answer'] == 'A']
    b = [j for j, x in enumerate(initial) if x['answer'] == 'B']
    if not a or not b:
        return None
    r = rng(SEED, item['id'], 'pair-targets')
    pair = [r.choice(a), r.choice(b)]
    targets = r.sample([j for j in range(6) if j not in pair], 2)
    return {'initial': initial, 'pair_A_B': pair, 'targets': targets}


def scores(root, arm):
    if arm == 'hidden':
        return None
    result = [p['p_B'] if p['answer'] == 'B' else 1 - p['p_B'] for p in root['initial']]
    a, b = root['pair_A_B']
    if arm == 'B_high':
        result[a], result[b] = LOW, HIGH
    elif arm == 'A_high':
        result[a], result[b] = HIGH, LOW
    elif arm == 'pair_equal':
        result[a] = result[b] = round((LOW + HIGH) / 2, 6)
    else:
        raise ValueError(arm)
    return result


def messages(item, member, root=None, visibility=None, arm=None):
    body = {'task': 'Predict whether product demand is LOW (A) or HIGH (B).',
            'generative_model': {'prior_probability_high': .5,
                'survey_accuracy': .6,
                'meaning': 'Each survey says high with probability 0.6 if demand is high, '
                           'and with probability 0.4 if demand is low. '
                           'All 18 survey observations are independent conditional on demand. '
                           'Every analyst initially observes exactly three distinct surveys. '
                           'Each observation must be counted once, not once per recommendation.'},
            'your_member_id': f'member-{member}',
            'your_surveys': [{'source_id': f'{item["id"]}-member-{member}-survey-{i}', 'signal': s}
                             for i, s in enumerate(item['signals'][member])]}
    if root is not None:
        body['your_previous_forecast'] = {k: root['initial'][member][k] for k in ('answer', 'p_B')}
        order = list(range(6))
        rng(SEED, item['id'], 'peer-order').shuffle(order)
        values = scores(root, arm)
        peers = []
        for j in order:
            if j == member:
                continue
            peer = {'member_id': f'member-{j}', 'answer': root['initial'][j]['answer']}
            if values is not None:
                peer['confidence'] = values[j]
            if visibility == 'full':
                peer['surveys'] = [{'source_id': f'{item["id"]}-member-{j}-survey-{i}', 'signal': s}
                                   for i, s in enumerate(item['signals'][j])]
            peers.append(peer)
        body['peer_reports'] = peers
    return [{'role': 'system', 'content': SYSTEM},
            {'role': 'user', 'content': json.dumps(body, sort_keys=True)}]


def advice_reference(item, member, root):
    """Ideal majority-report policy, ignoring scores; not a known LLM likelihood model."""
    probability = posterior(item['signals'][member])
    odds = probability / (1 - probability)
    # A majority of three iid 60%-accurate surveys is 64.8%-accurate.
    reliability = Fraction(81, 125)
    for j, report in enumerate(root['initial']):
        if j != member:
            odds *= reliability / (1 - reliability) if report['answer'] == 'B' else (1 - reliability) / reliability
    return float(odds / (1 + odds))


def source_hash():
    return digest({name: (Path(__file__).parent / name).read_text(encoding='utf-8')
                   for name in ('signal_visibility.py', 'runtime.py', 'design.py')})


def ci(values, label, strata=None):
    if len(values) < 2:
        return None
    r = rng(SEED, 'bootstrap', label)
    strata = strata or ['all'] * len(values)
    groups = [[v for v, s in zip(values, strata) if s == group] for group in sorted(set(strata))]
    samples = sorted(mean(list(itertools.chain.from_iterable(r.choices(g, k=len(g)) for g in groups))) for _ in range(2000))
    return [samples[49], samples[1949]]


def summarize(manifest, roots, initial, rows, records):
    items = {i['id']: i for i in manifest['items']}
    cell = {(r['item_id'], r['member'], r['visibility'], r['arm'], r['repeat']): r for r in rows}
    item_effects = []
    for item_id, root in sorted(roots.items()):
        values = {}
        for visibility in VISIBILITY:
            comparisons = []
            for j in root['targets']:
                for rep in range(2):
                    a, b = [cell.get((item_id, j, visibility, arm, rep), {}).get('parsed')
                            for arm in ('A_high', 'B_high')]
                    if a is not None and b is not None:
                        comparisons.append((b['p_B'] - a['p_B'], int(b['answer'] == 'B') - int(a['answer'] == 'B')))
            if len(comparisons) == 4:
                values[visibility] = {'p_B_shift': mean(x[0] for x in comparisons),
                                      'choose_B_shift': mean(x[1] for x in comparisons)}
        if len(values) == 2:
            item_effects.append({'item_id': item_id, **values,
                'interaction': values['advice']['p_B_shift'] - values['full']['p_B_shift']})
    primary = {}
    for key in ('full', 'advice', 'interaction'):
        v = [r['interaction'] if key == 'interaction' else r[key]['p_B_shift'] for r in item_effects]
        primary[key] = {'n_items': len(v), 'mean_p_B_shift': mean(v) if v else None,
                        'descriptive_item_bootstrap_95pct': ci(v, key, [items[r['item_id']]['state'] for r in item_effects])}
        if key != 'interaction':
            primary[key]['choose_B_shift'] = mean(r[key]['choose_B_shift'] for r in item_effects) if item_effects else None
    cells = {}
    for visibility in VISIBILITY:
        for arm in ARMS:
            valid = [r for r in rows if r['visibility'] == visibility and r['arm'] == arm and r['parsed'] is not None]
            cells[f'{visibility}/{arm}'] = {'n_valid': len(valid),
                'mean_p_B': mean(r['parsed']['p_B'] for r in valid) if valid else None,
                'Brier_realized_state': mean((r['parsed']['p_B'] - int(items[r['item_id']]['state'] == 'high'))**2 for r in valid) if valid else None,
                'MSE_full_information_posterior': mean((r['parsed']['p_B'] - items[r['item_id']]['posterior_full'])**2 for r in valid) if valid else None,
                'accuracy_realized_state': mean(r['parsed']['answer'] == ('B' if items[r['item_id']]['state'] == 'high' else 'A') for r in valid) if valid else None}
    # Sampled-repeat variation is descriptive, not a standard error for the treatment effect.
    repeat_differences = {v: [] for v in VISIBILITY}
    for item_id, root in roots.items():
        for j in root['targets']:
            for visibility in VISIBILITY:
                for arm in ARMS:
                    x, y = [cell.get((item_id, j, visibility, arm, k), {}).get('parsed') for k in (0, 1)]
                    if x is not None and y is not None:
                        repeat_differences[visibility].append(abs(x['p_B'] - y['p_B']))
    all_parsed = [r['parsed'] for r in initial + rows if r['parsed'] is not None]
    return {'protocol': PROTOCOL, 'backend': manifest['backend'],
            'planned_items': 16, 'eligible_mixed_roots': len(roots),
            'primary': primary, 'item_effects': item_effects, 'cells': cells,
            'mean_absolute_same_input_repeat_difference': {v: mean(x) if x else None for v, x in repeat_differences.items()},
            'answer_probability_inconsistencies': sum(p['answer'] != ('B' if p['p_B'] > .5 else 'A') for p in all_parsed),
            'usage': {'requests': len(records), 'valid': sum(r.get('valid', False) for r in records),
                      'known_cost_usd': sum(r.get('response', {}).get('usage', {}).get('cost', 0) or 0 for r in records),
                      'unknown_cost_requests': sum(r.get('response', {}).get('usage', {}).get('cost') is None for r in records)},
            'limitations': ['Only 16 independent tasks; exploratory pilot with two repeats per cell.',
                'Six real initial analysts; two unselected receivers per item are probed, not a group rollout.',
                'Self-reported p_B is a behavioral output, not internal model belief.',
                'Full posterior is a normative benchmark only with all raw signals.',
                'Advice reference assumes deterministic majority reports and ignores confidence.',
                'Influence alone does not establish harmful or irrational reliance.']}


def run(directory, backend, bank_seed=SEED, replication_of=None):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    model = json.loads(Path('configs/luna-reliable.json').read_text(encoding='utf-8'))['models']['luna']
    manifest = {'protocol': PROTOCOL, 'seed': SEED, 'backend': backend, 'items': bank(bank_seed), 'model': model,
                'max_tokens': 8192, 'max_requests': 608, 'repeats': 2, 'targets_per_item': 2,
                'arms': list(ARMS), 'visibility': list(VISIBILITY), 'low': LOW, 'high': HIGH,
                'source_hash': source_hash()}
    if bank_seed != SEED or replication_of is not None:
        manifest['bank_seed'] = bank_seed
        manifest['replication_of'] = replication_of
    path = directory / 'manifest.json'
    if path.exists():
        if json.loads(path.read_text(encoding='utf-8')) != manifest:
            raise ValueError('Frozen manifest differs; use a new directory')
    else:
        save(path, manifest)
        (directory / 'PROTOCOL.md').write_bytes(Path('SIGNAL_VISIBILITY_PROTOCOL.md').read_bytes())
        frozen = directory / 'frozen_source' / 'confidence_agents'
        frozen.mkdir(parents=True, exist_ok=True)
        for name in ('signal_visibility.py', 'runtime.py', 'design.py', '__init__.py'):
            (frozen / name).write_bytes((Path(__file__).parent / name).read_bytes())
    if backend == 'openrouter':
        snap = catalog({'luna': model})
        if not (directory / 'catalog.json').exists():
            save(directory / 'catalog.json', snap)
        if not os.environ.get('OPENROUTER_API_KEY'):
            os.environ['OPENROUTER_API_KEY'] = getpass.getpass('OpenRouter key: ')
    lock = directory / '.running'
    with lock.open('x'):
        pass
    stop = threading.Event()
    def sample(item, jobs):
        calls = Calls(directory / 'items' / item['id'], backend, 38, 8192)
        rows = []
        for job in jobs:
            if stop.is_set():
                break
            call_id = f"{item['id']}/{job['id']}"
            record_path = calls.directory / (digest(call_id) + '.json')
            if record_path.exists() and json.loads(record_path.read_text(encoding='utf-8'))['status'] != 'complete':
                parsed = None
            else:
                try:
                    parsed = calls.ask(call_id, model, job['messages'], initial=True)
                except Exception:
                    rec = json.loads(record_path.read_text(encoding='utf-8')) if record_path.exists() else {}
                    if rec.get('error_type') not in ('IncompleteRead', 'TimeoutError', 'URLError', 'RemoteDisconnected', 'ConnectionResetError'):
                        stop.set()
                        raise
                    parsed = None
            rows.append({k: v for k, v in job.items() if k != 'messages'} |
                        {'item_id': item['id'], 'parsed': parsed})
        return rows
    def batch(jobs, label):
        rows = []
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(sample, item, requests) for item, requests in jobs]
            for n, future in enumerate(as_completed(futures), 1):
                rows.extend(future.result())
                rows.sort(key=lambda r: (r['item_id'], r['id']))
                save(directory / f'{label}.json', rows)
                print(f'{label}: {n}/{len(futures)} items', flush=True)
        return rows
    try:
        initial = batch([(item, [{'id': f'initial/{j}', 'member': j, 'messages': messages(item, j)} for j in range(6)])
                         for item in manifest['items']], 'initial')
        roots = {}
        for item in manifest['items']:
            values = {r['member']: r['parsed'] for r in initial if r['item_id'] == item['id']}
            if len(values) == 6 and all(values.values()):
                root = root_design(item, [values[j] for j in range(6)])
                if root is not None:
                    roots[item['id']] = root
        save(directory / 'roots.json', roots)
        jobs = []
        for item in manifest['items']:
            if item['id'] not in roots:
                continue
            root = roots[item['id']]
            grid = list(itertools.product(root['targets'], VISIBILITY, ARMS, range(2)))
            rng(SEED, item['id'], 'request-order').shuffle(grid)
            jobs.append((item, [{'id': f'update/{j}/{v}/{a}/{rep}', 'member': j, 'visibility': v, 'arm': a, 'repeat': rep,
                                'messages': messages(item, j, root, v, a)} for j, v, a, rep in grid]))
        updates = batch(jobs, 'updates')
        records = [json.loads(p.read_text(encoding='utf-8')) for p in directory.glob('items/*/calls/*.json')]
        result = summarize(manifest, roots, initial, updates, records)
        save(directory / 'summary.json', result)
        print(json.dumps({k: v for k, v in result.items() if k not in ('item_effects', 'cells')}, indent=2), flush=True)
        return result
    finally:
        lock.unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', required=True)
    parser.add_argument('--backend', choices=('mock', 'openrouter'), default='mock')
    parser.add_argument('--bank-seed', type=int, default=SEED)
    parser.add_argument('--replication-of')
    args = parser.parse_args()
    run(args.directory, args.backend, args.bank_seed, args.replication_of)
