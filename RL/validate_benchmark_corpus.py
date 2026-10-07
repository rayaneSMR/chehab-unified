import argparse
import csv
import os
import re
import shutil
import statistics
import subprocess
import tempfile
from pathlib import Path

from pytrs.expr import Const, Op, Var
from pytrs.peak_ram import FHEParams, LATTIGO_CONFIG, estimate_peak_ram


ROOT = Path(__file__).resolve().parent.parent
SOURCE_BENCHMARKS = ROOT / "benchmarks"
BUILD_BENCHMARKS = ROOT / "build" / "benchmarks"
LATTIGO_DIR = ROOT / "lattigo_backend"
DEFAULT_RAW_OUTPUT = ROOT / "RL" / "compiled_corpus_runs.csv"
DEFAULT_SUMMARY_OUTPUT = ROOT / "RL" / "compiled_corpus_summary.csv"
DEFAULT_METRICS_OUTPUT = ROOT / "RL" / "compiled_corpus_metrics.csv"
DEFAULT_FAILURES_OUTPUT = ROOT / "RL" / "compiled_corpus_failures.csv"
BENCHMARKS = (
    "box_blur",
    "conv2d",
    "discrete_cosin_transform",
    "deep_network",
    "dot_product",
    "gx_kernel",
    "gy_kernel",
    "hamming_dist",
    "l2_distance",
    "lin_reg",
    "matrix_mul",
    "max",
    "poly_derivative",
    "poly_reg",
    "roberts_cross",
    "sobel",
    "sort",
)
WIDTHS = (4, 8, 16, 32)
EXTENDED_WIDTH_BENCHMARKS = frozenset(
    {"dot_product", "hamming_dist", "l2_distance"}
)
REPEATS = 5
COMPILER_TIMEOUT_SECONDS = 180
BUILD_TIMEOUT_SECONDS = 300
RUN_TIMEOUT_SECONDS = 180
PHASE_NAMES = ("baseline", "keys", "inputs", "evaluation")


def parse_compiler_program(source: str):
    variables = {
        name: Var(input_name)
        for name, input_name in re.findall(
            r'^\s*(\w+)\s*:=\s*encryptedInputs\["([^"]+)"\]',
            source,
            flags=re.MULTILINE,
        )
    }
    plaintext_names = set(
        re.findall(
            r'^\s*(\w+)\s*:=\s*encodedInputs\["[^"]+"\]',
            source,
            flags=re.MULTILINE,
        )
    )
    plaintext_names.update(
        re.findall(
            r"^\s*(\w+)\s*:=\s*\w+\.NewPlaintext\(",
            source,
            flags=re.MULTILINE,
        )
    )
    variables.update({name: Const(0) for name in plaintext_names})
    operations = {
        "MulRelinNew": "*",
        "MulNew": "*",
        "AddNew": "+",
        "SubNew": "-",
        "RotateNew": "<<",
    }
    pattern = re.compile(
        r"^\s*(\w+),\s*_\s*=\s*eval\.(MulRelinNew|MulNew|AddNew|SubNew|RotateNew)"
        r"\(([^,]+),\s*([^)]+)\)",
        flags=re.MULTILINE,
    )
    for destination, method, left_text, right_text in pattern.findall(source):
        left_name = left_text.strip()
        if left_name not in variables:
            raise ValueError(f"Unknown generated operand: {left_name}")
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
                    raise ValueError(f"Unknown generated operand: {right_name}") from error
        variables[destination] = Op(operations[method], [variables[left_name], right])

    unary_pattern = re.compile(
        r"^\s*(\w+),\s*_\s*=\s*eval\.NegNew\(([^)]+)\)",
        flags=re.MULTILINE,
    )
    for destination, operand_text in unary_pattern.findall(source):
        operand_name = operand_text.strip()
        if operand_name not in variables:
            raise ValueError(f"Unknown generated operand: {operand_name}")
        variables[destination] = Op("-", [Const(0), variables[operand_name]])

    output_names = re.findall(
        r'^\s*encryptedOutputs\["[^"]+"\]\s*=\s*(\w+)',
        source,
        flags=re.MULTILINE,
    )
    if not output_names:
        raise ValueError("No generated ciphertext output was found")
    missing_outputs = [name for name in output_names if name not in variables]
    if missing_outputs:
        raise ValueError(
            "Generated ciphertext output(s) have no parsed expression: "
            + ", ".join(missing_outputs)
        )
    outputs = [variables[name] for name in output_names]
    return outputs[0] if len(outputs) == 1 else Op("Vec", outputs)


