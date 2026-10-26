"""End-to-end run on Euler's prime-generating polynomial n^2 + n + 41."""

import sys
import sympy as sp
from discovery_lab.ledger import Ledger
from discovery_lab.kg import MathKG
from discovery_lab.tools import ToolGateway, lean_check
from discovery_lab.agents import (
    Generator,
    SearchAgent,
    Critic,
    Verifier,
    LeanAgent,
    HumanGate,
)
from discovery_lab.orchestrator import Orchestrator

lean_cmd = sys.argv[1] if len(sys.argv) > 1 else "lean"
ledger, kg = Ledger("ledger.jsonl"), MathKG()
gw = ToolGateway(ledger)
gw.register(
    "isprime",
    lambda k: bool(sp.isprime(k)),
    "exact primality test (SymPy)",
)
gw.register(
    "lean",
    lambda source: lean_check(source, lean_cmd),
    "Lean 4 kernel check",
)

orch = Orchestrator(
    kg,
    ledger,
    Generator(),
    SearchAgent(gw),
    Critic(kg),
    Verifier(gw, LeanAgent()),
    HumanGate(policy="auto-approve"),
)
claim, outcome = orch.run(coeffs=(1, 1, 41), observed_up_to=20)

for node, data in kg.g.nodes(data=True):
    level = data.get("evidence")
    tag = level.name if level is not None else ""
    print(f"{node:4} {data['kind']:15} {tag}")
    print(f"     {data['statement']}")
print("\nFinal:", claim.text())
print("Status:", outcome)
