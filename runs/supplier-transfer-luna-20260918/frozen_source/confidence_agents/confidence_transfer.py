"""Frozen-evidence, genuine-root local-to-group pilot. Standard library only."""
import argparse
import getpass
import itertools
import json
import math
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from statistics import mean

from .design import digest, rng
from .runtime import Calls, catalog, save

ARMS = ('aligned', 'misaligned', 'equal', 'hidden')
GROUP_ARMS = ('aligned', 'misaligned', 'hidden')
SEED = 20260918
PROTOCOL = 'supplier-confidence-transfer-v1'
SYSTEM = ('You are one of six equal committee members choosing supplier A or B. '
          'The only objective is to maximize expected net benefit under the stated accounting rules. '
          'Audit records are verified facts. Count each source_id exactly once, even if repeated. '
          'Recommendations can be mistaken. If a confidence field is present, it is the reporting '
          "member's stated probability that their recommended supplier is better; it is not a guarantee. "
          'Return only JSON with answer (A or B).')


def bank(seed=SEED):
    """Select by numerical properties only, before any model responses exist."""
    items = []
    seen = set()
    for split in ('train', 'test'):
        for k in range(8):
            r = rng(seed, 'supplier', split, k)
            sign = 1 if k % 2 == 0 else -1
            margin_range = (1, 4) if (k // 2) % 2 == 0 else (5, 10)
            for attempt in range(100000):
                public = r.choice((-6, -4, 4, 6))
                private = [r.randint(-12, 12) for _ in range(6)]
                total = public + sum(private)
                signature = (public, *sorted(private))
                partial = [public + d for d in private]
                if (margin_range[0] <= total * sign <= margin_range[1]
                        and min(partial) < 0 < max(partial) and 0 not in partial
                        and signature not in seen):
                    break
            else:
                raise ValueError('Task rejection sampler exhausted')
            seen.add(signature)
            item_id = f'{split}-{k:02d}'
            cards = []
            # Store both supplier amounts; truth is independently checked by summing each column.
            for j, delta in enumerate([public] + private):
                b = r.randint(30, 90)
                cards.append({'source_id': f'{item_id}-audit-{j}',
                              'component': 'public contract adjustment' if j == 0 else f'audit component {j}',
                              'A_net_benefit': b + delta, 'B_net_benefit': b})
            items.append({'id': item_id, 'split': split, 'truth': 'A' if total > 0 else 'B',
                          'public': cards[0], 'private': cards[1:], 'net_A_minus_B': total,
                          'private_deltas': private, 'public_delta': public,
                          'margin_band': list(margin_range), 'sampling_attempt': attempt})
    return items


def messages(item, member=None, state=None, scores=None, oracle=False):
    # Explicit allowlist prevents experimental truth/split/arm labels entering prompts.
    body = {'task': 'Choose the supplier with the larger expected total net benefit. '
                    'Total benefit is the sum of seven audit components, counting each once.',
            'accounting_assumption': 'Before disclosure, use the stipulated decision prior: '
                    'each unseen component has an independent A-minus-B difference uniform over '
                    'the integers -12 through 12. Its expected difference is zero. '
                    'After disclosure, replace that prior with its verified amounts. '
                    'Initial recommendations were made before all components were disclosed.',
            'public_record': item['public']}
    if oracle:
        body['all_other_records'] = item['private']
    else:
        body['your_member_id'] = f'member-{member}'
        body['your_private_record'] = item['private'][member]
    if state is not None:
        body['your_previous_answer'] = state[member]
        order = list(range(6))
        rng(SEED, item['id'], 'peer-order').shuffle(order)
        body['peer_reports'] = [dict(member_id=f'member-{j}', answer=state[j],
                                    audit_record=item['private'][j],
                                    **({} if scores is None else {'confidence': scores[j]}))
                                for j in order if j != member]
    return [{'role': 'system', 'content': SYSTEM},
            {'role': 'user', 'content': json.dumps(body, sort_keys=True)}]


def choose_pair(item, state):
    r = rng(SEED, item['id'], 'pair')
    correct = [j for j, a in enumerate(state) if a == item['truth']]
    wrong = [j for j, a in enumerate(state) if a != item['truth']]
    return [r.choice(correct), r.choice(wrong)] if correct and wrong else None


def allocation(pair, arm):
    if arm == 'hidden':
        return None
    scores = [.75] * 6
    if arm in ('aligned', 'misaligned') and pair is not None:
        a, b = pair
        scores[a], scores[b] = ((.95, .55) if arm == 'aligned' else (.55, .95))
    return scores


def features(item, member, state, scores, with_confidence=True):
    signs = [1 if a == 'B' else -1 for a in state]
    peers = [j for j in range(6) if j != member]
    result = [1., -item['net_A_minus_B'] / 10, signs[member],
              mean(signs[j] for j in peers), -item['private_deltas'][member] / 12]
    if with_confidence:
        result += [0. if scores is None else mean((scores[j] - .75) * signs[j] / .2 for j in peers),
                   float(scores is not None)]
    return result


def sigmoid(x):
    return 1 / (1 + math.exp(-max(-35., min(35., x))))


def fit(rows, items, roots, with_confidence):
    data = []
    for row in rows:
        if row['answer'] is None:
            continue
        item = items[row['item_id']]
        root = roots[item['id']]
        data.append((features(item, row['member'], root['state'],
                              allocation(root['pair'], row['arm']), with_confidence),
                     int(row['answer'] == 'B')))
    if not data:
        raise ValueError('No valid local training data')
    w = [0.] * len(data[0][0])
    # Fixed optimizer and regularization; no tuning using test outcomes.
    for _ in range(2000):
        gradient = [0.] * len(w)
        for x, y in data:
            error = sigmoid(sum(a * b for a, b in zip(w, x))) - y
            for j in range(len(w)):
                gradient[j] += error * x[j] / len(data)
        for j in range(len(w)):
            w[j] -= .2 * (gradient[j] + (.01 * w[j] if j else 0))
    return {'weights': w, 'with_confidence': with_confidence, 'n': len(data),
            'regularization': .01, 'iterations': 2000, 'learning_rate': .2}


STATES = list(itertools.product('AB', repeat=6))


def state_distribution(probabilities):
    return {s: math.prod(p if a == 'B' else 1 - p for a, p in zip(s, probabilities)) for s in STATES}


def predict(item, state, pair, arm, model):
    def probabilities(previous, scores):
        return [sigmoid(sum(w * x for w, x in zip(model['weights'],
                    features(item, j, previous, scores, model['with_confidence'])))) for j in range(6)]
    first = state_distribution(probabilities(state, allocation(pair, arm)))
    second = dict.fromkeys(STATES, 0.)
    for previous, mass in first.items():
        for nxt, conditional in state_distribution(probabilities(previous, None)).items():
            second[nxt] += mass * conditional
    def metrics(distribution):
        return {'wrong_fraction': sum(p * sum(a != item['truth'] for a in s) / 6 for s, p in distribution.items()),
                'wrong_consensus': sum(p for s, p in distribution.items() if all(a != item['truth'] for a in s)),
                'p_B_by_member': [sum(p for s, p in distribution.items() if s[j] == 'B') for j in range(6)]}
    return [metrics(first), metrics(second)]


def source_hash():
    return digest({name: (Path(__file__).parent / name).read_text(encoding='utf-8')
                   for name in ('confidence_transfer.py', 'runtime.py', 'design.py')})


class Runner:
    def __init__(self, directory, backend, manifest):
        self.directory, self.backend, self.manifest = Path(directory), backend, manifest
        self.stop = threading.Event()

    def sample_item(self, item, jobs):
        folder = self.directory / 'items' / item['id']
        calls = Calls(folder, self.backend, 64, self.manifest['max_tokens'])
        rows = []
        for job in jobs:
            if self.stop.is_set():
                break
            call_id = f"{item['id']}/{job['id']}"
            path = folder / 'calls' / (digest(call_id) + '.json')
            if path.exists() and json.loads(path.read_text(encoding='utf-8'))['status'] != 'complete':
                parsed = None  # Preserve uncertain/failed calls; never resend automatically.
            else:
                try:
                    parsed = calls.ask(call_id, self.manifest['model'], job['messages'])
                except Exception:
                    record = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
                    if record.get('error_type') not in ('IncompleteRead', 'TimeoutError', 'URLError',
                                                       'RemoteDisconnected', 'ConnectionResetError'):
                        self.stop.set()
                        raise
                    parsed = None
            rows.append({k: v for k, v in job.items() if k != 'messages'} |
                        {'item_id': item['id'], 'answer': parsed['answer'] if parsed else None})
        return rows

    def batch(self, jobs_by_item, label):
        rows = []
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(self.sample_item, item, jobs) for item, jobs in jobs_by_item]
            for i, future in enumerate(as_completed(futures), 1):
                rows.extend(future.result())
                save(self.directory / f'{label}.json', sorted(rows, key=lambda r: (r['item_id'], r['id'])))
                print(f'{label}: {i}/{len(futures)} items', flush=True)
        return rows


