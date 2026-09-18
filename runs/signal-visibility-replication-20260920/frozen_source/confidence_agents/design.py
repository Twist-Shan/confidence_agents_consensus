"""Deterministic task bank and randomized, paired experimental design."""
import hashlib
import itertools
import json
import random
from fractions import Fraction


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def rng(*parts):
    return random.Random(int(digest(parts), 16))


def tasks(count, seed):
    """Development tasks only: exact rational Bayesian comparisons and state tracking."""
    result = []
    for i in range(count):
        r = rng(seed, "task", i)
        if i % 2 == 0:
            prior, sensitivity, false_positive = [Fraction(r.randint(1, 9), 10) for _ in range(3)]
            posterior = prior * sensitivity / (prior * sensitivity + (1-prior) * false_positive)
            threshold = Fraction(r.randint(2, 8), 10)
            statement = (f"P(H)={prior}, P(E|H)={sensitivity}, P(E|not H)={false_positive}. "
                         f"Is P(H|E) strictly greater than {threshold}?")
            yes = posterior > threshold
            proof = {"posterior": str(posterior), "threshold": str(threshold)}
            family = "bayes"
        else:
            start = r.randint(0, 10)
            value = start
            operations = []
            for _ in range(8):
                a, b = r.randint(1, 4), r.randint(0, 10)
                value = (a * value + b) % 11
                operations.append(f"x <- ({a}*x + {b}) mod 11")
            statement = f"Start x={start}. In order apply: {'; '.join(operations)}. Is final x even?"
            yes = value % 2 == 0
            proof = {"final_x": value}
            family = "state"
        options = ["Yes", "No"]
        r.shuffle(options)
        truth = "AB"[options.index("Yes" if yes else "No")]
        result.append({"id": f"item-{i:03d}", "base_id": f"item-{i:03d}", "family": family,
                       "question": statement + f"\nA: {options[0]}\nB: {options[1]}",
                       "truth": truth, "verification": proof})
    return result


def allocations(correct, arm):
    choices = list(itertools.combinations(range(len(correct)), 2))
    if arm in ("random", "hidden"):
        return choices
    scores = [sum(correct[j] for j in c) for c in choices]
    best = (max if arm == "aligned" else min)(scores)
    return [c for c, score in zip(choices, scores) if score == best]


def confidence(answers, truth, arm, random_source):
    high = random_source.choice(allocations([a == truth for a in answers], arm))
    return [0.95 if j in high else 0.55 for j in range(len(answers))]


def prompt(question, own=None, peers=None):
    # Deliberate allowlist: never serialize the task's truth or private initial p_B.
    system = 'Solve the binary task. Return only JSON {"answer":"A" or "B"}.'
    body = {"question": question}
    if own is None:
        system = ('Solve independently. Return only JSON with answer (A or B), '
                  'reason (one short sentence), and p_B (your probability B is correct, 0 to 1).')
    else:
        body.update(own_previous_answer=own, peer_reports=peers)
        system += ' Peer reports may be wrong. Any displayed confidence is a reported score, not a guarantee.'
    return [{"role": "system", "content": system}, {"role": "user", "content": json.dumps(body)}]


def parse(content, initial=False):
    try:
        obj = json.loads(content)
        if not isinstance(obj, dict) or obj.get("answer") not in ("A", "B"):
            return None
        if initial:
            p = obj.get("p_B")
            if isinstance(p, bool) or not isinstance(p, (int, float)) or not 0 <= p <= 1:
                return None
            if not isinstance(obj.get("reason"), str):
                return None
        return obj
    except (ValueError, TypeError):
        return None


def local_cells(answers, random_source):
    """Six stance allocations, three equal-score controls, one hidden control."""
    d = len(answers)
    subsets = list(itertools.combinations(range(d), d // 2))
    counts = [sum(answers[i] == "B" for i in s) for s in subsets]
    cells = []
    for lo, hi in ((.55, .75), (.75, .95), (.55, .95)):
        for direction, target in (("B_high", max(counts)), ("A_high", min(counts))):
            high = random_source.choice([s for s, n in zip(subsets, counts) if n == target])
            cells.append((f"{lo}-{hi}-{direction}", [hi if j in high else lo for j in range(d)]))
    cells += [(f"equal-{v}", [v]*d) for v in (.55, .75, .95)]
    return cells + [("hidden", None)]
