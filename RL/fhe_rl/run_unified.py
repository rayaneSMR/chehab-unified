"""Single-expression inference for the UNIFIED agent (MORL preference + noise budget).

Called by the C++ compiler through ``python -m fhe_rl --framework unified run <in> <out> --w_ops W``.
Everything the compiler cannot pass on its command line comes from CLI flags or,
when absent, from environment variables (they survive the compiler's ``system()`` call):

    CHEHAB_RL_MODEL          path to the trained unified agent (.zip)
    CHEHAB_RL_W_OPS          preference weight for execution time (w_keys = 1 - w_ops)
    CHEHAB_RL_BUDGET         noise budget for this compilation (used BFV bits)
    CHEHAB_RL_TRAIN_BUDGETS  comma list of budgets the agent was trained on (sets the one-hot size)
    CHEHAB_RL_METHOD         constraint method the agent was trained with (default nato_sc)
    CHEHAB_RL_CONSTRAINT     constraint metric: noise (default) or mem
    CHEHAB_RL_ROLLBACK       1 (default) = safety rollback to the best compliant step, 0 = raw agent output
    CHEHAB_RL_INFO_JSON      if set, a JSON summary of the episode is written there
    CHEHAB_RL_RULES_SUBSET   all (default) | ops | rotations  (separated-pipeline agents)

The agent output is written in the same format as run.py (expression line + vector-size footer)
and the summary lines ``Final exec cost:`` / ``Final keys cost:`` are printed so the existing
benchmark drivers can parse them.
"""

from __future__ import annotations

import importlib
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
from stable_baselines3 import PPO
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv

from .config import get_env_class
from .utils import calc_vec_sizes, create_rules, load_expressions_named, parse_sexpr

DEFAULT_NOISE_BUDGETS = [230, 236, 369, 9_000_000]


def _env(name, default=None):
    value = os.environ.get(name)
    return value if value not in (None, "") else default


def _keys_cost(expr_str: str) -> int:
    """C_keys: number of distinct rotation steps = number of Galois keys (same as fheEnvUnified)."""
    from pytrs.cost import keys_cost
    return int(keys_cost(parse_sexpr(expr_str)))


def _exec_cost(expr_str: str) -> float:
    """C_exec: MORL/unified execution cost (same as fheEnvUnified.get_split_costs)."""
    from pytrs.cost import exec_cost_mo
    return float(exec_cost_mo(parse_sexpr(expr_str)))


def resolve_run_settings(model=None, w_ops=None, budget=None, train_budgets=None,
                         method=None, constraint=None, rollback=None, info_json=None):
    """Merge CLI values with CHEHAB_RL_* environment variables (CLI wins)."""
    from .config import get_model_path

    model = model or _env("CHEHAB_RL_MODEL") or str(get_model_path("unified_agent_model"))
    w_ops = float(w_ops if w_ops is not None else _env("CHEHAB_RL_W_OPS", 1.0))
    if train_budgets is None:
        raw = _env("CHEHAB_RL_TRAIN_BUDGETS")
        train_budgets = [int(b) for b in raw.split(",")] if raw else list(DEFAULT_NOISE_BUDGETS)
    budget = int(budget if budget is not None else _env("CHEHAB_RL_BUDGET", train_budgets[-1]))
    method = method or _env("CHEHAB_RL_METHOD", "nato_sc")
    constraint = constraint or _env("CHEHAB_RL_CONSTRAINT", "noise")
    if rollback is None:
        rollback = _env("CHEHAB_RL_ROLLBACK", "1") not in ("0", "false", "False")
    info_json = info_json or _env("CHEHAB_RL_INFO_JSON")
    return dict(model=model, w_ops=w_ops, budget=budget, train_budgets=train_budgets,
                method=method, constraint=constraint, rollback=bool(rollback), info_json=info_json)


