"""Small reference worker for the bounded Lean gate in Chapter 4."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import tempfile

from . import (
    Claim,
    DiscoveryDatabase,
    EvidenceLedger,
    first_factor,
    is_prime,
    lean_check,
)


def default_lean_command() -> str:
    configured = shutil.which("lean")
    toolchains = sorted(
        (Path.home() / ".elan" / "toolchains").glob(
            "leanprover--lean4---*/bin/lean"
        )
    )
    return str(toolchains[-1]) if toolchains else (configured or "lean")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--task",
        choices=("lean-check", "prime", "factor"),
        required=True,
    )
    parser.add_argument("--value", type=int)
    parser.add_argument("--constant", type=int, default=41)
    parser.add_argument("--upper-exclusive", type=int, default=40)
    parser.add_argument("--lean", default=default_lean_command())
    args = parser.parse_args()

    if args.task == "prime":
        if args.value is None:
            parser.error("--value is required for --task prime")
        print(json.dumps({"value": args.value, "is_prime": is_prime(args.value)}))
        return 0

    if args.task == "factor":
        if args.value is None:
            parser.error("--value is required for --task factor")
        print(json.dumps({"value": args.value, "factor": first_factor(args.value)}))
        return 0

    claim = Claim(
        "worker-claim",
        args.constant,
        upper_exclusive=args.upper_exclusive,
    )
    with tempfile.TemporaryDirectory(prefix="chapter4-worker-") as directory:
        database = DiscoveryDatabase(Path(directory) / "worker.sqlite3")
        database.start_run("worker-run", {"task": "lean-check"})
        ledger = EvidenceLedger(database, "worker-run")
        result = lean_check(
            claim,
            args.lean,
            ledger,
            artifact_dir=Path(directory) / "artifacts",
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
        database.close()
    return 0 if result["status"] == "checked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
