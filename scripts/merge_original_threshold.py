#!/usr/bin/env python3
"""Merge the per-benchmark results of the original CHEHAB RL agent on the threshold dataset.

    python scripts/merge_original_threshold.py OUT_DIR [N_EXPECTED]

Reads OUT_DIR/original_thr_<index>.csv and writes OUT_DIR/original_threshold_ALL.xlsx:
  all_runs : one row per benchmark x budget
  summary  : per budget, violations on all / feasible / infeasible programs
  missing  : benchmark indices without a result (failed or unfinished jobs)
"""
import sys
from pathlib import Path

import pandas as pd


def main(out_dir, n_expected=60):
    out_dir = Path(out_dir)
    files = sorted(out_dir.glob("original_thr_*.csv"))
    if not files:
        sys.exit(f"No original_thr_*.csv in {out_dir}")
    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    df = df.sort_values(["Budget", "Expression #"]).reset_index(drop=True)

    rows = []
    for b, g in df.groupby("Budget"):
        f, inf = g[g["Is Feasible"]], g[~g["Is Feasible"]]
        rows.append({
            "Budget": b, "N": len(g), "Feasible": len(f), "Infeasible": len(inf),
            "Violations": int(g["Agent Violated"].sum()),
            "Violations (%)": round(100 * g["Agent Violated"].mean(), 1),
            "Violations feasible": int(f["Agent Violated"].sum()),
            "Violations feasible (%)": round(100 * f["Agent Violated"].mean(), 1) if len(f) else None,
            "Violations infeasible": int(inf["Agent Violated"].sum()),
            "Mean final noise (bits)": round(g["Agent Final Noise"].mean(), 2),
        })
    summary = pd.DataFrame(rows)

    done = set(df["Expression #"] - 1)
    missing = pd.DataFrame({"Missing index": [i for i in range(n_expected) if i not in done]})

    out = out_dir / "original_threshold_ALL.xlsx"
    with pd.ExcelWriter(out) as w:
        df.to_excel(w, sheet_name="all_runs", index=False)
        summary.to_excel(w, sheet_name="summary", index=False)
        missing.to_excel(w, sheet_name="missing", index=False)
    print(summary.to_string(index=False))
    if len(missing):
        print(f"\nMissing indices: {missing['Missing index'].tolist()}")
    print(f"\nSaved {out}")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 60)
