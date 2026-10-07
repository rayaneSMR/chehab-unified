import argparse
import csv
import subprocess
import sys
import tempfile
from pathlib import Path

from pytrs.peak_ram import (
    FHEParams,
    LATTIGO_CONFIG,
    SEAL_CONFIG,
    estimate_peak_ram,
)
from pytrs.expr import Op, Var


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
    products = [
        Op("*", [Var(f"c{i}"), Var(f"c{i + 1}")])
        for i in range(0, size, 2)
    ]
    result = products[0] if products else Var("x")
    for product in products[1:]:
        result = Op("+", [result, product])
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
    {"type": 3, "name": "Dot Product", "arg": 16, "N": 16384, "L": 6},
    {"type": 3, "name": "Dot Product", "arg": 32, "N": 16384, "L": 6},
    {"type": 3, "name": "Dot Product", "arg": 64, "N": 16384, "L": 6},
    {"type": 3, "name": "Dot Product", "arg": 128, "N": 32768, "L": 8},
    {"type": 3, "name": "Dot Product", "arg": 256, "N": 32768, "L": 8},
]

CSV_FIELDS = [
    "Benchmark",
    "Variant",
    "N",
    "L",
    "Total Keys",
    "SEAL Actual (MB)",
    "SEAL Est Lo (MB)",
    "SEAL Est Hi (MB)",
    "SEAL Error Lo (%)",
    "SEAL Dir Lo",
    "SEAL Error Hi (%)",
    "SEAL Dir Hi",
    "SEAL In Bounds",
    "Lattigo Actual (MB)",
    "Lattigo Est Lo (MB)",
    "Lattigo Est Hi (MB)",
    "Lattigo Error Lo (%)",
    "Lattigo Dir Lo",
    "Lattigo Error Hi (%)",
    "Lattigo Dir Hi",
    "Lattigo In Bounds",
]


def run_peak_rss(command, timeout_seconds, cwd=None):
    try:
        result = subprocess.run(
            ["/usr/bin/time", "-v", *command],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
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


def run_seal_worker(experiment, timeout_seconds):
    command = [
        sys.executable,
        str(SEAL_WORKER),
        str(experiment["type"]),
        str(experiment["N"]),
        str(experiment["L"]),
        str(experiment["arg"]),
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as error:
        print(f"Timed out after {timeout_seconds}s: {' '.join(command)}", file=sys.stderr)
        if error.stderr:
            print(error.stderr, file=sys.stderr)
        return -1

    if result.returncode:
        print(f"SEAL worker failed ({result.returncode}): {' '.join(command)}", file=sys.stderr)
        if result.stdout:
            print(result.stdout, file=sys.stderr)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return -1

    try:
        peak_bytes = int(result.stdout.strip())
    except ValueError:
        print(f"SEAL worker returned invalid peak RSS: {result.stdout!r}", file=sys.stderr)
        return -1
    if peak_bytes <= 0:
        print(f"SEAL worker returned non-positive peak RSS: {peak_bytes}", file=sys.stderr)
        return -1
    return peak_bytes


def metric_columns(name, actual_bytes, estimate_lo, estimate_hi):
    if actual_bytes <= 0:
        return {
            f"{name} Actual (MB)": "FAIL",
            f"{name} Error Lo (%)": "FAIL",
            f"{name} Dir Lo": "FAIL",
            f"{name} Error Hi (%)": "FAIL",
            f"{name} Dir Hi": "FAIL",
            f"{name} In Bounds": "FAIL",
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


def append_result(output_path, row):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", newline="") as result_file:
        writer = csv.DictWriter(result_file, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writerow(row)


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

        for experiment in EXPERIMENTS:
            print(
                f"Running {experiment['name']} "
                f"(Arg: {experiment['arg']}, N: {experiment['N']}, L: {experiment['L']})...",
                flush=True,
            )
            if experiment["type"] == 1:
                ast, keys = ast_addition(experiment["arg"])
            elif experiment["type"] == 2:
                ast, keys = ast_batched_multiplications(experiment["arg"])
            else:
                ast, keys = ast_dot_product(experiment["arg"])

            log_n = {8192: 13, 16384: 14, 32768: 15}[experiment["N"]]
            lattigo_actual = run_peak_rss(
                [
                    str(runner),
                    str(experiment["type"]),
                    str(log_n),
                    str(experiment["L"]),
                    str(experiment["arg"]),
                ],
                args.timeout_seconds,
                cwd=LATTIGO_DIR,
            )
            seal_actual = run_seal_worker(experiment, args.timeout_seconds)

            params = FHEParams(
                poly_modulus_degree=experiment["N"],
                coeff_modulus_num_primes=experiment["L"],
            )
            lattigo_estimate = estimate_peak_ram(
                ast, params, keys_threshold=9999, backend_config=LATTIGO_CONFIG
            )
            seal_estimate = estimate_peak_ram(
                ast, params, keys_threshold=9999, backend_config=SEAL_CONFIG
            )

            row = {
                "Benchmark": experiment["name"],
                "Variant": experiment["arg"],
                "N": experiment["N"],
                "L": experiment["L"],
                "Total Keys": keys,
                "SEAL Est Lo (MB)": round(seal_estimate.total_bytes_lo / 1024**2, 2),
                "SEAL Est Hi (MB)": round(seal_estimate.total_bytes_hi / 1024**2, 2),
                "Lattigo Est Lo (MB)": round(lattigo_estimate.total_bytes_lo / 1024**2, 2),
                "Lattigo Est Hi (MB)": round(lattigo_estimate.total_bytes_hi / 1024**2, 2),
            }
            row.update(
                metric_columns(
                    "SEAL",
                    seal_actual,
                    seal_estimate.total_bytes_lo,
                    seal_estimate.total_bytes_hi,
                )
            )
            row.update(
                metric_columns(
                    "Lattigo",
                    lattigo_actual,
                    lattigo_estimate.total_bytes_lo,
                    lattigo_estimate.total_bytes_hi,
                )
            )
            append_result(output_path, row)

    print(f"Results written to {output_path}")


if __name__ == "__main__":
    main()
