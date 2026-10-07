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
from pytrs.peak_ram import (
    FHEParams,
    LATTIGO_CONFIG,
    LATTIGO_CONFIG_V1,
    estimate_peak_ram,
)


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
PHASE_NAMES = (
    "baseline",
    "parameters",
    "keys",
    "helpers",
    "inputs",
    "evaluation",
    "postprocess",
)


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
    # Single source-order pass: generated code reuses Go variable names in SSA
    # style, so a destination overwritten by a later op (e.g. NegNew) must not
    # retroactively change an earlier op that already consumed the old value.
    combined_pattern = re.compile(
        r"^\s*(\w+),\s*_\s*=\s*eval\.(MulRelinNew|MulNew|AddNew|SubNew|RotateNew|NegNew)"
        r"\(([^)]+)\)",
        flags=re.MULTILINE,
    )

    def resolve_operand(name: str):
        if name in variables:
            return variables[name]
        try:
            return Const(int(name))
        except ValueError:
            try:
                return Const(float(name))
            except ValueError as error:
                raise ValueError(f"Unknown generated operand: {name}") from error

    for destination, method, args_text in combined_pattern.findall(source):
        if method == "NegNew":
            operand_name = args_text.strip()
            if operand_name not in variables:
                raise ValueError(f"Unknown generated operand: {operand_name}")
            variables[destination] = Op("-", [Const(0), variables[operand_name]])
            continue
        parts = [part.strip() for part in args_text.split(",", 1)]
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise ValueError(f"Unknown generated operand: {args_text.strip()}")
        left_name, right_name = parts
        if left_name not in variables:
            raise ValueError(f"Unknown generated operand: {left_name}")
        variables[destination] = Op(
            operations[method], [variables[left_name], resolve_operand(right_name)]
        )

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
	fmt.Printf("MEM_PHASE %s vmrss=%s vmhwm=%s heap_alloc=%d heap_inuse=%d heap_sys=%d num_gc=%d total_alloc=%d\n",
		name, rss, hwm, stats.HeapAlloc, stats.HeapInuse, stats.HeapSys,
		stats.NumGC, stats.TotalAlloc)
}
'''
    main_start = source.find("func main() {")
    if main_start < 0:
        raise ValueError("Generated source has no main function")
    source = source[:main_start] + helper + "\n" + source[main_start:]
    source = source.replace(
        "func main() {", "func main() {\n\treportMemoryPhase(\"baseline\")", 1
    )
    parameters_anchor = "// Key Generation"
    keys_anchor = "// Encoder, Encryptor, Decryptor, Evaluator"
    helpers_anchor = "// Input/Output maps"
    inputs_anchor = "// Run computation"
    postprocess_anchor = "\t_ = encodedOutputs"
    anchors = (
        parameters_anchor,
        keys_anchor,
        helpers_anchor,
        inputs_anchor,
        postprocess_anchor,
    )
    if any(source.count(anchor) != 1 for anchor in anchors):
        raise ValueError("Generated main has unexpected key/input section markers")
    source = source.replace(
        parameters_anchor,
        'reportMemoryPhase("parameters")\n\t' + parameters_anchor,
        1,
    )
    source = source.replace(
        keys_anchor, 'reportMemoryPhase("keys")\n\t' + keys_anchor, 1
    )
    source = source.replace(
        helpers_anchor, 'reportMemoryPhase("helpers")\n\t' + helpers_anchor, 1
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
            "\n".join(encoded_lines) + '\n\treportMemoryPhase("inputs")',
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
    source = source.replace(
        postprocess_anchor,
        'reportMemoryPhase("postprocess")\n' + postprocess_anchor,
        1,
    )
    return source


def parse_phases(stderr: str):
    found = {}
    pattern = re.compile(
        rf"MEM_PHASE ({'|'.join(PHASE_NAMES)}) "
        r"vmrss=(\d+) kB vmhwm=(\d+) kB heap_alloc=(\d+) "
        r"heap_inuse=(\d+) heap_sys=(\d+) num_gc=(\d+) total_alloc=(\d+)"
    )
    for phase, rss, hwm, alloc, inuse, heap_sys, num_gc, total_alloc in pattern.findall(stderr):
        found[phase] = {
            "rss_kib": int(rss),
            "hwm_kib": int(hwm),
            "heap_alloc": int(alloc),
            "heap_inuse": int(inuse),
            "heap_sys": int(heap_sys),
            "num_gc": int(num_gc),
            "total_alloc": int(total_alloc),
        }
    if set(found) != set(PHASE_NAMES):
        raise ValueError(f"Missing memory phase snapshots: {sorted(found)}")
    return found


def phase_rss_summary(runs):
    summary = {}
    for phase in PHASE_NAMES:
        label = phase.capitalize()
        values = [run["Phases"][phase]["rss_kib"] / 1024 for run in runs]
        summary[f"{label} RSS Median (MiB)"] = statistics.median(values)
        summary[f"{label} RSS Min (MiB)"] = min(values)
        summary[f"{label} RSS Max (MiB)"] = max(values)
        summary[f"{label} Heap Inuse Median (MiB)"] = statistics.median(
            run["Phases"][phase]["heap_inuse"] / 2**20 for run in runs
        )
        summary[f"{label} Total Alloc Median (MiB)"] = statistics.median(
            run["Phases"][phase]["total_alloc"] / 2**20 for run in runs
        )
        summary[f"{label} NumGC Median"] = statistics.median(
            run["Phases"][phase]["num_gc"] for run in runs
        )
    for before, after in zip(PHASE_NAMES, PHASE_NAMES[1:]):
        deltas = [
            (
                run["Phases"][after]["rss_kib"]
                - run["Phases"][before]["rss_kib"]
            )
            / 1024
            for run in runs
        ]
        summary[
            f"{before.capitalize()} To {after.capitalize()} RSS Delta Median (MiB)"
        ] = statistics.median(deltas)
        for metric, label in (
            ("heap_inuse", "Heap Inuse"),
            ("total_alloc", "Total Alloc"),
        ):
            phase_deltas = [
                (
                    run["Phases"][after][metric]
                    - run["Phases"][before][metric]
                )
                / 2**20
                for run in runs
            ]
            summary[
                f"{before.capitalize()} To {after.capitalize()} "
                f"{label} Delta Median (MiB)"
            ] = statistics.median(phase_deltas)
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


def benchmarks_for_split(benchmarks, split):
    selected = set(benchmarks)
    holdout = holdout_benchmarks(BENCHMARKS)
    if split == "development":
        return sorted(selected - holdout)
    if split == "holdout":
        return sorted(selected & holdout)
    raise ValueError(f"Unknown corpus split: {split}")


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


def measure_program(
    benchmark: str,
    width: int,
    vectorization: str,
    repeat_count: int,
    gogc_values,
):
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
        legacy_estimate = estimate_peak_ram(
            ast, params, backend_config=LATTIGO_CONFIG_V1
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

        runs_by_gogc = {}
        for gogc in gogc_values:
            runs = []
            for repeat in range(1, repeat_count + 1):
                measured = subprocess.run(
                    ["/usr/bin/time", "-f", "peak_rss_kib=%M", str(executable)],
                    cwd=working_directory,
                    env={**os.environ, "GOGC": gogc},
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
                        "GOGC": gogc,
                        "Peak RSS (MiB)": int(peak.group(1)) / 1024,
                        "Phases": phases,
                    }
                )
            runs_by_gogc[gogc] = runs
        return params, estimate, legacy_estimate, runs_by_gogc


def rank_pairwise_accuracy(rows, estimate_column="Estimated Lo (MiB)"):
    concordant = total = 0
    grouped = {}
    for row in rows:
        grouped.setdefault(row["Benchmark"], []).append(row)
    for candidates in grouped.values():
        for index, left in enumerate(candidates):
            for right in candidates[index + 1 :]:
                actual_difference = (
                    numeric_value(left, "Median RSS (MiB)")
                    - numeric_value(right, "Median RSS (MiB)")
                )
                estimated_difference = (
                    numeric_value(left, estimate_column)
                    - numeric_value(right, estimate_column)
                )
                if actual_difference == 0 or estimated_difference == 0:
                    continue
                total += 1
                concordant += actual_difference * estimated_difference > 0
    return concordant / total if total else float("nan"), total


def numeric_value(row, column):
    return float(row[column])


def boolean_value(row, column):
    value = row[column]
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return bool(value)


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


def spearman_rank_correlation(rows, estimate_column="Estimated Lo (MiB)"):
    grouped = {}
    for row in rows:
        grouped.setdefault(row["Benchmark"], []).append(row)
    correlations = []
    for candidates in grouped.values():
        if len(candidates) < 2:
            continue
        estimated = rank_values(
            [numeric_value(row, estimate_column) for row in candidates]
        )
        measured = rank_values(
            [numeric_value(row, "Median RSS (MiB)") for row in candidates]
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


def evaluation_metrics(rows, model_version="v2"):
    if not rows:
        return []
    if model_version == "v1":
        lo_column = "V1 Estimated Lo (MiB)"
        hi_column = "V1 Estimated Hi (MiB)"
        interval_column = "V1 In Interval"
        signed_error_column = "V1 Signed Lo Error (%)"
    else:
        lo_column = "Estimated Lo (MiB)"
        hi_column = "Estimated Hi (MiB)"
        interval_column = "In Interval"
        signed_error_column = "Signed Lo Error (%)"
    signed_errors = [numeric_value(row, signed_error_column) for row in rows]
    absolute_errors = [abs(error) for error in signed_errors]
    rho, ranked_pairs = rank_pairwise_accuracy(rows, lo_column)
    metrics = [
        ("program_count", len(rows)),
        (
            "interval_coverage",
            sum(boolean_value(row, interval_column) for row in rows) / len(rows),
        ),
        ("median_absolute_error_mib", statistics.median(
            abs(
                numeric_value(row, lo_column)
                - numeric_value(row, "Median RSS (MiB)")
            )
            for row in rows
        )),
        ("median_absolute_percentage_error", statistics.median(absolute_errors)),
        ("mean_signed_lo_error_percent", statistics.mean(signed_errors)),
        (
            "mean_within_benchmark_spearman",
            spearman_rank_correlation(rows, lo_column),
        ),
        ("within_benchmark_pairwise_rank_accuracy", rho),
        ("ranked_pair_count", ranked_pairs),
    ]
    for budget in (64, 256, 1024):
        false_accepts = false_rejects = measured_fit_count = 0
        for row in rows:
            estimate_fits = numeric_value(row, hi_column) <= budget
            measured_fits = numeric_value(row, "Median RSS (MiB)") <= budget
            false_accepts += estimate_fits and not measured_fits
            false_rejects += not estimate_fits and measured_fits
            measured_fit_count += measured_fits
        metrics.extend(
            [
                (f"false_accept_count_at_{budget}_mib", false_accepts),
                (f"false_reject_count_at_{budget}_mib", false_rejects),
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


def benchmark_metrics(rows, model_version="v2"):
    if model_version == "v1":
        interval_column = "V1 In Interval"
        signed_error_column = "V1 Signed Lo Error (%)"
    else:
        interval_column = "In Interval"
        signed_error_column = "Signed Lo Error (%)"
    grouped = {}
    for row in rows:
        grouped.setdefault(row["Benchmark"], []).append(row)

    result = []
    for benchmark, candidates in sorted(grouped.items()):
        errors = [numeric_value(row, signed_error_column) for row in candidates]
        absolute_errors = [abs(error) for error in errors]
        result.append(
            {
                "Model": model_version,
                "Benchmark": benchmark,
                "Program Count": len(candidates),
                "Interval Coverage": sum(
                    boolean_value(row, interval_column) for row in candidates
                ) / len(candidates),
                "Median Absolute Percentage Error": statistics.median(
                    absolute_errors
                ),
                "Mean Signed Lo Error (%)": statistics.mean(errors),
                "Min Signed Lo Error (%)": min(errors),
                "Max Signed Lo Error (%)": max(errors),
                "Min Absolute Percentage Error": min(absolute_errors),
                "Max Absolute Percentage Error": max(absolute_errors),
            }
        )
    return result


def interpolated_percentile(values, percentile):
    if not values:
        raise ValueError("percentile requires at least one value")
    if not 0.0 <= percentile <= 1.0:
        raise ValueError("percentile must be between 0 and 1")
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + fraction * (ordered[upper] - ordered[lower])


def gc_headroom_residual_ratios(rows):
    return [
        (
            float(row["Median RSS (MiB)"])
            - float(row["Estimated Base (MiB)"])
            - float(row["Estimated Managed Live (MiB)"])
            - float(
                row.get(
                    "Estimated Input Plaintext Transient (MiB)",
                    float(row.get("Estimated Inputs (MiB)", 0.0)) * 0.5,
                )
            )
        )
        / float(row["Estimated Managed Live (MiB)"])
        for row in rows
        if row["Split"] == "development"
        and str(row["GOGC"]) == "100"
        and float(row["Estimated Managed Live (MiB)"]) > 0
    ]


def development_gc_headroom_factor(rows, percentile=0.95):
    """Select additional GC/RSS headroom after source-derived input plaintexts."""
    return max(
        0.0,
        interpolated_percentile(gc_headroom_residual_ratios(rows), percentile),
    )


def leave_one_benchmark_out_calibration(rows, percentile=0.95):
    """Evaluate GC/RSS headroom while withholding each benchmark in turn."""
    development = [
        row
        for row in rows
        if row["Split"] == "development" and str(row["GOGC"]) == "100"
    ]
    grouped = {}
    for row in development:
        grouped.setdefault(row["Benchmark"], []).append(row)
    results = []
    for benchmark, test_rows in sorted(grouped.items()):
        training_rows = [
            row for row in development if row["Benchmark"] != benchmark
        ]
        ratios = gc_headroom_residual_ratios(training_rows)
        if not ratios:
            continue
        gc_headroom_factor = max(
            0.0, interpolated_percentile(ratios, percentile)
        )
        actuals = [float(row["Median RSS (MiB)"]) for row in test_rows]
        lo_values = [float(row["Estimated Lo (MiB)"]) for row in test_rows]
        hi_values = [
            float(row["Estimated Base (MiB)"])
            + float(row["Estimated Managed Live (MiB)"])
            + float(
                row.get(
                    "Estimated Input Plaintext Transient (MiB)",
                    float(row.get("Estimated Inputs (MiB)", 0.0)) * 0.5,
                )
            )
            + float(row["Estimated Managed Live (MiB)"])
            * gc_headroom_factor
            for row in test_rows
        ]
        signed_errors = [
            (lo - actual) / actual * 100
            for lo, actual in zip(lo_values, actuals)
        ]
        result = {
            "Benchmark": benchmark,
            "Training Program Count": len(training_rows),
            "Test Program Count": len(test_rows),
            "Training P95 GC Headroom Factor": gc_headroom_factor,
            "Interval Coverage": sum(
                lo <= actual <= hi
                for lo, actual, hi in zip(lo_values, actuals, hi_values)
            ) / len(test_rows),
            "Median Absolute Percentage Error": statistics.median(
                abs(error) for error in signed_errors
            ),
            "Mean Signed Lo Error (%)": statistics.mean(signed_errors),
            "Min Signed Lo Error (%)": min(signed_errors),
            "Max Signed Lo Error (%)": max(signed_errors),
            "Min Absolute Percentage Error": min(
                abs(error) for error in signed_errors
            ),
            "Max Absolute Percentage Error": max(
                abs(error) for error in signed_errors
            ),
        }
        for budget in (64, 256, 1024):
            result[f"False Accepts At {budget} MiB"] = sum(
                hi <= budget and actual > budget
                for hi, actual in zip(hi_values, actuals)
            )
            measured_fit = sum(actual <= budget for actual in actuals)
            false_reject = sum(
                hi > budget and actual <= budget
                for hi, actual in zip(hi_values, actuals)
            )
            result[f"False Rejects At {budget} MiB"] = false_reject
            result[f"Measured Fits At {budget} MiB"] = measured_fit
            result[f"False Reject Rate At {budget} MiB"] = (
                false_reject / measured_fit if measured_fit else float("nan")
            )
        results.append(result)
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Compile and repeatedly measure CHEHAB benchmark programs."
    )
    parser.add_argument("--benchmarks", nargs="+", default=BENCHMARKS)
    parser.add_argument("--widths", nargs="+", type=int, default=WIDTHS)
    parser.add_argument("--repeats", type=int, default=REPEATS)
    parser.add_argument(
        "--split", choices=("development", "holdout"), default="development"
    )
    parser.add_argument("--gogc-values", nargs="+", default=("100",))
    parser.add_argument("--raw-output", type=Path, default=DEFAULT_RAW_OUTPUT)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY_OUTPUT)
    parser.add_argument("--metrics-output", type=Path, default=DEFAULT_METRICS_OUTPUT)
    parser.add_argument(
        "--benchmark-metrics-output",
        type=Path,
        default=ROOT / "RL" / "compiled_corpus_benchmark_metrics.csv",
    )
    parser.add_argument("--failures-output", type=Path, default=DEFAULT_FAILURES_OUTPUT)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    invalid_gogc = [
        value
        for value in args.gogc_values
        if value != "off" and (not value.isdigit() or int(value) < 0)
    ]
    if invalid_gogc:
        parser.error(f"invalid GOGC value(s): {', '.join(invalid_gogc)}")

    # Hold out every fourth benchmark from the fixed sorted corpus before
    # collecting new results. No coefficients are fit by this runner.
    selected_benchmarks = sorted(args.benchmarks)
    unknown_benchmarks = sorted(set(selected_benchmarks) - set(BENCHMARKS))
    if unknown_benchmarks:
        parser.error(f"Unknown benchmark(s): {', '.join(unknown_benchmarks)}")
    ordered_benchmarks = benchmarks_for_split(
        selected_benchmarks, args.split
    )
    splits_to_report = (args.split,)
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
        benchmark_metric_rows = []
        for split in splits_to_report:
            split_rows = [row for row in summary_rows if row["Split"] == split]
            for gogc in args.gogc_values:
                gc_rows = [row for row in split_rows if row["GOGC"] == gogc]
                for model_version in ("v1", "v2"):
                    for metric, value in evaluation_metrics(
                        gc_rows, model_version
                    ):
                        metric_rows.append(
                            {
                                "Model": model_version,
                                "Split": split,
                                "GOGC": gogc,
                                "Metric": metric,
                                "Value": value,
                            }
                        )
                    benchmark_metric_rows.extend(
                        {
                            **row,
                            "Split": split,
                            "GOGC": gogc,
                        }
                        for row in benchmark_metrics(gc_rows, model_version)
                    )
        args.metrics_output.parent.mkdir(parents=True, exist_ok=True)
        with args.metrics_output.open("w", newline="") as output:
            writer = csv.DictWriter(
                output,
                fieldnames=("Model", "Split", "GOGC", "Metric", "Value"),
                lineterminator="\n",
            )
            writer.writeheader()
            writer.writerows(metric_rows)
        args.benchmark_metrics_output.parent.mkdir(
            parents=True, exist_ok=True
        )
        with args.benchmark_metrics_output.open("w", newline="") as output:
            writer = csv.DictWriter(
                output,
                fieldnames=(
                    "Model",
                    "Split",
                    "GOGC",
                    "Benchmark",
                    "Program Count",
                    "Interval Coverage",
                    "Median Absolute Percentage Error",
                    "Mean Signed Lo Error (%)",
                    "Min Signed Lo Error (%)",
                    "Max Signed Lo Error (%)",
                    "Min Absolute Percentage Error",
                    "Max Absolute Percentage Error",
                ),
                lineterminator="\n",
            )
            writer.writeheader()
            writer.writerows(benchmark_metric_rows)

    for benchmark in ordered_benchmarks:
        candidates = candidate_cases(benchmark, args.widths)
        for width, vectorization in candidates:
            key = f"{benchmark}/width={width}/{vectorization}"
            print(f"Measuring {key}", flush=True)
            try:
                params, estimate, legacy_estimate, runs_by_gogc = measure_program(
                    benchmark,
                    width,
                    vectorization,
                    args.repeats,
                    args.gogc_values,
                )
                for gogc, runs in runs_by_gogc.items():
                    actuals = [run["Peak RSS (MiB)"] for run in runs]
                    median_actual = statistics.median(actuals)
                    median_lo = estimate.estimated_bytes_lo / 2**20
                    median_hi = estimate.estimated_bytes_hi / 2**20
                    signed_error = (median_lo - median_actual) / median_actual * 100
                    legacy_lo = legacy_estimate.estimated_bytes_lo / 2**20
                    legacy_hi = legacy_estimate.estimated_bytes_hi / 2**20
                    legacy_signed_error = (
                        (legacy_lo - median_actual) / median_actual * 100
                    )
                    row = {
                        "Benchmark": benchmark,
                        "Width": width,
                        "Vectorization": vectorization,
                        "GOGC": gogc,
                        "N": params.poly_modulus_degree,
                        "L": params.coeff_modulus_num_primes,
                        "Split": args.split,
                        "Estimated Base (MiB)": estimate.base_overhead_bytes / 2**20,
                        "Estimated Parameters (MiB)": estimate.parameter_bytes / 2**20,
                        "Estimated Helper Buffers (MiB)": estimate.helper_buffers_bytes / 2**20,
                        "Estimated Rotation Indexes (MiB)": estimate.rotation_index_bytes / 2**20,
                        "Estimated Input Staging (MiB)": estimate.input_staging_bytes / 2**20,
                        "Estimated Postprocess (MiB)": estimate.postprocess_bytes / 2**20,
                        "Estimated Keys (MiB)": estimate.keys_bytes / 2**20,
                        "Keygen Transient (MiB)": estimate.keygen_transient_bytes / 2**20,
                        "Estimated Inputs (MiB)": estimate.inputs_bytes / 2**20,
                        "Estimated Plaintexts (MiB)": estimate.plaintexts_bytes / 2**20,
                        "Estimated Input Plaintext Transient (MiB)": (
                            estimate.input_plaintext_transient_bytes / 2**20
                        ),
                        "Estimated Intermediates (MiB)": estimate.intermediates_bytes / 2**20,
                        "Estimated Managed Live (MiB)": estimate.managed_live_bytes / 2**20,
                        "Estimated GC Growth (MiB)": estimate.high_growth_bytes / 2**20,
                        "Estimated Allocation Budget (MiB)": estimate.allocation_bytes / 2**20,
                        "V1 Garbage Term (MiB)": legacy_estimate.high_growth_bytes / 2**20,
                        "Estimated Lo (MiB)": median_lo,
                        "Estimated Hi (MiB)": median_hi,
                        "V1 Estimated Lo (MiB)": legacy_lo,
                        "V1 Estimated Hi (MiB)": legacy_hi,
                        "Median RSS (MiB)": median_actual,
                        "Min RSS (MiB)": min(actuals),
                        "Max RSS (MiB)": max(actuals),
                        "Signed Lo Error (%)": signed_error,
                        "In Interval": median_lo <= median_actual <= median_hi,
                        "V1 Signed Lo Error (%)": legacy_signed_error,
                        "V1 In Interval": (
                            legacy_lo <= median_actual <= legacy_hi
                        ),
                        "Repeat Count": len(runs),
                    }
                    row.update(phase_rss_summary(runs))
                    summary_rows.append(row)
                    for run in runs:
                        phase_row = {
                            "Benchmark": benchmark,
                            "Width": width,
                            "Vectorization": vectorization,
                            "GOGC": gogc,
                            "N": params.poly_modulus_degree,
                            "L": params.coeff_modulus_num_primes,
                            "Split": row["Split"],
                            "Repeat": run["Repeat"],
                            "Peak RSS (MiB)": run["Peak RSS (MiB)"],
                        }
                        for phase, values in run["Phases"].items():
                            phase_row[f"{phase} RSS (MiB)"] = values["rss_kib"] / 1024
                            phase_row[f"{phase} HWM (MiB)"] = values["hwm_kib"] / 1024
                            phase_row[f"{phase} Heap Alloc (MiB)"] = values["heap_alloc"] / 2**20
                            phase_row[f"{phase} Heap Inuse (MiB)"] = values["heap_inuse"] / 2**20
                            phase_row[f"{phase} Heap Sys (MiB)"] = values["heap_sys"] / 2**20
                            phase_row[f"{phase} NumGC"] = values["num_gc"]
                            phase_row[f"{phase} Total Alloc (MiB)"] = values["total_alloc"] / 2**20
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
    for split in splits_to_report:
        for gogc in args.gogc_values:
            values = dict(
                (metric, value)
                for metric, value in evaluation_metrics(
                    [
                        row
                        for row in summary_rows
                        if row["Split"] == split and row["GOGC"] == gogc
                    ]
                )
            )
            if values:
                print(
                    f"{split} GOGC={gogc}: "
                    f"coverage={values['interval_coverage']:.3f}, "
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
