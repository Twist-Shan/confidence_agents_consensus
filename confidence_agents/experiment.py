"""L (local replay) and C (sustained confidence) pilot, complete graph."""
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean

from .design import confidence, digest, local_cells, prompt, rng, tasks
from .runtime import Calls, catalog, save


def validate(config):
    if config["agents"] != 6:
        raise ValueError("This pilot fixes N=6 and exactly two high scores")
    for field in ("items", "roots_per_item", "rounds", "local_contexts", "local_repeats", "max_tokens"):
        if type(config[field]) is not int or config[field] <= 0:
            raise ValueError(f"{field} must be a positive integer")
    if not config["selected"] or len(set(config["selected"])) != len(config["selected"]):
        raise ValueError("Select unique model keys")
    if not set(config["selected"]) <= config["models"].keys():
        raise ValueError("Unknown selected model")
    arms = config["arms"]
    if len(set(arms)) != len(arms) or not {"aligned", "misaligned"} <= set(arms):
        raise ValueError("Unique arms including aligned and misaligned are required")
    if not set(arms) <= {"aligned", "misaligned", "random", "hidden"}:
        raise ValueError("Unknown treatment arm")


def plan(config):
    validate(config)
    initial = config["items"] * config["roots_per_item"] * 6
    group = initial * len(config["arms"]) * config["rounds"]
    local = config["local_contexts"] * 10 * config["local_repeats"]
    return {"models": config["selected"], "initial_per_model": initial,
            "discussion_per_model": group, "local_per_model": local,
            "maximum_calls_per_model": initial + group + local,
            "maximum_calls_total": (initial + group + local) * len(config["selected"])}


def source_hash():
    return digest({p.name: p.read_text(encoding="utf-8") for p in sorted(Path(__file__).parent.glob("*.py"))})


def run(config, directory, backend="mock", max_requests=None):
    validate(config)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    lock = directory / ".running"
    try:
        handle = lock.open("x")
    except FileExistsError:
        raise RuntimeError("Run is locked. After a crash verify no process is running before removing .running") from None
    try:
        handle.close()
        return _run(config, directory, backend, max_requests)
    finally:
        lock.unlink(missing_ok=True)


