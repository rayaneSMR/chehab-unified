#!/usr/bin/env python3
"""Merge the bisection of the 9 missing benchmarks into one file for scripts/mo_metrics_46.py.

  --main   job 19348949's file (budget 230; it saves after each benchmark)
  --parts  folder of scripts/run_bisection_one.sbatch (one budget x one benchmark per file)
A (budget, benchmark) found in both: the part is kept. Checks that the 36 pairs are present.

    python scripts/merge_bisection_parts.py
    python scripts/mo_metrics_46.py --run43 RL/test_results/hpc_done/bisection_unified_19038297.xlsx \\
        --run9 RL/test_results/bisection_unified_missing_merged.xlsx \\
        --output RL/test_results/mo_metrics_46_merged.xlsx --tables-dir RL/test_results/mo_tables_46_merged
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

SHEETS = ["metrics", "fronts", "probes"]
BUDGETS = [230, 236, 369, 9000000]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--main", default="RL/test_results/bisection_unified_missing_19348949.xlsx")
    ap.add_argument("--parts", default="RL/test_results/bisection_missing9_parts")
    ap.add_argument("--output", default="RL/test_results/bisection_unified_missing_merged.xlsx")
    args = ap.parse_args()

    # (source, metrics of that source): parts first so they win over the main job
    sources = sorted(Path(args.parts).glob("b*_L*_*.xlsx"))
    if Path(args.main).is_file():
        sources.append(Path(args.main))
    else:
        print(f"WARNING: {args.main} not found")
    data = {s: {} for s in SHEETS}
    done = set()
    for f in sources:
        m = pd.read_excel(f, sheet_name="metrics")
        # keep only the (budget, benchmark) pairs whose bisection finished (a metrics row is
        # written at the end of each benchmark) and not already taken from a part
        keep = {(int(b), e) for b, e in zip(m.Budget, m.Expression)} - done
        for s in SHEETS:
            d = pd.read_excel(f, sheet_name=s)
            if d.empty:
                continue
            mask = [(int(b), e) in keep for b, e in zip(d.Budget, d.Expression)]
            data[s].setdefault(f.name, d[mask])
        done |= keep
        print(f"  {f.name}: {len(keep)} (budget, benchmark) pairs")

    names = sorted({e for _, e in done})
    missing = [(b, e) for b in BUDGETS for e in names if (b, e) not in done]
    print(f"\n{len(done)} pairs, {len(names)} benchmarks")
    if missing:
        print("MISSING (still running?):")
        for b, e in missing:
            print(f"  budget {b}: {e}")
    if len(names) != 9 or missing:
        print("WARNING: expected 9 benchmarks x 4 budgets = 36 pairs")

    out = Path(args.output)
    with pd.ExcelWriter(out) as w:
        for s in SHEETS:
            d = pd.concat(data[s].values(), ignore_index=True) if data[s] else pd.DataFrame()
            if not d.empty:
                d = d.sort_values(["Budget", "Expression"], kind="stable")
            d.to_excel(w, sheet_name=s, index=False)
    print(f"Written: {out}")
    sys.exit(1 if missing else 0)


if __name__ == "__main__":
    main()
