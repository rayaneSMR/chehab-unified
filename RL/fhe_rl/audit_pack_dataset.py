import contextlib
import io
import math
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent

sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "RL" / "pytrs"))

import memory
import parser
from ckks_memory_estimator import estimate_expression_memory

print("=" * 70)
print(f"memory.CALIB_PATH        : {memory.CALIB_PATH}")
print(f"memory.ESTIMATOR_VERSION : {memory.ESTIMATOR_VERSION}")
print("=" * 70)

dataset_path = HERE / "datasets" / "final_llm_dataset.txt"
if not dataset_path.exists():
    print(f"Error: {dataset_path} does not exist!")
    sys.exit(1)

with open(dataset_path, "r", encoding="utf-8") as f:
    lines = [line.strip() for line in f if line.strip()]

total_lines = len(lines)
print(f"Total non-empty lines in dataset: {total_lines}")

devnull = io.StringIO()

records = []
for expr in lines:
    # 1. orig_ok
    try:
        with contextlib.redirect_stdout(devnull), contextlib.redirect_stderr(devnull):
            parser.parse_sexpr(expr)
        orig_ok = True
    except Exception:
        orig_ok = False

    # 2. raw
    try:
        with contextlib.redirect_stdout(devnull), contextlib.redirect_stderr(devnull):
            raw_est = estimate_expression_memory(expr, "cpu")
        raw_ok = True
        raw_N = int(raw_est.params.N)
        raw_L = int(raw_est.params.L)
        raw_K = int(raw_est.params.K)
        raw_mb = float(raw_est.total_mb)
    except Exception:
        raw_ok = False
        raw_N, raw_L, raw_K, raw_mb = None, None, None, None

    # 3. packed
    try:
        with contextlib.redirect_stdout(devnull), contextlib.redirect_stderr(devnull):
            p_est = memory.peak_ram_breakdown(expr, margin=False)
        packed_ok = True
        p_mb = float(p_est["mb"])
        p_N = int(p_est["N"])
        p_L = int(p_est["L"])
        p_K = int(p_est["K"])
        p_G = int(p_est["G"])
        p_packed_flag = bool(p_est["packed"])
        p_raw_net_mb = float(p_est["raw_net_mb"])
        p_live_cts = int(p_est["live_cts"])
    except Exception:
        packed_ok = False
        p_mb, p_N, p_L, p_K, p_G, p_packed_flag, p_raw_net_mb, p_live_cts = None, None, None, None, None, None, None, None

    records.append({
        "expr": expr,
        "len_expr": len(expr),
        "orig_ok": orig_ok,
        "raw_ok": raw_ok,
        "raw_N": raw_N,
        "raw_L": raw_L,
        "raw_K": raw_K,
        "raw_mb": raw_mb,
        "packed_ok": packed_ok,
        "p_mb": p_mb,
        "p_N": p_N,
        "p_L": p_L,
        "p_K": p_K,
        "p_G": p_G,
        "p_packed_flag": p_packed_flag,
        "p_raw_net_mb": p_raw_net_mb,
        "p_live_cts": p_live_cts
    })

# -----------------------------------------------------------------------------
# ITEM 1: Counts
# -----------------------------------------------------------------------------
print("\n" + "=" * 70)
print("ITEM 1: OVERALL EVALUATION COUNTS")
print("=" * 70)

both_ok = sum(1 for r in records if r["raw_ok"] and r["packed_ok"])
raw_fail_packed_ok = sum(1 for r in records if (not r["raw_ok"]) and r["packed_ok"])
raw_ok_packed_fail = sum(1 for r in records if r["raw_ok"] and (not r["packed_ok"]))
both_fail = sum(1 for r in records if (not r["raw_ok"]) and (not r["packed_ok"]))

print(f"raw_ok and packed_ok both : {both_ok}/{total_lines} ({both_ok/total_lines*100:.2f}%)")
print(f"raw failed but packed ok  : {raw_fail_packed_ok}/{total_lines} ({raw_fail_packed_ok/total_lines*100:.2f}%)")
print(f"raw ok but packed failed  : {raw_ok_packed_fail}/{total_lines} ({raw_ok_packed_fail/total_lines*100:.2f}%)")
print(f"both failed               : {both_fail}/{total_lines} ({both_fail/total_lines*100:.2f}%)")

# -----------------------------------------------------------------------------
# ITEM 2: Parameter differences among both_ok
# -----------------------------------------------------------------------------
print("\n" + "=" * 70)
print("ITEM 2: PARAMETER DIFFERENCES AMONG LINES WITH BOTH OK")
print("=" * 70)

both_ok_recs = [r for r in records if r["raw_ok"] and r["packed_ok"]]
n_both = len(both_ok_recs)

diff_nl_recs = [r for r in both_ok_recs if (r["p_N"], r["p_L"]) != (r["raw_N"], r["raw_L"])]
k_diff = len(diff_nl_recs)

