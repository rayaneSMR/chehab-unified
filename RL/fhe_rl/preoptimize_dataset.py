"""
Pre-optimize a training dataset using the trained Stage 1 (Ops) agent.

This produces the intermediate dataset required to train the Stage 2 (Rotations) agent
in the Separated Pipeline architecture:
    Expressions (raw) ──> Stage 1 (Ops Agent) ──> Expressions (ops-optimized)
    Expressions (ops-optimized) ──> Stage 2 (Rotations Agent) ──> Expressions (fully-optimized)
"""

import argparse
import os
import sys
import time
from pathlib import Path

from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.common.monitor import Monitor

from .utils import load_expressions_named, load_embeddings_from_config, create_rules
from .config import get_env_class, get_policy_class, set_embeddings_model_type, set_framework
from .memory import MemoryEstimator
from pytrs import parse_sexpr, calculate_cost


def preoptimize_dataset(
    input_file: str,
    output_file: str,
    model_path: str,
    embedder: str = "gnn",
    budget: int = 9000000,
    constraint_method: str = "nato_sc",
    constraint_metric: str = "mem",
    max_positions: int = 16,
):
    set_framework("unified")
    set_embeddings_model_type(embedder)

    print("=" * 60)
    print("  PRE-OPTIMIZE DATASET FOR STAGE 2 (ROTATIONS) TRAINING")
    print(f"  Input Dataset:    {input_file}")
    print(f"  Output Dataset:   {output_file}")
    print(f"  Stage 1 Model:    {model_path}")
    print(f"  Embedder:         {embedder}")
    print(f"  Budget:           {budget}")
    print(f"  Constraint:       {constraint_metric}")
    print("=" * 60)

    embeddings, _ = load_embeddings_from_config("dynamic", embedder_type=embedder)

    named_pairs = load_expressions_named(input_file)
    expr_names = [name for _, name in named_pairs]
    expressions = [expr for expr, _ in named_pairs]
    total_exprs = len(expressions)
    print(f"Loaded {total_exprs} expressions from {input_file}.")

    rules_p = "rules.txt"
    rot_p = "rotations_rules.txt"
    if not os.path.exists(rules_p):
        rules_p = os.path.join(os.path.dirname(os.path.dirname(__file__)), "rules.txt")
    if not os.path.exists(rot_p):
        rot_p = os.path.join(os.path.dirname(os.path.dirname(__file__)), "rotations_rules.txt")

    # Load only ops rules (Stage 1)
    rules_list = create_rules(rules_p, rot_p if os.path.exists(rot_p) else None, rules_subset="ops")
    rules_list["END"] = None

    EnvCls = get_env_class()
    PolicyCls = get_policy_class()

    env = DummyVecEnv([
        lambda: Monitor(
            EnvCls(
                rules_list,
                expressions,
                max_positions=max_positions,
                embeddings_model=embeddings,
                budget_options=[budget],
                constraint_method=constraint_method,
                constraint_metric=constraint_metric,
            )
        )
    ])

    print(f"Loading Stage 1 model from: {model_path}")
    model = PPO(policy=PolicyCls, env=env).load(model_path)
    noise_estimator = MemoryEstimator()

    os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)

    optimized_entries = []
    t_start = time.perf_counter()

    for i, (orig_expr, name) in enumerate(zip(expressions, expr_names)):
        env.set_options({"budget": budget, "expression": orig_expr})
        obs = env.reset()

        wrapper = env.envs[0]
        fhe_env = wrapper.env
        init_cost = fhe_env.initial_cost
        init_noise = float(getattr(fhe_env, "curr_constraint", None) or noise_estimator.estimate(parse_sexpr(orig_expr)))

        checkpoints = [{
            "step": 0,
            "expression": orig_expr,
            "cost": init_cost,
            "noise": init_noise,
        }]

        done = False
        steps = 0
        while not done:
            action, _ = model.predict(obs, deterministic=True)
            obs, rewards, dones, infos = env.step(action)
            done = bool(dones[0])
            steps += 1

            if done:
                terminal = infos[0]
                cp_expr = terminal.get("expression", fhe_env.expression)
                cp_cost = terminal.get("cost", fhe_env.current_cost)
                cp_noise = float(terminal.get("constraint_value", getattr(fhe_env, "curr_constraint", 0.0)))
            else:
                cp_expr = fhe_env.expression
                cp_cost = fhe_env.current_cost
                cp_noise = float(getattr(fhe_env, "curr_constraint", None) or noise_estimator.estimate(parse_sexpr(cp_expr)))

            checkpoints.append({
                "step": steps,
                "expression": cp_expr,
                "cost": cp_cost,
                "noise": cp_noise,
            })

        # Rollback: lowest cost among valid
        valid = [cp for cp in checkpoints if cp["noise"] <= budget]
        best = min(valid, key=lambda cp: cp["cost"]) if valid else checkpoints[0]
        safe_expr = best["expression"]
        final_cost = best["cost"]
        cost_red = ((init_cost - final_cost) / init_cost * 100) if init_cost > 0 else 0.0

        optimized_entries.append((safe_expr, name))

        if (i + 1) % 50 == 0 or (i + 1) == total_exprs:
            elapsed = time.perf_counter() - t_start
            print(f"  [{i+1}/{total_exprs}] Pre-optimized in {elapsed:.1f}s | Latest: {init_cost}->{final_cost} ({cost_red:+.1f}%)", flush=True)

    with open(output_file, "w", encoding="utf-8") as f:
        for expr, name in optimized_entries:
            if name and name != "None":
                f.write(f"{expr}:{name}\n")
            else:
                f.write(f"{expr}\n")

    print("=" * 60)
    print(f"Pre-optimization complete! Saved {len(optimized_entries)} expressions to:")
    print(f"  {output_file}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Pre-optimize training dataset with Stage 1 Ops model")
    parser.add_argument("--input", "--input_file", type=str, default="./fhe_rl/datasets/final_llm_dataset.txt",
                        help="Input raw dataset")
    parser.add_argument("--output", "--output_file", type=str, default="./fhe_rl/datasets/final_llm_dataset_ops_preoptimized.txt",
                        help="Output pre-optimized dataset")
    parser.add_argument("--model", type=str, required=True,
                        help="Path to trained Stage 1 Ops model (.zip)")
    parser.add_argument("--embedder", type=str, default="gnn", choices=["gnn", "dynamic", "bpe"],
                        help="Embedder architecture (default: gnn)")
    parser.add_argument("--budget", type=int, default=9000000,
                        help="Budget to enforce during pre-optimization")
    parser.add_argument("--constraint", type=str, default="noise", choices=["noise", "mem"],
                        help="Constraint metric: 'noise' or 'mem'")
    parser.add_argument("--method", type=str, default="nato_sc",
                        help="Constraint method (default: nato_sc)")

    args = parser.parse_args()
    preoptimize_dataset(
        input_file=args.input,
        output_file=args.output,
        model_path=args.model,
        embedder=args.embedder,
        budget=args.budget,
        constraint_method=args.method,
        constraint_metric=args.constraint,
    )


if __name__ == "__main__":
    main()
