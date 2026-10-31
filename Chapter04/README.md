# Chapter 4 -- Agentic Mathematical Discovery

Companion code for Chapter 4 of *Hands-On AI for Mathematical Discovery*.

| Path | What it is |
|---|---|
| `discovery_lab/` | **Reference package.** The code printed in the chapter: evidence ledger, knowledge graph, tool gateway, the six roles, and the orchestrator with four evidence gates. |
| `run_euler.py` | The end-to-end run from the chapter (Euler's polynomial n^2 + n + 41). |
| `discovery_lab/worker.py` | The SLURM array worker used in the chapter's job script. |
| `tests/` | Tests for the reference package. |
| `examples/` | **Extended variants** (integrated SQLite engine, Ollama, notebook). See `examples/README.md`. |

## Quick start

From this directory:

```bash
pip install -r requirements.txt
python3 run_euler.py                      # uses Lean from PATH or elan
python3 run_euler.py --interactive        # human review instead of auto-approve
python3 -m unittest discover -s tests -v
```

Expected end of the output of `run_euler.py`:

```text
Final: for all n with 0 <= n < 40: 1n^2 + 1n + 41 is prime
Status: formally verified and approved
```

Without Lean, the run stops honestly at
`certified, formal proof unavailable`.

## Roles and where they live

| Role in the chapter | Code |
|---|---|
| Evidence levels, ledger | `discovery_lab/ledger.py` (`Evidence`, `Ledger`) |
| Knowledge graph | `discovery_lab/kg.py` (`MathKG`) |
| Tool gateway, Lean checker | `discovery_lab/tools.py` (`ToolGateway`, `lean_check`) |
| Generator, search, critic, verifier, Lean agent, human gate | `discovery_lab/agents.py` |
| Orchestrator with evidence gates | `discovery_lab/orchestrator.py` |

## Lean worker on a SLURM cluster

The chapter's job array runs one shard per task. Each task reads
`SLURM_ARRAY_TASK_ID`, proves its sub-range in Lean, and writes
`artifacts/shards/shard-NNNNN.json`. Finished shards are skipped, so an
interrupted array can be resubmitted. Locally:

```bash
SLURM_ARRAY_TASK_ID=0 python3 -m discovery_lab.worker --task lean-check
```

## Requirements

- Python 3.10 or newer with SymPy and NetworkX (`requirements.txt`).
- Lean 4.33.0 (pinned in `lean-toolchain`), core library only; Mathlib is
  not needed for this chapter.
- No language model or network access is needed for the reference package.

Tested with Python 3.12, SymPy 1.14, NetworkX 3.6, and Lean 4.33.0.
