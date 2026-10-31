import unittest

from discovery_loop import (
    EvidenceLedger,
    find_counterexample,
    is_prime,
    polynomial,
)


class DiscoveryLoopTests(unittest.TestCase):
    def test_polynomial_has_expected_initial_values(self) -> None:
        self.assertEqual([polynomial(n) for n in range(4)], [5, 7, 11, 17])

    def test_exact_primality_check(self) -> None:
        self.assertTrue(is_prime(17))
        self.assertFalse(is_prime(25))
        self.assertFalse(is_prime(1))

    def test_search_finds_first_counterexample(self) -> None:
        self.assertEqual(find_counterexample(10), 4)

    def test_ledger_hash_chain(self) -> None:
        ledger = EvidenceLedger()
        ledger.record("generator", "proposed", claim_id="C1")
        ledger.record("search", "refuted", claim_id="C1", n=4)
        self.assertTrue(ledger.verify())
        ledger.entries[0]["action"] = "changed"
        self.assertFalse(ledger.verify())


if __name__ == "__main__":
    unittest.main()
