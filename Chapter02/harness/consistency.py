"""Self-consistency: vote over equivalence classes."""

import random
import sympy as sp
from .checks import SPECIAL, equivalent
from .parse import normalize, to_sympy


def same_answer(task, a, b):
    """True if answers a and b belong to one class: equal on the
    task's domain; antiderivatives equal up to a constant."""
    sa, sb = (
        normalize(r["final_answer"]).lower() for r in (a, b)
    )
    if task["kind"] not in (
        "value",
        "expression",
        "antiderivative",
    ):
        return sa == sb
    if sa in SPECIAL or sb in SPECIAL:
        return sa == sb
    domain, rng = task.get("domain", {}), random.Random(0)
    try:
        fa, fb = (to_sympy(s, domain) for s in (sa, sb))
        if task["kind"] == "antiderivative":
            x = sp.Symbol(task["variable"])
            fa, fb = sp.diff(fa, x), sp.diff(fb, x)
        return all(
            equivalent(u, v, domain, rng)[0] != "differ"
            for u, v in ((fa, fb), (fb, fa))
        )
    except Exception:  # unreadable or unevaluable: no match
        return False


def vote(task, parsed_answers):
    """Return (majority, agreement in [0, 1]). The majority lists
    one sample index per largest class; a tie such as 2-2-1 has
    two. Unparseable answers cannot vote."""
    classes = []  # lists of sample indices
    for i, ans in enumerate(parsed_answers):
        if not ans or "final_answer" not in ans:
            continue
        for members in classes:
            if same_answer(task, parsed_answers[members[0]], ans):
                members.append(i)
                break
        else:
            classes.append([i])
    if not classes:
        return [], 0.0
    top = max(map(len, classes))
    majority = [c[0] for c in classes if len(c) == top]
    return majority, top / len(parsed_answers)
