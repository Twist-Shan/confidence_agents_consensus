"""Independent difficulty screening; never use treatment outcomes to select tasks."""
import argparse
import itertools
import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from fractions import Fraction
from pathlib import Path
from statistics import mean

from .design import digest, prompt, rng
from .experiment import source_hash
from .runtime import Calls, catalog, save


def solve(problem):
    """Exact reference solvers; no model or floating-point ground truth."""
    kind = problem["kind"]
    if kind == "state":
        x = problem["start"]
        trace = [x]
        for a, b in problem["operations"]:
            x = (a*x+b) % problem["modulus"]
            trace.append(x)
        return x % 2 == 0, {"trace": trace}
    if kind == "bayes":
        successes, failures = problem["successes"], problem["failures"]
        weights = [Fraction(w)*Fraction(p)**successes*(1-Fraction(p))**failures
                   for w, p in zip(problem["prior_weights"], problem["rates"])]
        posterior = weights[problem["target"]] / sum(weights)
        return posterior > Fraction(problem["threshold"]), {"posterior": str(posterior)}
    if kind == "logic":
        models = []
        for assignment in itertools.product((False, True), repeat=problem["variables"]):
            if all(any(assignment[abs(lit)-1] == (lit > 0) for lit in clause)
                   for clause in problem["clauses"]):
                models.append(assignment)
        if not models:
            raise ValueError("Unsatisfiable premise set is excluded")
        query = problem["query"]
        counterexamples = [m for m in models if m[abs(query)-1] != (query > 0)]
        return not counterexamples, {"satisfying_count": len(models),
                                     "counterexample": list(counterexamples[0]) if counterexamples else None}
    raise ValueError(kind)


def render(problem):
    if problem["kind"] == "state":
        ops = "; ".join(f"x <- ({a}*x+{b}) mod {problem['modulus']}" for a,b in problem["operations"])
        return f"Start x={problem['start']}. Apply sequentially, using nonnegative residues: {ops}. Is final x even?"
    if problem["kind"] == "bayes":
        hypotheses = "; ".join(f"H{i}: prior weight {w}, success probability {p}"
            for i,(w,p) in enumerate(zip(problem["prior_weights"], problem["rates"])))
        return (f"Exactly one hypothesis holds; normalize prior weights to sum to one. {hypotheses}. "
                f"Trials are independent conditional on the hypothesis. Observe {problem['successes']} successes "
                f"and {problem['failures']} failures. Is P(H{problem['target']} | observations) strictly greater "
                f"than {problem['threshold']}?")
    literal = lambda lit: ("NOT " if lit < 0 else "") + f"X{abs(lit)}"
    clauses = " AND ".join("(" + " OR ".join(map(literal, c)) + ")" for c in problem["clauses"])
    return (f"Boolean variables X1 through X{problem['variables']}. Premises: {clauses}. "
            f"Do the premises logically entail {literal(problem['query'])}? "
            "Answer Yes only if the query is true in EVERY assignment satisfying all premises; otherwise No.")


