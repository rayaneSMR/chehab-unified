#!/usr/bin/env python3
"""Near-threshold table (tab:near-threshold) with the measured SEAL execution time.

Reads the CSVs written by scripts/launch_threshold_e2e.sh under <root>:
    unconstrained_norollback/  agent at budget 9000000, no rollback (its final program)
    cmorl/                     CMO-RL at B, rollback at B
    input/                     input program (baseline)
Rows: Unconstrained (B = 230 and 236 pooled), CMO-RL at B = 230, 236, 369. Programs whose input is
within B (estimated noise <= B).
  Violations       % of programs whose returned program exceeds B (estimated noise): the agent's
                   final program without rollback, the rollback's choice for CMO-RL; all programs
  Total time red.  mean over programs of 1 - t / t_input, t = total SEAL time (circuit + rotation
                   key generation); programs that compiled and ran (also the circuit time alone)
  Key size         mean rotation (Galois) key size in MB, as serialized by SEAL
  RL time          geometric mean of the agent's episode time (all programs)
  Compile time     geometric mean of the whole CHEHAB compilation (agent call included)

    python scripts/threshold_table4.py RL/test_results/threshold_e2e_w0.9
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

T, TT, K, C = ("circuit_execution_time (s)", "total_execution_time (s)",
               "rotation_keys_size (MB)", "compile_time (s)")


def load(root, kind):
    files = sorted((root / kind).glob("*.csv"))
    if not files:
        sys.exit(f"No CSV in {root / kind}")
    d = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    # a program run twice: keep the successful run, else the last one
    d = (d.assign(_ok=d["status"].eq("ok")).sort_values("_ok", kind="stable")
         .drop_duplicates("dataset_line", keep="last").drop(columns="_ok")
         .set_index("dataset_line").sort_index())
    d["B"] = d["benchmark"].str.extract(r"thresh_b(\d+)_", expand=False).astype(int)
    return d


def gmean(s):
    return float(np.exp(np.log(s).mean()))


def row(name, run, inp, budgets, noise_col):
    a = run.join(inp[[T, TT, "status", "initial_noise_est"]], rsuffix="_in")
    a = a[a.B.isin(budgets) & (a.initial_noise_est_in <= a.B)]
    d = a[a.status.eq("ok") & a.status_in.eq("ok")]
    return {
        "Agent": name, "Programs": len(a), "Timed": len(d),
        "Violations (%)": 100 * (a[noise_col] > a.B).mean(),
        "Total time red. (%)": 100 * (1 - d[TT] / d[TT + "_in"]).mean(),
        "Circuit time red. (%)": 100 * (1 - d[T] / d[T + "_in"]).mean(),
        "Total time (s)": d[TT].mean(),
        "Input total time (s)": d[TT + "_in"].mean(),
        "Key size (MB)": d[K].mean(),
        "RL time (s)": gmean(a["rl_time_ms"] / 1000),
        "Compile time (s)": gmean(d[C]),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    args = ap.parse_args()
    root = Path(args.root)
    inp = load(root, "input")
    rows = [row("Unconstrained", load(root, "unconstrained_norollback"), inp, [230, 236], "agent_noise_est")]
    if (root / "unconstrained").is_dir():   # same agent, rollback at B
        rows.append(row("Unconstrained + rollback", load(root, "unconstrained"), inp, [230, 236], "safe_noise_est"))
    cm = load(root, "cmorl")
    rows += [row(f"Lagrangian (B = {b})", cm, inp, [b], "safe_noise_est") for b in (230, 236, 369)]
    tab = pd.DataFrame(rows).set_index("Agent")

    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", None)
    print(tab.round(2).to_string())
    tab.round(3).to_csv(root / "table4_total_time.csv")

    print("\n% rows of tab:near-threshold (Violations, Time red., Key size, RL time)")
    names = list(tab.index)
    for name, r in tab.iterrows():
        label = name if name.startswith("Unconstrained") else rf"\ToolName{{}} ($B={name.split('= ')[1].rstrip(')')}$)"
        last_unc = name.startswith("Unconstrained") and not names[names.index(name) + 1].startswith("Unconstrained")
        print(f"{label:<24} & {r['Violations (%)']:.1f} & {r['Total time red. (%)']:.1f} & "
              f"{r['Key size (MB)']:.1f} & {r['RL time (s)']:.1f} \\\\" + ("\n\\midrule" if last_unc else ""))
    print(f"\nWritten: {root / 'table4_total_time.csv'}")


if __name__ == "__main__":
    main()
