"""Aggregate a run: accuracy with error bars, failure modes,
and model gaps."""

import argparse, json, random, urllib.error, urllib.request
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from .checks import normalize_id
from .consistency import vote
from .run import load_tasks


def bootstrap(values, reps=2000, seed=0):
    """95% interval for a mean, resampling tasks, not samples."""
    rng, n = random.Random(seed), len(values)
    means = sorted(
        sum(rng.choices(values, k=n)) / n for _ in range(reps)
    )
    return means[int(0.025 * reps)], means[int(0.975 * reps) - 1]


def load(run_dir):
    latest = {}
    with open(Path(run_dir) / "results.jsonl") as f:
        for line in f:
            r = json.loads(line)
            key = (r["model"], r["task"], r["sample"])
            if key not in latest or "error" not in r:
                latest[key] = r
    by_model = defaultdict(lambda: defaultdict(list))
    for (model, task, sample), r in sorted(latest.items()):
        by_model[model][task].append(r)
    return by_model


def passed(r):
    return r["verdict"]["status"] == "pass"


def summarize(tasks, per_task):
    by_id = {t["id"]: t for t in tasks}
    acc = {
        t: sum(map(passed, rs)) / len(rs)
        for t, rs in per_task.items()
    }
    s = {"tasks": len(acc), "acc": sum(acc.values()) / len(acc)}
    s["ci"] = bootstrap(list(acc.values()))
    sc, agree = {}, {}
    for t, rs in per_task.items():
        if len(rs) >= 3:
            winner, agreement = vote(
                by_id[t], [r.get("parsed") for r in rs]
            )
            sc[t] = winner is not None and passed(rs[winner])
            agree[t] = agreement
    if sc:
        s["sc_acc"] = sum(sc.values()) / len(sc)
        s["agreement"] = sum(agree.values()) / len(agree)
        high = [sc[t] for t in sc if agree[t] >= 0.8]
        low = [sc[t] for t in sc if agree[t] < 0.8]
        s["acc_high_agreement"] = (
            (sum(high) / len(high), len(high)) if high else None
        )
        s["acc_low_agreement"] = (
            (sum(low) / len(low), len(low)) if low else None
        )
    samples = [r for rs in per_task.values() for r in rs]
    s["samples"] = len(samples)
    s["unparseable"] = sum(
        r["verdict"]["status"] == "unparseable" for r in samples
    ) / len(samples)
    s["truncated"] = sum(
        r.get("finish") in ("length", "max_tokens")
        for r in samples
    ) / len(samples)
    s["errors"] = sum(
        r["verdict"]["status"] == "error" for r in samples
    )
    s["reasons"] = Counter(
        r["verdict"]["reason"]
        for r in samples
        if r["verdict"]["status"] == "fail"
    ).most_common()
    kinds = defaultdict(list)
    for t, a in acc.items():
        kinds[by_id[t]["kind"]].append(a)
    s["by_kind"] = {
        k: sum(v) / len(v) for k, v in sorted(kinds.items())
    }
    chain = [
        r for r in samples if passed(r) and "chain_break" in r
    ]
    breaks = Counter(
        r["chain_break"][1] for r in chain if r["chain_break"]
    )
    s["right_answer_chain"] = {
        "checked": len(chain),
        "invalid-step": breaks["not-equal"],
        "steps-not-expressions": breaks["unreadable"],
    }
    pairs = defaultdict(dict)
    for t, a in acc.items():
        if "pair" in by_id[t]:
            pairs[by_id[t]["pair"]][by_id[t]["family"]] = a
    gaps = [
        p["balls-plain"] - p["balls-distractor"]
        for p in pairs.values()
        if len(p) == 2
    ]
    if gaps:
        s["distractor_gap"] = (
            sum(gaps) / len(gaps),
            bootstrap(gaps),
        )
    tokens = [
        (r.get("usage") or {}).get("completion_tokens")
        or (r.get("usage") or {}).get("output_tokens")
        or 0
        for r in samples
    ]
    s["mean_output_tokens"] = sum(tokens) / len(tokens)
    s["per_task"] = acc
    return s


