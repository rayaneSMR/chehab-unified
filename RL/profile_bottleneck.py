"""
Bottleneck profiler for the unified RAM-FiLM training env (fheEnvUnified).

Measures, on REAL dataset expressions:
  A) per-component costs: parse, action-mask (N rules x matching), cost x3,
     peak-RAM estimate (packing + CKKS estimator), GNN embedding forward
  B) end-to-end env.reset / env.step wall time with random valid actions
  C) apply_rule timing per rule (stall detection)
  D) PPO-style update cost emulated with the real policy architecture (pure
     torch, no SB3 needed): n_steps=2048, n_epochs=15, batch=256
  E) eval-episode cost on the single benchmark expression

Run from anywhere:  python RL/profile_bottleneck.py
Prints a summary + extrapolation to 5M timesteps with 8 envs.
"""
import os
import sys
import time
import random
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)
for p in (SCRIPT_DIR, os.path.join(SCRIPT_DIR, "pytrs")):
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np
import torch

torch.set_num_threads(1)

from fhe_rl.config import set_framework
set_framework("unified")

from pytrs import create_rules, parse_sexpr, calculate_cost
from fhe_rl.memory import MemoryEstimator, peak_ram_mb
from fhe_rl.gnn_embeddings import FHEFeatureExtractor
from fhe_rl.config import get_model_path
from fhe_rl.env_unified import fheEnvUnified
from fhe_rl.utils import mlp

RANDOM_SEED = 0
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)
torch.manual_seed(RANDOM_SEED)


def t(fn, n=20):
    """avg seconds per call over n calls"""
    t0 = time.perf_counter()
    for _ in range(n):
        fn()
    return (time.perf_counter() - t0) / n


