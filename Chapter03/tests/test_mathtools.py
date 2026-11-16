"""Tests for Chapter 3. No model or network access needed."""

import json
import random
import re
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sympy as sp
from mathtools.census import census
from mathtools.experiment import (
    grade,
    main as run_main,
    make_tasks,
)
from mathtools.maps import cycle_from_word, orbit_cycle
from mathtools.numeric import float_terms, stable_terms
from mathtools.registry import Registry
from mathtools.report import load, summarize, tool_stats
from mathtools.symbolic import fixed_point
from mathtools.tools import TOOLS

LOG2_3 = [1, 1, 1, 2, 2, 3, 1, 5, 2, 23, 2, 2, 1, 1, 55, 1, 4, 3]


class TestMathematics(unittest.TestCase):
    def test_census_matches_brute_force(self):
        for c in range(-1, 60, 2):
            found = {
                tuple(f["members"]) for f in census(3, c, 14)
            }
            brute = set()
            for x in range(1, 5000):
                tail, cycle = orbit_cycle(3, c, x)
                if len(cycle) <= 14:
                    brute.add(tuple(cycle))
            self.assertLessEqual(brute, found, c)

    def test_known_cycles(self):
        smallest = lambda c, L: [
            f["smallest"] for f in census(3, c, L)
        ]
        self.assertEqual(smallest(1, 20), [1])
        self.assertEqual(smallest(-1, 11), [1, 5, 17])

    def test_symbolic_equals_exact(self):
        q, c = sp.symbols("q c")
        rng = random.Random(0)
        for _ in range(100):
            word = "".join(
                rng.choice("01")
                for _ in range(rng.randrange(1, 10))
            )
            x0 = cycle_from_word(3, 7, word)
            self.assertEqual(
                fixed_point(word).subs({q: 3, c: 7}),
                sp.Rational(x0.numerator, x0.denominator),
            )

    def test_denominator_equals_c(self):
        # 2**8 - 3**5 = 13: every word with l = 8, k = 5 is a cycle
        from mathtools.census import lyndon_words

        words = [
            w
            for w in lyndon_words(8)
            if len(w) == 8 and w.count("1") == 5
        ]
        self.assertEqual(len(words), 7)
        for w in words:
            self.assertEqual(
                cycle_from_word(3, 13, w).denominator, 1
            )

    def test_survey_sees_long_cycles_census_does_not(self):
        from mathtools.census import survey

        cycles, escaped, last = survey(3, 29, 10**4)
        self.assertEqual(sorted(cycles), [1, 11, 29, 3811, 7055])
        self.assertEqual(len(cycles[3811]), 65)
        smallest = [f["smallest"] for f in census(3, 29, 20)]
        self.assertEqual(smallest, [1, 11, 29])
        self.assertEqual((escaped, last), (0, 10**4))

    def test_precision(self):
        self.assertEqual(stable_terms(3)[:18], LOG2_3)
        self.assertEqual(float_terms(3)[:16], LOG2_3[:16])
        self.assertNotEqual(float_terms(3)[16], LOG2_3[16])


class TestRegistry(unittest.TestCase):
    def call(self, name, **args):
        return json.loads(
            Registry(TOOLS).call(name, json.dumps(args))
        )

    def test_rejections(self):
        cases = [
            ("orbit", dict(q=3, c=2, x=7, max_steps=10), "odd"),
            (
                "orbit",
                dict(q=3, c=1, x="7", max_steps=10),
                "integer",
            ),
            (
                "cycle_census",
                dict(q=3, c=1, max_len=40),
                "[1, 20]",
            ),
            ("word_cycle", dict(q=3, c=1, word="12"), "0 and 1"),
            (
                "exact_eval",
                dict(expression="open('f')"),
                "not a valid",
            ),
            ("orbit", dict(q=3, c=1, x=7), "missing"),
        ]
        for name, args, text in cases:
            self.assertIn(
                text, self.call(name, **args)["error"], name
            )

    def test_bad_json_and_unknown_tool(self):
        r = Registry(TOOLS)
        self.assertIn(
            "not valid JSON",
            json.loads(r.call("orbit", '{"q": 3'))["error"],
        )
        self.assertIn(
            "unknown tool",
            json.loads(r.call("collatz", "{}"))["error"],
        )

    def test_wrong_result_is_withheld(self):
        broken = dict(TOOLS)
        broken["word_cycle"] = dict(
            TOOLS["word_cycle"],
            run=lambda q, c, word: {"cycle": [5, 8, 4]},
        )
        out = json.loads(
            Registry(broken).call(
                "word_cycle",
                json.dumps(dict(q=3, c=-1, word="110")),
            )
        )
        self.assertIn("internal check failed", out["error"])

    def test_worst_cases_are_fast(self):
        """Python cannot stop a thread, so every tool must finish
        quickly at the limits of its arguments."""
        import time

        worst = [
            ("orbit", dict(q=5, c=1, x=7, max_steps=10**6)),
            (
                "orbit",
                dict(
                    q=99, c=10**6 - 1, x=10**18, max_steps=10**6
                ),
            ),
            ("cycle_census", dict(q=3, c=999999, max_len=20)),
            ("word_cycle", dict(q=99, c=1, word="1" * 64)),
            ("cycle_formula", dict(word="1011011101101110")),
            ("log2_convergents", dict(q=97, count=20)),
            ("exact_eval", dict(expression="factorial(10000)")),
            ("exact_eval", dict(expression="(9**9)**(9**9)")),
            ("exact_eval", dict(expression="2**2**2**2**2")),
        ]
        for name, args in worst:
            t0 = time.time()
            self.call(name, **args)
            self.assertLess(time.time() - t0, 5, name)

    def test_results(self):
        self.assertEqual(
            self.call("word_cycle", q=3, c=-1, word="110")[
                "cycle"
            ],
            [5, 7, 10],
        )
        self.assertEqual(
            self.call("exact_eval", expression="2**8 - 3**5")[
                "value"
            ],
            "13",
        )
        rows = self.call("log2_convergents", q=3, count=20)[
            "convergents"
        ]
        self.assertEqual(
            [(r["l"], r["k"]) for r in rows[3:6]],
            [(8, 5), (19, 12), (65, 41)],
        )
        self.assertEqual(rows[3]["two_l_minus_q_k"], "13")
        self.assertNotIn("two_l_minus_q_k", rows[-1])
        f = self.call("factor", n=2**65 - 3**41)["factors"]
        self.assertEqual(
            f, [[19, 1], [29, 1], [17021, 1], [44835377399, 1]]
        )