def parse_parameters(source: str) -> FHEParams:
    log_n = re.search(r"LogN\s*:\s*(\d+)", source)
    log_q = re.search(r"LogQ\s*:\s*\[\]int\{([^}]*)\}", source)
    log_p = re.search(r"LogP\s*:\s*\[\]int\{([^}]*)\}", source)
    if not log_n or not log_q or not log_p:
        raise ValueError("Could not parse LogN, LogQ, and LogP from generated source")
    q_count = len([value for value in log_q.group(1).split(",") if value.strip()])
    p_count = len([value for value in log_p.group(1).split(",") if value.strip()])
    return FHEParams(
        poly_modulus_degree=1 << int(log_n.group(1)),
        coeff_modulus_num_primes=q_count + p_count,
    )


def instrument_go_source(source: str) -> str:
    imports = re.search(r"import\s*\((.*?)\)", source, flags=re.DOTALL)
    if not imports:
        raise ValueError("Expected parenthesized Go imports in compiler output")
    import_block = imports.group(1)
    for package in ('"os"', '"runtime"', '"strings"'):
        if package not in import_block:
            import_block += f"\n\t{package}"
    source = source[: imports.start(1)] + import_block + source[imports.end(1) :]
    helper = r'''
func reportMemoryPhase(name string) {
	status, err := os.ReadFile("/proc/self/status")
	if err != nil {
		panic(err)
	}
	rss, hwm := "unknown", "unknown"
	for _, line := range strings.Split(string(status), "\n") {
		if strings.HasPrefix(line, "VmRSS:") {
			rss = strings.TrimSpace(strings.TrimPrefix(line, "VmRSS:"))
		}
		if strings.HasPrefix(line, "VmHWM:") {
			hwm = strings.TrimSpace(strings.TrimPrefix(line, "VmHWM:"))
		}
	}
	var stats runtime.MemStats
	runtime.ReadMemStats(&stats)
	fmt.Printf("MEM_PHASE %s vmrss=%s vmhwm=%s heap_alloc=%d heap_sys=%d\n",
		name, rss, hwm, stats.HeapAlloc, stats.HeapSys)
}
'''
    main_start = source.find("func main() {")
    if main_start < 0:
        raise ValueError("Generated source has no main function")
    source = source[:main_start] + helper + "\n" + source[main_start:]
    source = source.replace(
        "func main() {", "func main() {\n\treportMemoryPhase(\"baseline\")", 1
    )
    keys_anchor = "// Encoder, Encryptor, Decryptor, Evaluator"
    inputs_anchor = "// Run computation"
    if source.count(keys_anchor) != 1 or source.count(inputs_anchor) != 1:
        raise ValueError("Generated main has unexpected key/input section markers")
    source = source.replace(
        keys_anchor, 'reportMemoryPhase("keys")\n\t' + keys_anchor, 1
    )
    source = source.replace(
        inputs_anchor, 'reportMemoryPhase("inputs")\n\t' + inputs_anchor, 1
    )
    plain_labels = sorted(
        set(re.findall(r'encodedInputs\["([^"]+)"\]', source))
    )
    if plain_labels:
        encoded_lines = []
        for index, label in enumerate(plain_labels):
            encoded_lines.extend(
                [
                    f'\tif encodedInputs["{label}"] == nil {{',
                    f"\t\tplainInput{index} := hefloat.NewPlaintext(params, params.MaxLevel())",
                    "\t\tplainValues := make([]float64, params.MaxSlots())",
                    "\t\tfor i := range plainValues { plainValues[i] = 1.0 }",
                    f"\t\tif err := encoder.Encode(plainValues, plainInput{index}); err != nil {{ panic(err) }}",
                    f'\t\tencodedInputs["{label}"] = plainInput{index}',
                    "\t}",
                ]
            )
        source = source.replace(
            'reportMemoryPhase("inputs")',
            'reportMemoryPhase("inputs")\n' + "\n".join(encoded_lines),
            1,
        )
    source = re.sub(
        r"eval\.NegNew\(([^)]+)\)",
        r"eval.MulNew(\1, -1.0)",
        source,
    )
    eval_elapsed = re.search(
        r"(^\s*elapsed := time\.Since\(t\)\.Seconds\(\) \* 1000\.0\s*$)",
        source,
        flags=re.MULTILINE,
    )
    if not eval_elapsed:
        raise ValueError("Generated main has no evaluation completion marker")
    line = eval_elapsed.group(1)
    source = source.replace(line, line + '\n\treportMemoryPhase("evaluation")', 1)
    return source


