"""A small end-to-end discovery workflow with Ollama, exact checks, and Lean."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from enum import IntEnum
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import platform
import shutil
import sqlite3
import ssl
import subprocess
import tempfile
import time
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import uuid


GENERATOR_PROMPT = (
    "For this reproducible worked example, formalize the seeded candidate "
    "n^2+n+5 as the conjecture that it is prime for every integer n >= 0. "
    "Return only JSON with integer field 'constant' set to 5 and a short "
    "string field 'reason'. This is a proposed claim, not a proof."
)


@dataclass(frozen=True)
class Claim:
    claim_id: str
    constant: int
    upper_exclusive: int | None = None
    parent_id: str | None = None

    def statement(self) -> str:
        polynomial = f"n^2 + n + {self.constant}"
        if self.upper_exclusive is None:
            return f"{polynomial} is prime for every integer n >= 0"
        return (
            f"{polynomial} is prime for integers "
            f"0 <= n < {self.upper_exclusive}"
        )


class Evidence(IntEnum):
    REFUTED = -1
    PROPOSED = 0
    SUPPORTED = 1
    SURVIVED_SEARCH = 2
    VALIDATED = 3
    CERTIFIED = 4
    FORMALLY_VERIFIED = 5


def json_default(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, IntEnum):
        return value.name
    raise TypeError(f"Object is not JSON serializable: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        default=json_default,
    )


class DiscoveryDatabase:
    """Persistent local graph, run metadata, source cache, and evidence ledger."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, timeout=30)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA journal_mode = WAL")
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                configuration_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS run_results (
                run_id TEXT PRIMARY KEY REFERENCES runs(run_id),
                outcome TEXT NOT NULL,
                error TEXT,
                completed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS graph_nodes (
                run_id TEXT NOT NULL REFERENCES runs(run_id),
                node_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                statement TEXT NOT NULL,
                evidence TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                PRIMARY KEY (run_id, node_id)
            );
            CREATE TABLE IF NOT EXISTS graph_edges (
                run_id TEXT NOT NULL REFERENCES runs(run_id),
                source_id TEXT NOT NULL,
                relation TEXT NOT NULL,
                target_id TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                PRIMARY KEY (run_id, source_id, relation, target_id),
                FOREIGN KEY (run_id, source_id)
                    REFERENCES graph_nodes(run_id, node_id),
                FOREIGN KEY (run_id, target_id)
                    REFERENCES graph_nodes(run_id, node_id)
            );
            CREATE TABLE IF NOT EXISTS evidence_events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL REFERENCES runs(run_id),
                actor TEXT NOT NULL,
                action TEXT NOT NULL,
                details_json TEXT NOT NULL,
                previous_hash TEXT NOT NULL,
                digest TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS literature_searches (
                search_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL REFERENCES runs(run_id),
                provider TEXT NOT NULL,
                query TEXT NOT NULL,
                status TEXT NOT NULL,
                response_json TEXT NOT NULL,
                retrieved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS worker_metrics (
                metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL REFERENCES runs(run_id),
                role TEXT NOT NULL,
                worker_pid INTEGER NOT NULL,
                duration_ms REAL NOT NULL,
                task_count INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS artifacts (
                artifact_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL REFERENCES runs(run_id),
                kind TEXT NOT NULL,
                path TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        self.connection.commit()

    def start_run(self, run_id: str, configuration: dict[str, Any]) -> None:
        self.connection.execute(
            "INSERT INTO runs (run_id, configuration_json) VALUES (?, ?)",
            (run_id, canonical_json(configuration)),
        )
        self.connection.commit()

    def record_event(
        self, run_id: str, actor: str, action: str, details: dict[str, Any]
    ) -> None:
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            last = self.connection.execute(
                "SELECT sequence, digest FROM evidence_events "
                "ORDER BY sequence DESC LIMIT 1"
            ).fetchone()
            sequence = 1 if last is None else int(last["sequence"]) + 1
            previous_hash = "0" * 64 if last is None else str(last["digest"])
            body = {
                "sequence": sequence,
                "run_id": run_id,
                "actor": actor,
                "action": action,
                "details": details,
                "previous_hash": previous_hash,
            }
            digest = hashlib.sha256(
                canonical_json(body).encode("utf-8")
            ).hexdigest()
            self.connection.execute(
                """
                INSERT INTO evidence_events
                    (sequence, run_id, actor, action, details_json,
                     previous_hash, digest)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sequence,
                    run_id,
                    actor,
                    action,
                    canonical_json(details),
                    previous_hash,
                    digest,
                ),
            )
            self.connection.commit()
        except sqlite3.Error:
            self.connection.rollback()
            raise

    def verify_ledger(self) -> bool:
        previous_hash = "0" * 64
        rows = self.connection.execute(
            "SELECT sequence, run_id, actor, action, details_json, "
            "previous_hash, digest FROM evidence_events ORDER BY sequence"
        ).fetchall()
        for expected_sequence, row in enumerate(rows, start=1):
            if row["sequence"] != expected_sequence:
                return False
            if row["previous_hash"] != previous_hash:
                return False
            body = {
                "sequence": row["sequence"],
                "run_id": row["run_id"],
                "actor": row["actor"],
                "action": row["action"],
                "details": json.loads(row["details_json"]),
                "previous_hash": row["previous_hash"],
            }
            expected = hashlib.sha256(
                canonical_json(body).encode("utf-8")
            ).hexdigest()
            if row["digest"] != expected:
                return False
            previous_hash = row["digest"]
        return True

    def add_node(
        self,
        run_id: str,
        node_id: str,
        kind: str,
        statement: str,
        evidence: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO graph_nodes
                (run_id, node_id, kind, statement, evidence, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id, node_id) DO UPDATE SET
                kind=excluded.kind,
                statement=excluded.statement,
                evidence=excluded.evidence,
                metadata_json=excluded.metadata_json
            """,
            (
                run_id,
                node_id,
                kind,
                statement,
                evidence,
                canonical_json(metadata or {}),
            ),
        )
        self.connection.commit()

    def add_edge(
        self,
        run_id: str,
        source_id: str,
        relation: str,
        target_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.connection.execute(
            """
            INSERT OR IGNORE INTO graph_edges
                (run_id, source_id, relation, target_id, metadata_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                run_id,
                source_id,
                relation,
                target_id,
                canonical_json(metadata or {}),
            ),
        )
        self.connection.commit()

    def set_evidence(self, run_id: str, node_id: str, evidence: str) -> None:
        cursor = self.connection.execute(
            "UPDATE graph_nodes SET evidence=? WHERE run_id=? AND node_id=?",
            (evidence, run_id, node_id),
        )
        if cursor.rowcount != 1:
            raise KeyError(f"Unknown graph node: {node_id}")
        self.connection.commit()

    def record_literature_search(
        self, run_id: str, query: str, status: str, response: dict[str, Any]
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO literature_searches
                (run_id, provider, query, status, response_json)
            VALUES (?, 'OpenAlex', ?, ?, ?)
            """,
            (run_id, query, status, canonical_json(response)),
        )
        self.connection.commit()

    def add_worker_metric(
        self,
        run_id: str,
        role: str,
        worker_pid: int,
        duration_ms: float,
        task_count: int,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO worker_metrics
                (run_id, role, worker_pid, duration_ms, task_count)
            VALUES (?, ?, ?, ?, ?)
            """,
            (run_id, role, worker_pid, duration_ms, task_count),
        )
        self.connection.commit()

    def add_artifact(self, run_id: str, kind: str, path: Path) -> None:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        self.connection.execute(
            "INSERT INTO artifacts (run_id, kind, path, sha256) "
            "VALUES (?, ?, ?, ?)",
            (run_id, kind, str(path), digest),
        )
        self.connection.commit()

    def finish_run(
        self, run_id: str, outcome: str, error: str | None = None
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO run_results (run_id, outcome, error)
            VALUES (?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                outcome=excluded.outcome,
                error=excluded.error,
                completed_at=CURRENT_TIMESTAMP
            """,
            (run_id, outcome, error),
        )
        self.connection.commit()

    def graph_snapshot(self, run_id: str) -> dict[str, Any]:
        nodes = self.connection.execute(
            "SELECT node_id, kind, statement, evidence, metadata_json "
            "FROM graph_nodes WHERE run_id=? ORDER BY node_id",
            (run_id,),
        ).fetchall()
        edges = self.connection.execute(
            "SELECT source_id, relation, target_id FROM graph_edges "
            "WHERE run_id=? ORDER BY source_id, relation, target_id",
            (run_id,),
        ).fetchall()
        return {
            "nodes": [
                {
                    "id": row["node_id"],
                    "kind": row["kind"],
                    "statement": row["statement"],
                    "evidence": row["evidence"],
                    "metadata": json.loads(row["metadata_json"]),
                }
                for row in nodes
            ],
            "edges": [
                {
                    "source": row["source_id"],
                    "relation": row["relation"],
                    "target": row["target_id"],
                }
                for row in edges
            ],
        }

    def close(self) -> None:
        self.connection.close()


class EvidenceLedger:
    """Append-only hash-chained ledger stored in the SQLite database."""

    def __init__(self, database: DiscoveryDatabase, run_id: str) -> None:
        self.database = database
        self.run_id = run_id

    def record(self, actor: str, action: str, **details: Any) -> None:
        self.database.record_event(self.run_id, actor, action, details)

    def verify(self) -> bool:
        return self.database.verify_ledger()


class KnowledgeGraph:
    """Persistent SQLite-backed claim and evidence graph."""

    def __init__(self, database: DiscoveryDatabase, run_id: str) -> None:
        self.database = database
        self.run_id = run_id

    def add_claim(self, claim: Claim, evidence: Evidence) -> None:
        self.database.add_node(
            self.run_id,
            claim.claim_id,
            "claim",
            claim.statement(),
            evidence.name,
            {"parent_id": claim.parent_id},
        )
        if claim.parent_id is not None:
            self.database.add_edge(
                self.run_id, claim.claim_id, "refines", claim.parent_id
            )

    def add_counterexample(
        self, claim: Claim, n: int, value: int, factor: int
    ) -> str:
        node_id = f"X-{claim.claim_id}"
        self.database.add_node(
            self.run_id,
            node_id,
            "counterexample",
            f"n={n}: {value} = {factor} * {value // factor}",
            "EXACT",
        )
        self.database.add_edge(
            self.run_id, node_id, "refutes", claim.claim_id
        )
        return node_id

    def add_source(
        self,
        source_id: str,
        title: str,
        evidence: str,
        target_claim: str,
        metadata: dict[str, Any],
    ) -> None:
        self.database.add_node(
            self.run_id,
            source_id,
            "source",
            title,
            evidence,
            metadata,
        )
        self.database.add_edge(
            self.run_id,
            source_id,
            "possible_prior_work",
            target_claim,
        )

    def set_evidence(self, claim_id: str, evidence: Evidence) -> None:
        self.database.set_evidence(self.run_id, claim_id, evidence.name)

    def snapshot(self) -> dict[str, Any]:
        return self.database.graph_snapshot(self.run_id)


def polynomial(constant: int, n: int) -> int:
    return n * n + n + constant


def first_factor(value: int) -> int | None:
    if value < 4:
        return None
    divisor = 2
    while divisor * divisor <= value:
        if value % divisor == 0:
            return divisor
        divisor += 1
    return None


def is_prime(value: int) -> bool:
    return value >= 2 and first_factor(value) is None


def openalex_search(
    query: str, timeout: int = 20, email: str | None = None
) -> dict[str, Any]:
    """Search OpenAlex for candidate related works; this is not a novelty proof."""
    parameters: dict[str, str | int] = {"search": query, "per-page": 5}
    if email:
        parameters["mailto"] = email
    request = Request(
        "https://api.openalex.org/works?" + urlencode(parameters),
        headers={"User-Agent": "Chapter4-Math-Discovery-Example/1.0"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"OpenAlex returned HTTP {error.code}: {detail}"
        ) from error
    except URLError as error:
        if isinstance(error.reason, ssl.SSLCertVerificationError):
            raise RuntimeError(
                "OpenAlex TLS certificate verification failed; configure "
                "Python's trusted CA certificates (for example with "
                "SSL_CERT_FILE) and retry"
            ) from error
        raise RuntimeError(
            f"Could not connect to OpenAlex: {error.reason}"
        ) from error
    except (TimeoutError, OSError) as error:
        raise RuntimeError(f"OpenAlex request failed: {error}") from error
    if not isinstance(payload, dict) or not isinstance(
        payload.get("results"), list
    ):
        raise ValueError("OpenAlex returned an unexpected response shape")
    works = []
    for work in payload["results"]:
        if not isinstance(work, dict) or not work.get("id"):
            continue
        location = work.get("primary_location") or {}
        source = location.get("source") or {}
        works.append(
            {
                "id": work["id"],
                "title": work.get("title") or "(untitled)",
                "year": work.get("publication_year"),
                "doi": work.get("doi"),
                "url": location.get("landing_page_url"),
                "venue": source.get("display_name"),
            }
        )
    return {
        "provider": "OpenAlex",
        "query": query,
        "status": "completed",
        "result_count": payload.get("meta", {}).get("count"),
        "works": works,
        "interpretation": (
            "Search hits are candidate sources only; no hits do not establish "
            "novelty, and hit relevance requires human review."
        ),
    }


def _critic_worker(constant: int, n_values: list[int]) -> dict[str, Any]:
    return {
        "worker_pid": os.getpid(),
        "checks": [
            (n, polynomial(constant, n), is_prime(polynomial(constant, n)))
            for n in n_values
        ],
    }


def _search_worker(
    constant: int, start: int, stop_exclusive: int
) -> dict[str, Any]:
    candidate = None
    for n in range(start, stop_exclusive):
        value = polynomial(constant, n)
        factor = first_factor(value)
        if factor is not None:
            candidate = (n, value, factor)
            break
    return {
        "worker_pid": os.getpid(),
        "range": (start, stop_exclusive),
        "counterexample": candidate,
    }


def ollama_propose(
    model: str, host: str, timeout: int
) -> tuple[int, str]:
    """Ask Ollama to formalize the seeded candidate as structured output."""
    request_body = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": GENERATOR_PROMPT}],
            "stream": False,
            "format": {
                "type": "object",
                "properties": {
                    "constant": {"type": "integer", "enum": [5]},
                    "reason": {"type": "string"},
                },
                "required": ["constant", "reason"],
            },
            "options": {"temperature": 0},
        }
    ).encode("utf-8")
    request = Request(
        f"{host.rstrip('/')}/api/chat",
        data=request_body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Ollama returned HTTP {error.code}: {detail}"
        ) from error
    except URLError as error:
        raise RuntimeError(
            f"Could not connect to Ollama at {host}: {error.reason}"
        ) from error
    try:
        content = payload["message"]["content"]
        result = json.loads(content)
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError("Ollama returned an invalid structured proposal") from error

    if not isinstance(result, dict):
        raise ValueError("Ollama proposal must be a JSON object")
    constant = result.get("constant")
    reason = result.get("reason")
    if isinstance(constant, bool) or not isinstance(constant, int):
        raise ValueError("Ollama proposal must contain integer constant")
    if not isinstance(reason, str):
        raise ValueError("Ollama proposal must contain string reason")
    if not 2 <= constant <= 100:
        raise ValueError("Proposed constant must be between 2 and 100")
    return constant, reason


class ToolGateway:
    """Route computations through one place and record calls in the ledger."""

    def __init__(self, ledger: EvidenceLedger) -> None:
        self.ledger = ledger
        self.tools: dict[str, Callable[..., Any]] = {}

    def register(self, name: str, function: Callable[..., Any]) -> None:
        if name in self.tools:
            raise ValueError(f"Tool is already registered: {name}")
        self.tools[name] = function

    def call(self, name: str, caller: str, **arguments: Any) -> Any:
        if name not in self.tools:
            raise KeyError(f"Unknown tool: {name}")
        logged_arguments = {
            key: asdict(value) if isinstance(value, Claim) else value
            for key, value in arguments.items()
        }
        try:
            result = self.tools[name](**arguments)
        except (
            OSError,
            ValueError,
            RuntimeError,
            KeyError,
            TypeError,
            sqlite3.Error,
            subprocess.SubprocessError,
        ) as error:
            self.ledger.record(
                caller,
                f"tool:{name}:failed",
                arguments=logged_arguments,
                error=f"{type(error).__name__}: {error}",
            )
            raise
        self.ledger.record(
            caller, f"tool:{name}", arguments=logged_arguments, result=result
        )
        return result


def lean_check(
    claim: Claim,
    lean_command: str,
    ledger: EvidenceLedger,
    artifact_dir: Path | None = None,
) -> dict[str, Any]:
    """Ask Lean to compute the bounded primality checks and counterexample."""
    executable = shutil.which(lean_command)
    if executable is None and Path(lean_command).is_file():
        executable = str(Path(lean_command))
    if executable is None:
        return {"status": "unavailable", "reason": "Lean executable not found"}

    try:
        version = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "failed",
            "reason": "Lean version command timed out after 10 seconds",
            "lean_command": executable,
        }
    if version.returncode != 0:
        return {
            "status": "failed",
            "reason": f"Could not identify Lean version: {version.stderr.strip()}",
        }

    if claim.upper_exclusive is None or claim.upper_exclusive < 1:
        return {"status": "failed", "reason": "Claim is not a non-empty finite range"}

    constant = claim.constant
    upper = claim.upper_exclusive
    last_n = upper
    last_value = polynomial(constant, last_n)
    factor = first_factor(last_value)
    if factor is None:
        return {
            "status": "failed",
            "reason": "Expected a composite counterexample at the range boundary",
        }

    source = f"""set_option maxRecDepth 4096

def primeCheck (n : Nat) : Bool :=
  if n < 2 then false
  else (List.range n).all (fun d => decide (d < 2 || n % d != 0))

theorem finite_checks_pass :
    (List.range {upper}).all
      (fun n => primeCheck (n * n + n + {constant})) = true := by
  decide

theorem counterexample_factorization :
    {last_n} * {last_n} + {last_n} + {constant} =
      {factor} * ({last_value // factor}) := by
  decide

#print axioms finite_checks_pass
#print axioms counterexample_factorization
"""
    if artifact_dir is not None:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        lean_file = artifact_dir / f"{claim.claim_id}_lean_check.lean"
        lean_file.write_text(source, encoding="utf-8")
        try:
            completed = subprocess.run(
                [executable, str(lean_file)],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {"status": "failed", "reason": "Lean check timed out"}
    else:
        with tempfile.TemporaryDirectory(prefix="chapter4-lean-") as directory:
            lean_file = Path(directory) / "discovery_check.lean"
            lean_file.write_text(source, encoding="utf-8")
            try:
                completed = subprocess.run(
                    [executable, str(lean_file)],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                return {"status": "failed", "reason": "Lean check timed out"}

    output = (completed.stdout + completed.stderr).strip()
    status = "checked" if completed.returncode == 0 and "sorryAx" not in output else "failed"
    return {
        "status": status,
        "lean_version_command": executable,
        "lean_version": version.stdout.strip(),
        "claim": claim.statement(),
        "artifact_path": str(lean_file),
        "source": source,
        "log": output[-4000:],
    }


def human_review(claim: Claim, lean_result: dict[str, Any], auto: bool) -> bool:
    print("\nHUMAN REVIEW")
    print(f"Claim: {claim.statement()}")
    print(
        "Lean artifact checks a finite Boolean primality computation and a "
        "factorization; it does not prove a general primality theorem."
    )
    if lean_result["status"] != "checked":
        print(f"Lean status: {lean_result['status']}")
        return False
    if auto:
        print("Decision: approved by explicit --auto-approve policy (not a human review)")
        return True
    answer = input("Does the formal computation match the finite claim? [y/N] ")
    return answer.strip().lower() in {"y", "yes"}


def interpretation_review(
    database_path: Path,
    run_id: str | None = None,
    auto: bool = False,
) -> tuple[str, bool]:
    """Interpret and release a completed run after the formal gate.

    Formal verification establishes a precise statement. This separate gate
    records the human interpretation of its scope, limitations, and release
    policy. It never treats literature search results as a novelty verdict.
    """
    database = DiscoveryDatabase(database_path)
    try:
        if run_id is None:
            row = database.connection.execute(
                "SELECT run_id FROM run_results "
                "ORDER BY completed_at DESC LIMIT 1"
            ).fetchone()
            if row is None:
                raise RuntimeError("No completed run is available for interpretation")
            run_id = str(row["run_id"])

        snapshot = database.graph_snapshot(run_id)
        claims = [
            node for node in snapshot["nodes"] if node["kind"] == "claim"
        ]
        original = next(
            (node for node in claims if node["evidence"] == Evidence.REFUTED.name),
            None,
        )
        established = next(
            (
                node
                for node in claims
                if node["evidence"] == Evidence.FORMALLY_VERIFIED.name
            ),
            None,
        )
        if established is None:
            established = next(
                (
                    node
                    for node in claims
                    if node["evidence"] == Evidence.CERTIFIED.name
                ),
                None,
            )
        if original is None or established is None:
            raise RuntimeError(
                "Run does not contain the refuted and established claims "
                "needed for interpretation"
            )

        counterexample = next(
            (
                node
                for node in snapshot["nodes"]
                if node["kind"] == "counterexample"
            ),
            None,
        )
        literature = database.connection.execute(
            "SELECT status FROM literature_searches WHERE run_id=? "
            "ORDER BY search_id DESC LIMIT 1",
            (run_id,),
        ).fetchone()
        formally_verified = (
            established["evidence"] == Evidence.FORMALLY_VERIFIED.name
        )
        report = {
            "original_claim": original["statement"],
            "original_result": (
                counterexample["statement"]
                if counterexample is not None
                else "refuted; counterexample node unavailable"
            ),
            "established_result": established["statement"],
            "evidence": (
                "exact finite computation, Lean kernel check, "
                "and statement-match review"
                if formally_verified
                else "exact finite computation only; formal gate not completed"
            ),
            "scope_limit": "This does not prove the universal claim for all n.",
            "novelty": (
                "Not established; literature hits are candidates only "
                "and require separate human screening."
            ),
            "literature_status": (
                literature["status"] if literature is not None else "not recorded"
            ),
            "release_scope": (
                "finite refinement and documented refutation only"
                if formally_verified
                else "not releasable until the formal gate is completed"
            ),
        }
        print("\nINTERPRETATION REVIEW")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        if not formally_verified:
            approved = False
            reviewer = "policy"
            print(
                "Decision: not released because the formal verification gate "
                "was not completed"
            )
        elif auto:
            approved = True
            reviewer = "automation"
            print(
                "Decision: approved by explicit --auto-approve policy "
                "(not a human interpretation review)"
            )
        else:
            answer = input(
                "Does this interpretation and its limited release scope match "
                "your mathematical judgment? [y/N] "
            )
            approved = answer.strip().lower() in {"y", "yes"}
            reviewer = "user"

        ledger = EvidenceLedger(database, run_id)
        ledger.record(
            "human",
            "interpretation_review",
            claim_id=established["id"],
            approved=approved,
            report=report,
            reviewer=reviewer,
        )
        outcome = (
            "Interpretation approved: finite refinement released; "
            "universal claim refuted"
            if approved
            else
            "Interpretation blocked: formal verification incomplete; "
            "result unreleased"
            if not formally_verified
            else
            "Interpretation not approved: result remains formally verified "
            "but unreleased"
        )
        database.finish_run(run_id, outcome)
        if not ledger.verify():
            raise RuntimeError(
                "Evidence ledger hash-chain verification failed after interpretation"
            )
        return outcome, approved
    finally:
        database.close()


def run(
    model: str,
    host: str,
    max_n: int,
    database_path: Path,
    lean_command: str,
    auto_approve: bool,
    workers: int = 2,
    offline_literature: bool = False,
    openalex_email: str | None = None,
    proposer: Callable[[str, str, int], tuple[int, str]] = ollama_propose,
    multiprocessing_context: str | None = None,
) -> str:
    if workers < 1:
        raise ValueError("At least one worker process is required")
    run_id = uuid.uuid4().hex[:8]
    database = DiscoveryDatabase(database_path)
    configuration = {
        "run_id": run_id,
        "python_version": platform.python_version(),
        "ollama_model": model,
        "ollama_host": host,
        "generator": getattr(proposer, "__name__", type(proposer).__name__),
        "generator_prompt": (
            GENERATOR_PROMPT if proposer is ollama_propose else None
        ),
        "temperature": 0,
        "openalex": "online" if not offline_literature else "explicitly skipped",
        "openalex_email_configured": bool(openalex_email),
        "search_n_range": [0, max_n],
        "worker_processes": workers,
        "lean_command": lean_command,
        "review_policy": "auto-approve" if auto_approve else "interactive",
        "database": str(database_path),
    }
    database.start_run(run_id, configuration)
    ledger = EvidenceLedger(database, run_id)
    graph = KnowledgeGraph(database, run_id)

    try:
        outcome = _run_with_database(
            database=database,
            run_id=run_id,
            ledger=ledger,
            graph=graph,
            model=model,
            host=host,
            max_n=max_n,
            database_path=database_path,
            lean_command=lean_command,
            auto_approve=auto_approve,
            workers=workers,
            offline_literature=offline_literature,
            openalex_email=openalex_email,
            proposer=proposer,
            multiprocessing_context=multiprocessing_context,
        )
        database.finish_run(run_id, outcome)
        return outcome
    except (
        OSError,
        ValueError,
        RuntimeError,
        KeyError,
        TypeError,
        sqlite3.Error,
        subprocess.SubprocessError,
    ) as error:
        database.record_event(
            run_id,
            "orchestrator",
            "run_failed",
            {"error": f"{type(error).__name__}: {error}"},
        )
        database.finish_run(
            run_id,
            "failed",
            f"{type(error).__name__}: {error}",
        )
        raise
    finally:
        database.close()


def _run_with_database(
    *,
    database: DiscoveryDatabase,
    run_id: str,
    ledger: EvidenceLedger,
    graph: KnowledgeGraph,
    model: str,
    host: str,
    max_n: int,
    database_path: Path,
    lean_command: str,
    auto_approve: bool,
    workers: int,
    offline_literature: bool,
    openalex_email: str | None,
    proposer: Callable[[str, str, int], tuple[int, str]],
    multiprocessing_context: str | None,
) -> str:
    gateway = ToolGateway(ledger)
    gateway.register(
        "generator_proposal",
        lambda model, host, timeout, prompt, temperature: proposer(
            model, host, timeout
        ),
    )
    gateway.register("is_prime", is_prime)
    artifact_dir = database_path.parent / f"{database_path.stem}_artifacts" / run_id
    gateway.register(
        "lean_check",
        lambda claim: lean_check(
            claim, lean_command, ledger, artifact_dir=artifact_dir
        ),
    )

    def literature_lookup(query: str) -> dict[str, Any]:
        if offline_literature:
            response = {
                "provider": "OpenAlex",
                "query": query,
                "status": "skipped",
                "reason": "offline mode was explicitly requested",
                "works": [],
            }
        else:
            try:
                response = openalex_search(
                    query, timeout=20, email=openalex_email
                )
            except (RuntimeError, ValueError) as error:
                response = {
                    "provider": "OpenAlex",
                    "query": query,
                    "status": "failed",
                    "error": f"{type(error).__name__}: {error}",
                    "works": [],
                }
                database.record_literature_search(
                    run_id, query, "failed", response
                )
                raise
        database.record_literature_search(
            run_id, query, response["status"], response
        )
        return response

    gateway.register("literature_search", literature_lookup)
    ledger.record(
        "orchestrator",
        "run_started",
        configuration=database.connection.execute(
            "SELECT configuration_json FROM runs WHERE run_id=?",
            (run_id,),
        ).fetchone()["configuration_json"],
    )

    constant, rationale = gateway.call(
        "generator_proposal",
        "generator",
        model=model,
        host=host,
        timeout=120,
        prompt=GENERATOR_PROMPT,
        temperature=0,
    )
    if not isinstance(constant, int) or isinstance(constant, bool):
        raise ValueError("Generator returned a non-integer constant")
    claim = Claim(f"C1-{run_id}", constant)
    ledger.record(
        "generator",
        "proposed",
        claim=asdict(claim),
        statement=claim.statement(),
        rationale=rationale,
    )
    graph.add_claim(claim, Evidence.PROPOSED)
    print(f"PROPOSED {claim.claim_id}: {claim.statement()}")
    print(f"GENERATOR REASON: {rationale}")

    query = (
        "prime generating polynomial "
        f"n squared plus n plus {constant}"
    )
    literature = gateway.call(
        "literature_search",
        "critic",
        query=query,
    )
    for work in literature.get("works", []):
        source_hash = hashlib.sha256(work["id"].encode("utf-8")).hexdigest()[:12]
        graph.add_source(
            f"S-{run_id}-{source_hash}",
            work["title"],
            "POSSIBLE_PRIOR_WORK",
            claim.claim_id,
            work,
        )
    ledger.record(
        "critic",
        "literature_screened",
        claim_id=claim.claim_id,
        provider="OpenAlex",
        status=literature["status"],
        result_count=literature.get("result_count"),
        candidate_works=literature.get("works", []),
        interpretation=(
            "Candidate matches require human review; this search does not "
            "establish novelty."
        ),
    )
    print(
        "LITERATURE: OpenAlex "
        f"{literature['status']}, {len(literature.get('works', []))} "
        "candidate works (not a novelty verdict)"
    )

    # Critic runs in a separate local process and checks the motivating examples.
    context = multiprocessing.get_context(multiprocessing_context or "spawn")
    critic_started = time.perf_counter()
    with ProcessPoolExecutor(
        max_workers=workers,
        mp_context=context,
    ) as executor:
        critic_result = executor.submit(
            _critic_worker, constant, list(range(4))
        ).result()
        critic_duration = (time.perf_counter() - critic_started) * 1000
        database.add_worker_metric(
            run_id,
            "critic",
            critic_result["worker_pid"],
            critic_duration,
            len(critic_result["checks"]),
        )
        sample_values = critic_result["checks"]
        if not all(prime for _, _, prime in sample_values):
            ledger.record(
                "critic",
                "rejected",
                claim_id=claim.claim_id,
                checked=sample_values,
                reason="one of the first four values is composite",
            )
            raise RuntimeError(
                "Critic rejected the proposal: initial values are not all prime"
            )
        graph.set_evidence(claim.claim_id, Evidence.SUPPORTED)
        ledger.record(
            "critic",
            "supported_initial_examples",
            claim_id=claim.claim_id,
            checked=sample_values,
            worker_pid=critic_result["worker_pid"],
            note="Support for examples is not proof of the universal claim",
        )
        print(
            "CRITIC: first four values pass in worker "
            f"process {critic_result['worker_pid']}"
        )

        # Search chunks are distributed to local OS processes; the minimum
        # counterexample is selected so results are deterministic.
        total = max_n + 1
        chunk_count = min(workers, total)
        chunk_size = (total + chunk_count - 1) // chunk_count
        chunks = [
            (start, min(start + chunk_size, total))
            for start in range(0, total, chunk_size)
        ]
        search_started = time.perf_counter()
        futures = [
            executor.submit(_search_worker, constant, start, stop)
            for start, stop in chunks
        ]
        search_results = [future.result() for future in futures]
        search_duration = (time.perf_counter() - search_started) * 1000

    for result in search_results:
        database.add_worker_metric(
            run_id,
            "search",
            result["worker_pid"],
            search_duration / len(search_results),
            result["range"][1] - result["range"][0],
        )
    counterexamples = [
        result["counterexample"]
        for result in search_results
        if result["counterexample"] is not None
    ]
    counterexample = min(counterexamples, key=lambda item: item[0]) if counterexamples else None
    if counterexample is None:
        ledger.record(
            "search",
            "budget_exhausted_without_counterexample",
            claim_id=claim.claim_id,
            searched_n=[0, max_n],
            worker_processes=workers,
        )
        raise RuntimeError(
            f"No counterexample found through n={max_n}; claim remains open"
        )

    n, value, factor = counterexample
    graph.add_counterexample(claim, n, value, factor)
    graph.set_evidence(claim.claim_id, Evidence.REFUTED)
    ledger.record(
        "search",
        "refuted",
        claim_id=claim.claim_id,
        n=n,
        value=value,
        factorization=[factor, value // factor],
        worker_processes=workers,
        worker_pids=sorted({result["worker_pid"] for result in search_results}),
    )
    print(f"SEARCH: n={n}, value={value}={factor}*{value // factor}")

    refined = Claim(
        f"C2-{run_id}",
        constant,
        upper_exclusive=n,
        parent_id=claim.claim_id,
    )
    graph.add_claim(refined, Evidence.PROPOSED)
    ledger.record(
        "critic",
        "refined_after_counterexample",
        claim=asdict(refined),
        statement=refined.statement(),
    )
    print(f"REFINED {refined.claim_id}: {refined.statement()}")

    # The critic's finite-range check and verifier repeat exact arithmetic.
    refined_checks = [
        (
            checked_n,
            polynomial(constant, checked_n),
            gateway.call(
                "is_prime",
                "search",
                value=polynomial(constant, checked_n),
            ),
        )
        for checked_n in range(refined.upper_exclusive or 0)
    ]
    if not all(result for _, _, result in refined_checks):
        raise RuntimeError("Refined claim failed exact search")
    graph.set_evidence(refined.claim_id, Evidence.SURVIVED_SEARCH)
    ledger.record(
        "search",
        "refined_range_survived",
        claim_id=refined.claim_id,
        searched_n=[0, n - 1],
    )

    exact_checks = [
        (
            checked_n,
            polynomial(constant, checked_n),
            gateway.call(
                "is_prime",
                "verifier",
                value=polynomial(constant, checked_n),
            ),
        )
        for checked_n in range(refined.upper_exclusive or 0)
    ]
    if not all(result for _, _, result in exact_checks):
        raise RuntimeError("Verifier rejected a value in the refined range")
    graph.set_evidence(refined.claim_id, Evidence.CERTIFIED)
    ledger.record(
        "verifier",
        "exact_finite_range_certified",
        claim_id=refined.claim_id,
        checks=exact_checks,
        method="exact integer trial division",
    )

    lean_result = gateway.call(
        "lean_check",
        "lean_agent",
        claim=refined,
    )
    if lean_result.get("artifact_path"):
        database.add_artifact(
            run_id, "lean_source", Path(lean_result["artifact_path"])
        )
    if lean_result["status"] != "checked":
        ledger.record(
            "lean_agent",
            "formal_check_unavailable_or_failed",
            claim_id=refined.claim_id,
            result=lean_result,
        )
        print(f"LEAN: {lean_result['status']}")
        return "certified, but Lean check unavailable or failed"

    ledger.record(
        "lean_agent",
        "finite_computation_checked",
        claim_id=refined.claim_id,
        result=lean_result,
    )
    print(
        "LEAN: finite computation and factorization checked by "
        f"{lean_result['lean_version']}"
    )

    approved = human_review(refined, lean_result, auto_approve)
    ledger.record(
        "human",
        "statement_match_review",
        claim_id=refined.claim_id,
        approved=approved,
        policy="auto-approve" if auto_approve else "interactive",
        reviewer="automation" if auto_approve else "user",
    )
    if approved:
        graph.set_evidence(refined.claim_id, Evidence.FORMALLY_VERIFIED)
        proof_id = f"P-{refined.claim_id}"
        database.add_node(
            run_id,
            proof_id,
            "proof",
            "Lean kernel check of the finite claim",
            "FORMAL",
            {"lean_version": lean_result["lean_version"]},
        )
        database.add_edge(
            run_id,
            proof_id,
            "proves",
            refined.claim_id,
        )
    ledger_valid = ledger.verify()
    ledger.record(
        "orchestrator",
        "ledger_integrity_check",
        valid_before_final_entry=ledger_valid,
    )
    if not ledger_valid or not ledger.verify():
        raise RuntimeError("Evidence ledger hash-chain verification failed")

    graph_snapshot = graph.snapshot()
    print("\nPERSISTED KNOWLEDGE GRAPH")
    print(json.dumps(graph_snapshot, indent=2))
    print(f"DATABASE: {database_path}")
    print(f"RUN ID: {run_id}")
    print(f"LEDGER VALID: {ledger.verify()}")
    print(f"WORKERS: critic PID {critic_result['worker_pid']}; search PIDs "
          f"{sorted({result['worker_pid'] for result in search_results})}")
    if approved:
        print("FINAL: finite claim exact-checked and approved")
        print("LIMIT: this does not prove the original universal conjecture")
        return "finite claim exact-checked and approved"
    print("FINAL: finite checks passed, but human approval was not granted")
    return "finite checks passed, not approved"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model", default=os.environ.get("OLLAMA_MODEL", "qwen3:0.6b")
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
    )
    parser.add_argument("--max-n", type=int, default=100)
    parser.add_argument(
        "--database",
        type=Path,
        default=Path("artifacts/chapter4_discovery.sqlite3"),
    )
    parser.add_argument("--lean", default="lean")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument(
        "--offline-literature",
        action="store_true",
        help="Skip OpenAlex and record an explicit offline policy",
    )
    parser.add_argument(
        "--online-literature",
        action="store_true",
        help="Explicitly use the live OpenAlex API (the default)",
    )
    parser.add_argument(
        "--openalex-email",
        default=os.environ.get("OPENALEX_EMAIL"),
        help="Optional email sent to OpenAlex as a polite-pool identifier",
    )
    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="Use an explicit automation policy instead of interactive review",
    )
    args = parser.parse_args()
    if args.max_n < 4:
        parser.error("--max-n must be at least 4")
    if args.workers < 1:
        parser.error("--workers must be at least 1")
    if args.online_literature and args.offline_literature:
        parser.error("--online-literature and --offline-literature are mutually exclusive")
    offline_literature = args.offline_literature
    outcome = run(
        args.model,
        args.host,
        args.max_n,
        args.database,
        args.lean,
        args.auto_approve,
        args.workers,
        offline_literature,
        args.openalex_email,
    )
    print(f"TECHNICAL OUTCOME: {outcome}")
    interpretation_outcome, _ = interpretation_review(
        args.database,
        auto=args.auto_approve,
    )
    print(f"INTERPRETATION OUTCOME: {interpretation_outcome}")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as error:
        # Fail closed, but readably: the failure is already in the ledger.
        print(f"STOPPED: {error}")
        print("Rerun with --offline-literature for an explicit offline run.")
        raise SystemExit(2)
