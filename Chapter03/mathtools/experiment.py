"""Cycle tasks for 3x + c, asked with and without tools, graded
against the tools' exact results."""

import argparse
import json
import random
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from . import __version__
from .census import census
from .client import ChatClient
from .loop import solve
from .maps import cycle_from_word, orbit_cycle
from .parse import extract_json
from .registry import Registry
from .tools import TOOLS

MAP = (
    "Let T(x) = (3x + c)/2 if x is odd and T(x) = x/2 if x is "
    "even, with c = {c}."
)

QUESTIONS = {
    "orbit": (
        "Starting from x = {x}, apply T repeatedly. How many "
        "steps pass before the orbit first reaches a member of a "
        "cycle, and what is the smallest member of that cycle?"
    ),
    "word": (
        "Is there a positive integer x0 whose orbit under T "
        "follows the parity word {word} periodically, starting "
        "at x0 (1 = odd step, 0 = even step)? If so, give x0."
    ),
    "census": (
        "List the smallest members of all cycles of T on the "
        "positive integers whose period (the number of steps of "
        "T in one cycle) is at most {max_len}."
    ),
}

FORMATS = {
    "orbit": '{"tail": <integer>, "smallest": <integer>}',
    "word": '{"exists": <true or false>, "x0": <integer or null>}',
    "census": '{"smallest_members": [<integers, increasing>]}',
}

SYSTEM = {
    "plain": (
        "You are a careful mathematician. Reply with one JSON "
        'object and nothing else: {"final_answer": ANSWER}.'
    ),
    "tools": (
        "You are a careful mathematician with tools for exact "
        "computation. Use the tools for every computation. When "
        "you are done, reply with one JSON object and nothing "
        'else: {"final_answer": ANSWER}.'
    ),
}


def make_tasks(seed=2026):
    """28 tasks whose answers the tools compute exactly."""
    rng, tasks = random.Random(seed), []
    for c in (1, -1, 5, 13, 17):
        starts = [
            x
            for x in range(101, 3000, 2)
            if 30 <= orbit_cycle(3, c, x)[0] <= 120
        ]
        for x in rng.sample(starts, 2):
            tail, cycle = orbit_cycle(3, c, x)
            tasks.append(
                {
                    "id": f"orbit-c{c}-x{x}",
                    "kind": "orbit",
                    "c": c,
                    "x": x,
                    "answer": {
                        "tail": tail,
                        "smallest": cycle[0],
                    },
                }
            )
    for c, max_len in ((-1, 11), (5, 10), (13, 8), (11, 16)):
        f = census(3, c, max_len)[-1]
        k = rng.randrange(len(f["word"]))
        word = f["word"][k:] + f["word"][:k]
        tasks.append(
            {
                "id": f"word-c{c}-{word}",
                "kind": "word",
                "c": c,
                "word": word,
                "answer": {
                    "exists": True,
                    "x0": int(cycle_from_word(3, c, word)),
                },
            }
        )
    while sum(t["kind"] == "word" for t in tasks) < 10:
        c = rng.choice((-1, 5, 7, 13))
        word = "".join(
            rng.choice("01") for _ in range(rng.randrange(5, 12))
        )
        x0 = cycle_from_word(3, c, word)
        if x0.denominator == 1 and x0 > 0:
            continue
        tasks.append(
            {
                "id": f"word-c{c}-{word}",
                "kind": "word",
                "c": c,
                "word": word,
                "answer": {"exists": False, "x0": None},
            }
        )
    for c, max_len in (
        (1, 20),
        (-1, 10),
        (-1, 11),
        (5, 10),
        (7, 12),
        (11, 16),
        (13, 8),
        (13, 20),
    ):
        tasks.append(
            {
                "id": f"census-c{c}-L{max_len}",
                "kind": "census",
                "c": c,
                "max_len": max_len,
                "answer": {
                    "smallest_members": [
                        f["smallest"]
                        for f in census(3, c, max_len)
                    ]
                },
            }
        )
    return tasks


def build_messages(task, mode):
    question = (
        MAP.format(c=task["c"])
        + " "
        + QUESTIONS[task["kind"]].format(**task)
    )
    system = SYSTEM[mode].replace("ANSWER", FORMATS[task["kind"]])
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": question},
    ]


def as_int(value):
    """An integer, or ValueError: no rounding of 68.5 to 68."""
    if isinstance(value, bool):
        raise ValueError("a boolean is not an integer")
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if isinstance(value, str) and re.fullmatch(r"-?\d+", value):
        value = int(value)
    if not isinstance(value, int):
        raise ValueError(f"not an integer: {value!r}")
    return value


