"""Table 3.2: accuracy without tools at two budgets, and with tools."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mathtools.report import bootstrap, load, summarize

MODELS = ("qwen3-4b-vllm", "qwen3-32b-vllm", "gpt-oss-120b-vllm")


def row(path, mode):
    records = [r for r in load(path) if r["mode"] == mode]
    cut = sum(
        any(x["finish"] == "length" for x in r["rounds"])
        for r in records
    )
    (summary,) = summarize(records).values()
    return summary, cut, len(records)


def pct(s):
    lo, hi = s["ci"]
    return (
        f"{100 * s['acc']:.1f} [{100 * lo:.1f}, {100 * hi:.1f}]"
    )


for m in MODELS:
    run = ROOT / "runs" / f"2026-11-16-{m}" / "results.jsonl"
    run32 = (
        ROOT
        / "runs"
        / f"2026-11-16-{m}-plain32k"
        / "results.jsonl"
    )
    p8, cut8, n = row(run, "plain")
    p32, cut32, _ = row(run32, "plain")
    tools, cut_t, _ = row(run, "tools")
    diffs = [
        tools["per_task"][t] - p32["per_task"][t]
        for t in tools["per_task"]
    ]
    lo, hi = bootstrap(diffs)
    print(
        f"{m}\n  without tools, 8,192 tokens:  {pct(p8)}, "
        f"{cut8} of {n} cut off"
    )
    print(
        f"  without tools, 32,768 tokens: {pct(p32)}, "
        f"{cut32} cut off, {p32['tokens']:.0f} tokens, "
        f"{p32['seconds']:.0f} s"
    )
    print(
        f"  with tools:                   {pct(tools)}, "
        f"{cut_t} cut off, {tools['tokens']:.0f} tokens, "
        f"{tools['seconds']:.0f} s"
    )
    print(
        f"  tools - 32k: {100 * sum(diffs) / len(diffs):+.1f} "
        f"[{100 * lo:+.1f}, {100 * hi:+.1f}] points"
    )
