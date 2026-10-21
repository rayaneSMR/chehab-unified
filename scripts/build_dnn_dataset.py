#!/usr/bin/env python3
"""One-time, resumable build of the DNN tensor-graph expression dataset.

Each DNN benchmark is a tensor *graph* in C++, not a plain S-expression.  The
only way to materialise it as an expression for `test.py` is to run the compiled
runtime and capture the ``expression.txt`` it dumps.  That step is expensive
(Large DNNs such as ResNet50 can take minutes per benchmark), so we make this
script:

- incremental (appends only *new* benchmarks to the dataset file),
- resumable (a failed benchmark is logged and skipped, the run can continue),
- portable (you point it at the HPC login node where the `chehab` conda env
  and `build/` directory already live).

You normally generate the dataset **once**, then evaluate forever with
`--dataset ./fhe_rl/datasets/dnn_full_benchmarks.txt` (fast, deterministic).
"""

from __future__ import annotations

import argparse
import subprocess
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

# Per-benchmark budget; DNN graphs are large, so keep this generous (seconds).
DEFAULT_TIMEOUT = 900


def _expr_for(name: str, timeout: int) -> tuple[str, str]:
    """Run the C++ runner for a single DNN benchmark and return ``(expr, name)``.

    Raises subprocess.TimeoutExpired / RuntimeError on failure.  The runner's
    CWD is the `dnn_tensor` build folder; it writes ``../expression.txt`` there,
    which is what we read below.
    """
    proj_root = BUILD_DIR / "benchmarks" / "dnn_tensor"
    expr_file = BUILD_DIR / "benchmarks" / "expression.txt"
    tmp = proj_root.parent / "tmp_dnn_dataset" / name
    tmp.mkdir(parents=True, exist_ok=True)

    proc = subprocess.run(
        [
            str(EXECUTABLE), "--benchmark", name, "--backend", "lattigo",
            "--optimizer", "original_rl", "--bsgs-base", "global",
        ],
        cwd=str(proj_root), text=True, capture_output=True, timeout=timeout,
    )

    if proc.returncode != 0 or not expr_file.is_file():
        raise RuntimeError(
            f"runner rc={proc.returncode} for {name}\n"
            f"stdout: {proc.stdout[-500:]}\nstderr: {proc.stderr[-500:]}"
        )

    expr = " ".join(expr_file.read_text().split())
    line = f"{expr}:{name}"
    # Clear any stale file we may have left from a previous (aborted) run for
    # this benchmark so we never append a half-baked expression.
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

    # Resolve the actual full path the runner will dump to (avoid `missing_ok`
    # edge-case on older pythons).
    expr_file_path = BUILD_DIR / "benchmarks" / "expression.txt"

    done = skipped = failed = 0
    log = []
    for name in selected:
        if args.skip_existing and _benchmark_already_present(name):
            skipped += 1
            log.append(f"SKIP  {name}  (already in dataset)")
            continue

        try:
            line = _expr_for(name, args.timeout)
        except subprocess.TimeoutExpired:
            failed += 1
            log.append(f"TIMEOUT  {name}  (>{args.timeout}s)")
            continue
        except Exception as exc:  # noqa: BLE001
            failed += 1
            log.append(f"FAIL  {name}  -> {exc}")
            continue

        (OUT_DIR / f"{name}.txt").write_text(line + "\n", encoding="utf-8")
        (DATASET).write_text("\n".join(
            l for l in (DATASET.read_text(encoding="utf-8").splitlines() if DATASET.exists() else []) 
            + [line]) + "\n", encoding="utf-8")
        done += 1
        log.append(f"OK    {name}  ({len(line)} chars)")

    print("\n".join(log))
    print(f"\nDone: {done} ok, {skipped} skipped, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
