"""From model text to structured answers and SymPy objects."""

import ast, json, operator, re
import sympy as sp

FUNCS = {
    "sqrt": sp.sqrt,
    "exp": sp.exp,
    "log": sp.log,
    "ln": sp.log,
    "sin": sp.sin,
    "cos": sp.cos,
    "tan": sp.tan,
    "atan": sp.atan,
    "asin": sp.asin,
    "acos": sp.acos,
    "sinh": sp.sinh,
    "cosh": sp.cosh,
    "Abs": sp.Abs,
    "abs": sp.Abs,
    "sign": sp.sign,
    "floor": sp.floor,
    "factorial": sp.factorial,
    "binomial": sp.binomial,
    "comb": sp.binomial,
    "gamma": sp.gamma,
    "zeta": sp.zeta,
    "Rational": sp.Rational,
}
CONSTS = {
    "pi": sp.pi,
    "E": sp.E,
    "e": sp.E,
    "I": sp.I,
    "oo": sp.oo,
}


def _pow(a, b):
    if a.is_Number and b.is_Integer and abs(b) > 10_000:
        raise ValueError("exponent too large to evaluate")
    return a**b


OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: lambda a, b: sp.floor(a / b),
    ast.Pow: _pow,
    ast.Mod: sp.Mod,
}


def normalize(text):
    text = str(text).strip().strip("$").rstrip(".").strip()
    for a, b in (
        ("^", "**"),
        ("\u2212", "-"),
        ("\u00d7", "*"),
        ("\u03c0", "pi"),
        ("\u00b7", "*"),
    ):
        text = text.replace(a, b)
    return text


def to_sympy(text, symbols=()):
    """Translate a whitelisted expression into SymPy.
    Never calls eval()."""
    names = {s: sp.Symbol(s) for s in symbols}

    def walk(node):
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant) and type(
            node.value
        ) in (int, float):
            return (
                sp.Integer(node.value)
                if type(node.value) is int
                else sp.Rational(repr(node.value))
            )
        if isinstance(node, ast.Name):
            if node.id in names:
                return names[node.id]
            if node.id in CONSTS:
                return CONSTS[node.id]
        if isinstance(node, ast.BinOp) and type(node.op) in OPS:
            return OPS[type(node.op)](
                walk(node.left), walk(node.right)
            )
        if isinstance(node, ast.UnaryOp) and isinstance(
            node.op, (ast.USub, ast.UAdd)
        ):
            value = walk(node.operand)
            return (
                -value if isinstance(node.op, ast.USub) else value
            )
        if (
            isinstance(node, ast.Call)
            and not node.keywords
            and isinstance(node.func, ast.Name)
            and node.func.id in FUNCS
        ):
            return FUNCS[node.func.id](
                *[walk(a) for a in node.args]
            )
        raise ValueError(f"not allowed: {ast.dump(node)[:60]}")

    return walk(ast.parse(normalize(text), mode="eval"))


THINK = re.compile(r"<think>.*?</think>", re.S)


def extract_json(text):
    """Return (answer dict or None, True if valid JSON)."""
    text = THINK.sub("", text or "")
    for block in re.findall(
        r"```(?:json)?\s*(.*?)```", text, re.S
    )[::-1]:
        try:
            obj = json.loads(block)
            if isinstance(obj, dict):
                return obj, True
        except ValueError:
            pass
    starts = [i for i, ch in enumerate(text) if ch == "{"]
    for i in starts:
        try:
            obj, _ = json.JSONDecoder().raw_decode(text[i:])
            if isinstance(obj, dict) and "final_answer" in obj:
                return obj, True
        except ValueError:
            continue
    m = re.search(r"final[ _]answer\W*(.+)", text, re.I)
    if m:
        return {
            "final_answer": m.group(1).strip().strip('"')
        }, False
    return None, False
