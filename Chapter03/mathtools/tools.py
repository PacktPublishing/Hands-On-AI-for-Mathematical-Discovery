"""The mathematical tools that the model may call."""

import mpmath as mp
import sympy as sp
from .census import census, survey
from .maps import (
    cycle_from_word,
    is_cycle,
    orbit_cycle,
    parity_word,
    step,
)
from .numeric import convergents, stable_terms
from .parse import to_sympy
from .symbolic import fixed_point
from .validate import Bits, Int, Text, ToolError

Q = Int(1, 99, odd=True, doc="odd multiplier q of the map")
C = Int(-(10**6), 10**6, odd=True, doc="odd shift c of the map")


def orbit(q, c, x, max_steps):
    found = orbit_cycle(q, c, x, max_steps)
    if found is None:
        msg = (
            f"no repeat in {max_steps} steps with |x| <= 10**100"
        )
        return {"repeated": False, "message": msg}
    tail, cycle = found
    return {
        "repeated": True,
        "tail": tail,
        "smallest": cycle[0],
        "period": len(cycle),
        "cycle": cycle[:50],
    }


def word_cycle(q, c, word):
    x0 = cycle_from_word(q, c, word)
    result = {
        "x0": str(x0),
        "integer": x0.denominator == 1,
        "positive": x0 > 0,
    }
    if x0.denominator == 1:
        members, x = [], int(x0)
        for _ in word:
            members.append(x)
            x = step(q, c, x)
        result["cycle"] = members
    return result


KEYS = ("smallest", "period", "word", "primitive", "members")
SHOW = 30  # cycles shown in full; the model's context is finite


def cycle_census(q, c, max_len):
    found = census(q, c, max_len)
    cycles = [{k: f[k] for k in KEYS} for f in found]
    return {
        "complete_for": f"all cycles with period <= {max_len}",
        "count": len(cycles),
        "smallest_members": [f["smallest"] for f in cycles][:200],
        "cycles": cycles[:SHOW],
    }


def cycle_survey(q, c, x_max):
    cycles, escaped, last = survey(q, c, x_max)
    rows = [
        {"smallest": m, "period": len(cyc), "members": cyc[:20]}
        for m, cyc in sorted(cycles.items())
    ]
    warning = (
        f"nothing: cycles not reached from 1..{last} are missed"
    )
    return {
        "complete_for": warning,
        "escaped_beyond_10**100": escaped,
        "count": len(rows),
        "smallest_members": [r["smallest"] for r in rows][:200],
        "cycles": rows[:SHOW],
    }


def factor(n):
    if n == 0:
        raise ToolError("0 has no prime factorization")
    pairs = sorted(sp.factorint(abs(n)).items())
    return {
        "sign": "-" if n < 0 else "+",
        "factors": [[int(p), e] for p, e in pairs],
    }


def verify_factor(args, result):
    """Primes whose product is |n|: cheap to check, so check it."""
    product = 1
    for p, e in result["factors"]:
        if not sp.isprime(p):
            return False
        product *= p**e
    return product == abs(args["n"])


def cycle_formula(word):
    return {
        "x0": str(fixed_point(word)),
        "note": "x0 as a function of the map parameters q and c",
    }


def exact_eval(expression):
    try:
        value = to_sympy(expression)
    except (ValueError, SyntaxError, TypeError) as e:
        raise ToolError(f"not a valid expression: {e}")
    if not value.is_number:
        raise ToolError("expression must not contain variables")
    result = {"decimal": str(sp.N(value, 30))}
    try:
        exact = str(value)
    except ValueError:  # Python refuses to print huge integers
        exact = ""
    if 0 < len(exact) <= 1000:
        result["value"] = exact
    else:
        result["note"] = "exact form longer than 1000 characters"
    return result


