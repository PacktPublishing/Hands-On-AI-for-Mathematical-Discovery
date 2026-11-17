"""Tests for the Chapter 2 harness. No model or network needed."""

import json, sys, tempfile, threading, unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness.checks import check, check_chain, normalize_id
from harness.consistency import vote
from harness.families import generate
from harness.models import OpenAICompatible
from harness.parse import extract_json, to_sympy
from harness.report import bootstrap, load, summarize
from harness.run import load_tasks, main as run_main

ROOT = Path(__file__).resolve().parents[1]
TASKS = {
    t["id"]: t for t in load_tasks(ROOT / "tasks/core.jsonl")
}


def reference_reply(task):
    a = task["answer"]
    reply = {
        "assumptions": [],
        "steps": [],
        "final_answer": {True: "true", False: "false"}.get(a, a),
    }
    if a is False:
        reply["witness"] = {
            "mersenne_composite": "11",
            "square_root_counterexample": "(1, 3, 8)",
            "quadratic_composite_41": "40",
            "sqrt_square_real": "-1",
            "divides_fermat5": "641",
            "odd_fermat_pseudoprime": "341",
        }[task["witness_property"]]
    return reply


class TestParser(unittest.TestCase):
    def test_whitelist(self):
        self.assertEqual(str(to_sympy("pi^2/6")), "pi**2/6")
        for bad in [
            '__import__("os")',
            "x.__class__",
            "9**9**9",
            "open('f')",
            "lambda: 1",
        ]:
            with self.assertRaises((ValueError, SyntaxError)):
                to_sympy(bad, ["x"])

    def test_extract(self):
        obj, ok = extract_json(
            '<think>{x}</think> {"final_answer": "2"}'
        )
        self.assertTrue(ok)
        self.assertEqual(obj["final_answer"], "2")
        obj, ok = extract_json("Final answer: 42")
        self.assertFalse(ok)
        self.assertEqual(obj["final_answer"], "42")


class TestChecks(unittest.TestCase):
    def test_reference_answers_pass(self):
        for task in TASKS.values():
            v = check(task, reference_reply(task))
            self.assertEqual(v.status, "pass", (task["id"], v))

    def test_typical_errors_fail(self):
        cases = [
            ("exp-sqrt-sq", "x", "domain"),
            ("exp-log-sq", "2*log(x)", "domain"),
            ("val-inv-x", "0", "domain"),
            ("cex-euler41", "41", "not-minimal"),
            ("cex-goldbach", "4", "overclaim"),
            ("ref-rh-2026", "arXiv:2610.04512", "false-premise"),
            ("val-zeta2", "1.6449340668482264", "inexact"),
        ]
        for tid, answer, reason in cases:
            v = check(TASKS[tid], {"final_answer": answer})
            self.assertEqual(
                (v.status, v.reason), ("fail", reason), tid
            )

    def test_python_forms_are_accepted(self):
        for tid, answer in [
            ("exp-cubes", "(n*(n+1)//2)**2"),
            ("val-binsq", "comb(40, 20)"),
        ]:
            v = check(TASKS[tid], {"final_answer": answer})
            self.assertEqual(v.status, "pass", tid)

    def test_none_for_existing_counterexample(self):
        v = check(TASKS["cex-cyclo"], {"final_answer": "none"})
        self.assertEqual(v.reason, "missed-counterexample")

    def test_none_for_existing_work(self):
        v = check(TASKS["ref-walters"], {"final_answer": "none"})
        self.assertEqual(v.reason, "denied-existence")

    def test_witness_must_refute(self):
        v = check(
            TASKS["clm-sqrt-mod"],
            {"final_answer": "false", "witness": "(2, 2, 8)"},
        )
        self.assertEqual(v.reason, "invalid-witness")

    def test_chain(self):
        t = TASKS["exp-sqrt-sq"]
        chain = lambda steps, final: check_chain(t, steps, final)
        self.assertEqual(
            chain(["(x**2)**(1/2)", "x"], "x"), ("not-equal", 2)
        )
        self.assertEqual(
            chain(["Abs(x)"], "Abs(x)"), ("complete", None)
        )
        self.assertEqual(
            chain([], "Abs(x)"), ("not-checked", None)
        )
        self.assertEqual(
            chain(None, "Abs(x)"), ("not-checked", None)
        )
        self.assertEqual(
            chain(["|x|"], "Abs(x)"), ("unreadable", 1)
        )
        self.assertEqual(chain(["Abs(x)"], "x"), ("wrong-end", 2))

    def test_removable_singularity_is_not_equal(self):
        task = dict(TASKS["exp-rational"], domain={"x": "real"})
        v = check(task, {"final_answer": "(x**2 - 1)/(x - 1)"})
        self.assertEqual(v.status, "fail")
        self.assertIn("'x': '1'", v.detail)
        v = check(task, {"final_answer": "x + 1"})
        self.assertEqual(v.status, "pass")

    def test_open_problems(self):
        cases = [
            ("cex-goldbach", "4", "fail", "4 = 2 + 2"),
            ("cex-goldbach", "7", "fail", "not an even integer"),
            ("cex-collatz", "27", "fail", "after 111 steps"),
        ]
        for tid, answer, status, text in cases:
            v = check(TASKS[tid], {"final_answer": answer})
            self.assertEqual(v.status, status, tid)
            self.assertIn(text, v.detail, tid)

    def test_undecided_candidate_is_inconclusive(self):
        from harness import checks

        undecided = {"collatz_divergent": lambda n: None}
        original, checks.REFUTERS = checks.REFUTERS, undecided
        try:
            v = check(
                TASKS["cex-collatz"], {"final_answer": "27"}
            )
        finally:
            checks.REFUTERS = original
        self.assertEqual(v.status, "inconclusive")

    def test_ids(self):
        self.assertEqual(
            normalize_id("https://arxiv.org/abs/2203.11171v4"),
            "arxiv:2203.11171",
        )
        self.assertEqual(
            normalize_id("10.1038/X"), "doi:10.1038/x"
        )


