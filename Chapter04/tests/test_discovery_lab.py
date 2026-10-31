"""Tests for the book's reference package discovery_lab."""
import hashlib
import json
import os
import tempfile
import unittest

import sympy as sp

from discovery_lab.agents import (Claim, Critic, Generator, HumanGate,
                                  LeanAgent, SearchAgent, Verifier)
from discovery_lab.cli import default_lean
from discovery_lab.kg import MathKG
from discovery_lab.ledger import Ledger
from discovery_lab.orchestrator import Orchestrator
from discovery_lab.tools import ToolGateway, lean_check

LEAN = default_lean()
HAS_LEAN = lean_check("#eval 1", LEAN)["status"] == "checked"


def build(tmp, lean_cmd=LEAN):
    ledger, kg = Ledger(os.path.join(tmp, "ledger.jsonl")), MathKG()
    gw = ToolGateway(ledger)
    gw.register("isprime", lambda k: bool(sp.isprime(k)), "primality")
    gw.register("lean", lambda source: lean_check(source, lean_cmd), "Lean")
    orch = Orchestrator(kg, ledger, Generator(), SearchAgent(gw),
                        Critic(kg), Verifier(gw, LeanAgent()),
                        HumanGate(policy="auto-approve"))
    return orch, ledger, gw


class ReferenceTests(unittest.TestCase):
    def test_counterexample_at_40(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, gw = build(tmp)
            hit = SearchAgent(gw).find_counterexample(Claim((1, 1, 41)))
            self.assertEqual(hit, (40, 1681))

    def test_critic_rejects_vacuous_range(self):
        ok, _ = Critic(MathKG()).review(Claim((1, 1, 41), lo=5, hi=5))
        self.assertFalse(ok)

    def test_ledger_hash_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch, ledger, _ = build(tmp, lean_cmd="/nonexistent/lean")
            orch.run(coeffs=(1, 1, 41), observed_up_to=20)
            prev = "0" * 64
            with open(ledger.path) as f:
                for line in f:
                    self.assertEqual(json.loads(line)["prev"], prev)
                    prev = hashlib.sha256(line.rstrip("\n").encode()).hexdigest()

    def test_without_lean_reports_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch, _, _ = build(tmp, lean_cmd="/nonexistent/lean")
            _, outcome = orch.run(coeffs=(1, 1, 41), observed_up_to=20)
            self.assertEqual(outcome, "certified, formal proof unavailable")

    @unittest.skipUnless(HAS_LEAN, "Lean 4 not available")
    def test_euler_run_is_formally_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch, _, _ = build(tmp)
            claim, outcome = orch.run(coeffs=(1, 1, 41), observed_up_to=20)
            self.assertEqual(outcome, "formally verified and approved")
            self.assertEqual((claim.lo, claim.hi), (0, 40))

    @unittest.skipUnless(HAS_LEAN, "Lean 4 not available")
    def test_false_claim_is_rejected_by_lean(self):
        source = LeanAgent().formalize(Claim((1, 1, 41), lo=0, hi=41))
        self.assertEqual(lean_check(source, LEAN)["status"], "failed")

    @unittest.skipUnless(HAS_LEAN, "Lean 4 not available")
    def test_sorry_is_rejected(self):
        source = LeanAgent.PRELUDE + (
            "\ntheorem t : forall n, n < 1000 -> "
            "isPrime (n*n+n+41) = true := by\n  sorry\n")
        self.assertEqual(lean_check(source, LEAN)["status"], "failed")


if __name__ == "__main__":
    unittest.main()
