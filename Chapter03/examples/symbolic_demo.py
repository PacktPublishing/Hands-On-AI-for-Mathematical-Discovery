"""SymPy derives the cycle condition; compare with the formula."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sympy as sp
from mathtools.symbolic import (
    c,
    denominator_factors,
    fixed_point,
    q,
)


def closed_form(word):
    """x0 = c * S(w) / (2**l - q**k), with q kept as a symbol."""
    l, k = len(word), word.count("1")
    s = sum(
        q ** word[i + 1 :].count("1") * 2**i
        for i in range(l)
        if word[i] == "1"
    )
    return c * s / (2**l - q**k)


for word, c_value in (
    ("110", -1),
    ("1000", 13),
    ("11010110", 13),
):
    x0 = fixed_point(word)
    same = sp.simplify(x0 - closed_form(word)) == 0
    print(
        f"{word}: x0 = {x0}\n    equals closed form: {same}; "
        f"q = 3, c = {c_value}: x0 = {x0.subs({q: 3, c: c_value})}"
    )

for l, k in ((8, 5), (11, 7), (24, 15)):
    d, factors = denominator_factors(l, k)
    print(f"2**{l} - 3**{k} = {d} = {factors}")
