"""
diagnose_rotations.py - root-cause check for the "no rotations ever" issue.

Run from the RL/ directory, inside conda env chehabEnv:
    conda activate chehabEnv
    cd RL
    python diagnose_rotations.py

Checks, in order:
  0. CWD / file presence  (if rotations_rules.txt is not found here, THAT is the bug)
  1. rule loading         (are the 7 rotate_* rules in the action space?)
  2. action-mask coverage (do rotation rules ever have valid positions?)
  3. reward math          (what happens to ops / keys / reward when rotate_* fires?)
  4. random rollout       (which rules does a random policy actually apply?)
"""

import os
import sys
import numpy as np
from collections import Counter

print("CWD:", os.getcwd())
if not os.path.exists("rules.txt"):
    sys.exit("FATAL: rules.txt not found in CWD. Run this script from the RL/ directory.")
if not os.path.exists("rotations_rules.txt"):
    sys.exit("FATAL: rotations_rules.txt NOT FOUND in CWD. "
             "Rule file missing = rotation actions silently absent. THIS IS THE BUG.")

from pytrs import create_rules, parse_sexpr, calculate_cost
from fhe_rl.utils import load_expressions
from fhe_rl.env import fheEnv

# ---------------------------------------------------------------- check 1
rules = create_rules("rules.txt", "rotations_rules.txt")
rules["END"] = None
rot_names = [n for n in rules if n.startswith("rotate_")]
intro_names = [n for n in rules if n.startswith("rot-") and "vectorize" in n]
print("\n[1] RULE LOADING")
print(f"  total rules incl END        : {len(rules)}")
print(f"  rotate_* decomposition rules: {len(rot_names)} -> {rot_names}")
print(f"  rot-* vectorize (INTRODUCE rotations): {len(intro_names)} -> {intro_names}")

# ---------------------------------------------------------------- helpers
class DummyEmbedder:
    def get_embedding(self, expr_str):
        return np.zeros(256, dtype=np.float32)

def split_costs(expr_str):
    p = parse_sexpr(expr_str)
    ops = calculate_cost(p, w_keys=0.0)
    keys = calculate_cost(p, w_keys=1.0) - ops
    return ops, keys

def reward_delta(o_old, o_new, k_old, k_new, w, n_budget=5):
    r_ops = (o_old - o_new) / o_old if o_old else 0.0
    r_keys = (k_old - k_new) / n_budget
    return r_ops, r_keys, float(np.dot(np.array(w), np.array([r_ops, r_keys])))

# ---------------------------------------------------------------- check 2
print("\n[2] ACTION-MASK COVERAGE on first 3 benchmark expressions")
try:
    exprs = load_expressions("./fhe_rl/datasets/benchmarks.txt")
except Exception as e:
    sys.exit(f"could not load benchmarks: {e}")

for expr_str in exprs[:3]:
    parsed = parse_sexpr(expr_str)
    rot_hits, intro_hits = 0, 0
    for name in rot_names:
        rot_hits += len(rules[name].find_matching_subexpressions(parsed))
    for name in intro_names:
        intro_hits += len(rules[name].find_matching_subexpressions(parsed))
    o, k = split_costs(expr_str)
    print(f"  expr[:60]={expr_str[:60]!r} ops={o} keys={k} "
          f"| rotate_* matches={rot_hits} | rot-vectorize matches={intro_hits}")

# ---------------------------------------------------------------- check 3
print("\n[3] REWARD MATH - force a rotation chain by hand")
# find an expression where a rot-vectorize rule matches, apply it, then a rotate_*
demo_done = False
for expr_str in exprs:
    parsed = parse_sexpr(expr_str)
    for name in intro_names:
        r = rules[name]
        matches = r.find_matching_subexpressions(parsed)
        if not matches:
            continue
        k_path, _ = matches[0]
        vec_expr = str(r.apply_rule(parsed, path=k_path))
        o0, k0 = split_costs(expr_str)
        o1, k1 = split_costs(vec_expr)
        print(f"  rule {name} on expr[:50]={expr_str[:50]!r}")
        print(f"    after vectorize: ops {o0}->{o1}, keys {k0}->{k1}")
        # now try every rotate_* on the vectorized expr
        vparsed = parse_sexpr(vec_expr)
        for rname in rot_names:
            rr = rules[rname]
            m2 = rr.find_matching_subexpressions(vparsed)
            if not m2:
                continue
            p2, _ = m2[0]
            new_expr = str(rr.apply_rule(vparsed, path=p2))
            o2, k2 = split_costs(new_expr)
            for w in ([1.0, 0.0], [0.2, 0.8]):
                ro, rk, R = reward_delta(o1, o2, k1, k2, w)
                print(f"    then {rname}: ops {o1}->{o2}, keys {k1}->{k2} | "
                      f"w={w}: r_ops={ro:+.4f} r_keys={rk:+.4f} R={R:+.4f}")
        demo_done = True
        break
    if demo_done:
        break
if not demo_done:
    print("  (no rot-vectorize matches found in first benchmarks - try dnn_benchmarks.txt)")

# ---------------------------------------------------------------- check 4
print("\n[4] RANDOM ROLLOUT - 5 episodes x 75 steps, uniform over masked actions")
env = fheEnv(rules, exprs[:10], max_positions=16, embeddings_model=DummyEmbedder(),
             budget_options=[240, 300, 1_000_000], constraint_method="lagrangian_od_ov",
             pref_list=[[1.0, 0.0], [0.2, 0.8]], lambda_env=0.0, lambda_kl=0.0,
             n_cycle=1, n_budget=5, verbose=False)
env.set_preference_vector([0.2, 0.8])

rule_names = list(rules.keys())
fired = Counter()
max_keys = 0
for ep in range(5):
    obs, _ = env.reset()
    done = False
    while not done:
        mask = obs["action_mask"]
        valid = np.where(mask > 0)[0]
        if len(valid) == 0:
            break
        a = int(np.random.choice(valid))
        obs, r, term, trunc, info = env.step(a)
        fired[rule_names[a // 16]] += 1
        max_keys = max(max_keys, info["c_keys"])
        done = term or trunc

print(f"  max keys ever seen in any state: {max_keys}")
print(f"  rotate_* applications          : {sum(c for n, c in fired.items() if n.startswith('rotate_'))}")
print(f"  top 10 fired rules             : {fired.most_common(10)}")
print("\nVERDICT:")
print("  - If [1] shows 7 rotate_* rules and [2] shows matches>0 after vectorization,")
print("    the machinery works; the cause is reward/training (see handoff doc 4.2).")
print("  - If [2] shows rot-vectorize matches=0 on all exprs, vectorization never")
print("    starts; if [4] max_keys stays 0, no rotation is ever introduced.")