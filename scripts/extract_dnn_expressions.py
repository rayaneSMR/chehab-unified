#!/usr/bin/env python3
"""Extract the original input expressions from the C++ DNN tensor benchmarks.

The C++ benchmark runner builds each DNN (ResNet, AlexNet, ...) as a tensor
graph in memory and writes the *original* scalar expression to
``build/benchmarks/expression.txt`` (relative path ``../expression.txt`` from
the runner's CWD) when the ``original_rl`` optimizer path is taken.  This
script runs that path for every benchmark, captures the expression before the
next benchmark overwrites it, and writes a dataset file that the standard
Python evaluator (``python -m fhe_rl test``) can consume.

No C++ code is modified.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = REPO_ROOT / "build"
EXECUTABLE = BUILD_DIR / "benchmarks" / "dnn_tensor" / "dnn_tensor_benchmarks_runner_bin"
EXPR_FILE = BUILD_DIR / "benchmarks" / "expression.txt"   # ../expression.txt from CWD
OUT_DIR = REPO_ROOT / "RL" / "fhe_rl" / "datasets" / "dnn_full"

BENCHMARKS = [
    "conv2d", "full_dnn", "cryptonets", "mlp", "lola", "lenet",
    "resnet20_relu", "resnet20_silu", "resnet34_relu", "resnet34_silu",
    "resnet50_relu", "resnet50_silu", "alexnet",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmarks", default=",".join(BENCHMARKS))
    parser.add_argument("--timeout", type=int, default=120,
                    help="per-benchmark timeout in seconds (the runner also invokes your conda `python` for the RL step)")
    parser.add_argument("--skip-build", action="store_true")
    args = parser.parse_args()

    if not args.skip_build:
        print("Building dnn_tensor_benchmarks_runner_bin ...")
        built = subprocess.run(
            ["cmake", "--build", str(BUILD_DIR), "--target",
             "dnn_tensor_benchmarks_runner_bin", "--parallel", "2"],
            cwd=REPO_ROOT, text=True, capture_output=True)
        if built.returncode:
            print(built.stdout + built.stderr, file=sys.stderr)
            return 1

    if not EXECUTABLE.is_file():
        print(f"Executable not found: {EXECUTABLE}", file=sys.stderr)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    selected = [b.strip() for b in args.benchmarks.split(",") if b.strip()]
    combined_lines: list[str] = []

    for name in selected:
        print(f"[extract] {name} ...")
        cmd = [str(EXECUTABLE), "--benchmark", name, "--backend", "lattigo",
               "--optimizer", "original_rl", "--bsgs-base", "global"]
        try:
            proc = subprocess.run(cmd, cwd=EXECUTABLE.parent, text=True,
                                  capture_output=True, timeout=args.timeout)
        except subprocess.TimeoutExpired:
            print(f"  TIMEOUT for {name}", file=sys.stderr)
            continue
        if proc.returncode:
            print(f"  FAILED (rc={proc.returncode}): {proc.stderr[:300]}", file=sys.stderr)
            continue
        if not EXPR_FILE.is_file():
            print(f"  no expression.txt produced for {name}", file=sys.stderr)
            continue
        expr = " ".join(EXPR_FILE.read_text().split())  # collapse to one line
        (OUT_DIR / f"{name}.txt").write_text(expr + "\n", encoding="utf-8")
        combined_lines.append(f"{expr}:{name}")
        print(f"  OK ({len(expr)} chars)")

    combined_path = REPO_ROOT / "RL" / "fhe_rl" / "datasets" / "dnn_full_benchmarks.txt"
    combined_path.write_text("\n".join(combined_lines) + "\n", encoding="utf-8")
    print(f"\nWrote {len(combined_lines)} expressions -> {combined_path}")
    print(f"Per-benchmark files in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