class TestTasks(unittest.TestCase):
    def test_deterministic(self):
        self.assertEqual(make_tasks(), make_tasks())

    def test_grade(self):
        task = next(
            t for t in make_tasks() if t["kind"] == "census"
        )
        ok = {"final_answer": dict(task["answer"])}
        self.assertEqual(grade(task, ok), "pass")
        self.assertEqual(
            grade(task, {"final_answer": {}}), "unparseable"
        )
        bad = {"final_answer": {"smallest_members": [2]}}
        self.assertEqual(grade(task, bad), "fail")


def answer_from(kind, result):
    if kind == "orbit":
        return {
            "tail": result["tail"],
            "smallest": result["smallest"],
        }
    if kind == "word":
        ok = result["integer"] and result["positive"]
        return {
            "exists": ok,
            "x0": int(result["x0"]) if ok else None,
        }
    return {"smallest_members": result["smallest_members"]}


class FakeEndpoint(BaseHTTPRequestHandler):
    """A test double for a tool-calling model server. With tools it
    first sends one invalid census call, then repairs it; without
    tools it gets every orbit tail wrong by one."""

    def do_POST(self):
        body = json.loads(
            self.rfile.read(int(self.headers["Content-Length"]))
        )
        question = body["messages"][1]["content"]
        c = int(re.search(r"c = (-?\d+)", question).group(1))
        kind = (
            "orbit"
            if "Starting" in question
            else "word" if "parity word" in question else "census"
        )
        if kind == "orbit":
            x = int(re.search(r"x = (\d+)", question).group(1))
            name, args = "orbit", dict(
                q=3, c=c, x=x, max_steps=10000
            )
        elif kind == "word":
            word = re.search(r"word ([01]+)", question).group(1)
            name, args = "word_cycle", dict(q=3, c=c, word=word)
        else:
            L = int(
                re.search(r"at most (\d+)", question).group(1)
            )
            name, args = "cycle_census", dict(q=3, c=c, max_len=L)
        last = body["messages"][-1]
        if "tools" in body and last["role"] == "user":
            if kind == "census":
                args = dict(args, max_len=str(args["max_len"]))
            msg = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": name,
                            "arguments": json.dumps(args),
                        },
                    }
                ],
            }
        elif "tools" in body and "error" in json.loads(
            last["content"]
        ):
            msg = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_2",
                        "type": "function",
                        "function": {
                            "name": name,
                            "arguments": json.dumps(args),
                        },
                    }
                ],
            }
        else:
            result = json.loads(
                Registry(TOOLS).call(name, json.dumps(args))
            )
            answer = answer_from(kind, result)
            if "tools" not in body and kind == "orbit":
                answer["tail"] += 1
            msg = {
                "role": "assistant",
                "content": json.dumps({"final_answer": answer}),
            }
        data = json.dumps(
            {
                "choices": [
                    {"message": msg, "finish_reason": "stop"}
                ]
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


class TestEndToEnd(unittest.TestCase):
    def test_experiment(self):
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
                                "model": "fake",
                                "base_url": f"http://127.0.0.1:{server.server_port}/v1",
                            }
                        ]
                    }
                )
            )
            out = Path(tmp) / "run"
            argv = [
                "--config",
                str(cfg),
                "--samples",
                "1",
                "--workers",
                "1",
                "--out",
                str(out),
            ]
            run_main(argv)
            run_main(argv)  # resume: nothing left to do
            records = load(out / "results.jsonl")
            self.assertEqual(len(records), 2 * len(make_tasks()))
            rows = summarize(records)
            self.assertEqual(rows[("fake", "tools")]["acc"], 1.0)
            self.assertEqual(
                rows[("fake", "plain")]["by_kind"]["orbit"], 0
            )
            stats = tool_stats(
                [r for r in records if r["mode"] == "tools"]
            )
            self.assertEqual(
                stats["conversations_with_rejection"], 8
            )
            self.assertEqual(stats["of_which_correct"], 8)
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    unittest.main()
