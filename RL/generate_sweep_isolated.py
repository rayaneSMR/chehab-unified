import argparse
import csv
import math
import os
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

from pytrs.peak_ram import (
    FHEParams,
    LATTIGO_CONFIG,
    NotEstimable,
    SEAL_CONFIG,
    estimate_peak_ram,
    estimate_vectorized_peak_ram,
)
from pytrs.expr import Const, Op, Var


RL_DIR = Path(__file__).resolve().parent
LATTIGO_DIR = RL_DIR.parent / "lattigo_backend"
SEAL_WORKER = RL_DIR / "seal_sweep_worker.py"
DEFAULT_OUTPUT = RL_DIR / "sweep_results_isolated.csv"


def ast_addition(size):
    inputs = [Var(f"a{i}") for i in range(size)]
    ast = inputs[0]
    for operand in inputs[1:]:
        ast = Op("+", [ast, operand])
    return ast, 0


def ast_batched_multiplications(count):
    products = [
        Op("*", [Var(f"a{i}"), Var(f"b{i}")])
        for i in range(count)
    ]
    return Op("Vec", products), 1


def ast_dot_product(size):
    left = Op("Vec", [Var(f"left_{i}") for i in range(size)])
    right = Op("Vec", [Var(f"right_{i}") for i in range(size)])
    result = Op("VecMul", [left, right])
    rotation_steps = []
    step = 1
    while step < size:
        rotation_steps.append(step)
        step *= 2
    for step in reversed(rotation_steps):
        result = Op("VecAddRot", [result, Const(step)])
    return result, len(rotation_steps) + 1


def ast_deep_polynomial(depth):
    result = Op("Vec", [Var("x")])
    for _ in range(depth):
        result = Op("VecMul", [result, result])
    return result, 1


def ast_rotation_convolution(image_size):
    input_vector = Op("Vec", [Var("input")])
    result = None
    rotation_count = 0
    for row in range(3):
        for col in range(3):
            step = row * image_size + col
            rotated = input_vector
            if step:
                rotated = Op("<<", [input_vector, Const(step)])
                rotation_count += 1
            term = Op("VecMul", [rotated, Const(1.0 / 9.0)])
            result = term if result is None else Op("VecAdd", [result, term])
    return result, rotation_count


def ast_high_churn(operation_count):
    result = Op("VecMul", [Op("Vec", [Var("left")]), Op("Vec", [Var("right")])])
    addend = Op("Vec", [Var("right")])
    for _ in range(operation_count):
        result = Op("VecAdd", [result, addend])
    return result, 1


EXPERIMENTS = [
    {"type": 1, "name": "Ciphertext Addition", "arg": 4, "N": 8192, "L": 4},
    {"type": 1, "name": "Ciphertext Addition", "arg": 16, "N": 8192, "L": 4},
    {"type": 1, "name": "Ciphertext Addition", "arg": 64, "N": 16384, "L": 6},
    {"type": 1, "name": "Ciphertext Addition", "arg": 128, "N": 32768, "L": 8},
    {"type": 2, "name": "Batched Ciphertext Multiplication", "arg": 2, "N": 8192, "L": 4},
    {"type": 2, "name": "Batched Ciphertext Multiplication", "arg": 8, "N": 8192, "L": 4},
    {"type": 2, "name": "Batched Ciphertext Multiplication", "arg": 16, "N": 16384, "L": 6},
    {"type": 2, "name": "Batched Ciphertext Multiplication", "arg": 32, "N": 32768, "L": 8},
    {"type": 3, "name": "Dot Product", "arg": 4, "N": 8192, "L": 4},
    {"type": 3, "name": "Dot Product", "arg": 8, "N": 8192, "L": 4},
]

LATTIGO_ONLY_EXPERIMENTS = [
    {"type": 3, "name": "Dot Product", "arg": 16, "N": 16384, "L": 6},
    {"type": 3, "name": "Dot Product", "arg": 32, "N": 16384, "L": 6},
    {"type": 3, "name": "Dot Product", "arg": 64, "N": 16384, "L": 6},
    {"type": 3, "name": "Dot Product", "arg": 128, "N": 32768, "L": 8},
    {"type": 3, "name": "Dot Product", "arg": 256, "N": 32768, "L": 8},
    {"type": 4, "name": "Deep Polynomial", "arg": 3, "N": 16384, "L": 7},
    {"type": 5, "name": "Conv2D Rotation Window", "arg": 8, "N": 8192, "L": 4},
    {"type": 6, "name": "High-Churn Arithmetic", "arg": 128, "N": 8192, "L": 4},
]