def grade(task, parsed):
    """pass, fail, or unparseable: exact comparison."""
    got = (parsed or {}).get("final_answer")
    if not isinstance(got, dict):
        return "unparseable"
    want = task["answer"]
    try:
        if task["kind"] == "census":
            ok = (
                sorted(map(as_int, got["smallest_members"]))
                == want["smallest_members"]
            )
        elif task["kind"] == "word":
            if not isinstance(got["exists"], bool):
                return "unparseable"
            ok = got["exists"] == want["exists"] and (
                not want["exists"]
                or as_int(got["x0"]) == want["x0"]
            )
        else:
            ok = (
                as_int(got["tail"]) == want["tail"]
                and as_int(got["smallest"]) == want["smallest"]
            )
    except (KeyError, TypeError, ValueError):
        return "unparseable"
    return "pass" if ok else "fail"


def run_one(client, task, mode, sample, base_seed, max_rounds):
    messages = build_messages(task, mode)
    seed = base_seed + sample if client.per_sample_seed else None
    registry = Registry(TOOLS)
    rec = {
        "model": client.name,
        "task": task["id"],
        "kind": task["kind"],
        "mode": mode,
        "sample": sample,
        "seed": seed,
    }
    try:
        if mode == "tools":
            text, messages, rounds = solve(
                client, registry, messages, max_rounds, seed
            )
        else:
            reply = client.chat(messages, seed=seed)
            text = reply["message"].get("content") or ""
            rounds = [
                {
                    k: reply[k]
                    for k in ("finish", "usage", "seconds")
                }
            ]
            messages.append(
                {
                    "role": "assistant",
                    "content": text,
                    "reasoning": reply["message"].get("reasoning")
                    or reply["message"].get("reasoning_content"),
                }
            )
    except Exception as e:  # recorded, and retried when resuming
        rec["error"] = f"{type(e).__name__}: {e}"[:300]
        return rec
    parsed, _ = extract_json(text or "")
    rec.update(
        text=text,
        rounds=rounds,
        transcript=messages,
        tool_log=registry.log,
        parsed=parsed,
        verdict=(
            grade(task, parsed)
            if text is not None
            else "budget-exhausted"
        ),
    )
    return rec


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="configs/models.json")
    ap.add_argument("--models", nargs="*")
    ap.add_argument(
        "--modes", nargs="*", default=["plain", "tools"]
    )
    ap.add_argument("--samples", type=int, default=3)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--max-rounds", type=int, default=10)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with open(args.config, encoding="utf-8-sig") as f:
        configs = [
            c
            for c in json.load(f)["models"]
            if not args.models or c["name"] in args.models
        ]
    clients = [
        ChatClient(
            **{k: v for k, v in c.items() if k != "backend"}
        )
        for c in configs
    ]
    tasks = make_tasks()
    (out / "manifest.json").write_text(
        json.dumps(
            {
                "mathtools": __version__,
                "tasks": len(tasks),
                "samples": args.samples,
                "seed": args.seed,
                "max_rounds": args.max_rounds,
                "modes": args.modes,
                "models": configs,
            },
            indent=2,
        )
    )
    results, done = out / "results.jsonl", set()
    if results.exists():
        with open(results) as f:
            for line in f:
                r = json.loads(line)
                if "error" not in r:
                    done.add(
                        (
                            r["model"],
                            r["task"],
                            r["mode"],
                            r["sample"],
                        )
                    )
    jobs = [
        (cl, t, m, i)
        for cl in clients
        for t in tasks
        for m in args.modes
        for i in range(args.samples)
        if (cl.name, t["id"], m, i) not in done
    ]
    print(
        f"{len(jobs)} conversations to run, {len(done)} recorded",
        flush=True,
    )
    with ThreadPoolExecutor(args.workers) as pool, open(
        results, "a"
    ) as f:
        futures = [
            pool.submit(
                run_one, cl, t, m, i, args.seed, args.max_rounds
            )
            for cl, t, m, i in jobs
        ]
        for k, future in enumerate(as_completed(futures), 1):
            f.write(
                json.dumps(future.result(), default=str) + "\n"
            )
            f.flush()
            if k % 20 == 0 or k == len(jobs):
                print(f"  {k}/{len(jobs)}", flush=True)


if __name__ == "__main__":
    main()
