#!/usr/bin/env python3
"""Empirical multi-trial measurement harness for unified calibration on HPC.

For every circuit in the calibration pool:
  1. Compiles AST into standalone native Lattigo Go executable via veclang_runner.
  2. Executes K >= 5 fresh-process independent runs under Linux /proc/self/statm MaxRSS tracking.
  3. Records:
     - Median physical MaxRSS (MB)
     - Min, Max, Spread (Max - Min), and Jitter Ratio (%)
     - Standard deviation across the 5+ runs
     - Emitted native cryptographic parameters (N, L, K, G)
     - Baseline theoretical net memory terms
  4. Incrementally appends to CSV (resumable across interruptions).
  5. Catches and logs all errors with detailed debugging diagnostics.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RL_DIR = REPO_ROOT / "RL"
DATASETS_DIR = RL_DIR / "fhe_rl" / "datasets"
PYTRS_DIR = RL_DIR / "pytrs"
LATTIGO_BACKEND_DIR = REPO_ROOT / "lattigo_backend"
VECLANG_BIN = REPO_ROOT / "build" / "RL" / "veclang_runner" / "veclang_runner"

sys.path.insert(0, str(PYTRS_DIR))
import config as _pytrs_cfg
sys.modules["config"] = _pytrs_cfg

from parser import parse_sexpr
from cost import get_multiplicative_depth
from ckks_memory_estimator import chehab_params, estimate_expression_memory
from expr import Expr, Op, Const, Var

CSV_FIELDS = [
    "pool_idx", "kind", "label", "struct_hash", "status", "status_detail",
    "depth", "est_N", "est_L", "est_K", "est_G", "est_net_mb",
    "est_cts_mb", "est_relin_mb", "est_galois_mb", "est_context_mb",
    "go_N", "go_L", "go_K", "go_G",
    "runs_count", "max_rss_mb_median", "max_rss_mb_min", "max_rss_mb_max",
    "max_rss_spread_mb", "jitter_pct", "max_rss_std", "max_rss_runs_json",
    "compile_time_s", "run_time_total_s", "expr",
]


def run_cmd(cmd: List[str], cwd: Path, timeout: int, env: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout, env=env
    )


def parse_go_params(go_src: str) -> Dict[str, Any]:
    params: Dict[str, Any] = {"go_N": 0, "go_L": 0, "go_K": 0, "go_G": 0}
    m = re.search(r"LogN:\s*(\d+)", go_src)
    if m:
        params["go_N"] = 1 << int(m.group(1))
    m = re.search(r"LogQ:\s*\[\]int\{([^}]*)\}", go_src)
    if m:
        params["go_L"] = len([t for t in m.group(1).split(",") if t.strip()])
    m = re.search(r"LogP:\s*\[\]int\{([^}]*)\}", go_src)
    if m:
        params["go_K"] = len([t for t in m.group(1).split(",") if t.strip()])
    m = re.search(r"return \[\]int\{([^}]*)\}", go_src)
    if m:
        steps = [t.strip() for t in m.group(1).split(",") if t.strip()]
        params["go_G"] = len(steps)
    return params


def patch_neg_new(go_src: str) -> str:
    """Replace eval.NegNew with Sub-based negate for Lattigo v5 compatibility."""
    def _replace_neg(m):
        dst, src = m.group(1), m.group(2)
        return (f"{dst}, _ = eval.SubNew({src}, {src})\n"
                f"\t{dst}, _ = eval.SubNew({dst}, {src})")
    return re.sub(r'(\w+),\s*_\s*=\s*eval\.NegNew\((\w+)\)', _replace_neg, go_src)


def parse_go_rss(stdout: str) -> Optional[float]:
    """Parse process peak MaxRSS from Go output."""
    for line in stdout.splitlines():
        if "max_rss_(MB):" in line:
            try:
                return float(line.split()[1])
            except (IndexError, ValueError):
                pass
    return None


def compile_and_profile_circuit(
    record: Dict[str, Any],
    workdir: Path,
    num_runs: int = 5,
    timeout_s: int = 600,
) -> Dict[str, Any]:
    """Compile and measure one circuit across K >= 5 fresh-process trials."""
    expr = record["expr"]
    row: Dict[str, Any] = {
        "pool_idx": record.get("pool_idx", 0),
        "kind": record.get("kind", "unknown"),
        "label": record.get("label", ""),
        "struct_hash": record.get("struct_hash", ""),
        "status": "ok",
        "status_detail": "",
        "expr": expr,
    }

    # 1. Theoretical estimation
    try:
        tree = parse_sexpr(expr)
        depth = get_multiplicative_depth(tree)
        row["depth"] = depth
        params = chehab_params(depth)
        est = estimate_expression_memory(tree, backend="cpu", params=params)
        terms = est.terms
        MB = 1024.0 * 1024.0
        row.update({
            "est_N": params.N,
            "est_L": params.L,
            "est_K": params.K,
            "est_G": est.rotation_steps,
            "est_net_mb": round(est.total_mb, 3),
            "est_cts_mb": round(terms.get("ciphertexts", 0.0) / MB, 3),
            "est_relin_mb": round(terms.get("relinearization_key", 0.0) / MB, 3),
            "est_galois_mb": round(terms.get("galois_keys", 0.0) / MB, 3),
            "est_context_mb": round((terms.get("public_secret_key", 0.0) +
                                    terms.get("context_evaluator", 0.0) +
                                    terms.get("key_switching_scratch", 0.0)) / MB, 3),
        })
    except Exception as e:
        row["status"] = "estimator_error"
        row["status_detail"] = f"Analytical estimator failure: {type(e).__name__}: {e}"[:300]
        return row

    # 2. Codegen via veclang_runner
    t_start = time.time()
    try:
        # Determine SIMD slot count
        vec_sizes = []
        def _rec(node):
            if isinstance(node, (Const, Var)):
                return
            if isinstance(node, Op):
                if node.op == "Vec":
                    vec_sizes.append(len(node.args))
                else:
                    for a in node.args:
                        _rec(a)
        _rec(tree)
        slot_count = vec_sizes[0] if vec_sizes else 1
        metadata = f"{slot_count} {slot_count} 1 0"
        (workdir / "vectorized_code.txt").write_text(expr + f"\n{metadata}")

        names = set()
        def collect_vars(n):
            if isinstance(n, Var):
                names.add(n.name)
            elif isinstance(n, Op):
                for a in n.args:
                    collect_vars(a)
        collect_vars(tree)
        names_sorted = sorted(names)
        (workdir / "inputs.txt").write_text(
            " ".join(names_sorted) + "\n" + " ".join(["1"] * len(names_sorted)) + "\n"
        )

        with open(workdir / "fhe_io_example.txt", "w") as f_io:
            f_io.write(f"1 {len(names_sorted)} 1\n")
            for inp in names_sorted:
                f_io.write(f"{inp} 1 1 5\n")

        runner_dir = VECLANG_BIN.parent
        for fname in ["vectorized_code.txt", "inputs.txt", "fhe_io_example.txt"]:
            shutil.copy2(workdir / fname, runner_dir / fname)
            if fname in ("vectorized_code.txt", "inputs.txt"):
                shutil.copy2(workdir / fname, runner_dir.parent / fname)

        res = run_cmd(["./veclang_runner", "1", "1", "1"], cwd=runner_dir, timeout=timeout_s)
        if "lattigo_output: generated_fhe.go" not in res.stdout:
            row["status"] = "codegen_error"
            row["status_detail"] = ("veclang_runner codegen failed: " + (res.stderr or res.stdout).strip()[-400:])
            return row

        gen_go = runner_dir / "generated_fhe.go"
        if not gen_go.is_file():
            row["status"] = "codegen_error"
            row["status_detail"] = "generated_fhe.go was not created by veclang_runner"
            return row

        go_src = patch_neg_new(gen_go.read_text(encoding="utf-8"))
        go_params = parse_go_params(go_src)
        row.update(go_params)
    except subprocess.TimeoutExpired:
        row["status"] = "codegen_timeout"
        row["status_detail"] = f"Codegen timed out after {timeout_s}s"
        return row
    except Exception as e:
        row["status"] = "codegen_exception"
        row["status_detail"] = f"{type(e).__name__}: {e}"[:300]
        return row

    # 3. Setup Go module & build standalone binary
    dest = workdir / "go_bin"
    dest.mkdir(exist_ok=True)
    (dest / "main.go").write_text(go_src)
    gosum_src = LATTIGO_BACKEND_DIR / "go.sum"
    if gosum_src.is_file():
        shutil.copy2(gosum_src, dest / "go.sum")
    (dest / "go.mod").write_text(
        "module calib_measure\n\ngo 1.21\n\nrequire github.com/tuneinsight/lattigo/v5 v5.0.7\n"
    )

    env = dict(os.environ)
    env["GOGC"] = "100"
    t_compile = time.time()
    try:
        run_cmd(["go", "mod", "tidy"], cwd=dest, timeout=timeout_s, env=env)
        build_res = run_cmd(["go", "build", "-o", "circuit_bin", "."], cwd=dest, timeout=timeout_s, env=env)
        if build_res.returncode != 0:
            row["status"] = "go_build_error"
            row["status_detail"] = ("go build failed: " + (build_res.stderr or build_res.stdout))[:300]
            row["compile_time_s"] = round(time.time() - t_compile, 2)
            return row
    except subprocess.TimeoutExpired:
        row["status"] = "go_build_timeout"
        row["status_detail"] = f"Go compilation timed out after {timeout_s}s"
        return row
    except Exception as e:
        row["status"] = "go_build_exception"
        row["status_detail"] = f"{type(e).__name__}: {e}"[:300]
        return row

    row["compile_time_s"] = round(time.time() - t_compile, 2)

    # 4. Multi-Trial Empirical Executions (K >= 5 runs)
    rss_runs: List[float] = []
    t_runs_start = time.time()
    circuit_bin = dest / "circuit_bin"

    for run_idx in range(num_runs):
        try:
            run_res = run_cmd([str(circuit_bin), "-repetitions=1"], cwd=dest, timeout=timeout_s, env=env)
            if run_res.returncode != 0:
                row["status"] = "run_error"
                row["status_detail"] = f"Run {run_idx+1} exited with {run_res.returncode}: {run_res.stderr[:200]}"
                return row
            rss = parse_go_rss(run_res.stdout)
            if rss is None:
                row["status"] = "missing_metrics"
                row["status_detail"] = f"Run {run_idx+1} did not report max_rss_(MB)"
                return row
            rss_runs.append(rss)
        except subprocess.TimeoutExpired:
            row["status"] = "run_timeout"
            row["status_detail"] = f"Trial {run_idx+1}/{num_runs} timed out after {timeout_s}s"
            return row
        except Exception as e:
            row["status"] = "run_exception"
            row["status_detail"] = f"Trial {run_idx+1} error: {type(e).__name__}: {e}"[:300]
            return row

    row["run_time_total_s"] = round(time.time() - t_runs_start, 2)
    row["runs_count"] = len(rss_runs)
    row["max_rss_runs_json"] = json.dumps(rss_runs)

    # Compute multi-trial statistical metrics
    median_val = statistics.median(rss_runs)
    min_val = min(rss_runs)
    max_val = max(rss_runs)
    spread = max_val - min_val
    jitter = (spread / median_val * 100.0) if median_val > 0 else 0.0
    stdev = statistics.stdev(rss_runs) if len(rss_runs) > 1 else 0.0

    row.update({
        "max_rss_mb_median": round(median_val, 3),
        "max_rss_mb_min": round(min_val, 3),
        "max_rss_mb_max": round(max_val, 3),
        "max_rss_spread_mb": round(spread, 3),
        "jitter_pct": round(jitter, 2),
        "max_rss_std": round(stdev, 3),
    })

    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool", type=Path, default=DATASETS_DIR / "unified_calibration_pool.jsonl",
                        help="Input JSONL pool file")
    parser.add_argument("--output-csv", type=Path, default=DATASETS_DIR / "unified_calib_measurements_5runs.csv",
                        help="Output measurements CSV file")
    parser.add_argument("--failures-log", type=Path, default=DATASETS_DIR / "unified_calib_failures.log",
                        help="Log file for detailed failure diagnostics")
    parser.add_argument("--runs", type=int, default=5,
                        help="Number of independent process runs per circuit (default: 5)")
    parser.add_argument("--timeout", type=int, default=600,
                        help="Timeout in seconds per circuit compilation/run (default: 600)")
    parser.add_argument("--max-circuits", type=int, default=0,
                        help="Limit number of circuits to profile (0 = all)")
    args = parser.parse_args()

    print("=" * 80)
    print("STARTING EMPIRICAL MULTI-TRIAL CALIBRATION MEASUREMENT (HPC)")
    print(f"Calibration Pool: {args.pool}")
    print(f"Output CSV      : {args.output_csv}")
    print(f"Trials per circuit: {args.runs} runs (reporting median + spread)")
    print(f"Timeout per run : {args.timeout}s")
    print("=" * 80)

    if not args.pool.is_file():
        print(f"[CRITICAL ERROR] Pool file not found: {args.pool}", file=sys.stderr)
        return 1

    if not VECLANG_BIN.is_file():
        print(f"[CRITICAL ERROR] veclang_runner binary not found: {VECLANG_BIN}", file=sys.stderr)
        return 1

    records: List[Dict[str, Any]] = []
    with open(args.pool, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            line = line.strip()
            if line:
                d = json.loads(line)
                d["pool_idx"] = idx
                records.append(d)

    if args.max_circuits > 0:
        records = records[:args.max_circuits]

    print(f"Loaded {len(records)} circuits from pool.")

    # Read already-completed indices for resume capability
    completed_indices: set[int] = set()
    csv_exists = args.output_csv.is_file()
    if csv_exists:
        try:
            with open(args.output_csv, "r", encoding="utf-8") as f_in:
                reader = csv.DictReader(f_in)
                for r in reader:
                    if "pool_idx" in r:
                        completed_indices.add(int(r["pool_idx"]))
            print(f"[Resume] Found {len(completed_indices)} circuits already measured in CSV.")
        except Exception as e:
            print(f"[Warning] Failed to inspect existing CSV for resume: {e}")

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    csv_file = open(args.output_csv, "a", newline="", encoding="utf-8")
    writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDS)
    if not csv_exists or args.output_csv.stat().st_size == 0:
        writer.writeheader()
        csv_file.flush()

    failures_file = open(args.failures_log, "a", encoding="utf-8")
    success_count = 0
    fail_count = 0

    t_all_start = time.time()
    for i, rec in enumerate(records, start=1):
        idx = rec["pool_idx"]
        label = rec.get("label", f"circuit_{idx}")
        kind = rec.get("kind", "base")
        if idx in completed_indices:
            continue

        print(f"[{i}/{len(records)}] Measuring #{idx} ({kind} - {label}) across {args.runs} runs...", flush=True)
        with tempfile.TemporaryDirectory(prefix=f"calib_{idx}_") as tmpdir:
            wd = Path(tmpdir)
            row = compile_and_profile_circuit(rec, wd, num_runs=args.runs, timeout_s=args.timeout)

        # Write clean row
        out_row = {k: row.get(k, "") for k in CSV_FIELDS}
        writer.writerow(out_row)
        csv_file.flush()

        if row.get("status") == "ok":
            success_count += 1
            med = row.get("max_rss_mb_median", 0.0)
            spread = row.get("max_rss_spread_mb", 0.0)
            jitter = row.get("jitter_pct", 0.0)
            print(f"    --> SUCCESS: Median = {med:.2f} MB | Spread = {spread:.2f} MB ({jitter:.1f}% jitter)", flush=True)
        else:
            fail_count += 1
            err_detail = row.get("status_detail", "unknown error")
            print(f"    --> FAILED ({row.get('status')}): {err_detail[:120]}", flush=True)
            failures_file.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] #{idx} ({kind}) {row.get('status')}: {err_detail}\n")
            failures_file.flush()

    csv_file.close()
    failures_file.close()

    total_time = time.time() - t_all_start
    print("\n" + "=" * 80)
    print("CALIBRATION MEASUREMENT RUN COMPLETE")
    print(f"Total Processed : {len(records)}")
    print(f"Successful Runs : {success_count}")
    print(f"Failed Runs     : {fail_count}")
    print(f"Total Time      : {total_time/60:.2f} minutes")
    print(f"Measurements CSV: {args.output_csv}")
    print(f"Failures Log    : {args.failures_log}")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    sys.exit(main())
