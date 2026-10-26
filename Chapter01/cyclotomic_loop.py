from sympy import Poly, cyclotomic_poly, factorint, symbols

x = symbols("x")


def coeffs(n):
    """Coefficients of Phi_n, constant term first."""
    return Poly(cyclotomic_poly(n, x), x).all_coeffs()[::-1]


def height(n):
    """Largest absolute value of a coefficient of Phi_n."""
    return max(abs(c) for c in coeffs(n))


for n in [1, 2, 3, 4, 6, 12, 15]:
    print(n, cyclotomic_poly(n, x))
print(sorted({height(n) for n in range(1, 101)}))
from sympy import divisors, expand, isprime, prod, totient


def validate(N=200):
    """Check the pipeline against identities with known answers."""
    for n in range(1, N + 1):
        f = cyclotomic_poly(n, x)
        assert len(coeffs(n)) - 1 == totient(n)
        lhs = prod(cyclotomic_poly(d, x) for d in divisors(n))
        assert expand(lhs - (x**n - 1)) == 0
        if isprime(n):
            assert expand(f - sum(x**k for k in range(n))) == 0
        if n % 2 == 1 and n > 1:
            g = cyclotomic_poly(2 * n, x)
            assert expand(g - f.subs(x, -x)) == 0
    return f"pipeline agrees with known identities for n <= {N}"


print(validate())
first = next(n for n in range(1, 10_000) if height(n) > 1)
print(first, height(first))
print([k for k, a in enumerate(coeffs(first)) if abs(a) > 1])
def odd_primes(n):
    return [p for p in factorint(n) if p != 2]


bad = [n for n in range(1, 1001)
       if height(n) > 1 and len(odd_primes(n)) <= 2]
print(bad)

flat = [n for n in range(1, 1001)
        if n % 2 == 1 and len(odd_primes(n)) == 3
        and max(factorint(n).values()) == 1 and height(n) == 1]
print(flat[:5])
