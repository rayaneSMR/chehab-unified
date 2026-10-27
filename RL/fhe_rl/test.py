from stable_baselines3 import PPO
import sys, importlib, time, os, subprocess, tempfile
from pathlib import Path
from .utils import load_expressions, load_expressions_named, create_rules
from pytrs import parse_sexpr, calculate_cost
from .memory import MemoryEstimator, extra_metrics
from .config import get_env_class, get_policy_class
from .seal_noise_bound import BFVNoiseBoundError, BFVNoiseBoundVerifier
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.common.monitor import Monitor
import pandas as pd

DNN_BENCHMARKS = [
    "conv2d", "full_dnn", "cryptonets", "mlp", "lola", "lenet",
    "resnet20_relu", "resnet20_silu", "resnet34_relu", "resnet34_silu",
    "resnet50_relu", "resnet50_silu", "alexnet",
]

_Runner_EXE = "dnn_tensor_benchmarks_runner_bin"
_Runner_DIR = Path(__file__).resolve().parent.parent / "build" / "benchmarks" / "dnn_tensor"

def _resolve_expressions(expressions_file: str):
    """Accept either a dataset file path or a DNN benchmark name.

    Benchmark names are expanded into a one-expression dataset file by running
    the C++ runner and serializing the tensor graph to an S-expression.  Returns
    the (possibly new) expressions-file path.
    """
    name = Path(expressions_file).name
    if Path(expressions_file).is_file() or name not in DNN_BENCHMARKS:
        return expressions_file
    print(f"[test] DNN benchmark '{name}' -> materializing S-expression via C++ runner ...")
    return _materialize_benchmark_expressions(name)


def _materialize_benchmark_expressions(name: str, build_dir: Path = None, timeout: int = 900):
    """Run the C++ DNN runner to serialize a tensor-graph benchmark to an
    S-expression, and return a temp file with one ``<expression>:<name>`` line.

    This is the only place the C++ graph becomes an expression your Python
    evaluator understands, so name resolution is done here (no hand-written
    S-expression).  Returns a path that `load_expressions_named` can read.

    Raises FileNotFoundError if the runner binary is missing, or RuntimeError
    if the build/dump step fails.
    """
    exe = build_dir or _Runner_DIR
    runner = exe / _Runner_EXE
    if not runner.is_file():
        raise FileNotFoundError(
            f"DNN runner not found: {runner}. "
            "Build the runner first (cmake --build build --target dnn_tensor_benchmarks_runner_bin), "
            "or use --dataset with the pre-generated `dnn_full_benchmarks.txt`."
        )

    expr_file = exe.parent.parent / "expression.txt"  # runner CWD is exe.parent; writes ../expression.txt
    tmp = tempfile.mkdtemp(
        prefix="dnn_expr_",
        dir=str(Path(__file__).resolve().parent.parent / "test_results"),
    )

    try:
        proc = subprocess.run(
            [str(runner), "--benchmark", name, "--backend", "lattigo",
             "--optimizer", "original_rl", "--bsgs-base", "global"],
            cwd=str(runner.parent), text=True, capture_output=True, timeout=timeout,
        )
        if proc.returncode != 0 or not expr_file.is_file():
            raise RuntimeError(
                f"Runner failed for '{name}' rc={proc.returncode}: "
                f"{proc.stderr[-400:] or proc.stdout[-400:]}"
            )
        expr = " ".join(expr_file.read_text().split())
        out = Path(tmp) / f"{name}.txt"
        out.write_text(f"{expr}:{name}\n", encoding="utf-8")
        return str(out)
    finally:
        # The runner may overwrite shared `expression.txt` between benchmarks;
        # remove the temp working copy we created to keep the disk tidy.
        expr_file.unlink(missing_ok=True)


