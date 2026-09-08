"""
diagnose_rotations_5.py — the test diagnose_rotations_2.py was meant to run, fixed.

diagnose_rotations_4.py proved rotate_N IS structurally reachable: 12/43 benchmarks have a
vectorize-rotation match site whose predicted offset (= matched Vec width) is in {4,8,9,16} --
i.e. actually has a rotate_* rule. diagnose_rotations_2.py's bug was stopping at the FIRST
vectorize match it found, which happened to be an offset-1 site (no rule possible, atomic).

This script specifically seeks a match whose predicted offset is decomposable BEFORE applying
anything, using the same offset = len(matched_vec.args) fact from _4, then reproduces _2's exact
reward-table logic at that real post-vectorization state.

Run: conda activate chehabEnv && cd RL && python ../diagnose_rotations_5.py
"""
import sys, os
sys.path.insert(0, os.getcwd())

from fhe_rl.utils import create_rules, load_expressions
from fhe_rl.pareto import generate_pref_list
from pytrs import parse_sexpr, calculate_cost, expr_to_str

def split_costs(expr):
    ops = calculate_cost(expr, w_keys=0.0)
    keys = calculate_cost(expr, w_keys=1.0) - ops
    return ops, keys

def reward_vector(old_ops, new_ops, old_keys, new_keys, n_budget=5.0):
    r_ops = (old_ops - new_ops) / old_ops if old_ops != 0 else 0.0
    r_keys = (old_keys - new_keys) / n_budget
    return r_ops, r_keys

print("=" * 100)
pref_list = generate_pref_list(11)
print(f"[0] Training preferences: {pref_list}  ([0,1] present? {[0.0, 1.0] in pref_list})")

rules = create_rules(rules_path="rules.txt", rotations_rules_path="rotations_rules.txt")
rules["END"] = None
benchmarks = load_expressions("fhe_rl/datasets/benchmarks.txt")

vec_names = [n for n in rules if n and n.startswith("rot-") and "vectorize" in n and rules[n] is not None]
rot_names = [n for n in rules if n and n.startswith("rotate_")]
expected_offsets = {int(n.split("_")[1]) for n in rot_names}

# --- [1] find a match site whose predicted offset is decomposable, BEFORE applying anything ---
target = None  # (expr_str, rule_name, path, predicted_offset)
for bi, expr_str in enumerate(benchmarks):
    tree = parse_sexpr(expr_str)
    for rname in vec_names:
        robj = rules[rname]
        matches = robj.find_matching_subexpressions(tree)
        for (path, matched_vec) in matches:
            predicted_offset = len(matched_vec.args)
            if predicted_offset in expected_offsets:
                target = (bi, expr_str, rname, path, predicted_offset)
                break
        if target:
            break
    if target:
        break

if target is None:
    print("!! No decomposable match site found -- contradicts diagnose_rotations_4.py output, stop and report.")
    sys.exit(1)

bi, expr_str, rname, path, predicted_offset = target
print(f"\n[1] Picked benchmark #{bi}, rule={rname}, predicted offset={predicted_offset} (decomposable)")
print(f"    expr[:80] = {expr_str[:80]!r}")

tree = parse_sexpr(expr_str)
old_ops, old_keys = split_costs(tree)
robj = rules[rname]
new_tree = robj.apply_rule(tree, path=path)
vec_ops, vec_keys = split_costs(new_tree)
print(f"    ops  : {old_ops} -> {vec_ops}")
print(f"    keys : {old_keys} -> {vec_keys}")
print(f"    post-vectorize expr[:100] = {expr_to_str(new_tree)[:100]!r}")

# --- [2] enumerate rotate_* matches at this real, decomposable post-vectorization state ---
print(f"\n[2] Enumerating rotate_* matches at this state")
any_match = False
any_positive = False
for rname2 in rot_names:
    robj2 = rules[rname2]
    matches = robj2.find_matching_subexpressions(new_tree)
    if not matches:
        continue
    any_match = True
    for (path2, _) in matches[:3]:
        decomposed_tree = robj2.apply_rule(new_tree, path=path2)
        d_ops, d_keys = split_costs(decomposed_tree)
        r_ops, r_keys = reward_vector(vec_ops, d_ops, vec_keys, d_keys)
        print(f"\n  rule={rname2}  ops {vec_ops}->{d_ops}  keys {vec_keys}->{d_keys}"
              f"   r_vec=({r_ops:+.4f}, {r_keys:+.4f})")
        for w in pref_list:
            R = w[0] * r_ops + w[1] * r_keys
            flag = "<-- NEGATIVE" if R < 0 else ("zero" if R == 0 else "POSITIVE")
            if R > 0:
                any_positive = True
            print(f"      w={w}  R={R:+.4f}  {flag}")

if not any_match:
    print("!! Predicted offset said this should match but find_matching_subexpressions found nothing"
          " -- there's a second-order mismatch between the offset prediction and actual rule"
          " matching (e.g. structural pattern beyond just the Const value). Report this exact case back.")
else:
    print("\n" + "=" * 100)
    print("VERDICT:")
    if any_positive:
        print("  -> rotate_N CAN be rewarded (some w gives R>0) at a real, decomposable state.")
        print("     So it's structurally reachable AND sometimes reward-positive -- if PPO still")
        print("     never fires it in practice, the explanation is exploration/sample-efficiency")
        print("     (200k steps, only 12/43 benchmarks even offer this site, competing against ~90")
        print("     other rules), not a structural or reward-shaping dead end.")
    else:
        print("  -> Every reward is <=0 across all training preferences even at a genuinely")
        print("     decomposable site. This mechanically confirms hypothesis #2 from the handoff doc:")
        print("     rotate_N is reward-negative by construction under the shipped preference list,")
        print("     independent of reachability.")