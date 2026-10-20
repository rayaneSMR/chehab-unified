"""Micro-profile: GNN collate (python graph build) vs GAT forward, and
action-mask/GNN cost on GROWN (rewritten) expressions."""
import os, sys, time
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
from fhe_rl.GNNAE import collate_fn_gnn, Graph2Seq, graph_builder
from fhe_rl.gnn_embeddings import FHEFeatureExtractor

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
        if len(exprs) >= 40:
            break

gnn = FHEFeatureExtractor(model_path=get_model_path("gnn_embeddings_model"))
model = gnn.model

def tavg(fn, n=20):
    t0 = time.perf_counter()
    for _ in range(n):
        fn()
    return (time.perf_counter() - t0) / n

# --- split collate vs forward ---
sample = [parse_sexpr(s) for s in exprs[:20]]

def collate_all():
    for p in sample:
        collate_fn_gnn([p])

t_collate = tavg(collate_all, n=10) / len(sample)

bd, _ = collate_fn_gnn([sample[0]])
bd = bd.to("cpu")
def fwd():
    with torch.no_grad():
        model.get_embedding(bd)
t_fwd_0 = tavg(fwd, n=20)

# per-expr size vs forward time
print(f"{'nodes':>6} {'edges':>6} {'chars':>7} {'collate ms':>10} {'fwd ms':>8}")
for p in sample[:10]:
    bd, _ = collate_fn_gnn([p])
    tc = tavg(lambda pp=p: collate_fn_gnn([pp]), n=10)
    b2 = bd.to("cpu")
    def fw(b=b2):
        with torch.no_grad():
            model.get_embedding(b)
    tf = tavg(fw, n=20)
    chars = len(p) if isinstance(p, str) else len(str(p))
    print(f"{bd.num_nodes:6d} {bd.edge_index.shape[1]:6d} {chars:7d} {tc*1000:10.2f} {tf*1000:8.2f}")

print(f"\navg collate (20 exprs): {t_collate*1000:.2f} ms | avg fwd: {t_fwd_0*1000:.2f} ms")

# --- grow an expression with vectorization rewrites, re-time mask & GNN ---
print("\n=== grown expression test (apply vectorize rules repeatedly) ===")
e = parse_sexpr(exprs[0])
s_cur = None
for it in range(6):
    from pytrs import expr_to_str
    s_cur = expr_to_str(e)
    best_rn, best_k = None, None
    for rn in rule_names:
        if rn == "END" or "vectorize" not in rn:
            continue
        try:
            m = rules[rn].find_matching_subexpressions(e)
        except Exception:
            continue
        if m:
            best_rn, best_k = rn, m[0][0]
            break
    if best_rn is None:
        print(f"iter {it}: no vectorize match; expr chars={len(s_cur)}")
        break
    t0 = time.perf_counter()
    e = rules[best_rn].apply_rule(e, path=best_k)
    t_apply = time.perf_counter() - t0
    s_cur = expr_to_str(e)
    # mask timing
    def mask_it():
        for rn in rule_names:
            if rn == "END":
                continue
            try:
                rules[rn].find_matching_subexpressions(e)
            except Exception:
                pass
    tm = tavg(mask_it, n=3)
    def emb_it():
        gnn.get_embedding(s_cur)
    te = tavg(emb_it, n=5)
    print(f"iter {it}: rule={best_rn:<25} chars={len(s_cur):6d} apply={t_apply*1000:7.1f}ms "
          f"mask={tm*1000:7.1f}ms gnn={te*1000:7.1f}ms", flush=True)
