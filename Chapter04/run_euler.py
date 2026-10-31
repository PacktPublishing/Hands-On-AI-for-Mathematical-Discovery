"""Run the Chapter 4 Euler discovery case from the reference directory."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from discovery_lab import interpretation_review, run


def euler_generator(_model: str, _host: str, _timeout: int) -> tuple[int, str]:
    """Return the deterministic candidate used by the chapter's worked case."""
    return (
        41,
        "The worked case starts from Euler's observed prime-generating pattern; "
        "all mathematical checks remain independent of this proposal.",
    )


def default_lean_command() -> str:
    configured = os.environ.get("LEAN_COMMAND")
    if configured:
        return configured
    toolchains = sorted(
        (Path.home() / ".elan" / "toolchains").glob(
            "leanprover--lean4---*/bin/lean"
        )
    )
    return str(toolchains[-1]) if toolchains else "lean"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        type=Path,
        default=Path("artifacts/euler_discovery.sqlite3"),
    )
    parser.add_argument("--lean", default=default_lean_command())
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument(
        "--online-literature",
        action="store_true",
        help="Explicitly use the live OpenAlex API (the default).",
    )
    parser.add_argument(
        "--offline-literature",
        action="store_true",
        help="Skip OpenAlex and record an explicit offline policy.",
    )
    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="Record an explicit automation policy instead of prompting.",
    )
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("--workers must be at least 1")
    if args.online_literature and args.offline_literature:
        parser.error("--online-literature and --offline-literature are mutually exclusive")

    outcome = run(
        model="deterministic-euler-generator",
        host="local://deterministic-euler-generator",
        max_n=100,
        database_path=args.database,
        lean_command=args.lean,
        auto_approve=args.auto_approve,
        workers=args.workers,
        offline_literature=args.offline_literature,
        proposer=euler_generator,
        multiprocessing_context=(
            "fork" if os.name == "posix" else "spawn"
        ),
    )
    print(f"TECHNICAL OUTCOME: {outcome}")
    interpretation_outcome, _ = interpretation_review(
        args.database,
        auto=args.auto_approve,
    )
    print(f"INTERPRETATION OUTCOME: {interpretation_outcome}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
