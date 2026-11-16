"""Arbitrary precision: where do 2**l and q**k nearly agree?"""

import math
import mpmath as mp


def continued_fraction(value, terms):
    """Continued-fraction terms of value, at current precision."""
    out = []
    for _ in range(terms):
        a = int(mp.floor(value))
        out.append(a)
        value = value - a
        if value == 0:
            break
        value = 1 / value
    return out


def stable_terms(q, terms=25, dps=50):
    """Terms of log2(q) that agree at dps and at 2*dps digits."""
    with mp.workdps(dps):
        low = continued_fraction(mp.log(q, 2), terms)
    with mp.workdps(2 * dps):
        high = continued_fraction(mp.log(q, 2), terms)
    n = next(
        (i for i, (a, b) in enumerate(zip(low, high)) if a != b),
        min(len(low), len(high)),
    )
    return high[:n]


def convergents(terms):
    """Best approximations l/k from continued-fraction terms."""
    p0, q0, p1, q1 = 1, 0, terms[0], 1
    result = [(p1, q1)]
    for a in terms[1:]:
        p0, q0, p1, q1 = p1, q1, a * p1 + p0, a * q1 + q0
        result.append((p1, q1))
    return result


def float_terms(q, terms=25):
    """The same expansion from a 53-bit float, for comparison."""
    value, out = math.log2(q), []
    for _ in range(terms):
        a = math.floor(value)
        out.append(a)
        value = 1 / (value - a)
    return out