def main():
    print("=== Loading rules + dataset sample ===", flush=True)
    t0 = time.perf_counter()
    rules = create_rules("rules.txt", "rotations_rules.txt")
    rules["END"] = None
    rule_names = list(rules.keys())
    print(f"rules: {len(rule_names)} (incl END) | load {time.perf_counter()-t0:.1f}s", flush=True)

    # Sample expressions from the real training dataset (Vec sizes in allowed set)
    allowed = {"1", "4", "8", "9", "16", "25", "32"}
    exprs = []
    ds = os.path.join("fhe_rl", "datasets", "final_llm_dataset.txt")
    with open(ds) as f:
        for line in f:
            s = line.split(":")[0].strip()
            if not s:
                continue
            try:
                e = parse_sexpr(s)
                if str(len(e.args)) in allowed:
                    exprs.append(s)
            except Exception:
                continue
            if len(exprs) >= 300:
                break
    sizes = np.array([len(e) for e in exprs])
    print(f"sampled {len(exprs)} exprs | chars: mean={sizes.mean():.0f} p50={np.percentile(sizes,50):.0f} "
          f"p90={np.percentile(sizes,90):.0f} max={sizes.max()}", flush=True)

    # -- A) component profile ------------------------------------------------
    print("\n=== A) per-component timing (avg per call, dataset sample) ===", flush=True)
    est = MemoryEstimator(margin=False)

    sample = exprs[:60]
    r_parse = t(lambda: [parse_sexpr(s) for s in sample], n=5) / len(sample)

    parsed = [parse_sexpr(s) for s in sample]

    def mask_one():
        for p in parsed[:1]:
            for rn in rule_names:
                if rn == "END":
                    continue
                try:
                    rules[rn].find_matching_subexpressions(p)
                except Exception:
                    pass
    r_mask = t(mask_one, n=3)

    r_cost = t(lambda: [calculate_cost(parse_sexpr(s)) for s in sample], n=3) / len(sample)
    r_split = t(lambda: [calculate_cost(parse_sexpr(s), w_keys=0.0) for s in sample], n=3) / len(sample)

    # cold estimate (packing + CKKS estimator), bypassing the string cache
    r_est_cold = t(lambda: [peak_ram_mb(s, margin=False) for s in sample], n=1) / len(sample)
    r_est_warm = t(lambda: [peak_ram_mb(s, margin=False) for s in sample], n=5) / len(sample)

    gnn = FHEFeatureExtractor(model_path=get_model_path("gnn_embeddings_model"))
    r_gnn = t(lambda: [gnn.get_embedding(s) for s in sample], n=3) / len(sample)

    for name, v in [("parse_sexpr", r_parse),
                    ("action_mask (all rules)", r_mask),
                    ("calculate_cost x1 (get_cost)", r_cost),
                    ("calculate_cost x1 (get_split_costs part)", r_split),
                    ("peak_ram_mb COLD (pack+CKKS est)", r_est_cold),
                    ("peak_ram_mb WARM (cache hit)", r_est_warm),
                    ("GNN embedding forward", r_gnn)]:
        print(f"  {name:<45}: {v*1000:8.2f} ms", flush=True)


    # -- C) apply_rule timing (stall detection) ------------------------------
    print("\n=== C) apply_rule timing per rule on matched positions ===", flush=True)
    per_rule = defaultdict(list)
    for s in exprs[:80]:
        p = parse_sexpr(s)
        for rn in rule_names:
            if rn == "END":
                continue
            try:
                matches = rules[rn].find_matching_subexpressions(p)
            except Exception:
                continue
            if not matches:
                continue
            k = matches[0][0]
            t0 = time.perf_counter()
            try:
                rules[rn].apply_rule(p, path=k)
            except Exception:
                pass
            per_rule[rn].append(time.perf_counter() - t0)
    rows = sorted(((np.mean(v), np.max(v), len(v), k) for k, v in per_rule.items()), reverse=True)
    print(f"  {'rule':<35} {'mean ms':>10} {'max ms':>10} {'n':>5}", flush=True)
    for mean_s, max_s, n, k in rows[:15]:
        print(f"  {k:<35} {mean_s*1000:10.2f} {max_s*1000:10.2f} {n:5d}", flush=True)

    # -- B) end-to-end env.reset / env.step ----------------------------------
    print("\n=== B) fheEnvUnified end-to-end (random valid actions, verbose=False) ===", flush=True)
    env = fheEnvUnified(
        rules, exprs, max_positions=16, embeddings_model=gnn,
        budget_options=[1500, 2000, 2600, 1000000], constraint_method="nato_sc",
        constraint_metric="mem", pref_list=[[1.0, 0.0], [0.5, 0.5]],
        n_cycle=1, n_budget=5, env_idx=0, verbose=False,
    )
    t0 = time.perf_counter()
    obs, info = env.reset()
    t_reset = time.perf_counter() - t0

    step_times = []
    n_steps = 150
    for i in range(n_steps):
        valid = np.flatnonzero(obs["action_mask"])
        valid = valid[valid // 16 != len(rule_names) - 1]  # avoid END so steps flow
        if len(valid) == 0:
            obs, _ = env.reset()
            continue
        a = int(np.random.choice(valid))
        t0 = time.perf_counter()
        obs, r, term, trunc, info = env.step(a)
        step_times.append(time.perf_counter() - t0)
        if term or trunc:
            obs, _ = env.reset()
    st = np.array(step_times)
    print(f"  reset: {t_reset*1000:.1f} ms", flush=True)
    print(f"  step:  mean={st.mean()*1000:.1f} ms  p50={np.percentile(st,50)*1000:.1f}  "
          f"p90={np.percentile(st,90)*1000:.1f}  max={st.max()*1000:.1f}", flush=True)

    # -- D) PPO update cost (real policy arch, pure torch emulation) ---------
    print("\n=== D) PPO update emulation (n_steps=2048, n_epochs=15, batch=256) ===", flush=True)
    rule_dim, max_pos = len(rule_names), 16
    enc_dim = 256 + 32 + 1  # film: 256 emb + 32 budget emb + noise_ratio
    rule_head = mlp(enc_dim, [64, 32], rule_dim, layernorm=True)
    pos_head = mlp(enc_dim + rule_dim, [32, 32], max_pos, layernorm=True)
    value_net = mlp(enc_dim, [128, 64, 32], 1, layernorm=True)
    params = list(rule_head.parameters()) + list(pos_head.parameters()) + list(value_net.parameters())
    opt = torch.optim.Adam(params, lr=1e-4)
    B = 256
    enc = torch.randn(B, enc_dim)
    tgt_r = torch.randint(0, rule_dim, (B,))
    tgt_p = torch.randint(0, max_pos, (B,))
    ret = torch.randn(B)
    onehot = torch.zeros(B, rule_dim).scatter_(1, tgt_r.unsqueeze(1), 1.0)

    def update_step():
        opt.zero_grad()
        rl = rule_head(enc)
        logp_r = torch.nn.functional.cross_entropy(rl, tgt_r)
        ph = pos_head(torch.cat([enc, onehot], dim=1))
        logp_p = torch.nn.functional.cross_entropy(ph, tgt_p)
        v = value_net(enc).squeeze(-1)
        loss = logp_r + logp_p + 0.5 * ((v - ret) ** 2).mean()
        loss.backward()
        opt.step()
    r_upd = t(update_step, n=20)
    n_batches = 2048 * 15 // 256
    upd_rollout_s = r_upd * n_batches
    print(f"  one minibatch: {r_upd*1000:.2f} ms | {n_batches} minibatches/rollout "
          f"-> update ~= {upd_rollout_s:.1f} s per 16384-timestep rollout", flush=True)

    # -- E) eval episode cost on the single benchmark ------------------------
    print("\n=== E) eval-episode cost (benchmarks.txt: 1 expr; random actions) ===", flush=True)
    bench = []
    with open(os.path.join("fhe_rl", "datasets", "benchmarks.txt")) as f:
        for line in f:
            s = line.split(":")[0].strip()
            if s:
                bench.append(s)
    env2 = fheEnvUnified(
        rules, bench, max_positions=16, embeddings_model=gnn,
        budget_options=[1500, 2000, 2600, 1000000], constraint_method="nato_sc",
        constraint_metric="mem", pref_list=[[1.0, 0.0]] * 10,
        n_cycle=1, n_budget=5, env_idx=0, verbose=False,
    )
    env2.set_preference_vector([0.5, 0.5])
    ep_times = []
    n = 0
    for _ in range(3):
        t0 = time.perf_counter()
        obs, _ = env2.reset()
        done = False
        n = 0
        while not done and n < 75:
            valid = np.flatnonzero(obs["action_mask"])
            a = int(np.random.choice(valid))
            obs, r, term, trunc, info = env2.step(a)
            done = term or trunc
            n += 1
        ep_times.append(time.perf_counter() - t0)
    print(f"  one eval episode (random policy, {n} steps): {np.mean(ep_times):.2f} s", flush=True)

    # -- Extrapolation -------------------------------------------------------
    mean_step_s = st.mean()
    total_ts = 5_000_000
    num_envs = 8
    steps_per_env = total_ts / num_envs
    env_wall_h = steps_per_env * mean_step_s / 3600
    upd_wall_h = (total_ts / (2048 * num_envs)) * upd_rollout_s / 3600
    print("\n=== EXTRAPOLATION to 5M timesteps, 8 envs (single-node) ===", flush=True)
    print(f"  env stepping wall time : {env_wall_h:6.1f} h  (at {mean_step_s*1000:.0f} ms/step/env)", flush=True)
    print(f"  PPO updates wall time  : {upd_wall_h:6.1f} h", flush=True)
    print("  NOTE: SubprocVecEnv is synchronous -> real time ~= max(env) + updates", flush=True)


if __name__ == "__main__":
    main()