CSV_FIELDS = [
    "Benchmark",
    "Variant",
    "N",
    "L",
    "Total Keys",
    "SEAL Baseline (MB)",
    "SEAL Keys Peak (MB)",
    "SEAL Inputs Peak (MB)",
    "SEAL Evaluation Peak (MB)",
    "SEAL Actual (MB)",
    "SEAL Est Delta Lo (MB)",
    "SEAL Est Delta Hi (MB)",
    "SEAL Error Lo (%)",
    "SEAL Dir Lo",
    "SEAL Error Hi (%)",
    "SEAL Dir Hi",
    "SEAL In Bounds",
    "Lattigo Baseline (MB)",
    "Lattigo Keys Peak (MB)",
    "Lattigo Inputs Peak (MB)",
    "Lattigo Evaluation Peak (MB)",
    "Lattigo Actual (MB)",
    "Lattigo Est Delta Lo (MB)",
    "Lattigo Est Delta Hi (MB)",
    "Lattigo Error Lo (%)",
    "Lattigo Dir Lo",
    "Lattigo Error Hi (%)",
    "Lattigo Dir Hi",
    "Lattigo In Bounds",
]


def run_peak_rss(command, timeout_seconds, cwd=None, env=None):
    try:
        result = subprocess.run(
            ["/usr/bin/time", "-v", *command],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=env,
        )
    except subprocess.TimeoutExpired as error:
        print(f"Timed out after {timeout_seconds}s: {' '.join(command)}", file=sys.stderr)
        if error.stderr:
            print(error.stderr, file=sys.stderr)
        return -1

    if result.returncode:
        print(f"Command failed ({result.returncode}): {' '.join(command)}", file=sys.stderr)
        if result.stdout:
            print(result.stdout, file=sys.stderr)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return -1

    for line in result.stderr.splitlines():
        if "Maximum resident set size" in line:
            return int(line.split(":")[-1].strip()) * 1024

    print(f"No peak RSS reported for: {' '.join(command)}", file=sys.stderr)
    return -1


def run_seal_worker(experiment, phase, timeout_seconds):
    command = [
        sys.executable,
        str(SEAL_WORKER),
        str(experiment["type"]),
        str(experiment["N"]),
        str(experiment["L"]),
        str(experiment["arg"]),
        phase,
    ]
    return run_peak_rss(command, timeout_seconds)


def metric_columns(name, actual_bytes, estimate_lo, estimate_hi):
    if actual_bytes < 0:
        return {
            f"{name} Actual (MB)": "FAIL",
            f"{name} Error Lo (%)": "FAIL",
            f"{name} Dir Lo": "FAIL",
            f"{name} Error Hi (%)": "FAIL",
            f"{name} Dir Hi": "FAIL",
            f"{name} In Bounds": "FAIL",
        }
    if actual_bytes == 0:
        return {
            f"{name} Actual (MB)": 0.0,
            f"{name} Error Lo (%)": "N/A",
            f"{name} Dir Lo": "N/A",
            f"{name} Error Hi (%)": "N/A",
            f"{name} Dir Hi": "N/A",
            f"{name} In Bounds": estimate_lo <= 0 <= estimate_hi,
        }

    def error_and_direction(estimate):
        error = abs(estimate - actual_bytes) / actual_bytes * 100
        direction = "OVER" if estimate > actual_bytes else "UNDER" if estimate < actual_bytes else "EXACT"
        return round(error, 2), direction

    error_lo, direction_lo = error_and_direction(estimate_lo)
    error_hi, direction_hi = error_and_direction(estimate_hi)
    return {
        f"{name} Actual (MB)": round(actual_bytes / 1024**2, 2),
        f"{name} Error Lo (%)": error_lo,
        f"{name} Dir Lo": direction_lo,
        f"{name} Error Hi (%)": error_hi,
        f"{name} Dir Hi": direction_hi,
        f"{name} In Bounds": estimate_lo <= actual_bytes <= estimate_hi,
    }


def phase_peaks(name, peaks):
    columns = {}
    names = ("baseline", "keys", "inputs", "evaluation")
    for phase in names:
        value = peaks[phase]
        columns[f"{name} {phase.title()} Peak (MB)" if phase != "baseline"
                else f"{name} Baseline (MB)"] = (
            "FAIL" if value <= 0 else round(value / 1024**2, 2)
        )
    baseline, evaluation = peaks["baseline"], peaks["evaluation"]
    columns[f"{name} Actual (MB)"] = (
        "FAIL"
        if min(peaks.values()) <= 0
        else round(max(0, evaluation - baseline) / 1024**2, 2)
    )
    return columns


