"""Fair A/B speedup benchmark: OLD (pre-optimization) vs NEW (fast-step) env
in the SAME process on the SAME action sequence. Reports wall time per env
and the speedup, plus counts _embed_expression calls per step in NEW
(expected: 1/step after removing the duplicate GNN call; OLD had 2/step)."""
import os
import sys
import time
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
import fhe_rl.env_unified as NEW

_spec = importlib.util.spec_from_file_location(
    "fhe_rl.env_unified_old", os.path.join(SCRIPT_DIR, ".diffref", "env_unified_old.py"))
OLD = importlib.util.module_from_spec(_spec)
sys.modules["fhe_rl.env_unified_old"] = OLD
_spec.loader.exec_module(OLD)

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
        if len(exprs) >= 300:
            break

gnn = FHEFeatureExtractor(model_path=get_model_path("gnn_embeddings_model"))
kw = dict(rules_list=rules, expressions=exprs, max_positions=16, embeddings_model=gnn,
          budget_options=[1500, 2000, 2600, 1000000], constraint_method="nato_sc",
          constraint_metric="mem", pref_list=[[1.0, 0.0], [0.5, 0.5]],
          n_cycle=1, n_budget=5, env_idx=0, verbose=False)
N = 250


def run(mod, tag, actions=None):
    env = mod.fheEnvUnified(**kw)
    if hasattr(env, "_emb_count_hook"):
        pass
    obs, _ = env.reset(seed=42)
    rng = np.random.RandomState(777)
    rec, t0 = [], time.perf_counter()
    for i in range(N):
        if actions is None:
            valid = np.flatnonzero(obs["action_mask"])
            valid = valid[valid // 16 != len(rules) - 1]
            a = int(rng.choice(valid)) if len(valid) else 0
            rec.append(a)
        else:
            a = actions[i]
        obs, r, term, trunc, info = env.step(a)
        if term or trunc:
            # NEW replays the same actions, so it reports termination at the
            # same indices (bit-identical) and resets align automatically.
            obs, _ = env.reset()
    wall = time.perf_counter() - t0
    print(f"  {tag}: {N} steps in {wall:.1f}s -> {wall/N*1000:.1f} ms/step", flush=True)
    return wall, rec


# Count embed calls per step in NEW
_orig_embed = NEW.fheEnvUnified._embed_expression
_calls = {"n": 0}
def _counted(self, expr):
    _calls["n"] += 1
    return _orig_embed(self, expr)
NEW.fheEnvUnified._embed_expression = _counted

# Phase 1: OLD drives (records actions), then NEW replays the same sequence
print("=== A/B benchmark (same process, same trajectory) ===", flush=True)
t_old, actions = run(OLD, "OLD (pre-optimization)")
_calls["n"] = 0
t_new, _ = run(NEW, "NEW (fast-step)     ", actions)
embeds_per_step = _calls["n"] / N
print(f"\n  speedup: {t_old/t_new:.2f}x  ({t_old/N*1000:.0f} -> {t_new/N*1000:.0f} ms/step)", flush=True)
print(f"  NEW _embed_expression calls per step: {embeds_per_step:.2f} (expected ~1.0)", flush=True)
print(f"  projected 5M-step env wall (8 envs): "
      f"{(5_000_000/8)*t_old/N/3600:.0f}h -> {(5_000_000/8)*t_new/N/3600:.0f}h", flush=True)