def log2_convergents(q, count):
    terms = stable_terms(q, terms=count + 1, dps=60)
    rows = []
    with mp.workdps(60):
        for l, k in convergents(terms)[:count]:
            gap = l - k * mp.log(q, 2)  # log2(2**l / q**k)
            row = {
                "l": l,
                "k": k,
                "sign": "+" if gap > 0 else "-",
                "log2_ratio": mp.nstr(gap, 6),
            }
            if l <= 200:  # exact sign and value while it is short
                d = 2**l - q**k
                row["sign"] = "+" if d > 0 else "-"
                row["two_l_minus_q_k"] = str(d)
            rows.append(row)
    return {
        "convergents": rows,
        "precision": "terms agree at 60 and 120 digits",
    }


def is_orbit_piece(q, c, members, period):
    """Listed members follow T and close up if the list is whole."""
    if period <= len(members):
        return is_cycle(q, c, members)
    return all(
        step(q, c, a) == b for a, b in zip(members, members[1:])
    )


def verify_cycle_result(args, result):
    """Re-check a reported cycle with the map itself."""
    if "cycle" not in result:
        return True
    q, c, members = args["q"], args["c"], result["cycle"]
    if "word" in args:
        word = args["word"]
        return (
            is_cycle(q, c, members)
            and parity_word(q, c, members[0], len(word)) == word
        )
    return is_orbit_piece(q, c, members, result["period"])


def verify_census(args, result):  # also used for the survey
    return all(
        is_orbit_piece(
            args["q"], args["c"], f["members"], f["period"]
        )
        for f in result["cycles"]
    )


TOOLS = {
    "orbit": {
        "run": orbit,
        "description": (
            "Iterate T(x) = (q*x + c)/2 for odd x, x/2 for even x, "
            "from x until a value repeats. Returns the number of "
            "steps before the cycle (tail), the cycle's smallest "
            "member, and its period."
        ),
        "params": {
            "q": Q,
            "c": C,
            "x": Int(1, 10**18, doc="starting value"),
            "max_steps": Int(1, 10**6, doc="step budget"),
        },
        "verify": verify_cycle_result,
    },
    "word_cycle": {
        "run": word_cycle,
        "description": (
            "Exact rational starting value whose orbit follows a "
            "parity word periodically (1 = odd step, 0 = even "
            "step). If it is an integer, the word belongs to a "
            "cycle, which is returned."
        ),
        "params": {
            "q": Q,
            "c": C,
            "word": Bits(128, doc="parity word, e.g. 110"),
        },
        "verify": verify_cycle_result,
    },
    "cycle_census": {
        "run": cycle_census,
        "description": (
            "All cycles of T on the positive integers whose period "
            "is at most max_len. Complete by construction: every "
            "parity word is tested."
        ),
        "params": {
            "q": Q,
            "c": C,
            "max_len": Int(1, 20, doc="largest period"),
        },
        "verify": verify_census,
    },
    "cycle_survey": {
        "run": cycle_survey,
        "description": (
            "Cycles of T, of any period, reached from the starting "
            "values 1..x_max. Not complete: a cycle that none of "
            "these orbits reaches is missed."
        ),
        "params": {
            "q": Q,
            "c": C,
            "x_max": Int(1, 10**4, doc="largest starting value"),
        },
        "verify": verify_census,
    },
    "factor": {
        "run": factor,
        "description": "Prime factorization of an integer n.",
        "params": {
            "n": Int(-(10**30), 10**30, doc="the integer")
        },
        "verify": verify_factor,
    },
    "cycle_formula": {
        "run": cycle_formula,
        "description": (
            "Symbolic starting value of the cycle with a given "
            "parity word, as a formula in q and c."
        ),
        "params": {"word": Bits(16, doc="parity word")},
    },
    "exact_eval": {
        "run": exact_eval,
        "description": (
            "Evaluate an arithmetic expression exactly, for "
            "example 2**65 - 3**41 or binomial(40, 20)."
        ),
        "params": {"expression": Text(300, doc="Python syntax")},
    },
    "log2_convergents": {
        "run": log2_convergents,
        "description": (
            "Best approximations l/k of log2(q), with log2(2**l / "
            "q**k) and, for l <= 200, the exact 2**l - q**k. "
            "Cycles of T need 2**l close to q**k."
        ),
        "params": {
            "q": Int(3, 99, odd=True, doc="odd q >= 3"),
            "count": Int(1, 20, doc="number of convergents"),
        },
    },
}