def resolve(identifier, timeout=20):
    """Does a cited identifier exist? Asks doi.org or arXiv."""
    s = normalize_id(identifier)
    if s.startswith("doi:"):
        url = "https://doi.org/api/handles/" + s[4:]
    elif s.startswith("arxiv:"):
        url = "https://arxiv.org/abs/" + s[6:]
    else:
        return "not-an-identifier"
    try:
        with urllib.request.urlopen(url, timeout=timeout):
            return "exists"
    except urllib.error.HTTPError as e:
        return "not-found" if e.code == 404 else "unavailable"
    except Exception:
        return "unavailable"


def fmt_ci(s):
    lo, hi = s["ci"]
    return (
        f"{100 * s['acc']:.1f} [{100 * lo:.1f}, {100 * hi:.1f}]"
    )


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run")
    ap.add_argument("--tasks", default="tasks/core.jsonl")
    ap.add_argument(
        "--resolve",
        action="store_true",
        help="check wrong references against doi.org and arXiv",
    )
    args = ap.parse_args(argv)
    manifest = json.loads(
        (Path(args.run) / "manifest.json").read_text()
    )
    tasks = load_tasks(
        args.tasks, manifest["family_seed"], manifest["families"]
    )
    by_model = load(args.run)
    stats = {
        m: summarize(tasks, pt) for m, pt in by_model.items()
    }

    lines = [
        f"# Report for {args.run}",
        "",
        f"prompt {manifest['prompt']} ({manifest['prompt_sha']}), "
        f"tasks {manifest['tasks_sha']}, samples {manifest['samples']}",
        "",
        "| model | acc@1 % [95% CI] | maj@k % | agreement | "
        "unparseable % | truncated % |",
        "|---|---|---|---|---|---|",
    ]
    for m, s in stats.items():
        lines.append(
            f"| {m} | {fmt_ci(s)} | "
            f"{100 * s.get('sc_acc', float('nan')):.1f} | "
            f"{s.get('agreement', float('nan')):.2f} | "
            f"{100 * s['unparseable']:.1f} | "
            f"{100 * s['truncated']:.1f} |"
        )
    for m, s in stats.items():
        lines += [
            "",
            f"## {m}",
            "",
            f"- tasks {s['tasks']}, samples {s['samples']}, "
            f"model errors {s['errors']}",
            f"- by kind: "
            + ", ".join(
                f"{k} {100 * v:.0f}%"
                for k, v in s["by_kind"].items()
            ),
            f"- failure reasons: "
            + ", ".join(f"{k} {n}" for k, n in s["reasons"]),
            f"- majority accuracy at agreement >= 0.8: "
            f"{s.get('acc_high_agreement')}, below: "
            f"{s.get('acc_low_agreement')}",
            f"- step chains behind right answers: "
            f"{s['right_answer_chain']}",
            f"- distractor gap (plain - distractor): "
            f"{s.get('distractor_gap')}",
            f"- mean output tokens: {s['mean_output_tokens']:.0f}",
        ]
    for a, b in combinations(stats, 2):
        common = sorted(
            set(stats[a]["per_task"]) & set(stats[b]["per_task"])
        )
        diffs = [
            stats[a]["per_task"][t] - stats[b]["per_task"][t]
            for t in common
        ]
        if diffs:
            lo, hi = bootstrap(diffs)
            lines.append(
                f"\n{a} - {b}: {100 * sum(diffs) / len(diffs):+.1f} "
                f"points, 95% CI [{100 * lo:+.1f}, {100 * hi:+.1f}]"
            )
    if args.resolve:
        lines += [
            "",
            "## Cited identifiers that did not match",
            "",
        ]
        for m, per_task in by_model.items():
            for rs in per_task.values():
                for r in rs:
                    if r["verdict"]["reason"] in (
                        "wrong-reference",
                        "false-premise",
                    ):
                        cited = r["parsed"]["final_answer"]
                        lines.append(
                            f"- {m} {r['task']}: {cited} -> "
                            f"{resolve(cited)}"
                        )
    report = "\n".join(lines) + "\n"
    (Path(args.run) / "report.md").write_text(report)
    rows = [
        f"{m} & {fmt_ci(s)} & {100 * s.get('sc_acc', 0):.1f} & "
        f"{s.get('agreement', 0):.2f} & {100 * s['unparseable']:.1f} \\\\"
        for m, s in stats.items()
    ]
    (Path(args.run) / "table.tex").write_text(
        "\n".join(rows) + "\n"
    )
    print(report)


if __name__ == "__main__":
    main()
