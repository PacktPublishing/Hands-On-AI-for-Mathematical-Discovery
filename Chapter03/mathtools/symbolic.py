"""Symbolic derivation of the cycle condition with SymPy."""

import sympy as sp

q, c, x = sp.symbols("q c x")


def fixed_point(word):
    """Compose the affine steps along `word` and solve for x.

    Returns the closed form of the starting value whose orbit
    follows `word`, as a rational function of q and c.
    """
    expr = x
    for bit in word:
        expr = (q * expr + c) / 2 if bit == "1" else expr / 2
    (solution,) = sp.solve(sp.Eq(expr, x), x)
    return sp.factor(solution)


def denominator_factors(l, k, base=3):
    """Factor 2**l - base**k, the denominator of the formula."""
    d = 2**l - base**k
    return d, sp.factorint(abs(d))
