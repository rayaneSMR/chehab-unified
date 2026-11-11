from stable_baselines3 import PPO
import time
from .utils import load_expressions, create_rules, parse_sexpr, calc_vec_sizes
import sys
import importlib
from stable_baselines3.common.vec_env import DummyVecEnv
from .config import get_env_class, get_policy_class
from stable_baselines3.common.monitor import Monitor


def _write_compiler_output(expr: str, output_file: str):
    """Rewritten expression + vector-size footer, the format the C++ compiler reads back."""
    vec_s = calc_vec_sizes(parse_sexpr(expr))
    footer = f"{vec_s[0]} {vec_s[0]} 1 0" if vec_s else "1 1 1 0"
    with open(output_file, "w") as f:
        f.write(expr + "\n" + footer + "\n")


def run_agent_unified(
    expressions_file: str,
    embeddings_model,
    model_filepath: str,
    output_file: str,
    budget: int,
    train_budgets: list,
    preference: list,
    constraint_metric: str = "noise",
    constraint_method: str = "nato_sc",
    log_file: str = None,
    model_stage2_filepath: str = None,
    rollback: bool = True,
    agent_budget: int = None,
):
    """Unified agent inside the C++ compiler (real compile + SEAL execution evaluation).

    Runs the joint agent (ops + rotation rules) on the expression written by the
    compiler, under `budget`, with preference `preference` = [w_ops, w_keys], then
    applies the same safety rollback as `fhe_rl test` (best checkpoint within budget,
    scored with the preference). Writes the safe expression back for the compiler,
    and appends one JSON line with the RL-side numbers to `log_file` if given.

    rollback=False: the compiler gets the agent's final program (still checked by the SEAL
    bound; the input if the bound does not certify it), see `_run_single_episode`.

    agent_budget: budget given to the agent when it differs from `budget`, which the rollback
    and the violation check use (e.g. 9000000: unconstrained agent rolled back at the real
    budget, as `fhe_rl test --agent_budget`).

    Separated pipeline (model_stage2_filepath given), as in `fhe_rl test --pipeline separated`:
    Stage 1 (model_filepath, ops rules) runs at w = [1, 0], then Stage 2 (model_stage2_filepath,
    rotation rules) runs at `preference` on the Stage 1 output. Each stage has its own rollback.
    """
    import json
    import os
    from pytrs import NoiseEstimator
    from .memory import MemoryEstimator
    from .test import _run_single_episode, _get_split_costs

    expressions = load_expressions(expressions_file)
    if not expressions:
        print("No valid expressions found in the file.")
        sys.exit(1)
    compiler_expr = expressions[0]
    # FHE_RL_INPUT_EXPRESSION: run on this expression instead of the compiler's, e.g. a dataset
    # program whose noise the compiler's front-end rewrites would change. It must be equivalent
    # to the compiler's (same inputs, outputs in the same order).
    override = os.environ.get("FHE_RL_INPUT_EXPRESSION", "").strip()
    expr = override.split(":")[0].strip() if override else compiler_expr

    # FHE_RL_PASSTHROUGH=1: no agent, the compiler gets the input program back (baseline).
    if os.environ.get("FHE_RL_PASSTHROUGH", "0") == "1":
        from pytrs import NoiseEstimator
        from .test import _get_split_costs
        _write_compiler_output(expr, output_file)
        ops0, keys0 = _get_split_costs(expr)
        noise0 = float(NoiseEstimator().estimate(parse_sexpr(expr)))
        record = {
            "w_ops": preference[0], "w_keys": preference[1], "budget": budget,
            "initial_ops": ops0, "initial_keys": keys0, "initial_noise_est": noise0,
            "agent_ops": ops0, "agent_keys": keys0, "agent_noise_est": noise0,
            "agent_violated": noise0 > budget,
            "safe_ops": ops0, "safe_keys": keys0, "safe_noise_est": noise0,
            "safety_activated": False, "best_valid_step": 0, "rl_steps": 0, "rl_time_ms": 0.0,
            "input_expression": expr, "safe_expression": expr,
            "compiler_expression": compiler_expr, "input_overridden": bool(override),
            "pipeline": "passthrough", "rollback": False, "method": "none",
        }
        print(f"[unified run] passthrough: ops {ops0}, keys {keys0}, noise est {noise0:.1f}", flush=True)
        if log_file:
            with open(log_file, "a") as f:
                f.write(json.dumps(record) + "\n")
        return record

    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    rules_p = "rules.txt" if os.path.exists("rules.txt") else os.path.join(here, "rules.txt")
    rot_p = "rotations_rules.txt" if os.path.exists("rotations_rules.txt") else os.path.join(here, "rotations_rules.txt")
    EnvCls = get_env_class()
    PolicyCls = get_policy_class()
    sys.modules["fhe_rl_new"] = importlib.import_module("fhe_rl")

    def _load(subset, path):
        rules_list = create_rules(rules_p, rot_p, rules_subset=subset)
        rules_list["END"] = None
        env = DummyVecEnv([lambda: Monitor(EnvCls(
            rules_list, [expr], max_positions=16, embeddings_model=embeddings_model,
            budget_options=train_budgets, constraint_method=constraint_method,
            constraint_metric=constraint_metric, verbose=False,
        ))])
        return PPO(policy=PolicyCls, env=env).load(path), env

    separated = bool(model_stage2_filepath)
    if separated:
        model, env = _load("ops", model_filepath)
        model_rot, env_rot = _load("rotations", model_stage2_filepath)
    else:
        model, env = _load("all", model_filepath)
    estimator = NoiseEstimator() if constraint_metric == "noise" else MemoryEstimator()

    # SEAL noise-bound certificate for the rollback, as in `fhe_rl test`: the returned program
    # must be certified decryptable. Required for the noise constraint (fails if not configured).
    verifier = None
    if constraint_metric == "noise":
        from .seal_noise_bound import BFVNoiseBoundVerifier
        verifier = BFVNoiseBoundVerifier.from_environment()

    if separated:
        res1 = _run_single_episode(model, env, expr, budget, estimator, verifier, constraint_metric,
                                   preference_vector=[1.0, 0.0], rollback=rollback, agent_budget=agent_budget)
        res = _run_single_episode(model_rot, env_rot, res1["safe_expr"], budget, estimator, verifier,
                                  constraint_metric, preference_vector=preference, rollback=rollback,
                                  agent_budget=agent_budget)
        # Report the whole pipeline: input of Stage 1 -> output of Stage 2
        res["initial_noise"] = res1["initial_noise"]
        res["safety_activated"] = res1["safety_activated"] or res["safety_activated"]
        res["steps"] = res1["steps"] + res["steps"]
        res["elapsed_ms"] = res1["elapsed_ms"] + res["elapsed_ms"]
    else:
        res = _run_single_episode(model, env, expr, budget, estimator, verifier, constraint_metric,
                                  preference_vector=preference, rollback=rollback, agent_budget=agent_budget)
    safe_expr = res["safe_expr"]
    _write_compiler_output(safe_expr, output_file)

    ops0, keys0 = _get_split_costs(expr)
    agent_ops, agent_keys = _get_split_costs(res["agent_final"]["expression"])
    safe_ops, safe_keys = _get_split_costs(safe_expr)
    record = {
        "w_ops": preference[0], "w_keys": preference[1], "budget": budget,
        "initial_ops": ops0, "initial_keys": keys0, "initial_noise_est": res["initial_noise"],
        "agent_ops": agent_ops, "agent_keys": agent_keys,
        "agent_noise_est": res["agent_final"]["noise"],
        "agent_violated": res["agent_final"]["noise"] > budget,
        "safe_ops": safe_ops, "safe_keys": safe_keys, "safe_noise_est": res["safe_noise"],
        "safety_activated": res["safety_activated"], "best_valid_step": res["best_valid_step"],
        "rl_steps": res["steps"], "rl_time_ms": round(res["elapsed_ms"], 1),
        "certified": res["certified"],
        "certified_remaining_bits": (res["certificate"].remaining_noise_budget_bits
                                     if res["certificate"] is not None else None),
        "input_expression": expr, "safe_expression": safe_expr,
        "compiler_expression": compiler_expr, "input_overridden": bool(override),
        "pipeline": "separated" if separated else "joint",
        "rollback": rollback, "method": constraint_method,
        "agent_budget": agent_budget if agent_budget is not None else budget,
    }
    if separated:
        st1_ops, st1_keys = _get_split_costs(res1["safe_expr"])
        record.update({"stage1_ops": st1_ops, "stage1_keys": st1_keys,
                       "stage1_noise_est": res1["safe_noise"],
                       "stage1_safety_activated": res1["safety_activated"]})
    print(f"[unified run] w={preference} budget={budget}: ops {ops0}->{safe_ops}, keys {keys0}->{safe_keys}, "
          f"noise est {res['initial_noise']:.1f}->{res['safe_noise']:.1f}, "
          f"rollback={'ON' if res['safety_activated'] else 'off'}, certified={res['certified']}", flush=True)
    if log_file:
        with open(log_file, "a") as f:
            f.write(json.dumps(record) + "\n")
    return record


