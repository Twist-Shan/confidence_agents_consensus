"""Four-arm local replay: only displayed confidence changes within a task."""
import argparse
import json
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from statistics import mean

from .calibration import load_frozen_bank
from .design import prompt, rng
from .experiment import source_hash
from .runtime import Calls, catalog, save

ARMS = ("correct_high", "wrong_high", "equal", "hidden")


def contexts(bank, seed):
    strata = defaultdict(list)
    for task in bank:
        semantic = task["options"]["AB".index(task["truth"])]
        strata[semantic, task["truth"]].append(task)
    result = []
    for stratum, tasks in sorted(strata.items()):
        if len(tasks) % 2:
            raise ValueError("Each semantic/answer-label stratum needs an even number of tasks")
        tasks = sorted(tasks, key=lambda x: x["id"])
        own_correct = [True]*(len(tasks)//2)+[False]*(len(tasks)//2)
        rng(seed, "own-status", stratum).shuffle(own_correct)
        for task, correct in zip(tasks, own_correct):
            wrong = "B" if task["truth"] == "A" else "A"
            answers = [task["truth"]]*2 + [wrong]*2
            rng(seed, task["id"], "peer-identities").shuffle(answers)
            peers = [{"agent":f"peer-{i}", "answer":a} for i,a in enumerate(answers)]
            rng(seed, task["id"], "peer-order").shuffle(peers)
            result.append({"task":task, "semantic":stratum[0], "own_correct":correct,
                           "own":task["truth"] if correct else wrong, "peers":peers})
    return sorted(result, key=lambda x: x["task"]["id"])


def messages(context, arm):
    if arm not in ARMS:
        raise ValueError(arm)
    peers = []
    for peer in context["peers"]:
        report = peer.copy()
        if arm != "hidden":
            if arm == "equal":
                score = .75
            else:
                high = (peer["answer"] == context["task"]["truth"]) == (arm == "correct_high")
                score = .95 if high else .55
            report["confidence"] = score
        peers.append(report)
    return prompt(context["task"]["question"], context["own"], peers)


def summarize(rows, repeats, backend, seed):
    items = defaultdict(list)
    for row in rows:
        items[row["item_id"]].append(row)
    item_effects = []
    for item_id, records in items.items():
        cells = {a:[r for r in records if r["arm"]==a] for a in ARMS}
        if any(len(cells[a]) != repeats for a in ARMS):
            continue
        a,b = cells["correct_high"],cells["wrong_high"]
        valid_pair = all(r["answer"] is not None for r in a+b)
        low = sum(r["wrong"] is True for r in b)/repeats - sum(r["wrong"] is not False for r in a)/repeats
        high = sum(r["wrong"] is not False for r in b)/repeats - sum(r["wrong"] is True for r in a)/repeats
        item_effects.append({"item_id":item_id,"semantic":records[0]["semantic"],
                             "truth":records[0]["truth"],"own_correct":records[0]["own_correct"],
                             "complete_primary_pair":valid_pair,
                             "delta_wrong_high_minus_correct_high":mean(r["wrong"] for r in b)-mean(r["wrong"] for r in a) if valid_pair else None,
                             "missing_response_bounds":[low,high]})
    def arm_stats(sub):
        result = {}
        for arm in ARMS:
            calls = [r for r in sub if r["arm"]==arm]
            by_item = defaultdict(list)
            for r in calls:
                if r["answer"] is not None:
                    by_item[r["item_id"]].append(r["wrong"])
            result[arm] = {"requests":len(calls),"valid":sum(len(v) for v in by_item.values()),
                           "invalid":sum(r["answer"] is None for r in calls),
                           "wrong":sum(r["wrong"] is True for r in calls),
                           "item_weighted_wrong_rate":mean(mean(v) for v in by_item.values()) if by_item else None}
        return result
    paired = [r for r in item_effects if r["complete_primary_pair"]]
    interval = None
    if len(paired) >= 2:
        # Stratified task-level paired bootstrap preserves semantic/label/own-status cells.
        clusters = defaultdict(list)
        for r in paired:
            clusters[r["semantic"],r["truth"],r["own_correct"]].append(r["delta_wrong_high_minus_correct_high"])
        random_source = rng(seed, "local-bootstrap")
        estimates = sorted(mean(x for values in clusters.values() for x in random_source.choices(values,k=len(values))) for _ in range(2000))
        interval = [estimates[49],estimates[1949]]
    subgroup = {}
    for field in ("semantic","own_correct","truth"):
        for value in sorted({r[field] for r in rows},key=str):
            subset = [r for r in rows if r[field]==value]
            effects = [r["delta_wrong_high_minus_correct_high"] for r in paired if r[field]==value]
            subgroup[f"{field}={value}"] = {"arms":arm_stats(subset),"paired_items":len(effects),
                                            "primary_delta":mean(effects) if effects else None}
    return {"backend":backend,"is_empirical":backend=="openrouter","arms":arm_stats(rows),
            "items_completed":len(item_effects),"primary_paired_items":len(paired),
            "primary_delta_wrong_high_minus_correct_high":mean(r["delta_wrong_high_minus_correct_high"] for r in paired) if paired else None,
            "descriptive_stratified_item_bootstrap_95pct":interval,
            "all_completed_item_missing_response_bounds":[mean(r["missing_response_bounds"][j] for r in item_effects) for j in (0,1)] if item_effects else None,
            "subgroups":subgroup,"item_effects":item_effects,
            "note":"Exploratory local replay of synthetic peer and own answers. Confidence treatment, not six-agent discussion. Invalid responses excluded from valid rates; complete primary pairs and missing-response bounds reported separately."}


def run(config, bank_file, directory, backend="mock", repeats=3, workers=4, cap=480, seed=20260922, spec=None):
    if repeats < 1 or workers < 1 or len(config["selected"])!=1:
        raise ValueError("Require positive repeats/workers and one selected model")
    bank, _, bank_hash = load_frozen_bank(bank_file)
    fixed = contexts(bank,seed)
    arms = tuple(spec["arms"]) if spec else ARMS
    message_fn = spec["messages"] if spec else messages
    summary_fn = spec["summarize"] if spec else summarize
    if len(fixed)*len(arms)*repeats > cap:
        raise ValueError("Local replay exceeds request cap")
    directory = Path(directory)
    directory.mkdir(parents=True,exist_ok=True)
    lock = directory/".running"
    with lock.open("x"):
        pass
    try:
        key=config["selected"][0]; model=config["models"][key]
        manifest={"protocol":"local-four-arm-v1","backend":backend,"source_hash":source_hash(),
                  "model":model,"max_tokens":config["max_tokens"],"seed":seed,"repeats":repeats,
                  "workers":workers,"bank_hash":bank_hash,"contexts":fixed,"arms":arms,
                  "primary":"P(wrong | wrong_high) - P(wrong | correct_high), equally weighted within paired tasks",
                  "analysis":"Complete primary pairs; stratified paired task bootstrap; invalid-response sensitivity bounds; all tasks retained",
                  "peer_design":"Four synthetic peers, two correct and two wrong; .95/.55 crossed allocation, equal .75, hidden",
                  "synthetic_own_answer":True}
        if spec:
            manifest.update(spec["manifest"])
        # Normalize tuples to the persisted JSON representation for resume equality.
        manifest=json.loads(json.dumps(manifest))
        path=directory/"manifest.json"
        if path.exists() and json.loads(path.read_text(encoding="utf-8"))!=manifest:
            raise ValueError("Manifest changed; use a new output directory")
        save(path,manifest)
        if backend=="openrouter":
            snapshot=catalog({key:model})
            if not (directory/"catalog.json").exists():
                save(directory/"catalog.json",snapshot)
        stop=threading.Event()
        def sample(context):
            task=context["task"]
            folder=directory/"items"/task["id"]
            calls=Calls(folder,backend,len(arms)*repeats,config["max_tokens"])
            order=[(arm,rep) for arm in arms for rep in range(repeats)]
            rng(seed,task["id"],"cell-order").shuffle(order)
            records=[]
            try:
                for arm,rep in order:
                    if stop.is_set():
                        return records
                    response=calls.ask(f"local/{key}/{task['id']}/{arm}/{rep}",model,message_fn(context,arm))
                    answer=response["answer"] if response else None
                    records.append({"item_id":task["id"],"semantic":context["semantic"],"truth":task["truth"],
                                    "own":context["own"],"own_correct":context["own_correct"],"arm":arm,"repeat":rep,
                                    "answer":answer,"wrong":answer!=task["truth"] if answer is not None else None})
                    save(folder/"results.json",records)
            except Exception:
                stop.set()
                raise
            return records
        order=fixed[:]; rng(seed,"task-order").shuffle(order)
        rows=[]
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures=[pool.submit(sample,c) for c in order]
            for i,future in enumerate(as_completed(futures),1):
                rows.extend(future.result())
                save(directory/"progress.json",{"items_completed":i,"items_planned":len(fixed),"rows":len(rows)})
                print(f"Completed {i}/{len(fixed)} local contexts",flush=True)
        rows.sort(key=lambda r:(r["item_id"],r["arm"],r["repeat"]))
        save(directory/"results.json",rows)
        summary=summary_fn(rows,repeats,backend,seed)
        calls=[json.loads(p.read_text(encoding="utf-8")) for p in (directory/"items").glob("*/calls/*.json")]
        costs=[r.get("response",{}).get("usage",{}).get("cost") for r in calls]
        summary["usage"]={"requests":len(calls),"reported_cost_usd":sum(x for x in costs if x is not None),
                          "requests_without_cost":sum(x is None for x in costs)}
        save(directory/"summary.json",summary)
        return summary
    finally:
        lock.unlink(missing_ok=True)


def main():
    p=argparse.ArgumentParser(description="Four-arm local confidence replay, mock by default")
    p.add_argument("--config",default="configs/luna-reliable.json")
    p.add_argument("--bank",default="data/logic-l2-balanced-20260921.json")
    p.add_argument("--out",required=True)
    p.add_argument("--backend",choices=["mock","openrouter"],default="mock")
    p.add_argument("--repeats",type=int,default=3)
    p.add_argument("--workers",type=int,default=4)
    p.add_argument("--max-requests",type=int,default=480)
    args=p.parse_args()
    config=json.loads(Path(args.config).read_text(encoding="utf-8"))
    result=run(config,args.bank,args.out,args.backend,args.repeats,args.workers,args.max_requests)
    print(json.dumps({k:v for k,v in result.items() if k not in ("subgroups","item_effects")},indent=2))


if __name__=="__main__":
    main()
