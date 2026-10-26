# Chapter 4 -- Agentic Mathematical Discovery

Reference implementation of the discovery architecture from Chapter 4:
evidence ledger, knowledge graph, tool gateway, six roles, and an
orchestrator with four evidence gates.

    pip install -r requirements.txt
    python run_euler.py            # uses `lean` from PATH if available
    python run_euler.py /path/to/lean

Tested with Python 3.12, SymPy 1.14, NetworkX 3.6, and Lean 4.19.0
(core library only, no Mathlib). Without Lean, the run stops at
"certified, formal proof unavailable".
