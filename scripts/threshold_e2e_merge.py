#!/usr/bin/env python3
"""All the near-threshold end-to-end results in one file: <root>/threshold_e2e_ALL.xlsx

  sheets cmorl / unconstrained / unconstrained_norollback / input: every row of the CSVs of that
  folder (+ source_file); sheet per_program: one row per program, main columns of the runs side by side.

    python scripts/threshold_e2e_merge.py RL/test_results/threshold_e2e_w0.9
"""
import argparse
from pathlib import Path

import pandas as pd

KINDS = ["cmorl", "unconstrained", "unconstrained_norollback", "input"]
COLS = {"status": "status", "circuit_execution_time (s)": "circuit s", "total_execution_time (s)": "total s",
        "galois_keys_generation_time (s)": "keygen s", "rotation_keys_size (MB)": "keys MB",
        "compile_time (s)": "compile s", "rl_time_ms": "RL ms", "safe_ops": "ops", "safe_keys": "rot. keys",
        "agent_noise_est": "agent noise", "safe_noise_est": "noise", "safety_activated": "rollback",
        "certified": "certified", "outputs_match": "outputs ok"}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    root = Path(ap.parse_args().root)

    runs = {}
    for kind in KINDS:
        files = sorted((root / kind).glob("*.csv"))
        if not files:
            print(f"  {kind}: no CSV, skipped")
            continue
        d = pd.concat([pd.read_csv(f).assign(source_file=f.name) for f in files], ignore_index=True)
        d = d.drop_duplicates("dataset_line", keep="last").sort_values("dataset_line")
        d.insert(0, "B", d["benchmark"].str.extract(r"thresh_b(\d+)_", expand=False).astype(int))
        runs[kind] = d
        print(f"  {kind}: {len(d)} programs from {len(files)} files, status {d.status.value_counts().to_dict()}")

    base = runs["input"][["dataset_line", "benchmark", "B", "initial_ops", "initial_keys", "initial_noise_est"]]
    per = base.set_index("dataset_line")
    for kind, d in runs.items():
        sub = d.set_index("dataset_line")[[c for c in COLS if c in d.columns]].rename(columns=COLS)
        per = per.join(sub.add_prefix(f"{kind}: "))

    out = root / "threshold_e2e_ALL.xlsx"
    with pd.ExcelWriter(out) as w:
        per.reset_index().to_excel(w, sheet_name="per_program", index=False)
        for kind, d in runs.items():
            d.to_excel(w, sheet_name=kind[:31], index=False)
    print(f"\nWritten: {out}  ({len(per)} programs, sheets: per_program, {', '.join(runs)})")


if __name__ == "__main__":
    main()
