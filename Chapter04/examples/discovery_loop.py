"""A tiny, deterministic example of an agentic mathematical discovery loop."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from math import isqrt
from typing import Any


def polynomial(n: int) -> int:
    """Evaluate the example polynomial n^2 + n + 5."""
    return n * n + n + 5


def is_prime(value: int) -> bool:
    """Return whether value is prime using exact trial division."""
    if value < 2:
        return False
    for divisor in range(2, isqrt(value) + 1):
        if value % divisor == 0:
            return False
    return True


def first_factor(value: int) -> int | None:
    """Return the smallest non-trivial factor, or None if value is prime."""
    for divisor in range(2, isqrt(value) + 1):
        if value % divisor == 0:
            return divisor
    return None


def find_counterexample(max_n: int) -> int | None:
    """Find the first n in [0, max_n] where the polynomial is not prime."""
    for n in range(max_n + 1):
        if not is_prime(polynomial(n)):
            return n
    return None


@dataclass(frozen=True)
class Claim:
    claim_id: str
    upper_exclusive: int | None

    def statement(self) -> str:
        if self.upper_exclusive is None:
            return "n^2 + n + 5 is prime for every n >= 0"
        return (
            "n^2 + n + 5 is prime for "
            f"0 <= n < {self.upper_exclusive}"
        )


class EvidenceLedger:
    """An in-memory, append-only ledger with a verifiable hash chain."""

    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []
        self._head = "0" * 64

    def record(self, actor: str, action: str, **details: Any) -> None:
        entry = {
            "sequence": len(self.entries) + 1,
            "actor": actor,
            "action": action,
            "details": details,
            "previous_hash": self._head,
        }
        encoded = json.dumps(
            entry, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        digest = hashlib.sha256(encoded).hexdigest()
        self.entries.append({**entry, "hash": digest})
        self._head = digest

    def verify(self) -> bool:
        previous_hash = "0" * 64
        for expected_sequence, entry in enumerate(self.entries, start=1):
            body = {key: value for key, value in entry.items() if key != "hash"}
            if body["sequence"] != expected_sequence:
                return False
            if body["previous_hash"] != previous_hash:
                return False
            encoded = json.dumps(
                body, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
            digest = hashlib.sha256(encoded).hexdigest()
            if entry["hash"] != digest:
                return False
            previous_hash = digest
        return True


def run_demo(
    max_n: int = 100,
    suggested_candidate: tuple[int, str] | None = None,
) -> None:
    ledger = EvidenceLedger()

    original = Claim("C1", upper_exclusive=None)
    ledger.record(
        "generator",
        "proposed",
        claim_id=original.claim_id,
        statement=original.statement(),
    )
    print(f"PROPOSED {original.claim_id}: {original.statement()}")

    if suggested_candidate is not None:
        candidate, reason = suggested_candidate
        if not 0 <= candidate <= max_n:
            raise ValueError(
                f"Suggested candidate must be between 0 and {max_n}"
            )
        value = polynomial(candidate)
        factor = first_factor(value)
        ledger.record(
            "ollama",
            "candidate_suggested",
            claim_id=original.claim_id,
            n=candidate,
            value=value,
            reason=reason,
            verified_counterexample=factor is not None,
        )
        if factor is None:
            print(
                f"OLLAMA: suggested n={candidate}; exact check found "
                f"{value} prime, so this is not a counterexample"
            )
        else:
            print(
                f"OLLAMA: suggested n={candidate}; exact check confirms "
                f"{value} = {factor} * {value // factor}"
            )

    counterexample = find_counterexample(max_n)
    if counterexample is None:
        raise RuntimeError(
            f"No counterexample found in the stated search range 0..{max_n}"
        )

    counterexample_value = polynomial(counterexample)
    factor = first_factor(counterexample_value)
    if factor is None:
        raise RuntimeError("Search returned a value that is still prime")
    ledger.record(
        "search",
        "counterexample_found",
        claim_id=original.claim_id,
        n=counterexample,
        value=counterexample_value,
        factor=factor,
    )
    print(
        f"SEARCH: counterexample n={counterexample}, "
        f"value={counterexample_value} = "
        f"{factor} * {counterexample_value // factor}"
    )

    refined = Claim("C2", upper_exclusive=counterexample)
    ledger.record(
        "critic",
        "refined",
        claim_id=refined.claim_id,
        parent_id=original.claim_id,
        statement=refined.statement(),
    )
    print(f"REFINED {refined.claim_id}: {refined.statement()}")

    checked_values = range(refined.upper_exclusive or 0)
    if not all(is_prime(polynomial(n)) for n in checked_values):
        raise RuntimeError("The refined finite-range claim did not pass")
    ledger.record(
        "verifier",
        "finite_range_checked",
        claim_id=refined.claim_id,
        checked_n=refined.upper_exclusive,
        result="all_prime",
        method="exact trial division",
    )
    print(
        "EXACT CHECK: all "
        f"{refined.upper_exclusive} values in the finite range are prime"
    )
    print(
        "LIMIT: checking a finite range does not prove the original "
        "universal claim"
    )

    if not ledger.verify():
        raise RuntimeError("Evidence ledger hash-chain verification failed")
    print(f"LEDGER: valid hash chain ({len(ledger.entries)} entries)")


if __name__ == "__main__":
    run_demo()
