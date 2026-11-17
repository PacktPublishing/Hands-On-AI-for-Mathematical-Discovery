"""Deterministic checks. A verdict never depends on what the
model says about its own answer."""

import ast, random, signal
from contextlib import contextmanager
from dataclasses import dataclass, asdict
import sympy as sp
from .parse import to_sympy, normalize
from .properties import PROPERTIES, REFUTERS

SPECIAL = {"diverges", "none", "true", "false"}


@dataclass
class Verdict:
    status: str  # pass | fail | unparseable | inconclusive
    method: str = ""  # exact | numeric | property | match
    reason: str = ""  # short failure code, used in reports
    detail: str = ""

    def as_dict(self):
        return asdict(self)


@contextmanager
def time_limit(seconds):
    """Abort slow symbolic work (main thread, Unix only)."""

    def handler(signum, frame):
        raise TimeoutError

    if not hasattr(signal, "SIGALRM"):  # Windows: no time limit
        yield
        return
    try:
        old = signal.signal(signal.SIGALRM, handler)
    except ValueError:  # not in the main thread
        yield
        return
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


SAMPLES = {
    "real": ["-5/2", "-1", "-3/10", "7/10", "19/10", "16/5"],
    "nonzero_real": [
        "-5/2",
        "-1",
        "-3/10",
        "7/10",
        "19/10",
        "16/5",
    ],
    "positive": ["3/10", "7/10", "17/10", "29/10", "51/10"],
    "positive_integer": ["1", "2", "3", "5", "8", "13"],
    "nonnegative_integer": ["0", "1", "2", "3", "5", "8"],
    "integer": ["-4", "-1", "0", "1", "2", "7"],
}


def sample_points(domain, rng, k=8):
    """Points from the stated domain, awkward ones included."""
    names = list(domain)
    pools = [
        [sp.Rational(v) for v in SAMPLES[domain[n]]]
        for n in names
    ]
    if len(names) == 1:
        return [{sp.Symbol(names[0]): v} for v in pools[0]]
    return [
        {
            sp.Symbol(n): rng.choice(p)
            for n, p in zip(names, pools)
        }
        for _ in range(k)
    ]


REGIONS = {
    "real": sp.S.Reals,
    "nonzero_real": sp.S.Reals - sp.FiniteSet(0),
    "positive": sp.Interval.open(0, sp.oo),
    "positive_integer": sp.S.Naturals,
    "nonnegative_integer": sp.S.Naturals0,
    "integer": sp.S.Integers,
}


def poles(expr, domain):
    """Points of a one-variable domain where expr, as written,
    divides by zero. Simplification would hide them."""
    if len(domain) != 1:
        return []
    ((name, kind),) = domain.items()
    x, found = sp.Symbol(name), set()
    try:
        with time_limit(10):
            for p in expr.atoms(sp.Pow):
                if p.exp.is_negative:
                    zeros = sp.solveset(p.base, x, sp.S.Reals)
                    if isinstance(zeros, sp.FiniteSet):
                        found |= set(zeros)
    except TimeoutError:
        pass
    inside = [
        z for z in found if REGIONS[kind].contains(z) == True
    ]
    return [{x: z} for z in sorted(inside, key=str)]


def equivalent(a, b, domain, rng, digits=40):
    """('exact'|'numeric', None) if a equals the reference b on the
    domain, else ('differ', witness point)."""
    for pt in poles(a, domain):  # a undefined where b is defined
        if sp.N(b.subs(pt), digits).is_finite:
            return "differ", {
                str(k): str(v) for k, v in pt.items()
            }
    try:
        with time_limit(10):
            if sp.simplify(a - b) == 0:
                return "exact", None
    except TimeoutError:
        pass
    points = sample_points(domain, rng) if domain else [{}]
    for pt in points:
        va = sp.N(a.subs(pt), digits)
        vb = sp.N(b.subs(pt), digits)
        if not vb.is_finite:  # outside the reference's domain
            continue
        if not va.is_finite or abs(va - vb) > sp.Float(10) ** (
            5 - digits
        ):
            return "differ", {
                str(k): str(v) for k, v in pt.items()
            }
    return "numeric", None


