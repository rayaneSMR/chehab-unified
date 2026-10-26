#!/usr/bin/env python3
import csv
import math
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import scipy.optimize
from sklearn.model_selection import GroupKFold

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent

sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "RL" / "pytrs"))

import packing  # noqa: E402

csv_path = REPO / "RL" / "veclang_runner" / "temp" / "pilot_results_packed.csv"
if not csv_path.exists():
    print(f"Error: {csv_path} does not exist!")
    sys.exit(1)

with open(csv_path, "r", encoding="utf-8") as f:
    all_rows = list(csv.DictReader(f))

def is_zero(v):
    try:
        return int(float(v or 0)) == 0
    except ValueError:
        return False

rows = [r for r in all_rows if r.get("status") == "ok" and is_zero(r.get("est_G"))]
print(f"Total rows in packed CSV with status=='ok' and est_G==0: {len(rows)} (expect 397)")

# -----------------------------------------------------------------------------
# ITEM 1: Parameter match for specific pilot_ids and overall
# -----------------------------------------------------------------------------
print("\n" + "=" * 70)
print("ITEM 1: PARAMETER MATCH (est_N, est_L vs go_N, go_L)")
print("=" * 70)

check_ids = ["173", "pair0_rw", "pair14_rw", "pair23_rw", "pair50_rw", "pair99_rw"]
rows_by_id = {r["pilot_id"]: r for r in rows}

print(f"{'pilot_id':>12} {'est_N':>8} {'est_L':>6} {'go_N':>8} {'go_L':>6} {'param_match':>12} {'max_rss_MB_median':>18}")
print("-" * 74)
for pid in check_ids:
    r = rows_by_id.get(pid)
    if r:
        print(f"{pid:>12} {r.get('est_N', ''):>8} {r.get('est_L', ''):>6} {r.get('go_N', ''):>8} {r.get('go_L', ''):>6} {r.get('param_match', ''):>12} {r.get('max_rss_MB_median', ''):>18}")
    else:
        print(f"{pid:>12} NOT FOUND")

mismatch_nl = 0
for r in rows:
    try:
        en = int(float(r["est_N"]))
        el = int(float(r["est_L"]))
        gn = int(float(r["go_N"]))
        gl = int(float(r["go_L"]))
        if (en, el) != (gn, gl):
            mismatch_nl += 1
    except (ValueError, KeyError):
        mismatch_nl += 1

print(f"\nrows (all {len(rows)}) where (est_N,est_L) != (go_N,go_L): {mismatch_nl}/{len(rows)}")

# -----------------------------------------------------------------------------
# ITEM 2: max_rss_spread distribution
# -----------------------------------------------------------------------------
print("\n" + "=" * 70)
print("ITEM 2: DISTRIBUTION OF max_rss_spread PER N-GROUP")
print("=" * 70)

raw_spreads_sample = [r.get("max_rss_spread", "") for r in rows[:5]]
print(f"First 5 raw values of max_rss_spread column: {raw_spreads_sample}")

for grp_name, sel in [("<=16384", lambda n: n <= 16384), (">16384", lambda n: n > 16384)]:
    sub = [r for r in rows if sel(int(float(r["est_N"])))]
    sp_vals = []
    for r in sub:
        v = r.get("max_rss_spread", "")
        try:
            sp_vals.append(float(v))
        except ValueError:
            pass
    sp_arr = np.array(sp_vals)
    print(f"N-group {grp_name} (n={len(sp_arr)}): min={sp_arr.min():.2f} MB, p50={np.percentile(sp_arr, 50):.2f} MB, p90={np.percentile(sp_arr, 90):.2f} MB, max={sp_arr.max():.2f} MB")

# -----------------------------------------------------------------------------
# Helper fitting functions
# -----------------------------------------------------------------------------
def fit_ratio(e_tr, y_tr):
    return float(np.median(y_tr / e_tr))

def pred_ratio(r, e_te):
    return r * e_te

def fit_affine(e_tr, y_tr):
    A = np.column_stack([np.ones(len(e_tr)), e_tr])
    res, _ = scipy.optimize.nnls(A, y_tr)
    return float(res[0]), float(res[1])

def pred_affine(params, e_te):
    a, s = params
    return a + s * e_te

def fit_loglog(e_tr, y_tr, L_tr):
    A = np.column_stack([np.ones(len(e_tr)), np.log(e_tr), L_tr])
    c, *_ = np.linalg.lstsq(A, np.log(y_tr), rcond=None)
    return float(c[0]), float(c[1]), float(c[2])

