"""Constant folding of a vector-language expression before it is given to the CHEHAB compiler.

Some rewrite rules introduce constant-only subexpressions, e.g. mul-0-0*0 (0 -> (* 0 0)) or
sub-0-0-0 (0 -> (- 0 0)). CHEHAB turns a vector of literals into a plaintext, so an operation whose
operands are all literals becomes a plaintext-plaintext operation, which its SEAL code generator
rejects ("backend does not support plain plain evaluation"). Folding evaluates every subexpression
without variables to a literal (scalar) or a (Vec c0 c1 ...) of literals, which a compiler would do
anyway; the value of the program does not change.

Operators: + - * (scalar, '-' unary or binary), Vec, VecAdd / VecMinus / VecMul (n-ary),
VecNeg, << (rotate left by a constant).
"""


def _tokenize(s):
    return s.replace("(", " ( ").replace(")", " ) ").split()


def _parse(tokens, i=0):
    if tokens[i] != "(":
        return tokens[i], i + 1
    op = tokens[i + 1]
    i += 2
    args = []
    while tokens[i] != ")":
        a, i = _parse(tokens, i)
        args.append(a)
    return (op, args), i + 1


def _is_int(tok):
    t = tok[1:] if tok.startswith("-") else tok
    return t.isdigit()


def _value(node):
    """('s', int) or ('v', [int, ...]) if the node has no variable, else None."""
    if isinstance(node, str):
        return ("s", int(node)) if _is_int(node) else None
    op, args = node
    if op == "<<":
        v = _value(args[0])
        if v is None or v[0] != "v" or not _is_int(args[1]):
            return None
        k = int(args[1]) % len(v[1])
        return ("v", v[1][k:] + v[1][:k])
    vals = [_value(a) for a in args]
    if any(v is None for v in vals):
        return None
    if op == "Vec":
        if any(v[0] != "s" for v in vals):
            return None
        return ("v", [v[1] for v in vals])
    if op in ("+", "*", "-") and all(v[0] == "s" for v in vals):
        xs = [v[1] for v in vals]
        if op == "-" and len(xs) == 1:
            return ("s", -xs[0])
        r = xs[0]
        for x in xs[1:]:
            r = r + x if op == "+" else r * x if op == "*" else r - x
        return ("s", r)
    if op in ("VecAdd", "VecMinus", "VecMul", "VecNeg") and all(v[0] == "v" for v in vals):
        xs = [v[1] for v in vals]
        if op == "VecNeg":
            return ("v", [-x for x in xs[0]])
        r = list(xs[0])
        for x in xs[1:]:
            r = [a + b if op == "VecAdd" else a * b if op == "VecMul" else a - b for a, b in zip(r, x)]
        return ("v", r)
    return None


def _fold(node, counter):
    if isinstance(node, str):
        return node
    op, args = node
    v = _value(node)
    if v is not None and not (op == "Vec" and all(isinstance(a, str) for a in args)):
        counter[0] += 1
        return str(v[1]) if v[0] == "s" else ("Vec", [str(x) for x in v[1]])
    if op == "<<":   # keep the rotation step as is
        return (op, [_fold(args[0], counter), args[1]])
    return (op, [_fold(a, counter) for a in args])


def _print(node):
    if isinstance(node, str):
        return node
    op, args = node
    return "(" + " ".join([op] + [_print(a) for a in args]) + ")"


def fold_constants(expr: str):
    """Returns (folded expression, number of folded subexpressions)."""
    tree, _ = _parse(_tokenize(expr))
    counter = [0]
    folded = _fold(tree, counter)
    return (_print(folded) if counter[0] else expr), counter[0]
