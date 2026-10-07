import argparse
import csv
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from pytrs.expr import Const, Op, Var
from pytrs.peak_ram import (
    FHEParams,
    LATTIGO_CONFIG,
    estimate_peak_ram,
)


ROOT = Path(__file__).resolve().parent.parent
BUILD_BENCHMARK = ROOT / "build" / "benchmarks"
DOT_PRODUCT_BINARY = BUILD_BENCHMARK / "dot_product" / "dot_product"
INPUT_GENERATOR = ROOT / "benchmarks" / "dot_product" / "generate_dot_product.py"
LATTIGO_DIR = ROOT / "lattigo_backend"
DEFAULT_OUTPUT = ROOT / "RL" / "compiled_program_results.csv"
WIDTHS = (2, 4, 8, 16, 32)


def parse_compiler_program(source: str):
    variables = {
        name: Var(input_name)
        for name, input_name in re.findall(
            r'^\s*(\w+)\s*:=\s*encryptedInputs\["([^"]+)"\]',
            source,
            flags=re.MULTILINE,
        )
    }
    operation_pattern = re.compile(
        r"^\s*(\w+),\s*_\s*=\s*eval\.(MulRelinNew|MulNew|AddNew|SubNew|RotateNew)"
        r"\(([^,]+),\s*([^)]+)\)",
        flags=re.MULTILINE,
    )
    operation_names = {
        "MulRelinNew": "*",
        "MulNew": "*",
        "AddNew": "+",
        "SubNew": "-",
        "RotateNew": "<<",
    }

    for destination, method, left_text, right_text in operation_pattern.findall(source):
        left_name = left_text.strip()
        if left_name not in variables:
            raise ValueError(f"Unknown compiler-generated operand: {left_name}")
        left = variables[left_name]
        right_name = right_text.strip()
        if right_name in variables:
            right = variables[right_name]
        else:
            try:
                right = Const(int(right_name))
            except ValueError:
                try:
                    right = Const(float(right_name))
                except ValueError as error:
                    raise ValueError(
                        f"Unknown compiler-generated operand: {right_name}"
                    ) from error
        variables[destination] = Op(operation_names[method], [left, right])

    outputs = re.findall(
        r'^\s*encryptedOutputs\["[^"]+"\]\s*=\s*(\w+)',
        source,
        flags=re.MULTILINE,
    )
    if not outputs or outputs[-1] not in variables:
        raise ValueError("No compiler-generated ciphertext output was found")
    return variables[outputs[-1]]


def parse_parameters(source: str) -> FHEParams:
    values = {}
    for key in ("LogN", "LogQ", "LogP"):
        match = re.search(
            rf"{key}\s*:\s*(\d+|\[\]int\{{[^}}]*\}})",
            source,
        )
        if not match:
            raise ValueError(f"Generated program is missing {key}")
        if key == "LogN":
            values[key] = int(match.group(1))
        else:
            values[key] = [
                int(value.strip())
                for value in match.group(1).removeprefix("[]int{").removesuffix("}").split(",")
                if value.strip()
            ]
    return FHEParams(
        poly_modulus_degree=1 << values["LogN"],
        coeff_modulus_num_primes=len(values["LogQ"]) + len(values["LogP"]),
    )