def pred_loglog(params, e_te, L_te):
    a, b, cL = params
    return np.exp(a + b * np.log(e_te) + cL * L_te)

# -----------------------------------------------------------------------------
# ITEM 4: Two CV Schemes (CV-A and CV-B)
# -----------------------------------------------------------------------------
print("\n" + "=" * 70)
print("ITEM 4: CV EVALUATION (CV-A: GroupKFold(5) on (N,L,n_c), CV-B: Leave-one-L-out)")
print("=" * 70)

# Precompute n_c for all rows
for r in rows:
    try:
        r["n_c"] = packing.pack(r["expr"])[1]
    except Exception:
        r["n_c"] = 1

oof_preds_cva = {}  # for item 5: pilot_id -> (oof_ratio, oof_affine, oof_loglog)

cv_results = []

for grp_name, sel in [("<=16384", lambda n: n <= 16384), (">16384", lambda n: n > 16384)]:
    sub = [r for r in rows if sel(int(float(r["est_N"])))]
    e = np.array([float(r["est_net_MB"]) for r in sub])
    y = np.array([float(r["max_rss_MB_median"]) for r in sub])
    L = np.array([float(r["est_L"]) for r in sub])
    pids = [r["pilot_id"] for r in sub]
    
    # --- CV-A: GroupKFold(5) on (N, L, n_c) ---
    group_ids = [f"{r['est_N']}_{r['est_L']}_{r['n_c']}" for r in sub]
    unique_groups = {g: i for i, g in enumerate(sorted(set(group_ids)))}
    groups_arr = np.array([unique_groups[g] for g in group_ids])
    
    oof_cva = {m: np.zeros(len(sub)) for m in ["ratio", "affine", "loglog"]}
    gkf = GroupKFold(n_splits=5)
    for tr_idx, te_idx in gkf.split(e, y, groups=groups_arr):
        # ratio
        r_val = fit_ratio(e[tr_idx], y[tr_idx])
        oof_cva["ratio"][te_idx] = pred_ratio(r_val, e[te_idx])
        
        # affine
        aff_params = fit_affine(e[tr_idx], y[tr_idx])
        oof_cva["affine"][te_idx] = pred_affine(aff_params, e[te_idx])
        
        # loglog
        ll_params = fit_loglog(e[tr_idx], y[tr_idx], L[tr_idx])
        oof_cva["loglog"][te_idx] = pred_loglog(ll_params, e[te_idx], L[te_idx])
        
    for i, pid in enumerate(pids):
        oof_preds_cva[pid] = (float(oof_cva["ratio"][i]), float(oof_cva["affine"][i]), float(oof_cva["loglog"][i]))

    for model_name in ["ratio", "affine", "loglog"]:
        pred = oof_cva[model_name]
        err = (pred - y) / y * 100.0
        abs_err = np.abs(err)
        worst_i = int(np.argmax(abs_err))
        worst_tuple = (str(pids[worst_i]), round(float(y[worst_i]), 2), round(float(pred[worst_i]), 2))
        cv_results.append({
            "group": grp_name, "model": model_name, "scheme": "CV-A",
            "n_test": len(sub), "p50": float(np.percentile(abs_err, 50)), "p90": float(np.percentile(abs_err, 90)),
            "median_signed": float(np.median(err)), "under": f"{int(np.sum(pred < y))}/{len(sub)}",
            "worst": worst_tuple
        })

    # --- CV-B: Leave-one-L-out ---
    l_counts = Counter(L)
    valid_Ls = sorted([l_val for l_val, cnt in l_counts.items() if cnt >= 3])
    skipped_Ls = sorted([l_val for l_val, cnt in l_counts.items() if cnt < 3])
    if skipped_Ls:
        print(f"CV-B note for group {grp_name}: skipped L with <3 rows: {skipped_Ls}")
    else:
        print(f"CV-B note for group {grp_name}: no L skipped (all L counts >= 3: {dict(sorted(l_counts.items()))})")

    oof_cvb = {m: [] for m in ["ratio", "affine", "loglog"]}
    y_cvb = []
    pids_cvb = []
    
    for l_val in valid_Ls:
        te_mask = (L == l_val)
        tr_mask = (L != l_val)
        
        # ratio
        r_val = fit_ratio(e[tr_mask], y[tr_mask])
        oof_cvb["ratio"].extend(pred_ratio(r_val, e[te_mask]))
        
        # affine
        aff_params = fit_affine(e[tr_mask], y[tr_mask])
        oof_cvb["affine"].extend(pred_affine(aff_params, e[te_mask]))
        
        # loglog
        ll_params = fit_loglog(e[tr_mask], y[tr_mask], L[tr_mask])
        oof_cvb["loglog"].extend(pred_loglog(ll_params, e[te_mask], L[te_mask]))
        
        y_cvb.extend(y[te_mask])
        pids_cvb.extend([pids[i] for i in range(len(pids)) if te_mask[i]])
        
    y_cvb = np.array(y_cvb)
    for model_name in ["ratio", "affine", "loglog"]:
        pred = np.array(oof_cvb[model_name])
        err = (pred - y_cvb) / y_cvb * 100.0
        abs_err = np.abs(err)
        worst_i = int(np.argmax(abs_err))
        worst_tuple = (str(pids_cvb[worst_i]), round(float(y_cvb[worst_i]), 2), round(float(pred[worst_i]), 2))
        cv_results.append({
            "group": grp_name, "model": model_name, "scheme": "CV-B",
            "n_test": len(y_cvb), "p50": float(np.percentile(abs_err, 50)), "p90": float(np.percentile(abs_err, 90)),
            "median_signed": float(np.median(err)), "under": f"{int(np.sum(pred < y_cvb))}/{len(y_cvb)}",
            "worst": worst_tuple
        })

