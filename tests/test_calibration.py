import json
import tempfile
import unittest
from pathlib import Path

from confidence_agents.calibration import candidates, calibrate, solve, summarize, load_frozen_bank


class CalibrationTests(unittest.TestCase):
    def test_frozen_bank_verification_and_run_scope(self):
        bank = [x for x in candidates(20260919) if x["family"] == "logic" and x["level"] in (1,2)]
        config = json.loads(Path("configs/pilot.json").read_text())
        config["selected"] = ["luna"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"bank.json"
            path.write_text(json.dumps({"seed":20260919,"tasks":bank}),encoding="utf-8")
            self.assertEqual(load_frozen_bank(path)[0],bank)
            result = calibrate(config,Path(directory)/"run",samples=6,cap=24,bank_file=path)
            self.assertEqual(result["usage"]["requests"],24)
            self.assertEqual({x["item_id"] for x in result["items"]},{x["id"] for x in bank})
            bank[0]["truth"] = "A" if bank[0]["truth"] == "B" else "B"
            path.write_text(json.dumps({"seed":20260919,"tasks":bank}),encoding="utf-8")
            with self.assertRaises(ValueError):
                load_frozen_bank(path)

    def test_exact_reference_examples(self):
        self.assertEqual(solve({"kind":"state", "start":2, "modulus":7,
                                "operations":[[3,1],[2,3]]}), (False, {"trace":[2,0,3]}))
        answer, proof = solve({"kind":"bayes", "prior_weights":[1,1], "rates":["3/4","1/4"],
                               "successes":2,"failures":0,"target":0,"threshold":"9/10"})
        self.assertFalse(answer)  # strict inequality at exactly 9/10
        self.assertEqual(proof["posterior"], "9/10")
        self.assertTrue(solve({"kind":"logic","variables":2,"clauses":[[1],[-1,2]],"query":2})[0])
        self.assertFalse(solve({"kind":"logic","variables":2,"clauses":[[1,2]],"query":2})[0])

    def test_bank_and_heldout_disjoint(self):
        bank = candidates()
        self.assertEqual(len(bank),24)
        other = candidates(20260919)
        self.assertFalse({x["question"] for x in bank} & {x["question"] for x in other})
        for item in bank:
            yes, _ = solve(item["problem"])
            self.assertEqual(item["options"]["AB".index(item["truth"])], "Yes" if yes else "No")
            if item["family"] == "state":
                # Independently compose affine transforms instead of sequential state updates.
                a,b = 1,0
                for c,d in item["problem"]["operations"]:
                    a,b = c*a,c*b+d
                x = (a*item["problem"]["start"]+b) % item["problem"]["modulus"]
                self.assertEqual(yes, x % 2 == 0)

    def test_invalid_not_counted_as_disagreement(self):
        bank = [{"id":"x","family":"state","level":1,"truth":"A"}]
        result = summarize(bank, {"x":[{"answer":"A"},{"answer":"B"},None]}, "mock", 3)
        self.assertFalse(result["strata"][0]["recommended_exploratory"])
        self.assertEqual(result["strata"][0]["mixed_groups"], 0)

    def test_parallel_mock_and_resume(self):
        config = json.loads(Path("configs/pilot.json").read_text())
        config["selected"] = ["luna"]
        with tempfile.TemporaryDirectory() as directory:
            first = calibrate(config,directory,variants=1,samples=2,workers=4,cap=24)
            self.assertEqual(first["usage"]["requests"],24)
            self.assertFalse(first["is_empirical"])
            self.assertEqual(first,calibrate(config,directory,variants=1,samples=2,workers=4,cap=24))


if __name__ == "__main__":
    unittest.main()