def interval(values, label):
    if len(values) < 2:
        return None
    r = rng(SEED, 'bootstrap', label)
    samples = sorted(mean(r.choices(values, k=len(values))) for _ in range(2000))
    return [samples[49], samples[1949]]


def report(directory, manifest, roots, local, groups, predictions, initial):
    directory = Path(directory)
    items = {x['id']: x for x in manifest['items']}
    local_contrasts = []
    for item_id, root in roots.items():
        if items[item_id]['split'] != 'train' or root['pair'] is None:
            continue
        by_member = {}
        for row in local:
            if row['item_id'] == item_id and row['member'] not in root['pair'] and row['answer']:
                by_member.setdefault(row['member'], {})[row['arm']] = row['answer'] != items[item_id]['truth']
        deltas = [int(v['misaligned']) - int(v['aligned']) for v in by_member.values()
                  if {'aligned', 'misaligned'} <= v.keys()]
        if len(deltas) == 4:
            local_contrasts.append(mean(deltas))
    group_contrasts, errors, scores = {}, {}, {}
    for t in (1, 2):
        effects = []
        for item in manifest['items']:
            if item['split'] != 'test' or item['id'] not in roots or roots[item['id']]['pair'] is None:
                continue
            arm_values = {}
            for arm in GROUP_ARMS:
                rows = [r for r in groups if r['item_id'] == item['id'] and r['arm'] == arm and r['round'] == t]
                if len(rows) != 6 or any(r['answer'] is None for r in rows):
                    continue
                wrong = mean(r['answer'] != item['truth'] for r in rows)
                arm_values[arm] = wrong
                errors.setdefault(f'round{t}/{arm}', []).append(wrong)
                for name in ('confidence', 'no_confidence'):
                    prediction = predictions[item['id']][arm][name][t-1]
                    key = f'round{t}/{name}'
                    brier = mean((prediction['p_B_by_member'][r['member']] - (r['answer'] == 'B'))**2 for r in rows)
                    scores.setdefault(key, {}).setdefault(item['id'], []).append(brier)
            if {'aligned', 'misaligned'} <= arm_values.keys():
                effects.append(arm_values['misaligned'] - arm_values['aligned'])
        group_contrasts[f'round{t}'] = {'n_items': len(effects), 'delta': mean(effects) if effects else None,
                                      'descriptive_item_bootstrap_95pct': interval(effects, f'group-{t}')}
    records = [json.loads(p.read_text(encoding='utf-8')) for p in directory.glob('items/*/calls/*.json')]
    costs = [r.get('response', {}).get('usage', {}).get('cost') for r in records]
    transitions = {}
    for arm in ARMS:
        for own_correct in (True, False):
            subset = [r for r in local if r['arm'] == arm and r['answer'] is not None
                      and r['member'] not in roots[r['item_id']]['pair']
                      and (roots[r['item_id']]['state'][r['member']] == items[r['item_id']]['truth']) == own_correct]
            transitions[f'{arm}/initial_{"correct" if own_correct else "wrong"}'] = {
                'n_member_responses': len(subset),
                'flip_rate': mean(r['answer'] != roots[r['item_id']]['state'][r['member']] for r in subset) if subset else None}
    prediction_contrasts = {f'round{t}/{name}': mean(
                arms['misaligned'][name][t-1]['wrong_fraction'] - arms['aligned'][name][t-1]['wrong_fraction']
                for arms in predictions.values()) if predictions else None
                for t in (1, 2) for name in models_names()}
    brier_differences = {}
    for t in (1, 2):
        conf, baseline = [scores.get(f'round{t}/{name}', {}) for name in models_names()]
        paired = [mean(conf[k]) - mean(baseline[k]) for k in sorted(conf.keys() & baseline.keys())]
        brier_differences[f'round{t}'] = {'n_items': len(paired),
            'confidence_minus_baseline': mean(paired) if paired else None,
            'descriptive_item_bootstrap_95pct': interval(paired, f'brier-{t}')}
    group_outcomes = {}
    for t in (1, 2):
        for arm in GROUP_ARMS:
            values = errors.get(f'round{t}/{arm}', [])
            group_outcomes[f'round{t}/{arm}'] = {'n_items': len(values),
                'wrong_majority': sum(v > .5 for v in values), 'tie': sum(v == .5 for v in values),
                'correct_majority': sum(v < .5 for v in values), 'wrong_consensus': sum(v == 1 for v in values)}
    summary = {'protocol': PROTOCOL, 'backend': manifest['backend'], 'empirical': manifest['backend'] != 'mock',
               'roots_complete': len(roots), 'roots_mixed': sum(v['pair'] is not None for v in roots.values()),
               'oracle': {'valid': sum(r['answer'] is not None for r in initial if r['id'] == 'oracle'),
                          'correct': sum(r['answer'] == items[r['item_id']]['truth'] for r in initial if r['id'] == 'oracle')},
               'local_primary': {'n_items': len(local_contrasts), 'delta': mean(local_contrasts) if local_contrasts else None,
                                 'descriptive_item_bootstrap_95pct': interval(local_contrasts, 'local')},
               'group_primary': group_contrasts,
               'local_transitions': transitions, 'group_outcomes': group_outcomes,
               'predicted_treatment_contrasts': prediction_contrasts,
               'prediction_Brier_paired_comparison': brier_differences,
               'group_error_rates': {k: {'n_items': len(v), 'mean': mean(v)} for k, v in errors.items()},
               'prediction_Brier': {k: mean(mean(v) for v in by_item.values()) for k, by_item in scores.items()},
               'usage': {'requests': len(records), 'valid': sum(r.get('valid', False) for r in records),
                         'known_cost_usd': sum(c for c in costs if isinstance(c, (int, float))),
                         'unknown_cost_requests': sum(c is None for c in costs)},
               'limitations': ['8 training and 8 held-out tasks; exploratory pilot, one root per task.',
                   'Full evidence disclosed; measures response to scores with verifiable evidence.',
                   'Initial wrong means ex-post suboptimal, not irrational given private evidence.',
                   'Prediction uses conditional independence and a one-step Markov approximation.',
                   'Second-round prediction extrapolates beyond initial-state training support.',
                   'Prediction Brier targets observed agent choices, not supplier truth.',
                   'Zero bootstrap width with all-zero effects is not proof of equivalence.']}
    save(directory / 'summary.json', summary)
    (directory / 'REPORT.md').write_text('# Confidence allocation transfer pilot\n\n'
        + ('MOCK ONLY — not empirical evidence.\n\n' if manifest['backend'] == 'mock' else '')
        + 'Frozen protocol: `PROTOCOL.md`. Predictions were saved before held-out group calls.\n\n'
        + '```json\n' + json.dumps(summary, indent=2, ensure_ascii=False) + '\n```\n', encoding='utf-8')
    return summary