def parse_phases(stderr: str):
    found = {}
    pattern = re.compile(
        r"MEM_PHASE (baseline|keys|inputs|evaluation) "
        r"vmrss=(\d+) kB vmhwm=(\d+) kB heap_alloc=(\d+) heap_sys=(\d+)"
    )
    for phase, rss, hwm, alloc, heap_sys in pattern.findall(stderr):
        found[phase] = {
            "rss_kib": int(rss),
            "hwm_kib": int(hwm),
            "heap_alloc": int(alloc),
            "heap_sys": int(heap_sys),
        }
    if set(found) != set(PHASE_NAMES):
        raise ValueError(f"Missing memory phase snapshots: {sorted(found)}")
    return found


def phase_rss_summary(runs):
    summary = {}
    for phase in PHASE_NAMES:
        values = [
            run["Phases"][phase]["rss_kib"] / 1024
            for run in runs
        ]
        label = phase.capitalize()
        summary[f"{label} RSS Median (MiB)"] = statistics.median(values)
        summary[f"{label} RSS Min (MiB)"] = min(values)
        summary[f"{label} RSS Max (MiB)"] = max(values)
    return summary


def candidate_cases(benchmark: str, requested_widths):
    if benchmark == "conv2d":
        return [
            (width, "compiler-native")
            for width in requested_widths
            if width <= 16
        ]
    if benchmark == "deep_network":
        return [
            (depth, "deep-poly") for depth in (3, 5, 8)
        ] + [
            (size, "deep-conv") for size in (3, 4, 8)
        ] + [
            (size, "deep-linear") for size in (2, 4, 8)
        ]
    return [
        (width, form)
        for width in requested_widths
        for form in ("scalar", "vectorized")
        if width <= 16 or (
            width == 32 and benchmark in EXTENDED_WIDTH_BENCHMARKS
        )
    ]


def holdout_benchmarks(benchmarks):
    return {
        benchmark
        for index, benchmark in enumerate(sorted(BENCHMARKS), start=1)
        if index % 4 == 0 and benchmark in benchmarks
    }


def command_for(benchmark: str, binary: Path, width: int, vectorization: str):
    if benchmark == "conv2d":
        return [str(binary), "1", str(width), "3", "1", "0"]
    if benchmark == "deep_network":
        if vectorization == "deep-poly":
            return [str(binary), "polynomial", str(width)]
        if vectorization == "deep-conv":
            return [str(binary), "conv", str(width), "3", "1"]
        if vectorization == "deep-linear":
            return [str(binary), "linear", str(width), "2"]
    return [
        str(binary),
        "1" if vectorization == "vectorized" else "0",
        str(width),
        "constrained",
        "0",
        "0",
        "0",
        "1",
        "1",
        "1",
    ]


def prepare_benchmark(benchmark: str, width: int, vectorization: str, working_directory: Path):
    build_directory = BUILD_BENCHMARKS / benchmark
    binary = build_directory / benchmark
    if not binary.is_file():
        raise FileNotFoundError(f"Built benchmark binary missing: {binary}")
    shutil.copytree(
        build_directory,
        working_directory,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(
            "he/build", "solutions", "CMakeFiles", "generated_*.go"
        ),
    )
    generator = working_directory / f"generate_{benchmark}.py"
    if generator.is_file():
        subprocess.run(
            ["python3", generator.name, "--slot_count", str(width)],
            cwd=working_directory,
            check=True,
            capture_output=True,
            text=True,
            timeout=180,
        )
    subprocess.run(
        command_for(benchmark, working_directory / benchmark, width, vectorization),
        cwd=working_directory,
        check=True,
        capture_output=True,
        text=True,
        timeout=COMPILER_TIMEOUT_SECONDS,
    )
    generated_name = "generated_fhe.go"
    if benchmark == "conv2d":
        generated_name = "generated_conv2d.go"
    elif benchmark == "deep_network":
        generated_name = {
            "deep-poly": "generated_deep_poly.go",
            "deep-conv": "generated_deep_conv.go",
            "deep-linear": "generated_deep_linear.go",
        }[vectorization]
    generated = working_directory / generated_name
    if not generated.is_file():
        raise FileNotFoundError(f"CHEHAB compiler did not emit {generated_name}")
    return generated


