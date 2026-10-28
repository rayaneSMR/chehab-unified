import os
import random
import re
import signal
import time
import numpy as np
import torch
from stable_baselines3.common.vec_env import SubprocVecEnv, DummyVecEnv
from stable_baselines3.common.monitor import Monitor
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import CheckpointCallback

from .config import get_env_class, get_framework_spec, get_framework, get_wrapper_class
from .wrappers import (
    LagrangianVecEnvWrapper,
    LagrangianPerStepWrapper,
    LagrangianAlwaysDoneWrapper,
)

# Wrapper class for each Lagrangian variant (used when wrapper_class = "auto";
# constraint methods not listed here train without a wrapper).
WRAPPER_MAP = {
    "lagrangian_od_ov":        LagrangianVecEnvWrapper,
    "lagrangian_perstep":      LagrangianPerStepWrapper,
    "lagrangian_always_done":  LagrangianAlwaysDoneWrapper,
}
from .policy import HierarchicalMaskablePolicy
from .policy_film_b import HierarchicalMaskablePolicyFiLMB
from .utils import load_expressions, create_rules
from .logger import log_training_details
from .callbacks import linear_schedule, EntCoefScheduler, ParetoEvalCallback, UnifiedMetricsCallback
from .pareto import generate_pref_list

def set_random_seed(seed: int = 42):
    """Set random seed for reproducibility"""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    os.environ['PYTHONHASHSEED'] = str(seed)

