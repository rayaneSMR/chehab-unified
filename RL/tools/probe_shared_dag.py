"""Task-5 probe: does structural Expr.__eq__ blow up on shared/DAG expressions?

1. Build a chain expression where the SAME subtree object is shared at k depth
   (this is what rot-*-vectorize / distributive rewrites produce: VecMul(d, <<(d,N))
   reuses d; applier substitution reuses bound subtrees).
2. Time:
   a. node == same_object           (Python first tries identity -> fast path?)
   b. node == structurally-equal-clone (deep walk; NO memo -> exponential if shared)
   c. _replace_expr on the shared tree (calls == at every node)
   d. validate_expression (deep recursion, no memo)
   e. expr_to_str (recursion, no memo)
3. Print a table so we can see exponential-vs-linear in chain depth.
"""
import os
import sys
import time

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
RL_DIR = os.path.dirname(TOOLS_DIR)            # one level up: RL/
if RL_DIR not in sys.path:
    sys.path.insert(0, RL_DIR)
PYTRS = os.path.join(RL_DIR, "pytrs")
if PYTRS not in sys.path:
    sys.path.insert(0, PYTRS)
os.chdir(RL_DIR)

from expr import Expr, Const, Var, Op  # noqa: E402
from rewrite_rule import RewriteRule, count_nodes, count_nodes_unrolled  # noqa: E402
from serializer import expr_to_str  # noqa: E402


def shared_chain(depth):
    """LINEAR shape: VecAdd(VecAdd(...v..), v) reusing leaf v.
    Unrolled grows linearly — NOT the hazard (kept for contrast)."""
    v = Op("Vec", [Var("x1"), Var("x2"), Var("x3"), Var("x4")])
    e = v
    for _ in range(depth):
        e = Op("VecAdd", [e, v])          # v shared at every level
    return e


def doubling_chain(depth):
    """EXPONENTIAL shape: e = f(e, e) — the SAME object on both sides.

    This mirrors what wrapper-rewrites in _apply_via_path produce
    (companion contains args[0] -> _replace_expr inserts the same new_vec
    once per occurrence, doubling the rewritten child's contribution per
    wrapper level) and what _build_rhs makes when the RHS repeats a bound
    variable (distribute: ?a appears twice). Unique nodes grow linearly,
    unrolled size 2^depth."""
    e = Op("Vec", [Var("x1"), Var("x2"), Var("x3"), Var("x4")])
    for _ in range(depth):
        e = Op("VecAdd", [e, e])          # SELF-share: DAG, 2^d unrolled
    return e


def clone(e):
    """Structurally-equal deep copy (breaks sharing)."""
    if isinstance(e, Op):
        return Op(e.op, [clone(a) for a in e.args])
    return e


def timeit(fn, n=3):
    best = float("inf")
    out = None
    for _ in range(n):
        t0 = time.perf_counter()
        out = fn()
        best = min(best, time.perf_counter() - t0)
    return best, out


def run_table(title, builder, depths):
    print(f"\n=== {title} ===")
    print(f"{'depth':>5} {'uniq':>6} {'unroll':>8} | "
          f"{'==self':>9} {'==clone':>10} {'repl':>9} {'valid':>9} {'str':>9}")
    print("-" * 80)
    for depth in depths:
        e = builder(depth)
        c = clone(e)
        uniq, unroll = count_nodes(e), count_nodes_unrolled(e)

        t_eq_self, _ = timeit(lambda e=e: e == e)
        t_eq_clone, _ = timeit(lambda e=e, c=c: e == c, n=1)
        t_repl, _ = timeit(lambda e=e: RewriteRule._replace_expr(
            e, Var("x1"), Const(0)), n=1)
        t_val, _ = timeit(lambda e=e: e.validate_expression(), n=1)
        t_str, _ = timeit(lambda e=e: expr_to_str(e), n=1)
        print(f"{depth:>5} {uniq:>6} {unroll:>8} | "
              f"{t_eq_self:>9.4f} {t_eq_clone:>10.4f} {t_repl:>9.4f} "
              f"{t_val:>9.4f} {t_str:>9.4f}")


run_table("LINEAR shape (leaf shared): control", shared_chain,
          (4, 8, 12, 16, 20, 24))
run_table("EXPONENTIAL shape (e=f(e,e) DAG): the hazard", doubling_chain,
          (4, 6, 8, 10, 12, 14, 16, 18, 20))

print("\nRead: linear shape stays ~constant; exponential shape doubles per +1 "
      "depth in ==clone/repl/valid/str if unmemoized. ==self stays fast "
      "(identity path in list ==).")

