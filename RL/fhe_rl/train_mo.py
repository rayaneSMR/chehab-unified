import os
from stable_baselines3.common.vec_env import SubprocVecEnv, VecNormalize
from stable_baselines3.common.monitor import Monitor
from .config import get_env_class, get_policy_class
from stable_baselines3 import PPO
from .utils  import load_expressions, create_rules, load_embeddings
from .logger import log_training_details
from stable_baselines3.common.vec_env import SubprocVecEnv, VecNormalize,DummyVecEnv
from .callbacks import linear_schedule, EntCoefScheduler, ParetoEvalCallback, UnifiedMetricsCallback
from stable_baselines3.common.callbacks import EvalCallback, CheckpointCallback


from .pareto import generate_pref_list

import random
import numpy as np
import torch

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

def train_agent_mo(expressions_file: str, embeddings_model, total_timesteps: int = 1_000_000, num_envs: int = 8, ent_coef: float = 0.1, seed: int = 42, 
                lambda_env: float = 0.0, lambda_kl: float = 0.0, n_cycle: int = 1, n_budget: int = 5, eval_freq: int = 10000,
                objective2: str = "keys", mem_backend: str = "gpu",
                budget_options: list = None, constraint_method: str = "lagrangian_od_ov", algo: str = "ppo",
                checkpoint_path: str = None, fresh_start: bool = False, n_pref: int = 11,
                rules_subset: str = "all"):
    set_random_seed(seed)
    N=2
    pref_list = generate_pref_list(N)
    benchmarks = load_expressions("./fhe_rl/datasets/benchmarks.txt") 
    expressions = load_expressions(expressions_file, benchmarks)
    max_positions = 16
    # Separated architecture: "ops" (stage 1), "rotations" (stage 2) or "all" (joint)
    rules_list  = create_rules("rules.txt", "rotations_rules.txt", rules_subset=rules_subset)
    rules_list["END"] = None
    print(f"[Rules] Mode: {rules_subset.upper()} | Loaded {len(rules_list)} rules (including END)")
    job_id = os.environ.get("SLURM_JOB_ID", "jobid")
    subset_tag = f"_{rules_subset}" if rules_subset != "all" else ""
    run_name = f"model_{job_id}{subset_tag}"
    tensorboard_log_dir = f"./tensorboard/{run_name}"

    checkpoint_dir = f"./checkpoints/{run_name}"
    os.makedirs(checkpoint_dir, exist_ok=True)


    steps_done = 0
    import re
    _CKPT_RE = re.compile(r"^rl_model_(\d+)_steps\.zip$")

    if fresh_start:
        checkpoint_path = None
        print("[Resume] --fresh_start specified: starting fresh training from step 0 (ignoring existing checkpoints).")
    elif checkpoint_path:
        if not os.path.exists(checkpoint_path):
            raise FileNotFoundError(f"Specified checkpoint file not found: {checkpoint_path}")
        m = _CKPT_RE.match(os.path.basename(checkpoint_path))
        if m:
            steps_done = int(m.group(1))
        print(f"[Resume] Explicit checkpoint provided: {checkpoint_path} (step {steps_done:,})")
    else:
        candidates = []
        if os.path.exists(checkpoint_dir):
            for f in os.listdir(checkpoint_dir):
                m = _CKPT_RE.match(f)
                if m:
                    candidates.append((int(m.group(1)), os.path.join(checkpoint_dir, f)))
        if not candidates and os.path.exists("./checkpoints"):
            import glob
            for d in glob.glob("./checkpoints/model_*"):
                # Only resume runs of the same stage (ops / rotations / joint)
                name = os.path.basename(d)
                same_stage = name.endswith(subset_tag) if subset_tag else not name.endswith(("_ops", "_rotations"))
                if os.path.isdir(d) and same_stage:
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
            print("[Resume] No existing checkpoints found. Starting fresh training.")

    lambda_env = 0.0
    def make_env(rank, expressions):
        def _init():
            # Initialize frameworks properly in the subprocess
            import pytrs.config
            pytrs.config.framework = "morl"
            from .config import set_framework
            set_framework("mo")
            
            # Pass pref_list and rank to each env
            EnvCls = get_env_class()
            return Monitor(EnvCls(rules_list, expressions, max_positions=max_positions, embeddings_model=embeddings_model, 
                                  pref_list=pref_list, lambda_env=lambda_env, lambda_kl=lambda_kl, n_cycle=n_cycle, n_budget=n_budget, env_idx=rank,
                                  objective2=objective2, mem_backend=mem_backend))
        return _init  
    env = SubprocVecEnv([make_env(i, expressions) for i in range(num_envs)])
    env.seed(seed)     
    val_env = DummyVecEnv([make_env(0, benchmarks)])
    # MORL has no constraints: budget_options / constraint_method / algo are
    # accepted for backward compatibility but not used.
    if budget_options:
        print(f"[MORL] No constraints in this framework; ignoring budgets={budget_options}, method={constraint_method}, algo={algo}")
    ent_schedule = linear_schedule(0.1)
    ent_callback = EntCoefScheduler(ent_schedule, verbose=1)
    model_params = {
        "policy": get_policy_class(),
        "env": env,
        "learning_rate": 1e-4,
        "n_steps": 2048,
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
            "features_dim": 258,   # 256 expression embedding + 2 preference weights
            "rule_dim":      len(rules_list),
            "max_positions": max_positions,
            "rule_hidden_dims":   [64, 32],
            "pos_hidden_dims":    [32, 32],
            "value_hidden_dims":    [128, 64, 32],
            "seed": seed,
        }
    }

    if checkpoint_path:
        print(f"Loading model from checkpoint: {checkpoint_path}")
        model = PPO.load(checkpoint_path, env=env, tensorboard_log=tensorboard_log_dir)
    else:
        model = PPO(**model_params)

    log_training_details(
        model_params,
        job_id,
        num_data=len(expressions),
        num_actions=len(rules_list),
        total_timesteps=total_timesteps,
        output_model_name=run_name,
        notes="2 level hierarchical PPO max steps 75 and 8 envs"
    )
    num_benchmarks = len(benchmarks)

    checkpoint_callback = CheckpointCallback(
        save_freq=10000,
        save_path=checkpoint_dir,
        name_prefix="rl_model",
        save_replay_buffer=False,
        save_vecnormalize=True,
        verbose=1
    )

 

    pareto_eval_cb = ParetoEvalCallback(
        val_env, 
        pref_list=pref_list,
        best_model_save_path=f"./eval/best_model_{run_name}", 
        log_path=tensorboard_log_dir, 
        eval_freq=eval_freq, # Using the exposed parameter
        n_eval_episodes=num_benchmarks, # Replicating your parameter
        deterministic=True, 
        verbose=1
    )

    if checkpoint_path:
        remaining_steps = total_timesteps - steps_done
        print(f"Resuming training: {remaining_steps} steps remaining out of {total_timesteps} total")
    else:
        remaining_steps = total_timesteps
        print(f"Starting fresh training: {total_timesteps} total steps")

    


    unified_metrics_cb = UnifiedMetricsCallback(
        pid_wrapper=None, 
        total_timesteps=total_timesteps, 
        progress_freq=2000, 
        verbose=1
    )

    model.learn(
        total_timesteps=remaining_steps, 
        log_interval=1, 
        progress_bar=True, 
        callback=[ent_callback, pareto_eval_cb, checkpoint_callback, unified_metrics_cb],
        reset_num_timesteps = (checkpoint_path is None)
    )
    model.save(run_name)    