def _run(config, directory, backend, max_requests):
    bank = tasks(config["items"], config["seed"])
    manifest = {"config": config, "backend": backend, "tasks": bank, "source_hash": source_hash(),
                "protocol": "L+C-complete-graph-v1"}
    path = directory / "manifest.json"
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != manifest:
            raise ValueError("Run directory belongs to a different config, source, task bank or backend")
    else:
        save(path, manifest)
    if backend == "openrouter":
        snapshot = catalog({k: config["models"][k] for k in config["selected"]})
        if not (directory / "catalog.json").exists():
            save(directory / "catalog.json", snapshot)
    calls = Calls(directory, backend, max_requests if max_requests is not None else config["max_requests"], config["max_tokens"])
    rows, local_rows = [], []
    for key in config["selected"]:
        model = config["models"][key]
        for item in bank:
            for rep in range(config["roots_per_item"]):
                root_id = f"{key}/{item['id']}/{rep}"
                initial = [calls.ask(f"{root_id}/initial/{j}", model, prompt(item["question"]), True) for j in range(6)]
                root = {"root_id": root_id, "model": key, "item_id": item["id"], "initial": initial}
                save(directory / "roots" / (digest(root_id)+".json"), root)
                if any(v is None for v in initial):
                    rows.append({**root, "status": "invalid_initial"})
                    continue
                answers = [v["answer"] for v in initial]
                order = list(range(6))
                rng(config["seed"], root_id, "order").shuffle(order)
                arms = list(config["arms"])
                rng(config["seed"], root_id, "arm-order").shuffle(arms)
                for arm in arms:
                    scores = confidence(answers, item["truth"], arm, rng(config["seed"], root_id, arm))
                    state = answers[:]
                    trajectory = [state[:]]
                    invalid = 0
                    for t in range(config["rounds"]):
                        previous = state[:]
                        updated = []
                        for j in range(6):
                            peers = [{"agent": f"agent-{i}", "answer": previous[i],
                                      **({} if arm == "hidden" else {"confidence": scores[i]})}
                                     for i in order if i != j]
                            response = calls.ask(f"{root_id}/{arm}/{t}/{j}", model,
                                                 prompt(item["question"], previous[j], peers))
                            invalid += response is None
                            updated.append(previous[j] if response is None else response["answer"])
                        state = updated  # synchronous: no new answer reaches another agent within a round
                        trajectory.append(state[:])
                    wrong = [sum(a != item["truth"] for a in s)/6 for s in trajectory]
                    rows.append({"root_id": root_id, "model": key, "item_id": item["id"],
                        "status": "complete", "arm": arm, "scores": scores, "trajectory": trajectory,
                        "wrong_fraction": wrong, "mixed_initial": 0 < wrong[0] < 1,
                        "final_consensus": len(set(state)) == 1,
                        "final_wrong_majority": wrong[-1] > .5,
                        "sustained_reversal": wrong[0] < .5 and all(w > .5 for w in wrong[-2:]),
                        "invalid_updates": invalid})
        # Frozen synthetic local contexts: balanced/near-balanced and unanimous peer answers.
        for context in range(config["local_contexts"]):
            item = bank[context % len(bank)]
            r = rng(config["seed"], "local", context)
            degree = 2 + context % 4
            composition = (context // 4) % 3
            answers = (["A"]*degree if composition == 0 else ["B"]*degree if composition == 1
                       else ["A"]*(degree//2) + ["B"]*(degree-degree//2))
            r.shuffle(answers)
            own = "AB"[(context // 12) % 2]
            cells = local_cells(answers, r)
            r.shuffle(cells)
            for cell, scores in cells:
                peers = [{"agent": f"peer-{i}", "answer": a,
                          **({} if scores is None else {"confidence": scores[i]})} for i, a in enumerate(answers)]
                for rep in range(config["local_repeats"]):
                    response = calls.ask(f"{key}/local/{context}/{cell}/{rep}", model,
                                         prompt(item["question"], own, peers))
                    local_rows.append({"model": key, "context": context, "item_id": item["id"],
                        "degree": degree, "own": own, "peers": answers, "cell": cell, "repeat": rep,
                        "answer": None if response is None else response["answer"]})
        print(f"Completed {key}; recorded requests: {calls.count}", flush=True)
    save(directory / "group_results.json", rows)
    save(directory / "local_results.json", local_rows)
    result = summarize(rows, local_rows, backend, config["seed"])
    records = [json.loads(p.read_text(encoding="utf-8")) for p in calls.directory.glob("*.json")]
    costs = [r.get("response", {}).get("usage", {}).get("cost") for r in records]
    result["usage"] = {"requests": len(records), "reported_cost_usd": sum(c for c in costs if isinstance(c, (int, float))),
                       "requests_without_cost": sum(c is None for c in costs)}
    save(directory / "summary.json", result)
    return result


def summarize(rows, local_rows, backend, seed):
    result = {"backend": backend, "is_empirical": backend != "mock", "models": {}}
    models = sorted({r["model"] for r in rows})
    for model in models:
        all_rows = [r for r in rows if r["model"] == model]
        valid = [r for r in all_rows if r["status"] == "complete"]
        roots = defaultdict(dict)
        for r in valid:
            roots[r["root_id"]][r["arm"]] = r
        deltas, all_deltas = defaultdict(list), defaultdict(list)
        for arms in roots.values():
            a, m = arms["aligned"], arms["misaligned"]
            delta = m["wrong_fraction"][-1] - a["wrong_fraction"][-1]
            all_deltas[a["item_id"]].append(delta)
            if a["mixed_initial"]:
                deltas[a["item_id"]].append(delta)
        values = [mean(v) for v in deltas.values()]
        # Paired base-item cluster bootstrap. Pilot interval is descriptive only.
        interval = None
        if len(values) >= 2:
            r = rng(seed, model, "bootstrap")
            samples = sorted(mean(r.choices(values, k=len(values))) for _ in range(1000))
            interval = [samples[24], samples[974]]
        local = [r for r in local_rows if r["model"] == model]
        result["models"][model] = {
            "eligible_items": len(values), "eligible_roots": sum(map(len, deltas.values())),
            "invalid_initial_roots": sum(r["status"] == "invalid_initial" for r in all_rows),
            "invalid_updates": sum(r["invalid_updates"] for r in valid),
            "tau_misaligned_minus_aligned": mean(values) if values else None,
            "descriptive_item_bootstrap_95pct": interval,
            "all_root_item_weighted_tau": mean([mean(v) for v in all_deltas.values()]) if all_deltas else None,
            "local_cells": {cell: {"n": len(sub := [r for r in local if r["cell"] == cell]),
                "valid_n": len(ok := [r for r in sub if r["answer"] is not None]),
                "p_choose_B": mean(r["answer"] == "B" for r in ok) if ok else None}
                for cell in sorted({r["cell"] for r in local})}}
    return result
