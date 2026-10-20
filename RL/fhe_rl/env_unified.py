import os
import signal

import numpy as np
import gymnasium as gym
from gymnasium import spaces
from pytrs import parse_sexpr, calculate_cost, expr_to_str
import torch

from .config import get_tokenizer_type
from .memory import MemoryEstimator, rotation_steps
from pytrs import NoiseEstimator

if get_tokenizer_type() == "bpe":
    from .TRAE_bpe import get_expression_cls_embedding
else:
    from .TRAE import get_expression_cls_embedding

RESET   = "\033[0m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
RED     = "\033[31m"
GREEN   = "\033[32m"
YELLOW  = "\033[33m"
BLUE    = "\033[34m"
MAGENTA = "\033[35m"
CYAN    = "\033[36m"

UNCONSTRAINED_BUDGET_THRESHOLD = 100_000

# ── Watchdog around RewriteRule.apply_rule ──────────────────────────────────
# A de-rotate rule (or any pathological match) can grind for minutes inside
# _apply_rule_everywhere -> deep validate_expression on huge expressions,
# freezing the whole SubprocVecEnv (all 8 workers are synchronous). This
# watchdog converts such a stall into a soft invalid-action instead.
# FHE_APPLY_RULE_TIMEOUT_S: seconds (default 20; <=0 disables the watchdog).
_APPLY_RULE_TIMEOUT_S = float(os.environ.get("FHE_APPLY_RULE_TIMEOUT_S", "20"))


class _ApplyRuleTimeout(Exception):
    """Raised by the SIGALRM watchdog when apply_rule exceeds its budget."""


def _apply_rule_timeout_handler(signum, frame):
    raise _ApplyRuleTimeout("apply_rule exceeded watchdog timeout")


def _apply_rule_with_timeout(rule_obj, parsed, path, timeout_s):
    """Run rule_obj.apply_rule(parsed, path=path) under a SIGALRM watchdog.

    The alarm is always cancelled in finally. Falls back to a plain call when
    SIGALRM is unavailable (Windows) or we are not on the main thread (signal
    handlers can only be installed there). SubprocVecEnv workers each run the
    env on their own process' main thread, so the watchdog is active on HPC.
    """
    if timeout_s <= 0 or not hasattr(signal, "SIGALRM"):
        return rule_obj.apply_rule(parsed, path=path)
    try:
        old_handler = signal.signal(signal.SIGALRM, _apply_rule_timeout_handler)
    except ValueError:
        # Not main thread: cannot install handlers; run unprotected.
        return rule_obj.apply_rule(parsed, path=path)
    try:
        signal.setitimer(signal.ITIMER_REAL, timeout_s)
        return rule_obj.apply_rule(parsed, path=path)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)      # always cancel the alarm
        signal.signal(signal.SIGALRM, old_handler)   # always restore handler