def collect_phase_peaks(experiment, runner, backend, timeout_seconds):
    peaks = {}
    for phase in ("baseline", "keys", "inputs", "evaluation"):
        if backend == "Lattigo":
            env = os.environ.copy()
            env["GOGC"] = "100"
            command = [
                str(runner),
                str(experiment["type"]),
                str(experiment["log_n"]),
                str(experiment["L"]),
                str(experiment["arg"]),
                phase,
            ]
            peaks[phase] = run_peak_rss(
                command, timeout_seconds, cwd=LATTIGO_DIR, env=env
            )
        elif (
            experiment not in LATTIGO_ONLY_EXPERIMENTS
            and experiment["type"] in (1, 2, 3)
        ):
            peaks[phase] = run_seal_worker(experiment, phase, timeout_seconds)
        else:
            peaks[phase] = -1
    return peaks


def append_result(output_path, row):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", newline="") as result_file:
        writer = csv.DictWriter(result_file, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writerow(row)


def _ranks(values):
    order = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and values[order[end]] == values[order[start]]:
            end += 1
        average_rank = ((start + 1) + end) / 2
        for position in range(start, end):
            ranks[order[position]] = average_rank
        start = end
    return ranks


def _spearman(left, right):
    left_ranks, right_ranks = _ranks(left), _ranks(right)
    left_mean, right_mean = statistics.mean(left_ranks), statistics.mean(right_ranks)
    numerator = sum(
        (left_rank - left_mean) * (right_rank - right_mean)
        for left_rank, right_rank in zip(left_ranks, right_ranks)
    )
    left_norm = sum((rank - left_mean) ** 2 for rank in left_ranks)
    right_norm = sum((rank - right_mean) ** 2 for rank in right_ranks)
    denominator = math.sqrt(left_norm * right_norm)
    return numerator / denominator if denominator else float("nan")


def print_validation_summary(output_path):
    with output_path.open(newline="") as result_file:
        rows = list(csv.DictReader(result_file))
    for backend in ("SEAL", "Lattigo"):
        points = []
        for row in rows:
            actual = row[f"{backend} Actual (MB)"]
            estimate_lo = row[f"{backend} Est Delta Lo (MB)"]
            if actual in ("FAIL", "N/A") or estimate_lo in ("FAIL", "N/A"):
                continue
            points.append((float(actual), float(estimate_lo), row))
        if not points:
            print(f"{backend}: no usable measurements")
            continue
        positive_points = [(actual, estimate) for actual, estimate, _ in points if actual > 0]
        signed_errors = [
            (estimate - actual) / actual * 100
            for actual, estimate in positive_points
        ]
        coverage = sum(
            str(row[f"{backend} In Bounds"]).lower() == "true"
            for _, _, row in points
        )
        rho = _spearman(
            [actual for actual, _, _ in points],
            [estimate for _, estimate, _ in points],
        )
        mean_signed_error = (
            statistics.mean(signed_errors) if signed_errors else float("nan")
        )
        print(
            f"{backend}: interval coverage={coverage}/{len(points)}, "
            f"mean signed lo error={mean_signed_error:.2f}% "
            f"(n={len(positive_points)} positive deltas), "
            f"Spearman rho={rho:.3f} (n={len(points)})"
        )


def main():
    parser = argparse.ArgumentParser(description="Measure isolated SEAL and Lattigo peak RSS.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--timeout-seconds", type=int, default=720)
    args = parser.parse_args()
    output_path = args.output.resolve()

    with tempfile.TemporaryDirectory(prefix="chehab-sweep-") as temp_dir:
        runner = Path(temp_dir) / "sweep_runner"
        subprocess.run(
            ["go", "build", "-mod=readonly", "-o", str(runner), "sweep_runner.go"],
            cwd=LATTIGO_DIR,
            check=True,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", newline="") as result_file:
            csv.DictWriter(
                result_file,
                fieldnames=CSV_FIELDS,
                lineterminator="\n",
            ).writeheader()

        for experiment in EXPERIMENTS + LATTIGO_ONLY_EXPERIMENTS:
            print(
                f"Running {experiment['name']} "
                f"(Arg: {experiment['arg']}, N: {experiment['N']}, L: {experiment['L']})...",
                flush=True,
            )
            if experiment["type"] == 1:
                ast, keys = ast_addition(experiment["arg"])
            elif experiment["type"] == 2:
                ast, keys = ast_batched_multiplications(experiment["arg"])
            elif experiment["type"] == 3:
                ast, keys = ast_dot_product(experiment["arg"])
            elif experiment["type"] == 4:
                ast, keys = ast_deep_polynomial(experiment["arg"])
            elif experiment["type"] == 5:
                ast, keys = ast_rotation_convolution(experiment["arg"])
            else:
                ast, keys = ast_high_churn(experiment["arg"])

            experiment["log_n"] = {8192: 13, 16384: 14, 32768: 15}[
                experiment["N"]
            ]
            lattigo_peaks = collect_phase_peaks(
                experiment, runner, "Lattigo", args.timeout_seconds
            )
            seal_peaks = collect_phase_peaks(
                experiment, runner, "SEAL", args.timeout_seconds
            )
            lattigo_actual = (
                max(
                    0,
                    lattigo_peaks["evaluation"] - lattigo_peaks["baseline"],
                )
                if min(lattigo_peaks.values()) > 0
                else -1
            )
            seal_actual = (
                max(0, seal_peaks["evaluation"] - seal_peaks["baseline"])
                if min(seal_peaks.values()) > 0
                else -1
            )

            params = FHEParams(
                poly_modulus_degree=experiment["N"],
                coeff_modulus_num_primes=experiment["L"],
            )
            if experiment["type"] in (3, 4, 5, 6):
                lattigo_estimate = estimate_vectorized_peak_ram(
                    ast, params, keys_threshold=9999, backend_config=LATTIGO_CONFIG
                )
                if isinstance(lattigo_estimate, NotEstimable):
                    raise RuntimeError(
                        f"{experiment['name']} was not vectorized: "
                        f"{lattigo_estimate.reason}"
                    )
            else:
                lattigo_estimate = estimate_peak_ram(
                    ast, params, keys_threshold=9999, backend_config=LATTIGO_CONFIG
                )
            is_lattigo_only = experiment in LATTIGO_ONLY_EXPERIMENTS
            seal_estimate = (
                None
                if is_lattigo_only
                else (
                    estimate_vectorized_peak_ram(
                        ast, params, keys_threshold=9999, backend_config=SEAL_CONFIG
                    )
                    if experiment["type"] == 3
                    else estimate_peak_ram(
                        ast, params, keys_threshold=9999, backend_config=SEAL_CONFIG
                    )
                )
            )
            if isinstance(seal_estimate, NotEstimable):
                raise RuntimeError(
                    f"{experiment['name']} was not vectorized for SEAL: "
                    f"{seal_estimate.reason}"
                )
            lattigo_base = LATTIGO_CONFIG.base_bytes_overhead(
                experiment["N"], experiment["L"]
            )
            lattigo_lo_delta = max(
                0, lattigo_estimate.estimated_bytes_lo - lattigo_base
            )
            lattigo_hi_delta = max(
                0, lattigo_estimate.estimated_bytes_hi - lattigo_base
            )
            if seal_estimate is not None:
                seal_base = SEAL_CONFIG.base_bytes_overhead(
                    experiment["N"], experiment["L"]
                )
                seal_lo_delta = max(
                    0, seal_estimate.estimated_bytes_lo - seal_base
                )
                seal_hi_delta = max(
                    0, seal_estimate.estimated_bytes_hi - seal_base
                )
            else:
                seal_lo_delta = None
                seal_hi_delta = None

            row = {
                "Benchmark": experiment["name"],
                "Variant": experiment["arg"],
                "N": experiment["N"],
                "L": experiment["L"],
                "Total Keys": keys,
                "SEAL Est Delta Lo (MB)": (
                    "N/A"
                    if seal_lo_delta is None
                    else round(seal_lo_delta / 1024**2, 2)
                ),
                "SEAL Est Delta Hi (MB)": (
                    "N/A"
                    if seal_hi_delta is None
                    else round(seal_hi_delta / 1024**2, 2)
                ),
                "Lattigo Est Delta Lo (MB)": round(
                    lattigo_lo_delta / 1024**2, 2
                ),
                "Lattigo Est Delta Hi (MB)": round(
                    lattigo_hi_delta / 1024**2, 2
                ),
            }
            row.update(
                phase_peaks("SEAL", seal_peaks)
            )
            row.update(
                phase_peaks("Lattigo", lattigo_peaks)
            )
            if seal_estimate is None:
                row.update(
                    {
                        "SEAL Baseline (MB)": "N/A",
                        "SEAL Keys Peak (MB)": "N/A",
                        "SEAL Inputs Peak (MB)": "N/A",
                        "SEAL Evaluation Peak (MB)": "N/A",
                        "SEAL Actual (MB)": "N/A",
                        "SEAL Error Lo (%)": "N/A",
                        "SEAL Dir Lo": "N/A",
                        "SEAL Error Hi (%)": "N/A",
                        "SEAL Dir Hi": "N/A",
                        "SEAL In Bounds": "N/A",
                    }
                )
            else:
                row.update(
                    metric_columns(
                        "SEAL",
                        seal_actual,
                        seal_lo_delta,
                        seal_hi_delta,
                    )
                )
            row.update(
                metric_columns(
                    "Lattigo",
                    lattigo_actual,
                    lattigo_lo_delta,
                    lattigo_hi_delta,
                )
            )
            append_result(output_path, row)

    print(f"Results written to {output_path}")
    print_validation_summary(output_path)


if __name__ == "__main__":
    main()
