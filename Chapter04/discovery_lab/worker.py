"""SLURM worker for the Lean gate: checks one shard of a finite claim.

Each array task reads SLURM_ARRAY_TASK_ID, formalizes its sub-range of
the claim, and writes a result file. Finished shards are skipped, so an
interrupted array can simply be resubmitted.

    python -m discovery_lab.worker --task lean-check
"""
import argparse
import json
import os
from pathlib import Path

from .agents import Claim, LeanAgent
from .cli import default_lean
from .ledger import Ledger
from .tools import lean_check


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", choices=("lean-check",), required=True)
    parser.add_argument("--coeffs", default="1,1,41")
    parser.add_argument("--upper", type=int, default=40)
    parser.add_argument("--shard-size", type=int, default=10)
    parser.add_argument("--out", default="artifacts/shards")
    parser.add_argument("--lean", default=default_lean())
    args = parser.parse_args()

    shard = int(os.environ.get("SLURM_ARRAY_TASK_ID", "0"))
    lo = shard * args.shard_size
    hi = min(lo + args.shard_size, args.upper)
    if lo >= hi:
        print(f"shard {shard}: empty range, nothing to do")
        return 0

    out = Path(args.out) / f"shard-{shard:05d}.json"
    if out.exists():
        print(f"shard {shard}: already done ({out})")
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)

    coeffs = tuple(int(c) for c in args.coeffs.split(","))
    claim = Claim(coeffs=coeffs, lo=lo, hi=hi, id=f"S{shard}")
    result = lean_check(LeanAgent().formalize(claim), args.lean)

    ledger = Ledger(str(out.with_suffix(".jsonl")))
    ledger.record("worker", "lean-check", claim.id,
                  statement=claim.text(), status=result["status"])
    record = {"shard": shard, "lo": lo, "hi": hi,
              "statement": claim.text(), "status": result["status"]}
    out.write_text(json.dumps(record, indent=2))
    print(json.dumps(record))
    return 0 if result["status"] == "checked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
