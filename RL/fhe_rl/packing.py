"""
Faithful Python port of CHEHAB's lane packing (src/fheco/dsl/compiler.cpp:
process(), process_composed_vectors(), and compiler_helper_functions.cpp:
constant_folding(), decompose_vector_op(), isSingleOperandExpression()).

Why: the memory estimator counted every scalar variable / per-lane sub-expression as its own
ciphertext, but the compiler packs the lanes of a (Vec ...) into a few ciphertexts (labels c0,c1,...).
Algorithm of the compiler (what is ported here):
  1. every lane of a Vec is constant-folded;
  2. lanes that are plain variables/constants form ONE input vector (a ciphertext c<i>, or a plaintext p<i>
     if every value is a literal); identical vectors inside one expression share one label (dictionary);
  3. lanes that are operations are split BY TOP-LEVEL OPERATOR (+, binary -, unary -, *); for each group the
     operands of all lanes are gathered into two new vectors (decompose_vector_op) and the procedure recurses;
     the groups are then combined with "+";
  4. VecAdd/VecMul/VecMinus/VecNeg/<< keep their structure around the packed Vecs.

pack_expr_str(expr) returns an equivalent expression in the estimator's scalar dialect where every
packed ciphertext is a Var c<i> and every plaintext vector is the constant 1, so the unchanged baseline
estimator then sees the real number of ciphertexts and the real multiplicative depth.
Known simplifications (documented): common-subexpression elimination done by the compiler later is not
modelled (small over-count), and rotation lanes inside a Vec are dropped by the compiler itself (ported as is).
"""
from collections import deque
import re


_LITERAL_RE = re.compile(r"^[+-]?\d+$")


def _tokens(s):
    if not isinstance(s, str):
        return []
    return s.replace("(", "( ").replace(")", " )").split()


def _is_literal(t):
    """Strict literal check: plain integers only (no parens, no vars).

    The old implementation (no alphabetic chars) misclassified folded
    expressions like "( - 0 )" as literals, which then crashed int().
    """
    return isinstance(t, str) and bool(_LITERAL_RE.match(t.strip()))


def _safe_eval(s):
    """Recursively evaluate a folded lane fragment to int, or None.

    Handles nested unary/binary +,-,* over integer literals, e.g.
    "( - 0 )" -> 0, "( - ( - 0 ) )" -> 0, "( + ( - 0 ) 1 )" -> 1.
    Returns None for anything containing variables/operators outside +,-,*.
    """
    if isinstance(s, int):
        return s
    if not isinstance(s, str):
        return None
    s = s.strip()
    if _LITERAL_RE.match(s):
        try:
            return int(s)
        except ValueError:
            return None
    if not (s.startswith("(") and s.endswith(")")):
        return None
    try:
        items = _groups(_tokens(s)[1:-1])
    except Exception:
        return None
    if not items:
        return None
    op = items[0]
    args = items[1:]
    if op == "-" and len(args) == 1:
        v = _safe_eval(args[0])
        return -v if v is not None else None
    if op == "+" and len(args) == 1:
        return _safe_eval(args[0])
    if op in ("+", "-", "*") and len(args) == 2:
        a, b = _safe_eval(args[0]), _safe_eval(args[1])
        if a is None or b is None:
            return None
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        return a * b
    return None


def _to_int(s):
    try:
        return int(s) if isinstance(s, str) and _LITERAL_RE.match(s.strip()) else int(s)
    except (ValueError, TypeError):
        pass
    # Fall back to recursive evaluation for folded fragments like "( - 0 )".
    try:
        return _safe_eval(s)
    except Exception:
        return None


