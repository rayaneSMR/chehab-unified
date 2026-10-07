import os
import random
import sys
import unittest

rl_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'RL'))
if rl_dir not in sys.path:
    sys.path.append(rl_dir)

from pytrs.expr import Const, Op, Var
from pytrs.peak_ram import (
    FHEParams,
    LATTIGO_CONFIG,
    LATTIGO_CONFIG_V1,
    LATTIGO_DEV_P95_GC_HEADROOM_FACTOR,
    _slots_dag,
    estimate_peak_ram,
)
from fhe_rl.memory_layout import (
    lattigo_helper_buffer_bytes,
    lattigo_input_staging_bytes,
    lattigo_parameter_bytes,
    lattigo_postprocess_bytes,
)


def recursive_slots(root, reverse_children=False):
    records = {}

    def visit(node):
        if isinstance(node, Var):
            key = ("input", node.name)
            records.setdefault(key, {"input": True, "args": []})
            return key
        if isinstance(node, Const):
            key = ("const", node.value)
            records.setdefault(key, {"input": False, "args": [], "op": "const"})
            return key

        args = node.args[::-1] if reverse_children else node.args
        arg_keys = [visit(arg) for arg in args if not isinstance(arg, int)]
        key = ("op", id(node))
        records[key] = {"input": False, "args": arg_keys, "op": node.op}
        return key

    root_key = visit(root)
    dep_count = {key: 0 for key in records}
    for record in records.values():
        for arg_key in record["args"]:
            dep_count[arg_key] += 1

    schedule = []
    scheduled = set()

    def schedule_node(key):
        if key in scheduled:
            return
        scheduled.add(key)
        for arg_key in records[key]["args"]:
            schedule_node(arg_key)
        schedule.append(key)

    schedule_node(root_key)

    live = set()
    peak = 0
    for key in schedule:
        record = records[key]
        if not record["input"] and record.get("op") not in ("const", "literal", "Vec"):
            live.add(key)
        peak = max(peak, len(live))
        for arg_key in record["args"]:
            if arg_key in live:
                dep_count[arg_key] -= 1
                if dep_count[arg_key] == 0:
                    live.remove(arg_key)
    return peak


