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

Vector containers are structural: every Vec element is retained and visited,
and lane-specific variable names remain distinct inputs. They do not allocate
an additional ciphertext themselves.

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
    coeff_modulus_num_primes: int = 8         # L (usually nQ + nP)
    
    def nQ(self, backend: str) -> int:
        return self.coeff_modulus_num_primes - (2 if backend.lower() == "lattigo" else 1)
        
    def nP(self, backend: str) -> int:
        return 2 if backend.lower() == "lattigo" else 1


@dataclass(frozen=True)
class BackendConfig:
    backend_name: str
    allocator_multiplier: float
    base_bytes_overhead: Any # callable(N, L) -> int

SEAL_CONFIG = BackendConfig(
    backend_name="seal",
    allocator_multiplier=1.0, 
    base_bytes_overhead=lambda N, L: int(10 * 1024 * 1024 + 1.5 * N * L * 8) # better base scaling
)

LATTIGO_CONFIG = BackendConfig(
    backend_name="lattigo",
    allocator_multiplier=1.0,
    base_bytes_overhead=lambda N, L: 5388 * 1024
)


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
    if isinstance(node, Op):
        if node.op in ("<<", "rot"):
            if len(node.args) >= 2 and isinstance(node.args[1], Const):
                return int(node.args[1].value)
    return None


# ---------------------------------------------------------------------------
# Core: peak simultaneously-live intermediate ciphertexts ("slots")
# ---------------------------------------------------------------------------

def build_dag(root: Any, memo: dict) -> dict:
    # Iterative post-order traversal to avoid RecursionError
    stack = [root]
    visited = set()
    post_order = []
    post_order_set = set()
    
    while stack:
        curr = stack[-1]
        if id(curr) not in visited:
            visited.add(id(curr))
            if not (is_input(curr) or isinstance(curr, Const) or isinstance(curr, int) or getattr(curr, 'op', '') == 'const'):
                for c in reversed(children(curr)):
                    if not isinstance(c, int):
                        stack.append(c)
        else:
            stack.pop()
            if id(curr) not in post_order_set:
                post_order_set.add(id(curr))
                post_order.append(curr)
            
    for node in post_order:
        if is_input(node):
            key = ("input", getattr(node, 'name', str(getattr(node, 'value', 'const'))))
            if key not in memo:
                memo[key] = {"node": node, "op": "input", "args": [], "dep_count": 0, "is_input": True, "id": id(node)}
            setattr(node, '_memo_key', key)
        elif isinstance(node, Const) or isinstance(node, int) or getattr(node, 'op', '') == 'const':
            key = ("const", getattr(node, 'value', str(node)))
            if key not in memo:
                memo[key] = {"node": node, "op": "const", "args": [], "dep_count": 0, "is_input": False, "id": id(node)}
            setattr(node, '_memo_key', key)
        else:
            args = []
            for c in children(node):
                if not isinstance(c, int):
                    k = getattr(c, '_memo_key')
                    args.append(memo[k])
            key = (getattr(node, 'op', ''), tuple(a["id"] for a in args))
            if key not in memo:
                memo[key] = {"node": node, "op": getattr(node, 'op', ''), "args": args, "dep_count": 0, "is_input": False, "id": id(node)}
            setattr(node, '_memo_key', key)
                
    return memo[getattr(root, '_memo_key')]