# ───────────── constant folding (port of constant_folding) ─────────────
def _cf(q):
    if not q:
        return ""
    t = q[0]
    if t != "(":
        return q.popleft()
    q.popleft()
    op = q.popleft()
    potential = ""
    o1 = o2 = ""
    if q[0] == "(":
        o1 = _cf(q)
    else:
        o1 = q.popleft()
    if q[0] == "(":
        o2 = _cf(q)
        potential += " "
    elif q[0] != ")":
        o2 = q[0]
        potential = q.popleft()
    if q and q[0] == ")":
        q.popleft()
    if not potential:
        val = _to_int(o1)
        if op == "-" and val is not None:
            return str(-val)
        if op == "+" and val is not None:
            return str(val)
        return f"( {op} {o1} )"

    i1 = _to_int(o1)
    i2 = _to_int(o2)
    gen = f"( {op} {o1} {o2} )"
    if i1 is not None and i2 is not None:
        r = i1 + i2 if op == "+" else i1 - i2 if op == "-" else i1 * i2 if op == "*" else 0
        return str(r)
    if i1 is not None:
        if i1 == 0:
            return o2 if op == "+" else f"( - {o2} )" if op == "-" else "0" if op == "*" else gen
        if i1 == 1:
            return o2 if op == "*" else gen
        if i1 == -1:
            return f"( - {o2} )" if op == "*" else gen
        return gen
    if i2 is not None:
        if i2 == 0:
            return o1 if op == "+" else f"( - {o1} )" if op == "-" else "0" if op == "*" else gen
        if i2 == 1:
            return o1 if op == "*" else gen
        if i2 == -1:
            return f"( - {o1} )" if op == "*" else gen
        return gen
    return gen


def _fold(lane):
    return _cf(deque(_tokens(lane)))


# ───────────── helpers ─────────────
def _groups(tokens):
    """split a token list into top-level items (atoms or balanced groups joined by single spaces)"""
    out, i = [], 0
    if not tokens:
        return out
    n = len(tokens)
    while i < n:
        if tokens[i] == "(":
            depth, j = 0, i
            while j < n:
                if tokens[j] == "(":
                    depth += 1
                elif tokens[j] == ")":
                    depth -= 1
                j += 1
                if depth == 0:
                    break
            if depth != 0:
                # Unbalanced input: treat remainder as one atom, never hang/crash.
                out.append(" ".join(tokens[i:]))
                break
            out.append(" ".join(tokens[i:j]))
            i = j
        else:
            out.append(tokens[i])
            i += 1
    return out


def _is_unary_minus(elem):
    try:
        toks = _tokens(elem)
        if len(toks) < 4 or toks[0] != "(" or toks[1] != "-" or toks[-1] != ")":
            return False
        items = _groups(toks[2:-1])      # operands between "( -" and ")"
        return len(items) == 1
    except Exception:
        return False


def _decompose(elems):
    ops1, ops2 = [], []
    for e in elems:
        if e == "0":
            ops1.append("0"); ops2.append("0"); continue
        try:
            toks = _tokens(e)
            if len(toks) < 4 or toks[0] != "(" or toks[-1] != ")":
                continue
            items = _groups(toks[2:-1])
        except Exception:
            continue
        if len(items) >= 2:
            ops1.append(items[0]); ops2.append(items[1])
        elif len(items) == 1:
            ops1.append(items[0])
    return ops1, ops2


