"""Post-hoc conditional interpretation; not a preregistered or uniquely normative model."""
import argparse
import json
import math
from pathlib import Path
from statistics import mean


def analyze(directory):
    directory = Path(directory)
    rd = lambda n: json.loads((directory / n).read_text(encoding='utf-8'))
    manifest, roots, rows = rd('manifest.json'), rd('roots.json'), rd('updates.json')
    assert (directory / 'summary.json').exists(), 'Use only after the frozen experiment finishes'
    items = {i['id']: i for i in manifest['items']}
    def logit(p):
        p = min(1-1e-9, max(1e-9, p))
        return math.log(p / (1-p))
    def prediction(item, root, member, arm):
        h = item['signals'][member].count('high')
        log_odds = (2*h-3)*math.log(1.5)
        a, b = root['pair_A_B']
        for j, initial in enumerate(root['initial']):
            if j == member:
                continue
            c = initial['p_B'] if initial['answer'] == 'B' else 1-initial['p_B']
            if arm == 'hidden':
                c = .648  # Assumed majority-of-three report policy, ignoring all scores.
            elif j in (a, b):
                if arm == 'pair_equal':
                    c = round((manifest['low']+manifest['high'])/2, 6)
                else:
                    c = manifest['high'] if (j == a) == (arm == 'A_high') else manifest['low']
            log_odds += logit(c) if initial['answer'] == 'B' else -logit(c)
        return 1/(1+math.exp(-log_odds))
    per_item = []
    errors = {'full': [], 'advice': []}
    for item_id, root in sorted(roots.items()):
        item = items[item_id]
        predicted_shift = mean(prediction(item, root, j, 'B_high')-prediction(item, root, j, 'A_high')
                               for j in root['targets'])
        per_item.append({'item_id': item_id, 'conditional_model_advice_shift': predicted_shift})
        for row in rows:
            if row['item_id'] != item_id or row['parsed'] is None:
                continue
            pred = item['posterior_full'] if row['visibility'] == 'full' else prediction(item, root, row['member'], row['arm'])
            errors[row['visibility']].append(abs(pred-row['parsed']['p_B']))
    result = {'status': 'post_hoc_conditional_interpretation',
        'timing': 'Specified during the live run, after inspection of the first completed item; not confirmatory.',
        'assumptions': ['Displayed peer scores are interpreted as calibrated private posteriors with prior 1/2.',
                        'Private observations are independent given demand.',
                        'With full raw evidence, recommendations and scores add no state information.',
                        'With hidden scores, reports follow the majority-of-three policy.'],
        'caveat': 'Displayed scores were experimentally replaced. This predicts a recipient interpreting reports as calibrated; it is not the true posterior under the intervention and does not identify an internal mechanism.',
        'mean_conditional_model_advice_shift': mean(x['conditional_model_advice_shift'] for x in per_item) if per_item else None,
        'mean_absolute_difference_from_reported_probability': {k: mean(v) if v else None for k,v in errors.items()},
        'per_item': per_item}
    (directory / 'posthoc_conditional_model.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='per_item'}, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('directory')
    analyze(parser.parse_args().directory)
