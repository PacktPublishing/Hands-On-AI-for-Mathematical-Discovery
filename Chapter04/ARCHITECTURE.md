# Chapter 4 architecture map

The reference release keeps the logical flow visible while using local,
reproducible components. The mathematical decision path is:

```text
observations / prompt
        ↓
generator proposal → orchestrator → critic and bounded search workers
                                      ↓ counterexample
                              refiner → exact verifier
                                      ↓
                         literature candidate lookup (OpenAlex)
                                      ↓
                              Lean formal gate
                                      ↓
                       statement-match human review
                                      ↓
                     interpretation and release review
                                      ↓
                         persisted audit and final status
```

## Component mapping

| Architectural component | Local implementation | Evidence or state |
|---|---|---|
| Generator | `generator_proposal` gateway; Ollama or deterministic proposer | Proposed claim and rationale |
| Orchestrator | `run()` and `_run_with_database()` in `examples/end_to_end_discovery.py` | Run configuration and final status |
| Critic | `_critic_worker()` | Initial finite checks and worker metrics |
| Bounded search | `_search_worker()` through `ProcessPoolExecutor` | Counterexample evidence |
| Refiner | Orchestrator refinement step | Refined finite claim and graph edge |
| Exact verifier | Python trial division and finite-range check | `CERTIFIED` evidence |
| Knowledge graph | `KnowledgeGraph` backed by SQLite | Claims, proof nodes, and relations |
| Evidence ledger | `EvidenceLedger` with a SHA-256 hash chain | Tamper-evident event history |
| Literature lookup | `openalex_search()` | Candidate sources and query status |
| Formal verifier | `lean_check()` and `discovery_lab.worker` | Lean source, log, hash, and axioms output |
| Statement-match gate | `human_review()` | Interactive or explicitly automated approval |
| Interpretation/release gate | `interpretation_review()` | Scope, limitations, novelty caveat, release decision |
| Artifact store | Run-scoped files below `artifacts/` | Lean source and logs; ignored by Git |

## Deliberate boundary

The book's full deployment architecture also discusses MCP tool servers,
Neo4j, Qdrant/pgvector, SLURM, remote agents, and production observability.
Those are architectural targets and deployment extensions, not hidden claims
of this local reference. In particular, the local orchestrator writes the
SQLite graph directly; it does not implement a separate knowledge-graph agent
with document ingestion, normalization, equivalence checking, or retrieval
neighborhoods.

