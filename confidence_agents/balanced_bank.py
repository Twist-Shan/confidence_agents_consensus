"""Freeze a truth-balanced bank without consulting any model outputs."""
import argparse
import json
from collections import Counter
from pathlib import Path

from .calibration import candidates, render
from .design import rng, digest
from .runtime import save


def build(seed=20260921, per_class=20, max_candidates=1000):
    if per_class <= 0 or per_class % 2:
        raise ValueError("per_class must be a positive even integer for A/B balance")
    selected = {"Yes": [], "No": []}
    seen = set()
    audit = []
    for task in candidates(seed, max_candidates, families=("logic",), levels=(2,)):
        semantic = task["options"]["AB".index(task["truth"])]
        fingerprint = digest(task["problem"])
        accepted = len(selected[semantic]) < per_class and fingerprint not in seen
        audit.append({"id": task["id"], "semantic": semantic, "selected": accepted})
        if accepted:
            selected[semantic].append(task)
            seen.add(fingerprint)
        if all(len(items) == per_class for items in selected.values()):
            break
    if any(len(items) != per_class for items in selected.values()):
        raise ValueError("Candidate cap exhausted before obtaining both truth quotas")
    bank = []
    for semantic, items in selected.items():
        labels = ["A"]*(per_class//2) + ["B"]*(per_class//2)
        rng(seed, "balanced-option-labels", semantic).shuffle(labels)
        for item, label in zip(items, labels):
            other = "No" if semantic == "Yes" else "Yes"
            options = [semantic, other] if label == "A" else [other, semantic]
            item.update(options=options, truth=label,
                        question=render(item["problem"])+f"\nA: {options[0]}\nB: {options[1]}")
            bank.append(item)
    rng(seed, "balanced-bank-order").shuffle(bank)
    return {"status": "unvalidated", "seed": seed,
            "construction": {"family":"logic", "level":2, "per_semantic_class":per_class,
                             "candidate_cap":max_candidates, "candidates_examined":len(audit),
                             "rule":"First unique items per exact semantic truth, then shuffled balanced A/B labels; no model outcomes used",
                             "audit":audit},
            "sampling_plan": {"samples_per_item":6, "maximum_calls":len(bank)*6,
                              "model":"openai/gpt-5.6-luna", "max_tokens":2048,
                              "reasoning_effort":"provider default", "workers":4,
                              "selection_accuracy_interval":[.3,.85], "max_invalid_rate":.1,
                              "min_mixed_groups":1, "analysis":"Report semantic and answer-label strata, mixed groups, and self-reported confidence on wrong answers"},
            "tasks": bank}


def main():
    p = argparse.ArgumentParser(description="Build a balanced L2 bank offline")
    p.add_argument("--out", required=True)
    p.add_argument("--seed", type=int, default=20260921)
    p.add_argument("--per-class", type=int, default=20)
    p.add_argument("--max-candidates", type=int, default=1000)
    args = p.parse_args()
    path = Path(args.out)
    if path.exists():
        raise ValueError("Refusing to overwrite a frozen bank")
    document = build(args.seed,args.per_class,args.max_candidates)
    save(path,document)
    counts=Counter((x["options"]["AB".index(x["truth"])],x["truth"]) for x in document["tasks"])
    print(json.dumps({"items":len(document["tasks"]),"candidates_examined":document["construction"]["candidates_examined"],
                      "cells":{f"{s}/{a}":n for (s,a),n in counts.items()}},indent=2))


if __name__ == "__main__":
    main()
