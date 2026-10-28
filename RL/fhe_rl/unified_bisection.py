"""
unified_bisection.py — the MORL bisection experiment (Algorithm 3 of the thesis),
run on the unified agent (MORL + noise/RAM budget).

For every (expression, test budget):
  Phase 1  coarse grid over w_ops in [w_lo, w_hi]           (morl.bisection.build_coarse_grid)
  Phase 2  bisection on every key-count gap between
           neighbouring grid points, up to max_depth        (morl.bisection.bisect_interval)
  Front    non-dominated (C_exec, C_keys) points            (morl.pareto_frontier.get_pareto_frontier)

The grid / bisection / front code is the original MORL code; only "run one
preference" is new: it runs the unified PPO agent on the expression with
preference w = [w_ops, 1 - w_ops] under the budget.

Which expression a probe returns:
  - the agent's final expression if it is within budget (as in the original
    experiment, which used the final expression), otherwise
  - the latest checkpoint of the trajectory that is within budget, otherwise
  - the probe is infeasible (the expression starts over budget): it is kept in
    the probes sheet but excluded from the front and the metrics.

Metrics per (expression, budget), on costs normalized by the initial expression
(o = C_exec / C_exec0, k = C_keys / max(C_keys0, 1)):
  IC                cardinality: number of non-dominated points
  HV                hypervolume of the front w.r.t. reference point (1.1, 1.1)
  SP                sparsity: mean squared distance between consecutive front points
                    (0 when the front has fewer than 2 points)
  EU                expected utility: mean over the 10 training preferences w of
                    max over the front of -(w_ops * o + w_keys * k)  (higher is better)
  bisection_yield   fraction of front points found only by bisection probes
"""

from __future__ import annotations

import importlib
import os
import sys
import time

import numpy as np
import pandas as pd
from stable_baselines3 import PPO
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv

from .config import get_env_class, get_policy_class
from .memory import MemoryEstimator
from .morl.bisection import build_coarse_grid, bisect_interval, DEFAULT_MAX_BISECT_DEPTH
from .morl.display import display_pareto_table
from .morl.pareto_frontier import get_pareto_frontier
from .pareto import generate_pref_list
from .test import _get_split_costs, _resolve_expressions, _run_single_episode
from .utils import create_rules, load_expressions_named

DEFAULT_W_LO = 0.1   # lowest training preference w_ops
DEFAULT_W_HI = 1.0
HV_REF = (1.1, 1.1)


# ── probe ─────────────────────────────────────────────────────────────────────

def _pick_feasible(res: dict, budget: float):
    """Agent's final expression if within budget, else the latest checkpoint within budget, else None."""
    cps = res["checkpoints"]
    if cps[-1]["noise"] <= budget:
        return cps[-1], False
    for cp in reversed(cps[:-1]):
        if cp["noise"] <= budget:
            return cp, True
    return None, True


def _make_run_point(model, env, expr, budget, noise_estimator, constraint_metric, probes, phase_ref):
    """run_point(w_ops) for morl.bisection: runs the unified agent at w = [w_ops, 1 - w_ops]."""
    cache = {}

    def run_point(w_ops: float):
        w_ops = round(float(w_ops), 10)
        if w_ops in cache:
            return cache[w_ops]
        w_keys = round(1.0 - w_ops, 10)
        res = _run_single_episode(model, env, expr, budget, noise_estimator,
                                  None, constraint_metric, preference_vector=[w_ops, w_keys])
        cp, rolled_back = _pick_feasible(res, budget)
        if cp is not None:
            ops, keys = _get_split_costs(cp["expression"])
            noise, out_expr = cp["noise"], cp["expression"]
        else:
            ops = keys = noise = out_expr = None
        point = {
            "w_ops": w_ops,
            "w_keys": w_keys,
            "phase": phase_ref["phase"],
            "feasible": cp is not None,
            "rolled_back": rolled_back,
            "final_exec_cost": ops,
            "final_keys_cost": keys,
            "final_noise": noise,
            "steps": res["steps"],
            "rl_time_ms": round(res["elapsed_ms"], 1),
            "_expr": out_expr,
        }
        cache[w_ops] = point
        probes.append(point)
        return point

    return run_point


# ── metrics ───────────────────────────────────────────────────────────────────

