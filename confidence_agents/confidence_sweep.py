"""Frozen eight-condition confidence-gap exploration; no outcome-based stopping."""
import argparse
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean

from .design import prompt, rng
from .local_replay import run, summarize as paired_summary

GAPS = {'10': (.80, .70), '30': (.90, .60), '40': (.95, .55)}
ARMS = tuple(f'{side}_{gap}' for gap in GAPS for side in ('correct_high', 'wrong_high')) + ('equal', 'hidden')


def messages(context, arm):
    if arm not in ARMS:
        raise ValueError(arm)
    peers = []
    for peer in context['peers']:
        report = peer.copy()
        if arm == 'equal':
            report['confidence'] = .75
        elif arm != 'hidden':
            side, gap = arm.rsplit('_', 1)
            high = (peer['answer'] == context['task']['truth']) == (side == 'correct_high')
            report['confidence'] = GAPS[gap][0 if high else 1]
        peers.append(report)
    result = prompt(context['task']['question'], context['own'], peers)
    result[0]['content'] += ' If shown, confidence is the peer\'s reported probability that its own selected answer is correct.'
    return result


def summarize(rows, repeats, backend, seed):
    contrasts = {}
    for gap in GAPS:
        subset = []
        for row in rows:
            if row['arm'] in ('equal', 'hidden', f'correct_high_{gap}', f'wrong_high_{gap}'):
                mapped = row.copy()
                mapped['arm'] = row['arm'].removesuffix('_' + gap)
                subset.append(mapped)
        contrasts[gap] = paired_summary(subset, repeats, backend, seed)
    # Per-item least-squares slope of paired effects against positive score gaps.
    # Equal/hidden are controls; no artificial zero-effect observation is inserted.
    effects = {gap: {r['item_id']: r for r in summary['item_effects'] if r['complete_primary_pair']}
               for gap, summary in contrasts.items()}
    common = sorted(set.intersection(*(set(x) for x in effects.values())))
    xs = [.10, .30, .40]
    center = mean(xs)
    denominator = sum((x-center)**2 for x in xs)
    clusters = defaultdict(list)
    slopes = []
    for item in common:
        ys = [effects[g][item]['delta_wrong_high_minus_correct_high'] for g in GAPS]
        slope = sum((x-center)*y for x,y in zip(xs,ys))/denominator
        slopes.append(slope)
        r = effects['10'][item]
        clusters[r['semantic'], r['truth'], r['own_correct']].append(slope)
    interval = None
    if len(slopes) >= 2:
        random = rng(seed, 'gap-slope-bootstrap')
        boot = sorted(mean(v for group in clusters.values() for v in random.choices(group,k=len(group))) for _ in range(2000))
        interval = [boot[49], boot[1949]]
    return {'backend':backend, 'is_empirical':backend=='openrouter',
            'primary': 'Slope of wrong-high minus correct-high error rate against confidence gap; per unit gap',
            'primary_complete_items':len(common), 'primary_slope':mean(slopes) if slopes else None,
            'descriptive_stratified_item_bootstrap_95pct':interval, 'gap_contrasts':contrasts,
            'note':'Exploratory reuse of 40 tasks. All three gap contrasts are secondary and their intervals are unadjusted. No stopping based on outcomes. Synthetic own and peer answers; single update.'}


SPEC = {'arms': ARMS, 'messages':messages, 'summarize':summarize,
        'manifest':{'protocol':'confidence-gap-eight-arm-v1',
                    'primary':'Per-item slope of paired error-rate differences against gaps .10,.30,.40, then equal item average',
                    'analysis':'Complete items for slope; stratified paired item bootstrap 2000; all gap contrasts and missing-response bounds reported; no outcome-based stopping',
                    'peer_design':'Four synthetic peers, two correct and two wrong; average confidence .75; gaps .10,.30,.40 crossed with correctness, equal .75, hidden',
                    'confidence_definition':'Reported probability that the peer own selected answer is correct',
                    'scores':GAPS}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend', choices=['mock','openrouter'], default='mock')
    parser.add_argument('--out', required=True)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--max-requests', type=int, default=960)
    args = parser.parse_args()
    config = json.loads(Path('configs/luna-reliable.json').read_text())
    result = run(config, 'data/logic-l2-balanced-20260921.json', args.out,
                 backend=args.backend, workers=args.workers, cap=args.max_requests, spec=SPEC)
    print(json.dumps({k:v for k,v in result.items() if k!='gap_contrasts'}, indent=2))


if __name__ == '__main__':
    main()