class TestPeakRAMDFSOrder(unittest.TestCase):
    def test_v1_estimate_preserves_legacy_garbage_term(self):
        estimate = estimate_peak_ram(
            Op("+", [Var("left"), Var("right")]),
            FHEParams(),
            backend_config=LATTIGO_CONFIG_V1,
        )

        self.assertGreater(estimate.base_overhead_bytes, 0)
        self.assertEqual(estimate.high_growth_bytes, min(
            estimate.allocation_bytes,
            int(1.6 * (
                estimate.keys_bytes
                + estimate.keygen_transient_bytes
                + estimate.inputs_bytes
                + estimate.plaintexts_bytes
                + estimate.intermediates_bytes
            )),
        ))
        self.assertEqual(
            estimate.estimated_bytes_lo,
            estimate.base_overhead_bytes
            + estimate.keys_bytes
            + estimate.keygen_transient_bytes
            + estimate.inputs_bytes
            + estimate.plaintexts_bytes
            + estimate.intermediates_bytes,
        )

    def test_v2_models_lattigo_tables_helpers_and_calibrated_growth(self):
        params = FHEParams(poly_modulus_degree=16384, coeff_modulus_num_primes=6)
        estimate = estimate_peak_ram(
            Op("+", [Var("left"), Var("right")]),
            params,
            backend_config=LATTIGO_CONFIG,
        )

        expected_parameters = lattigo_parameter_bytes(16384, 4, 2)
        expected_helpers = lattigo_helper_buffer_bytes(16384, 4, 2)
        expected_staging = lattigo_input_staging_bytes(16384)
        expected_postprocess = lattigo_postprocess_bytes(16384, 4)
        self.assertEqual(expected_parameters, int(1.5 * 2**20))
        self.assertEqual(expected_helpers, 16187408)
        self.assertEqual(estimate.base_overhead_bytes, 8 * 2**20)
        self.assertEqual(estimate.parameter_bytes, expected_parameters)
        self.assertEqual(estimate.helper_buffers_bytes, expected_helpers)
        self.assertEqual(estimate.input_staging_bytes, expected_staging)
        self.assertEqual(estimate.postprocess_bytes, expected_postprocess)
        self.assertEqual(estimate.input_plaintext_transient_bytes, 1 * 2**20)
        self.assertEqual(
            estimate.managed_live_bytes,
            estimate.keys_bytes
            + estimate.keygen_transient_bytes
            + estimate.inputs_bytes
            + estimate.plaintexts_bytes
            + estimate.intermediates_bytes
            + expected_parameters
            + expected_helpers
            + estimate.rotation_index_bytes
            + expected_staging
            + expected_postprocess,
        )
        expected_growth = int(
            estimate.managed_live_bytes
            * LATTIGO_DEV_P95_GC_HEADROOM_FACTOR
        )
        self.assertEqual(estimate.high_growth_bytes, expected_growth)
        self.assertEqual(
            estimate.estimated_bytes_lo,
            estimate.base_overhead_bytes + estimate.managed_live_bytes,
        )
        self.assertEqual(
            estimate.estimated_bytes_hi,
            estimate.base_overhead_bytes
            + estimate.managed_live_bytes
            + estimate.input_plaintext_transient_bytes
            + expected_growth,
        )

    def test_v2_counts_lattigo_automorphism_index_per_rotation_key(self):
        estimate = estimate_peak_ram(
            Op("<<", [Var("input"), Const(1)]),
            FHEParams(poly_modulus_degree=16384, coeff_modulus_num_primes=6),
            backend_config=LATTIGO_CONFIG,
        )

        self.assertEqual(estimate.galois_keys_count, 1)
        self.assertEqual(estimate.rotation_index_bytes, 16384 * 8)

    def test_cpp_left_to_right_order_for_asymmetric_tree(self):
        small = Op("+", [Var("a"), Var("b")])
        big = Op("+", [
            Op("+", [Var("c"), Var("d")]),
            Op("+", [Var("e"), Var("f")]),
        ])
        left_first = Op("*", [small, big])
        right_first = Op("*", [big, small])

        self.assertEqual(recursive_slots(left_first), 4)
        self.assertEqual(recursive_slots(left_first, reverse_children=True), 3)
        self.assertEqual(_slots_dag(left_first), 4)
        self.assertEqual(_slots_dag(right_first), 3)

    def test_matches_recursive_left_to_right_reference_for_400_trees(self):
        rng = random.Random(97103)
        next_name = 0

        def make_tree(depth):
            nonlocal next_name
            if depth == 0 or rng.random() < 0.3:
                name = f"v{next_name}"
                next_name += 1
                return Var(name)
            return Op(rng.choice(["+", "-", "*"]), [
                make_tree(depth - 1),
                make_tree(depth - 1),
            ])

        for _ in range(400):
            tree = make_tree(rng.randint(1, 6))
            self.assertEqual(_slots_dag(tree), recursive_slots(tree))

    def test_long_chain_does_not_use_python_recursion(self):
        tree = Var("x")
        for _ in range(5000):
            tree = Op("+", [tree, Var("x")])

        estimate = estimate_peak_ram(tree, FHEParams())
        self.assertEqual(estimate.slots_fixed, 2)

    def test_vec_lanes_and_input_names_are_preserved(self):
        estimate = estimate_peak_ram(
            Op("Vec", [Var("v1_0"), Var("v1_1")]),
            FHEParams(),
        )
        one_input = estimate_peak_ram(Var("v1"), FHEParams())

        self.assertEqual(estimate.inputs_bytes, 2 * one_input.inputs_bytes)
        self.assertEqual(estimate.allocating_ops, 0)


if __name__ == '__main__':
    unittest.main()
