"""Run a benchmark: every model x task x sample, recorded and
graded."""

import argparse, datetime, hashlib, json, platform, sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import sympy as sp
from . import __version__
from .checks import Verdict, check, check_chain
from .families import generate
from .models import ModelError, Replay, make_client, request_key
from .parse import extract_json
from .prompts import PROMPT_VERSION, build_messages, prompt_sha


def load_tasks(path, family_seed=2026, family_size=4):
    with open(path) as f:
        tasks = [json.loads(line) for line in f if line.strip()]
    return tasks + (
        generate(family_seed, family_size) if family_size else []
    )


def ask(client, task, sample, base_seed):
    """One model call. Runs in a worker thread; never grades."""
    messages = build_messages(task)
    seed = base_seed + sample if client.per_sample_seed else None
    rec = {
        "model": client.name,
        "task": task["id"],
        "kind": task["kind"],
        "sample": sample,
        "seed": seed,
        "request_key": request_key(client.name, messages, seed),
    }
    try:
        c = client.complete(messages, seed=seed)
        rec.update(
            text=c.text,
            reasoning=c.reasoning,
            finish=c.finish,
            served_model=c.model,
            usage=c.usage,
            seconds=c.seconds,
        )
    except ModelError as e:
        rec["error"] = str(e)[:300]
    return rec


def grade(task, rec):
    """Deterministic grading. Runs in the main thread."""
    if "error" in rec:
        rec["verdict"] = Verdict(
            "error", reason="model-error"
        ).as_dict()
        return rec
    parsed, valid_json = extract_json(rec["text"])
    verdict = check(task, parsed, seed=rec["sample"])
    rec.update(
        parsed=parsed,
        valid_json=valid_json,
        verdict=verdict.as_dict(),
    )
    steps = (parsed or {}).get("steps")
    if task.get("chain") and isinstance(steps, list):
        rec["chain_break"] = check_chain(task, steps)
    return rec


def write_manifest(out, args, tasks, clients):
    tasks_blob = json.dumps(tasks, sort_keys=True).encode()
    now = datetime.datetime.now(datetime.timezone.utc)
    manifest = {
        "created": now.isoformat(timespec="seconds"),
        "harness": __version__,
        "prompt": PROMPT_VERSION,
        "prompt_sha": prompt_sha(),
        "tasks_sha": hashlib.sha256(tasks_blob).hexdigest()[:16],
        "n_tasks": len(tasks),
        "samples": args.samples,
        "seed": args.seed,
        "families": args.families,
        "family_seed": args.family_seed,
        "python": platform.python_version(),
        "sympy": sp.__version__,
        "argv": sys.argv[1:],
        "models": [
            {
                "name": c.name,
                "model": c.model,
                "endpoint": getattr(c, "base_url", ""),
                "params": getattr(c, "params", {}),
                "per_sample_seed": c.per_sample_seed,
                "served": c.describe(),
            }
            for c in clients
        ],
    }
    name = "manifest.json"
    if (out / name).exists():  # a resumed run
        name = f"manifest-{now:%Y%m%dT%H%M%S}.json"
    (out / name).write_text(
        json.dumps(manifest, indent=2, default=str)
    )


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="configs/models.json")
    ap.add_argument(
        "--models", nargs="*", help="names from the config"
    )
    ap.add_argument("--tasks", default="tasks/core.jsonl")
    ap.add_argument(
        "--families",
        type=int,
        default=4,
        help="variants per task family (0 = none)",
    )
    ap.add_argument("--family-seed", type=int, default=2026)
    ap.add_argument("--samples", type=int, default=5)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument(
        "--replay",
        help="results.jsonl of an earlier run; "
        "re-grade it without calling any model",
    )
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    tasks = load_tasks(
        args.tasks, args.family_seed, args.families
    )
    by_id = {t["id"]: t for t in tasks}
    if args.replay:
        with open(args.replay) as f:
            names = sorted(
                {json.loads(line)["model"] for line in f}
            )
        clients = [
            Replay(n, args.replay)
            for n in names
            if not args.models or n in args.models
        ]
    else:
        with open(args.config) as f:
            configs = json.load(f)["models"]
        clients = [
            make_client(c)
            for c in configs
            if not args.models or c["name"] in args.models
        ]
    write_manifest(out, args, tasks, clients)

    results, done = out / "results.jsonl", set()
    if results.exists():  # resume, skip finished
        with open(results) as f:
            for line in f:
                r = json.loads(line)
                if "error" not in r:
                    done.add((r["model"], r["task"], r["sample"]))
    jobs = [
        (c, t, i)
        for c in clients
        for t in tasks
        for i in range(args.samples)
        if (c.name, t["id"], i) not in done
    ]
    print(
        f"{len(jobs)} calls to run, {len(done)} already recorded"
    )
    with ThreadPoolExecutor(args.workers) as pool, open(
        results, "a"
    ) as f:
        futures = [
            pool.submit(ask, c, t, i, args.seed)
            for c, t, i in jobs
        ]
        for k, future in enumerate(as_completed(futures), 1):
            rec = future.result()
            rec = grade(by_id[rec["task"]], rec)
            f.write(json.dumps(rec, default=str) + "\n")
            f.flush()
            if k % 50 == 0 or k == len(jobs):
                print(f"  {k}/{len(jobs)}")


if __name__ == "__main__":
    main()