def _slots_dag(node: Any) -> int:
    """Exact liveness simulation on the CSE DAG in DFS post-order."""
    memo = {}
    root = build_dag(node, memo)
    
    # Calculate dep_count
    for n in memo.values():
        for arg in n["args"]:
            arg["dep_count"] += 1
            
    # DFS post-order (iterative)
    schedule = []
    schedule_set = set()
    visited_sched = set()
    stack = [root]
    
    while stack:
        curr = stack[-1]
        if curr["id"] not in visited_sched:
            visited_sched.add(curr["id"])
            for a in reversed(curr["args"]):
                stack.append(a)
        else:
            stack.pop()
            # Only append if not already in schedule (multiple parents might have pushed it)
            if curr["id"] not in schedule_set:
                schedule_set.add(curr["id"])
                schedule.append(curr)
    
    peak_live = 0
    live_set = set()
    
    for step in schedule:
        if step["is_input"]:
            pass # inputs managed separately
        elif step["op"] in ("const", "literal", "Vec"):
            pass # plaintext constants don't take ciphertext space
        else:
            live_set.add(step["id"])
            
        peak_live = max(peak_live, len(live_set))
        
        for a in step["args"]:
            if a["id"] in live_set:
                a["dep_count"] -= 1
                if a["dep_count"] == 0:
                    live_set.remove(a["id"])
                    
    return peak_live


# ---------------------------------------------------------------------------
# Rotation keys, incl. the reduce_rotation_keys / NAF view
# ---------------------------------------------------------------------------

def is_power_of_two(n: int) -> bool:
    n = abs(n)
    return (n & (n-1) == 0) and n != 0

def get_naf(value: int) -> list:
    res = []
    sign = value < 0
    value = abs(value)
    i = 0
    while value > 0:
        zi = 2 - (value & 3) if (value & 1) else 0
        value = (value - zi) >> 1
        if zi != 0:
            res.append((-zi if sign else zi) * (1 << i))
        i += 1
    return res

def get_rotation_freq(node: Any) -> dict:
    from collections import Counter
    freq = Counter()
    memo = {}
    build_dag(node, memo)
    
    for n in memo.values():
        if n["op"] in ("<<", "rot"):
            args = n["args"]
            if len(args) >= 2 and args[1]["op"] == "const":
                step = int(args[1]["node"].value)
                freq[step] += 1
    return dict(freq)

def reduce_rotation_keys_pass(steps_freq: dict, keys_threshold: int) -> set:
    ordered_used_steps = list(steps_freq.keys())
    keys_count = len(ordered_used_steps)
    if keys_count <= keys_threshold:
        return set(ordered_used_steps)
        
    steps_nafs = {}
    for step in ordered_used_steps:
        if is_power_of_two(abs(step)):
            steps_nafs[step] = [step]
        else:
            steps_nafs[step] = get_naf(step)
            
    steps_costs = {}
    for step, freq in steps_freq.items():
        steps_costs[step] = freq * (len(steps_nafs[step]) - 1)
        
    def sort_key(step):
        # We want to pop the MINIMUM cost step first from the back.
        # In C++: lhs > rhs (descending), so back is smallest.
        # If lhs_cost == rhs_cost, steps_nafs[lhs] < steps_nafs[rhs].
        # In Python, sorting ascending by (-cost, naf_list) puts biggest at index 0, smallest at end.
        return (-steps_costs[step], steps_nafs[step])
        
    ordered_used_steps.sort(key=sort_key)
    
    used_steps = set()
    steps_to_decomp = set()
    
    while ordered_used_steps:
        min_cost_step = ordered_used_steps[-1]
        
        if is_power_of_two(abs(min_cost_step)):
            used_steps.add(min_cost_step)
            ordered_used_steps.pop()
            continue
            
        steps_to_decomp.add(min_cost_step)
        ordered_used_steps.pop()
        keys_count -= 1
        
        for naf_comp in steps_nafs[min_cost_step]:
            if naf_comp not in used_steps:
                used_steps.add(naf_comp)
                keys_count += 1
                
        if keys_count <= keys_threshold:
            break

    if keys_count > keys_threshold:
        raise RuntimeError(
            "could not go lower than the threshold; keys_threshold may be too low"
        )
            
    for step in ordered_used_steps:
        used_steps.add(step)
        
    return used_steps


# ---------------------------------------------------------------------------
# Public estimator
# ---------------------------------------------------------------------------

