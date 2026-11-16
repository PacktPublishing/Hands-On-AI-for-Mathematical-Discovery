# Chapter 3: Tool-Integrated Reasoning

Code for Chapter 3 of *Hands-On AI for Mathematical Discovery*. A language
model answers questions about cycles of the maps

    T(x) = (q*x + c)/2 for odd x,   T(x) = x/2 for even x,

once from its own reasoning and once with tools for exact computation. The
tools sit behind one gateway that validates every call, runs it, checks the
result, and logs it.

| Path | Contents |
|---|---|
| `mathtools/maps.py`, `census.py` | The maps, the parity-word formula for cycles, an exhaustive census |
| `mathtools/symbolic.py` | SymPy derivation of the cycle formula |
| `mathtools/numeric.py` | Continued fractions of log2(q) with mpmath, and the float comparison |
| `mathtools/validate.py`, `registry.py` | Argument checks and the tool gateway |
| `mathtools/tools.py` | The six tools a model may call |
| `mathtools/client.py`, `loop.py` | OpenAI-compatible client with tool calls; the inner loop |
| `mathtools/experiment.py`, `report.py` | 28 tasks with and without tools; the report |
| `examples/` | The demos printed in the chapter |
| `configs/models.example.json` | Model endpoints (vLLM on a cluster, Ollama on a laptop) |
| `slurm/tools_vllm.sbatch` | Serves a model with tool calling and runs the experiment |
| `runs/` | Recorded runs: every conversation, tool call, and verdict |

The listings in the chapter are taken verbatim from these files.

## Requirements

Python 3.10 or later with `sympy` and `mpmath` (`pip install -r requirements.txt`).
New runs need a model endpoint with tool calling; the tests and demos need none.

## Tests and demos

```bash
python -m unittest discover -s tests
python examples/cycles_demo.py
python examples/symbolic_demo.py
python examples/precision_demo.py
python examples/schema_demo.py
python examples/registry_demo.py
```

The end-to-end test runs the whole experiment against a local stand-in for a
model server that first sends an invalid tool call and then repairs it.

## Running the experiment

On a laptop with Ollama:

```bash
ollama pull qwen3:4b
OLLAMA_CONTEXT_LENGTH=32768 ollama serve &
python -m mathtools.experiment --config configs/models.example.json \
    --models qwen3-4b-ollama --samples 3 --workers 1 --out runs/qwen3-4b-ollama
python -m mathtools.report runs/qwen3-4b-ollama
```

On a SLURM cluster with vLLM (activate the environment that contains vLLM
first; the job inherits it):

```bash
MODEL=openai/gpt-oss-120b NAME=gpt-oss-120b-vllm \
    TOOL_ARGS="--tool-call-parser openai" sbatch slurm/tools_vllm.sbatch
MODEL=Qwen/Qwen3-32B NAME=qwen3-32b-vllm \
    TOOL_ARGS="--tool-call-parser hermes --reasoning-parser qwen3" \
    sbatch slurm/tools_vllm.sbatch
```

Runs are resumable: start the same command again and only missing
conversations are run. To read one conversation:

```bash
python examples/show_transcript.py runs/<run> <model> <task-id>
```

## A note on time limits

The gateway stops slow tools with `SIGALRM`, which exists only on Unix and
works only in the main thread. The experiment runs conversations in threads,
so there every tool must be fast at the limits of its arguments. The test
`test_worst_cases_are_fast` checks exactly that. If you add a tool whose cost
you cannot bound, run it in a separate process.
