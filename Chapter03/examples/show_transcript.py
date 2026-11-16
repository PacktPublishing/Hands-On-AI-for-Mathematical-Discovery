"""Print one recorded conversation in a compact form.

Usage: python examples/show_transcript.py RUN MODEL TASK [SAMPLE]
"""

import json
import sys
import textwrap


def short(text, width=300):
    text = " ".join(str(text).split())
    return text if len(text) <= width else text[:width] + " ..."


run, model, task = sys.argv[1:4]
sample = int(sys.argv[4]) if len(sys.argv) > 4 else 0
with open(f"{run}/results.jsonl", encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        if (r["model"], r["task"], r["mode"], r["sample"]) == (
            model,
            task,
            "tools",
            sample,
        ) and "error" not in r:
            break
    else:
        sys.exit("no such conversation")

for m in r["transcript"][1:]:
    if m["role"] == "user":
        print("USER:", short(m["content"]))
    elif m["role"] == "tool":
        print("TOOL:", short(m["content"]))
    else:
        if m.get("reasoning") or m.get("reasoning_content"):
            thought = m.get("reasoning") or m.get(
                "reasoning_content"
            )
            print("MODEL (thinking):", short(thought, 200))
        for call in m.get("tool_calls") or []:
            fn = call["function"]
            print(f"MODEL calls {fn['name']}({fn['arguments']})")
        if m.get("content"):
            print("MODEL:", short(m["content"]))
print(f"verdict: {r['verdict']}, rounds: {len(r['rounds'])}")
