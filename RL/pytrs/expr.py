from __future__ import annotations
# expr.py  ────────────────────────────────────────────────────────────────────
"""
Light‑weight algebraic AST with built‑in structural validation.

New in this version
───────────────────
* support for a rotate‑left operator  `<<`
  – first argument must be a *vector expression*  
  – second argument must be an integer `Const`
"""

##############################################################################
#  Base class and leaf nodes
##############################################################################

class Expr:
    """
    Parent of Const, Var and Op.
    Provides a single .validate_expression(debug=True/False) method that checks:

    • scalar correctness for  +  *  unary/binary -
    • vector correctness for   Vec  VecNeg  VecAdd  VecMinus  VecMul
    • NEW: rotate‑left          <<   (vector , int‑Const)
    • all (Vec …) containers appearing in the tree have identical length
    """

    # ---------- operator class‑level sets -----------------------------------
    SCALAR_BINARY_ONLY  = {"+", "*"}                     # strictly binary
    VECTOR_UNARY_OPS    = {"VecNeg"}                     # strictly unary
    VECTOR_N_ARY_OPS    = {"VecAdd", "VecMinus", "VecMul"}  # >= 2 children
    ROTATE_OP           = "<<"                           # exactly 2 children

    # ---------- validation --------------------------------------------------
    def validate_expression(
        self,
        depth: int = 0,
        expected_vec_length: int | None = None,
        debug: bool = False
    ) -> bool:
        """Return True if the expression tree is well‑formed (see doc‑string).

        DAG-aware: results are memoized by (id(self), expected_vec_length) for
        the duration of a single top-level call, so shared subtrees are
        validated once instead of once-per-occurrence (exponential -> linear
        on shared/DAG trees produced by the vectorize / distributive rules).
        """
        cache: dict = {}
        return self._validate_cached(depth, expected_vec_length, debug, cache)

    def _validate_cached(
        self,
        depth: int,
        expected_vec_length: int | None,
        debug: bool,
        cache: dict,
    ) -> bool:
        key = (id(self), expected_vec_length)
        cached = cache.get(key)
        if cached is not None:
            return cached
        result = self._validate_impl(depth, expected_vec_length, debug, cache)
        cache[key] = result
        return result

    def _validate_impl(
        self,
        depth: int,
        expected_vec_length: int | None,
        debug: bool,
        cache: dict,
    ) -> bool:
        """Original validation logic; recursive calls go through _validate_cached."""
        ind = "  " * depth  # indentation helper

        if debug:
            print(f"{ind}[INFO] Checking: {self}")

        # ── leaf: Const or Var ──────────────────────────────────────────────
        if isinstance(self, Const):
            if debug:
                print(f"{ind}  -> Const ⇒ OK")
            return True

        if isinstance(self, Var):
            if debug:
                print(f"{ind}  -> Var   ⇒ OK")
            return True

        # ── internal node: Op ───────────────────────────────────────────────
        if not isinstance(self, Op):
            if debug:
                print(f"{ind}[ERROR] Unknown node type: {type(self)}")
            return False

        op   = self.op
        args = self.args
        n    = len(args)

        if debug:
            print(f"{ind}  -> Op '{op}' with {n} child(ren)")

        # ────────────────────────────────────────────────────────────────────
        # A) plain (Vec …) container
        # ────────────────────────────────────────────────────────────────────
        if op == "Vec":
            vec_len = n
            if expected_vec_length is None:
                expected_vec_length = vec_len
                if debug:
                    print(f"{ind}  • set common Vec length = {vec_len}")
            elif vec_len != expected_vec_length:
                if debug:
                    print(f"{ind}[ERROR] Vec length {vec_len} ≠ expected {expected_vec_length}")
                return False

            for i, child in enumerate(args):
                if debug:
                    print(f"{ind}    checking Vec element #{i}")
                if not child._validate_cached(depth+2, None, debug, cache):
                    return False
            return True

        # ────────────────────────────────────────────────────────────────────
        # B) unary vector op  (VecNeg)
        # ────────────────────────────────────────────────────────────────────
        if op in self.VECTOR_UNARY_OPS:
            if n != 1:
                if debug:
                    print(f"{ind}[ERROR] '{op}' expects 1 child, got {n}")
                return False
            return args[0]._validate_cached(depth+2, expected_vec_length, debug, cache)

        # ────────────────────────────────────────────────────────────────────
        # C) n‑ary vector ops  (VecAdd / VecMinus / VecMul)
        # ────────────────────────────────────────────────────────────────────
        if op in self.VECTOR_N_ARY_OPS:
            if n < 2:
                if debug:
                    print(f"{ind}[ERROR] '{op}' expects ≥2 children, got {n}")
                return False
            return all(
                child._validate_cached(depth+2, expected_vec_length, debug, cache)
                for child in args
            )

        # ────────────────────────────────────────────────────────────────────
        # D) rotate‑left  (<< vector  Const‑int)
        # ────────────────────────────────────────────────────────────────────
        if op == self.ROTATE_OP:
            if n != 2:
                if debug:
                    print(f"{ind}[ERROR] '<<' expects 2 children, got {n}")
                return False

            vec_child, shift_child = args

            # first argument must be a *vector expression*
            if not vec_child._validate_cached(depth+2, expected_vec_length, debug):
                if debug:
                    print(f"{ind}[ERROR] first arg of '<<' must be a vector")
                return False

            # second argument must be an integer Const (shift amount)
            if not (isinstance(shift_child, Const) and isinstance(shift_child.value, int)):
                if debug:
                    print(f"{ind}[ERROR] second arg of '<<' must be integer Const")
                return False
            return True

        # ────────────────────────────────────────────────────────────────────
        # E) unary minus  /  binary minus
        # ────────────────────────────────────────────────────────────────────
        if op == "-" and n == 1:         # unary
            return args[0]._validate_cached(depth+2, None, debug, cache)

        if op == "-" and n == 2:         # binary
            return all(
                child._validate_cached(depth+2, None, debug, cache)
                for child in args
            )

        # ────────────────────────────────────────────────────────────────────
        # F) scalar binary (+, *)
        # ────────────────────────────────────────────────────────────────────
        if op in self.SCALAR_BINARY_ONLY:
            if n != 2:
                if debug:
                    print(f"{ind}[ERROR] '{op}' expects 2 children, got {n}")
                return False
            return all(
                child._validate_cached(depth+2, None, debug, cache)
                for child in args
            )

        # ────────────────────────────────────────────────────────────────────
        # otherwise: unknown / wrong arity
        # ────────────────────────────────────────────────────────────────────
        if debug:
            print(f"{ind}[ERROR] unknown or mis‑used operator '{op}'")
        return False


