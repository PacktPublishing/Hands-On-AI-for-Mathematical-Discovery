# Chapter 4 examples

These examples share the implementation in `end_to_end_discovery.py` but have
different teaching goals. The chapter text is authoritative for the logical
architecture; this file records deliberate differences in scale and
presentation.

## Example matrix

| Example | Fidelity | Input | Literature | Main lesson |
|---|---|---|---|---|
| `discovery_loop.py` | simplified | Seeded `n²+n+5` claim | Not used | The smallest complete propose–search–refine–verify loop |
| `end_to_end_discovery.py` | integrated | Model proposal or deterministic fallback | OpenAlex online by default | The complete local architecture and evidence flow |
| `interactive_agentic_discovery.ipynb` | realistic | Observations only | OpenAlex online by default | Discovery from observations, interpretation, release, and audit |
| `ollama_discovery.py` | focused | Ollama suggestion | Not used | A model proposes; exact Python checks |
| `counterexample_check.lean` | direct artifact | Fixed finite statement | Not used | A small Lean kernel check |

The two polynomial constants are intentional rather than inconsistent. The
short `discovery_loop.py` example uses `n²+n+5`, because its counterexample is
found immediately at `n=4`. The realistic notebook and the book-facing Euler
runner use Euler's classical `n²+n+41`, whose counterexample appears at
`n=40`. Both examples exercise the same orchestration, evidence gates, Lean
check, and review flow.

## Complete flow

The integrated examples run the same gates in sequence:

1. propose a claim;
2. record it in the SQLite graph and hash-chained ledger;
3. run critic and bounded-search workers;
4. record a counterexample and refine the claim;
5. verify the surviving finite range exactly;
6. query OpenAlex for candidate literature;
7. run the Lean check and inspect `#print axioms`;
8. perform statement-match review;
9. interpret the result and decide the limited release scope;
10. verify the ledger and report the final status.

OpenAlex results are candidates, not a novelty proof. An empty result does
not establish novelty, and literature hits require human screening against the
exact statement and quantified domain. The interpretation report therefore
uses wording such as “not assessed conclusively” rather than claiming that a
search established novelty.

## Commands

From the `Chapter04` directory:

```bash
python3 examples/discovery_loop.py
python3 -m unittest discover -s examples -p 'test_*.py' -v
python3 examples/end_to_end_discovery.py --model qwen3:0.6b
```

The Euler case and the Lean worker can also be run through the integrated engine:

```bash
python3 examples/run_euler_integrated.py --auto-approve
python3 examples/integrated_worker.py --task lean-check
```

To run the notebook, open `interactive_agentic_discovery.ipynb` in Jupyter or
VS Code. The setup cell uses `LIVE_LITERATURE = True`. Set it to `False` only
for a deliberately offline run. The notebooks create run-specific databases
under `artifacts/`, which are ignored by Git.

