"""Self-consistency: vote over equivalence classes."""

from .checks import check


def same_answer(task, a, b):
    """True if answer a would be graded like answer b."""
    if task["kind"] in ("value", "expression", "antiderivative"):
        probe = dict(task, kind="value", answer=a["final_answer"])
        try:
            return check(probe, b).status == "pass"
        except Exception:
            return False
    key = lambda r: str(r.get("final_answer", "")).strip().lower()
    return key(a) == key(b)


def vote(task, parsed_answers):
    """Return (index of a majority answer, agreement in [0, 1])."""
    classes = []  # lists of sample indices
    for i, ans in enumerate(parsed_answers):
        if not ans or "final_answer" not in ans:
            continue  # unparseable answers cannot vote
        for members in classes:
            if same_answer(task, parsed_answers[members[0]], ans):
                members.append(i)
                break
        else:
            classes.append([i])
    if not classes:
        return None, 0.0
    best = max(classes, key=len)
    return best[0], len(best) / len(parsed_answers)