def measure_program(benchmark: str, width: int, vectorization: str, repeat_count: int):
    with tempfile.TemporaryDirectory(
        prefix=f"chehab-{benchmark}-{width}-{vectorization}-",
        dir=BUILD_BENCHMARKS,
    ) as temporary_directory:
        working_directory = Path(temporary_directory)
        generated = prepare_benchmark(
            benchmark, width, vectorization, working_directory
        )
        generated_source = generated.read_text()
        ast = parse_compiler_program(generated_source)
        params = parse_parameters(generated_source)
        estimate = estimate_peak_ram(
            ast, params, backend_config=LATTIGO_CONFIG
        )
        instrumented = instrument_go_source(generated_source)
        instrumented_path = working_directory / "instrumented_fhe.go"
        instrumented_path.write_text(instrumented)
        executable = working_directory / "compiled_fhe"
        subprocess.run(
            [
                "go",
                "build",
                "-mod=readonly",
                "-o",
                str(executable),
                str(instrumented_path),
            ],
            cwd=LATTIGO_DIR,
            check=True,
            capture_output=True,
            text=True,
            timeout=BUILD_TIMEOUT_SECONDS,
        )

        runs = []
        for repeat in range(1, repeat_count + 1):
            measured = subprocess.run(
                ["/usr/bin/time", "-f", "peak_rss_kib=%M", str(executable)],
                cwd=working_directory,
                env={**os.environ, "GOGC": "100"},
                check=True,
                capture_output=True,
                text=True,
                timeout=RUN_TIMEOUT_SECONDS,
            )
            phases = parse_phases(measured.stdout)
            peak = re.search(r"peak_rss_kib=(\d+)", measured.stderr)
            if not peak:
                raise RuntimeError("Missing /usr/bin/time peak RSS measurement")
            runs.append(
                {
                    "Repeat": repeat,
                    "Peak RSS (MiB)": int(peak.group(1)) / 1024,
                    "Phases": phases,
                }
            )
        return params, estimate, runs


def rank_pairwise_accuracy(rows):
    concordant = total = 0
    grouped = {}
    for row in rows:
        grouped.setdefault(row["Benchmark"], []).append(row)
    for candidates in grouped.values():
        for index, left in enumerate(candidates):
            for right in candidates[index + 1 :]:
                actual_difference = (
                    left["Median RSS (MiB)"] - right["Median RSS (MiB)"]
                )
                estimated_difference = (
                    left["Estimated Lo (MiB)"] - right["Estimated Lo (MiB)"]
                )
                if actual_difference == 0 or estimated_difference == 0:
                    continue
                total += 1
                concordant += actual_difference * estimated_difference > 0
    return concordant / total if total else float("nan"), total


def rank_values(values):
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and ordered[end][1] == ordered[index][1]:
            end += 1
        average_rank = (index + 1 + end) / 2
        for position in range(index, end):
            ranks[ordered[position][0]] = average_rank
        index = end
    return ranks


def spearman_rank_correlation(rows):
    grouped = {}
    for row in rows:
        grouped.setdefault(row["Benchmark"], []).append(row)
    correlations = []
    for candidates in grouped.values():
        if len(candidates) < 2:
            continue
        estimated = rank_values(
            [row["Estimated Lo (MiB)"] for row in candidates]
        )
        measured = rank_values(
            [row["Median RSS (MiB)"] for row in candidates]
        )
        estimated_mean = statistics.mean(estimated)
        measured_mean = statistics.mean(measured)
        covariance = sum(
            (left - estimated_mean) * (right - measured_mean)
            for left, right in zip(estimated, measured)
        )
        estimated_ss = sum((value - estimated_mean) ** 2 for value in estimated)
        measured_ss = sum((value - measured_mean) ** 2 for value in measured)
        if estimated_ss and measured_ss:
            correlations.append(covariance / (estimated_ss * measured_ss) ** 0.5)
    return statistics.mean(correlations) if correlations else float("nan")


