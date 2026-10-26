"""Orchestrator: routes claims through the evidence gates."""

from .ledger import Evidence


class Orchestrator:
    def __init__(
        self,
        kg,
        ledger,
        generator,
        search,
        critic,
        verifier,
        human,
        max_rounds=5,
    ):
        self.kg, self.ledger = kg, ledger
        self.gen, self.search, self.critic = generator, search, critic
        self.verifier, self.human, self.max_rounds = (
            verifier,
            human,
            max_rounds,
        )
        self.counter = 0

    def _register(self, claim, parent=None, rel=None):
        self.counter += 1
        claim.id = f"C{self.counter}"
        self.kg.add(
            claim.id,
            "claim",
            claim.text(),
            evidence=Evidence.PROPOSED,
        )
        if parent:
            self.kg.relate(claim.id, rel, parent)
        self.ledger.record(
            "orchestrator",
            "register",
            claim.id,
            statement=claim.text(),
        )
        return claim

    def run(self, coeffs, observed_up_to):
        claim = self._register(
            self.gen.propose(coeffs, observed_up_to)
        )
        for _ in range(self.max_rounds):
            ok, why = self.critic.review(claim)
            self.ledger.record(
                "critic", "review", claim.id, ok=ok, reason=why
            )
            if not ok:
                return claim, "rejected by critic: " + why
            self.kg.set_evidence(claim.id, Evidence.SUPPORTED)

            hit = self.search.find_counterexample(claim)
            if hit is not None:  # gate 1: refutation
                n, value = hit
                cx = self.kg.add(
                    f"X{claim.id}",
                    "counterexample",
                    f"n={n}: {value} is not prime",
                )
                self.kg.relate(cx, "refutes", claim.id)
                self.kg.set_evidence(claim.id, Evidence.REFUTED)
                self.ledger.record(
                    "search", "refuted", claim.id, n=n, value=value
                )
                claim = self._register(
                    self.critic.refine_after(claim, n),
                    claim.id,
                    "refines",
                )
                continue
            self.kg.set_evidence(claim.id, Evidence.SURVIVED_SEARCH)

            # gate 2: certification
            level, why = self.verifier.certify(claim)
            self.kg.set_evidence(claim.id, level)
            self.ledger.record(
                "verifier",
                "certify",
                claim.id,
                level=level.name,
                reason=why,
            )
            if level < Evidence.CERTIFIED:
                return claim, "open: " + why

            # gate 3: formal proof
            source, result = self.verifier.formalize_and_check(claim)
            if result["status"] != "checked":
                return (
                    claim,
                    f"certified, formal proof {result['status']}",
                )
            # gate 4: human review
            approved, who = self.human.approve(claim, source)
            self.ledger.record(
                "human",
                "statement-match",
                claim.id,
                approved=approved,
                by=who,
            )
            if approved:
                proof = self.kg.add(
                    f"P{claim.id}",
                    "proof",
                    "Lean 4 kernel proof (decide)",
                )
                self.kg.relate(proof, "proves", claim.id)
                self.kg.set_evidence(
                    claim.id, Evidence.FORMALLY_VERIFIED
                )
                return claim, "formally verified and approved"
            return claim, "formal proof not approved by reviewer"
        return claim, "stopped: round budget exhausted"
