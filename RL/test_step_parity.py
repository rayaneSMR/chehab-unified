"""Differential parity test: current fhe_rl.env_unified (fast-step optimized)
vs .diffref/env_unified_old.py (pre-optimization copy).

Both envs get identical constructor args, identical reset(seed=42), and the
IDENTICAL action sequence (chosen deterministically from the OLD env's mask).
Every observation array, reward, terminated/truncated flag and step-info field
must be BIT-identical. Also covers noise_masking budget-keyed mask caching and
margin_barrier obs. Exit code 0 = PASS.

Run:  python RL/test_step_parity.py   (no SB3 required)
"""
import os
import sys
import importlib.util
import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)
for p in (SCRIPT_DIR, os.path.join(SCRIPT_DIR, "pytrs")):
    if p not in sys.path:
        sys.path.insert(0, p)

import torch
torch.set_num_threads(1)

from fhe_rl.config import set_framework, get_model_path
set_framework("unified")

from pytrs import create_rules, parse_sexpr
from fhe_rl.gnn_embeddings import FHEFeatureExtractor
from fhe_rl.config import get_model_path
import fhe_rl.env_unified as NEW

# Load the pre-optimization copy as part of the same package (relative imports)
_spec = importlib.util.spec_from_file_location(
    "fhe_rl.env_unified_old", os.path.join(SCRIPT_DIR, ".diffref", "env_unified_old.py"))
OLD = importlib.util.module_from_spec(_spec)
sys.modules["fhe_rl.env_unified_old"] = OLD
_spec.loader.exec_module(OLD)

FAILURES = []


def check(cond, msg):
    if not cond:
        FAILURES.append(msg)
        print(f"  FAIL: {msg}", flush=True)


def cmp_obs(a, b, tag):
    check(set(a.keys()) == set(b.keys()), f"{tag}: obs keys {sorted(a)} vs {sorted(b)}")
    for k in a:
        if k not in b:
            continue
        x, y = np.asarray(a[k]), np.asarray(b[k])
        check(x.shape == y.shape and x.dtype == y.dtype and np.array_equal(x, y),
              f"{tag}: obs['{k}'] mismatch (shape {x.shape}/{y.shape} "
              f"maxdiff={np.abs(x.astype(float)-y.astype(float)).max() if x.shape==y.shape else 'n/a'})")


INFO_KEYS = ["expression", "budget", "constraint_value", "cost", "initial_cost",
             "c_exec", "initial_ops", "c_keys", "initial_keys", "cost_reduction",
             "ops_reduction", "keys_reduction", "violation", "margin",
             "is_compliant", "r_exec", "r_keys", "rotation_keys"]


def cmp_info(a, b, tag):
    for k in INFO_KEYS:
        va, vb = a.get(k), b.get(k)
        if isinstance(va, np.ndarray) or isinstance(vb, np.ndarray):
            ok = np.array_equal(np.asarray(va), np.asarray(vb))
        else:
            ok = (va == vb)
        check(bool(ok), f"{tag}: info['{k}'] {va!r} != {vb!r}")


