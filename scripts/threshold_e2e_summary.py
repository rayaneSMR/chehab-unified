#!/usr/bin/env python3
"""Near-threshold table with measured SEAL execution times.

Reads the CSVs written by scripts/launch_threshold_e2e.sh:
    <root>/cmorl/*.csv          CMO-RL at the program's budget B, with rollback at B
    <root>/unconstrained/*.csv  same agent at budget 9000000, with rollback at B
    <root>/input/*.csv          input program (no agent)
(as threshold_w0.9_2026-11-08) and reports, per budget, on the programs whose input is within B
(estimated noise <= B): violation rate before rollback (agent's final program) and after rollback
(compiled program), rollback rate, circuit execution time reduction w.r.t. the input program,
rotation key size, compile time. Reductions are the mean over programs of 1 - t / t_input
(and, in brackets, the reduction of the summed time).

    python scripts/threshold_e2e_summary.py RL/test_results/threshold_e2e_<date> [--xlsx out.xlsx]
"""
import argparse
import re
import sys
from pathlib import Path

import pandas as pd

T = "circuit_execution_time (s)"
K = "rotation_keys_size (MB)"
C = "compile_time (s)"


def load(folder):
    files = sorted(Path(folder).glob("*.csv"))
    if not files:
        sys.exit(f"No CSV in {folder}")
    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    df["B"] = df["benchmark"].str.extract(r"thresh_b(\d+)_", expand=False).astype(int)
    dup = df["dataset_line"].duplicated(keep="last")
    if dup.any():
        print(f"  {folder}: {dup.sum()} duplicate lines, keeping the last run")
        df = df[~dup]
    return df.set_index("dataset_line").sort_index()


def red(t, t0):
    """(mean per-program reduction %, reduction of the summed time %)."""
    per = (1 - t / t0).mean() * 100
    tot = (1 - t.sum() / t0.sum()) * 100
    return round(per, 1), round(tot, 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--xlsx", default=None, help="also write the merged per-program table here")
    args = ap.parse_args()
    root = Path(args.root)
    cm, un, inp = (load(root / d) for d in ("cmorl", "unconstrained", "input"))

    m = pd.DataFrame({
        "benchmark": inp["benchmark"], "B": inp["B"],
        "init_noise": inp["initial_noise_est"],
        "t_in": inp[T], "keys_in": inp[K], "ok_in": inp["status"].eq("ok"), "match_in": inp["outputs_match"],
        "t_cm": cm[T], "keys_cm": cm[K], "comp_cm": cm[C],
        "agent_noise_cm": cm["agent_noise_est"], "noise_cm": cm["safe_noise_est"],
        "ok_cm": cm["status"].eq("ok"), "match_cm": cm["outputs_match"], "cert_cm": cm["certified"],
        "rollback_cm": cm["safety_activated"],
        "t_un": un[T], "keys_un": un[K], "comp_un": un[C],
        "agent_noise_un": un["agent_noise_est"], "noise_un": un["safe_noise_est"],
        "ok_un": un["status"].eq("ok"), "match_un": un["outputs_match"], "cert_un": un["certified"],
        "rollback_un": un["safety_activated"],
        # the three runs start from the same program (same initial ops, keys and noise)
        "same_input": pd.concat([(inp[c] == cm[c]) & (inp[c] == un[c])
                                 for c in ("initial_ops", "initial_keys", "initial_noise_est")], axis=1).all(axis=1),
    })
    m["viol_before_cm"] = m["agent_noise_cm"] > m["B"]
    m["viol_before_un"] = m["agent_noise_un"] > m["B"]
    m["viol_cm"] = m["noise_cm"] > m["B"]
    m["viol_un"] = m["noise_un"] > m["B"]

    print(f"Programs: {len(m)} | all three runs ok: {(m.ok_in & m.ok_cm & m.ok_un).sum()} | "
          f"same input expression in the three runs: {m.same_input.sum()}")
    print(f"Decrypted outputs correct: input {m.match_in.eq(True).sum()}, CMO-RL {m.match_cm.eq(True).sum()}, "
          f"unconstrained {m.match_un.eq(True).sum()} (of {len(m)})")
    print(f"Not certified by the SEAL bound (input compiled instead): CMO-RL {(~m.cert_cm.astype(bool)).sum()}, "
          f"unconstrained {(~m.cert_un.astype(bool)).sum()}\n")

    rows = []
    groups = [("230", [230]), ("236", [236]), ("230+236", [230, 236]), ("369", [369])]
    for label, bs in groups:
        g = m[m.B.isin(bs) & (m.init_noise <= m.B) & m.ok_in & m.ok_cm & m.ok_un]
        if g.empty:
            continue
        rows.append({
            "B": label, "programs": len(g),
            "CMO-RL viol % (before rollback)": round(g.viol_before_cm.mean() * 100, 1),
            "Unc. viol % (before rollback)": round(g.viol_before_un.mean() * 100, 1),
            "CMO-RL viol % (after rollback)": round(g.viol_cm.mean() * 100, 1),
            "Unc. viol % (after rollback)": round(g.viol_un.mean() * 100, 1),
            "CMO-RL rollback %": round(g.rollback_cm.astype(bool).mean() * 100, 1),
            "Unc. rollback %": round(g.rollback_un.astype(bool).mean() * 100, 1),
            "CMO-RL exec red. %": red(g.t_cm, g.t_in),
            "Unc. exec red. %": red(g.t_un, g.t_in),
            "CMO-RL keys MB": round(g.keys_cm.mean(), 1),
            "Unc. keys MB": round(g.keys_un.mean(), 1),
            "keys red. vs Unc. %": round((1 - g.keys_cm.sum() / g.keys_un.sum()) * 100, 1),
            "CMO-RL compile s": round(g.comp_cm.mean(), 2),
            "Unc. compile s": round(g.comp_un.mean(), 2),
            "compile faster vs Unc. %": round((1 - g.comp_cm.sum() / g.comp_un.sum()) * 100, 1),
            "input exec s (mean)": round(g.t_in.mean(), 3),
        })
    summary = pd.DataFrame(rows)
    with pd.option_context("display.max_columns", None, "display.width", 250):
        print(summary.T.to_string(header=False))

    if args.xlsx:
        with pd.ExcelWriter(args.xlsx) as w:
            summary.astype(str).to_excel(w, sheet_name="summary", index=False)
            m.to_excel(w, sheet_name="per_program")
        print(f"\nWritten: {args.xlsx}")


if __name__ == "__main__":
    main()
