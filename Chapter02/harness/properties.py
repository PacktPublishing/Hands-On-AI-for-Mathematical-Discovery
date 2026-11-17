"""Computable properties for checking counterexamples and
witnesses."""

import sympy as sp
from sympy import isprime


def composite_quadratic(n, a, b, c):
    v = a * n * n + b * n + c
    return n >= 0 and v > 1 and not isprime(v)


def cyclotomic_nonflat(n):
    if n < 1:
        return False
    coeffs = sp.Poly(
        sp.cyclotomic_poly(n, sp.Symbol("x"))
    ).all_coeffs()
    return max(abs(c) for c in coeffs) > 1


def fermat_pseudoprime(n):
    return n > 2 and not isprime(n) and pow(2, n, n) == 2


def odd_fermat_pseudoprime(n):
    return (
        isinstance(n, int)
        and n > 1
        and n % 2 == 1
        and not isprime(n)
        and pow(2, n - 1, n) == 1
    )


def prime_divisor_of(n, target):
    return n > 1 and isprime(n) and target % n == 0


def mersenne_composite(p):
    return (
        isinstance(p, int)
        and isprime(p)
        and not isprime(2**p - 1)
    )


def two_cube_sums(n):
    reps, a = 0, 1
    while 2 * a**3 <= n:
        b = round((n - a**3) ** (1 / 3))
        reps += any(
            b + d >= a and a**3 + (b + d) ** 3 == n
            for d in (-1, 0, 1)
        )
        a += 1
    return n > 0 and reps >= 2


def goldbach_violation(n):
    if (
        n <= 2 or n % 2 or n > 10**8
    ):  # larger n: not checkable here
        return False
    return not any(
        isprime(p) and isprime(n - p)
        for p in range(2, n // 2 + 1)
    )


def collatz_divergent(n, max_steps=10**6):
    if n < 1:
        return False
    for _ in range(max_steps):
        if n == 1:
            return False
        n = n // 2 if n % 2 == 0 else 3 * n + 1
    return (
        False  # undecided within budget: never accepted as proof
    )


def goldbach_split(n, limit=10**6):
    """Primes (p, n - p) with p <= limit, or None if there are none."""
    for p in range(2, min(n // 2, limit) + 1):
        if isprime(p) and isprime(n - p):
            return p, n - p
    return None


def collatz_steps(n, max_steps=10**6):
    """Steps until the trajectory of n reaches 1, or None."""
    for k in range(max_steps):
        if n == 1:
            return k
        n = n // 2 if n % 2 == 0 else 3 * n + 1
    return None


def refute_goldbach(n):
    """Why n is not a counterexample; None if undecided."""
    if n <= 2 or n % 2:
        return f"{n} is not an even integer greater than 2"
    split = goldbach_split(n)
    return f"{n} = {split[0]} + {split[1]}" if split else None


def refute_collatz(n):
    """Why n is not a counterexample; None if undecided."""
    if n < 1:
        return f"{n} is not a positive integer"
    k = collatz_steps(n)
    return (
        f"{n} reaches 1 after {k} steps"
        if k is not None
        else None
    )


def square_root_counterexample(w):
    a, b, n = w
    return (
        n > 1
        and (a * a - b * b) % n == 0
        and (a - b) % n != 0
        and (a + b) % n != 0
    )


def sqrt_square_real(x):
    x = sp.nsimplify(x)
    return x.is_real and sp.sqrt(x**2) != x


def quadratic_composite_41(n):
    return composite_quadratic(n, 1, 1, 41)


def divides_fermat5(d):
    f5 = 2**32 + 1
    return isinstance(d, int) and 1 < d < f5 and f5 % d == 0


PROPERTIES = {
    f.__name__: f
    for f in (
        composite_quadratic,
        cyclotomic_nonflat,
        fermat_pseudoprime,
        odd_fermat_pseudoprime,
        prime_divisor_of,
        mersenne_composite,
        two_cube_sums,
        goldbach_violation,
        collatz_divergent,
        square_root_counterexample,
        sqrt_square_real,
        quadratic_composite_41,
        divides_fermat5,
    )
}

REFUTERS = {  # open problems whose candidates can be checked
    "goldbach_violation": refute_goldbach,
    "collatz_divergent": refute_collatz,
}
