"""Accuracy with and without tools, and how the loop behaved."""

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path


def bootstrap(values, reps=2000, seed=0):
    """95% interval for a mean, resampling tasks, not samples."""
    rng, n = random.Random(seed), len(values)
    means = sorted(
        sum(rng.choices(values, k=n)) / n for _ in range(reps)
    )
    return means[int(0.025 * reps)], means[int(0.975 * reps) - 1]


def load(path):
    latest = {}
    with open(path) as f:
        for line in f:
            r = json.loads(line)
            key = (r["model"], r["task"], r["mode"], r["sample"])
            if key not in latest or "error" not in r:
                latest[key] = r
    return list(latest.values())


def tool_stats(records):
    """How often the model called tools, and what went wrong."""
    n = max(1, len(records))
    calls = [e for r in records for e in r.get("tool_log", [])]
    rejected = [e for e in calls if not e["ok"]]
    hit = [
        r
        for r in records
        if any(not e["ok"] for e in r.get("tool_log", []))
    ]
    by_tool = defaultdict(int)
    for e in calls:
        by_tool[e["tool"]] += 1
    rounds = [r.get("rounds", []) for r in records]
    return {
        "calls": len(calls),
        "calls_per_task": round(len(calls) / n, 2),
        "rounds_per_task": round(sum(map(len, rounds)) / n, 2),
        "rejected": len(rejected),
        "conversations_with_rejection": len(hit),
        "of_which_correct": sum(
            r["verdict"] == "pass" for r in hit
        ),
        "no_tool_used": sum(
            not r.get("tool_log") for r in records
        ),
        "budget_exhausted": sum(
            r["verdict"] == "budget-exhausted" for r in records
        ),
        "truncated": sum(
            any(x["finish"] == "length" for x in rs)
            for rs in rounds
        ),
        "by_tool": dict(sorted(by_tool.items())),
        "rejections": [e["error"] for e in rejected][:10],
    }


def summarize(records):
    groups = defaultdict(lambda: defaultdict(list))
    for r in records:
        if "error" in r:
            continue
        groups[(r["model"], r["mode"])][r["task"]].append(
            r["verdict"] == "pass"
        )
    rows = {}
    for (model, mode), per_task in sorted(groups.items()):
        acc = {t: sum(v) / len(v) for t, v in per_task.items()}
        kinds = defaultdict(list)
        for t, a in acc.items():
            kinds[t.split("-")[0]].append(a)
        recs = [
            r
            for r in records
            if r["model"] == model
            and r["mode"] == mode
            and "error" not in r
        ]
        tokens = [
            sum(
                x["usage"].get("completion_tokens", 0)
                for x in r["rounds"]
            )
            for r in recs
        ]
        rows[(model, mode)] = {
            "acc": sum(acc.values()) / len(acc),
            "tokens": sum(tokens) / len(tokens),
            "seconds": sum(
                sum(x["seconds"] for x in r["rounds"])
                for r in recs
            )
            / len(recs),
            "ci": bootstrap(list(acc.values())),
            "by_kind": {
                k: sum(v) / len(v)
                for k, v in sorted(kinds.items())
            },
            "per_task": acc,
        }
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run")
    args = ap.parse_args(argv)
    records = load(Path(args.run) / "results.jsonl")
    rows = summarize(records)
    lines = [
        f"# Report for {args.run}",
        "",
        "| model | mode | accuracy % [95% CI] | orbit | word | "
        "census | tokens | seconds |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for (model, mode), s in rows.items():
        lo, hi = s["ci"]
        k = s["by_kind"]
        lines.append(
            f"| {model} | {mode} | {100 * s['acc']:.1f} "
            f"[{100 * lo:.1f}, {100 * hi:.1f}] | "
            f"{100 * k.get('orbit', 0):.0f} | "
            f"{100 * k.get('word', 0):.0f} | "
            f"{100 * k.get('census', 0):.0f} | "
            f"{s['tokens']:.0f} | {s['seconds']:.1f} |"
        )
    for model in sorted({m for m, _ in rows}):
        recs = [
            r
            for r in records
            if r["model"] == model
            and r["mode"] == "tools"
            and "error" not in r
        ]
        if recs:
            lines += [
                "",
                f"## Tool use: {model}",
                "",
                json.dumps(tool_stats(recs), indent=2),
            ]
        if (model, "plain") in rows and (model, "tools") in rows:
            a, b = rows[(model, "tools")], rows[(model, "plain")]
            common = sorted(
                set(a["per_task"]) & set(b["per_task"])
            )
            diffs = [
                a["per_task"][t] - b["per_task"][t]
                for t in common
            ]
            lo, hi = bootstrap(diffs)
            lines.append(
                f"\ntools - plain: "
                f"{100 * sum(diffs) / len(diffs):+.1f} points, "
                f"95% CI [{100 * lo:+.1f}, {100 * hi:+.1f}]"
            )
    errors = sum("error" in r for r in records)
    lines.append(f"\nmodel errors: {errors}")
    report = "\n".join(lines) + "\n"
    (Path(args.run) / "report.md").write_text(report)
    print(report)


if __name__ == "__main__":
    main()