def train_agent(
    expressions_file: str,
    embeddings_model,
    total_timesteps: int = 2_000_000,
    num_envs: int = 8,
    seed: int = 42,
    budget_options: list = None,
    constraint_method: str = "lagrangian_pid",
    constraint_metric: str = "mem",
    budget_encoding: str = "film",
    ent_coef: float = 0.01,
    algo: str = "ppo",
    lambda_env: float = 0.0,
    lambda_kl: float = 0.0,
    n_cycle: int = 1,
    n_budget: int = 5,
    policy_variant: str = "film_a",
    pref_mode: str = "pareto",
    denom_factor: int = 4,
    curriculum: bool = False,
    eval_freq: int = 10000,
    checkpoint_path: str = None,
    fresh_start: bool = False,
    n_pref: int = 11,
    embedder_type: str = "gnn",
    n_steps: int = 2048,
    rules_subset: str = "all",
):
    set_random_seed(seed)
    
    # Preferences (same as the original MORL separated experiment):
    # - Stage 1 (ops only): single-objective -> fixed speed focus w = [1.0, 0.0]
    # - Stage 2 (rotations only) and the joint agent: the normal preference list
    if rules_subset == "ops" or pref_mode == "single":
        pref_list = [[1.0, 0.0]]
        print(f"[Preferences] Single-objective / Stage 1 (Ops Agent): preference fixed to speed focus: {pref_list}")
    elif n_pref == 9:
        # Drop 2 least important extreme-keys vectors ([0.1, 0.9] and [0.2, 0.8])
        # Preserves speed focus [1.0, 0.0], balanced [0.5, 0.5], down to [0.3, 0.7] (8 vectors)
        all_prefs = generate_pref_list(11)
        pref_list = all_prefs[:-2]
        print(f"[Preferences] Using {len(pref_list)} preference vectors (dropped 2 least important extreme-keys vectors): {pref_list}")
    elif n_pref == 10:
        # Drop 1 least important extreme-keys vector ([0.1, 0.9])
        all_prefs = generate_pref_list(11)
        pref_list = all_prefs[:-1]
        print(f"[Preferences] Using {len(pref_list)} preference vectors (dropped 1 extreme-keys vector): {pref_list}")
    else:
        pref_list = generate_pref_list(n_pref)
        print(f"[Preferences] Generated {len(pref_list)} preference vectors (n_points={n_pref}): {pref_list}")

    # Resolve the env class in the PARENT process
    EnvCls = get_env_class()
    spec = get_framework_spec()
    pytrs_framework = spec["pytrs"]
    
    # Common setup
    benchmarks_file = "./fhe_rl/datasets/benchmarks.txt"
    if not os.path.exists(benchmarks_file):
        benchmarks_file = os.path.join(os.path.dirname(__file__), "datasets", "benchmarks.txt")
    benchmarks = load_expressions(benchmarks_file)

    if not os.path.exists(expressions_file):
        alt_expr = os.path.join(os.path.dirname(__file__), "datasets", os.path.basename(expressions_file))
        if os.path.exists(alt_expr):
            expressions_file = alt_expr
    expressions = load_expressions(expressions_file)

    max_positions = 16
    rules_p = "rules.txt"
    rot_p = "rotations_rules.txt"
    if not os.path.exists(rules_p):
        rules_p = os.path.join(os.path.dirname(os.path.dirname(__file__)), "rules.txt")
    if not os.path.exists(rot_p):
        rot_p = os.path.join(os.path.dirname(os.path.dirname(__file__)), "rotations_rules.txt")
    framework = get_framework()
    if framework == "constrained" and rules_subset != "ops":
        # The constrained framework has no access to rotation rules.
        print(f"[Rules] constrained framework: ignoring rules_subset='{rules_subset}', using 'ops' (no rotation rules)")
        rules_subset = "ops"
    rules_list = create_rules(rules_p, rot_p, rules_subset=rules_subset)
    rules_list["END"] = None
    print(f"[Rules] Mode: {rules_subset.upper()} | Loaded {len(rules_list)} rules (including END)")
    
    embedder_tag = "gnn" if "gnn" in str(embedder_type).lower() else "trae"
    job_id = os.environ.get("SLURM_JOB_ID", "jobid")
    subset_tag = f"_{rules_subset}" if rules_subset != "all" else ""
    run_name = f"model_{job_id}_{constraint_method}_{policy_variant}_{embedder_tag}{subset_tag}"
    tensorboard_log_dir = f"./tensorboard/{run_name}"
    checkpoint_dir = f"./checkpoints/{run_name}"
    os.makedirs(checkpoint_dir, exist_ok=True)

    # Checkpoint resumption: default is auto-resume from latest checkpoint for this config
    steps_done = 0
    _CKPT_RE = re.compile(r"^rl_model_(\d+)_steps\.zip$")

    if fresh_start:
        checkpoint_path = None
        print(f"[Resume] --fresh_start specified: starting fresh training from step 0 (ignoring existing checkpoints).")
    elif checkpoint_path:
        if not os.path.exists(checkpoint_path):
            raise FileNotFoundError(f"Specified checkpoint file not found: {checkpoint_path}")
        m = _CKPT_RE.match(os.path.basename(checkpoint_path))
        if m:
            steps_done = int(m.group(1))
        print(f"[Resume] Explicit checkpoint provided: {checkpoint_path} (step {steps_done:,})")
    else:
        # Auto-detect latest checkpoint across all matching runs
        candidates = []
        # 1. Search inside the current job's checkpoint dir
        if os.path.exists(checkpoint_dir):
            for f in os.listdir(checkpoint_dir):
                m = _CKPT_RE.match(f)
                if m:
                    candidates.append((int(m.group(1)), os.path.join(checkpoint_dir, f)))

        # 2. Search other run dirs matching this configuration (e.g. model_*_nato_sc_film_a)
        if os.path.exists("./checkpoints"):
            import glob
            config_pattern = f"./checkpoints/model_*_{constraint_method}_{policy_variant}_{embedder_tag}{subset_tag}"
            for d in glob.glob(config_pattern):
                if os.path.isdir(d):
                    for f in os.listdir(d):
                        m = _CKPT_RE.match(f)
                        if m:
                            candidates.append((int(m.group(1)), os.path.join(d, f)))

        if candidates:
            best_steps, best_file = max(candidates, key=lambda t: t[0])
            checkpoint_path = best_file
            steps_done = best_steps
            print(f"[Resume] Auto-detected latest checkpoint: {checkpoint_path}")
            print(f"[Resume] Resuming training from step {steps_done:,}")
        else:
            print(f"[Resume] No existing checkpoints found for '{constraint_method}_{policy_variant}'. Starting fresh training.")

    # Env options: only the unified env takes the MORL (preference) options;
    # the constrained env does not accept them.
    morl_env_kwargs = {}
    if framework == "unified":
        morl_env_kwargs = dict(
            pref_list=pref_list,
            lambda_env=lambda_env, lambda_kl=lambda_kl,
            n_cycle=n_cycle, n_budget=n_budget,
        )

    # Environment creation
    def make_env(rank, exprs, is_eval=False):
        def _init():
            np.random.seed(seed + rank)
            torch.manual_seed(seed + rank)
            torch.set_num_threads(1)
            try:
                import pytrs.config
                pytrs.config.framework = pytrs_framework
            except ImportError:
                pass
            worker_emb = embeddings_model
            if worker_emb is None:
                from .utils import load_embeddings_from_config
                worker_emb, _ = load_embeddings_from_config(embedder_type=embedder_type)
            extra = dict(morl_env_kwargs, env_idx=rank) if morl_env_kwargs else {}
            env = EnvCls(
                rules_list, exprs, max_positions=max_positions,
                embeddings_model=worker_emb,
                budget_options=budget_options,
                constraint_method=constraint_method,
                constraint_metric=constraint_metric,
                verbose=False,
                **extra,
            )
            return Monitor(env)
        return _init

    env = SubprocVecEnv([make_env(i, expressions) for i in range(num_envs)], start_method='spawn')
    pid_wrapper = None
    if algo == "lagrangian_pid" or constraint_method in ("lagrangian_pid", "lagrangian_pid_nato"):
        from .algos.lagrangian_pid import PIDLagrangianWrapper
        pid_wrapper = PIDLagrangianWrapper(env)
        env = pid_wrapper
        if checkpoint_path:
            pid_state_file = checkpoint_path.replace(".zip", "_pid.json")
            if os.path.exists(pid_state_file):
                pid_wrapper.load_state(pid_state_file)
                print(f"[Resume] Restored PID controller state from {pid_state_file}")
            else:
                print(f"[Resume] Note: PID state file {pid_state_file} not found; initializing fresh PID.")

    val_env = DummyVecEnv([make_env(0, benchmarks, is_eval=True)])
    val_env.seed(seed)

    # Lagrangian wrappers (lagrangian_od_ov / perstep / always_done).
    # "auto" picks the wrapper matching the constraint method; None disables
    # wrapping; a custom class from COMPONENT_CONFIG is used as-is.
    wrapper_setting = get_wrapper_class()
    if wrapper_setting == "auto":
        WrapperCls = WRAPPER_MAP.get(constraint_method)
    else:
        WrapperCls = wrapper_setting
    if WrapperCls is not None:
        env = WrapperCls(env)
        val_env = WrapperCls(val_env)
        print(f"[Constraint] Lagrangian wrapper: {WrapperCls.__name__}")
    # The lambda outer loop runs only when the wrapper exposes lambda updates.
    use_lagrange = hasattr(env, "update_lambda_penalty")

    # PPO model params
    ent_schedule = linear_schedule(ent_coef)
    ent_callback = EntCoefScheduler(ent_schedule, verbose=1)
    
    policy_cls = HierarchicalMaskablePolicyFiLMB if policy_variant == "film_b" else HierarchicalMaskablePolicy

    model_params = {
        "policy": policy_cls,
        "env": env,
        "learning_rate": 1e-4,
        "n_steps": n_steps,  # rollout = n_steps * num_envs samples per PPO update
        "batch_size": 256,
        "gamma": 0.99,
        "gae_lambda": 0.98,
        "n_epochs": 15,
        "clip_range": 0.1,
        "clip_range_vf": 0.2,
        "ent_coef": ent_coef,
        "verbose": 1,
        "tensorboard_log": tensorboard_log_dir,
        "seed": seed,
        "policy_kwargs": {
            "ent_coef": ent_coef,
            "budget_encoding": budget_encoding,
            "rule_dim": len(rules_list),
            "max_positions": max_positions,
            "rule_hidden_dims": [64, 32],
            "pos_hidden_dims": [32, 32],
            "value_hidden_dims": [128, 64, 32],
            "seed": seed,
        }
    }

    # Algorithm selection
    if algo == "focops":
        from .algos.focops import FOCOPS
        model = FOCOPS(**model_params, cost_limit=0.0, nu_lr=0.01, nu_max=10.0)
    else:
        if checkpoint_path:
            print(f"Loading model from checkpoint: {checkpoint_path}")
            # Pass n_steps explicitly: SB3 otherwise reuses the value stored in the checkpoint.
            model = PPO.load(checkpoint_path, env=env, tensorboard_log=tensorboard_log_dir, n_steps=n_steps)
        else:
            model = PPO(**model_params)

    log_training_details(
        model_params,
        job_id,
        num_data=len(expressions),
        num_actions=len(rules_list),
        total_timesteps=total_timesteps,
        output_model_name=run_name,
        notes=f"Algo: {algo} | Method: {constraint_method} | metric={constraint_metric} | budget_encoding={budget_encoding} | policy_variant={policy_variant} | embedder={embedder_tag} | num_envs={num_envs} | budgets={budget_options} | pref_mode={pref_mode}",
    )

    # Callbacks
    class PIDCheckpointCallback(CheckpointCallback):
        """CheckpointCallback that also saves PID controller state if present."""
        def __init__(self, *args, pid_wrapper=None, **kwargs):
            super().__init__(*args, **kwargs)
            self._pid_wrapper = pid_wrapper

        def _on_step(self) -> bool:
            res = super()._on_step()
            if self._pid_wrapper is not None and self.n_calls % self.save_freq == 0:
                pid_path = self._checkpoint_path(extension="json").replace("rl_model_", "rl_model_").replace(".json", "_pid.json")
                try:
                    self._pid_wrapper.save_state(pid_path)
                    if self.verbose >= 2:
                        print(f"Saved PID state to {pid_path}")
                except Exception as e:
                    print(f"Warning: could not save PID state to {pid_path}: {e}")
            return res

    checkpoint_callback = PIDCheckpointCallback(
        save_freq=max(40000 // num_envs, 1),  # counted in vec-env calls -> every ~40k timesteps
        save_path=checkpoint_dir,
        name_prefix="rl_model",
        save_replay_buffer=False,
        save_vecnormalize=False,
        verbose=1,
        pid_wrapper=pid_wrapper,
    )

    # Heartbeat file: lets HPC babysitting detect a frozen worker without
    # parsing multi-MB logs. Updated by the metrics callback below.
    heartbeat_path = os.path.join(checkpoint_dir, "heartbeat.json")
    try:
        with open(heartbeat_path, "w") as _hb:
            _hb.write('{"timesteps": %d, "time": %.1f, "run": "%s"}' % (steps_done, time.time(), run_name))
    except Exception:
        pass

    pareto_eval_cb = ParetoEvalCallback(
        val_env, 
        pref_list=pref_list,
        best_model_save_path=f"./eval/best_model_{run_name}", 
        log_path=tensorboard_log_dir, 
        eval_freq=eval_freq,
        n_eval_episodes=len(benchmarks),
        deterministic=True, 
        verbose=1
    )

    # Training execution
    if checkpoint_path:
        remaining_steps = total_timesteps - steps_done
        print(f"Resuming training: {remaining_steps} steps remaining out of {total_timesteps} total")
    else:
        remaining_steps = total_timesteps
        print(f"Starting fresh training: {total_timesteps} total steps")

    unified_metrics_cb = UnifiedMetricsCallback(pid_wrapper=pid_wrapper, total_timesteps=total_timesteps, progress_freq=2000, verbose=1)

    # Heartbeat alongside every progress line, gated to progress_freq (writes
    # on EVERY vecenv step would be 625k file writes over a 5M-step run).
    _orig_progress_step = unified_metrics_cb._on_step
    _hb_state = {"last_write": -1}
    def _on_step_with_heartbeat():
        ok = _orig_progress_step()
        nts = int(unified_metrics_cb.num_timesteps)
        if nts - _hb_state["last_write"] < unified_metrics_cb.progress_freq:
            return ok
        _hb_state["last_write"] = nts
        try:
            with open(heartbeat_path, "w") as _hb:
                _hb.write('{"timesteps": %d, "time": %.1f, "run": "%s"}' % (
                    nts, time.time(), run_name))
        except Exception:
            pass
        return ok
    unified_metrics_cb._on_step = _on_step_with_heartbeat

    # Graceful SIGTERM: SLURM sends TERM before KILL (see --signal in sbatch).
    # Save an emergency checkpoint so scancel/timeout never loses everything.
    _term_state = {"hit": False}
    def _handle_term(signum, frame):
        if _term_state["hit"]:
            return
        _term_state["hit"] = True
        try:
            emg = os.path.join(checkpoint_dir, "rl_model_emergency.zip")
            model.save(emg)
            print(f"\n[SIGTERM] emergency checkpoint saved to {emg}", flush=True)
        except Exception as e:
            print(f"\n[SIGTERM] emergency save failed: {e}", flush=True)
    try:
        signal.signal(signal.SIGTERM, _handle_term)
    except Exception:
        pass

    callbacks = [ent_callback, pareto_eval_cb, checkpoint_callback, unified_metrics_cb]
    if use_lagrange:
        _train_lagrangian_loop(
            model, env, val_env,
            total_timesteps=remaining_steps,
            n_steps=n_steps,
            num_envs=num_envs,
            denom_factor=denom_factor,
            num_benchmarks=len(benchmarks),
            callbacks=callbacks,
            tensorboard_log_dir=tensorboard_log_dir,
            reset_num_timesteps=(checkpoint_path is None),
        )
    else:
        model.learn(
            total_timesteps=remaining_steps,
            log_interval=1,
            progress_bar=True,
            callback=callbacks,
            reset_num_timesteps=(checkpoint_path is None)
        )

    model.save(run_name)
    print(f"\nModel saved as: {run_name}")


def _train_lagrangian_loop(
    model, env, val_env, *,
    total_timesteps, n_steps, num_envs, denom_factor,
    num_benchmarks, callbacks, tensorboard_log_dir,
    reset_num_timesteps=True,
):
    """Lagrangian PPO outer loop (from the original constrained repo):
    train a chunk -> run the benchmarks -> update lambda -> repeat."""
    from torch.utils.tensorboard import SummaryWriter
    tensorboard_writer = SummaryWriter(tensorboard_log_dir)

    lagrange_iterations = total_timesteps // ((n_steps * num_envs) * denom_factor)
    lagrange_iterations = max(1, lagrange_iterations)
    timesteps_per_iter = total_timesteps // lagrange_iterations

    print(f"Lagrangian loop: {lagrange_iterations} iterations x {timesteps_per_iter:,} timesteps each")

    for lagrange_iteration in range(lagrange_iterations):
        model.learn(
            total_timesteps=timesteps_per_iter,
            reset_num_timesteps=(reset_num_timesteps and lagrange_iteration == 0),
            log_interval=1,
            progress_bar=True,
            callback=callbacks,
        )

        # ── Evaluate the constraint on the validation benchmarks ──────────
        total_value = 0.0
        for _ in range(num_benchmarks):
            obs = val_env.reset()
            done, ep_value, ep_budget = False, 0.0, None
            while not done:
                action, _ = model.predict(obs, deterministic=True)
                obs, reward, dones, infos = val_env.step(action)
                done = bool(dones[0])
                ep_value = infos[0].get("constraint_value", 0.0)
                ep_budget = infos[0].get("budget", ep_budget)
            total_value += ep_value

            # Update lambda on both train and val wrappers
            val_env.update_lambda_penalty(constraint_value=ep_value, budget=ep_budget)
            env.update_lambda_penalty(constraint_value=ep_value, budget=ep_budget)

        lambda_penalty = val_env.lambda_penalty
        avg_value = total_value / max(num_benchmarks, 1)

        print(f"[Step {model.num_timesteps}] Avg constraint value: {avg_value:.2f}, "
              f"λ: {lambda_penalty:.3f}")
        tensorboard_writer.add_scalar("Lagrange/lambda_penalty", lambda_penalty, model.num_timesteps)
        tensorboard_writer.add_scalar("Lagrange/avg_constraint", avg_value, model.num_timesteps)

    tensorboard_writer.close()
