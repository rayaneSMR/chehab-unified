import os
import sys
import unittest

rl_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "RL"))
if rl_dir not in sys.path:
    sys.path.append(rl_dir)

from pytrs.expr import Const, Op, Var
from pytrs.peak_ram import FHEParams, estimate_peak_ram_v3
from fhe_rl.size_oracle import OracleParams, object_bytes

BASELINE = 8 * 1024 * 1024


class TestV3Estimator(unittest.TestCase):
    def test_no_hi_widening_and_baseline_passthrough(self):
        x, y = Var("a"), Var("b")
        ast = Op("*", [Op("+", [x, y]), x])
        params = FHEParams(poly_modulus_degree=16384, coeff_modulus_num_primes=6)

        est = estimate_peak_ram_v3(ast, params, BASELINE)

        # No GC term: hi equals lo.
        self.assertEqual(est.estimated_bytes_hi, est.estimated_bytes_lo)
        self.assertEqual(est.high_growth_bytes, 0)
        # Baseline is the supplied prediction, not a compiled-in constant.
        self.assertEqual(est.base_overhead_bytes, BASELINE)

    def test_object_sizes_come_from_oracle(self):
        x = Var("a")
        ast = Op("*", [x, x])
        params = FHEParams(poly_modulus_degree=16384, coeff_modulus_num_primes=6)
        oracle = OracleParams.from_fhe_params(params)
        ct_b = object_bytes("ciphertext_deg1", oracle)

        est = estimate_peak_ram_v3(ast, params, BASELINE)

        # One input ciphertext plus exactly one live multiply result.
        self.assertEqual(est.inputs_bytes, ct_b)
        self.assertEqual(est.intermediates_bytes, ct_b)

    def test_more_unknown_inputs_increase_live_not_hi(self):
        ast_small = Op("*", [Var("a"), Var("a")])
        ast_big = Op(
            "+",
            [Op("*", [Var("a"), Var("b")]), Op("*", [Var("c"), Var("d")])],
        )
        params = FHEParams(poly_modulus_degree=16384, coeff_modulus_num_primes=6)

        small = estimate_peak_ram_v3(ast_small, params, BASELINE)
        big = estimate_peak_ram_v3(ast_big, params, BASELINE)

        self.assertGreater(big.estimated_bytes_lo, small.estimated_bytes_lo)
        self.assertEqual(
            big.estimated_bytes_hi, big.estimated_bytes_lo,
            "v3 must not widen hi from lo",
        )


if __name__ == "__main__":
    unittest.main()
