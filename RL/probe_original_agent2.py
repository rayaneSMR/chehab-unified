# probe_original_agent_v2.py — run from chehab-original-imed/RL
# Adds: pos_idx, exact matched subexpr, and per-step correctness check
import sys, importlib
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.common.monitor import Monitor
from fhe_rl.utils import load_expressions, load_embeddings_from_config, create_rules
from fhe_rl.env import fheEnv
from fhe_rl.policy_film_b import HierarchicalMaskablePolicyFiLMB
from pytrs.util import evaluate_expr, generate_random_assignments
from pytrs.parser import parse_sexpr

CHECKPOINT = "checkpoints/model_jobid_lagrangian_od_ov_film_b/rl_model_200000_steps.zip"
EXPR_FILE  = "/tmp/hamming8.txt"

expressions = load_expressions(EXPR_FILE)
rules_list  = create_rules("rules.txt", "rotations_rules.txt")
rules_list["END"] = None
embeddings_model, _ = load_embeddings_from_config()

env = DummyVecEnv([lambda: Monitor(fheEnv(rules_list, expressions, max_positions=16,
                                            embeddings_model=embeddings_model))])

sys.modules["fhe_rl_new"] = importlib.import_module("fhe_rl")
model = PPO(policy=HierarchicalMaskablePolicyFiLMB, env=env)
model = model.load(CHECKPOINT)

obs = env.reset()
fhe_env = env.envs[0].env
original_expr = fhe_env.initial_expression
print("ORIGINAL:", original_expr)

orig_tree = parse_sexpr(original_expr.split(":")[0].strip() if ":" in original_expr else original_expr)
assignments = generate_random_assignments(orig_tree)
orig_val = evaluate_expr(orig_tree, assignments)
print("original_val:", orig_val)

done = False
rule_names = list(rules_list.keys())
max_positions = 16
step_i = 0

while not done:
    # state BEFORE this action, for match inspection
    cur_expr_str = fhe_env.expression
    cur_tree = parse_sexpr(cur_expr_str)

    action, _ = model.predict(obs, deterministic=True)
    a = int(action[0])
    rule_name = rule_names[a // max_positions]
    pos_idx = a % max_positions

    if rule_name != "END":
        matches = rules_list[rule_name].find_matching_subexpressions(cur_tree)
        matched_sub = matches[pos_idx][1] if pos_idx < len(matches) else f"OUT_OF_RANGE (only {len(matches)} matches)"
        print(f"step {step_i}: rule={rule_name} pos={pos_idx}/{len(matches)-1} matched_subexpr={matched_sub}")
    else:
        print(f"step {step_i}: rule=END")

    obs, rewards, dones, infos = env.step(action)
    done = bool(dones[0])
    final_expr = infos[0]["expression"]

    if rule_name != "END":
        try:
            step_tree = parse_sexpr(final_expr)
            step_val = evaluate_expr(step_tree, assignments)
            print(f"  -> result: {final_expr}")
            print(f"  -> eval: {step_val}  (orig was {orig_val})")
        except Exception as e:
            print(f"  -> eval FAILED: {e}")
            print(f"  -> result was: {final_expr}")
    step_i += 1

print("\nFINAL:", final_expr)
final_tree = parse_sexpr(final_expr)
final_val = evaluate_expr(final_tree, assignments)
print("Original result:", orig_val)
print("Final result   :", final_val)
print("STILL CORRECT? ", orig_val == final_val)