def compile_measurement(width: int):
    if not DOT_PRODUCT_BINARY.is_file():
        raise FileNotFoundError(
            f"{DOT_PRODUCT_BINARY} is missing; build it with "
            "`cmake --build build --target dot_product`"
        )
    with tempfile.TemporaryDirectory(
        prefix=f"chehab-dot-{width}-", dir=BUILD_BENCHMARK
    ) as temporary_directory:
        working_directory = Path(temporary_directory)
        shutil.copy2(DOT_PRODUCT_BINARY, working_directory / "dot_product")
        shutil.copy2(INPUT_GENERATOR, working_directory / "generate_dot_product.py")
        (working_directory / "he").mkdir()
        subprocess.run(
            [
                "python3",
                "generate_dot_product.py",
                "--slot_count",
                str(width),
            ],
            cwd=working_directory,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            [
                "./dot_product",
                "0",
                str(width),
                "constrained",
                "1",
                "0",
                "0",
                "1",
                "1",
                "1",
            ],
            cwd=working_directory,
            check=True,
            capture_output=True,
            text=True,
            timeout=300,
        )
        generated_source = working_directory / "generated_fhe.go"
        if not generated_source.is_file():
            raise FileNotFoundError("CHEHAB compiler did not emit generated_fhe.go")
        source = generated_source.read_text()
        ast = parse_compiler_program(source)
        params = parse_parameters(source)
        estimate = estimate_peak_ram(
            ast,
            params,
            backend_config=LATTIGO_CONFIG,
        )

        executable = working_directory / "compiled_fhe"
        subprocess.run(
            [
                "go",
                "build",
                "-mod=readonly",
                "-o",
                str(executable),
                str(generated_source),
            ],
            cwd=LATTIGO_DIR,
            check=True,
            capture_output=True,
            text=True,
            timeout=300,
        )
        measurement = subprocess.run(
            ["/usr/bin/time", "-f", "peak_rss_kib=%M", str(executable)],
            cwd=working_directory,
            env={**os.environ, "GOGC": "100"},
            check=True,
            capture_output=True,
            text=True,
            timeout=300,
        )
        rss_match = re.search(r"peak_rss_kib=(\d+)", measurement.stderr)
        if not rss_match:
            raise RuntimeError(
                f"Could not read peak RSS for width {width}: {measurement.stderr}"
            )
        actual_bytes = int(rss_match.group(1)) * 1024
        return {
            "Width": width,
            "N": params.poly_modulus_degree,
            "L": params.coeff_modulus_num_primes,
            "Estimated Lo (MiB)": estimate.estimated_bytes_lo / 2**20,
            "Estimated Hi (MiB)": estimate.estimated_bytes_hi / 2**20,
            "Measured RSS (MiB)": actual_bytes / 2**20,
            "Signed Lo Error (%)": (
                (estimate.estimated_bytes_lo - actual_bytes) / actual_bytes * 100
            ),
            "In Interval": (
                estimate.estimated_bytes_lo
                <= actual_bytes
                <= estimate.estimated_bytes_hi
            ),
        }


def average_ranks(values):
    ordered = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and values[ordered[end]] == values[ordered[start]]:
            end += 1
        rank = (start + 1 + end) / 2
        for index in range(start, end):
            ranks[ordered[index]] = rank
        start = end
    return ranks


def spearman(left, right):
    left_ranks, right_ranks = average_ranks(left), average_ranks(right)
    left_mean = sum(left_ranks) / len(left_ranks)
    right_mean = sum(right_ranks) / len(right_ranks)
    covariance = sum(
        (left_rank - left_mean) * (right_rank - right_mean)
        for left_rank, right_rank in zip(left_ranks, right_ranks)
    )
    left_variance = sum((rank - left_mean) ** 2 for rank in left_ranks)
    right_variance = sum((rank - right_mean) ** 2 for rank in right_ranks)
    return covariance / (left_variance * right_variance) ** 0.5


def main():
    parser = argparse.ArgumentParser(
        description="Compile CHEHAB dot-product programs and validate peak-RAM estimates."
    )
    parser.add_argument(
        "--widths",
        nargs="+",
        type=int,
        default=WIDTHS,
        help="dot-product widths to compile and measure",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    results = [compile_measurement(width) for width in args.widths]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fields = list(results[0])
    with args.output.open("w", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(results)

    coverage = sum(result["In Interval"] for result in results)
    mean_signed_error = sum(
        result["Signed Lo Error (%)"] for result in results
    ) / len(results)
    rho = spearman(
        [result["Measured RSS (MiB)"] for result in results],
        [result["Estimated Lo (MiB)"] for result in results],
    )
    print(f"Wrote {args.output}")
    for result in results:
        print(
            f"width={result['Width']} N={result['N']} L={result['L']} "
            f"lo={result['Estimated Lo (MiB)']:.2f} MiB "
            f"hi={result['Estimated Hi (MiB)']:.2f} MiB "
            f"RSS={result['Measured RSS (MiB)']:.2f} MiB "
            f"signed_lo_error={result['Signed Lo Error (%)']:.2f}% "
            f"in_interval={result['In Interval']}"
        )
    print(
        f"coverage={coverage}/{len(results)}, "
        f"mean_signed_lo_error={mean_signed_error:.2f}%, "
        f"spearman_rho={rho:.3f}"
    )


if __name__ == "__main__":
    main()
