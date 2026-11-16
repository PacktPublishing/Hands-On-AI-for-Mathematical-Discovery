"""Cycles of T(x) = (3x + c)/2 for odd x, x/2 for even x."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mathtools.census import census, survey
from mathtools.maps import cycle_from_word, orbit_cycle

for c, word in ((-1, "110"), (-1, "100"), (13, "11010110")):
    x0 = cycle_from_word(3, c, word)
    print(f"c = {c:3}, word {word}: x0 = {x0}")

print("\nAll cycles of 3x + 13 with period <= 20:")
print("smallest  period  odd  word      primitive")
for f in census(3, 13, 20):
    print(
        f"{f['smallest']:8}  {f['period']:6}  {f['odd_steps']:3}  "
        f"{f['word']:8}  {f['primitive']}"
    )

tail, cycle = orbit_cycle(3, 13, 2861)
print(
    f"\nOrbit of 2861: {tail} steps to the cycle of {cycle[0]}, "
    f"period {len(cycle)}"
)

complete = [f["smallest"] for f in census(3, 29, 20)]
found, escaped, last = survey(3, 29, 10**4)
print(f"\n3x + 29, census up to period 20: {complete}")
pairs = [(m, len(cyc)) for m, cyc in found.items()]
print(
    f"3x + 29, survey of 1..{last}, (smallest, period):\n  {pairs}"
)