l_gt = [r for r in both_ok_recs if r["p_L"] > r["raw_L"]]
l_lt = [r for r in both_ok_recs if r["p_L"] < r["raw_L"]]
n_gt = [r for r in both_ok_recs if r["p_N"] > r["raw_N"]]
n_lt = [r for r in both_ok_recs if r["p_N"] < r["raw_N"]]

print(f"(N,L) differ      : {k_diff}/{n_both} ({k_diff/n_both*100:.2f}%)")
print(f"  L_packed > L_raw: {len(l_gt)}/{n_both}")
print(f"  L_packed < L_raw: {len(l_lt)}/{n_both}")
print(f"  N_packed > N_raw: {len(n_gt)}/{n_both}")
print(f"  N_packed < N_raw: {len(n_lt)}/{n_both}")

gt_examples = [r for r in both_ok_recs if r["p_L"] > r["raw_L"] or r["p_N"] > r["raw_N"]]
print(f"\nExamples of L_packed > L_raw or N_packed > N_raw (total matching: {len(gt_examples)}, showing up to 5):")
for i, r in enumerate(gt_examples[:5], 1):
    raw_params = f"({r['raw_N']},{r['raw_L']},{r['raw_K']})"
    p_params = f"({r['p_N']},{r['p_L']},{r['p_K']})"
    print(f"Example {i}:")
    print(f"  raw (N,L,K)   : {raw_params}, raw mb: {r['raw_mb']:.2f}")
    print(f"  packed (N,L,K): {p_params}, packed mb: {r['p_mb']:.2f}")
    print(f"  len(expr)     : {r['len_expr']}")
    print(f"  first 150 ch  : {r['expr'][:150]}")

# -----------------------------------------------------------------------------
# ITEM 3: Among raw failed but packed ok
# -----------------------------------------------------------------------------
print("\n" + "=" * 70)
print("ITEM 3: AMONG 'RAW FAILED BUT PACKED OK'")
print("=" * 70)

rf_po = [r for r in records if (not r["raw_ok"]) and r["packed_ok"]]
n_rf_po = len(rf_po)
orig_fail_in_rf_po = [r for r in rf_po if not r["orig_ok"]]
k_orig_fail = len(orig_fail_in_rf_po)

print(f"Count with orig_ok == False: {k_orig_fail}/{n_rf_po}")
print("\n3 Examples of raw failed but packed ok with orig_ok == False:")
for i, r in enumerate(orig_fail_in_rf_po[:3], 1):
    print(f"Example {i}: len={r['len_expr']}")
    print(f"  LAST 120 chars: {r['expr'][-120:]}")

# -----------------------------------------------------------------------------
# ITEM 4: Top 10 lines overall by packed mb
# -----------------------------------------------------------------------------
print("\n" + "=" * 70)
print("ITEM 4: TOP 10 LINES OVERALL BY PACKED MB")
print("=" * 70)

valid_packed = [r for r in records if r["packed_ok"]]
valid_packed.sort(key=lambda x: x["p_mb"], reverse=True)
top10_overall = valid_packed[:10]

print(f"{'rank':>4} {'mb':>9} {'N':>6} {'L':>3} {'K':>2} {'G':>2} {'raw_ok':>7} {'raw(N,L,K)':>12} {'raw_mb':>9} {'len':>6} {'orig_ok':>8} | {'first 150 chars'}")
print("-" * 95)
for i, r in enumerate(top10_overall, 1):
    raw_params_str = f"({r['raw_N']},{r['raw_L']},{r['raw_K']})" if r["raw_ok"] else "N/A"
    raw_mb_str = f"{r['raw_mb']:.2f}" if r["raw_ok"] else "N/A"
    print(f"{i:>4} {r['p_mb']:>9.2f} {r['p_N']:>6} {r['p_L']:>3} {r['p_K']:>2} {r['p_G']:>2} {str(r['raw_ok']):>7} {raw_params_str:>12} {raw_mb_str:>9} {r['len_expr']:>6} {str(r['orig_ok']):>8} | {r['expr'][:150]}")

# -----------------------------------------------------------------------------
# ITEM 5: Distinct packed (N,L,K) table and out-of-set N
# -----------------------------------------------------------------------------
print("\n" + "=" * 70)
print("ITEM 5: DISTINCT PACKED (N,L,K) VALUES & COUNTS")
print("=" * 70)

nlk_counts = Counter((r["p_N"], r["p_L"], r["p_K"]) for r in valid_packed)
print(f"{'N':>8} {'L':>4} {'K':>3} | {'count':>8} {'share%':>8}")
print("-" * 30)
for (n_val, l_val, k_val), cnt in sorted(nlk_counts.items(), key=lambda x: (x[0][0], x[0][1], x[0][2])):
    print(f"{n_val:>8} {l_val:>4} {k_val:>3} | {cnt:>8} {cnt/len(valid_packed)*100:>7.2f}%")

bad_n = [r for r in valid_packed if r["p_N"] not in {16384, 32768}]
print(f"\nlines with N not in {{16384, 32768}}: {len(bad_n)}/{len(valid_packed)}")