def run_agent_unified(expressions_file: str, embeddings_model, output_file: str, **settings):
    s = resolve_run_settings(**settings)
    if not Path(s["model"]).is_file():
        print(f"[run_unified] model not found: {s['model']}", file=sys.stderr)
        sys.exit(2)
    w = [round(s["w_ops"], 10), round(1.0 - s["w_ops"], 10)]

    # load_expressions() drops vector sizes outside {1,4,8,9,16,25,32} (e.g. max_3, sort_3);
    # the named loader keeps every parsable expression.
    expressions = [e for e, _ in load_expressions_named(expressions_file)]
    if not expressions:
        print("No valid expressions found in the file.", file=sys.stderr)
        sys.exit(1)

    rl_dir = Path(__file__).resolve().parent.parent
    rules_p = Path("rules.txt") if Path("rules.txt").is_file() else rl_dir / "rules.txt"
    rot_p = Path("rotations_rules.txt") if Path("rotations_rules.txt").is_file() else rl_dir / "rotations_rules.txt"
    # Same rule set as train.py; CHEHAB_RL_RULES_SUBSET=ops|rotations for the separated-pipeline agents.
    rules_list = create_rules(str(rules_p), str(rot_p) if rot_p.is_file() else None,
                              rules_subset=_env("CHEHAB_RL_RULES_SUBSET", "all"))
    rules_list["END"] = None

    EnvCls = get_env_class()
    env = DummyVecEnv([lambda: Monitor(EnvCls(
        rules_list, expressions, max_positions=16,
        embeddings_model=embeddings_model,
        budget_options=s["train_budgets"],
        constraint_method=s["method"],
        constraint_metric=s["constraint"],
        pref_list=[w],
        verbose=False,
    ))])
    env.env_method("set_preference_vector", w)
    env.set_options({"budget": s["budget"]})

    sys.modules.setdefault("fhe_rl_new", importlib.import_module("fhe_rl"))
    # Let SB3 unpickle the policy class stored in the zip (HierarchicalMaskablePolicy or a FiLM
    # variant); forcing PolicyCls here would break FiLM-b checkpoints.
    model = PPO.load(s["model"], env=env)
    model_keys = set(getattr(model.observation_space, "spaces", {}).keys())

    t0 = time.perf_counter()
    obs = env.reset()
    fhe_env = env.envs[0].env
    initial_expr = fhe_env.initial_expression
    trajectory = [{"step": 0, "expression": initial_expr,
                   "constraint": float(fhe_env.curr_constraint)}]
    done, steps = False, 0
    while not done:
        obs_in = {k: v for k, v in obs.items() if not model_keys or k in model_keys}
        action, _ = model.predict(obs_in, deterministic=True)
        obs, _, dones, infos = env.step(action)
        done = bool(dones[0])
        steps += 1
        # DummyVecEnv auto-resets on done: the terminal state is only in infos.
        info = infos[0]
        trajectory.append({"step": steps,
                           "expression": info.get("expression", fhe_env.expression),
                           "constraint": float(info.get("constraint_value", fhe_env.curr_constraint))})
    inference_s = time.perf_counter() - t0

    agent_final = trajectory[-1]
    chosen, rollback_used = agent_final, False
    if s["rollback"] and agent_final["constraint"] > s["budget"]:
        valid = [cp for cp in trajectory if cp["constraint"] <= s["budget"]]
        if valid:
            # best compliant state under the SAME scalarisation the agent optimises
            def score(cp):
                return w[0] * _exec_cost(cp["expression"]) + w[1] * _keys_cost(cp["expression"])
            chosen = min(valid, key=score)
        else:
            chosen = trajectory[0]
        rollback_used = chosen["step"] != agent_final["step"]

    final_expr = chosen["expression"]
    vec_s = calc_vec_sizes(parse_sexpr(final_expr))
    footer = f"{vec_s[0]} {vec_s[0]} 1 0" if vec_s else "1 1 1 0"
    with open(output_file, "w") as f:
        f.write(final_expr + "\n" + footer + "\n")

    summary = {
        "w_ops": w[0], "w_keys": w[1], "budget": s["budget"], "train_budgets": s["train_budgets"],
        "method": s["method"], "constraint_metric": s["constraint"], "model": s["model"],
        "steps": steps, "inference_time_s": round(inference_s, 4),
        "initial_exec_cost": _exec_cost(initial_expr), "initial_keys_cost": _keys_cost(initial_expr),
        "initial_constraint": trajectory[0]["constraint"],
        "agent_exec_cost": _exec_cost(agent_final["expression"]),
        "agent_keys_cost": _keys_cost(agent_final["expression"]),
        "agent_constraint": agent_final["constraint"],
        "agent_violated": agent_final["constraint"] > s["budget"],
        "final_exec_cost": _exec_cost(final_expr), "final_keys_cost": _keys_cost(final_expr),
        "final_constraint": chosen["constraint"],
        "final_violated": chosen["constraint"] > s["budget"],
        "rollback_used": rollback_used,
    }
    print(f"Final exec cost: {summary['final_exec_cost']}")
    print(f"Final keys cost: {summary['final_keys_cost']}")
    print(f"Final estimated noise: {summary['final_constraint']:.2f} (budget {s['budget']})")
    if s["info_json"]:
        Path(s["info_json"]).parent.mkdir(parents=True, exist_ok=True)
        with open(s["info_json"], "w") as f:
            json.dump(summary, f, indent=2)
    return summary