class _Packer:
    def __init__(self):
        self.dictionary = {}          # "Vec lane lane ..." -> label
        self.entries = {}             # label -> kind ('c' or 'p')
        self.n = 0

    def _entry(self, key, kind):
        if key in self.dictionary:
            return self.dictionary[key]
        label = f"{kind}{self.n}"
        self.n += 1
        self.dictionary[key] = label
        self.entries[label] = kind
        return label

    def pcv(self, elems):
        """port of process_composed_vectors; returns a label or a '( op x y )' string"""
        allzero = all(e == "0" for e in elems)
        key = "Vec " + " ".join(elems)
        if allzero:
            return self._entry(key, "p")
        simple, comp = [], []
        for e in elems:
            if e.startswith("("):
                comp.append(e); simple.append("0")
            else:
                comp.append("0"); simple.append(e)
        s0 = all(e == "0" for e in simple)
        c0 = all(e == "0" for e in comp)
        if not s0 and not c0:
            return f"( + {self.pcv(simple)} {self.pcv(comp)} )"
        if not c0:
            add, sub, mul, neg = [], [], [], []
            for e in comp:
                if e == "0":
                    add.append("0"); sub.append("0"); mul.append("0"); neg.append("0"); continue
                if not isinstance(e, str) or len(e) < 5 or not e.startswith("("):
                    # Malformed lane: keep as opaque cipher input, never index-crash.
                    return self._entry(key, "c")
                ch = e[2]
                z = ["0", "0", "0", "0"]
                if ch == "+":
                    z[0] = e
                elif ch == "-":
                    if _is_unary_minus(e):
                        z[3] = e
                    else:
                        z[1] = e
                elif ch == "*":
                    z[2] = e
                add.append(z[0]); sub.append(z[1]); mul.append(z[2]); neg.append(z[3])
            nz = lambda v: not all(x == "0" for x in v)
            if nz(add) and nz(sub) and nz(mul):
                return f"( + {self.pcv(add)} ( + {self.pcv(sub)} {self.pcv(mul)} ) )"
            if nz(add) and nz(sub):
                return f"( + {self.pcv(add)} {self.pcv(sub)} )"
            if nz(sub) and nz(mul):
                return f"( + {self.pcv(sub)} {self.pcv(mul)} )"
            if nz(add) and nz(mul):
                return f"( + {self.pcv(add)} {self.pcv(mul)} )"
            if nz(add):
                a, b = _decompose(add); return f"( + {self.pcv(a)} {self.pcv(b)} )"
            if nz(sub):
                a, b = _decompose(sub); return f"( - {self.pcv(a)} {self.pcv(b)} )"
            if nz(mul):
                a, b = _decompose(mul); return f"( * {self.pcv(a)} {self.pcv(b)} )"
            if nz(neg):
                a, _ = _decompose(neg); return f"( - {self.pcv(a)} )"
            return self._entry(key, "c")      # other composed lanes (e.g. rotations): kept as an input vector, as the compiler does
        # only simple lanes (variables / literals)
        is_lit = all(_is_literal(v) for v in simple)
        return self._entry(key, "p" if is_lit else "c")


def _parse(tokens):
    if not tokens:
        return []
    def rec(i):
        if i >= len(tokens):
            raise ValueError("truncated token stream")
        if tokens[i] == "(":
            i += 1
            node = []
            while i < len(tokens) and tokens[i] != ")":
                ch, i = rec(i)
                node.append(ch)
            if i >= len(tokens):
                raise ValueError("unbalanced parentheses")
            return node, i + 1
        return tokens[i], i + 1
    node, _ = rec(0)
    return node


def _to_str(node):
    return node if isinstance(node, str) else "( " + " ".join(_to_str(x) for x in node) + " )"


_VEC_OPS = {"VecAdd": "+", "VecMinus": "-", "VecNeg": "-", "VecMul": "*", "<<": "<<",
            "VecAddRot": "VecAddRot", "VecMinusRot": "VecMinusRot", "VecMulRot": "VecMulRot"}


def pack(expr):
    """returns (ir_string, n_cipher_inputs, n_plain_inputs, n_ops)

    Never raises: on malformed input returns the raw expression with zero
    cipher/plain counts so the memory estimator falls back gracefully
    instead of killing a SubprocVecEnv worker.
    """
    try:
        return _pack_inner(expr)
    except Exception:
        raw = expr if isinstance(expr, str) else ""
        return raw, 0, 0, 0


def _pack_inner(expr):
    pk = _Packer()

    def proc(node):
        if isinstance(node, str):
            return node
        if node[0] == "Vec":
            lanes = [_fold(_to_str(x)) for x in node[1:]]
            return pk.pcv(lanes)
        op = _VEC_OPS.get(node[0], node[0])
        return "( " + op + " " + " ".join(proc(x) for x in node[1:]) + " )"

    ir = proc(_parse(_tokens(expr)))
    used = set(re.findall(r"\b[cp]\d+\b", ir))
    n_c = sum(1 for l in used if l[0] == "c")
    n_p = sum(1 for l in used if l[0] == "p")
    n_ops = ir.count("(")
    return ir, n_c, n_p, n_ops


def pack_expr_str(expr):
    """expression in the estimator's dialect: cipher vectors -> Var, plaintext vectors -> constant 1"""
    try:
        ir, _, _, _ = pack(expr)
        ir = re.sub(r"\bp\d+\b", "1", ir)
        return ir.replace("( ", "(").replace(" )", ")")
    except Exception:
        return expr if isinstance(expr, str) else ""