class fheEnvUnified(gym.Env):
    """
    Unified FHE Optimization Environment:
    - Multi-Objective RL: Balances compute latency (ops) and rotation keys
    - Preference Conditioning: Biased cycling across preference vectors
    - Configurable Constraint: Supports 'mem' (Process Peak RAM in MB via calibrated model)
                               or 'noise' (Multiplicative depth / noise bits)
    - Full Constraint Integration: Compatible with NATO-SC quadratic penalty,
                                   margin barrier, and PID Lagrangian dual updates.
    """

    DEFAULT_MEM_BUDGETS = [1500, 2000, 2600, 1_000_000]
    DEFAULT_NOISE_BUDGETS = [230, 236, 369, 9_000_000]

    def __init__(
        self,
        rules_list,
        expressions,
        max_positions=16,
        embeddings_model=None,
        budget_options=None,
        constraint_method="lagrangian_pid",
        constraint_metric="mem",
        verbose=True,
        pref_list=None,
        lambda_env=0.0,
        lambda_kl=0.0,
        n_cycle=1,
        n_budget=5,
        env_idx=0,
    ):
        super().__init__()

        self.rules = rules_list
        self.expressions = expressions
        self.max_positions = max_positions
        self.embeddings_model = embeddings_model
        self.constraint_method = constraint_method
        self.constraint_metric = str(constraint_metric).lower().strip()
        self.verbose = verbose
        self.max_steps = 75
        self.max_expression_size = 10000
        self.embedding_dim = 256
        self.env_idx = env_idx
        self.embed_fallback_count = 0
        self._worker_logged = False

        # ── Deterministic memoization (bit-identical to recomputation) ──────
        # GNN embeddings and action masks are pure functions of the expression
        # string (budget additionally only for noise_masking) and never depend
        # on policy weights, so caching them is exactly equivalent to
        # recomputing. The GNN forward was ~85% of env.step wall time; caches
        # mainly make repeated evaluations (deterministic eval trajectories)
        # and recurrent expressions nearly free. Sized for 64 GB nodes:
        # ~50 MB embeddings + ~140 MB masks per worker process.
        self._EMB_CACHE_MAX = 50_000
        self._MASK_CACHE_MAX = 20_000
        self._emb_cache = {}
        self._mask_cache = {}

        # Clamping threads inside each worker environment to prevent thread contention
        torch.set_num_threads(1)

        # Construction-time assertion on embedding dimension for ANY embedder
        if self.embeddings_model is not None:
            if hasattr(self.embeddings_model, "get_embedding"):
                probe_raw = self.embeddings_model.get_embedding("(+ 1 1)")
                if probe_raw is None:
                    raise AssertionError(
                        f"Construction probe failed: Embedder {type(self.embeddings_model).__name__} returned None for '(+ 1 1)'"
                    )
                probe_arr = np.asarray(probe_raw, dtype=np.float32).reshape(-1)
            else:
                expr_tree = parse_sexpr("(+ 1 1)")
                with torch.no_grad():
                    probe_emb = get_expression_cls_embedding(expr_tree, self.embeddings_model)
                if probe_emb is None:
                    raise AssertionError(
                        f"Construction probe failed: Embedder {type(self.embeddings_model).__name__} returned None for '(+ 1 1)'"
                    )
                probe_arr = probe_emb.squeeze(0).cpu().numpy().astype(np.float32).reshape(-1)

            assert probe_arr.shape == (self.embedding_dim,), (
                f"Construction assertion failed: Embedder {type(self.embeddings_model).__name__} "
                f"output shape {probe_arr.shape} != ({self.embedding_dim},)"
            )
            assert np.all(np.isfinite(probe_arr)), (
                f"Construction assertion failed: Embedder {type(self.embeddings_model).__name__} produced non-finite values"
            )

        # Initialize constraint estimator & default budgets
        if self.constraint_metric == "mem":
            self.estimator = MemoryEstimator(margin=False)
            default_budgets = self.DEFAULT_MEM_BUDGETS
            self.metric_name = "Peak RAM"
            self.metric_unit = "MB"
        elif self.constraint_metric == "noise":
            self.estimator = NoiseEstimator()
            default_budgets = self.DEFAULT_NOISE_BUDGETS
            self.metric_name = "Noise"
            self.metric_unit = "bits"
        else:
            raise ValueError(f"Unknown constraint_metric: {constraint_metric}. Must be 'mem' or 'noise'.")

        self.noise_estimator = self.estimator  # Compatibility alias

        if budget_options is not None:
            self.budget_options = list(budget_options)
        else:
            self.budget_options = list(default_budgets)

        self.budget_dim = len(self.budget_options)
        self.active_budgets = list(self.budget_options)

        # MORL & Preference configuration
        self.n_cycle = n_cycle
        self.episode_count = 0
        if pref_list is None:
            pref_list = [[1.0, 0.0], [0.8, 0.2]]
        self.pref_list = [np.array(p, dtype=np.float32) for p in pref_list]
        self.current_pref_idx = env_idx % len(self.pref_list)
        self.current_w = self.pref_list[self.current_pref_idx]
        self.n_budget = n_budget
        self.lambda_kl = lambda_kl
        self.lambda_env = lambda_env
        self.pref_locked = False

        # State tracking
        self.initial_cost = 0
        self.current_cost = 0
        self.initial_ops = 0
        self.initial_keys = 0
        self.curr_ops = 0
        self.curr_keys = 0
        self.initial_constraint = 0.0
        self.curr_constraint = 0.0
        self._last_val = 0.0

        self.action_space = spaces.Discrete(len(self.rules.keys()) * self.max_positions)

        # Unified Observation Space
        obs_dict = {
            "observation": spaces.Box(low=-np.inf, high=np.inf, shape=(self.embedding_dim,), dtype=np.float32),
            "budget_one_hot_encoding": spaces.Box(low=0, high=1, shape=(self.budget_dim,), dtype=np.float32),
            "action_mask": spaces.Box(low=0, high=1, shape=(len(self.rules.keys()) * self.max_positions,), dtype=np.float32),
            "preference_vector": spaces.Box(low=0, high=1, shape=(2,), dtype=np.float32),
            "noise_ratio": spaces.Box(low=0, high=20, shape=(1,), dtype=np.float32),
        }
        if self.constraint_method == "margin_barrier":
            obs_dict["budget_margin"] = spaces.Box(low=-1, high=1, shape=(1,), dtype=np.float32)

        self.observation_space = spaces.Dict(obs_dict)

    def set_preference_vector(self, w):
        self.current_w = np.array(w, dtype=np.float32)
        self.pref_locked = True

    def unlock_preferences(self):
        self.pref_locked = False

    def get_split_costs(self, expr_str):
        parsed = parse_sexpr(expr_str)
        ops = calculate_cost(parsed, w_keys=0.0)
        keys = calculate_cost(parsed, w_keys=1.0) - ops
        return ops, keys

    def _sample_preference(self) -> tuple[np.ndarray, str]:
        if self.n_cycle > 0 and (self.episode_count % (self.n_cycle + 1)) < self.n_cycle:
            w = self.pref_list[0]
            mode_name = "SPEED FOCUS"
        else:
            idx = int(self.np_random.integers(0, len(self.pref_list)))
            w = self.pref_list[idx]
            mode_name = "BALANCED EXPLORATION"

        self.episode_count += 1
        return w, mode_name

    def _estimate(self, expr_str):
        try:
            val = float(self.estimator.estimate(expr_str))
            self._last_val = val
            return val
        except Exception:
            return getattr(self, "_last_val", 0.0)

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        if not hasattr(self, "current_index"):
            self.current_index = 0

        self.expression = self.expressions[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.expressions)
        self.initial_expression = self.expression
        self.steps = 0

        # Base costs
        self.initial_cost = self.current_cost = self.get_cost(self.expression)
        self.initial_ops, self.initial_keys = self.get_split_costs(self.expression)
        self.curr_ops, self.curr_keys = self.initial_ops, self.initial_keys

        # Budget sampling
        budget = int(self.np_random.choice(self.active_budgets))
        if isinstance(options, dict):
            budget = options.get("budget", budget)
        self.set_noise_budget(budget)

        self.initial_constraint = self.curr_constraint = self._estimate(self.expression)

        # Preference sampling
        if self.pref_locked:
            mode_name = "LOCKED (EVALUATION)"
        else:
            self.current_w, mode_name = self._sample_preference()
        self.current_mode_name = mode_name
        self._last_r_vec = np.array([0.0, 0.0], dtype=np.float32)

        if self.verbose:
            print(f"\n{BLUE}{'='*40} EPISODE START {'='*40}{RESET}")
            print(f"{BOLD}{MAGENTA}Optimization Mode    {RESET}: {CYAN}{mode_name}{RESET} (w=[ops={self.current_w[0]:.2f}, keys={self.current_w[1]:.2f}])")
            print(f"{BOLD}{MAGENTA}Initial Total Cost   {RESET}: {YELLOW}{self.initial_cost}{RESET}")
            print(f"{BOLD}{MAGENTA}Initial Exec Cost    {RESET}: {YELLOW}{self.initial_ops}{RESET}")
            print(f"{BOLD}{MAGENTA}Initial Keys Cost    {RESET}: {YELLOW}{self.initial_keys}{RESET}")
            print(f"{BOLD}{MAGENTA}{self.metric_name} Budget     {RESET}: {CYAN}{self.budget} {self.metric_unit}{RESET}")
            print(f"{BOLD}{MAGENTA}Initial {self.metric_name:<13}{RESET}: {YELLOW}{self.initial_constraint:.1f} {self.metric_unit}{RESET}")

        obs = self._get_obs(self.curr_constraint)
        return obs, {
            "expression": self.expression,
            "budget": self.budget,
            "constraint_value": self.curr_constraint,
            "noise": self.curr_constraint,
            "cost": self.current_cost,
            "initial_cost": self.initial_cost,
            "c_exec": self.curr_ops,
            "initial_ops": self.initial_ops,
            "c_keys": self.curr_keys,
            "initial_keys": self.initial_keys,
            "rotation_keys": rotation_steps(self.expression),
            "preference_vector": self.current_w,
            "mode_name": self.current_mode_name,
        }

    def _get_obs(self, constraint_val: float):
        embedding = self._embed_expression(self.expression)
        if embedding is None:
            embedding = np.zeros(self.embedding_dim, dtype=np.float32)

        w = np.atleast_1d(self.current_w).astype(np.float32)
        ratio = float(np.clip(constraint_val / max(self.budget, 1), 0.0, 20.0))

        obs = {
            "observation": embedding,
            "budget_one_hot_encoding": self.budget_one_hot_encoding,
            "action_mask": self.get_action_mask(),
            "preference_vector": w,
            "noise_ratio": np.array([ratio], dtype=np.float32),
        }

        if self.constraint_method == "margin_barrier":
            margin = np.clip((self.budget - constraint_val) / max(self.budget, 1), -1.0, 1.0)
            obs["budget_margin"] = np.array([margin], dtype=np.float32)

        return obs

    def step(self, action: int):
        # Rate-limited worker logging on first step from inside each worker
        if not getattr(self, "_worker_logged", False):
            self._worker_logged = True
            emb_cls = type(self.embeddings_model).__name__ if self.embeddings_model is not None else "None"
            print(
                f"[Worker {getattr(self, 'env_idx', 0)}] Embedder: {emb_cls} | "
                f"Dim: {self.embedding_dim} | Threads: {torch.get_num_threads()}",
                flush=True,
            )

        if self.current_w[0] == 0.0 and self.current_w[1] == 1.0:
            action = list(self.rules.keys()).index("END") * self.max_positions

        self.steps += 1
        rule_idx = action // self.max_positions
        pos_idx = action % self.max_positions
        rule_name = list(self.rules.keys())[rule_idx]
        terminated = False
        truncated = False
        reward = 0

        old_cost = self.current_cost
        old_ops = self.curr_ops
        old_keys = self.curr_keys
        old_constraint = self.curr_constraint
        old_expr = self.expression

        if self.verbose:
            print(f"\n{CYAN}{'-'*100}{RESET}")
            print(f"{BOLD}{MAGENTA}Old expression       {RESET}: {YELLOW}{old_expr}{RESET}")
            print(f"{BOLD}{MAGENTA}Old total cost       {RESET}: {RED}{old_cost}{RESET}")
            print(f"{BOLD}{MAGENTA}Old exec cost        {RESET}: {RED}{old_ops}{RESET}")
            print(f"{BOLD}{MAGENTA}Old keys cost        {RESET}: {RED}{old_keys}{RESET}")
            print(f"{BOLD}{MAGENTA}Old {self.metric_name:<17}{RESET}: {RED}{old_constraint:.1f} {self.metric_unit}{RESET}")

        if rule_name == "END":
            terminated = True
            truncated = False
            reward = self.calculate_final_reward()
            self.curr_constraint = self._estimate(self.expression)
        else:
            try:
                parsed = parse_sexpr(self.expression)
                rule_obj = self.rules[rule_name]
                matches = rule_obj.find_matching_subexpressions(parsed)
            except Exception as e:
                # Never kill a SubprocVecEnv worker on a bad expression/rule:
                # fall back to a safe no-op terminal transition.
                if self.verbose:
                    print(f"[env] step fallback (parse/match failed for {rule_name}): {type(e).__name__}: {e}")
                terminated = True
                reward = self.calculate_final_reward()
                obs = self._get_obs(self.curr_constraint)
                return obs, reward, terminated, True, self._step_info(reward, terminated, True)
            if not matches:
                # Mask should have excluded this; treat as invalid action with a
                # small penalty instead of raising (which would stall the worker).
                if self.verbose:
                    print(f"[env] invalid action: rule {rule_name} has no matches at pos {pos_idx}; penalizing")
                reward = -1.0
                obs = self._get_obs(self.curr_constraint)
                return obs, reward, False, False, self._step_info(reward, False, False)
            try:
                k, _ = matches[min(pos_idx, len(matches) - 1)]
                new_expr_tree = _apply_rule_with_timeout(
                    rule_obj, parsed, k, _APPLY_RULE_TIMEOUT_S)
                temp = expr_to_str(new_expr_tree)
            except _ApplyRuleTimeout:
                # Watchdog fired: treat the action as invalid, do NOT terminate
                # the episode (other rules remain usable next step).
                print(
                    f"[env] apply_rule timeout (>{_APPLY_RULE_TIMEOUT_S}s): "
                    f"rule={rule_name} expr_size={len(self.expression)}",
                    flush=True,
                )
                reward = -1.0
                obs = self._get_obs(self.curr_constraint)
                return obs, reward, False, False, self._step_info(reward, False, False)
            except Exception as e:
                if self.verbose:
                    print(f"[env] step fallback (apply_rule failed for {rule_name}): {type(e).__name__}: {e}")
                terminated = True
                reward = self.calculate_final_reward()
                obs = self._get_obs(self.curr_constraint)
                return obs, reward, terminated, True, self._step_info(reward, terminated, True)
            self.expression = temp

            try:
                new_cost = self.get_cost(self.expression)
                new_ops, new_keys = self.get_split_costs(self.expression)
            except Exception:
                new_cost, new_ops, new_keys = self.current_cost, self.curr_ops, self.curr_keys
            self.curr_constraint = self._estimate(self.expression)

            reward = self.calculate_intermediate_reward(new_ops, new_keys)

            self.curr_ops = new_ops
            self.curr_keys = new_keys
            self.current_cost = new_cost

            if self.steps >= self.max_steps:
                terminated = True
                reward = self.calculate_final_reward()

        if self.verbose:
            reward_color = GREEN if reward >= 0 else RED
            val_color = GREEN if self.curr_constraint <= self.budget else RED
            print(f"Episode: {self.episode_count} | Step: {self.steps}")
            print(f"{BOLD}{MAGENTA}New expression       {RESET}: {YELLOW}{self.expression}{RESET}")
            print(f"{BOLD}{MAGENTA}New total cost       {RESET}: {RED}{self.current_cost}{RESET}")
            print(f"{BOLD}{MAGENTA}New exec cost        {RESET}: {RED}{self.curr_ops}{RESET}")
            print(f"{BOLD}{MAGENTA}New keys cost        {RESET}: {RED}{self.curr_keys}{RESET}")
            print(f"{BOLD}{MAGENTA}New {self.metric_name:<17}{RESET}: {val_color}{self.curr_constraint:.1f} {self.metric_unit}{RESET} (Budget: {self.budget} {self.metric_unit})")
            print(f"{BOLD}{MAGENTA}Reward (scalar)      {RESET}: {reward_color}{reward:.4f}{RESET}")
            print(f"{BOLD}{MAGENTA}Reward vector        {RESET}: [r_exec={self._last_r_vec[0]:.4f}, r_keys={self._last_r_vec[1]:.4f}]")
            print(f"{BOLD}{MAGENTA}Preference w         {RESET}: [w_ops={self.current_w[0]:.2f}, w_keys={self.current_w[1]:.2f}]")
            print(f"{BOLD}{MAGENTA}Rule name            {RESET}: {CYAN}{rule_name}{RESET}")
            print(f"{BOLD}{MAGENTA}At position          {RESET}: {BLUE}{pos_idx}{RESET}")
            print(f"{CYAN}{'-'*100}{RESET}")

        # Fast-step optimization: _embed_expression NEVER returns None (it
        # returns a zeros fallback), so the old "embedding is None" branch was
        # dead code and this second GNN forward pass was redundant -- _get_obs()
        # below embeds the exact same expression. Only the max_steps guard from
        # the old else-branch is kept (it is also enforced above, right after
        # applying a non-END rule).
        terminated = terminated or (self.steps >= self.max_steps)

        # ── NATO-SC Terminal Quadratic Penalty ──
        if self.constraint_method in ("nato_sc", "lagrangian_pid_nato") and (terminated or truncated):
            cost_reward = self.calculate_final_reward()
            if self.curr_constraint > self.budget:
                violation_ratio = (self.curr_constraint - self.budget) / max(self.budget, 1)
                reward = cost_reward - 50.0 * (violation_ratio ** 2)
            else:
                if self.budget <= UNCONSTRAINED_BUDGET_THRESHOLD:
                    utilization = self.curr_constraint / max(self.budget, 1)
                    reward = cost_reward + utilization * 5.0
                else:
                    reward = cost_reward

        # ── Margin Barrier Hard Penalty ──
        if self.constraint_method == "margin_barrier" and (terminated or truncated):
            if self.curr_constraint > self.budget:
                reward = -100.0
            else:
                cost_reward = self.calculate_final_reward()
                if self.budget <= UNCONSTRAINED_BUDGET_THRESHOLD:
                    utilization = self.curr_constraint / max(self.budget, 1)
                    reward = cost_reward + utilization * 5.0
                else:
                    reward = cost_reward

        cost_red = ((self.initial_cost - self.current_cost) / max(self.initial_cost, 1e-6)) * 100.0
        ops_red = ((self.initial_ops - self.curr_ops) / max(self.initial_ops, 1e-6)) * 100.0
        keys_red = ((self.initial_keys - self.curr_keys) / max(self.initial_keys, 1e-6)) * 100.0
        is_compliant = bool(self.curr_constraint <= self.budget)

        info = self._step_info(reward, terminated, truncated)

        if terminated or truncated:
            info["episode"] = {"r": reward, "l": self.steps, "t": None}
            val_color = GREEN if is_compliant else RED
            status_str = f"{GREEN}COMPLIANT{RESET}" if is_compliant else f"{RED}VIOLATED (+{self.curr_constraint - self.budget:.1f} {self.metric_unit}){RESET}"

            if self.verbose:
                print(f"\n{BLUE}{'='*30} EPISODE {self.episode_count} SUMMARY {'='*30}{RESET}")
                print(f"{BOLD}{'Metric':<25} | {'Initial':<12} | {'Final':<12} | {'Change / Status'}{RESET}")
                print(f"{'-'*75}")
                print(f"{'Total Cost (Constrained)':<25} | {self.initial_cost:<12} | {self.current_cost:<12} | {cost_red:+.1f}%")
                print(f"{'Exec Cost (MORL Ops)':<25} | {self.initial_ops:<12} | {self.curr_ops:<12} | {ops_red:+.1f}%")
                print(f"{'Keys Cost (MORL Keys)':<25} | {self.initial_keys:<12} | {self.curr_keys:<12} | {keys_red:+.1f}%")
                print(f"{self.metric_name + ' (' + self.metric_unit + ')':<25} | {self.initial_constraint:<12.1f} | {self.curr_constraint:<12.1f} | {status_str}")
                print(f"{self.metric_name + ' Budget':<25} | {self.budget:<12} {self.metric_unit} | {'--':<12} | {'Margin: ' + str(round(self.budget - self.curr_constraint, 1)) + ' ' + self.metric_unit}")
                print(f"{'Preference Vector':<25} | w=[ops={self.current_w[0]:.2f}, keys={self.current_w[1]:.2f}] (Mode: {self.current_mode_name})")
                print(f"{'Episode Length':<25} | {self.steps} steps | Cumulative Reward: {reward:.4f}")
                print(f"{BLUE}{'='*77}{RESET}\n")

        obs = self._get_obs(self.curr_constraint)
        return obs, reward, terminated, truncated, info

    def _step_info(self, reward, terminated=False, truncated=False):
        """Build the step info dict; never raises (safe for early fallbacks)."""
        try:
            cost_red = ((self.initial_cost - self.current_cost) / max(self.initial_cost, 1e-6)) * 100.0
        except Exception:
            cost_red = 0.0
        try:
            ops_red = ((self.initial_ops - self.curr_ops) / max(self.initial_ops, 1e-6)) * 100.0
        except Exception:
            ops_red = 0.0
        try:
            keys_red = ((self.initial_keys - self.curr_keys) / max(self.initial_keys, 1e-6)) * 100.0
        except Exception:
            keys_red = 0.0
        try:
            is_compliant = bool(self.curr_constraint <= self.budget)
            violation = max(0.0, self.curr_constraint - self.budget)
            margin = self.budget - self.curr_constraint
        except Exception:
            is_compliant, violation, margin = True, 0.0, 0.0
        try:
            rot_keys = rotation_steps(self.expression)
        except Exception:
            rot_keys = -1
        try:
            r_exec, r_keys = float(self._last_r_vec[0]), float(self._last_r_vec[1])
        except Exception:
            r_exec, r_keys = 0.0, 0.0
        info = {
            "expression": getattr(self, "expression", ""),
            "budget": getattr(self, "budget", None),
            "constraint_value": getattr(self, "curr_constraint", 0.0),
            "noise": getattr(self, "curr_constraint", 0.0),
            "cost": getattr(self, "current_cost", 0),
            "initial_cost": getattr(self, "initial_cost", 0),
            "cost_reduction": cost_red / 100.0,
            "c_exec": getattr(self, "curr_ops", 0),
            "initial_ops": getattr(self, "initial_ops", 0),
            "ops_reduction": ops_red / 100.0,
            "c_keys": getattr(self, "curr_keys", 0),
            "initial_keys": getattr(self, "initial_keys", 0),
            "keys_reduction": keys_red / 100.0,
            "initial_constraint": getattr(self, "initial_constraint", 0.0),
            "constraint_metric": getattr(self, "constraint_metric", "mem"),
            "constraint_name": getattr(self, "metric_name", "Peak RAM"),
            "constraint_unit": getattr(self, "metric_unit", "MB"),
            "violation": violation,
            "margin": margin,
            "is_compliant": is_compliant,
            "preference_vector": getattr(self, "current_w", np.array([1.0, 0.0], dtype=np.float32)),
            "r_exec": r_exec,
            "r_keys": r_keys,
            "rotation_keys": rot_keys,
        }
        if terminated or truncated:
            info["episode"] = {"r": reward, "l": getattr(self, "steps", 0), "t": None}
        # Aliases expected by UnifiedMetricsCallback.
        info.setdefault("final_cost", info["cost"])
        info.setdefault("final_ops", info["c_exec"])
        info.setdefault("final_keys", info["c_keys"])
        info.setdefault("final_constraint", info["constraint_value"])
        return info

    def _reward_vector(self, delta_ops_old, delta_ops_new, delta_keys_old, delta_keys_new) -> np.ndarray:
        r_ops = (delta_ops_old - delta_ops_new) / delta_ops_old if delta_ops_old != 0 else 0.0
        r_keys = (delta_keys_old - delta_keys_new) / self.n_budget
        return np.array([r_ops, r_keys], dtype=np.float32)

    def _kl_bonus(self, r_vec: np.ndarray) -> float:
        r_pos = np.maximum(r_vec, 0.0) + 1e-6
        r_tilde = r_pos / np.sum(r_pos)
        uniform = np.full_like(r_tilde, 1.0 / len(r_tilde))
        return float(np.sum(r_tilde * np.log((r_tilde + 1e-6) / uniform)))

    def _pareto_envelope_bonus(self, r_vec: np.ndarray) -> float:
        return float(max(np.dot(p, r_vec) for p in self.pref_list))

    def _compose_reward(self, r_vec: np.ndarray) -> float:
        reward = float(np.dot(self.current_w, r_vec))
        if self.lambda_env != 0.0:
            reward += self.lambda_env * self._pareto_envelope_bonus(r_vec)
        if self.lambda_kl != 0.0:
            reward += self.lambda_kl * self._kl_bonus(r_vec)
        return reward

    def calculate_intermediate_reward(self, new_ops: float, new_keys: float) -> float:
        r_vec = self._reward_vector(self.curr_ops, new_ops, self.curr_keys, new_keys)
        self._last_r_vec = r_vec
        return self._compose_reward(r_vec)

    def calculate_final_reward(self) -> float:
        r_vec = self._reward_vector(self.initial_ops, self.curr_ops, self.initial_keys, self.curr_keys)
        self._last_r_vec = r_vec
        return self._compose_reward(r_vec) * 100

    def get_cost(self, expr: str) -> float:
        return calculate_cost(parse_sexpr(expr))

    def _embed_expression(self, expr: str) -> np.ndarray:
        fallback = np.zeros((self.embedding_dim,), dtype=np.float32)
        try:
            if self.embeddings_model is None:
                self.embed_fallback_count += 1
                return fallback
            cached = self._emb_cache.get(expr)
            if cached is not None:
                return cached.copy()
            if hasattr(self.embeddings_model, "get_embedding"):
                emb = self.embeddings_model.get_embedding(expr)
                if emb is None:
                    self.embed_fallback_count += 1
                    return fallback
                arr = np.asarray(emb, dtype=np.float32).reshape(-1)
                if arr.size != self.embedding_dim:
                    self.embed_fallback_count += 1
                    return fallback
                if len(self._emb_cache) >= self._EMB_CACHE_MAX:
                    self._emb_cache.clear()
                self._emb_cache[expr] = arr
                return arr.copy()
            expr_tree = parse_sexpr(expr)
            with torch.no_grad():
                emb = get_expression_cls_embedding(expr_tree, self.embeddings_model)
            if emb is None:
                self.embed_fallback_count += 1
                return fallback
            arr = emb.squeeze(0).cpu().numpy().astype(np.float32).reshape(-1)
            if arr.size != self.embedding_dim:
                self.embed_fallback_count += 1
                return fallback
            if len(self._emb_cache) >= self._EMB_CACHE_MAX:
                self._emb_cache.clear()
            self._emb_cache[expr] = arr
            return arr.copy()
        except Exception:
            self.embed_fallback_count += 1
            return fallback

    def get_fallback_count(self) -> int:
        return getattr(self, "embed_fallback_count", 0)

    def set_noise_budget(self, budget: int | None):
        if budget is None:
            self.budget = None
            self.budget_one_hot_encoding = None
            return
        self.budget = budget
        self.budget_one_hot_encoding = np.zeros(self.budget_dim, dtype=np.float32)
        if budget in self.budget_options:
            budget_idx = self.budget_options.index(budget)
        else:
            budget_idx = min(range(len(self.budget_options)), key=lambda i: abs(self.budget_options[i] - budget))
        self.budget_one_hot_encoding[budget_idx] = 1.0

    def set_active_budgets(self, budgets):
        self.active_budgets = list(budgets)

    def get_action_mask(self) -> np.ndarray:
        n_actions = len(self.rules.keys()) * self.max_positions
        mask = np.zeros(n_actions, dtype=np.float32)
        try:
            use_masking = (
                self.constraint_method == "noise_masking"
                and self.budget is not None
                and self.budget < UNCONSTRAINED_BUDGET_THRESHOLD
            )
        except Exception:
            use_masking = False
        # Memoization: the mask is a pure function of the expression (plus the
        # budget only when noise_masking is active), so a cached mask is
        # bit-identical to a freshly computed one.
        cache_key = (self.expression, self.budget) if use_masking else self.expression
        cached = self._mask_cache.get(cache_key)
        if cached is not None:
            return cached.copy()
        try:
            parsed = parse_sexpr(self.expression)
        except Exception:
            # Unparseable expression: allow only END so the episode can close.
            mask[0] = 1.0
            return mask
        for rule_idx, rule_name in enumerate(self.rules.keys()):
            if rule_name == "END":
                mask[rule_idx * self.max_positions] = 1.0
                continue
            try:
                rule_obj = self.rules[rule_name]
                matches = rule_obj.find_matching_subexpressions(parsed)
            except Exception:
                continue
            valid_positions = min(len(matches), self.max_positions)
            if valid_positions > 0:
                start = rule_idx * self.max_positions
                if use_masking:
                    for pos_idx in range(valid_positions):
                        k, _ = matches[pos_idx]
                        try:
                            new_expr_tree = rule_obj.apply_rule(parsed, path=k)
                            val = self.estimator.estimate(new_expr_tree)
                            if val <= self.budget:
                                mask[start + pos_idx] = 1.0
                        except Exception:
                            pass
                else:
                    mask[start:start + valid_positions] = 1.0
        if not np.any(mask):
            mask[0] = 1.0  # never return an all-zero mask (would stall sampling)
        return self._store_mask(cache_key, mask)

    def _store_mask(self, key, mask: np.ndarray) -> np.ndarray:
        """Cache the pristine mask and hand the caller a copy, so caller-side
        mutation can never poison the cache (results stay bit-identical)."""
        if len(self._mask_cache) >= self._MASK_CACHE_MAX:
            self._mask_cache.clear()
        self._mask_cache[key] = mask
        return mask.copy()