def evaluation_metrics(rows):
    if not rows:
        return []
    signed_errors = [row["Signed Lo Error (%)"] for row in rows]
    absolute_errors = [abs(error) for error in signed_errors]
    rho, ranked_pairs = rank_pairwise_accuracy(rows)
    metrics = [
        ("program_count", len(rows)),
        ("interval_coverage", sum(row["In Interval"] for row in rows) / len(rows)),
        ("median_absolute_error_mib", statistics.median(
            abs(row["Estimated Lo (MiB)"] - row["Median RSS (MiB)"])
            for row in rows
        )),
        ("median_absolute_percentage_error", statistics.median(absolute_errors)),
        ("mean_signed_lo_error_percent", statistics.mean(signed_errors)),
        ("mean_within_benchmark_spearman", spearman_rank_correlation(rows)),
        ("within_benchmark_pairwise_rank_accuracy", rho),
        ("ranked_pair_count", ranked_pairs),
    ]
    for budget in (64, 256, 1024):
        false_accepts = false_rejects = measured_fit_count = 0
        for row in rows:
            estimate_fits = row["Estimated Hi (MiB)"] <= budget
            measured_fits = row["Median RSS (MiB)"] <= budget
            false_accepts += estimate_fits and not measured_fits
            false_rejects += not estimate_fits and measured_fits
            measured_fit_count += measured_fits
        metrics.extend(
            [
                (f"false_accept_count_at_{budget}_mib", false_accepts),
                (f"measured_fit_count_at_{budget}_mib", measured_fit_count),
                (
                    f"false_reject_rate_at_{budget}_mib",
                    false_rejects / measured_fit_count
                    if measured_fit_count
                    else float("nan"),
                ),
            ]
        )
    return metrics