def test_agent(
    expressions_file: str,
    embeddings_model,
    model_filepath: str,
    noise_budget: int = 1500,
    budget_options: list = None,
    test_budgets: list = None,
    constraint_method: str = "lagrangian_od_ov",
    output_file: str = None,
):
    """Test a trained agent on benchmark expressions across multiple budgets.

    Parameters
    ----------
    expressions_file : str
        Path to the benchmark expressions file.
    embeddings_model : object
        The loaded embeddings model.
    model_filepath : str
        Path to the saved model (.zip).
    noise_budget : int
        Single budget for backward-compatible calls.
    budget_options : list
        Budget options the model was TRAINED on (needed for correct obs space).
    test_budgets : list
        Budgets to TEST on. If None, uses [noise_budget].
    constraint_method : str
        Constraint method the model was trained with (affects obs space).
    output_file : str
        Path for the output Excel file. If None, auto-generated.
    """
    expressions_file = _resolve_expressions(expressions_file)
    expressions = load_expressions(expressions_file)
    rules_p = "rules.txt"
    rot_p = "rotations_rules.txt"
    if not os.path.exists(rules_p):
        rules_p = os.path.join(os.path.dirname(os.path.dirname(__file__)), "rules.txt")
    if not os.path.exists(rot_p):
        rot_p = os.path.join(os.path.dirname(os.path.dirname(__file__)), "rotations_rules.txt")
    rules_list = create_rules(rules_p, rot_p if os.path.exists(rot_p) else None)
    rules_list["END"] = None
    max_positions = 16

    # Determine budgets to test
    if test_budgets is None:
        test_budgets = [noise_budget]

    # Budget options must match what the model was trained on (for obs space)
    if budget_options is None:
        budget_options = test_budgets  # Assume test budgets = train budgets

    # Create env with correct budget_options and constraint_method
    EnvCls = get_env_class()
    PolicyCls = get_policy_class()
    env = DummyVecEnv([
        lambda: Monitor(
            EnvCls(
                rules_list,
                expressions,
                max_positions=max_positions,
                embeddings_model=embeddings_model,
                budget_options=budget_options,
                constraint_method=constraint_method,
            )
        )
    ])

    # Load model
    model = PPO(policy=PolicyCls, env=env)
    sys.modules["fhe_rl_new"] = importlib.import_module("fhe_rl")
    model = model.load(model_filepath)
    noise_estimator = MemoryEstimator()

    all_results = []

    for budget in test_budgets:
        print(f"\n{'='*60}")
        print(f"  Testing with budget = {budget}")
        print(f"{'='*60}")

        # Set the budget for all episodes
        env.set_options({"budget": budget})

        for expr_idx in range(len(expressions)):
            obs = env.reset()

            wrapper = env.envs[0]
            fhe_env = wrapper.env

            test_expr = fhe_env.initial_expression
            initial_cost = fhe_env.initial_cost
            initial_noise = noise_estimator.estimate(parse_sexpr(test_expr))

            done = False
            steps = 0

            while not done:
                action, _ = model.predict(obs, deterministic=True)
                obs, rewards, dones, infos = env.step(action)
                done = bool(dones[0])
                steps += 1

            # Use info dict for terminal state (fhe_env may have been
            # auto-reset by DummyVecEnv when done=True).
            terminal = infos[0]
            last_expr = terminal["expression"]
            last_cost = terminal["cost"]
            final_noise = float(terminal["constraint_value"])
            cost_reduction = ((initial_cost - last_cost) / initial_cost * 100) if initial_cost > 0 else 0
            budget_violated = final_noise > budget

            all_results.append({
                "Budget": budget,
                "Expression #": expr_idx + 1,
                "Initial Expression": test_expr,
                "Final Expression": last_expr,
                "Initial Cost": initial_cost,
                "Final Cost": last_cost,
                "Cost Reduction (%)": round(cost_reduction, 2),
                "Initial RAM (MB)": round(initial_noise, 2),
                "Final RAM (MB)": round(final_noise, 2),
                "Budget Violated": budget_violated,
                "RAM Headroom (MB)": round(budget - final_noise, 2),
                "Steps": steps,
                **extra_metrics(test_expr, last_expr, initial_noise, final_noise, budget),
            })

            status = "VIOLATED" if budget_violated else "OK"
            print(f"  [{status}] Expr {expr_idx+1}: cost {initial_cost}->{last_cost} "
                  f"({cost_reduction:+.1f}%), RAM {initial_noise:.0f}->{final_noise:.0f}, "
                  f"margin={budget - final_noise:.0f}")

    # ── Write results to Excel ──────────────────────────────────────────
    df = pd.DataFrame(all_results)

    if output_file is None:
        job_id = os.environ.get("SLURM_JOB_ID", "jobid")
        model_name = os.path.basename(model_filepath).replace(".zip", "")
        output_file = f"test_results_{model_name}.xlsx"

    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        # Full results sheet
        df.to_excel(writer, sheet_name="all_results", index=False)

        # Summary per budget
        summary_rows = []
        for budget in test_budgets:
            bdf = df[df["Budget"] == budget]
            summary_rows.append({
                "Budget": budget,
                "Num Expressions": len(bdf),
                "Avg Cost Reduction (%)": round(bdf["Cost Reduction (%)"].mean(), 2),
                "Avg Final RAM (MB)": round(bdf["Final RAM (MB)"].mean(), 2),
                "Violations": int(bdf["Budget Violated"].sum()),
                "Violation Rate (%)": round(bdf["Budget Violated"].mean() * 100, 1),
                "Avg RAM Headroom (MB)": round(bdf["RAM Headroom (MB)"].mean(), 2),
                "Avg Steps": round(bdf["Steps"].mean(), 1),
                "Started Infeasible (%)": round(bdf["Started Infeasible"].mean() * 100, 1),
                "Recovered (count)": int(bdf["Recovered"].sum()),
                "Avg RAM Expansion (%)": round(bdf["RAM Expansion (%)"].mean(), 2),
            })
        pd.DataFrame(summary_rows).to_excel(writer, sheet_name="summary_per_budget", index=False)

    print(f"\n{'='*60}")
    print(f"Results written to: {output_file}")
    print(f"  - Sheet 'all_results': {len(all_results)} rows (expressions x budgets)")
    print(f"  - Sheet 'summary_per_budget': {len(test_budgets)} rows")
    print(f"{'='*60}")

    # Print summary table
    print(f"\n  {'Budget':>10}  {'Violations':>10}  {'Avg Cost Red%':>14}  {'Avg RAM (MB)':>10}")
    print(f"  {'-'*50}")
    for s in summary_rows:
        print(f"  {s['Budget']:>10}  {s['Violations']:>10}  {s['Avg Cost Reduction (%)']:>14.1f}  {s['Avg Final RAM (MB)']:>10.1f}")