def models_names():
    return ('confidence', 'no_confidence')


def run(directory, backend):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    config = json.loads(Path('configs/luna-reliable.json').read_text(encoding='utf-8'))
    manifest = {'protocol': PROTOCOL, 'seed': SEED, 'items': bank(), 'model': config['models']['luna'],
                'max_tokens': 8192, 'maximum_requests': 592, 'backend': backend, 'source_hash': source_hash(),
                'local_repeats': 1, 'group_rounds': 2, 'confidence_intervention': 'first update only',
                'local_arms': list(ARMS), 'group_arms': list(GROUP_ARMS)}
    manifest_path = directory / 'manifest.json'
    if manifest_path.exists():
        if json.loads(manifest_path.read_text(encoding='utf-8')) != manifest:
            raise ValueError('Frozen manifest differs; use a new directory')
    else:
        save(manifest_path, manifest)
        (directory / 'PROTOCOL.md').write_text(Path('TRANSFER_PROTOCOL.md').read_text(encoding='utf-8'), encoding='utf-8')
    if backend == 'openrouter':
        snapshot = catalog({'luna': manifest['model']})
        if not (directory / 'catalog.json').exists():
            save(directory / 'catalog.json', snapshot)
        if not os.environ.get('OPENROUTER_API_KEY'):
            os.environ['OPENROUTER_API_KEY'] = getpass.getpass('OpenRouter key: ')
    lock = directory / '.running'
    with lock.open('x'):
        pass
    try:
        runner = Runner(directory, backend, manifest)
        items = manifest['items']
        jobs = [(item, [{'id': f'initial/{j}', 'member': j, 'messages': messages(item, j)} for j in range(6)]
                       + [{'id': 'oracle', 'member': None, 'messages': messages(item, oracle=True)}]) for item in items]
        initial = runner.batch(jobs, 'initial')
        roots = {}
        for item in items:
            answers = {r['member']: r['answer'] for r in initial if r['item_id'] == item['id'] and r['member'] is not None}
            if len(answers) == 6 and all(answers.values()):
                state = [answers[j] for j in range(6)]
                roots[item['id']] = {'state': state, 'pair': choose_pair(item, state)}
        save(directory / 'roots.json', roots)
        jobs = []
        for item in items:
            if item['split'] != 'train' or item['id'] not in roots:
                continue
            root = roots[item['id']]
            if root['pair'] is None:
                continue
            cells = [(arm, j) for arm in ARMS for j in range(6)]
            rng(SEED, item['id'], 'local-order').shuffle(cells)
            jobs.append((item, [{'id': f'local/{arm}/{j}', 'member': j, 'arm': arm,
                                'messages': messages(item, j, root['state'], allocation(root['pair'], arm))}
                               for arm, j in cells]))
        local = runner.batch(jobs, 'local')
        models = {name: fit(local, {x['id']: x for x in items}, roots, use)
                  for name, use in [('confidence', True), ('no_confidence', False)]}
        save(directory / 'response_models.json', models)
        predictions = {item['id']: {arm: {name: predict(item, roots[item['id']]['state'], roots[item['id']]['pair'], arm, model)
                              for name, model in models.items()} for arm in GROUP_ARMS}
                       for item in items if item['split'] == 'test' and item['id'] in roots and roots[item['id']]['pair'] is not None}
        predpath = directory / 'predictions_before_group.json'
        if predpath.exists() and json.loads(predpath.read_text(encoding='utf-8')) != predictions:
            raise ValueError('Previously frozen predictions differ')
        if not predpath.exists():
            save(predpath, predictions)
        print('Predictions frozen before group evaluation', flush=True)
        groups = []
        for t in (1, 2):
            jobs = []
            for item in items:
                if item['id'] not in predictions:
                    continue
                root = roots[item['id']]
                cells = []
                arms = list(GROUP_ARMS)
                rng(SEED, item['id'], t, 'group-order').shuffle(arms)
                for arm in arms:
                    if t == 1:
                        state = root['state']
                    else:
                        previous = {r['member']: r['answer'] for r in groups if r['item_id'] == item['id'] and r['arm'] == arm and r['round'] == 1}
                        if len(previous) != 6 or not all(previous.values()):
                            continue  # Missing outcome is never replaced with the previous answer.
                        state = [previous[j] for j in range(6)]
                    scores = allocation(root['pair'], arm) if t == 1 else None
                    for j in range(6):
                        cells.append({'id': f'group/{arm}/{t}/{j}', 'member': j, 'arm': arm, 'round': t,
                                      'messages': messages(item, j, state, scores)})
                jobs.append((item, cells))
            groups.extend(runner.batch(jobs, f'group_round{t}'))
        save(directory / 'group_results.json', groups)
        result = report(directory, manifest, roots, local, groups, predictions, initial)
        print(json.dumps(result, indent=2), flush=True)
        return result
    finally:
        lock.unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', required=True)
    parser.add_argument('--backend', choices=['mock', 'openrouter'], default='mock')
    args = parser.parse_args()
    run(args.directory, args.backend)
