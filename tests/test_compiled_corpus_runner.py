import os
import sys
import unittest

rl_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "RL"))
if rl_dir not in sys.path:
    sys.path.append(rl_dir)

from pytrs.expr import Op, Var
from validate_benchmark_corpus import (
    BENCHMARKS,
    benchmark_metrics,
    benchmarks_for_split,
    candidate_cases,
    development_gc_headroom_factor,
    evaluation_metrics,
    holdout_benchmarks,
    leave_one_benchmark_out_calibration,
    WIDTHS,
    parse_compiler_program,
    rank_pairwise_accuracy,
    spearman_rank_correlation,
    instrument_go_source,
    parse_phases,
    phase_rss_summary,
    save_generated_source,
)


class TestCompiledCorpusRunner(unittest.TestCase):
    def test_parser_preserves_generated_unary_negation(self):
        source = """
x := encryptedInputs["x"]
p := encodedInputs["weight"]
y, _ = eval.NegNew(x)
encryptedOutputs["result"] = y
"""
        expression = parse_compiler_program(source)

        self.assertIsInstance(expression, Op)
        self.assertEqual(expression.op, "-")
        self.assertEqual(expression.args[0].value, 0)
        self.assertEqual(expression.args[1], Var("x"))

    def test_parser_keeps_every_generated_ciphertext_output(self):
        source = """
x := encryptedInputs["x"]
a, _ = eval.AddNew(x, x)
b, _ = eval.MulNew(x, 2)
encryptedOutputs["a"] = a
encryptedOutputs["b"] = b
"""
        expression = parse_compiler_program(source)

        self.assertEqual(expression.op, "Vec")
        self.assertEqual(len(expression.args), 2)
        self.assertEqual([output.op for output in expression.args], ["+", "*"])

    def test_parser_preserves_ssa_values_when_names_are_reused(self):
        source = """
x := encryptedInputs["a"]
y := encryptedInputs["b"]
z, _ = eval.NegNew(x)
w, _ = eval.MulNew(x, y)
encryptedOutputs["o"] = w
"""
        expression = parse_compiler_program(source)

        self.assertEqual(expression.op, "*")
        self.assertEqual(expression.args[0], Var("a"))
        self.assertEqual(expression.args[1], Var("b"))

    def test_saved_generated_source_records_sha256_and_manifest(self):
        import hashlib
        import tempfile
        from pathlib import Path

        source = "package main\nfunc main() {}\n"
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            saved, digest = save_generated_source(
                "dot_product", 4, "vectorized", source,
                output_dir=root / "sources",
            )

            self.assertTrue(saved.is_file())
            self.assertEqual(saved.read_bytes(), source.encode())
            self.assertEqual(
                digest, hashlib.sha256(source.encode()).hexdigest()
            )
            manifest = root / "compiled_corpus_generated_sources_manifest.csv"
            self.assertTrue(manifest.is_file())
            manifest_text = manifest.read_text()
            self.assertIn(digest, manifest_text)
            self.assertIn("dot_product", manifest_text)

    def test_instrumentation_records_phases_and_repairs_plaintext_inputs(self):
        source = '''package main
import (
    "fmt"
)
func main() {
    // Key Generation
    // Encoder, Encryptor, Decryptor, Evaluator
    // Input/Output maps
    encodedInputs := map[string]*Plaintext{}
    encodedOutputs := map[string]*Plaintext{}
    input := encodedInputs["weight"]
    // Run computation
    elapsed := time.Since(t).Seconds() * 1000.0
    for range encryptedOutputs {}
	_ = encodedOutputs
}
'''
        instrumented = instrument_go_source(source)

        for phase in (
            "baseline",
            "parameters",
            "keys",
            "helpers",
            "inputs",
            "evaluation",
            "postprocess",
        ):
            self.assertIn(f'reportMemoryPhase("{phase}")', instrumented)
        self.assertIn('if encodedInputs["weight"] == nil', instrumented)
        self.assertLess(
            instrumented.index('encodedInputs["weight"] = plainInput0'),
            instrumented.index('reportMemoryPhase("inputs")'),
        )
        for stat in ("HeapInuse", "NumGC", "TotalAlloc"):
            self.assertIn(f"stats.{stat}", instrumented)

    def test_phase_parser_reads_heap_inuse_gc_count_and_total_alloc(self):
        sample = "\n".join(
            f"MEM_PHASE {phase} vmrss=1024 kB vmhwm=2048 kB "
            "heap_alloc=10 heap_inuse=20 heap_sys=30 num_gc=4 total_alloc=50"
            for phase in (
                "baseline",
                "parameters",
                "keys",
                "helpers",
                "inputs",
                "evaluation",
                "postprocess",
            )
        )

        parsed = parse_phases(sample)

        self.assertEqual(parsed["keys"]["heap_inuse"], 20)
        self.assertEqual(parsed["inputs"]["num_gc"], 4)
        self.assertEqual(parsed["evaluation"]["total_alloc"], 50)

    def test_deep_network_cases_are_native_and_conv_sizes_are_valid(self):
        cases = candidate_cases("deep_network", (4,))

        self.assertIn((3, "deep-poly"), cases)
        self.assertIn((3, "deep-conv"), cases)
        self.assertIn((2, "deep-linear"), cases)
        self.assertNotIn((2, "deep-conv"), cases)

    def test_default_corpus_has_more_than_one_hundred_candidates(self):
        count = sum(
            len(candidate_cases(benchmark, WIDTHS))
            for benchmark in BENCHMARKS
        )

        self.assertEqual(count, 108)

    def test_holdout_assignment_is_stable_for_partial_runs(self):
        self.assertEqual(
            benchmarks_for_split(("deep_network", "dot_product"), "development"),
            ["deep_network", "dot_product"],
        )
        self.assertEqual(
            benchmarks_for_split(("hamming_dist", "sobel"), "holdout"),
            ["hamming_dist", "sobel"],
        )
        self.assertEqual(
            benchmarks_for_split(("deep_network", "hamming_dist"), "development"),
            ["deep_network"],
        )

    def test_partial_development_results_are_labeled_as_development(self):
        development = benchmarks_for_split(("matrix_mul",), "development")
        self.assertEqual(development, ["matrix_mul"])
        self.assertNotIn("matrix_mul", holdout_benchmarks(BENCHMARKS))

    def test_lobo_calibration_excludes_the_test_benchmark(self):
        rows = [
            {
                "Benchmark": benchmark,
                "Split": "development",
                "GOGC": "100",
                "Estimated Base (MiB)": 8.0,
                "Estimated Managed Live (MiB)": live,
                "Estimated Lo (MiB)": 8.0 + live,
                "Median RSS (MiB)": 8.0 + live * (1.0 + ratio),
            }
            for benchmark, live, ratio in (
                ("a", 10.0, 0.2),
                ("b", 10.0, 0.4),
                ("c", 10.0, 1.0),
            )
        ]

        results = leave_one_benchmark_out_calibration(rows)
        by_benchmark = {row["Benchmark"]: row for row in results}
        self.assertEqual(by_benchmark["a"]["Training Program Count"], 2)
        self.assertAlmostEqual(
            by_benchmark["a"]["Training P95 GC Headroom Factor"],
            0.97,
        )
        self.assertEqual(by_benchmark["c"]["Interval Coverage"], 0.0)
        holdout_row = {
            **rows[0],
            "Benchmark": "holdout",
            "Split": "holdout",
            "Median RSS (MiB)": 108.0,
        }
        self.assertAlmostEqual(
            development_gc_headroom_factor(rows + [holdout_row]),
            0.94,
        )
        below_lo_rows = [
            {
                "Benchmark": "small",
                "Split": "development",
                "GOGC": "100",
                "Estimated Base (MiB)": 8.0,
                "Estimated Managed Live (MiB)": 10.0,
                "Median RSS (MiB)": 10.0,
            }
        ]
        self.assertEqual(development_gc_headroom_factor(below_lo_rows), 0.0)

    def test_ranking_metrics_report_spearman_and_pairwise_agreement(self):
        rows = [
            {"Benchmark": "dot_product", "Estimated Lo (MiB)": estimate,
             "Median RSS (MiB)": actual}
            for estimate, actual in ((1.0, 2.0), (2.0, 3.0), (3.0, 4.0))
        ]

        self.assertEqual(spearman_rank_correlation(rows), 1.0)
        self.assertEqual(rank_pairwise_accuracy(rows), (1.0, 3))

    def test_phase_rss_summary_reports_median_and_spread(self):
        runs = [
            {
                "Phases": {
                    phase: {
                        "rss_kib": value,
                        "heap_inuse": value * 2 * 1024,
                        "total_alloc": value * 3 * 1024,
                        "num_gc": value // 512,
                    }
                    for phase, value in zip(
                        (
                            "baseline",
                            "parameters",
                            "keys",
                            "helpers",
                            "inputs",
                            "evaluation",
                            "postprocess",
                        ),
                        (1024, 1536, 2048, 2560, 3072, 4096, 5120),
                    )
                }
            }
            for _ in range(3)
        ]
        runs[0]["Phases"]["baseline"]["rss_kib"] = 512
        runs[2]["Phases"]["baseline"]["rss_kib"] = 1536

        summary = phase_rss_summary(runs)

        self.assertEqual(summary["Baseline RSS Median (MiB)"], 1.0)
        self.assertEqual(summary["Baseline RSS Min (MiB)"], 0.5)
        self.assertEqual(summary["Baseline RSS Max (MiB)"], 1.5)
        self.assertEqual(
            summary["Baseline To Parameters RSS Delta Median (MiB)"], 0.5
        )
        self.assertEqual(
            summary["Baseline To Parameters Heap Inuse Delta Median (MiB)"],
            1.0,
        )
        self.assertEqual(summary["Keys NumGC Median"], 4)

    def test_false_reject_rate_uses_measured_fitting_programs_as_denominator(self):
        rows = [
            {
                "Benchmark": "dot_product",
                "Signed Lo Error (%)": -10.0,
                "In Interval": True,
                "Estimated Lo (MiB)": 8.0,
                "Estimated Hi (MiB)": high,
                "V1 Signed Lo Error (%)": -10.0,
                "V1 In Interval": True,
                "V1 Estimated Lo (MiB)": 8.0,
                "V1 Estimated Hi (MiB)": high,
                "Median RSS (MiB)": actual,
            }
            for high, actual in ((80.0, 10.0), (20.0, 20.0))
        ]

        metrics = dict(evaluation_metrics(rows))

        self.assertEqual(metrics["false_reject_rate_at_64_mib"], 0.5)
        self.assertEqual(metrics["false_reject_count_at_64_mib"], 1)
        self.assertEqual(metrics["measured_fit_count_at_64_mib"], 2)
        self.assertEqual(metrics["false_accept_count_at_64_mib"], 0)
        self.assertEqual(
            dict(evaluation_metrics(rows, model_version="v1"))[
                "interval_coverage"
            ],
            1.0,
        )

    def test_benchmark_metrics_report_signed_and_absolute_error_spread(self):
        rows = [
            {
                "Benchmark": "dot_product",
                "Signed Lo Error (%)": -20.0,
                "In Interval": True,
            },
            {
                "Benchmark": "dot_product",
                "Signed Lo Error (%)": 10.0,
                "In Interval": False,
            },
        ]

        result = benchmark_metrics(rows)[0]

        self.assertEqual(result["Program Count"], 2)
        self.assertEqual(result["Interval Coverage"], 0.5)
        self.assertEqual(result["Median Absolute Percentage Error"], 15.0)
        self.assertEqual(result["Min Signed Lo Error (%)"], -20.0)
        self.assertEqual(result["Max Signed Lo Error (%)"], 10.0)

    def test_metrics_accept_csv_string_rows(self):
        rows = [
            {
                "Benchmark": "dot_product",
                "Signed Lo Error (%)": "-10.0",
                "In Interval": "True",
                "Estimated Lo (MiB)": "8.0",
                "Estimated Hi (MiB)": "20.0",
                "V1 Signed Lo Error (%)": "-20.0",
                "V1 In Interval": "False",
                "V1 Estimated Lo (MiB)": "7.0",
                "V1 Estimated Hi (MiB)": "21.0",
                "Median RSS (MiB)": "10.0",
            },
            {
                "Benchmark": "dot_product",
                "Signed Lo Error (%)": "5.0",
                "In Interval": "False",
                "Estimated Lo (MiB)": "12.0",
                "Estimated Hi (MiB)": "80.0",
                "V1 Signed Lo Error (%)": "1.0",
                "V1 In Interval": "True",
                "V1 Estimated Lo (MiB)": "11.0",
                "V1 Estimated Hi (MiB)": "40.0",
                "Median RSS (MiB)": "11.0",
            },
        ]

        metrics = dict(evaluation_metrics(rows))
        by_benchmark = benchmark_metrics(rows)[0]

        self.assertEqual(metrics["interval_coverage"], 0.5)
        self.assertEqual(metrics["false_reject_count_at_64_mib"], 1)
        self.assertEqual(metrics["ranked_pair_count"], 1)
        self.assertEqual(by_benchmark["Median Absolute Percentage Error"], 7.5)
        self.assertEqual(
            dict(evaluation_metrics(rows, model_version="v1"))[
                "interval_coverage"
            ],
            0.5,
        )


if __name__ == "__main__":
    unittest.main()
