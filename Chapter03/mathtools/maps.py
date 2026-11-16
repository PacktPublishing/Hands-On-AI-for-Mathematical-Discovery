"""The maps T(x) = (q*x + c)/2 for odd x, T(x) = x/2 for even x."""

from fractions import Fraction
from math import gcd


def step(q, c, x):
    """One step of T for odd q and c; exact on all integers."""
    return (q * x + c) // 2 if x % 2 else x // 2


def parity_word(q, c, x, length):
    """The parities of x, T(x), T(T(x)), ... as a bit string."""
    bits = []
    for _ in range(length):
        bits.append("1" if x % 2 else "0")
        x = step(q, c, x)
    return "".join(bits)


def cycle_from_word(q, c, word):
    """The unique rational x0 whose orbit repeats `word` forever.

    x0 = c * S(w) / (2**l - q**k), with S(w) the sum of
    q**(number of 1s after i) * 2**i over the positions i of 1s.
    """
    l, k = len(word), word.count("1")
    s, ones_after = 0, 0
    for i in reversed(range(l)):
        if word[i] == "1":
            s += q**ones_after * 2**i
            ones_after += 1
    return Fraction(c * s, 2**l - q**k)


def orbit_cycle(q, c, x, max_steps=1_000_000, limit=10**100):
    """Iterate from x until a value repeats.

    Returns (tail, cycle): the number of steps before the orbit
    enters the cycle, and the cycle from its smallest member on.
    Returns None if no value repeats within max_steps or if |x|
    exceeds limit (for q = 5, most orbits seem to grow forever).
    """
    seen, seq = {}, []
    while x not in seen:
        if len(seq) >= max_steps or abs(x) > limit:
            return None
        seen[x] = len(seq)
        seq.append(x)
        x = step(q, c, x)
    tail = seen[x]
    return tail, rotate_to_min(seq[tail:])


def rotate_to_min(cycle):
    i = cycle.index(min(cycle))
    return cycle[i:] + cycle[:i]


def is_cycle(q, c, members):
    """Independent check: does T map each member to the next?"""
    n = len(members)
    return (
        n > 0
        and all(
            step(q, c, members[i]) == members[(i + 1) % n]
            for i in range(n)
        )
        and len(set(members)) == n
    )


def is_primitive(c, members):
    """Lagarias: a cycle is primitive if gcd(member, c) = 1."""
    return all(gcd(m, c) == 1 for m in members)
