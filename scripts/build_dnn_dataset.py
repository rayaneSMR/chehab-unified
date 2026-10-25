#!/usr/bin/env python3
"""One-time, resumable build of the DNN tensor-graph expression dataset.

Each DNN benchmark is a tensor graph in C++, not a plain S-expression. The
only way to materialise it as an expression for test.py is to run the compiled
runner and capture the expression.txt it dumps.

This builder:
- Runs without executing any optimizer (terminates the runner immediately once
  expression.txt is written).
- Live heartbeat progress prints for interactive terminal monitoring.
- Incremental and resumable (appends to dnn_full_benchmarks.txt).
- Cleans expressions (e.g. outer rescale) for full pytrs compatibility.
"""

from __future__ import annotations

import argparse
import subprocess
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = REPO_ROOT / "build"
EXECUTABLE = BUILD_DIR / "benchmarks" / "dnn_tensor" / "dnn_tensor_benchmarks_runner_bin"
OUT_DIR = REPO_ROOT / "RL" / "fhe_rl" / "datasets"
DATASET = OUT_DIR / "dnn_full_benchmarks.txt"

DNN_BENCHMARKS = [
    "conv2d", "full_dnn", "cryptonets", "mlp", "lola", "lenet",
    "resnet20_relu", "resnet20_silu", "resnet34_relu", "resnet34_silu",
    "resnet50_relu", "resnet50_silu", "alexnet",
]

DEFAULT_TIMEOUT = 7200


def _clean_expression(expr: str) -> str:
    """Clean up expression formatting and strip outer rescale if present."""
    expr = " ".join(expr.split())
    # Handle outer ( rescale ... ) if present: (Vec ( rescale ( + ... ) ) ) -> (Vec ( + ... ) )
    if "( rescale " in expr:
        expr = expr.replace("( rescale ", "")
        last_paren_idx = expr.rfind(")")
        if last_paren_idx != -1:
            expr = expr[:last_paren_idx] + expr[last_paren_idx + 1:]
    return expr


def _expr_for(name: str, timeout: int) -> str:
    """Run C++ runner for a benchmark, capture expression.txt, and terminate runner immediately."""
    proj_root = BUILD_DIR / "benchmarks" / "dnn_tensor"
    expr_file = BUILD_DIR / "benchmarks" / "expression.txt"
    tmp = proj_root.parent / "tmp_dnn_dataset" / name
    tmp.mkdir(parents=True, exist_ok=True)
    expr_file.unlink(missing_ok=True)

    proc = subprocess.Popen(
        [
            str(EXECUTABLE), "--benchmark", name, "--backend", "lattigo",
            "--optimizer", "original_rl", "--bsgs-base", "global",
        ],
        cwd=str(proj_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    t0 = time.time()
    last_print = t0
    raw_content = None
    while time.time() - t0 < timeout:
        now = time.time()
        if now - last_print >= 10:
            elapsed = int(now - t0)
            if expr_file.is_file():
                sz = expr_file.stat().st_size
                print(f"  [{name}] {elapsed}s elapsed (writing expression.txt: {sz / 1e6:.1f} MB)...", flush=True)
            else:
                print(f"  [{name}] {elapsed}s elapsed (building C++ graph in memory)...", flush=True)
            last_print = now

        if expr_file.is_file() and expr_file.stat().st_size > 0:
            size1 = expr_file.stat().st_size
            time.sleep(0.5)
            if expr_file.is_file() and expr_file.stat().st_size == size1:
                # File is completely written
                raw_content = expr_file.read_text(encoding="utf-8").strip()
                proc.kill()
                break
        if proc.poll() is not None:
            if expr_file.is_file() and expr_file.stat().st_size > 0:
                raw_content = expr_file.read_text(encoding="utf-8").strip()
                break
            stdout, stderr = proc.communicate()
            raise RuntimeError(f"runner failed for {name} with rc={proc.returncode}\nstderr: {stderr[-300:]}")
        time.sleep(0.2)

    if raw_content is None:
        proc.kill()
        raise subprocess.TimeoutExpired(cmd=str(EXECUTABLE), timeout=timeout)

    expr = _clean_expression(raw_content)
    line = f"{expr}:{name}"
    (tmp / f"{name}.txt").write_text(line + "\n", encoding="utf-8")
    expr_file.unlink(missing_ok=True)
    return line


def _benchmark_already_present(name: str) -> bool:
    return (OUT_DIR / f"{name}.txt").exists()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmarks", default=",".join(DNN_BENCHMARKS))
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                        help=f"per-benchmark seconds (default {DEFAULT_TIMEOUT})")
    parser.add_argument("--skip-existing", action="store_true",
                        help="skip benchmarks we already wrote to the dataset")
    args = parser.parse_args()

    selected = [b.strip() for b in args.benchmarks.split(",") if b.strip()]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DATASET.parent.mkdir(parents=True, exist_ok=True)

    total_count = len(selected)
    print(f"\n=======================================================", flush=True)
    print(f"  Starting DNN Expression Extraction ({total_count} benchmarks)", flush=True)
    print(f"  Skip existing: {args.skip_existing} | Timeout per benchmark: {args.timeout}s", flush=True)
    print(f"=======================================================\n", flush=True)

    done = skipped = failed = 0
    log = []
    for idx, name in enumerate(selected, 1):
        if args.skip_existing and _benchmark_already_present(name):
            skipped += 1
            sz = (OUT_DIR / f"{name}.txt").stat().st_size
            log.append(f"SKIP  [{idx}/{total_count}] {name}  (already exists: {sz / 1e6:.1f} MB)")
            print(f"--> [{idx}/{total_count}] SKIP: {name} (already exists: {sz / 1e6:.1f} MB)", flush=True)
            continue

        print(f"--> [{idx}/{total_count}] EXTRACTING: {name} ...", flush=True)
        t_start = time.time()
        try:
            line = _expr_for(name, args.timeout)
            dur = time.time() - t_start
        except subprocess.TimeoutExpired:
            failed += 1
            msg = f"TIMEOUT [{idx}/{total_count}] {name} (>{args.timeout}s)"
            log.append(msg)
            print(f"    FAILED: {msg}", flush=True)
            continue
        except Exception as exc:
            failed += 1
            msg = f"FAIL [{idx}/{total_count}] {name} -> {exc}"
            log.append(msg)
            print(f"    FAILED: {msg}", flush=True)
            continue

        (OUT_DIR / f"{name}.txt").write_text(line + "\n", encoding="utf-8")
        
        # Read existing dataset lines and append
        existing_lines = []
        if DATASET.exists():
            existing_lines = [l for l in DATASET.read_text(encoding="utf-8").splitlines() if l.strip()]
        # Remove any previous line for this benchmark
        existing_lines = [l for l in existing_lines if not l.endswith(f":{name}")]
        existing_lines.append(line)
        DATASET.write_text("\n".join(existing_lines) + "\n", encoding="utf-8")

        done += 1
        msg = f"OK [{idx}/{total_count}] {name} ({len(line) / 1e6:.2f} MB extracted in {dur:.1f}s)"
        log.append(msg)
        print(f"    SUCCESS: {msg}\n", flush=True)

    print("\n=======================================================", flush=True)
    print("  EXTRACTION SUMMARY", flush=True)
    print("=======================================================", flush=True)
    print("\n".join(log), flush=True)
    print(f"\nTotal: {done} ok, {skipped} skipped, {failed} failed", flush=True)
    print(f"Dataset location: {DATASET}\n", flush=True)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
