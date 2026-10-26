import sympy as sp

z1, z2, z3 = sp.symbols("z1 z2 z3")
u = 1 + z1*z2
F = sp.Matrix([
    u**3*z3 + z2**2*u*(4 + 3*z1*z2),
    z2 + 3*z1*u**2*z3 + 3*z1*z2**2*(4 + 3*z1*z2),
    2*z1 - 3*z1**2*z2 - z1**3*z3,
])

print(sp.expand(F.jacobian([z1, z2, z3]).det()))   # -2

R = sp.Rational
points = [
    (0, 0, R(-1, 4)),
    (1, R(-3, 2), R(13, 2)),
    (-1, R(3, 2), R(13, 2)),
]
for p in points:
    print(list(F.subs(dict(zip((z1, z2, z3), p)))))  # [-1/4, 0, 0]