def _expr_check(task, answer, reference, rng):
    domain = task.get("domain", {})
    try:
        got = to_sympy(answer, domain)
    except (ValueError, SyntaxError, TypeError) as e:
        return Verdict(
            "unparseable", reason="format", detail=str(e)[:80]
        )
    how, witness = equivalent(got, reference, domain, rng)
    if how != "differ":
        return Verdict("pass", how)
    if not domain:
        exact = got.is_Rational and reference.is_Rational
        g, r = (
            (got, reference)
            if exact
            else (sp.N(got, 15), sp.N(reference, 15))
        )
        if "." in answer and abs(g - r) <= 1e-8 * (1 + abs(r)):
            return Verdict(
                "fail",
                "numeric",
                "inexact",
                f"decimal {answer} approximates {reference}",
            )
        return Verdict(
            "fail",
            "numeric",
            task.get("probe", "wrong-value"),
            f"got {g}, expected {r}",
        )
    return Verdict(
        "fail",
        "numeric",
        task.get("probe", "wrong-value"),
        f"differs at {witness}",
    )


def check_value(task, answer, rng):
    want = task["answer"]
    if want in SPECIAL or answer.lower() in SPECIAL:
        ok = answer.lower() == want
        return Verdict(
            "pass" if ok else "fail",
            "match",
            "" if ok else task.get("probe", "wrong-value"),
            f"expected {want}, got {answer}",
        )
    return _expr_check(
        task, answer, to_sympy(want, task.get("domain", {})), rng
    )


def check_antiderivative(task, answer, rng):
    x = sp.Symbol(task["variable"])
    try:
        F = to_sympy(answer, task["domain"])
    except (ValueError, SyntaxError, TypeError) as e:
        return Verdict(
            "unparseable", reason="format", detail=str(e)[:80]
        )
    f = to_sympy(task["integrand"], task["domain"])
    how, witness = equivalent(
        sp.diff(F, x), f, task["domain"], rng
    )
    if how == "differ":
        return Verdict(
            "fail",
            "numeric",
            "wrong-value",
            f"F' differs from f at {witness}",
        )
    return Verdict("pass", how)


def _integer(answer):
    value = to_sympy(answer)
    if not value.is_Integer:
        raise ValueError("not an integer")
    return int(value)


def check_open_problem(task, answer):
    """A candidate for a problem nobody has solved (reference answer
    none): refute it if we can; never accept it automatically."""
    if answer.lower() == "none":
        return Verdict("pass", "match")
    try:
        n = _integer(answer)
    except (ValueError, SyntaxError, TypeError):
        return Verdict(
            "unparseable", reason="format", detail=answer[:80]
        )
    refute = REFUTERS.get(task["property"])
    if refute is None:
        return Verdict(
            "fail",
            "match",
            "overclaim",
            f"claimed {n}; compared with the reference none only",
        )
    why = refute(n)
    if why is None:
        return Verdict(
            "inconclusive",
            "property",
            "undecided",
            f"claimed {n}; not refuted within the budget",
        )
    return Verdict("fail", "property", "overclaim", why)


def check_counterexample(task, answer, rng):
    if task["answer"] == "none":
        return check_open_problem(task, answer)
    has = PROPERTIES[task["property"]]
    params = task.get("params", {})
    if answer.lower() == "none":
        return Verdict(
            "fail",
            "match",
            "missed-counterexample",
            f"answered none; {task['answer']} has the property",
        )
    try:
        n = _integer(answer)
    except (ValueError, SyntaxError, TypeError):
        return Verdict(
            "unparseable", reason="format", detail=answer[:80]
        )
    if not has(n, **params):
        return Verdict(
            "fail",
            "property",
            "false-counterexample",
            f"{n} does not have the property",
        )
    if task.get("minimal"):
        for m in range(task.get("start", 0), n):
            if has(m, **params):
                return Verdict(
                    "fail",
                    "property",
                    "not-minimal",
                    f"{m} < {n} also has the property",
                )
    return Verdict("pass", "property")