def _normalize(front, ops0, keys0):
    return [(p["final_exec_cost"] / ops0 if ops0 else p["final_exec_cost"],
             p["final_keys_cost"] / max(keys0, 1)) for p in front]


def _hypervolume(pts, ref=HV_REF):
    hv, prev_k = 0.0, ref[1]
    for o, k in sorted(pts):
        if o < ref[0] and k < prev_k:
            hv += (ref[0] - o) * (prev_k - k)
            prev_k = k
    return hv


def _sparsity(pts):
    if len(pts) < 2:
        return 0.0
    pts = sorted(pts)
    return float(sum((pts[i][0] - pts[i + 1][0]) ** 2 + (pts[i][1] - pts[i + 1][1]) ** 2
                     for i in range(len(pts) - 1)) / (len(pts) - 1))


def _expected_utility(pts, prefs):
    if not pts:
        return None
    return float(np.mean([max(-(w[0] * o + w[1] * k) for o, k in pts) for w in prefs]))


# ── experiment ────────────────────────────────────────────────────────────────

def run_unified_bisection(
    benchmarks_file: str,
    embeddings_model,
    model_path: str,
    test_budgets: list,
    train_budgets: list,
    constraint_metric: str = "noise",
    constraint_method: str = "nato_sc",
    w_lo: float = DEFAULT_W_LO,
    w_hi: float = DEFAULT_W_HI,
    max_depth: int = DEFAULT_MAX_BISECT_DEPTH,
    output_file: str = None,
    max_positions: int = 16,
):
    benchmarks_file = _resolve_expressions(benchmarks_file)
    named = load_expressions_named(benchmarks_file)
    expressions = [e for e, _ in named]
    names = [n if n and n != "None" else f"expr_{i}" for i, (_, n) in enumerate(named)]

    rules_p, rot_p = "rules.txt", "rotations_rules.txt"
    if not os.path.exists(rules_p):
        rules_p = os.path.join(os.path.dirname(os.path.dirname(__file__)), "rules.txt")
    if not os.path.exists(rot_p):
        rot_p = os.path.join(os.path.dirname(os.path.dirname(__file__)), "rotations_rules.txt")
    rules_list = create_rules(rules_p, rot_p, rules_subset="all")   # joint unified agent
    rules_list["END"] = None

    EnvCls = get_env_class()
    env = DummyVecEnv([lambda: Monitor(EnvCls(
        rules_list, expressions, max_positions=max_positions, embeddings_model=embeddings_model,
        budget_options=train_budgets, constraint_method=constraint_method,
        constraint_metric=constraint_metric, verbose=False,
    ))])
    sys.modules["fhe_rl_new"] = importlib.import_module("fhe_rl")
    model = PPO(policy=get_policy_class(), env=env).load(model_path)
    noise_estimator = MemoryEstimator()
    eu_prefs = generate_pref_list(11)

    if output_file is None:
        output_file = f"bisection_results_{os.environ.get('SLURM_JOB_ID', 'local')}.xlsx"
    os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)

    print("=" * 70)
    print("  UNIFIED BISECTION EXPERIMENT (Algorithm 3)")
    print(f"  Model:          {model_path}")
    print(f"  Benchmarks:     {benchmarks_file} ({len(expressions)} expressions)")
    print(f"  Test budgets:   {test_budgets}   (trained on {train_budgets})")
    print(f"  Constraint:     {constraint_metric} / {constraint_method}")
    print(f"  w_ops range:    [{w_lo}, {w_hi}]   grid: {build_coarse_grid(w_lo, w_hi)}")
    print(f"  Max depth:      {max_depth}")
    print("=" * 70)

    probe_rows, front_rows, metric_rows = [], [], []
    t0 = time.perf_counter()

    for budget in test_budgets:
        for idx, (expr, name) in enumerate(zip(expressions, names)):
            print(f"\n[Budget {budget}] [{idx + 1}/{len(expressions)}] {name}")
            ops0, keys0 = _get_split_costs(expr)
            probes, phase_ref = [], {"phase": "grid"}
            run_point = _make_run_point(model, env, expr, budget, noise_estimator,
                                        constraint_metric, probes, phase_ref)

            # Phase 1: coarse grid
            grid_results = [run_point(w) for w in build_coarse_grid(w_lo, w_hi)]
            for r in grid_results:
                print(f"  grid w_ops={r['w_ops']:.4f}  ops={r['final_exec_cost']}  keys={r['final_keys_cost']}"
                      + ("" if r["feasible"] else "  (infeasible)"))

            # Phase 2: bisection on key-count gaps (same loop as the MORL menu mode)
            phase_ref["phase"] = "bisection"
            feasible_grid = [r for r in grid_results if r["feasible"]]
            if max_depth > 0 and len(feasible_grid) >= 2:
                ordered = sorted(feasible_grid, key=lambda r: r["w_ops"])
                for lo_pt, hi_pt in zip(ordered, ordered[1:]):
                    ks_lo, ks_hi = int(lo_pt["final_keys_cost"]), int(hi_pt["final_keys_cost"])
                    if ks_lo == ks_hi:
                        continue
                    bisect_interval(name, 0, hi_pt["w_ops"], ks_hi, lo_pt["w_ops"], ks_lo,
                                    [], max_depth, run_point=run_point)

            # Front + metrics
            feasible = [p for p in probes if p["feasible"]]
            front = get_pareto_frontier(feasible)
            grid_pts = {(p["final_exec_cost"], p["final_keys_cost"]) for p in feasible if p["phase"] == "grid"}
            pts = _normalize(front, ops0, keys0)
            n_bisect_only = sum((p["final_exec_cost"], p["final_keys_cost"]) not in grid_pts for p in front)
            if front:
                display_pareto_table(front)
            else:
                print("  no feasible solution (expression starts over budget)")

            for p in probes:
                probe_rows.append({"Budget": budget, "Expression": name, "Initial Ops": ops0,
                                   "Initial Keys": keys0,
                                   **{k: v for k, v in p.items() if not k.startswith("_")}})
            for i, p in enumerate(front, 1):
                front_rows.append({"Budget": budget, "Expression": name, "Front #": i,
                                   "w_ops": p["w_ops"], "w_keys": p["w_keys"], "phase": p["phase"],
                                   "Exec Cost": p["final_exec_cost"], "Keys Cost": p["final_keys_cost"],
                                   "Noise": p["final_noise"], "Optimized Expression": p["_expr"]})
            metric_rows.append({
                "Budget": budget, "Expression": name,
                "Initial Ops": ops0, "Initial Keys": keys0,
                "Grid Probes": sum(p["phase"] == "grid" for p in probes),
                "Bisection Probes": sum(p["phase"] == "bisection" for p in probes),
                "Infeasible Probes": sum(not p["feasible"] for p in probes),
                "Distinct Key Counts": len({p["final_keys_cost"] for p in feasible}),
                "IC": len(front),
                "HV": round(_hypervolume(pts), 6) if front else None,
                "SP": round(_sparsity(pts), 6) if front else None,
                "EU": round(_expected_utility(pts, eu_prefs), 6) if front else None,
                "Bisection Yield": round(n_bisect_only / len(front), 4) if front else None,
            })
            _save(output_file, probe_rows, front_rows, metric_rows)   # progressive save

    _save(output_file, probe_rows, front_rows, metric_rows, final=True)
    print(f"\nDone in {(time.perf_counter() - t0) / 60:.1f} min. Results: {output_file}")


def _save(output_file, probe_rows, front_rows, metric_rows, final=False):
    try:
        mdf = pd.DataFrame(metric_rows)
        with pd.ExcelWriter(output_file, engine="openpyxl") as w:
            mdf.to_excel(w, sheet_name="metrics", index=False)
            pd.DataFrame(front_rows).to_excel(w, sheet_name="fronts", index=False)
            pd.DataFrame(probe_rows).to_excel(w, sheet_name="probes", index=False)
            if len(mdf):
                cols = ["IC", "HV", "SP", "EU", "Bisection Yield", "Grid Probes",
                        "Bisection Probes", "Infeasible Probes", "Distinct Key Counts"]
                summary = mdf.groupby("Budget")[cols].mean(numeric_only=True).round(4).reset_index()
                summary.insert(1, "Expressions", mdf.groupby("Budget").size().values)
                summary.to_excel(w, sheet_name="summary_per_budget", index=False)
        if final:
            pd.DataFrame(probe_rows).to_csv(os.path.splitext(output_file)[0] + "_probes.csv", index=False)
    except Exception as e:
        print(f"[warn] could not save results: {e}")