def candidates(seed=20260918, variants=2, families=("state", "bayes", "logic"), levels=(1,2,3,4)):
    if not set(families) <= {"state", "bayes", "logic"} or not set(levels) <= {1,2,3,4}:
        raise ValueError("Unknown candidate family or level")
    bank = []
    for family in families:
        for level in levels:
            for variant in range(variants):
                r = rng(seed, "calibration", family, level, variant)
                if family == "state":
                    modulus = [11, 37, 97, 251][level-1]
                    problem = {"kind": family, "modulus": modulus, "start": r.randrange(modulus),
                               "operations": [[r.randint(2, 9), r.randrange(modulus)]
                                              for _ in range([8, 16, 24, 40][level-1])]}
                elif family == "bayes":
                    n = level + 1
                    trials = [4, 8, 16, 32][level-1]
                    successes = r.randint(trials//3, trials*2//3)
                    problem = {"kind": family, "prior_weights": [r.randint(1, 9) for _ in range(n)],
                               "rates": [str(Fraction(r.randint(2, 8), 10)) for _ in range(n)],
                               "successes": successes, "failures": trials-successes,
                               "target": r.randrange(n), "threshold": "1/2"}
                    _, proof = solve(problem)
                    posterior = Fraction(proof["posterior"])
                    # Increasing decimal precision tests close comparisons; exact rational key retained.
                    scale = 10**[1, 2, 3, 4][level-1]
                    floor = posterior.numerator * scale // posterior.denominator
                    problem["threshold"] = str(Fraction(floor + variant % 2, scale))
                else:
                    n = [5, 7, 9, 11][level-1]
                    planted = [r.choice((False, True)) for _ in range(n)]
                    clauses = []
                    while len(clauses) < n*4:
                        clause = [i*r.choice((-1,1)) for i in r.sample(range(1,n+1), 3)]
                        if any(planted[abs(lit)-1] == (lit > 0) for lit in clause):
                            clauses.append(clause)
                    q = r.randrange(n)
                    problem = {"kind": family, "variables": n, "clauses": clauses,
                               "query": (q+1)*(1 if planted[q] else -1)*(1 if variant % 2 == 0 else -1)}
                yes, proof = solve(problem)
                options = ["Yes", "No"]
                r.shuffle(options)
                item_id = f"cal-{seed}-{family}-L{level}-v{variant}"
                bank.append({"id": item_id, "base_id": item_id, "family": family, "level": level,
                             "problem": problem, "verification": proof, "options": options,
                             "truth": "AB"[options.index("Yes" if yes else "No")],
                             "question": render(problem)+f"\nA: {options[0]}\nB: {options[1]}"})
    return bank


def summarize(bank, answers, backend, samples):
    rows = []
    for item in bank:
        responses = answers.get(item["id"], [])
        valid = [x for x in responses if x is not None]
        correct = sum(x["answer"] == item["truth"] for x in valid)
        rows.append({"item_id": item["id"], "family": item["family"], "level": item["level"],
                     "n": len(responses), "valid_n": len(valid), "correct_n": correct,
                     "accuracy_valid": correct/len(valid) if valid else None,
                     "mixed_complete_group": len(valid) == samples and 0 < correct < samples})
    strata = []
    for family, level in sorted({(x["family"], x["level"]) for x in rows}):
        sub = [x for x in rows if x["family"] == family and x["level"] == level]
        n, valid_n = sum(x["n"] for x in sub), sum(x["valid_n"] for x in sub)
        accuracy = sum(x["correct_n"] for x in sub)/valid_n if valid_n else None
        invalid_rate = (n-valid_n)/n if n else None
        complete = n == samples*len(sub)
        mixed = sum(x["mixed_complete_group"] for x in sub)
        # Predeclared exploratory recommendation at family x level, not per observed root.
        recommended = complete and invalid_rate <= .1 and accuracy is not None and .3 <= accuracy <= .85 and mixed > 0
        strata.append({"family": family, "level": level, "n": n, "valid_n": valid_n,
                       "accuracy_valid": accuracy, "invalid_rate": invalid_rate,
                       "mixed_groups": mixed, "items": len(sub), "recommended_exploratory": recommended})
    return {"backend": backend, "is_empirical": backend == "openrouter", "items": rows, "strata": strata,
            "note": "Recommendations are exploratory; inspect per-stratum item counts and validate on new held-out items and fresh calls."}


def load_frozen_bank(path):
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    bank = document["tasks"]
    if not bank or len({x["id"] for x in bank}) != len(bank):
        raise ValueError("Frozen task bank must contain unique items")
    for item in bank:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", item["id"]):
            raise ValueError("Unsafe item ID")
        if sorted(item["options"]) != ["No", "Yes"]:
            raise ValueError("Invalid options")
        yes, proof = solve(item["problem"])
        truth = "AB"[item["options"].index("Yes" if yes else "No")]
        question = render(item["problem"])+f"\nA: {item['options'][0]}\nB: {item['options'][1]}"
        if item["truth"] != truth or item["question"] != question or item["verification"] != proof:
            raise ValueError("Frozen item failed exact answer/prompt verification")
    return bank, document["seed"], digest(document)


def calibrate(config, directory, backend="mock", seed=20260918, variants=2, samples=6, workers=4, cap=144, bank_file=None):
    if len(config["selected"]) != 1:
        raise ValueError("Calibrate one model at a time")
    if min(variants, samples, workers) < 1:
        raise ValueError("variants, samples and workers must be positive")
    bank_hash = None
    if bank_file is None:
        bank = candidates(seed, variants)
    else:
        bank, seed, bank_hash = load_frozen_bank(bank_file)
    if len(bank)*samples > cap:
        raise ValueError("Calibration plan exceeds request cap")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    lock = directory/".running"
    with lock.open("x"):
        pass
    try:
        key = config["selected"][0]
        model = config["models"][key]
        manifest = {"kind": "difficulty-calibration-v1", "backend": backend, "model": model,
                    "tasks": bank, "samples": samples, "max_tokens": config["max_tokens"],
                    "source_hash": source_hash(), "seed": seed, "workers": workers,
                    "selection": {"accuracy_valid": [.3,.85], "max_invalid_rate": .1, "min_mixed_groups": 1}}
        if bank_file is not None:
            manifest.update(kind="difficulty-holdout-validation-v1", frozen_bank_hash=bank_hash,
                            frozen_bank_path=str(Path(bank_file).resolve()))
        path = directory/"manifest.json"
        if path.exists() and json.loads(path.read_text(encoding="utf-8")) != manifest:
            raise ValueError("Calibration manifest changed; use a new directory")
        save(path, manifest)
        if backend == "openrouter":
            snapshot = catalog({key: model})
            if not (directory/"catalog.json").exists():
                save(directory/"catalog.json", snapshot)
        stop = threading.Event()
        def sample(item):
            calls = Calls(directory/"items"/item["id"], backend, samples, config["max_tokens"])
            responses = []
            try:
                for rep in range(samples):
                    if stop.is_set():
                        return item["id"], responses
                    response = calls.ask(f"calibration/{key}/{item['id']}/{rep}", model, prompt(item["question"]), True)
                    responses.append(response)
                    save(directory/"items"/item["id"]/"answers.json", responses)
            except Exception:
                stop.set()
                raise
            return item["id"], responses
        answers = {}
        order = bank[:]
        rng(seed, "execution-order").shuffle(order)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(sample, item) for item in order]
            for future in as_completed(futures):
                item_id, responses = future.result()
                answers[item_id] = responses
                summary = summarize(bank, answers, backend, samples)
                save(directory/"summary.json", summary)
                print(f"Completed {len(answers)}/{len(bank)} items: {item_id}", flush=True)
        records = [json.loads(p.read_text(encoding="utf-8")) for p in (directory/"items").glob("*/calls/*.json")]
        costs = [x.get("response", {}).get("usage", {}).get("cost") for x in records]
        summary["usage"] = {"requests": len(records), "reported_cost_usd": sum(x for x in costs if x is not None),
                            "requests_without_cost": sum(x is None for x in costs)}
        save(directory/"summary.json", summary)
        # A distinct seed prevents reusing calibration questions as confirmatory evidence.
        if bank_file is None:
            recommended = {(s["family"], s["level"]) for s in summary["strata"] if s["recommended_exploratory"]}
            holdout = [x for x in candidates(seed+1, variants) if (x["family"], x["level"]) in recommended]
            save(directory/"holdout_candidates.json", {"status": "unvalidated", "seed": seed+1, "tasks": holdout})
        return summary
    finally:
        lock.unlink(missing_ok=True)


def main():
    p = argparse.ArgumentParser(description="Independent difficulty calibration; mock by default")
    p.add_argument("--config", default="configs/pilot.json")
    p.add_argument("--model", default="luna")
    p.add_argument("--backend", choices=["mock", "openrouter"], default="mock")
    p.add_argument("--out", required=True)
    p.add_argument("--seed", type=int, default=20260918)
    p.add_argument("--variants", type=int, default=2)
    p.add_argument("--samples", type=int, default=6)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--max-requests", type=int, default=144)
    p.add_argument("--bank", help="Validate an existing frozen candidate JSON bank; do not regenerate tasks")
    args = p.parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    config["selected"] = [args.model]
    result = calibrate(config, args.out, args.backend, args.seed, args.variants, args.samples, args.workers, args.max_requests, args.bank)
    print(json.dumps({"strata": result["strata"], "usage": result["usage"]}, indent=2))


if __name__ == "__main__":
    main()