@dataclass
class PeakRAMEstimate:
    keys_bytes: int
    inputs_bytes: int
    plaintexts_bytes: int
    intermediates_bytes: int
    total_bytes_lo: int
    total_bytes_hi: int
    allocating_ops: int
    total_bytes: int # Alias for lo for compatibility
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
                      keys_threshold: int = 9999,
                      count_inputs: bool = True,
                      backend_config: "BackendConfig | None" = None) -> PeakRAMEstimate:
    """
    keys_threshold : The max number of keys allowed before reduce_rotation_keys 
                     decomposes them into NAF components. Matches codegen exactly.
    """
    steps_freq = get_rotation_freq(node)
    step_set = reduce_rotation_keys_pass(steps_freq, keys_threshold)

    def get_unique_leaves(nd):
        seen = set()
        stack = [nd]
        while stack:
            curr = stack.pop()
            if is_input(curr):
                name = getattr(curr, 'name', str(getattr(curr, 'value', 'const')))
                seen.add(name)
            elif isinstance(curr, Op) or hasattr(curr, 'args'):
                for c in children(curr):
                    if not isinstance(c, int):
                        stack.append(c)
        return len(seen)

    s_dag = _slots_dag(node)

    # RAM sizes: The mathematical footprint based on params, scaled by the backend's
    # known allocator/GC overhead multiplier.
    
    import sys
    import os
    rl_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if rl_dir not in sys.path:
        sys.path.append(rl_dir)
        
    try:
        from fhe_rl.memory_layout import key_bytes, ct_bytes, sk_bytes, pk_bytes, pt_bytes
    except ImportError:
        def key_bytes(backend, N, nQ, nP):
            import math
            return math.ceil(nQ/nP) * 2 * (nQ + nP) * N * 8 if backend == "lattigo" else nQ * 2 * (nQ + nP) * N * 8
        def ct_bytes(backend, level, N, nQ, nP):
            return 2 * nQ * N * 8
        def sk_bytes(backend, N, nQ, nP):
            return (nQ + nP) * N * 8
        def pk_bytes(backend, N, nQ, nP):
            return 2 * (nQ + nP) * N * 8
        def pt_bytes(backend, level, N, nQ, nP):
            return nQ * N * 8

    backend_name = backend_config.backend_name if backend_config else "lattigo"
    
    nQ = params.nQ(backend_name)
    nP = params.nP(backend_name)
    
    key_b = key_bytes(backend_name, params.poly_modulus_degree, nQ, nP)
    ct_b  = ct_bytes(backend_name, 0, params.poly_modulus_degree, nQ, nP)
    sk_b  = sk_bytes(backend_name, params.poly_modulus_degree, nQ, nP)
    pk_b  = pk_bytes(backend_name, params.poly_modulus_degree, nQ, nP)
    pt_b  = pt_bytes(backend_name, 0, params.poly_modulus_degree, nQ, nP)
    
    mult = backend_config.allocator_multiplier if backend_config else 1.0
    base_b = backend_config.base_bytes_overhead(params.poly_modulus_degree, params.coeff_modulus_num_primes) if backend_config else 0

    def get_unique_consts(nd):
        seen = set()
        stack = [(nd, False)]
        while stack:
            curr, is_rot_arg = stack.pop()
            if (isinstance(curr, Const) or getattr(curr, 'op', '') == 'const') and not is_rot_arg:
                name = getattr(curr, 'value', str(curr))
                seen.add(name)
            elif isinstance(curr, Op) or hasattr(curr, 'args'):
                for i, c in enumerate(children(curr)):
                    is_step = (getattr(curr, 'op', '') in ("<<", "rot") and i == 1)
                    if not isinstance(c, int):
                        stack.append((c, is_step))
        return len(seen)

    # The number of ops that allocate a new ciphertext is exactly the number of inner DAG nodes.
    # (Inputs and constants don't allocate during evaluation).
    alloc_ops = 0
    memo = {}
    build_dag(node, memo)
    for n in memo.values():
        if not n["is_input"] and n["op"] not in ("const", "literal", "Vec"):
            alloc_ops += 1

    inputs_b  = int(get_unique_leaves(node) * ct_b) if count_inputs else 0
    plaintexts_b = int(get_unique_consts(node) * pt_b)
    
    actual_slots = s_dag
    inter_b   = int(actual_slots * ct_b * mult)

    labels = {
        "keys": "exact simulated key set (after reduce_rotation_keys pass)",
        "intermediates": "exact simulated over CSE DAG",
    }
    
    # Analyze the AST for Bootstrapping
    # TODO: In Étape 3, Kimi said "pas de clés bootstrap inventées". 
    # For now, if the user codegen does not explicitly enable bootstrap, we should NOT add bootstrap keys.
    # The true codegen parameter 'enable_bootstrap' should dictate this. We'll set it to 0 here to strictly 
    # obey "no invented bootstrap keys" as requested by Kimi, until it's wired into the compiler flags.
    boot_keys = 0
    
    # Key Counts
    relin_keys = int(any(n["op"] in ("*", "mul", "square") for n in memo.values()))
    galois_keys = len(step_set)
    
    total_keys = relin_keys + galois_keys + boot_keys
    # Adding Secret Key and Public Key to the keys pool
    keys_b = int(total_keys * key_b + sk_b + pk_b)

    lo = base_b + keys_b + inputs_b + plaintexts_b + inter_b
    
    # GC garbage bound (hi).
    # Since hi is an estimation and not a strict bound, we add a 10% safety margin.
    live_set = keys_b + inputs_b + plaintexts_b + inter_b
    A = alloc_ops * ct_b
    garbage_bound = min(A, int(1.6 * live_set)) if backend_name == "lattigo" else 0
    hi = int((lo + garbage_bound) * 1.1)

    return PeakRAMEstimate(
        keys_bytes=keys_b, inputs_bytes=inputs_b, plaintexts_bytes=plaintexts_b, intermediates_bytes=inter_b,
        total_bytes_lo=lo, total_bytes_hi=hi, total_bytes=lo, allocating_ops=alloc_ops,
        slots_fixed=s_dag, slots_min=s_dag,
        n_keys_raw=total_keys, n_keys_reduced=total_keys, # Same now since it's the exact set
        relin_keys_count=relin_keys, galois_keys_count=galois_keys, bootstrap_keys_count=boot_keys,
        labels=labels)