# ═══════════════════════════════════════════════════════════════════════════════
#  test_agent_v2 — Trajectory Checkpointing + Safety Rollback + Feasible Split
# ═══════════════════════════════════════════════════════════════════════════════

def _get_split_costs(expr_str):
    try:
        parsed = parse_sexpr(expr_str)
        ops = calculate_cost(parsed, w_keys=0.0)
        keys = calculate_cost(parsed, w_keys=1.0) - ops
        return float(ops), float(keys)
    except Exception:
        return 0.0, 0.0


def _run_single_episode(
    model,
    env,
    expr_str: str,
    budget: float,
    noise_estimator,
    bfv_noise_bound_verifier=None,
    constraint_metric: str = "mem",
):
    t0 = time.perf_counter()
    env.set_options({"budget": budget, "expression": expr_str})
    obs = env.reset()

    wrapper = env.envs[0]
    fhe_env = wrapper.env

    test_expr = fhe_env.expression
    initial_cost = fhe_env.initial_cost
    initial_noise = float(getattr(fhe_env, "curr_constraint", None) or noise_estimator.estimate(parse_sexpr(test_expr)))

    checkpoints = [{
        "step": 0,
        "expression": test_expr,
        "cost": initial_cost,
        "noise": initial_noise,
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

    rl_time_ms = (time.perf_counter() - t0) * 1000
    agent_final = checkpoints[-1]

    # Safety rollback: pick best valid checkpoint (lowest cost among valid)
    valid_checkpoints = [cp for cp in checkpoints if cp["noise"] <= budget]
    certificate = None
    if constraint_metric == "noise" and bfv_noise_bound_verifier is not None:
        best = None
        for checkpoint in sorted(valid_checkpoints, key=lambda cp: cp["cost"]):
            candidate_certificate = bfv_noise_bound_verifier.BFV_noise_bound(checkpoint["expression"])
            if candidate_certificate.decryptable and candidate_certificate.remaining_noise_budget_bits > 0:
                best = checkpoint
                certificate = candidate_certificate
                break
    elif valid_checkpoints:
        best = min(valid_checkpoints, key=lambda cp: cp["cost"])
    else:
        best = None

    if best is not None:
        safe_expr = best["expression"]
        safe_cost = best["cost"]
        safe_noise = best["noise"]
        best_valid_step = best["step"]
        safety_activated = (best["step"] != agent_final["step"])
    else:
        if constraint_metric == "noise" and bfv_noise_bound_verifier is not None:
            initial_certificate = bfv_noise_bound_verifier.BFV_noise_bound(test_expr)
            if not initial_certificate.decryptable or initial_certificate.remaining_noise_budget_bits <= 0:
                raise BFVNoiseBoundError("no rollback checkpoint has a positive certified BFV remaining noise budget")
            certificate = initial_certificate
        safe_expr = test_expr
        safe_cost = initial_cost
        safe_noise = initial_noise
        best_valid_step = 0
        safety_activated = True

    return {
        "initial_expr": test_expr,
        "initial_cost": initial_cost,
        "initial_noise": initial_noise,
        "agent_final": agent_final,
        "safe_expr": safe_expr,
        "safe_cost": safe_cost,
        "safe_noise": safe_noise,
        "best_valid_step": best_valid_step,
        "safety_activated": safety_activated,
        "steps": steps,
        "elapsed_ms": rl_time_ms,
        "checkpoints": checkpoints,
        "certificate": certificate,
    }


def test_agent_v2(
    expressions_file: str,
    embeddings_model,
    model_filepath: str,
    noise_budget: int = 1500,
    budget_options: list = None,
    test_budgets: list = None,
    constraint_method: str = "nato_sc",
    constraint_metric: str = "mem",
    bfv_noise_bound_verifier=None,
    output_file: str = None,
    save_optimized: str = None,
    pipeline: str = "joint",
    model_stage2_filepath: str = None,
):
    """Test with trajectory checkpointing, safety rollback, and feasible/infeasible split.

    Supports both 'joint' (single-agent pass) and 'separated' (Stage 1 ops -> Stage 2 rotations)
    pipeline architectures.
    """
    expressions_file = _resolve_expressions(expressions_file)
    named_pairs = load_expressions_named(expressions_file)
    expr_names = [name for _, name in named_pairs]
    expressions = [expr for expr, _ in named_pairs]

    rules_p = "rules.txt"
    rot_p = "rotations_rules.txt"
    if not os.path.exists(rules_p):
        rules_p = os.path.join(os.path.dirname(os.path.dirname(__file__)), "rules.txt")
    if not os.path.exists(rot_p):
        rot_p = os.path.join(os.path.dirname(os.path.dirname(__file__)), "rotations_rules.txt")

    max_positions = 16

    if test_budgets is None:
        test_budgets = [noise_budget]
    if budget_options is None:
        budget_options = test_budgets

    EnvCls = get_env_class()
    PolicyCls = get_policy_class()
    sys.modules["fhe_rl_new"] = importlib.import_module("fhe_rl")
    noise_estimator = MemoryEstimator()
    if constraint_metric == "noise" and bfv_noise_bound_verifier is None:
        bfv_noise_bound_verifier = BFVNoiseBoundVerifier.from_environment()

    if pipeline == "separated":
        if not model_stage2_filepath:
            raise ValueError(
                "Separated pipeline evaluation requires --model-stage2 pointing to the Stage 2 rotations model .zip"
            )
        print(f"\n{'='*60}")
        print(f"  SEPARATED PIPELINE EVALUATION")
        print(f"  Stage 1 (Ops) Model:       {model_filepath}")
        print(f"  Stage 2 (Rotations) Model: {model_stage2_filepath}")
        print(f"{'='*60}")

        rules_list_ops = create_rules(rules_p, rot_p if os.path.exists(rot_p) else None, rules_subset="ops")
        rules_list_ops["END"] = None
        env_ops = DummyVecEnv([
            lambda: Monitor(
                EnvCls(
                    rules_list_ops,
                    expressions,
                    max_positions=max_positions,
                    embeddings_model=embeddings_model,
                    budget_options=budget_options,
                    constraint_method=constraint_method,
                    constraint_metric=constraint_metric,
                )
            )
        ])
        model_ops = PPO(policy=PolicyCls, env=env_ops).load(model_filepath)

        rules_list_rot = create_rules(rules_p, rot_p if os.path.exists(rot_p) else None, rules_subset="rotations")
        rules_list_rot["END"] = None
        env_rot = DummyVecEnv([
            lambda: Monitor(
                EnvCls(
                    rules_list_rot,
                    expressions,
                    max_positions=max_positions,
                    embeddings_model=embeddings_model,
                    budget_options=budget_options,
                    constraint_method=constraint_method,
                    constraint_metric=constraint_metric,
                )
            )
        ])
        model_rot = PPO(policy=PolicyCls, env=env_rot).load(model_stage2_filepath)
    else:
        print(f"\n{'='*60}")
        print(f"  JOINT PIPELINE EVALUATION (All Rules)")
        print(f"  Model: {model_filepath}")
        print(f"{'='*60}")

        rules_list = create_rules(rules_p, rot_p if os.path.exists(rot_p) else None, rules_subset="all")
        rules_list["END"] = None
        env = DummyVecEnv([
            lambda: Monitor(
                EnvCls(
                    rules_list,
                    expressions,
                    max_positions=max_positions,
                    embeddings_model=embeddings_model,
                    budget_options=budget_options,
                    constraint_method=constraint_method,
                    constraint_metric=constraint_metric,
                )
            )
        ])
        model = PPO(policy=PolicyCls, env=env).load(model_filepath)

    all_results = []

    for budget in test_budgets:
        print(f"\n{'='*60}")
        print(f"  Testing ({pipeline}) with budget = {budget}")
        print(f"{'='*60}")

        total_exprs = len(expressions)
        for expr_idx in range(total_exprs):
            expr_name = expr_names[expr_idx] if expr_idx < len(expr_names) else f"expr_{expr_idx}"
            test_expr = expressions[expr_idx]
            initial_noise = float(noise_estimator.estimate(parse_sexpr(test_expr)))
            is_feasible = initial_noise <= budget
            initial_ops, initial_keys = _get_split_costs(test_expr)

            if pipeline == "separated":
                print(f"  [Budget {budget}] [{expr_idx+1}/{total_exprs}] '{expr_name}' -> Stage 1 (Ops)...", flush=True)
                res1 = _run_single_episode(model_ops, env_ops, test_expr, budget, noise_estimator, bfv_noise_bound_verifier, constraint_metric)
                stage1_safe_expr = res1["safe_expr"]
                stage1_ops, stage1_keys = _get_split_costs(stage1_safe_expr)

                print(f"  [Budget {budget}] [{expr_idx+1}/{total_exprs}] '{expr_name}' -> Stage 2 (Rotations)...", flush=True)
                res2 = _run_single_episode(model_rot, env_rot, stage1_safe_expr, budget, noise_estimator, bfv_noise_bound_verifier, constraint_metric)
                final_safe_expr = res2["safe_expr"]
                final_ops, final_keys = _get_split_costs(final_safe_expr)

                initial_cost = res1["initial_cost"]
                stage1_cost = res1["safe_cost"]
                safe_cost = res2["safe_cost"]
                safe_noise = res2["safe_noise"]
                agent_final = res2["agent_final"]
                total_steps = res1["steps"] + res2["steps"]
                total_time_ms = res1["elapsed_ms"] + res2["elapsed_ms"]
                safety_activated = res1["safety_activated"] or res2["safety_activated"]
                certificate = res2["certificate"] or res1["certificate"]

                agent_cr = ((initial_cost - agent_final["cost"]) / initial_cost * 100) if initial_cost > 0 else 0
                safe_cr = ((initial_cost - safe_cost) / initial_cost * 100) if initial_cost > 0 else 0
                ops_red = ((initial_ops - final_ops) / initial_ops * 100) if initial_ops > 0 else 0
                keys_red = ((initial_keys - final_keys) / max(initial_keys, 1) * 100)

                all_results.append({
                    "Pipeline": "separated",
                    "Budget": budget,
                    "Expression #": expr_idx + 1,
                    "Expression Name": expr_name,
                    "Is Feasible": is_feasible,
                    "Initial Cost": initial_cost,
                    "Initial Ops": initial_ops,
                    "Initial Keys": initial_keys,
                    "Initial RAM (MB)": round(initial_noise, 2),
                    "Stage1 Safe Cost": stage1_cost,
                    "Stage1 Safe Ops": stage1_ops,
                    "Stage1 Safe Keys": stage1_keys,
                    "Stage1 Safe RAM (MB)": round(res1["safe_noise"], 2),
                    "Stage1 Steps": res1["steps"],
                    "Stage1 Time (ms)": round(res1["elapsed_ms"], 1),
                    "Agent Final Cost": agent_final["cost"],
                    "Agent Final RAM (MB)": round(agent_final["noise"], 2),
                    "Agent Cost Reduction (%)": round(agent_cr, 2),
                    "Agent Violated": agent_final["noise"] > budget,
                    "Safe Final Cost": safe_cost,
                    "Safe Final Ops": final_ops,
                    "Safe Final Keys": final_keys,
                    "Safe Final RAM (MB)": round(safe_noise, 2),
                    "Safe Cost Reduction (%)": round(safe_cr, 2),
                    "Safe Ops Reduction (%)": round(ops_red, 2),
                    "Safe Keys Reduction (%)": round(keys_red, 2),
                    "Safe Violated": safe_noise > budget,
                    "Safety Activated": safety_activated,
                    "Best Valid Step": res2["best_valid_step"],
                    "Stage2 Steps": res2["steps"],
                    "Total Steps": total_steps,
                    "RL Time (ms)": round(total_time_ms, 1),
                    "RAM Headroom (MB)": round(budget - safe_noise, 2),
                    "BFV Bound Remaining Budget (bits)": (
                        certificate.remaining_noise_budget_bits if certificate is not None else None
                    ),
                    "_stage1_expr": stage1_safe_expr,
                    "_safe_expr": final_safe_expr,
                    **extra_metrics(test_expr, agent_final["expression"], initial_noise, agent_final["noise"], budget),
                    **extra_metrics(test_expr, final_safe_expr, initial_noise, safe_noise, budget, prefix="Safe "),
                })
            else:
                print(f"  [Budget {budget}] [{expr_idx+1}/{total_exprs}] Evaluating '{expr_name}'...", flush=True)
                res = _run_single_episode(model, env, test_expr, budget, noise_estimator, bfv_noise_bound_verifier, constraint_metric)
                initial_cost = res["initial_cost"]
                agent_final = res["agent_final"]
                safe_expr = res["safe_expr"]
                safe_cost = res["safe_cost"]
                safe_noise = res["safe_noise"]
                safety_activated = res["safety_activated"]
                best_valid_step = res["best_valid_step"]
                steps = res["steps"]
                rl_time_ms = res["elapsed_ms"]
                certificate = res["certificate"]
                final_ops, final_keys = _get_split_costs(safe_expr)

                agent_cr = ((initial_cost - agent_final["cost"]) / initial_cost * 100) if initial_cost > 0 else 0
                safe_cr = ((initial_cost - safe_cost) / initial_cost * 100) if initial_cost > 0 else 0
                ops_red = ((initial_ops - final_ops) / initial_ops * 100) if initial_ops > 0 else 0
                keys_red = ((initial_keys - final_keys) / max(initial_keys, 1) * 100)

                all_results.append({
                    "Pipeline": "joint",
                    "Budget": budget,
                    "Expression #": expr_idx + 1,
                    "Expression Name": expr_name,
                    "Is Feasible": is_feasible,
                    "Initial Cost": initial_cost,
                    "Initial Ops": initial_ops,
                    "Initial Keys": initial_keys,
                    "Initial RAM (MB)": round(initial_noise, 2),
                    "Agent Final Cost": agent_final["cost"],
                    "Agent Final RAM (MB)": round(agent_final["noise"], 2),
                    "Agent Cost Reduction (%)": round(agent_cr, 2),
                    "Agent Violated": agent_final["noise"] > budget,
                    "Safe Final Cost": safe_cost,
                    "Safe Final Ops": final_ops,
                    "Safe Final Keys": final_keys,
                    "Safe Final RAM (MB)": round(safe_noise, 2),
                    "Safe Cost Reduction (%)": round(safe_cr, 2),
                    "Safe Ops Reduction (%)": round(ops_red, 2),
                    "Safe Keys Reduction (%)": round(keys_red, 2),
                    "Safe Violated": safe_noise > budget,
                    "Safety Activated": safety_activated,
                    "Best Valid Step": best_valid_step,
                    "Total Steps": steps,
                    "RL Time (ms)": round(rl_time_ms, 1),
                    "RAM Headroom (MB)": round(budget - safe_noise, 2),
                    "BFV Bound Remaining Budget (bits)": (
                        certificate.remaining_noise_budget_bits if certificate is not None else None
                    ),
                    "Trajectory Costs": "|".join(str(cp["cost"]) for cp in res["checkpoints"]),
                    "Trajectory RAM (MB)": "|".join(f'{cp["noise"]:.2f}' for cp in res["checkpoints"]),
                    "_safe_expr": safe_expr,
                    **extra_metrics(test_expr, agent_final["expression"], initial_noise, agent_final["noise"], budget),
                    **extra_metrics(test_expr, safe_expr, initial_noise, safe_noise, budget, prefix="Safe "),
                })

            tag = "FEASIBLE" if is_feasible else "INFEAS"
            safe_tag = "SAFE" if safe_noise <= budget else "VIOL"
            print(f"  [{tag}][{safe_tag}] [{expr_idx+1}/{total_exprs}] '{expr_name}': "
                  f"cost {initial_cost}->{safe_cost} ({safe_cr:+.1f}%), "
                  f"ops {initial_ops}->{final_ops} ({ops_red:+.1f}%), "
                  f"keys {initial_keys}->{final_keys} ({keys_red:+.1f}%), "
                  f"RAM {initial_noise:.1f}->{safe_noise:.1f} MB, "
                  f"safety={'ON' if safety_activated else 'off'}", flush=True)

            # Progressive Excel save (never lose completed expressions)
            if output_file and all_results:
                try:
                    excel_results = [{k: v for k, v in r.items() if not k.startswith("_")} for r in all_results]
                    pd.DataFrame(excel_results).to_excel(output_file, index=False)
                except Exception:
                    pass

    # ── Write results to Excel and CSV ──────────────────────────────────
    excel_results = [{k: v for k, v in r.items() if not k.startswith("_")} for r in all_results]
    df = pd.DataFrame(excel_results)

    if output_file is None:
        job_id = os.environ.get("SLURM_JOB_ID", "jobid")
        model_name = os.path.basename(model_filepath).replace(".zip", "")
        output_file = f"test_results_v2_{pipeline}_{model_name}.xlsx"

    csv_file = os.path.splitext(output_file)[0] + ".csv"
    try:
        df.to_csv(csv_file, index=False)
        print(f"Results CSV written to: {csv_file}")
    except Exception as e:
        print(f"Failed to write CSV: {e}")

    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="all_results", index=False)

        # Summary per budget (all expressions)
        summary_rows = []
        for b in test_budgets:
            bdf = df[df["Budget"] == b]
            summary_rows.append({
                "Budget": b,
                "Pipeline": pipeline,
                "Num Expressions": len(bdf),
                "Feasible Count": int(bdf["Is Feasible"].sum()),
                "Infeasible Count": int((~bdf["Is Feasible"]).sum()),
                "Safe Avg Cost Red (%)": round(bdf["Safe Cost Reduction (%)"].mean(), 2),
                "Safe Avg Ops Red (%)": round(bdf["Safe Ops Reduction (%)"].mean(), 2),
                "Safe Avg Keys Red (%)": round(bdf["Safe Keys Reduction (%)"].mean(), 2),
                "Safe Violations": int(bdf["Safe Violated"].sum()),
                "Safe Violation Rate (%)": round(bdf["Safe Violated"].mean() * 100, 1),
                "Safety Activations": int(bdf["Safety Activated"].sum()),
                "Avg RAM Headroom (MB)": round(bdf["RAM Headroom (MB)"].mean(), 2),
                "Avg RL Time (s)": round(bdf["RL Time (ms)"].mean() / 1000.0, 2),
            })
        pd.DataFrame(summary_rows).to_excel(writer, sheet_name="summary_per_budget", index=False)

        # Feasible-only summary (primary metric for paper)
        feasible_rows = []
        for b in test_budgets:
            fdf = df[(df["Budget"] == b) & (df["Is Feasible"])]
            if len(fdf) == 0:
                continue
            feasible_rows.append({
                "Budget": b,
                "Pipeline": pipeline,
                "Feasible Expressions": len(fdf),
                "Safe Avg Cost Red (%)": round(fdf["Safe Cost Reduction (%)"].mean(), 2),
                "Safe Avg Ops Red (%)": round(fdf["Safe Ops Reduction (%)"].mean(), 2),
                "Safe Avg Keys Red (%)": round(fdf["Safe Keys Reduction (%)"].mean(), 2),
                "Safe Violations": int(fdf["Safe Violated"].sum()),
                "Safe Violation Rate (%)": round(fdf["Safe Violated"].mean() * 100, 1),
                "Safety Activations": int(fdf["Safety Activated"].sum()),
                "Avg Safe RAM Headroom (MB)": round(fdf["RAM Headroom (MB)"].mean(), 2),
                "Avg RL Time (s)": round(fdf["RL Time (ms)"].mean() / 1000.0, 2),
            })
        if feasible_rows:
            pd.DataFrame(feasible_rows).to_excel(writer, sheet_name="feasible_summary", index=False)

        # Infeasible-only summary
        infeasible_rows = []
        for b in test_budgets:
            idf = df[(df["Budget"] == b) & (~df["Is Feasible"])]
            if len(idf) == 0:
                continue
            infeasible_rows.append({
                "Budget": b,
                "Pipeline": pipeline,
                "Infeasible Expressions": len(idf),
                "Agent Avg Cost Red (%)": round(idf["Agent Cost Reduction (%)"].mean(), 2),
                "Agent Avg Final RAM (MB)": round(idf["Agent Final RAM (MB)"].mean(), 2),
                "Safe Avg Cost Red (%)": round(idf["Safe Cost Reduction (%)"].mean(), 2),
                "Avg RAM Increase (MB)": round((idf["Agent Final RAM (MB)"] - idf["Initial RAM (MB)"]).mean(), 2),
            })
        if infeasible_rows:
            pd.DataFrame(infeasible_rows).to_excel(writer, sheet_name="infeasible_summary", index=False)

    print(f"\n{'='*60}")
    print(f"Results (v2, {pipeline}) written to: {output_file}")
    print(f"  - Sheet 'all_results': {len(all_results)} rows")
    print(f"  - Sheet 'summary_per_budget': {len(test_budgets)} budgets")
    if feasible_rows:
        print(f"  - Sheet 'feasible_summary': {len(feasible_rows)} budgets (primary metric)")
    print(f"{'='*60}")

    # Print feasible summary table
    if feasible_rows:
        print(f"\n  FEASIBLE pairs (primary metric) - Pipeline: {pipeline}:")
        print(f"  {'Budget':>10}  {'N':>4}  {'SafeCR%':>8}  {'SafeOps%':>9}  {'SafeKeys%':>10}  {'SafeViol%':>10}  {'SafetyON':>8}  {'Time(s)':>8}")
        print(f"  {'-'*75}")
        for r in feasible_rows:
            print(f"  {r['Budget']:>10}  {r['Feasible Expressions']:>4}  "
                  f"{r['Safe Avg Cost Red (%)']:>8.1f}  "
                  f"{r['Safe Avg Ops Red (%)']:>9.1f}  "
                  f"{r['Safe Avg Keys Red (%)']:>10.1f}  "
                  f"{r['Safe Violation Rate (%)']:>10.1f}  "
                  f"{r['Safety Activations']:>8}  "
                  f"{r['Avg RL Time (s)']:>8.2f}")

    # Save RL-optimized expressions for downstream compilation
    if save_optimized:
        best_per_expr = {}
        for r in all_results:
            name = r["Expression Name"]
            if name not in best_per_expr or r["Safe Cost Reduction (%)"] > best_per_expr[name]["Safe Cost Reduction (%)"]:
                best_per_expr[name] = r
        with open(save_optimized, "w") as f:
            for name, r in best_per_expr.items():
                idx = r["Expression #"] - 1
                safe_expr = r.get("_safe_expr", expressions[idx])
                f.write(f"{safe_expr}:{name}\n")
        print(f"\nRL-optimized expressions saved to: {save_optimized}")
        print(f"  {len(best_per_expr)} expressions (best result per expression across budgets)")
