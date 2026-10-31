from io import BytesIO
import json
from pathlib import Path
import ssl
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError

from end_to_end_discovery import (
    Claim,
    DiscoveryDatabase,
    Evidence,
    EvidenceLedger,
    KnowledgeGraph,
    first_factor,
    human_review,
    interpretation_review,
    is_prime,
    openalex_search,
    polynomial,
    run,
)


class EndToEndDiscoveryTests(unittest.TestCase):
    def test_exact_arithmetic(self) -> None:
        self.assertEqual(polynomial(5, 4), 25)
        self.assertEqual(first_factor(25), 5)
        self.assertFalse(is_prime(25))
        self.assertTrue(is_prime(17))

    def test_claim_graph_records_refinement_and_refutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "graph.sqlite3"
            database = DiscoveryDatabase(path)
            database.start_run("test", {})
            graph = KnowledgeGraph(database, "test")
            original = Claim("C1", 5)
            refined = Claim("C2", 5, upper_exclusive=4, parent_id="C1")
            graph.add_claim(original, Evidence.PROPOSED)
            graph.add_claim(refined, Evidence.SURVIVED_SEARCH)
            counterexample_id = graph.add_counterexample(
                original, 4, 25, 5
            )
            snapshot = graph.snapshot()
            self.assertEqual(
                next(node for node in snapshot["nodes"]
                     if node["id"] == counterexample_id)["kind"],
                "counterexample",
            )
            self.assertIn(
                {"source": "C2", "relation": "refines", "target": "C1"},
                snapshot["edges"],
            )
            database.close()

            reopened = DiscoveryDatabase(path)
            self.assertEqual(
                len(reopened.graph_snapshot("test")["nodes"]),
                3,
            )
            reopened.close()

    def test_ledger_detects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = DiscoveryDatabase(Path(directory) / "ledger.sqlite3")
            database.start_run("test", {})
            ledger = EvidenceLedger(database, "test")
            ledger.record("generator", "proposed", claim_id="C1")
            self.assertTrue(ledger.verify())
            database.connection.execute(
                "UPDATE evidence_events SET action='altered'"
            )
            database.connection.commit()
            self.assertFalse(ledger.verify())
            database.close()

    @patch(
        "end_to_end_discovery.urlopen",
        return_value=BytesIO(
            b'{"meta":{"count":1},"results":[{"id":"https://openalex.org/W1",'
            b'"title":"A candidate paper","publication_year":2024,'
            b'"doi":"https://doi.org/10/example",'
            b'"primary_location":{"landing_page_url":"https://example.org",'
            b'"source":{"display_name":"Example Journal"}}}]}'
        ),
    )
    def test_openalex_search_returns_candidate_sources(self, mock_urlopen) -> None:
        result = openalex_search("prime generating polynomial")
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["works"][0]["title"], "A candidate paper")
        self.assertIn("do not establish novelty", result["interpretation"])
        self.assertIn("api.openalex.org/works", mock_urlopen.call_args.args[0].full_url)

    @patch(
        "end_to_end_discovery.urlopen",
        side_effect=URLError(ssl.SSLCertVerificationError("untrusted issuer")),
    )
    def test_openalex_certificate_errors_explain_trust_configuration(
        self, _mock_urlopen
    ) -> None:
        with self.assertRaisesRegex(RuntimeError, "TLS certificate verification"):
            openalex_search("prime generating polynomial")

    @patch("builtins.input", return_value="y")
    def test_interactive_review_requires_explicit_approval(self, _mock_input) -> None:
        claim = Claim("C2", 5, upper_exclusive=4, parent_id="C1")
        lean_result = {"status": "checked"}
        self.assertTrue(human_review(claim, lean_result, auto=False))
        with patch("builtins.input", return_value="n"):
            self.assertFalse(human_review(claim, lean_result, auto=False))

    def test_interpretation_review_records_limited_release(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "interpretation.sqlite3"
            database = DiscoveryDatabase(path)
            database.start_run("interpretation-run", {})
            graph = KnowledgeGraph(database, "interpretation-run")
            original = Claim("C1", 41)
            refined = Claim(
                "C2",
                41,
                upper_exclusive=40,
                parent_id="C1",
            )
            graph.add_claim(original, Evidence.REFUTED)
            graph.add_counterexample(original, 40, 1681, 41)
            graph.add_claim(refined, Evidence.FORMALLY_VERIFIED)
            database.add_node(
                "interpretation-run",
                "P-C2",
                "proof",
                "Lean kernel check",
                "FORMAL",
            )
            database.add_edge(
                "interpretation-run",
                "P-C2",
                "proves",
                "C2",
            )
            database.close()

            outcome, approved = interpretation_review(
                path,
                run_id="interpretation-run",
                auto=True,
            )
            self.assertTrue(approved)
            self.assertIn("finite refinement released", outcome)

            reopened = DiscoveryDatabase(path)
            self.assertTrue(reopened.verify_ledger())
            result = reopened.connection.execute(
                "SELECT outcome FROM run_results WHERE run_id=?",
                ("interpretation-run",),
            ).fetchone()
            self.assertIn("universal claim refuted", result["outcome"])
            review = reopened.connection.execute(
                "SELECT action FROM evidence_events "
                "WHERE run_id=? AND action='interpretation_review'",
                ("interpretation-run",),
            ).fetchone()
            self.assertIsNotNone(review)
            reopened.close()

    @patch("end_to_end_discovery.lean_check")
    def test_complete_orchestration_with_injected_model_and_lean(
        self, mock_lean_check
    ) -> None:
        mock_lean_check.side_effect = lambda claim, lean_command, ledger, artifact_dir=None: {
            "status": "checked",
            "claim": claim.statement(),
            "source": "theorem checked := by decide",
            "log": "no axioms",
            "lean_version": "test Lean",
            "artifact_path": None,
        }
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "discovery.sqlite3"
            outcome = run(
                model="test-model",
                host="http://localhost:11434",
                max_n=100,
                database_path=database_path,
                lean_command="lean",
                auto_approve=True,
                workers=1,
                offline_literature=True,
                proposer=lambda _model, _host, _timeout: (
                    5,
                    "small illustrative polynomial",
                ),
            )
            self.assertEqual(outcome, "finite claim exact-checked and approved")
            database = DiscoveryDatabase(database_path)
            self.assertTrue(database.verify_ledger())
            events = database.connection.execute(
                "SELECT action FROM evidence_events WHERE run_id IN "
                "(SELECT run_id FROM runs ORDER BY started_at DESC LIMIT 1)"
            ).fetchall()
            actions = [event["action"] for event in events]
            self.assertIn("proposed", actions)
            self.assertIn("refuted", actions)
            self.assertIn("refined_after_counterexample", actions)
            self.assertIn("statement_match_review", actions)
            worker_pids = database.connection.execute(
                "SELECT DISTINCT worker_pid FROM worker_metrics"
            ).fetchall()
            self.assertTrue(worker_pids)
            graph = database.connection.execute(
                "SELECT COUNT(*) AS count FROM graph_nodes"
            ).fetchone()
            self.assertGreaterEqual(graph["count"], 3)
            formal_claim = database.connection.execute(
                "SELECT evidence FROM graph_nodes WHERE node_id LIKE 'C2-%'"
            ).fetchone()
            self.assertEqual(formal_claim["evidence"], Evidence.FORMALLY_VERIFIED.name)
            proof_edge = database.connection.execute(
                "SELECT relation FROM graph_edges WHERE relation='proves'"
            ).fetchone()
            self.assertIsNotNone(proof_edge)
            literature = database.connection.execute(
                "SELECT status FROM literature_searches ORDER BY search_id DESC LIMIT 1"
            ).fetchone()
            self.assertEqual(literature["status"], "skipped")
            database.close()


if __name__ == "__main__":
    unittest.main()