print(f"\n{'group':>8} {'scheme':>6} {'model':>8} | {'n_test':>6} {'p50|err|%':>10} {'p90|err|%':>10} {'signed%':>9} {'under':>8} | {'worst (pilot_id, true, pred)'}")
print("-" * 88)
for res in cv_results:
    print(f"{res['group']:>8} {res['scheme']:>6} {res['model']:>8} | {res['n_test']:>6} {res['p50']:>10.2f} {res['p90']:>10.2f} {res['median_signed']:>9.2f} {res['under']:>8} | {res['worst']}")

# -----------------------------------------------------------------------------
# ITEM 5: Rows in N <= 16384 with est_net_MB > 150
# -----------------------------------------------------------------------------
print("\n" + "=" * 70)
print("ITEM 5: N <= 16384 ROWS WITH est_net_MB > 150")
print("=" * 70)

sub_16k = [r for r in rows if int(float(r["est_N"])) <= 16384]
large_16k = [r for r in sub_16k if float(r["est_net_MB"]) > 150.0]
print(f"Total rows in N<=16384 group: {len(sub_16k)}")
print(f"Rows with est_net_MB > 150: {len(large_16k)} (expected 7 in 297-row set; real count in 397-row set: {len(large_16k)})\n")

print(f"{'pilot_id':>12} {'est_net_MB':>11} {'est_L':>6} {'true_rss':>9} | {'oof_ratio':>10} {'oof_affine':>11} {'oof_loglog':>11}")
print("-" * 77)
for r in large_16k:
    pid = r["pilot_id"]
    net = float(r["est_net_MB"])
    l_val = int(float(r["est_L"]))
    tr_rss = float(r["max_rss_MB_median"])
    oof_r, oof_a, oof_ll = oof_preds_cva[pid]
    print(f"{pid:>12} {net:>11.3f} {l_val:>6} {tr_rss:>9.2f} | {oof_r:>10.2f} {oof_a:>11.2f} {oof_ll:>11.2f}")

# -----------------------------------------------------------------------------
# ITEM 6: Fitted parameters on ALL rows of each group
# -----------------------------------------------------------------------------
print("\n" + "=" * 70)
print("ITEM 6: FULL-DATASET FITTED PARAMETERS PER GROUP")
print("=" * 70)

for grp_name, sel in [("<=16384", lambda n: n <= 16384), (">16384", lambda n: n > 16384)]:
    sub = [r for r in rows if sel(int(float(r["est_N"])))]
    e = np.array([float(r["est_net_MB"]) for r in sub])
    y = np.array([float(r["max_rss_MB_median"]) for r in sub])
    L = np.array([float(r["est_L"]) for r in sub])
    
    r_val = fit_ratio(e, y)
    a_aff, s_aff = fit_affine(e, y)
    a_ll, b_ll, c_ll = fit_loglog(e, y, L)
    
    print(f"Group {grp_name} (n={len(sub)}):")
    print(f"  ratio : r = {r_val:.5f}")
    print(f"  affine: a = {a_aff:.5f}, s = {s_aff:.5f}")
    print(f"  loglog: a = {a_ll:.5f}, b = {b_ll:.5f}, cL = {c_ll:.5f}\n")
