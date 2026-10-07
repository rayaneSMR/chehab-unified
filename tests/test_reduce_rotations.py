import os
import sys
import unittest

rl_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'RL'))
if rl_dir not in sys.path:
    sys.path.append(rl_dir)

from pytrs.peak_ram import reduce_rotation_keys_pass


class TestReduceRotationKeys(unittest.TestCase):
    def test_decomposition_matches_cpp_rotation_key_set(self):
        # C++ reduce_rotation_keys decomposes these six steps to their shared
        # power-of-two components when the threshold is four.
        steps_freq = {3: 1, 15: 1, 19: 1, 20: 1}
        self.assertEqual(
            reduce_rotation_keys_pass(steps_freq, 3),
            {-1, 4, 16},
        )

    def test_steps_are_unchanged_when_under_the_threshold(self):
        self.assertEqual(
            reduce_rotation_keys_pass({-3: 10, 5: 5}, 2),
            {-3, 5},
        )

    def test_power_of_two_steps_are_kept_when_threshold_is_met(self):
        self.assertEqual(
            reduce_rotation_keys_pass({2: 10, 4: 20}, 2),
            {2, 4},
        )

    def test_unattainable_threshold_matches_cpp_failure(self):
        with self.assertRaisesRegex(RuntimeError, "could not go lower"):
            reduce_rotation_keys_pass({3: 10, 4: 20, 5: 5}, 2)


if __name__ == '__main__':
    unittest.main()
