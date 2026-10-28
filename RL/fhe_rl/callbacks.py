from collections import deque
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.evaluation import evaluate_policy
import numpy as np
import torch
import os
import time


RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"

class EntCoefScheduler(BaseCallback):
    def __init__(self, schedule, verbose: int = 0):
        super().__init__(verbose)
        self.schedule = schedule

    def _on_training_start(self) -> None:
        p = self.model._current_progress_remaining
        self.model.ent_coef = float(self.schedule(p))

    def _on_rollout_end(self) -> None:
        p = self.model._current_progress_remaining
        self.model.ent_coef = float(self.schedule(p))

    def _on_step(self) -> bool:
        return True

class ParetoEvalCallback(BaseCallback):
    def __init__(self, eval_env, pref_list, 
                 best_model_save_path=None, 
                 log_path=None, 
                 eval_freq=10000, 
                 n_eval_episodes=5, 
                 deterministic=True, 
                 verbose=1):
        super().__init__(verbose)
        self.eval_env = eval_env
        self.pref_list = pref_list
        self.eval_freq = eval_freq
        self.n_eval_episodes = n_eval_episodes
        self.deterministic = deterministic
        self.best_model_save_path = best_model_save_path
        self.log_path = log_path
        
        # Track best performance (Average across the Pareto Front)
        self.best_mean_reward = -np.inf

        # Ensure directories exist
        if self.best_model_save_path is not None:
            os.makedirs(self.best_model_save_path, exist_ok=True)

    def _init_callback(self) -> None:
        super()._init_callback()
        if self.eval_freq > 0 and self.training_env is not None:
            self.eval_freq = max(self.eval_freq // self.training_env.num_envs, 1)

    def _on_step(self) -> bool:
        if self.n_calls % self.eval_freq == 0:
            GREEN = "\033[92m"
            RED = "\033[91m"
            YELLOW = "\033[93m"
            CYAN = "\033[96m"
            BOLD = "\033[1m"
            RESET = "\033[0m"
            if self.verbose > 0:
                print(f"\n{BLUE}{'='*105}{RESET}", flush=True)
                print(f"{BOLD}Step {self.num_timesteps:,} [Evaluation]: Starting Pareto & Safe Execution Evaluation ({len(self.pref_list)} front points, {self.n_eval_episodes} benchmarks each){RESET}", flush=True)
                print(f"{BLUE}{'='*105}{RESET}")


            all_means = []
            all_lengths = []
            all_cost_reds = []
            all_exec_reds = []
            all_keys_reds = []
            all_safe_cost_reds = []
            all_safe_exec_reds = []
            all_safe_keys_reds = []
            all_compliances = []
            all_violations = []
            all_margins = []
            all_safety_activated = []
            all_rl_times_ms = []

            point_summaries = []

            for p_idx, w in enumerate(self.pref_list):
                # Lock eval env to this preference vector (constrained env has no preferences)
                try:
                    self.eval_env.env_method("set_preference_vector", w)
                except AttributeError:
                    pass

                pt_rewards = []
                pt_lengths = []
                pt_cost_reds = []
                pt_exec_reds = []
                pt_keys_reds = []
                pt_safe_cost_reds = []
                pt_safe_exec_reds = []
                pt_safe_keys_reds = []
                pt_compliances = []
                pt_violations = []
                pt_margins = []
                pt_constraints = []
                pt_budgets = []
                pt_safety_activated = []
                pt_rl_times_ms = []
                metric_name = "Peak RAM"
                metric_unit = "MB"

                for _ in range(self.n_eval_episodes):
                    t_start = time.perf_counter()
                    obs = self.eval_env.reset()
                    done = False
                    ep_rew = 0.0
                    ep_len = 0
                    checkpoints = []

                    while not done:
                        action, _ = self.model.predict(obs, deterministic=self.deterministic)
                        obs, reward, dones, infos = self.eval_env.step(action)
                        ep_rew += float(reward[0])
                        ep_len += 1
                        done = bool(dones[0])
                        info = infos[0]

                        checkpoints.append({
                            "cost": float(info.get("cost", 0.0)),
                            "ops": float(info.get("c_exec", 0.0)),
                            "keys": float(info.get("c_keys", 0.0)),
                            "constraint": float(info.get("constraint_value", 0.0)),
                            "budget": float(info.get("budget", 1.0)),
                            "initial_cost": float(info.get("initial_cost", 1.0)),
                            "initial_ops": float(info.get("initial_ops", 1.0)),
                            "initial_keys": float(info.get("initial_keys", 1.0)),
                            "initial_constraint": float(info.get("initial_constraint", 0.0)),
                        })

                    rl_time_ms = (time.perf_counter() - t_start) * 1000.0
                    terminal = checkpoints[-1]
                    bgt = terminal["budget"]
                    raw_constraint = terminal["constraint"]

                    # Safety Checkpointing Rollback (NATO-SC / constrained system)
                    valid_checkpoints = [cp for cp in checkpoints if cp["constraint"] <= bgt]
                    if valid_checkpoints:
                        # Best state among those strictly meeting the constraint
                        best_safe = min(valid_checkpoints, key=lambda cp: cp["cost"])
                        safety_activated = (best_safe is not terminal)
                    else:
                        best_safe = {
                            "cost": terminal["initial_cost"],
                            "ops": terminal["initial_ops"],
                            "keys": terminal["initial_keys"],
                            "constraint": terminal["initial_constraint"],
                        }
                        safety_activated = True

                    init_c = max(terminal["initial_cost"], 1e-6)
                    init_o = max(terminal["initial_ops"], 1e-6)
                    init_k = max(terminal["initial_keys"], 1)  # keys are integers; avoid /1e-6 when 0

                    # Raw agent reductions
                    raw_cost_red = (init_c - terminal["cost"]) / init_c * 100.0
                    raw_exec_red = (init_o - terminal["ops"]) / init_o * 100.0
                    raw_keys_red = (init_k - terminal["keys"]) / init_k * 100.0

                    # Safe verified reductions (guaranteed within budget)
                    safe_cost_red = (init_c - best_safe["cost"]) / init_c * 100.0
                    safe_exec_red = (init_o - best_safe["ops"]) / init_o * 100.0
                    safe_keys_red = (init_k - best_safe["keys"]) / init_k * 100.0

                    is_safe = (raw_constraint <= bgt)
                    violation = max(0.0, raw_constraint - bgt)
                    margin = bgt - raw_constraint

                    pt_rewards.append(ep_rew)
                    pt_lengths.append(ep_len)
                    pt_cost_reds.append(raw_cost_red)
                    pt_exec_reds.append(raw_exec_red)
                    pt_keys_reds.append(raw_keys_red)
                    pt_safe_cost_reds.append(safe_cost_red)
                    pt_safe_exec_reds.append(safe_exec_red)
                    pt_safe_keys_reds.append(safe_keys_red)
                    pt_compliances.append(1.0 if is_safe else 0.0)
                    pt_violations.append(violation)
                    pt_margins.append(margin)
                    pt_constraints.append(raw_constraint)
                    pt_budgets.append(bgt)
                    pt_safety_activated.append(1.0 if safety_activated else 0.0)
                    pt_rl_times_ms.append(rl_time_ms)

                    metric_name = terminal.get("constraint_name", metric_name)
                    metric_unit = terminal.get("constraint_unit", metric_unit)

                mean_r = float(np.mean(pt_rewards))
                mean_l = float(np.mean(pt_lengths))
                mean_cost_red = float(np.mean(pt_cost_reds))
                mean_exec_red = float(np.mean(pt_exec_reds))
                mean_keys_red = float(np.mean(pt_keys_reds))
                mean_safe_cost_red = float(np.mean(pt_safe_cost_reds))
                mean_safe_exec_red = float(np.mean(pt_safe_exec_reds))
                mean_safe_keys_red = float(np.mean(pt_safe_keys_reds))
                safe_rate = float(np.mean(pt_compliances)) * 100.0
                safety_act_rate = float(np.mean(pt_safety_activated)) * 100.0
                mean_rl_time = float(np.mean(pt_rl_times_ms))
                mean_viol = float(np.mean(pt_violations))
                mean_cons = float(np.mean(pt_constraints))
                mean_bgt = float(np.mean(pt_budgets))

                all_means.append(mean_r)
                all_lengths.append(mean_l)
                all_cost_reds.append(mean_cost_red)
                all_exec_reds.append(mean_exec_red)
                all_keys_reds.append(mean_keys_red)
                all_safe_cost_reds.append(mean_safe_cost_red)
                all_safe_exec_reds.append(mean_safe_exec_red)
                all_safe_keys_reds.append(mean_safe_keys_red)
                all_compliances.extend(pt_compliances)
                all_violations.extend(pt_violations)
                all_margins.extend(pt_margins)
                all_safety_activated.extend(pt_safety_activated)
                all_rl_times_ms.extend(pt_rl_times_ms)

                # Log per-point metrics to TensorBoard
                self.logger.record(f"eval/reward_w_{w[1]:.2f}", mean_r)
                self.logger.record(f"eval/safe_rate_w_{w[1]:.2f}", safe_rate)
                self.logger.record(f"eval/safe_exec_red_w_{w[1]:.2f}", mean_safe_exec_red)
                self.logger.record(f"eval/safe_cost_red_w_{w[1]:.2f}", mean_safe_cost_red)
                self.logger.record(f"eval/raw_exec_red_w_{w[1]:.2f}", mean_exec_red)
                self.logger.record(f"eval/safety_act_rate_w_{w[1]:.2f}", safety_act_rate)
                self.logger.record(f"eval/rl_time_ms_w_{w[1]:.2f}", mean_rl_time)

                point_summaries.append({
                    "p_idx": p_idx + 1,
                    "w": w,
                    "mean_r": mean_r,
                    "raw_cost_red": mean_cost_red,
                    "safe_cost_red": mean_safe_cost_red,
                    "raw_exec_red": mean_exec_red,
                    "safe_exec_red": mean_safe_exec_red,
                    "raw_keys_red": mean_keys_red,
                    "safe_keys_red": mean_safe_keys_red,
                    "constraint": mean_cons,
                    "budget": mean_bgt,
                    "safe_rate": safe_rate,
                    "safety_act": safety_act_rate,
                    "rl_time_ms": mean_rl_time,
                    "violations": int(len(pt_compliances) - sum(pt_compliances)),
                    "metric_name": metric_name,
                    "metric_unit": metric_unit,
                })

            self.eval_env.env_method("unlock_preferences")

            # Global Front Scores
            current_mean_reward = float(np.mean(all_means))
            current_mean_length = float(np.mean(all_lengths))
            current_safe_rate = float(np.mean(all_compliances)) * 100.0
            current_mean_cost_red = float(np.mean(all_cost_reds))
            current_mean_safe_cost_red = float(np.mean(all_safe_cost_reds))
            current_mean_exec_red = float(np.mean(all_exec_reds))
            current_mean_safe_exec_red = float(np.mean(all_safe_exec_reds))
            current_mean_keys_red = float(np.mean(all_keys_reds))
            current_mean_safe_keys_red = float(np.mean(all_safe_keys_reds))
            current_safety_act_rate = float(np.mean(all_safety_activated)) * 100.0
            current_avg_rl_time_ms = float(np.mean(all_rl_times_ms))
            current_mean_violation = float(np.mean(all_violations))
            current_mean_margin = float(np.mean(all_margins))
            total_violations = int(len(all_compliances) - sum(all_compliances))

            # Log to TensorBoard
            self.logger.record("eval/pareto_avg_reward", current_mean_reward)
            self.logger.record("eval/pareto_avg_ep_length", current_mean_length)
            self.logger.record("eval/pareto_safe_compliance_rate", current_safe_rate)
            self.logger.record("eval/pareto_safety_rollback_rate", current_safety_act_rate)
            self.logger.record("eval/pareto_avg_safe_exec_red_pct", current_mean_safe_exec_red)
            self.logger.record("eval/pareto_avg_raw_exec_red_pct", current_mean_exec_red)
            self.logger.record("eval/pareto_avg_safe_cost_red_pct", current_mean_safe_cost_red)
            self.logger.record("eval/pareto_avg_raw_cost_red_pct", current_mean_cost_red)
            self.logger.record("eval/pareto_avg_safe_keys_red_pct", current_mean_safe_keys_red)
            self.logger.record("eval/pareto_avg_rl_time_ms", current_avg_rl_time_ms)
            self.logger.record("eval/pareto_avg_violation", current_mean_violation)
            self.logger.record("eval/pareto_avg_margin", current_mean_margin)

            # Print Detailed Evaluation Table
            if self.verbose > 0:
                print(f"{BOLD}{'Pt':<3} | {'Preference w':<24} | {'Exec Red% (Safe/Raw)':<22} | {'Cost Red% (Safe/Raw)':<22} | {'Avg ' + metric_name:<14} | {'Safe Status / Rollback'}{RESET}")
                print(f"{'-'*105}")
                for s in point_summaries:
                    safe_color = GREEN if s["safe_rate"] >= 100.0 else (YELLOW if s["safe_rate"] >= 80.0 else RED)
                    safe_str = f"{safe_color}{s['safe_rate']:>5.1f}% SAFE{RESET} (Rollback: {s['safety_act']:.0f}%)"
                    exec_str = f"{s['safe_exec_red']:>+5.1f}% / {s['raw_exec_red']:>+5.1f}%"
                    cost_str = f"{s['safe_cost_red']:>+5.1f}% / {s['raw_cost_red']:>+5.1f}%"
                    print(
                        f"#{s['p_idx']:<2} | "
                        f"[ops={s['w'][0]:.2f}, keys={s['w'][1]:.2f}] | "
                        f"{exec_str:<22} | "
                        f"{cost_str:<22} | "
                        f"{s['constraint']:>5.1f} / {s['budget']:<4.0f} {s['metric_unit']} | "
                        f"{safe_str}"
                    )
                print(f"{'-'*105}")
                overall_color = GREEN if current_safe_rate >= 100.0 else (YELLOW if current_safe_rate >= 80.0 else RED)
                print(f"{BOLD}Front Summary (Step {self.num_timesteps:,}):{RESET}")
                print(f"  • {BOLD}Mean Pareto Reward{RESET}        : {CYAN}{current_mean_reward:.4f}{RESET} +/- {np.std(all_means):.4f}")
                print(f"  • {BOLD}Safe Compliance Rate{RESET}      : {overall_color}{current_safe_rate:.1f}% SAFE{RESET} ({total_violations} total violations / {len(all_compliances)} evaluations)")
                print(f"  • {BOLD}Safety Rollback Rate{RESET}      : {CYAN}{current_safety_act_rate:.1f}%{RESET} (rescued infeasible trajectories)")
                print(f"  • {BOLD}Safe Exec Cost Red% {RESET}      : {GREEN if current_mean_safe_exec_red > 0 else RED}{current_mean_safe_exec_red:+.1f}%{RESET} (Raw: {current_mean_exec_red:+.1f}%) [FHE Exec Time/Ops]")
                print(f"  • {BOLD}Safe Total Cost Red%{RESET}      : {GREEN if current_mean_safe_cost_red > 0 else RED}{current_mean_safe_cost_red:+.1f}%{RESET} (Raw: {current_mean_cost_red:+.1f}%)")
                print(f"  • {BOLD}Safe Keys Cost Red% {RESET}      : {GREEN if current_mean_safe_keys_red > 0 else RED}{current_mean_safe_keys_red:+.1f}%{RESET} (Raw: {current_mean_keys_red:+.1f}%)")
                print(f"  • {BOLD}Avg Safe Headroom   {RESET}      : {CYAN}{current_mean_margin:+.1f} {metric_unit}{RESET}")
                print(f"  • {BOLD}Avg RL Inference Time{RESET}     : {current_avg_rl_time_ms:.1f} ms / benchmark")
                print(f"  • {BOLD}Avg Episode Length  {RESET}      : {current_mean_length:.1f} steps")

            # Model Checkpointing for Best Score
            if current_mean_reward > self.best_mean_reward:
                if self.verbose > 0:
                    print(f"  ★ {GREEN}New Best Pareto Frontier Score: {current_mean_reward:.4f}! Saving checkpoint...{RESET}")
                if self.best_model_save_path is not None:
                    self.model.save(os.path.join(self.best_model_save_path, "best_model"))
                self.best_mean_reward = current_mean_reward

            print(f"{BLUE}{'='*105}{RESET}\n", flush=True)
            self.logger.dump(step=self.num_timesteps)

        return True


class CurriculumCallback(BaseCallback):
    """Gradually widens the set of budgets sampled during training.

    Parameters
    ----------
    budget_phases : list[list[int]]
        Budget lists for each phase.  Phase 0 is used from the start.
        Example: [[60,80], [60,80,100,200], [60,80,100,200,1000000]]
    phase_boundaries : list[float]
        Training progress thresholds (0→1) at which to advance.
        Example: [0.33, 0.66] means phase 1 starts at 33% and phase 2 at 66%.
    """

    def __init__(self, budget_phases, phase_boundaries, verbose=0):
        super().__init__(verbose)
        self.budget_phases = budget_phases
        self.phase_boundaries = phase_boundaries
        self._current_phase = 0

    def _on_training_start(self) -> None:
        self._update_envs(self.budget_phases[0])
        print(f"[Curriculum] Phase 0: budgets = {self.budget_phases[0]}")

    def _on_step(self) -> bool:
        if self._current_phase >= len(self.phase_boundaries):
            return True
        progress = 1.0 - self.model._current_progress_remaining
        if progress >= self.phase_boundaries[self._current_phase]:
            self._current_phase += 1
            new_budgets = self.budget_phases[self._current_phase]
            self._update_envs(new_budgets)
            print(f"[Curriculum] Phase {self._current_phase}: budgets = {new_budgets}")
        return True

    def _update_envs(self, budgets):
        env = self.model.get_env()
        while hasattr(env, 'venv'):
            env = env.venv
        env.env_method('set_active_budgets', budgets)


def linear_schedule(start: float, end: float = 0.0):
    def sched(progress_remaining):
        return (start - end) * progress_remaining + end
    return sched


class UnifiedMetricsCallback(BaseCallback):
    """Tracks and logs comprehensive metrics from the unified environment to TensorBoard
    and reports live step progress, FPS, ETA, and constraint status to the console and log files.
    """
    def __init__(self, pid_wrapper=None, total_timesteps: int = 5000000, progress_freq: int = 2000, verbose: int = 1):
        super().__init__(verbose)
        self.pid_wrapper = pid_wrapper
        self.total_timesteps = total_timesteps
        self.progress_freq = progress_freq
        self.last_progress_step = 0
        self.start_time = None
        self.last_step_time = None
        self.last_step_count = 0
        
        # Rolling history for responsive real-time status reporting
        self.recent_cost_reds = deque(maxlen=100)
        self.recent_ops_reds = deque(maxlen=100)
        self.recent_keys_reds = deque(maxlen=100)
        self.recent_compliances = deque(maxlen=100)
        self.recent_constraints = deque(maxlen=100)
        
        # Per-rollout metrics for TensorBoard logging
        self.ep_costs = []
        self.ep_cost_reductions = []
        self.ep_ops = []
        self.ep_ops_reductions = []
        self.ep_keys = []
        self.ep_keys_reductions = []
        self.ep_constraints = []
        self.ep_violations = []
        self.ep_compliances = []

    def _init_callback(self) -> None:
        super()._init_callback()
        self.start_time = time.time()
        self.last_step_time = self.start_time
        self.last_step_count = self.num_timesteps
        self.last_progress_step = self.num_timesteps

    def _on_step(self) -> bool:
        if self.start_time is None:
            self.start_time = time.time()
            self.last_step_time = self.start_time
            self.last_step_count = self.num_timesteps
            self.last_progress_step = self.num_timesteps

        infos = self.locals.get("infos", [])
        dones = self.locals.get("dones", [])
        for done, info in zip(dones, infos):
            if done and "final_cost" in info:
                cost_red = info.get("cost_reduction", 0.0) * 100.0
                ops_red = info.get("ops_reduction", 0.0) * 100.0
                keys_red = info.get("keys_reduction", 0.0) * 100.0
                c_val = info.get("final_constraint", 0.0)
                is_comp = 1.0 if info.get("is_compliant", True) else 0.0

                self.ep_costs.append(info["final_cost"])
                self.ep_cost_reductions.append(cost_red)
                self.ep_ops.append(info.get("final_ops", 0))
                self.ep_ops_reductions.append(ops_red)
                self.ep_keys.append(info.get("final_keys", 0))
                self.ep_keys_reductions.append(keys_red)
                self.ep_constraints.append(c_val)
                self.ep_violations.append(info.get("violation", 0.0))
                self.ep_compliances.append(is_comp)

                self.recent_cost_reds.append(cost_red)
                self.recent_ops_reds.append(ops_red)
                self.recent_keys_reds.append(keys_red)
                self.recent_constraints.append(c_val)
                self.recent_compliances.append(is_comp)

        # Real-time Step Progress update whenever accessed in terminal / log file
        if (self.num_timesteps - self.last_progress_step) >= self.progress_freq:
            now = time.time()
            elapsed = now - self.start_time
            step_delta = self.num_timesteps - self.last_step_count
            time_delta = now - self.last_step_time
            inst_fps = (step_delta / time_delta) if time_delta > 0 else 0.0
            avg_fps = (self.num_timesteps / elapsed) if elapsed > 0 else 0.0

            pct = (self.num_timesteps / max(self.total_timesteps, 1)) * 100.0
            eta_sec = ((self.total_timesteps - self.num_timesteps) / avg_fps) if avg_fps > 0 else 0.0

            def _fmt_dur(sec):
                sec = int(max(0, sec))
                h = sec // 3600
                m = (sec % 3600) // 60
                s = sec % 60
                return f"{h:02d}:{m:02d}:{s:02d}"

            mean_red = float(np.mean(self.recent_cost_reds)) if self.recent_cost_reds else 0.0
            mean_comp = float(np.mean(self.recent_compliances) * 100.0) if self.recent_compliances else 100.0
            lam = float(getattr(self.pid_wrapper, "lambda_penalty", 0.0)) if self.pid_wrapper else 0.0

            total_fallbacks = 0
            try:
                if hasattr(self.training_env, "env_method"):
                    counts = self.training_env.env_method("get_fallback_count")
                    total_fallbacks = sum(counts)
            except Exception:
                pass
            fallback_str = f" | Fallbacks: {total_fallbacks}" if total_fallbacks > 0 else ""

            if self.verbose > 0:
                print(
                    f"[Step Progress] {self.num_timesteps:7,d} / {self.total_timesteps:,d} ({pct:5.2f}%) | "
                    f"Elapsed: {_fmt_dur(elapsed)} | ETA: {_fmt_dur(eta_sec)} | "
                    f"FPS: {inst_fps:5.1f} (avg: {avg_fps:5.1f}) | "
                    f"Cost Red: {mean_red:+5.1f}% | Compl: {mean_comp:5.1f}% | λ: {lam:.4f}{fallback_str}",
                    flush=True
                )
            self.last_progress_step = self.num_timesteps
            self.last_step_count = self.num_timesteps
            self.last_step_time = now

        return True

    def _on_rollout_end(self) -> None:
        now = time.time()
        elapsed = now - (self.start_time or now)
        avg_fps = (self.num_timesteps / elapsed) if elapsed > 0 else 0.0
        pct = (self.num_timesteps / max(self.total_timesteps, 1)) * 100.0

        def _fmt_dur(sec):
            sec = int(max(0, sec))
            return f"{sec//3600:02d}:{(sec%3600)//60:02d}:{sec%60:02d}"

        lam = float(getattr(self.pid_wrapper, "lambda_penalty", 0.0)) if self.pid_wrapper else 0.0

        total_fallbacks = 0
        try:
            if hasattr(self.training_env, "env_method"):
                counts = self.training_env.env_method("get_fallback_count")
                total_fallbacks = sum(counts)
        except Exception:
            pass
        self.logger.record("rollout/embed_fallback_count", total_fallbacks)

        if self.ep_costs:
            m_cost_red = float(np.mean(self.ep_cost_reductions))
            m_exec_red = float(np.mean(self.ep_ops_reductions))
            m_keys_red = float(np.mean(self.ep_keys_reductions))
            m_constraint = float(np.mean(self.ep_constraints))
            m_compl = float(np.mean(self.ep_compliances)) * 100.0

            if self.verbose > 0:
                print(
                    f"\n--- [Rollout Complete @ Step {self.num_timesteps:,} / {self.total_timesteps:,} ({pct:.2f}%)] "
                    f"Elapsed: {_fmt_dur(elapsed)} | FPS: {avg_fps:.1f} | λ: {lam:.4f} ---\n"
                    f"    Cost Red: {m_cost_red:+.1f}% (Exec: {m_exec_red:+.1f}%, Keys: {m_keys_red:+.1f}%) | "
                    f"Constraint Mean: {m_constraint:.1f} | Safe Compliance: {m_compl:.1f}%\n",
                    flush=True
                )

            self.logger.record("unified/cost_final_mean", float(np.mean(self.ep_costs)))
            self.logger.record("unified/cost_reduction_pct_mean", m_cost_red)
            self.logger.record("unified/exec_cost_final_mean", float(np.mean(self.ep_ops)))
            self.logger.record("unified/exec_reduction_pct_mean", m_exec_red)
            self.logger.record("unified/keys_cost_final_mean", float(np.mean(self.ep_keys)))
            self.logger.record("unified/keys_reduction_pct_mean", m_keys_red)
            self.logger.record("unified/constraint_final_mean", m_constraint)
            self.logger.record("unified/violation_mean", float(np.mean(self.ep_violations)))
            self.logger.record("unified/compliance_rate", m_compl / 100.0)
            self.ep_costs.clear()
            self.ep_cost_reductions.clear()
            self.ep_ops.clear()
            self.ep_ops_reductions.clear()
            self.ep_keys.clear()
            self.ep_keys_reductions.clear()
            self.ep_constraints.clear()
            self.ep_violations.clear()
            self.ep_compliances.clear()

        if self.pid_wrapper is not None:
            self.logger.record("unified/lagrangian_lambda", lam)