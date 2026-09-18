import copy
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from confidence_agents.design import allocations, confidence, local_cells, parse, prompt, rng, tasks
from confidence_agents.experiment import plan, run, summarize
from confidence_agents.runtime import Calls, output_format


CONFIG = json.loads(Path("configs/pilot.json").read_text(encoding="utf-8"))


class DesignTests(unittest.TestCase):
    def test_assignment_support_and_ties(self):
        self.assertEqual(len(allocations([True]*6, "aligned")), 15)
        self.assertEqual(len(allocations([True]*6, "misaligned")), 15)
        self.assertEqual(len(allocations([True]*5+[False], "misaligned")), 5)
        self.assertEqual(allocations([True, True, False, False, False, False], "aligned"), [(0, 1)])
        scores = confidence(list("AABBBB"), "A", "misaligned", rng(1))
        self.assertEqual(sorted(scores), [.55]*4+[.95]*2)

    def test_prompt_excludes_private_fields(self):
        text = json.dumps(prompt("question", "A", [{"answer": "B", "confidence": .95}]))
        for forbidden in ("truth", "p_B", "reason", "round"):
            self.assertNotIn(forbidden, text)

    def test_parse_invalid(self):
        for value in ('{"answer":"C"}', '[]', 'A', '{"answer":"A","p_B":true,"reason":"r"}',
                      '{"answer":"A","p_B":NaN,"reason":"r"}'):
            self.assertIsNone(parse(value, True))
        self.assertIsNotNone(parse('{"answer":"B","p_B":0.4,"reason":"r"}', True))

    def test_local_cells(self):
        cells = local_cells(list("AABBB"), rng(1))
        self.assertEqual(len(cells), 10)
        for _, scores in cells[:6]:
            self.assertEqual(scores.count(max(scores)), 2)
        self.assertIsNone(cells[-1][1])

    def test_budget(self):
        self.assertEqual(plan(CONFIG)["maximum_calls_total"], 5760)

    def test_tasks_reproducible(self):
        self.assertEqual(tasks(12, 9), tasks(12, 9))
        self.assertEqual(len({x["id"] for x in tasks(12, 9)}), 12)

    def test_item_weighting_and_unanimous(self):
        rows = []
        for root, item, delta, mixed in (("r1", "x", 1, True), ("r2", "x", 1, True),
                                         ("r3", "y", 0, True), ("r4", "z", 1, False)):
            for arm in ("aligned", "misaligned"):
                rows.append(dict(root_id=root, model="m", item_id=item, arm=arm, status="complete",
                                 mixed_initial=mixed, invalid_updates=0,
                                 wrong_fraction=[.5, delta if arm == "misaligned" else 0]))
        result = summarize(rows, [], "mock", 1)["models"]["m"]
        self.assertEqual(result["tau_misaligned_minus_aligned"], .5)
        self.assertEqual(result["eligible_roots"], 3)


class RuntimeTests(unittest.TestCase):
    def test_strict_schema_and_token_limit_handling(self):
        schema=output_format(True)["json_schema"]
        self.assertTrue(schema["strict"])
        self.assertFalse(schema["schema"]["additionalProperties"])
        self.assertEqual(set(schema["schema"]["required"]),{"answer","reason","p_B"})
        self.assertEqual(output_format(False)["json_schema"]["schema"]["required"],["answer"])
        response={"choices":[{"message":{"content":'{"answer":"A"}'},"finish_reason":"length"}],"usage":{}}
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict("os.environ", {"OPENROUTER_API_KEY":"test-only-secret"}):
                calls=Calls(directory,"openrouter",1,8192)
                with patch("urllib.request.urlopen") as transport:
                    transport.return_value.__enter__.return_value=io.BytesIO(json.dumps(response).encode())
                    result=calls.ask("id",{"id":"test/model","structured_outputs":True,"reasoning_effort":"medium"},prompt("q"))
                    self.assertIsNone(result)
                    body=json.loads(transport.call_args.args[0].data)
                    self.assertEqual(body["max_tokens"],8192)
                    self.assertEqual(body["reasoning"],{"effort":"medium"})
                    self.assertEqual(body["response_format"],output_format(False))
            record=json.loads(next((Path(directory)/"calls").glob("*.json")).read_text())
            self.assertEqual(record["failure_category"],"output_token_limit")

    def test_http_error_reason_saved_without_key(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-only-secret"}):
                calls = Calls(directory, "openrouter", 1, 100)
                error = urllib.error.HTTPError("https://openrouter.ai", 403, "Forbidden", {},
                    io.BytesIO(b'{"error":{"message":"Denied test-only-secret"},"user_id":"not-for-logs"}'))
                with patch("urllib.request.urlopen", side_effect=error):
                    with self.assertRaisesRegex(RuntimeError, "HTTP 403"):
                        calls.ask("id", {"id": "test/model"}, prompt("question"), True)
            record = json.loads(next((Path(directory)/"calls").glob("*.json")).read_text())
            self.assertEqual(record["error_message"], "Denied [REDACTED]")
            self.assertNotIn("not-for-logs", json.dumps(record))

    def tiny_config(self):
        c = copy.deepcopy(CONFIG)
        c.update(items=2, roots_per_item=1, rounds=2, local_contexts=4, local_repeats=1, selected=["luna"])
        return c

    def test_end_to_end_sync_and_resume(self):
        config = self.tiny_config()
        with tempfile.TemporaryDirectory() as directory:
            result = run(config, directory)
            self.assertFalse(result["is_empirical"])
            self.assertEqual(result["usage"]["requests"], 124)
            self.assertEqual(run(config, directory), result)
            base = Path(directory)
            records = {x["call_id"]: x for p in (base/"calls").glob("*.json")
                       for x in [json.loads(p.read_text())]}
            rows = json.loads((base/"group_results.json").read_text())
            for row in rows:
                for t in range(2):
                    for j in range(6):
                        call = records[f"{row['root_id']}/{row['arm']}/{t}/{j}"]
                        body = json.loads(call["request"]["messages"][1]["content"])
                        self.assertEqual(body["own_previous_answer"], row["trajectory"][t][j])
                        for peer in body["peer_reports"]:
                            i = int(peer["agent"].split("-")[1])
                            self.assertEqual(peer["answer"], row["trajectory"][t][i])
                            if row["arm"] == "hidden":
                                self.assertNotIn("confidence", peer)
                            else:
                                self.assertEqual(peer["confidence"], row["scores"][i])
            changed = copy.deepcopy(config)
            changed["seed"] += 1
            with self.assertRaises(ValueError):
                run(changed, directory)

    def test_cap_then_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(RuntimeError):
                run(self.tiny_config(), directory, max_requests=2)
            result = run(self.tiny_config(), directory, max_requests=124)
            self.assertEqual(result["usage"]["requests"], 124)

    def test_timeout_not_retried_and_key_not_logged(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-only-secret"}):
                calls = Calls(directory, "openrouter", 10, 100)
                with patch("urllib.request.urlopen", side_effect=TimeoutError("test-only-secret")) as transport:
                    for _ in range(2):
                        with self.assertRaises(RuntimeError):
                            calls.ask("id", {"id": "test/model"}, prompt("question"), True)
                    self.assertEqual(transport.call_count, 1)
            for path in (Path(directory)/"calls").glob("*.json"):
                self.assertNotIn("test-only-secret", path.read_text())


if __name__ == "__main__":
    unittest.main()
