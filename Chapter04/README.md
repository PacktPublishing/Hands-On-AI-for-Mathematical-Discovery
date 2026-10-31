# Chapter 4 reference release

This folder is a curated, commit-ready companion to Chapter 4 of
*Agentic Mathematical Discovery*. It contains only the runnable reference
code, the teaching examples promised by the chapter, their tests, and the
small amount of documentation needed to run them.

The chapter text remains the source of truth for the architecture and its
terminology. The code below implements the local reference profile described
there: a single-writer SQLite graph and evidence ledger, local worker
processes, an OpenAlex literature connector, a Lean subprocess, and explicit
human review gates. Production components such as Neo4j, Qdrant/pgvector,
MCP servers, and SLURM are described in the chapter but are intentionally not
pretended to be implemented here.

## Book-facing reference entry points

Run these commands from this directory:

```bash
python3 run_euler.py
python3 -m discovery_lab.worker --task lean-check
```

`run_euler.py` executes the worked Euler case through the complete local flow:
candidate proposal, critic, bounded search, refinement, exact verification,
OpenAlex lookup, Lean checking, statement review, interpretation/release
review, and final audit. Literature search is online by default. Use
`--offline-literature` only when an explicit offline run is intended.

The default `run_euler.py` flow asks for review. For an explicitly automated
smoke run, use `--auto-approve`; the automation policy is recorded in the
ledger and is not presented as human approval.

## Example profiles

The `examples/` directory contains three complementary levels:

| File | Profile | Purpose |
|---|---|---|
| `discovery_loop.py` | simplified | Short deterministic flow using `n²+n+5`; matches the quick teaching example and its exact output. |
| `end_to_end_discovery.py` | integrated | Full local architecture with Ollama or a deterministic fallback, workers, SQLite graph, ledger, OpenAlex, Lean, and review gates. |
| `interactive_agentic_discovery.ipynb` | realistic | Starts from observations rather than a supplied formula, reconstructs `n²+n+41`, runs the integrated flow, and performs interpretation/release review. |
| `ollama_discovery.py` | focused | Isolates the model-suggestion boundary; Python remains the source of exact checks. |
| `counterexample_check.lean` | direct proof artifact | Small standalone Lean check for the finite counterexample case. |

The realistic notebook is an intentional companion variation, not a verbatim
listing from the chapter: it makes the discovery process visible while using
the same engine and evidence gates as the reference runner.

The two polynomial constants are intentional. The short deterministic example
uses `n²+n+5`, whose counterexample appears already at `n=4`, so the complete
flow is quick to inspect. The book-facing Euler runner and the realistic
notebook use Euler's classical `n²+n+41`, whose counterexample appears at
`n=40`. The mathematical flow and evidence gates are the same in both cases.

## Running the supplementary examples

From this directory:

```bash
python3 examples/discovery_loop.py
python3 -m unittest discover -s examples -p 'test_*.py' -v
python3 examples/end_to_end_discovery.py --model qwen3:0.6b
```

The end-to-end script needs Lean 4 and, when the model-backed path is used, a
running local Ollama instance with the selected model. The OpenAlex request
needs network access and a valid local Python CA configuration. Set
`OPENALEX_EMAIL` or pass `--openalex-email` when desired. The notebook can be
opened in Jupyter or VS Code; its setup cell uses online OpenAlex search by
default and supports `LIVE_LITERATURE = False` as an explicit offline opt-out.

## Requirements and scope

- Python 3.10 or newer; the reference code uses the standard library.
- Lean 4.33.0, pinned by `lean-toolchain`, for the formal gate.
- Jupyter/IPython only for the notebook.
- Ollama is optional and is not required for the deterministic Euler runner.
- OpenAlex is the one external research service called by this local profile.

The implementation does not claim to provide the chapter's production
deployment: there is no separate knowledge-graph agent, document ingestion or
retrieval service, remote/distributed worker cluster, SLURM job array, Neo4j,
vector database, MCP server, or production observability layer. The local
SQLite graph and worker pool are deliberately small analogues that make the
control flow executable and auditable.

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the component-to-code mapping
and [`examples/README.md`](examples/README.md) for the book-section mapping.

