"""Parameterized task families: new numbers, same mathematics."""

import random
from math import comb, factorial
from sympy import divisor_count


def generate(seed=2026, n=4):
    rng = random.Random(seed)
    tasks = []

    for i, digits in enumerate([6, 9, 12, 15][:n]):
        a = rng.randrange(10 ** (digits - 1), 10**digits)
        b = rng.randrange(10 ** (digits - 1), 10**digits)
        tasks.append(
            {
                "id": f"fam-mult-{i}",
                "kind": "value",
                "family": "mult",
                "probe": "arithmetic",
                "prompt": f"Compute {a} * {b} exactly.",
                "answer": str(a * b),
            }
        )

    for i in range(n):
        a, e = rng.randrange(3, 98), rng.randrange(1000, 9999)
        tasks.append(
            {
                "id": f"fam-powmod-{i}",
                "kind": "value",
                "family": "powmod",
                "probe": "arithmetic",
                "prompt": f"What are the last four digits of "
                f"{a}^{e}? Give them as an integer "
                f"between 0 and 9999.",
                "answer": str(pow(a, e, 10000)),
            }
        )

    for i in range(n):
        p, N = rng.choice([2, 3, 4]), rng.randrange(100, 999)
        total = sum(k**p for k in range(1, N + 1))
        tasks.append(
            {
                "id": f"fam-sumpow-{i}",
                "kind": "value",
                "family": "sumpow",
                "probe": "arithmetic",
                "prompt": f"Compute the sum of k^{p} for "
                f"k = 1, ..., {N}.",
                "answer": str(total),
            }
        )

    for i in range(n):
        red, blue = rng.randrange(6, 15), rng.randrange(6, 15)
        k = rng.randrange(4, 7)
        j = rng.randrange(1, k)
        base = (
            f"A box contains {red} red and {blue} blue balls. In how "
            f"many ways can you choose {k} balls so that exactly {j} "
            f"of them are red?"
        )
        noise = (
            f" Three of the blue balls are slightly smaller than "
            f"the others."
        )
        answer = str(comb(red, j) * comb(blue, k - j))
        for variant, text in (
            ("plain", base),
            ("distractor", base + noise),
        ):
            tasks.append(
                {
                    "id": f"fam-balls-{i}-{variant}",
                    "kind": "value",
                    "family": f"balls-{variant}",
                    "probe": "distractor",
                    "pair": f"fam-balls-{i}",
                    "prompt": text,
                    "answer": answer,
                }
            )

    for i in range(n):
        m = rng.randrange(8, 17)
        tasks.append(
            {
                "id": f"fam-divisors-{i}",
                "kind": "value",
                "family": "divisors",
                "probe": "arithmetic",
                "prompt": f"How many positive divisors does {m}! "
                f"have?",
                "answer": str(divisor_count(factorial(m))),
            }
        )
    return tasks
