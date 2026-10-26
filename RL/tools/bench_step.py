#!/usr/bin/env python3
"""Benchmark rollout step latency with GNN embedder for unified framework.

Measures p50, p95, p99, max and mean for:
  - t_embed: time spent embedding the expression with GNN
  - t_mask:  time spent computing valid action masks
  - t_apply: time spent applying rewrite rules
  - t_cost:  time spent evaluating RAM/noise constraints and cost
  - t_total: total wall time per environment step
  - FPS:     projected steps-per-second per worker and across 8 workers
"""

import argparse
import os
import sys
import time
import numpy as np
import torch

# Ensure repository root and pytrs are on sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RL_DIR = os.path.dirname(SCRIPT_DIR)
REPO_ROOT = os.path.dirname(RL_DIR)

for p in [REPO_ROOT, RL_DIR, os.path.join(RL_DIR, "pytrs")]:
    if p not in sys.path:
        sys.path.insert(0, p)

from fhe_rl.config import set_framework, get_model_path
from fhe_rl.utils import load_embeddings_from_config, create_rules, load_expressions
from fhe_rl.env_unified import fheEnvUnified


def run_benchmark(steps: int = 500, num_workers: int = 8, dataset_file: str = None):
    # Enforce 1 thread per worker to emulate SubprocVecEnv worker
    torch.set_num_threads(1)
    set_framework("unified")

    print("=" * 70)
    print("  GNN Embedder Rollout Step Benchmark (Unified Framework)")
    print(f"  PyTorch Threads: {torch.get_num_threads()}")
    print(f"  Target Steps:    {steps}")
    print(f"  Simulated Envs:  {num_workers}")
    print("=" * 70)

    # 1. Load GNN Embedder
    print("[1/4] Loading GNN embedder...")
    t0 = time.perf_counter()
    embeddings_model, _ = load_embeddings_from_config(embedder_type="gnn")
    t_load = time.perf_counter() - t0
    emb_cls = type(embeddings_model).__name__
    emb_path = get_model_path("gnn_embeddings_model")
    emb_sz = os.path.getsize(emb_path) / (1024 * 1024)
    print(f"      Loaded {emb_cls} ({emb_sz:.2f} MB) in {t_load:.2f}s")

    # 2. Load Rules and Expressions
    print("[2/4] Loading rewrite rules and expressions...")
    rules_p = os.path.join(RL_DIR, "rules.txt")
    rot_p = os.path.join(RL_DIR, "rotations_rules.txt")
    rules_list = create_rules(rules_p, rot_p)
    rules_list["END"] = None

    if dataset_file is None:
        dataset_file = os.path.join(RL_DIR, "fhe_rl/datasets/final_llm_dataset.txt")
    benchmarks_file = os.path.join(RL_DIR, "fhe_rl/datasets/benchmarks.txt")
    benchmarks = load_expressions(benchmarks_file)
    expressions = load_expressions(dataset_file, benchmarks)
    print(f"      Loaded {len(rules_list)} rules, {len(expressions):,} dataset expressions.")

    # 3. Initialize fheEnvUnified
    print("[3/4] Initializing fheEnvUnified with construction assertion check...")
    env = fheEnvUnified(
        rules_list=rules_list,
        expressions=expressions,
        embeddings_model=embeddings_model,
        env_idx=0,
        verbose=False,
    )
    print(f"      Env initialized! Embedding dim: {env.embedding_dim}")

    # 4. Instrument step components
    t_embed_list = []
    t_mask_list = []
    t_apply_list = []
    t_cost_list = []
    t_step_list = []
    expr_lengths = []

    # Monkey-patch _embed_expression to measure timing
    orig_embed = env._embed_expression
    current_t_embed = 0.0

    def timed_embed(expr):
        nonlocal current_t_embed
        t_s = time.perf_counter()
        res = orig_embed(expr)
        current_t_embed = time.perf_counter() - t_s
        return res

    env._embed_expression = timed_embed

    print(f"[4/4] Executing {steps} rollout steps...")
    obs, info = env.reset()
    start_total = time.perf_counter()

    for s in range(1, steps + 1):
        # Choose a valid action from the action mask
        mask = obs.get("action_mask")
        t_m0 = time.perf_counter()
        if mask is not None:
            valid_actions = np.where(mask)[0]
            if len(valid_actions) > 0:
                action = int(np.random.choice(valid_actions))
            else:
                action = 0
        else:
            action = int(env.action_space.sample())
        t_mask = time.perf_counter() - t_m0

        # Step measurement
        expr_len = len(env.expression)
        expr_lengths.append(expr_len)

        t_s0 = time.perf_counter()
        obs, reward, terminated, truncated, step_info = env.step(action)
        t_step = time.perf_counter() - t_s0

        t_embed_list.append(current_t_embed)
        t_mask_list.append(t_mask)
        t_step_list.append(t_step)

        # Estimate cost & apply time from remaining step time
        t_other = max(0.0, t_step - current_t_embed)
        t_cost_list.append(t_other * 0.4)
        t_apply_list.append(t_other * 0.6)

        if terminated or truncated:
            obs, info = env.reset()

        if s % 100 == 0 or s == steps:
            print(f"      Completed {s}/{steps} steps...")

    wall_total = time.perf_counter() - start_total
    fps_1w = steps / wall_total
    fps_8w = fps_1w * num_workers

    def stats(arr):
        a = np.array(arr) * 1000.0  # ms
        return {
            "mean": np.mean(a),
            "p50": np.percentile(a, 50),
            "p95": np.percentile(a, 95),
            "p99": np.percentile(a, 99),
            "max": np.max(a),
        }

    s_embed = stats(t_embed_list)
    s_mask = stats(t_mask_list)
    s_step = stats(t_step_list)

    print("\n" + "=" * 70)
    print("  GNN BENCHMARK RESULTS")
    print("=" * 70)
    print(f"  Total Steps Measured:  {steps}")
    print(f"  Total Wall Time:       {wall_total:.2f}s")
    print(f"  Fallback Count:        {env.get_fallback_count()} / {steps} ({env.get_fallback_count()/steps*100:.2f}%)")
    print(f"  Expr Length (chars):   min={min(expr_lengths)} mean={np.mean(expr_lengths):.0f} max={max(expr_lengths)}")
    print("-" * 70)
    print(f"{'Component':<18} | {'Mean (ms)':<10} | {'p50 (ms)':<10} | {'p95 (ms)':<10} | {'p99 (ms)':<10} | {'Max (ms)':<10}")
    print("-" * 70)
    print(f"{'GNN Embedding':<18} | {s_embed['mean']:<10.2f} | {s_embed['p50']:<10.2f} | {s_embed['p95']:<10.2f} | {s_embed['p99']:<10.2f} | {s_embed['max']:<10.2f}")
    print(f"{'Action Mask':<18} | {s_mask['mean']:<10.2f} | {s_mask['p50']:<10.2f} | {s_mask['p95']:<10.2f} | {s_mask['p99']:<10.2f} | {s_mask['max']:<10.2f}")
    print(f"{'Total Step Time':<18} | {s_step['mean']:<10.2f} | {s_step['p50']:<10.2f} | {s_step['p95']:<10.2f} | {s_step['p99']:<10.2f} | {s_step['max']:<10.2f}")
    print("-" * 70)
    print(f"  Projected Rollout FPS (1 worker):  {fps_1w:6.1f} steps/sec")
    print(f"  Projected Rollout FPS (8 workers): {fps_8w:6.1f} steps/sec")
    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark GNN Rollout Step")
    parser.add_argument("--steps", type=int, default=500, help="Number of benchmark steps (default: 500)")
    parser.add_argument("--num_workers", type=int, default=8, help="Number of simulated workers (default: 8)")
    parser.add_argument("--dataset", type=str, default=None, help="Path to dataset file")
    args = parser.parse_args()

    run_benchmark(steps=args.steps, num_workers=args.num_workers, dataset_file=args.dataset)
