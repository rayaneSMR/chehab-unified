"""Episode-growth probe (task 5): does expression size balloon over an episode?

Runs fheEnvUnified for a few steps per episode (same shape as the RL training
loop) and prints, per episode, the max expression length and max unique node
count seen, so you can see whether rot-*-vectorize / distributive rules balloon
the tree against the (unenforced) max_expression_size=10000.
"""
import os
import sys

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
RL_DIR = os.path.dirname(TOOLS_DIR)            # one level up: RL/
if RL_DIR not in __import__("sys").path:
    __import__("sys").path.insert(0, RL_DIR)
PYTRS = os.path.join(RL_DIR, "pytrs")
if PYTRS not in __import__("sys").path:
    __import__("sys").path.insert(0, PYTRS)
os.chdir(RL_DIR)

from pytrs import create_rules, parse_sexpr  # noqa: E402
from fhe_rl.env_unified import fheEnvUnified  # noqa: E402


def node_counts(expr):
    from pytrs.rewrite_rule import count_nodes, count_nodes_unrolled
    return count_nodes(parse_sexpr(expr)), count_nodes_unrolled(parse_sexpr(expr))


def main():
    for ep in range(2):
        env = fheEnvUnified(
            create_rules("rules.txt", "rotations_rules.txt"),
            ["(VecAdd (VecMul v1_0 v2_0) (* v1_1 v2_1))"],
            max_positions=16, budget_options=[1500, 2000, 2600, 1000000],
            constraint_metric="mem", verbose=False)
        obs, _ = env.reset(seed=42)
        maxn = maxu = maxl = 0
        for step in range(30):
            valid = [int(a) for a in __import__("numpy").where(obs["action_mask"] == 1)[0]]
            if not valid:
                break
            obs, _r, term, trunc, _info = env.step(valid[0])
            maxl = max(maxl, len(env.expression))
            try:
                n_u, n_uu = node_counts(env.expression)
                maxn = max(maxn, n_u)
                maxu = max(maxu, n_uu)
            except Exception:
                pass
        print(f"episode {ep}: steps={step+1} final_len={len(env.expression)} "
              f"max_nodes(uniq)={maxn} max_unrolled={maxu} "
              f"final_expr[:90]={env.expression[:90]}")
        print(f"   [diag] episode={ep+1} finished steps={step+1} "
              f"max_nodes={maxn} final_nodes={node_counts(env.expression)[0]} "
              f"expr_len={len(env.expression)}")
        del env

    print("\nepisode-growth probe done: report max node count per episode "
          "from the [diag] lines above.")


if __name__ == "__main__":
    main()
