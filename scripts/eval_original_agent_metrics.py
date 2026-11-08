#!/usr/bin/env python3
"""Noise-budget violations of the original CHEHAB RL agent (agent level).

Runs the original agent (PPO + TRAE, 84 rules, deterministic) on every benchmark and
estimates the noise of its output with the same estimator as CMO-RL (pytrs.NoiseEstimator).
For each budget B: Violated = final estimated noise > B (Is Feasible = initial noise <= B).
CHEHAB RL has no rollback, so Safe Violated = Violated.

Run from the RL/ directory:
    cd RL
    PYTHONPATH=.:pytrs python ../scripts/eval_original_agent_metrics.py \
        --benchmarks fhe_rl/datasets/benchmarks.txt \
        --budgets 230 236 369 9000000 \
        --out test_results/original_agent_metrics/original_agent_violations.xlsx
"""
import argparse
import importlib
import os
import sys

# The original agent's env uses pytrs' legacy cost; set its framework before any pytrs import.
import pytrs.config
pytrs.config.framework = "baseline"

import pandas as pd
from stable_baselines3 import PPO
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv

from pytrs import parse_sexpr, NoiseEstimator

from fhe_rl.config import set_framework, set_embeddings_model_type, get_model_path
from fhe_rl.utils import create_rules, load_expressions_named, load_embeddings_from_config
from fhe_rl.TRAE_bpe import BPETokenizer  # noqa: F401  (needed to unpickle the embedder)
from fhe_rl.baseline.env_baseline import fheEnv
from fhe_rl.baseline.policy_baseline import HierarchicalMaskablePolicy


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--benchmarks", default="fhe_rl/datasets/benchmarks.txt")
    ap.add_argument("--model", default=None, help="default: config agent_model (agent_dynamic_llm_data.zip)")
    ap.add_argument("--rules", default="rules.txt")
    ap.add_argument("--budgets", type=float, nargs="+", default=[230, 236, 369, 9000000])
    ap.add_argument("--indices", default=None, help="comma-separated 0-based line indices of the benchmark file (default: all)")
    ap.add_argument("--out", default="original_agent_violations.xlsx", help=".xlsx (rows + summary) or .csv (rows)")
    args = ap.parse_args()

    set_framework("baseline")
    set_embeddings_model_type("trae")
    embeddings, _ = load_embeddings_from_config(None, embedder_type="trae")
    model_path = args.model or get_model_path("agent_model")

    # (0-based line index in the benchmark file, expression, name); names may repeat,
    # so "Expression #" (= index + 1, as in CMO-RL's results) identifies a benchmark.
    named = [(i, e, n) for i, (e, n) in enumerate(load_expressions_named(args.benchmarks))]
    if args.indices:
        keep = {int(i) for i in args.indices.split(",")}
        named = [x for x in named if x[0] in keep]
    if not named:
        sys.exit("No benchmark selected.")
    exprs = [e for _, e, _ in named]

    rules = create_rules(args.rules, rules_subset="ops")
    rules["END"] = None
    env = DummyVecEnv([lambda: Monitor(fheEnv(rules, exprs, max_positions=16, embeddings_model=embeddings))])
    sys.modules["fhe_rl_new"] = importlib.import_module("fhe_rl")
    model = PPO(policy=HierarchicalMaskablePolicy, env=env).load(model_path)
    fhe_env = env.envs[0].env
    noise_est = NoiseEstimator()

    rows = []
    for k, (idx, expr, name) in enumerate(named):
        print(f"[{k + 1}/{len(named)}] #{idx + 1} {name}", flush=True)
        fhe_env.current_index = k          # env cycles through `exprs`; pin it to this benchmark
        obs = env.reset()
        assert fhe_env.initial_expression == expr
        done, last_expr = False, expr
        while not done:
            last_expr = fhe_env.expression    # DummyVecEnv auto-resets on done: keep the last state
            action, _ = model.predict(obs, deterministic=True)
            obs, _, dones, _ = env.step(action)
            done = bool(dones[0])

        n0 = float(noise_est.estimate(parse_sexpr(expr)))
        nf = float(noise_est.estimate(parse_sexpr(last_expr)))
        for b in args.budgets:
            rows.append({
                "Budget": b, "Expression #": idx + 1, "Expression Name": name,
                "Is Feasible": n0 <= b,
                "Initial Noise": round(n0, 2), "Agent Final Noise": round(nf, 2),
                "Agent Violated": nf > b,
                "Safe Violated": nf > b,   # no rollback in CHEHAB RL
                "Final Expression": last_expr,
            })

    df = pd.DataFrame(rows)
    summary = pd.DataFrame([{
        "Budget": b, "N": len(g), "Feasible": int(g["Is Feasible"].sum()),
        "Violations": int(g["Agent Violated"].sum()),
        "Violations (feasible only)": int(g.loc[g["Is Feasible"], "Agent Violated"].sum()),
        "Safe Violations": int(g["Safe Violated"].sum()),
    } for b, g in df.groupby("Budget")])
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    if args.out.endswith(".csv"):        # one-benchmark jobs: raw rows only
        df.to_csv(args.out, index=False)
    else:
        with pd.ExcelWriter(args.out) as w:
            df.to_excel(w, sheet_name="all_runs", index=False)
            summary.to_excel(w, sheet_name="summary", index=False)
    print(summary.to_string(index=False))
    print(f"\nSaved {args.out}")


if __name__ == "__main__":
    main()
