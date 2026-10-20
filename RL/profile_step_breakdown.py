"""Attribution profile: monkeypatch env components to attribute every ms of
fheEnvUnified.step() to: GNN embed, action mask, cost, RAM estimate,
rotation_steps, and the remainder (parse/match/apply/serialize)."""
import os, sys, time, functools
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)
for p in (SCRIPT_DIR, os.path.join(SCRIPT_DIR, "pytrs")):
    if p not in sys.path:
        sys.path.insert(0, p)
import numpy as np
import torch
torch.set_num_threads(1)
from fhe_rl.config import set_framework, get_model_path
set_framework("unified")
from pytrs import create_rules, parse_sexpr
from fhe_rl.gnn_embeddings import FHEFeatureExtractor
from fhe_rl.config import get_model_path
import fhe_rl.env_unified as EU
from fhe_rl.env_unified import fheEnvUnified

ACC = {}
def acc(key, dt):
    ACC[key] = ACC.get(key, 0.0) + dt

def wrap(obj, name, key):
    orig = getattr(obj, name)
    @functools.wraps(orig)
    def inner(*a, **kw):
        t0 = time.perf_counter()
        r = orig(*a, **kw)
        acc(key, time.perf_counter() - t0)
        return r
    setattr(obj, name, inner)
    return orig

rules = create_rules("rules.txt", "rotations_rules.txt")
rules["END"] = None
rule_names = list(rules.keys())

allowed = {"1", "4", "8", "9", "16", "25", "32"}
exprs = []
with open(os.path.join("fhe_rl", "datasets", "final_llm_dataset.txt")) as f:
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

gnn = FHEFeatureExtractor(model_path=get_model_path("gnn_embeddings_model"))
env = fheEnvUnified(
    rules, exprs, max_positions=16, embeddings_model=gnn,
    budget_options=[1500, 2000, 2600, 1000000], constraint_method="nato_sc",
    constraint_metric="mem", pref_list=[[1.0, 0.0], [0.5, 0.5]],
    n_cycle=1, n_budget=5, env_idx=0, verbose=False,
)

wrap(env, "_embed_expression", "gnn_embed")
wrap(env, "get_action_mask", "action_mask")
wrap(env, "get_cost", "get_cost")
wrap(env, "get_split_costs", "get_split_costs")
wrap(env, "_estimate", "ram_estimate")
_orig_rot = EU.rotation_steps
def _rot(expr, *a, **kw):
    t0 = time.perf_counter()
    r = _orig_rot(expr, *a, **kw)
    acc("rotation_steps", time.perf_counter() - t0)
    return r
EU.rotation_steps = _rot

N = 120
obs, info = env.reset()
t_wall0 = time.perf_counter()
steps = 0
chars = []
for i in range(N):
    valid = np.flatnonzero(obs["action_mask"])
    valid = valid[valid // 16 != len(rule_names) - 1]
    if len(valid) == 0:
        obs, _ = env.reset()
        continue
    a = int(np.random.choice(valid))
    t0 = time.perf_counter()
    obs, r, term, trunc, info = env.step(a)
    acc("step_wall", time.perf_counter() - t0)
    steps += 1
    chars.append(len(env.expression))
    if term or trunc:
        obs, _ = env.reset()
wall = time.perf_counter() - t_wall0

print(f"\nsteps={steps} | total wall={wall:.1f}s | mean step={ACC['step_wall']/steps*1000:.0f} ms")
print(f"expr chars during run: mean={np.mean(chars):.0f} p90={np.percentile(chars,90):.0f} max={max(chars)}\n")
print(f"{'component':<20} {'total s':>9} {'ms/step':>9} {'%step':>7}")
gw = ACC["step_wall"]
attributed = 0.0
for k in ["gnn_embed", "action_mask", "get_cost", "get_split_costs", "ram_estimate",
          "rotation_steps"]:
    v = ACC.get(k, 0.0)
    attributed += v
    print(f"{k:<20} {v:9.2f} {v/steps*1000:9.1f} {100*v/gw:6.1f}%")
rest = gw - attributed
print(f"{'other(step-internal)':<20} {rest:9.2f} {rest/steps*1000:9.1f} {100*rest/gw:6.1f}%")
print(f"{'TOTAL step':<20} {gw:9.2f} {gw/steps*1000:9.1f} {100.0:6.1f}%")
