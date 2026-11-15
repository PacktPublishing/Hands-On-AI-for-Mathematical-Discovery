"""Grade typical wrong answers. Run from the Chapter02 folder:
python3 examples/check_demo.py"""

import sys

sys.path.insert(0, ".")
from harness.run import load_tasks
from harness.checks import check, check_chain
from harness.consistency import vote

tasks = {t["id"]: t for t in load_tasks("tasks/core.jsonl")}

answers = [
    ("val-quartic", {"final_answer": "pi/(2*sqrt(2))"}),
    ("val-zeta2", {"final_answer": "1.6449340668482264"}),
    ("exp-sqrt-sq", {"final_answer": "x"}),
    ("val-inv-x", {"final_answer": "0"}),
    ("cex-euler41", {"final_answer": "41"}),
    (
        "clm-sqrt-mod",
        {"final_answer": "false", "witness": "(2, 2, 8)"},
    ),
    ("cex-goldbach", {"final_answer": "4"}),
    ("ref-rh-2026", {"final_answer": "arXiv:2610.04512"}),
]
for task_id, answer in answers:
    v = check(tasks[task_id], answer)
    print(f"{task_id:13} {v.status:5} {v.reason}")
    if v.detail:
        print(f"    {v.detail}")

steps = ["(x**2)**(1/2)", "x"]
print(
    "first broken step:", check_chain(tasks["exp-sqrt-sq"], steps)
)

samples = [
    {"final_answer": a}
    for a in [
        "pi*sqrt(2)/4",
        "pi/(2*sqrt(2))",
        "pi/4",
        "sqrt(2)*pi/4",
    ]
]
print("majority, agreement:", vote(tasks["val-quartic"], samples))
