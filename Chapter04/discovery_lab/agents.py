"""The roles: generator, search, critic, verifier, Lean, human."""

from dataclasses import dataclass, field
import sympy as sp
from .ledger import Evidence


@dataclass
class Claim:
    """For all n with lo <= n < hi, poly(n) is prime.

    hi=None means: for all n >= lo.
    """

    coeffs: tuple
    lo: int = 0
    hi: int = None
    id: str = ""
    history: list = field(default_factory=list)

    def poly(self, n):
        a, b, c = self.coeffs
        return a * n * n + b * n + c

    def text(self):
        a, b, c = self.coeffs
        rng = f"{self.lo} <= n" + (
            f" < {self.hi}" if self.hi is not None else ""
        )
        return f"for all n with {rng}: {a}n^2 + {b}n + {c} is prime"


class Generator:
    """Proposes a conjecture from data.

    Swap in an LLM here; the interface stays the same.
    """

    def __init__(self, llm=None):
        self.llm = llm

    def propose(self, coeffs, observed_up_to):
        if self.llm is not None:
            return self.llm.propose(coeffs, observed_up_to)
        # Fallback: generalize the observed pattern (an overreach).
        return Claim(coeffs=coeffs, lo=0, hi=None)


class SearchAgent:
    """Tries to refute a claim within an explicit budget."""

    def __init__(self, gateway, budget=10_000):
        self.gw, self.budget = gateway, budget

    def find_counterexample(self, claim):
        hi = (
            claim.hi
            if claim.hi is not None
            else claim.lo + self.budget
        )
        for n in range(claim.lo, hi):
            value = claim.poly(n)
            if not self.gw.call(
                "isprime", "search", claim.id, k=value
            ):
                return n, value
        return None


class Critic:
    """Rejects claims that are malformed, trivial, or already known."""

    def __init__(self, kg):
        self.kg = kg

    def review(self, claim):
        if claim.hi is not None and claim.hi <= claim.lo:
            return False, "empty range: the claim is vacuous"
        if self.kg.known(claim.text(), exclude=claim.id):
            return False, "already in the knowledge graph"
        return True, "ok"

    def refine_after(self, claim, n):
        """Strongest finite claim that the counterexample allows."""
        return Claim(coeffs=claim.coeffs, lo=claim.lo, hi=n)


class Verifier:
    """Exact certification, then a formal proof via the Lean agent."""

    def __init__(self, gateway, lean_agent):
        self.gw, self.lean = gateway, lean_agent

    def certify(self, claim):
        if claim.hi is None:
            return (
                Evidence.SURVIVED_SEARCH,
                "infinite range: exact check impossible",
            )
        ok = all(
            self.gw.call(
                "isprime", "verifier", claim.id, k=claim.poly(n)
            )
            for n in range(claim.lo, claim.hi)
        )
        return (
            (Evidence.CERTIFIED, "exhaustive exact check")
            if ok
            else (Evidence.REFUTED, "exact check failed")
        )

    def formalize_and_check(self, claim):
        source = self.lean.formalize(claim)
        result = self.gw.call(
            "lean", "lean-agent", claim.id, source=source
        )
        return source, result


class LeanAgent:
    """Formalizer: a template here, an LLM with repair in Chapter 10."""

    PRELUDE = """def noDivisorFrom (n : Nat) : Nat -> Nat -> Bool
  | 0, _ => true
  | fuel + 1, d =>
    if n < d * d then true
    else if n % d == 0 then false
    else noDivisorFrom n fuel (d + 1)

def isPrime (n : Nat) : Bool := 2 <= n && noDivisorFrom n n 2

set_option maxRecDepth 10000
"""

    def formalize(self, claim):
        a, b, c = claim.coeffs
        # Bounded quantifier m < hi - lo, so that `decide` applies.
        n = f"(m + {claim.lo})"
        return self.PRELUDE + f"""
theorem discovered :
    forall m, m < {claim.hi - claim.lo} ->
      isPrime ({a} * {n} * {n} + {b} * {n} + {c}) = true := by
  decide

#print axioms discovered
"""


class HumanGate:
    """Human checkpoint: does the formal statement say what we meant?"""

    def __init__(self, policy="ask"):
        self.policy = policy

    def approve(self, claim, lean_source):
        if self.policy == "auto-approve":  # tests and batch runs only
            return True, "auto-approved (test policy)"
        print(
            "\n--- HUMAN REVIEW ---\n"
            + claim.text()
            + "\n"
            + lean_source
        )
        return (
            input("Does the Lean statement match the claim? [y/N] ")
            .strip()
            .lower()
            == "y",
            "human",
        )