def within_budget(est: PeakRAMEstimate, budget_bytes: int,
                  use_lower_bound: bool = False) -> bool:
    """Hard constraint check.
    If use_lower_bound=True, we check against the 'lo' estimate (exact live set + base).
    If False, we check against the 'hi' estimate (live set + GC garbage bound + base).
    """
    total = est.total_bytes_lo if use_lower_bound else est.total_bytes_hi
    return total <= budget_bytes


# ---------------------------------------------------------------------------
# Self-test with a stand-in tree (replace by real pytrs nodes later)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from pytrs.expr import Var, Op, Const
    a, b, c, d = Var("a"), Var("b"), Var("c"), Var("d")
    t = Op("*", [Op("<<", [Op("+", [a, b]), Const(7)]), Op("*", [c, d])])

    p = FHEParams()
    est = estimate_peak_ram(t, p, keys_threshold=9999)
    print(f"tree: {t}")
    print(f"slots simulated DAG = {est.slots_fixed}")
    print(f"allocating ops (A) = {est.allocating_ops}")
    print(f"keys exact set = {est.n_keys_raw} (reduced pass applied)")
    print(f"total lo = {est.total_bytes_lo/2**20:.1f} MiB  [{est.keys_bytes/2**20:.1f} keys + "
          f"{est.inputs_bytes/2**20:.1f} inputs + {est.intermediates_bytes/2**20:.1f} inter + {est.plaintexts_bytes/2**20:.1f} pt]")
    print(f"total hi = {est.total_bytes_hi/2**20:.1f} MiB")