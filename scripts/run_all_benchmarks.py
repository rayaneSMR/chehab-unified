#!/usr/bin/env python3
"""Run the CHEHAB DNN benchmark suite and report encrypted FHE metrics."""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = REPO_ROOT / "build"
LATTIGO_DIR = REPO_ROOT / "lattigo_backend"
RESULTS_DIR = REPO_ROOT / "results"
TARGET = "dnn_tensor_benchmarks_runner_bin"


@dataclass(frozen=True)
class Benchmark:
    name: str

    @property
    def generated_go(self) -> Path:
        return BUILD_DIR / "benchmarks" / "dnn_tensor" / "he" / f"tensor_{self.name}_auto.go"

    @property
    def generated_cu(self) -> Path:
        return BUILD_DIR / "benchmarks" / "dnn_tensor" / "heongpu" / "generated_fhe.cu"


BENCHMARKS = {name: Benchmark(name) for name in (
    "conv2d", "full_dnn", "cryptonets", "mlp", "lola", "lenet",
    "resnet20_relu", "resnet20_silu", "resnet34_relu", "resnet34_silu",
    "resnet50_relu", "resnet50_silu", "alexnet"
)}
CSV_FIELDS = [
    "benchmark", "backend", "repetitions", "dsl_generation_ms", "encrypt_ms", "compute_ms",
    "decrypt_ms", "total_measured_ms", "rotation_keys", "bootstrap_count", "level_start",
    "level_end", "levels_consumed", "max_abs_error", "precision_checked", "run_status",
    "generated_file", "error_message",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CHEHAB encrypted DNN benchmark runner")
    parser.add_argument("--benchmarks", default=",".join(BENCHMARKS),
                        help="comma-separated benchmark names; see the default list")
             
    parser.add_argument("--backend", choices=("lattigo", "heongpu"), default="lattigo",
                        help="cryptographic backend: lattigo (default) or heongpu")

    parser.add_argument("--repetitions", type=int, default=3,
                        help="encrypted inference repetitions per benchmark")
    parser.add_argument("--optimizer", choices=("trs", "original_rl", "morl", "constrained_rl", "none"),
                        default="trs", help="veclang optimizer: trs, original_rl, morl, constrained_rl, none")
    parser.add_argument("--w-ops", type=float, default=0.5,
                        help="weight for operations in MORL (default: 0.5)")
    parser.add_argument("--bsgs-base", default="global", help="global, 0, or a positive BSGS base")
    parser.add_argument("--naf", action="store_true",
                        help="enable NAF rotation-key reduction during Lattigo code generation")
    parser.add_argument("--naf-threshold", type=int, default=0,
                        help="maximum rotation-key count targeted by NAF reduction; 0 selects the smallest possible budget")
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--output-csv", default=None, help="custom path for output CSV file")
    parser.add_argument("--timeout", type=int, default=180, help="per-command timeout in seconds")
    return parser.parse_args()


def run(command: list[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=timeout, check=False)


def first_lines(output: str, limit: int = 3) -> str:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return " ".join(lines[:limit])


def dsl_time(output: str) -> float | None:
    match = re.search(r"DSL generation time:\s*([0-9.]+)\s*ms", output, re.IGNORECASE)
    return float(match.group(1)) if match else None


def parse_go_metrics(output: str) -> dict[str, Any] | None:
    match = re.search(r"BENCHMARK_METRICS\s+(\{[^\n]+\})", output)
    if not match:
        return None
    try:
        metrics = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    required = {"encrypt_ms", "compute_ms", "decrypt_ms", "galois_keys", "bootstrap_count",
                "level_start", "level_end", "max_abs_error", "precision_checked"}
    return metrics if required.issubset(metrics) else None


def select_benchmarks(raw_names: str) -> list[Benchmark]:
    selected: list[Benchmark] = []
    for name in (item.strip() for item in raw_names.split(",")):
        if not name:
            continue
        try:
            selected.append(BENCHMARKS[name])
        except KeyError as error:
            raise ValueError(f"Unknown benchmark: {name}") from error
    if not selected:
        raise ValueError("No benchmarks selected")
    return selected


def build_target(timeout: int) -> tuple[bool, str]:
    if not (BUILD_DIR / "CMakeCache.txt").is_file():
        configured = run(["cmake", "-S", str(REPO_ROOT), "-B", str(BUILD_DIR)], REPO_ROOT, timeout)
        if configured.returncode:
            return False, configured.stdout + configured.stderr
    built = run(["cmake", "--build", str(BUILD_DIR), "--target", TARGET, "--parallel", "2"],
                REPO_ROOT, timeout)
    return built.returncode == 0, built.stdout + built.stderr


def executable_path() -> Path:
    suffix = ".exe" if sys.platform == "win32" else ""
    return BUILD_DIR / "benchmarks" / "dnn_tensor" / f"{TARGET}{suffix}"


def empty_row(benchmark: Benchmark, repetitions: int, backend: str = "lattigo") -> dict[str, Any]:
    return {
        "benchmark": benchmark.name, "backend": backend, "repetitions": repetitions,
        "dsl_generation_ms": "", "encrypt_ms": "", "compute_ms": "", "decrypt_ms": "",
        "total_measured_ms": "", "rotation_keys": "", "bootstrap_count": "", "level_start": "",
        "level_end": "", "levels_consumed": "", "max_abs_error": "", "precision_checked": False,
        "run_status": "PENDING", "generated_file": "", "error_message": "",
    }


def execute_benchmark(benchmark: Benchmark, executable: Path, args: argparse.Namespace) -> dict[str, Any]:
    row = empty_row(benchmark, args.repetitions, backend=args.backend)
    cmd = [str(executable), "--benchmark", benchmark.name, "--backend", args.backend,
           "--optimizer", args.optimizer, "--bsgs-base", args.bsgs_base]
    if args.naf:
        cmd.extend(["--naf", "--naf-threshold", str(args.naf_threshold)])
    if args.optimizer == "morl":
        cmd.extend(["--w-ops", str(args.w_ops)])
    try:
        dsl = run(cmd, executable.parent, args.timeout)
    except subprocess.TimeoutExpired:
        row.update(
            dsl_generation_ms="TIMEOUT",
            run_status="TIMEOUT",
            error_message=f"DSL generation exceeded the {args.timeout}s timeout",
        )
        return row

    dsl_output = dsl.stdout + dsl.stderr
    row["dsl_generation_ms"] = dsl_time(dsl_output) or ""
    gen_file = benchmark.generated_go if args.backend == "lattigo" else benchmark.generated_cu
    row["generated_file"] = str(gen_file)
    if dsl.returncode:
        row.update(run_status=f"DSL_FAILED_{dsl.returncode}", error_message=first_lines(dsl_output))
        return row
    if not gen_file.is_file():
        row.update(run_status="GENERATE_FAILED", error_message=f"Generated {args.backend} file was not created")
        return row

    if args.backend == "lattigo":
        try:
            go = run(["go", "run", str(benchmark.generated_go), "-repetitions", str(args.repetitions)],
                     LATTIGO_DIR, args.timeout)
        except subprocess.TimeoutExpired:
            row.update(
                total_measured_ms="TIMEOUT",
                run_status="TIMEOUT",
                error_message=f"Encrypted benchmark exceeded the {args.timeout}s timeout",
            )
            return row

        go_output = go.stdout + go.stderr
        if go.returncode:
            row.update(run_status="LATTIGO_FAILED", error_message=first_lines(go_output))
            return row
        metrics = parse_go_metrics(go_output)
        if metrics is None:
            row.update(run_status="METRICS_MISSING", error_message="Generated Go program did not emit BENCHMARK_METRICS")
            return row
    else:
        # HEonGPU backend execution
        heongpu_dir = BUILD_DIR / "benchmarks" / "dnn_tensor" / "heongpu"
        cu_build_dir = heongpu_dir / "build_cu"
        cu_bin = cu_build_dir / ("generated_fhe.exe" if sys.platform == "win32" else "generated_fhe")
        try:
            if (heongpu_dir / "CMakeLists.txt").is_file():
                if not ((cu_build_dir / "Makefile").is_file() or (cu_build_dir / "build.ninja").is_file()):
                    cfg = run(["cmake", "-S", ".", "-B", "build_cu"], heongpu_dir, args.timeout)
                    if cfg.returncode != 0:
                        row.update(run_status="GPU_BUILD_PENDING", error_message=first_lines(cfg.stdout + cfg.stderr))
                        return row
                bld = run(["cmake", "--build", "build_cu"], heongpu_dir, args.timeout)
                if bld.returncode != 0:
                    row.update(run_status="HEONGPU_BUILD_FAILED", error_message=first_lines(bld.stdout + bld.stderr))
                    return row
            if not cu_bin.is_file():
                row.update(run_status="GPU_BUILD_PENDING", error_message=f"CUDA build required: {cu_bin}")
                return row
            cu_res = run([str(cu_bin), "-repetitions", str(args.repetitions)], heongpu_dir, args.timeout)
        except subprocess.TimeoutExpired:
            row.update(
                total_measured_ms="TIMEOUT",
                run_status="TIMEOUT",
                error_message=f"Encrypted HEonGPU benchmark exceeded the {args.timeout}s timeout",
            )
            return row
        except Exception as e:
            row.update(run_status="HEONGPU_FAILED", error_message=str(e))
            return row

        cu_output = cu_res.stdout + cu_res.stderr
        if cu_res.returncode:
            row.update(run_status="HEONGPU_FAILED", error_message=first_lines(cu_output))
            return row
        metrics = parse_go_metrics(cu_output)
        if metrics is None:
            row.update(run_status="METRICS_MISSING", error_message="Generated HEonGPU program did not emit BENCHMARK_METRICS")
            return row

    encrypt = float(metrics["encrypt_ms"])
    compute = float(metrics["compute_ms"])
    decrypt = float(metrics["decrypt_ms"])
    total_measured = round(encrypt + compute + decrypt, 3)
    level_start = int(metrics["level_start"])
    level_end = int(metrics["level_end"])
    row.update(
        repetitions=int(metrics.get("repetitions", args.repetitions)),
        encrypt_ms=encrypt,
        compute_ms=compute,
        decrypt_ms=decrypt,
        total_measured_ms=total_measured,
        rotation_keys=int(metrics["galois_keys"]),
        bootstrap_count=int(metrics["bootstrap_count"]),
        level_start=level_start,
        level_end=level_end,
        levels_consumed=level_start - level_end if level_end >= 0 else "",
        max_abs_error="" if metrics["max_abs_error"] is None else float(metrics["max_abs_error"]),
        precision_checked=bool(metrics["precision_checked"]),
        run_status="SUCCESS",
    )
    return row


def write_csv(rows: Iterable[dict[str, Any]], output_path: Path | None = None) -> Path:
    RESULTS_DIR.mkdir(exist_ok=True)
    output = output_path if output_path is not None else (RESULTS_DIR / "all_benchmarks_fhe_metrics.csv")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return output


def print_summary(rows: Iterable[dict[str, Any]]) -> None:
    print("\nFHE BENCHMARK METRICS SUMMARY")
    print("| Benchmark | Status | DSL ms | Encrypt ms | Compute ms | Decrypt ms | Total ms | Keys | Levels | Max Error |")
    print("| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for row in rows:
        print("| {benchmark} | {run_status} | {dsl_generation_ms} | {encrypt_ms} | {compute_ms} | "
              "{decrypt_ms} | {total_measured_ms} | {rotation_keys} | {levels_consumed} | {max_abs_error} |".format(**row))


def main() -> int:
    args = parse_args()
    if args.repetitions <= 0 or args.timeout <= 0:
        raise ValueError("--repetitions and --timeout must be positive")
    if args.naf_threshold < 0:
        raise ValueError("--naf-threshold must be non-negative")
    benchmarks = select_benchmarks(args.benchmarks)
    if args.backend == "lattigo" and not (LATTIGO_DIR / "go.mod").is_file():
        raise RuntimeError(f"Missing Lattigo module: {LATTIGO_DIR / 'go.mod'}")

    if not args.skip_build:
        print(f"Building {TARGET}...")
        built, output = build_target(args.timeout)
        if not built:
            print(output, file=sys.stderr)
            return 1

    executable = executable_path()
    if not executable.is_file():
        raise RuntimeError(f"Benchmark executable not found: {executable}")

    rows: list[dict[str, Any]] = []
    for index, benchmark in enumerate(benchmarks, start=1):
        print(f"[{index}/{len(benchmarks)}] {benchmark.name}...")
        row = execute_benchmark(benchmark, executable, args)
        rows.append(row)
        print(f"  {row['run_status']}")

    output_path = Path(args.output_csv) if args.output_csv else None
    csv_path = write_csv(rows, output_path)
    print_summary(rows)
    print(f"\nResults saved to: {csv_path}")
    return 0 if all(row["run_status"] == "SUCCESS" for row in rows) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
        print(error, file=sys.stderr)
        raise SystemExit(2)
