import os
import sys
import unittest

rl_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "RL"))
if rl_dir not in sys.path:
    sys.path.append(rl_dir)

from pytrs.expr import Op, Var
from validate_benchmark_corpus import (
    BENCHMARKS,
    candidate_cases,
    evaluation_metrics,
    holdout_benchmarks,
    WIDTHS,
    parse_compiler_program,
    rank_pairwise_accuracy,
    spearman_rank_correlation,
    instrument_go_source,
    phase_rss_summary,
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

    def test_instrumentation_records_phases_and_repairs_plaintext_inputs(self):
        source = '''package main
import (
    "fmt"
)
func main() {
    encodedInputs := map[string]*Plaintext{}
    input := encodedInputs["weight"]
    // Encoder, Encryptor, Decryptor, Evaluator
    // Run computation
    elapsed := time.Since(t).Seconds() * 1000.0
}
'''
        instrumented = instrument_go_source(source)

        for phase in ("baseline", "keys", "inputs", "evaluation"):
            self.assertIn(f'reportMemoryPhase("{phase}")', instrumented)
        self.assertIn('if encodedInputs["weight"] == nil', instrumented)

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
        full_holdout = holdout_benchmarks(BENCHMARKS)
        partial_holdout = holdout_benchmarks(("deep_network", "dot_product"))

        self.assertEqual(full_holdout.intersection(partial_holdout), partial_holdout)

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
                    phase: {"rss_kib": value}
                    for phase, value in zip(
                        ("baseline", "keys", "inputs", "evaluation"),
                        (1024, 2048, 3072, 4096),
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

    def test_false_reject_rate_uses_measured_fitting_programs_as_denominator(self):
        rows = [
            {
                "Benchmark": "dot_product",
                "Signed Lo Error (%)": -10.0,
                "In Interval": True,
                "Estimated Lo (MiB)": 8.0,
                "Estimated Hi (MiB)": high,
                "Median RSS (MiB)": actual,
            }
            for high, actual in ((80.0, 10.0), (20.0, 20.0))
        ]

        metrics = dict(evaluation_metrics(rows))

        self.assertEqual(metrics["false_reject_rate_at_64_mib"], 0.5)
        self.assertEqual(metrics["measured_fit_count_at_64_mib"], 2)
        self.assertEqual(metrics["false_accept_count_at_64_mib"], 0)


if __name__ == "__main__":
    unittest.main()
