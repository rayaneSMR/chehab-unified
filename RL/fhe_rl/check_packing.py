#!/usr/bin/env python3
import csv
import sys
from pathlib import Path
from collections import Counter

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import packing

csv_path = HERE.parent / "veclang_runner" / "temp" / "input_ct_truth.csv"
if not csv_path.exists():
    print(f"Error: {csv_path} does not exist!")
    sys.exit(1)

rows = list(csv.DictReader(open(csv_path, "r", encoding="utf-8")))

print(f"{'idx':>3} {'N':>6} {'L':>3} | {'real_in':>7} {'packed_in':>9} {'diff':>5} | {'real_ops':>8} {'packed_ops':>10}")
print("-" * 55)

exact_matches = 0
undercounts = 0
overcounts = 0
ops_diffs = Counter()
mismatches = []

for idx, r in enumerate(rows):
    real_in = int(r["real_in"])
    real_ops = int(r["real_ops"])
    expr = r["expr"]
    N = int(r["N"])
    L = int(r["L"])
    
    try:
        res = packing.pack(expr)
        packed_in = res[1]
        packed_ops = res[3]
    except Exception as e:
        print(f"{idx:>3} {N:>6} {L:>3} | FAILED: {type(e).__name__}: {e}")
        mismatches.append((idx, real_in, None, f"FAIL: {e}"))
        continue

    diff_in = packed_in - real_in
    diff_ops = packed_ops - real_ops
    ops_diffs[diff_ops] += 1

    if diff_in == 0:
        exact_matches += 1
    elif diff_in < 0:
        undercounts += 1
        mismatches.append((idx, real_in, packed_in, "UNDERCOUNT"))
    else:
        overcounts += 1
        mismatches.append((idx, real_in, packed_in, f"+{diff_in}"))

    print(f"{idx:>3} {N:>6} {L:>3} | {real_in:>7} {packed_in:>9} {diff_in:>5} | {real_ops:>8} {packed_ops:>10}")

n = len(rows)
print("\n" + "=" * 55)
print("SUMMARY STATS:")
print(f"  Exact matches (packed_in == real_in): {exact_matches}/{n}")
print(f"  Under-counts (packed_in < real_in):   {undercounts}/{n}")
print(f"  Over-counts (packed_in > real_in):    {overcounts}/{n}")
print(f"  Ops count diff (packed_ops - real_ops) distribution: {sorted(ops_diffs.items())}")

gate_pass = (exact_matches > 45) and (undercounts == 0)
print(f"  GATE: exact_matches > 45/80 ({exact_matches} > 45) AND undercounts == 0 ({undercounts} == 0) -> {'PASS' if gate_pass else 'FAIL'}")
print("=" * 55)
