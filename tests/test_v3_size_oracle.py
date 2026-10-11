import os
import sys
import unittest

rl_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "RL"))
if rl_dir not in sys.path:
    sys.path.append(rl_dir)

from fhe_rl.memory_layout import (
    ct_bytes,
    key_bytes,
    pk_bytes,
    pt_bytes,
    sk_bytes,
)
from fhe_rl.size_oracle import KINDS, OracleParams, object_bytes

# (logN, nQ, nP) sets present in the oracle table.
CORPUS_SETS = (
    (14, 4, 2),
    (14, 5, 2),
    (14, 6, 2),
    (14, 7, 2),
    (14, 8, 2),
    (15, 10, 2),
)

TOLERANCE = 0.001  # 0.1%


class TestV3SizeOracle(unittest.TestCase):
    def test_oracle_matches_formulas_within_0_1_percent(self):
        for log_n, n_q, n_p in CORPUS_SETS:
            n = 1 << log_n
            params = OracleParams(log_n=log_n, n_q=n_q, n_p=n_p)
            checks = (
                ("secret_key", sk_bytes("lattigo", n, n_q, n_p)),
                ("public_key", pk_bytes("lattigo", n, n_q, n_p)),
                ("relinearization_key", key_bytes("lattigo", n, n_q, n_p)),
                ("galois_key", key_bytes("lattigo", n, n_q, n_p)),
                ("ciphertext_deg1", ct_bytes("lattigo", 0, n, n_q, n_p)),
                ("plaintext_max_level", pt_bytes("lattigo", 0, n, n_q, n_p)),
            )
            for kind, formula_bytes in checks:
                oracle = object_bytes(kind, params)
                relative = abs(oracle - formula_bytes) / formula_bytes
                self.assertLessEqual(
                    relative, TOLERANCE,
                    f"{kind} logN={log_n} nQ={n_q} nP={n_p}: "
                    f"oracle={oracle} formula={formula_bytes} "
                    f"relative={relative:.5f}",
                )

    def test_all_kinds_present_for_every_table_row(self):
        params = OracleParams(log_n=14, n_q=4, n_p=2)
        for kind in KINDS:
            self.assertGreater(object_bytes(kind, params), 0)

    def test_unknown_backend_raises_instead_of_approximating(self):
        params = OracleParams(log_n=14, n_q=4, n_p=2, backend="seal")
        with self.assertRaises(LookupError):
            object_bytes("galois_key", params)

    def test_unknown_params_raise(self):
        params = OracleParams(log_n=16, n_q=40, n_p=2)
        with self.assertRaises(LookupError):
            object_bytes("galois_key", params)

    def test_unknown_kind_raises(self):
        params = OracleParams(log_n=14, n_q=4, n_p=2)
        with self.assertRaises(ValueError):
            object_bytes("mystery", params)


if __name__ == "__main__":
    unittest.main()