##############################################################################
#  Leaf nodes
##############################################################################

class Const(Expr):
    def __init__(self, value: int | float):
        self.value = value
    def _struct_hash(self) -> int:
        return hash(("const", self.value))
    def __repr__(self) -> str:
        return f"Const({self.value})"
    def __eq__(self, other):  return isinstance(other, Const) and self.value == other.value
    def __hash__(self):       return hash(("const", self.value))

class Var(Expr):
    def __init__(self, name: str,parent:str=None):
        self.name = name
        self.parent_op = parent
    def _struct_hash(self) -> int:
        return hash(("var", self.name))
    def __repr__(self) -> str:
        return f"Var({self.name})"
    def __eq__(self, other):  return isinstance(other, Var) and self.name == other.name
    def __hash__(self):       return hash(("var", self.name))


##############################################################################
#  Internal node
##############################################################################

class Op(Expr):
    def __init__(self, op: str, args: list[Expr]):
        self.op   = op
        self.args = args
        self._cached_struct_hash = None
    def _struct_hash(self) -> int:
        """Structural hash of this Op, memoized. Children are hashed first
        (bottom-up construction guarantees they are already memoized)."""
        if self._cached_struct_hash is None:
            self._cached_struct_hash = hash((self.op, tuple(a._struct_hash() for a in self.args)))
        return self._cached_struct_hash
    def __repr__(self) -> str:
        return f"Op({self.op}, [{', '.join(repr(a) for a in self.args)}])"
    def __eq__(self, other):
        if self is other:
            return True                       # identity fast-path
        if not isinstance(other, Op):
            return False
        if self._struct_hash() != other._struct_hash():   # hash short-circuit
            return False
        return self.op == other.op and self.args == other.args
    def __hash__(self):
        return self._struct_hash()