def check_claim(task, parsed, rng):
    said = normalize(parsed.get("final_answer", "")).lower()
    want = "true" if task["answer"] else "false"
    if said not in ("true", "false"):
        return Verdict(
            "unparseable", reason="format", detail=said[:80]
        )
    if said != want:
        return Verdict(
            "fail",
            "match",
            task.get("probe", "wrong-verdict"),
            f"answered {said}",
        )
    if task["answer"]:
        return Verdict("pass", "match")
    refutes = PROPERTIES[task["witness_property"]]
    try:
        witness = ast.literal_eval(
            normalize(parsed.get("witness", ""))
        )
        ok = refutes(witness)
    except (ValueError, SyntaxError, TypeError):
        ok = False
    if not ok:
        return Verdict(
            "fail",
            "property",
            "invalid-witness",
            f"right verdict, witness {parsed.get('witness')!r} "
            "does not refute the claim",
        )
    return Verdict("pass", "property")


def normalize_id(identifier):
    s = (
        normalize(identifier)
        .lower()
        .replace("https://doi.org/", "doi:")
    )
    s = s.replace("https://arxiv.org/abs/", "arxiv:").replace(
        " ", ""
    )
    if s.startswith("10."):
        s = "doi:" + s
    if s.startswith("arxiv:") and "v" in s[6:]:
        s = s[:6] + s[6:].split("v")[0]
    return s


def check_reference(task, answer, rng):
    got, want = normalize_id(answer), normalize_id(task["answer"])
    if got == want:
        return Verdict("pass", "match")
    if got == "none":
        return Verdict(
            "fail",
            "match",
            "denied-existence",
            f"answered none; the work is {task['answer']}",
        )
    if want == "none":
        return Verdict(
            "fail",
            "match",
            "false-premise",
            f"cited {answer} for a work that does not exist",
        )
    return Verdict(
        "fail",
        "match",
        "wrong-reference",
        f"expected {task['answer']}, got {answer}",
    )


CHECKERS = {
    "value": check_value,
    "expression": check_value,
    "antiderivative": check_antiderivative,
    "counterexample": check_counterexample,
    "reference": check_reference,
}


def check(task, parsed, seed=0):
    """Grade one parsed answer against the task's reference."""
    rng = random.Random(seed)
    if not parsed or "final_answer" not in parsed:
        return Verdict(
            "unparseable", reason="format", detail="no answer"
        )
    if task["kind"] == "claim":
        return check_claim(task, parsed, rng)
    answer = normalize(parsed["final_answer"])
    try:
        return CHECKERS[task["kind"]](task, answer, rng)
    except TimeoutError:
        return Verdict("inconclusive", reason="timeout")


def check_chain(task, steps, final, seed=0):
    """Follow the steps from the task's start to the final answer.
    Returns (status, step): complete, not-checked (no steps),
    unreadable, not-equal, or wrong-end (the final answer does not
    follow from the last step); step is 1-based, or None."""
    if not isinstance(steps, list) or not steps:
        return "not-checked", None
    domain, rng = task.get("domain", {}), random.Random(seed)
    previous = to_sympy(task["start"], domain)
    for i, step in enumerate([*steps, final], 1):
        try:
            current = to_sympy(str(step), domain)
        except (ValueError, SyntaxError, TypeError):
            return "unreadable", i
        if (
            equivalent(current, previous, domain, rng)[0]
            == "differ"
        ):
            return (
                "not-equal" if i <= len(steps) else "wrong-end"
            ), i
        previous = current
    return "complete", None