def run_agent(expressions_file: str, embeddings_model, model_filepath: str, output_file: str, noise_budget: int = 1500, framework: str = "constrained"):
    start_time = time.perf_counter()
    expressions = load_expressions(expressions_file)
    if not len(expressions):
        print("No valid expressions found in the file.")
        sys.exit(1)
        return
    from pathlib import Path
    rules_path = Path("rules.txt")
    if not rules_path.is_file():
        rules_path = Path(__file__).resolve().parent.parent / "rules.txt"
    rules_list = create_rules(str(rules_path))
    rules_list["END"] = None
    results = []
    max_positions = 16
    end_time = time.perf_counter()
    elapsed_seconds = end_time - start_time
    EnvCls = get_env_class()
    PolicyCls = get_policy_class()
    if framework in ("constrained", "constrained_rl"):
        env_fn = lambda: Monitor(EnvCls(
            rules_list, expressions, max_positions=max_positions,
            embeddings_model=embeddings_model,
            budget_options=[230, 236, 369, 9_000_000],
            constraint_method="nato_sc",
            verbose=False,
        ))
    else:
        env_fn = lambda: Monitor(EnvCls(
            rules_list, expressions, max_positions=max_positions,
            embeddings_model=embeddings_model,
            budget_options=[9_000_000],
            constraint_method="none",
            verbose=False,
        ))
    if "fhe_rl_new" not in sys.modules:
        try:
            sys.modules["fhe_rl_new"] = importlib.import_module("fhe_rl")
        except Exception:
            pass
    try:
        import fhe_rl.policy
        fhe_rl.policy.HierarchicalMaskablePolicy = PolicyCls
    except Exception:
        pass

    env = DummyVecEnv([env_fn])
    env.set_options({ "budget": noise_budget })

    model = PPO(
        policy=PolicyCls,
        env=env
    )
    model = model.load(model_filepath)
    model_obs_keys = set(
        list(model.observation_space.spaces.keys())
        if hasattr(model, "observation_space") and hasattr(model.observation_space, "spaces") else []
    )
    start_time = time.perf_counter()
    obs = env.reset()
    wrapper  = env.envs[0]
    fhe_env   = wrapper.env
    test_expr = fhe_env.initial_expression
    initial_cost = fhe_env.initial_cost
    done = False
    steps = 0
    last_expr = None
    bad_count = 0
    while not done:
        last_expr = fhe_env.expression
        last_cost = fhe_env.current_cost
        obs_for_model = {
            k: v for k, v in obs.items()
            if not model_obs_keys or k in model_obs_keys or k in ("action_mask", "observation")
        }
        action, _ = model.predict(obs_for_model, deterministic=True)
        obs, rewards, dones, infos = env.step(action)
        # if rewards[0] < 0:
        #     bad_count += 1
        #     # on first bad decision, remember the expression
        #     if bad_count == 1:
        #         final_expr = last_expr
        # else:
        #     # any non-negative reward resets the streak
        #     bad_count = 0
        #     final_expr = None

        # # once we've seen 3 negatives in a row, capture and break
        # if bad_count >= 3:
        #     final_expr = last_expr
        #     break
        done = bool(dones[0])
        steps += 1
    # if final_expr is not None:
    #     last_expr = final_expr
    parsed = parse_sexpr(last_expr)
    vec_s = calc_vec_sizes(parsed)
    if vec_s:
        sz = vec_s[0]
        footer = f"{sz} {sz} 1 0"
    else:
        footer = "1 1 1 0"
    with open(output_file, "w") as f:
        f.write(last_expr + "\n" + footer + "\n")
    end_time = time.perf_counter()
    elapsed_seconds = end_time - start_time
    