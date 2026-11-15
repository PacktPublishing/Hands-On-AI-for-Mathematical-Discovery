# Chapter 2 -- LLM Mathematical Reasoning and Its Failure Modes

Companion code for Chapter 2 of *Hands-On AI for Mathematical Discovery*.

| Path | What it is |
|---|---|
| `harness/` | The reasoning and evaluation harness printed in the chapter. |
| `harness/models.py` | One client interface for vLLM, Ollama, hosted APIs, and replay. |
| `harness/prompts.py` | The single, versioned prompt and answer formats. |
| `harness/parse.py` | JSON extraction and a whitelist parser (never `eval`). |
| `harness/checks.py` | Deterministic checks, one per task kind, plus step-chain checks. |
| `harness/properties.py` | Computable properties for counterexamples and witnesses. |
| `harness/consistency.py` | Self-consistency voting over equivalence classes. |
| `harness/families.py` | Parameterized task families, including distractor pairs. |
| `harness/run.py` | Runs model x task x sample, records everything, grades. |
| `harness/report.py` | Accuracy with bootstrap intervals, failure modes, model gaps. |
| `tasks/core.jsonl` | 62 hand-written tasks, each probing one failure mode. |
| `configs/models.example.json` | Example endpoints: Ollama, vLLM, OpenAI, Anthropic, Gemini. |
| `slurm/bench_vllm.sbatch` | Serve a model with vLLM on a GPU node and benchmark it. |
| `runs/` | Recorded runs from the chapter. Re-grade them offline with `--replay`. |
| `tests/` | Tests; they use a local fake endpoint and need no model. |

## Quick start

```bash
pip install -r requirements.txt
python3 -m unittest discover -s tests -v
cp configs/models.example.json configs/models.json   # then edit
```

Re-grade a recorded run without any model or network access:

```bash
python3 -m harness.run --replay runs/<run>/results.jsonl \
    --out runs/regraded
python3 -m harness.report runs/regraded
```

## Running against models

Laptop, with Ollama:

```bash
ollama pull qwen3:4b
OLLAMA_CONTEXT_LENGTH=32768 ollama serve &
python3 -m harness.run --models qwen3-4b-ollama --samples 5 --workers 1 \
    --out runs/qwen3-4b
python3 -m harness.report runs/qwen3-4b
```

Cluster, with vLLM (adjust partition and resources in the script first):

```bash
MODEL=openai/gpt-oss-120b NAME=gpt-oss-120b-vllm \
    sbatch slurm/bench_vllm.sbatch
```

Hosted APIs (set the model fields in `configs/models.json` to dated snapshots):

```bash
export OPENAI_API_KEY=... ANTHROPIC_API_KEY=... GEMINI_API_KEY=...
python3 -m harness.run --models openai-api anthropic-api gemini-api \
    --samples 5 --workers 4 --out runs/apis
python3 -m harness.report runs/apis --resolve
```

Runs are resumable: start the same command again and finished calls are skipped.
Every run directory contains `manifest.json` (prompt and task hashes, sampling
parameters, what each endpoint reported serving), `results.jsonl` (raw responses,
parsed answers, verdicts), `report.md`, and `table.tex`.

## Requirements

Python 3.10 or newer with SymPy. Model access is needed only to create new runs.
Tested with Python 3.13 and SymPy 1.14.