# -----------------------------------------------------------------------------
# ITEM 6: Percentiles restricted to orig_ok == True lines
# -----------------------------------------------------------------------------
print("\n" + "=" * 70)
print("ITEM 6: PERCENTILES OF PACKED MB (RESTRICTED TO orig_ok == True)")
print("=" * 70)

clean_recs = [r for r in valid_packed if r["orig_ok"]]

groups_p = [
    ("ALL (clean)", clean_recs),
    ("<=16384", [r for r in clean_recs if r["p_N"] <= 16384]),
    (">16384", [r for r in clean_recs if r["p_N"] > 16384])
]

print(f"{'group':>12} | {'n':>6} {'p50':>8} {'p90':>8} {'p95':>8} {'p99':>8} {'p99.9':>8} {'max':>10}")
print("-" * 75)
for name, recs in groups_p:
    arr = np.array([r["p_mb"] for r in recs])
    n = len(arr)
    p50 = np.percentile(arr, 50)
    p90 = np.percentile(arr, 90)
    p95 = np.percentile(arr, 95)
    p99 = np.percentile(arr, 99)
    p99_9 = np.percentile(arr, 99.9)
    mx = np.max(arr)
    print(f"{name:>12} | {n:>6} {p50:>8.2f} {p90:>8.2f} {p95:>8.2f} {p99:>8.2f} {p99_9:>8.2f} {mx:>10.2f}")

# -----------------------------------------------------------------------------
# ITEM 7: SELECTION FOR NEXT PHASE
# -----------------------------------------------------------------------------
print("\n" + "=" * 70)
print("ITEM 7: SELECTION FOR NEXT PHASE (top16384_exprs_v2.txt)")
print("=" * 70)

# Restrict to N<=16384, orig_ok==True, unique expression strings, G==0
cand_pool = [r for r in valid_packed if r["p_N"] <= 16384 and r["orig_ok"] and r["p_G"] == 0]

# Deduplicate by expr string
cand_unique = {}
for r in cand_pool:
    if r["expr"] not in cand_unique:
        cand_unique[r["expr"]] = r
cand_list = list(cand_unique.values())
print(f"Candidate pool after filter (N<=16384, orig_ok==True, G==0, deduplicated): {len(cand_list)}")

# Group by (round(raw_net_mb, 1), L)
groups_dict = defaultdict(list)
for r in cand_list:
    key = (round(r["p_raw_net_mb"], 1), r["p_L"])
    groups_dict[key].append(r)

# Rank groups by highest packed mb (max packed mb in the group)
sorted_groups = sorted(groups_dict.items(), key=lambda kv: max(x["p_mb"] for x in kv[1]), reverse=True)

# Pick top 4 groups (one expression each, shortest)
selected_recs = []
taken_keys = set()

for key, grp_items in sorted_groups[:4]:
    shortest = min(grp_items, key=lambda x: x["len_expr"])
    selected_recs.append(shortest)
    taken_keys.add(key)

# Among groups with 150 <= raw_net_mb <= 273.6 NOT already taken, pick 6 evenly spaced
mid_groups = [
    (key, grp_items) for key, grp_items in groups_dict.items()
    if 150.0 <= key[0] <= 273.6 and key not in taken_keys
]
# Sort ascending by raw_net_mb, then L
mid_groups.sort(key=lambda kv: (kv[0][0], kv[0][1]))

print(f"Available mid groups (150 <= raw_net_mb <= 273.6, not taken): {len(mid_groups)}")

M = len(mid_groups)
if M < 6:
    print(f"Warning: only {M} groups available in range!")
    spaced_indices = list(range(M))
else:
    spaced_indices = [int(round(idx)) for idx in np.linspace(0, M - 1, 6)]

for idx in spaced_indices:
    key, grp_items = mid_groups[idx]
    shortest = min(grp_items, key=lambda x: x["len_expr"])
    selected_recs.append(shortest)
    taken_keys.add(key)

out_v2_path = HERE.parent / "veclang_runner" / "temp" / "top16384_exprs_v2.txt"
out_v2_path.parent.mkdir(parents=True, exist_ok=True)

with open(out_v2_path, "w", encoding="utf-8") as f:
    for r in selected_recs:
        f.write(r["expr"] + "\n")

print(f"\n{'rank':>4} {'packed_mb':>10} {'raw_net_mb':>11} {'L':>4} {'live_cts':>9} {'len(expr)':>10}")
print("-" * 55)
for i, r in enumerate(selected_recs, 1):
    print(f"{i:>4} {r['p_mb']:>10.2f} {r['p_raw_net_mb']:>11.2f} {r['p_L']:>4} {r['p_live_cts']:>9} {r['len_expr']:>10}")

print(f"\nWrote {len(selected_recs)} expressions to {out_v2_path}")
sys.stdout.flush()
os.system(f"wc -l {out_v2_path}")