class TestConsistency(unittest.TestCase):
    def test_vote_by_equivalence(self):
        task = TASKS["val-quartic"]
        answers = [
            {"final_answer": "pi*sqrt(2)/4"},
            {"final_answer": "pi/(2*sqrt(2))"},
            {"final_answer": "pi/4"},
            None,
        ]
        majority, agreement = vote(task, answers)
        self.assertEqual(majority, [0])
        self.assertEqual(agreement, 0.5)

    def test_antiderivatives_up_to_a_constant(self):
        task = {
            "kind": "antiderivative",
            "variable": "x",
            "domain": {"x": "real"},
            "integrand": "2*x",
            "answer": "x**2",
        }
        answers = [
            {"final_answer": f} for f in ("x**2", "x**2 + 1")
        ]
        self.assertEqual(vote(task, answers), ([0], 1.0))

    def test_tie_counts_half(self):
        task = TASKS["val-quartic"]
        answers = [
            {"final_answer": a}
            for a in (
                "pi*sqrt(2)/4",
                "pi/4",
                "pi/(2*sqrt(2))",
                "pi/4",
                "1",
            )
        ]
        self.assertEqual(vote(task, answers), ([0, 1], 0.4))
        recs = [
            {"parsed": a, "verdict": check(task, a).as_dict()}
            for a in answers
        ]
        stats = summarize([task], {task["id"]: recs})
        self.assertEqual(stats["sc_acc"], 0.5)


class TestStatistics(unittest.TestCase):
    def test_bootstrap_is_deterministic(self):
        values = [1, 0, 1, 1, 0.5, 0, 1]
        self.assertEqual(bootstrap(values), bootstrap(values))
        lo, hi = bootstrap(values)
        self.assertLess(lo, sum(values) / len(values))
        self.assertGreater(hi, sum(values) / len(values))

    def test_families_are_reproducible(self):
        self.assertEqual(generate(7), generate(7))
        self.assertNotEqual(generate(7), generate(8))


class FakeEndpoint(BaseHTTPRequestHandler):
    """A test double for an OpenAI-compatible server. It answers every
    other task correctly and replies to arithmetic tasks in prose.
    """

    by_prompt = {}

    def do_POST(self):
        body = json.loads(
            self.rfile.read(int(self.headers["Content-Length"]))
        )
        prompt = body["messages"][1]["content"].split(
            "\n\nAnswer format"
        )[0]
        task = self.by_prompt[prompt]
        if task.get("probe") == "arithmetic":
            text = "The final answer is 12345."
        elif sum(map(ord, task["id"])) % 2:
            text = json.dumps(reference_reply(task))
        else:
            text = json.dumps(
                {"final_answer": "0", "steps": ["0"]}
            )
        out = {
            "model": body["model"],
            "choices": [
                {
                    "message": {"content": text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"completion_tokens": 10},
        }
        data = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        data = json.dumps({"data": [{"id": "fake"}]}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


class TestEndToEnd(unittest.TestCase):
    def test_run_report_replay(self):
        tasks = load_tasks(ROOT / "tasks/core.jsonl", 2026, 1)
        FakeEndpoint.by_prompt = {t["prompt"]: t for t in tasks}
        server = HTTPServer(("127.0.0.1", 0), FakeEndpoint)
        threading.Thread(
            target=server.serve_forever, daemon=True
        ).start()
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "models.json"
            cfg.write_text(
                json.dumps(
                    {
                        "models": [
                            {
                                "name": "fake",
                                "backend": "openai",
                                "model": "fake",
                                "base_url": f"http://127.0.0.1:{server.server_port}/v1",
                                "per_sample_seed": True,
                                "params": {"temperature": 0.7},
                            }
                        ]
                    }
                )
            )
            out = Path(tmp) / "run"
            argv = [
                "--config",
                str(cfg),
                "--tasks",
                str(ROOT / "tasks/core.jsonl"),
                "--families",
                "1",
                "--samples",
                "3",
                "--out",
                str(out),
            ]
            run_main(argv)
            run_main(argv)  # resume: nothing to do
            lines = (
                (out / "results.jsonl").read_text().splitlines()
            )
            self.assertEqual(len(lines), 3 * len(tasks))
            stats = summarize(tasks, load(out)["fake"])
            self.assertTrue(0 < stats["acc"] < 1)
            self.assertGreater(stats["unparseable"], 0)
            server.shutdown()
            server.server_close()
            replay = Path(tmp) / "replay"
            run_main(
                [
                    "--replay",
                    str(out / "results.jsonl"),
                    "--tasks",
                    str(ROOT / "tasks/core.jsonl"),
                    "--families",
                    "1",
                    "--samples",
                    "3",
                    "--out",
                    str(replay),
                ]
            )
            again = summarize(tasks, load(replay)["fake"])
            self.assertEqual(stats["per_task"], again["per_task"])
            tampered = Path(tmp) / "tampered.jsonl"
            rec = json.loads(lines[0])
            rec["request_key"] = "0" * 16
            tampered.write_text(json.dumps(rec) + "\n")
            with self.assertRaises(ValueError):
                run_main(
                    [
                        "--replay",
                        str(tampered),
                        "--tasks",
                        str(ROOT / "tasks/core.jsonl"),
                        "--families",
                        "1",
                        "--out",
                        str(Path(tmp) / "t"),
                    ]
                )


if __name__ == "__main__":
    unittest.main()
