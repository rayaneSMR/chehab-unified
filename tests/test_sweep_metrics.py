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
    ast_high_churn,
    metric_columns,
    phase_peaks,
)
from pytrs.peak_ram import (
    FHEParams,
    NotEstimable,
    SEAL_CONFIG,
    expand_compiler_vector_ops,
    estimate_peak_ram,
    estimate_vectorized_peak_ram,
    is_fully_vectorized,
)
from pytrs.expr import Const, Op, Var
from pytrs.parser import parse_sexpr
from fhe_rl.memory_layout import key_bytes


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

    def test_zero_increment_is_distinguished_from_worker_failure(self):
        metrics = metric_columns("SEAL", 0, 768, 1280)
        self.assertEqual(metrics["SEAL Actual (MB)"], 0.0)
        self.assertEqual(metrics["SEAL Error Lo (%)"], "N/A")
        self.assertEqual(metrics["SEAL In Bounds"], False)

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
        for field in (
            "SEAL Baseline (MB)",
            "SEAL Keys Peak (MB)",
            "SEAL Inputs Peak (MB)",
            "SEAL Evaluation Peak (MB)",
        ):
            self.assertIn(field, CSV_FIELDS)

    def test_phase_metrics_subtract_the_startup_baseline(self):
        peaks = {
            "baseline": 100 * 1024**2,
            "keys": 120 * 1024**2,
            "inputs": 130 * 1024**2,
            "evaluation": 150 * 1024**2,
        }
        metrics = phase_peaks("Lattigo", peaks)
        self.assertEqual(metrics["Lattigo Baseline (MB)"], 100.0)
        self.assertEqual(metrics["Lattigo Evaluation Peak (MB)"], 150.0)
        self.assertEqual(metrics["Lattigo Actual (MB)"], 50.0)

    def test_replacement_benchmarks_match_estimator_key_needs(self):
        addition, addition_keys = ast_addition(4)
        batched_multiplications, multiplication_keys = ast_batched_multiplications(3)
        dot_product, dot_product_keys = ast_dot_product(4)

        addition_estimate = estimate_peak_ram(addition, FHEParams())
        multiplication_estimate = estimate_peak_ram(
            batched_multiplications, FHEParams()
        )
        dot_estimate = estimate_vectorized_peak_ram(dot_product, FHEParams())

        self.assertEqual(addition_keys, 0)
        self.assertEqual(addition_estimate.relin_keys_count, 0)
        self.assertEqual(multiplication_keys, 1)
        self.assertEqual(multiplication_estimate.relin_keys_count, 1)
        self.assertEqual(multiplication_estimate.allocating_ops, 3)
        self.assertEqual(dot_product_keys, 3)
        self.assertEqual(dot_estimate.relin_keys_count, 1)
        self.assertEqual(dot_estimate.galois_keys_count, 2)
        self.assertEqual(dot_estimate.keygen_transient_bytes, 0)

        params = FHEParams()
        seal_dot_estimate = estimate_vectorized_peak_ram(
            dot_product, params, backend_config=SEAL_CONFIG
        )
        self.assertGreater(seal_dot_estimate.keygen_transient_bytes, 0)
        self.assertEqual(
            seal_dot_estimate.keygen_transient_bytes,
            key_bytes(
                "seal",
                params.poly_modulus_degree,
                params.nQ("seal"),
                params.nP("seal"),
            ),
        )

    def test_vectorized_estimator_rejects_scalar_and_partial_expressions(self):
        self.assertFalse(is_fully_vectorized(Op("Vec", [Op("+", [Var("a"), Var("b")])])))
        self.assertFalse(is_fully_vectorized(Op("VecAdd", [Var("a"), Var("b")])))
        result = estimate_vectorized_peak_ram(
            Op("Vec", [Op("+", [Var("a"), Var("b")])]),
            FHEParams(),
        )
        self.assertIsInstance(result, NotEstimable)
        self.assertIn("scalar", result.reason)

    def test_vectorized_estimator_counts_packed_inputs_not_lanes(self):
        left = Op("Vec", [Var("left_0"), Var("left_1"), Const(0)])
        right = Op("Vec", [Var("right_0"), Var("right_1"), Const(0)])
        expression = Op("VecMul", [left, right])

        self.assertTrue(is_fully_vectorized(expression))
        estimate = estimate_vectorized_peak_ram(expression, FHEParams())
        scalar_estimate = estimate_peak_ram(expression, FHEParams())
        self.assertEqual(estimate.inputs_bytes, scalar_estimate.inputs_bytes // 2)
        self.assertLess(estimate.inputs_bytes, scalar_estimate.inputs_bytes)
        self.assertEqual(estimate.relin_keys_count, 1)

    def test_repeated_packed_input_is_counted_once(self):
        left = Op("Vec", [Var("x_0"), Var("x_1")])
        repeated = Op("Vec", [Var("x_0"), Var("x_1")])
        expression = Op("VecAdd", [left, repeated])

        estimate = estimate_vectorized_peak_ram(expression, FHEParams())
        one_vector = estimate_vectorized_peak_ram(left, FHEParams())
        self.assertEqual(estimate.inputs_bytes, one_vector.inputs_bytes)

    def test_high_churn_live_set_stays_at_two_intermediates(self):
        expression, _ = ast_high_churn(128)
        estimate = estimate_vectorized_peak_ram(
            expression,
            FHEParams(poly_modulus_degree=8192, coeff_modulus_num_primes=4),
        )

        self.assertEqual(estimate.slots_fixed, 2)
        self.assertEqual(estimate.allocating_ops, 129)

    def test_vectorized_estimator_turns_unreachable_key_threshold_into_status(self):
        expression = Op(
            "VecAdd",
            [
                Op("<<", [Op("Vec", [Var("a")]), Const(3)]),
                Op("<<", [Op("Vec", [Var("b")]), Const(5)]),
            ],
        )
        result = estimate_vectorized_peak_ram(
            expression,
            FHEParams(),
            keys_threshold=1,
        )
        self.assertIsInstance(result, NotEstimable)
        self.assertIn("threshold", result.reason)

    def test_compiler_emitted_vector_rotations_are_estimable(self):
        compiler_expression = parse_sexpr(
            "(VecAddRot (VecAddRot "
            "(VecMul (Vec a_0 a_1 a_2 a_3) "
            "(Vec b_0 b_1 b_2 b_3)) 4) 2)"
        )
        expanded = expand_compiler_vector_ops(compiler_expression)

        self.assertTrue(is_fully_vectorized(expanded))
        estimate = estimate_vectorized_peak_ram(compiler_expression, FHEParams())
        scalar_estimate = estimate_peak_ram(compiler_expression, FHEParams())
        self.assertEqual(estimate.galois_keys_count, 2)
        self.assertEqual(estimate.relin_keys_count, 1)
        self.assertEqual(estimate.inputs_bytes, scalar_estimate.inputs_bytes // 4)

    def test_plaintext_weighted_vector_multiply_needs_no_relinearization_key(self):
        expression = Op(
            "VecMul",
            [Op("Vec", [Var("input")]), Const(1.0 / 9.0)],
        )
        self.assertTrue(is_fully_vectorized(expression))
        estimate = estimate_vectorized_peak_ram(expression, FHEParams())
        self.assertEqual(estimate.relin_keys_count, 0)


if __name__ == "__main__":
    unittest.main()
