import os
import sys
import unittest

rl_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'RL'))
if rl_dir not in sys.path:
    sys.path.append(rl_dir)

from generate_sweep_isolated import (
    CSV_FIELDS,
    ast_addition,
    ast_batched_multiplications,
    ast_dot_product,
    metric_columns,
)
from pytrs.peak_ram import FHEParams, estimate_peak_ram


class TestSweepMetrics(unittest.TestCase):
    def test_success_metrics_include_both_estimate_bounds(self):
        metrics = metric_columns("SEAL", 1024**2, 768 * 1024, 1280 * 1024)

        self.assertEqual(metrics["SEAL Actual (MB)"], 1.0)
        self.assertEqual(metrics["SEAL Error Lo (%)"], 25.0)
        self.assertEqual(metrics["SEAL Dir Lo"], "UNDER")
        self.assertEqual(metrics["SEAL Error Hi (%)"], 25.0)
        self.assertEqual(metrics["SEAL Dir Hi"], "OVER")
        self.assertTrue(metrics["SEAL In Bounds"])

    def test_failures_are_not_reported_as_zero_or_success(self):
        metrics = metric_columns("SEAL", -1, 768, 1280)

        self.assertEqual(metrics["SEAL Actual (MB)"], "FAIL")
        self.assertEqual(metrics["SEAL Error Lo (%)"], "FAIL")
        self.assertEqual(metrics["SEAL Dir Hi"], "FAIL")
        self.assertEqual(metrics["SEAL In Bounds"], "FAIL")

    def test_schema_contains_low_high_and_bounds_metrics(self):
        for field in (
            "SEAL Error Hi (%)",
            "SEAL Dir Hi",
            "SEAL In Bounds",
            "Lattigo Error Hi (%)",
            "Lattigo Dir Hi",
            "Lattigo In Bounds",
        ):
            self.assertIn(field, CSV_FIELDS)

    def test_replacement_benchmarks_match_estimator_key_needs(self):
        addition, addition_keys = ast_addition(4)
        batched_multiplications, multiplication_keys = ast_batched_multiplications(3)
        dot_product, dot_product_keys = ast_dot_product(4)

        addition_estimate = estimate_peak_ram(addition, FHEParams())
        multiplication_estimate = estimate_peak_ram(
            batched_multiplications, FHEParams()
        )
        dot_estimate = estimate_peak_ram(dot_product, FHEParams())

        self.assertEqual(addition_keys, 0)
        self.assertEqual(addition_estimate.relin_keys_count, 0)
        self.assertEqual(multiplication_keys, 1)
        self.assertEqual(multiplication_estimate.relin_keys_count, 1)
        self.assertEqual(multiplication_estimate.allocating_ops, 3)
        self.assertEqual(dot_product_keys, 1)
        self.assertEqual(dot_estimate.relin_keys_count, 1)


if __name__ == "__main__":
    unittest.main()