def main():
    parser = argparse.ArgumentParser(
        description="Compile and repeatedly measure CHEHAB benchmark programs."
    )
    parser.add_argument("--benchmarks", nargs="+", default=BENCHMARKS)
    parser.add_argument("--widths", nargs="+", type=int, default=WIDTHS)
    parser.add_argument("--repeats", type=int, default=REPEATS)
    parser.add_argument("--raw-output", type=Path, default=DEFAULT_RAW_OUTPUT)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY_OUTPUT)
    parser.add_argument("--metrics-output", type=Path, default=DEFAULT_METRICS_OUTPUT)
    parser.add_argument("--failures-output", type=Path, default=DEFAULT_FAILURES_OUTPUT)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")

    # Hold out every fourth benchmark from the fixed sorted corpus before
    # collecting new results. No coefficients are fit by this runner.
    ordered_benchmarks = sorted(args.benchmarks)
    unknown_benchmarks = sorted(set(ordered_benchmarks) - set(BENCHMARKS))
    if unknown_benchmarks:
        parser.error(f"Unknown benchmark(s): {', '.join(unknown_benchmarks)}")
    holdout = holdout_benchmarks(ordered_benchmarks)
    raw_rows, summary_rows, failures = [], [], []
    def persist_results():
        if raw_rows:
            args.raw_output.parent.mkdir(parents=True, exist_ok=True)
            with args.raw_output.open("w", newline="") as output:
                writer = csv.DictWriter(
                    output, fieldnames=list(raw_rows[0]), lineterminator="\n"
                )
                writer.writeheader()
                writer.writerows(raw_rows)
        if summary_rows:
            args.summary_output.parent.mkdir(parents=True, exist_ok=True)
            with args.summary_output.open("w", newline="") as output:
                writer = csv.DictWriter(
                    output,
                    fieldnames=list(summary_rows[0]),
                    lineterminator="\n",
                )
                writer.writeheader()
                writer.writerows(summary_rows)
        if failures:
            args.failures_output.parent.mkdir(parents=True, exist_ok=True)
            with args.failures_output.open("w", newline="") as output:
                writer = csv.DictWriter(
                    output,
                    fieldnames=("Program", "Error"),
                    lineterminator="\n",
                )
                writer.writeheader()
                writer.writerows(failures)
        metric_rows = []
        for split in ("development", "holdout"):
            split_rows = [row for row in summary_rows if row["Split"] == split]
            for metric, value in evaluation_metrics(split_rows):
                metric_rows.append(
                    {"Split": split, "Metric": metric, "Value": value}
                )
        args.metrics_output.parent.mkdir(parents=True, exist_ok=True)
        with args.metrics_output.open("w", newline="") as output:
            writer = csv.DictWriter(
                output,
                fieldnames=("Split", "Metric", "Value"),
                lineterminator="\n",
            )
            writer.writeheader()
            writer.writerows(metric_rows)

    for benchmark in ordered_benchmarks:
        candidates = candidate_cases(benchmark, args.widths)
        for width, vectorization in candidates:
            key = f"{benchmark}/width={width}/{vectorization}"
            print(f"Measuring {key}", flush=True)
            try:
                params, estimate, runs = measure_program(
                    benchmark, width, vectorization, args.repeats
                )
                actuals = [run["Peak RSS (MiB)"] for run in runs]
                median_actual = statistics.median(actuals)
                median_lo = estimate.estimated_bytes_lo / 2**20
                median_hi = estimate.estimated_bytes_hi / 2**20
                signed_error = (median_lo - median_actual) / median_actual * 100
                row = {
                    "Benchmark": benchmark,
                    "Width": width,
                    "Vectorization": vectorization,
                    "N": params.poly_modulus_degree,
                    "L": params.coeff_modulus_num_primes,
                    "Split": "holdout" if benchmark in holdout else "development",
                    "Estimated Lo (MiB)": median_lo,
                    "Estimated Hi (MiB)": median_hi,
                    "Median RSS (MiB)": median_actual,
                    "Min RSS (MiB)": min(actuals),
                    "Max RSS (MiB)": max(actuals),
                    "Signed Lo Error (%)": signed_error,
                    "In Interval": median_lo <= median_actual <= median_hi,
                    "Repeat Count": len(runs),
                }
                row.update(phase_rss_summary(runs))
                summary_rows.append(row)
                for run in runs:
                    phase_row = {
                        "Benchmark": benchmark,
                        "Width": width,
                        "Vectorization": vectorization,
                        "N": params.poly_modulus_degree,
                        "L": params.coeff_modulus_num_primes,
                        "Split": row["Split"],
                        "Repeat": run["Repeat"],
                        "Peak RSS (MiB)": run["Peak RSS (MiB)"],
                    }
                    for phase, values in run["Phases"].items():
                        phase_row[f"{phase} RSS (MiB)"] = values["rss_kib"] / 1024
                        phase_row[f"{phase} HWM (MiB)"] = values["hwm_kib"] / 1024
                        phase_row[f"{phase} Heap Alloc (MiB)"] = (
                            values["heap_alloc"] / 2**20
                        )
                        phase_row[f"{phase} Heap Sys (MiB)"] = (
                            values["heap_sys"] / 2**20
                        )
                    raw_rows.append(phase_row)
            except Exception as error:
                detail = str(error)
                if isinstance(error, subprocess.CalledProcessError):
                    detail = (
                        f"{detail}\nstdout: {error.stdout}\nstderr: {error.stderr}"
                    )
                failures.append({"Program": key, "Error": detail})
                print(f"FAILED {key}: {error}", flush=True)
            persist_results()
    persist_results()
    print(
        f"Completed {len(summary_rows)} programs, "
        f"{len(raw_rows)} repeated runs, {len(failures)} failures."
    )
    print(f"Raw phases: {args.raw_output}")
    print(f"Summary: {args.summary_output}")
    print(f"Metrics: {args.metrics_output}")
    print(f"Failures: {args.failures_output}")
    for split in ("development", "holdout"):
        values = dict(
            (metric, value)
            for metric, value in evaluation_metrics(
                [row for row in summary_rows if row["Split"] == split]
            )
        )
        if values:
            print(
                f"{split}: coverage={values['interval_coverage']:.3f}, "
                f"median_APE={values['median_absolute_percentage_error']:.2f}%, "
                f"signed_lo_bias={values['mean_signed_lo_error_percent']:.2f}%, "
                "mean_within_benchmark_spearman="
                f"{values['mean_within_benchmark_spearman']:.3f}, "
                "pairwise_rank_accuracy="
                f"{values['within_benchmark_pairwise_rank_accuracy']:.3f}"
            )
    if failures:
        print("Failures:")
        for failure in failures:
            print(f"  {failure['Program']}: {failure['Error']}")


if __name__ == "__main__":
    main()
