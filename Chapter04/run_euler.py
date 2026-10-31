"""End-to-end run on Euler's prime-generating polynomial n^2 + n + 41."""

import argparse

import sympy as sp

from discovery_lab.agents import (
    Critic,
    Generator,
    HumanGate,
    LeanAgent,
    SearchAgent,
    Verifier,
)
from discovery_lab.cli import default_lean
from discovery_lab.kg import MathKG
from discovery_lab.ledger import Ledger
from discovery_lab.orchestrator import Orchestrator
from discovery_lab.tools import ToolGateway, lean_check

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--lean", default=default_lean())
parser.add_argument("--interactive", action="store_true",
                    help="ask a human instead of the auto-approve policy")
args = parser.parse_args()

ledger, kg = Ledger("ledger.jsonl"), MathKG()
gw = ToolGateway(ledger)
gw.register("isprime", lambda k: bool(sp.isprime(k)), "exact primality")
gw.register("lean", lambda source: lean_check(source, args.lean),
            "Lean 4 kernel check")

orch = Orchestrator(kg, ledger, Generator(), SearchAgent(gw), Critic(kg),
                    Verifier(gw, LeanAgent()), HumanGate(policy="auto-approve"))
if args.interactive:
    orch.human = HumanGate(policy="ask")
claim, outcome = orch.run(coeffs=(1, 1, 41), observed_up_to=20)

for node, data in kg.g.nodes(data=True):
    level = data.get("evidence")
    tag = level.name if level is not None else ""
    print(f"{node:4} {data['kind']:15} {tag}")
    print(f"     {data['statement']}")

print("\nFinal:", claim.text())
print("Status:", outcome)
