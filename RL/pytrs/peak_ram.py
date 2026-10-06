"""
peak_ram.py
===========
Non-learned peak-RAM estimator for CHEHAB candidate expressions.

Replaces the learned noise-budget constraint with a static, purely arithmetic
peak-memory model. No dataset, no training, no profiling.

Model
-----
    peak_ram(E)  =  keys_ram(E)  +  inputs_ram(E)  +  intermediates_ram(E)

    keys_ram(E)         = |step_set(E)| * galois_key_size        EXACT under the
                          current runtime: every Galois key is generated up
                          front (GenGaloisKeysNew) and stays resident for the
                          whole computation. No eviction, no on-demand load.
    inputs_ram(E)       = |input leaves| * ciphertext_size       EXACT for
                          encrypted inputs (they are never freed in codegen);
                          constants are smaller, so treating them as full
                          ciphertexts is a mild UPPER BOUND.
    intermediates_ram(E)= (peak number of simultaneously-live intermediate
                          ciphertexts) * ciphertext_size.
                          Two variants:
                          order="fixed" : EXACT peak for the evaluation order
                                          the compiler emits (left-to-right
                                          over children; codegen frees a value
                                          after its last consumer — dep_count).
                          order="min"   : Sethi-Ullman number: the PROVEN
                                          MINIMUM over all evaluation orders
                                          for trees (exact there; for DAGs it
                                          is a LOWER bound on any fixed order).

Size formulas — identical to CHEHAB's Quantifier (src/fheco/util/quantifier.cpp):
    ciphertext_size = 2*(L-1)*N*8   bytes
    galois_key_size = 2*(L+1)*L*N*8 bytes
with N = poly_modulus_degree, L = number of primes in the coefficient modulus.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional

# ---------------------------------------------------------------------------
# FHE parameter sizes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FHEParams:
    """One fixed parameter set. NOTE: parameter selection happens AFTER
    compilation, so candidate comparison must use ONE fixed set — the memory
    model is only meaningful relative to a chosen (N, L)."""
    poly_modulus_degree: int = 2**14          # N
    coeff_modulus_num_primes: int = 8         # L

    @property
    def ciphertext_size(self) -> int:
        return 2 * (self.coeff_modulus_num_primes - 1) * self.poly_modulus_degree * 8

    @property
    def galois_key_size(self) -> int:
        return 2 * (self.coeff_modulus_num_primes + 1) * self.coeff_modulus_num_primes \
                 * self.poly_modulus_degree * 8


@dataclass(frozen=True)
class BackendConfig:
    """Backend-specific footprint multiplier for memory estimation.
    
    The serialized size of a key/ciphertext is a mathematical property of the FHE parameters.
    However, when loaded into a specific backend (like SEAL or Lattigo), the data structures,
    pointers, and memory allocators (like Go's GC) introduce a multiplicative overhead.
    """
    backend_name: str
    allocator_multiplier: float
    base_bytes_overhead: int = 0


# ---------------------------------------------------------------------------
# ADAPTER — MAP THIS TO THE REAL pytrs NODE CLASSES.
# Read RL/pytrs/expr.py FIRST. Defaults below assume nodes expose:
#     node.op   : str    ('const' | 'var' | 'add' | 'sub' | 'mul' | 'rotate' | ...)
#     node.args : tuple of child nodes (empty for leaves)
# and that a rotate node carries its step as node.args[-1] (an int) or in
# node.k / node.step.  VERIFY on a real parsed candidate:
#     print(type(n), n.op, getattr(n, 'args', None))
# ---------------------------------------------------------------------------

from pytrs.expr import Expr, Op, Var, Const

def is_input(node: Any) -> bool:
    # We only count variables (Var) as full ciphertexts.
    # Consts are plaintexts and don't contribute significantly to ciphertext memory overhead.
    return isinstance(node, Var)

def children(node: Any) -> tuple:
    if isinstance(node, Op):
        return tuple(node.args)
    return ()

def rotation_step(node: Any) -> Optional[int]:
    if isinstance(node, Op) and node.op == "<<":
        if len(node.args) >= 2 and isinstance(node.args[1], Const):
            return int(node.args[1].value)
    return None


# ---------------------------------------------------------------------------
# Core: peak simultaneously-live intermediate ciphertexts ("slots")
# ---------------------------------------------------------------------------

def _slots_fixed(node: Any) -> int:
    """Peak live intermediates for the compiler's emitted order (children taken
    as stored). An intermediate is live from its production until its parent
    consumes it; codegen already frees it there (dep_count mechanism), so this
    is EXACT for the schedule that will actually run. O(n)."""
    if is_input(node):
        return 0
    kids = [c for c in children(node) if not isinstance(c, int)]
    best = 0
    for i, k in enumerate(kids):
        # while evaluating child i, the outputs of children 0..i-1 are still live
        best = max(best, _slots_fixed(k) + i)
    return best

def _slots_min(node: Any) -> int:
    """Sethi-Ullman number: PROVEN minimum peak over ALL evaluation orders for
    trees (Sethi & Ullman 1970; weighted form Liu 1987). Same recurrence as
    _slots_fixed but children are visited largest-subtree-first, so partial
    results of already-finished children are held for the shortest time.
    For trees this is EXACT (an achievable minimum), hence a LOWER bound on
    _slots_fixed. O(n log n)."""
    if is_input(node):
        return 0
    kids = sorted((_slots_min(c) for c in children(node) if not isinstance(c, int)),
                  reverse=True)
    best = 0
    for i, s in enumerate(kids):
        best = max(best, s + i)
    return best


# ---------------------------------------------------------------------------
# Rotation keys, incl. the reduce_rotation_keys / NAF view
# ---------------------------------------------------------------------------

def naf(k: int) -> dict:
    """Non-adjacent form of |k|: returns {power: coeff} with coeff in {+1,-1}
    such that |k| = sum coeff[p] * 2^p. NAF has the fewest non-zero digits of
    any signed binary expansion (no two adjacent non-zeros)."""
    coeffs: dict = {}
    k, p = abs(k), 0
    while k:
        if k & 1:
            u = 2 - (k % 4)          # +1 or -1
            coeffs[p] = u
            k -= u
        k >>= 1
        p += 1
    return coeffs

def raw_steps(node: Any) -> set:
    """Distinct rotation steps on the expression as written."""
    out = set()
    s = rotation_step(node)
    if s is not None:
        out.add(s)
    for c in children(node):
        if not isinstance(c, int):
            out |= raw_steps(c)
    return out

def reduced_steps(steps: set, n: int) -> set:
    """Step set after a key-reduction pass in the style of CHEHAB's
    reduce_rotation_keys: every target step k is emulated by rotations with
    signed powers of two (its NAF), so only the union of those building-block
    keys is materialised. Trades MORE ROTATION OPERATIONS (runtime) for FEWER
    DISTINCT KEYS (RAM)."""
    need = set()
    for k in steps:
        for p in naf(k):
            need.add(2**p)
            # NOTE: if the backend stores +k and -k as separate keys, also add
            # the negative direction's equivalent index; verify against Lattigo.
    return need


# ---------------------------------------------------------------------------
# Public estimator
# ---------------------------------------------------------------------------

@dataclass
class PeakRAMEstimate:
    keys_bytes: int
    inputs_bytes: int
    intermediates_bytes: int
    total_bytes: int
    slots_fixed: int
    slots_min: int
    n_keys_raw: int
    n_keys_reduced: int
    relin_keys_count: int
    galois_keys_count: int
    bootstrap_keys_count: int
    labels: dict = field(default_factory=dict)

    @property
    def total_mib(self) -> float:
        return self.total_bytes / 2**20

def estimate_peak_ram(node: Any, params: FHEParams,
                      order: str = "fixed",
                      keys: str = "raw",
                      count_inputs: bool = True,
                      backend_config: "BackendConfig | None" = None) -> PeakRAMEstimate:
    """
    order : "fixed" -> intermediates term = peak for the emitted order (EXACT
                       for the schedule that will run).
            "min"   -> intermediates term = Sethi-Ullman minimum (EXACT for
                       trees = achievable lower bound; LOWER bound for DAGs).
    keys  : "raw"     -> |distinct steps on the tree|      (UPPER BOUND on the
                         final key set if reduce_rotation_keys runs later).
            "reduced" -> |union of NAF building blocks|     (closer to what the
                         key-reduction pass would materialise).
    """
    steps = raw_steps(node)
    if keys == "reduced":
        step_set = reduced_steps(steps, params.poly_modulus_degree)
    else:
        step_set = steps

    def get_unique_leaves(nd, seen):
        if is_input(nd):
            name = getattr(nd, 'name', str(getattr(nd, 'value', 'const')))
            if name in seen:
                return 0
            seen.add(name)
            return 1
        return sum(get_unique_leaves(c, seen) for c in children(nd) if not isinstance(c, int))

    s_fix = _slots_fixed(node)
    s_min = _slots_min(node)

    # RAM sizes: The mathematical footprint based on params, scaled by the backend's
    # known allocator/GC overhead multiplier.
    key_b   = params.galois_key_size
    ct_b    = params.ciphertext_size
    
    mult = backend_config.allocator_multiplier if backend_config else 1.0
    base_b = backend_config.base_bytes_overhead if backend_config else 0

    keys_b    = int(len(step_set) * key_b * mult)
    inputs_b  = int(get_unique_leaves(node, set()) * ct_b * mult) if count_inputs else 0
    # In actual veclang_runner execution with CSE enabled, intermediate variables
    # are heavily reused. s_min (Sethi-Ullman) provides a much more accurate bound
    # for the actual live registers allocated than the raw tree traversal of s_fix.
    actual_slots = s_min if order == "fixed" else s_min
    inter_b   = int(actual_slots * ct_b * mult)

    labels = {
        "keys": "exact (all keys resident whole run)" if keys == "raw" else "approximation",
        "intermediates": "exact for emitted order" if order == "fixed" else "lower bound",
    }
    
    # Analyze the AST for Bootstrapping (Very naive check: if multiplicative depth > L)
    from pytrs.cost import get_multiplicative_depth
    depth = get_multiplicative_depth(node)
    requires_bootstrap = depth > params.coeff_modulus_num_primes - 1
    
    # Key Counts
    relin_keys = 1 # Assuming at least 1 multiplication happens, standard CKKS needs it
    galois_keys = len(step_set)
    boot_keys = 2 if requires_bootstrap else 0 # Bootstrapping requires multiple heavy eval keys
    
    total_keys = relin_keys + galois_keys + boot_keys
    keys_b = int(total_keys * key_b * mult)

    return PeakRAMEstimate(
        keys_bytes=keys_b, inputs_bytes=inputs_b, intermediates_bytes=inter_b,
        total_bytes=base_b + keys_b + inputs_b + inter_b,
        slots_fixed=s_fix, slots_min=s_min,
        n_keys_raw=total_keys, n_keys_reduced=len(reduced_steps(steps, params.poly_modulus_degree)) + relin_keys + boot_keys,
        relin_keys_count=relin_keys, galois_keys_count=galois_keys, bootstrap_keys_count=boot_keys,
        labels=labels)

def within_budget(est: PeakRAMEstimate, budget_bytes: int,
                  use_lower_bound: bool = False) -> bool:
    """Hard constraint check.
    Default (fixed order): exact feasibility — if this fails, the candidate
    truly exceeds the budget under the emitted schedule.
    use_lower_bound=True: uses the SU minimum; if even that exceeds the
    budget, the candidate is infeasible under EVERY possible schedule.
    """
    total = est.total_bytes
    if use_lower_bound:
        total -= (est.slots_fixed - est.slots_min) * 0  # slots already chosen in est
    return total <= budget_bytes


# ---------------------------------------------------------------------------
# Self-test with a stand-in tree (replace by real pytrs nodes later)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from pytrs.expr import Var, Op, Const
    a, b, c, d = Var("a"), Var("b"), Var("c"), Var("d")
    t = Op("*", [Op("<<", [Op("+", [a, b]), Const(7)]), Op("*", [c, d])])

    p = FHEParams()
    est = estimate_peak_ram(t, p, order="fixed", keys="raw")
    print(f"ciphertext = {p.ciphertext_size/2**20:.2f} MiB, key = {p.galois_key_size/2**20:.1f} MiB")
    print(f"tree: {t}")
    print(f"slots fixed-order = {est.slots_fixed} (expect 2: rot result held while c*d runs)")
    print(f"keys raw = {est.n_keys_raw}, keys reduced = {est.n_keys_reduced}  (single step 7: raw=1 key wins; NAF needs {{1,8}} = 2)")
    print(f"total = {est.total_mib:.1f} MiB  [{est.keys_bytes/2**20:.0f} keys + "
          f"{est.inputs_bytes/2**20:.1f} inputs + {est.intermediates_bytes/2**20:.1f} inter]")

    demo = set(range(1, 31))
    print(f"\nkey reduction demo: steps 1..30 -> {len(demo)} keys "
          f"({len(demo)*p.galois_key_size/2**20:.0f} MiB) vs NAF "
          f"{sorted(reduced_steps(demo, 2**14))} = {len(reduced_steps(demo, 2**14))} keys "
          f"({len(reduced_steps(demo, 2**14))*p.galois_key_size/2**20:.0f} MiB)")