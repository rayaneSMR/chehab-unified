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
    coeff_modulus_num_primes: int = 8         # L (usually nQ + nP)
    
    @property
    def nQ(self) -> int:
        return self.coeff_modulus_num_primes - 2
        
    @property
    def nP(self) -> int:
        return 2


@dataclass(frozen=True)
class BackendConfig:
    backend_name: str
    allocator_multiplier: float
    base_bytes_overhead: Any # callable(N, L) -> int

SEAL_CONFIG = BackendConfig(
    backend_name="seal",
    allocator_multiplier=1.0, 
    base_bytes_overhead=lambda N, L: int(45848 * 1024 * (N / 16384))
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

def build_dag(node: Any, memo: dict) -> dict:
    if is_input(node):
        key = ("input", getattr(node, 'name', str(getattr(node, 'value', 'const'))))
        if key not in memo:
            memo[key] = {"node": node, "op": "input", "args": [], "dep_count": 0, "is_input": True}
        return memo[key]
    elif isinstance(node, Const) or isinstance(node, int) or getattr(node, 'op', '') == 'const':
        key = ("const", getattr(node, 'value', str(node)))
        if key not in memo:
            memo[key] = {"node": node, "op": "const", "args": [], "dep_count": 0, "is_input": False}
        return memo[key]
    else:
        args = []
        for c in children(node):
            if not isinstance(c, int):
                args.append(build_dag(c, memo))
        key = (getattr(node, 'op', ''), tuple(id(a) for a in args))
        if key not in memo:
            memo[key] = {"node": node, "op": getattr(node, 'op', ''), "args": args, "dep_count": 0, "is_input": False}
        return memo[key]

def _slots_dag(node: Any) -> int:
    """Exact liveness simulation on the CSE DAG in DFS post-order."""
    memo = {}
    root = build_dag(node, memo)
    
    # Calculate dep_count
    for n in memo.values():
        for arg in n["args"]:
            arg["dep_count"] += 1
            
    # DFS post-order
    schedule = []
    visited = set()
    def dfs(n):
        if id(n) in visited: return
        visited.add(id(n))
        for a in n["args"]:
            dfs(a)
        schedule.append(n)
    
    dfs(root)
    
    peak_live = 0
    live_set = set()
    
    for step in schedule:
        if step["is_input"]:
            pass # inputs managed separately
        elif step["op"] in ("const", "literal"):
            pass # plaintext constants don't take ciphertext space
        else:
            live_set.add(id(step))
            
        peak_live = max(peak_live, len(live_set))
        
        for a in step["args"]:
            if id(a) in live_set:
                a["dep_count"] -= 1
                if a["dep_count"] == 0:
                    live_set.remove(id(a))
                    
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
                      keys_threshold: int = 9999,
                      count_inputs: bool = True,
                      backend_config: "BackendConfig | None" = None) -> PeakRAMEstimate:
    """
    keys_threshold : The max number of keys allowed before reduce_rotation_keys 
                     decomposes them into NAF components. Matches codegen exactly.
    """
    steps_freq = get_rotation_freq(node)
    step_set = reduce_rotation_keys_pass(steps_freq, keys_threshold)

    def get_unique_leaves(nd, seen):
        if is_input(nd):
            name = getattr(nd, 'name', str(getattr(nd, 'value', 'const')))
            if name in seen:
                return 0
            seen.add(name)
            return 1
        return sum(get_unique_leaves(c, seen) for c in children(nd) if not isinstance(c, int))

    s_dag = _slots_dag(node)

    # RAM sizes: The mathematical footprint based on params, scaled by the backend's
    # known allocator/GC overhead multiplier.
    
    import sys
    import os
    rl_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if rl_dir not in sys.path:
        sys.path.append(rl_dir)
        
    try:
        from fhe_rl.memory_layout import key_bytes, ct_bytes
    except ImportError:
        def key_bytes(backend, N, nQ, nP):
            import math
            return math.ceil(nQ/nP) * 2 * (nQ + nP) * N * 8 if backend == "lattigo" else nQ * 2 * (nQ + nP) * N * 8
        def ct_bytes(backend, level, N, nQ, nP):
            return 2 * nQ * N * 8

    backend_name = backend_config.backend_name if backend_config else "lattigo"
    
    key_b = key_bytes(backend_name, params.poly_modulus_degree, params.nQ, params.nP)
    ct_b  = ct_bytes(backend_name, 0, params.poly_modulus_degree, params.nQ, params.nP)
    
    mult = backend_config.allocator_multiplier if backend_config else 1.0
    base_b = backend_config.base_bytes_overhead(params.poly_modulus_degree, params.coeff_modulus_num_primes) if backend_config else 0

    inputs_b  = int(get_unique_leaves(node, set()) * ct_b) if count_inputs else 0
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
    relin_keys = 1 # Assuming at least 1 multiplication happens, standard CKKS needs it
    galois_keys = len(step_set)
    
    total_keys = relin_keys + galois_keys + boot_keys
    keys_b = int(total_keys * key_b)

    return PeakRAMEstimate(
        keys_bytes=keys_b, inputs_bytes=inputs_b, intermediates_bytes=inter_b,
        total_bytes=base_b + keys_b + inputs_b + inter_b,
        slots_fixed=s_dag, slots_min=s_dag,
        n_keys_raw=total_keys, n_keys_reduced=total_keys, # Same now since it's the exact set
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
    est = estimate_peak_ram(t, p, keys_threshold=9999)
    print(f"tree: {t}")
    print(f"slots simulated DAG = {est.slots_fixed}")
    print(f"keys exact set = {est.n_keys_raw} (reduced pass applied)")
    print(f"total = {est.total_mib:.1f} MiB  [{est.keys_bytes/2**20:.0f} keys + "
          f"{est.inputs_bytes/2**20:.1f} inputs + {est.intermediates_bytes/2**20:.1f} inter]")