def lockstep(mod_a, mod_b, method, N, seed=42):
    rules = create_rules("rules.txt", "rotations_rules.txt")
    rules["END"] = None
    end_idx = list(rules.keys()).index("END") * 16

    allowed = {"1", "4", "8", "9", "16", "25", "32"}
    exprs = []
    with open(os.path.join("fhe_rl", "datasets", "final_llm_dataset.txt")) as f:
        for line in f:
            s = line.split(":")[0].strip()
            if not s:
                continue
            try:
                if str(len(parse_sexpr(s).args)) in allowed:
                    exprs.append(s)
            except Exception:
                continue
            if len(exprs) >= 80:
                break

    gnn = FHEFeatureExtractor(model_path=get_model_path("gnn_embeddings_model"))
    kw = dict(rules_list=rules, expressions=exprs, max_positions=16,
              embeddings_model=gnn, budget_options=[1500, 2000, 2600, 1000000],
              constraint_method=method, constraint_metric="mem",
              pref_list=[[1.0, 0.0], [0.5, 0.5], [0.0, 1.0]],
              n_cycle=1, n_budget=5, env_idx=0, verbose=False)
    ea, eb = mod_a.fheEnvUnified(**kw), mod_b.fheEnvUnified(**kw)
    oa, ia = ea.reset(seed=seed)
    ob, ib = eb.reset(seed=seed)
    cmp_obs(oa, ob, f"{method}/reset")
    rng = np.random.RandomState(777)
    for i in range(N):
        valid = np.flatnonzero(oa["action_mask"])
        if i % 29 == 28 and oa["action_mask"][end_idx] > 0:
            a = int(end_idx)                       # force terminal path
        elif i % 23 == 22:
            a = int(rng.randint(0, oa["action_mask"].size))  # often invalid
        elif len(valid):
            a = int(rng.choice(valid))
        else:
            a = 0
        ra = ea.step(a)
        rb = eb.step(a)
        cmp_obs(ra[0], rb[0], f"{method}/step{i}")
        check(ra[1] == rb[1], f"{method}/step{i}: reward {ra[1]} != {rb[1]}")
        check(ra[2] == rb[2] and ra[3] == rb[3],
              f"{method}/step{i}: flags ({ra[2]},{ra[3]}) != ({rb[2]},{rb[3]})")
        cmp_info(ra[4], rb[4], f"{method}/step{i}")
        oa, ob = ra[0], rb[0]
        if ra[2] or ra[3]:
            oa, ia = ea.reset()
            ob, ib = eb.reset()
            cmp_obs(oa, ob, f"{method}/re-reset@{i}")
    check(ea.get_fallback_count() == eb.get_fallback_count(),
          f"{method}: fallback count {ea.get_fallback_count()} != {eb.get_fallback_count()}")
    return ea, eb

print("=== Lockstep parity: nato_sc (500 steps, multiple episodes) ===", flush=True)
e1a, e1b = lockstep(OLD, NEW, "nato_sc", 500)
print(f"  NEW caches warm: emb={len(e1b._emb_cache)} mask={len(e1b._mask_cache)} "
      f"(OLD has no caches: {not hasattr(e1a, '_emb_cache')})", flush=True)

print("=== Lockstep parity: margin_barrier (120 steps, budget_margin obs) ===", flush=True)
lockstep(OLD, NEW, "margin_barrier", 120)

print("=== Lockstep parity: noise_masking (200 steps, budget-keyed masks) ===", flush=True)
lockstep(OLD, NEW, "noise_masking", 200)

print("=== Direct mask parity across budget switches (cache-hit correctness) ===", flush=True)
rules = create_rules("rules.txt", "rotations_rules.txt")
rules["END"] = None
with open(os.path.join("fhe_rl", "datasets", "benchmarks.txt")) as f:
    bench = [l.split(":")[0].strip() for l in f if l.strip()]
gnn = FHEFeatureExtractor(model_path=get_model_path("gnn_embeddings_model"))
kw = dict(rules_list=rules, expressions=bench, max_positions=16, embeddings_model=gnn,
          budget_options=[1500, 2000, 2600, 1000000], constraint_method="noise_masking",
          constraint_metric="mem", pref_list=[[0.5, 0.5]], n_cycle=0, n_budget=5,
          env_idx=0, verbose=False)
em, en = OLD.fheEnvUnified(**kw), NEW.fheEnvUnified(**kw)
em.reset(seed=1)
en.reset(seed=1)
for b in [1500, 2600, 1000000, 1500, 1000000, 2600, 1500]:
    em.set_noise_budget(b)
    en.set_noise_budget(b)
    ma, mb = em.get_action_mask(), en.get_action_mask()
    check(np.array_equal(ma, mb), f"mask parity broken at budget={b}")
check(len(en._mask_cache) > 0, "noise_masking mask cache never populated")
print(f"  mask cache entries after switches: {len(en._mask_cache)}", flush=True)

print("\n" + ("ALL PARITY CHECKS PASSED (v)" if not FAILURES
              else f"{len(FAILURES)} FAILURES (x)"), flush=True)
sys.exit(1 if FAILURES else 0)

