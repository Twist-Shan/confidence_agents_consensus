"""Preflight: original prompt semantics and independently generated task overlap."""
import importlib.util
import json
from pathlib import Path

from confidence_agents import signal_visibility as current


def check():
    original = Path('runs/signal-visibility-luna-20260919')
    spec = importlib.util.spec_from_file_location('confidence_agents.frozen_visibility',
        original / 'frozen_source/confidence_agents/signal_visibility.py')
    frozen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(frozen)
    old = json.loads((original / 'manifest.json').read_text(encoding='utf-8'))
    assert current.bank() == frozen.bank() == old['items']
    new = current.bank(20260920)
    assert sum(i['state'] == 'high' for i in new) == 8
    roots = json.loads((original / 'roots.json').read_text(encoding='utf-8'))
    comparisons = 0
    for item in old['items'] + new:
        root = roots[item['id']]
        for j in range(6):
            assert current.messages(item, j) == frozen.messages(item, j)
            for v in current.VISIBILITY:
                for a in current.ARMS:
                    assert current.messages(item, j, root, v, a) == frozen.messages(item, j, root, v, a)
                    comparisons += 1
        assert current.root_design(item, root['initial']) == frozen.root_design(item, root['initial'])
    signature = lambda i: tuple(tuple(s) for s in i['signals'])
    counts = lambda i: tuple(s.count('high') for s in i['signals'])
    matches = lambda fn: sum(any(fn(i) == fn(j) for j in old['items']) for i in new)
    result = {'bank_seed': 20260920, 'design_seed': current.SEED,
              'prompt_comparisons_passed': comparisons,
              'exact_signal_overlap_new_items': matches(signature),
              'member_signal_count_overlap_new_items': matches(counts),
              'unordered_member_count_overlap_new_items': matches(lambda i: tuple(sorted(counts(i)))),
              'within_new_exact_duplicates': len(new) - len({signature(i) for i in new}),
              'original_bank_preserved': True}
    target = Path('runs/signal-visibility-replication-20260920')
    target.mkdir(parents=True, exist_ok=True)
    (target / 'PREFLIGHT.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    (target / 'REPLICATION_PLAN.md').write_bytes(Path('REPLICATION_PLAN_20260920.md').read_bytes())
    (target / 'planned_items.json').write_text(json.dumps(new, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    check()
