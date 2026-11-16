"""log2(3) from a float and from mpmath, and what it means."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mathtools.numeric import float_terms, stable_terms
from mathtools.tools import log2_convergents

exact, approx = stable_terms(3, 20), float_terms(3, 20)
print("mpmath:", exact)
print("float: ", approx)
first = next(
    i for i, (a, b) in enumerate(zip(exact, approx)) if a != b
)
print(f"first wrong term from the float: index {first}\n")

print("     l      k  sign  log2(2**l/3**k)  2**l - 3**k")
for r in log2_convergents(3, 12)["convergents"]:
    l, k, ratio = r["l"], r["k"], r["log2_ratio"]
    exact_value = r.get("two_l_minus_q_k", "(too long)")
    print(
        f"{l:6} {k:6}    {r['sign']}   {ratio:>13}    {exact_value}"
    )
