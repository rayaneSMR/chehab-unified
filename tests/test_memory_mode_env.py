import os
import sys
import unittest

import numpy as np

rl_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "RL"))
if rl_dir not in sys.path:
    sys.path.append(rl_dir)

from fhe_rl.env import fheEnv


class ZeroEmbedding:
    def get_embedding(self, expression):
        return np.zeros(256, dtype=np.float32)


class TestMemoryModeEnv(unittest.TestCase):
    def make_env(self, expression):
        return fheEnv(
            {"END": None},
            [expression],
            embeddings_model=ZeroEmbedding(),
            budget_options=[64 * 1024**2],
            constraint_method="nato_sc",
            constraint_mode="memory",
            verbose=False,
        )

    def test_scalar_expression_is_not_estimable_and_terminally_infeasible(self):
        env = self.make_env("(+ a b)")

        observation, info = env.reset(seed=1)

        self.assertFalse(info["memory_estimable"])
        self.assertIsNone(info["noise"])
        self.assertIn("scalar", info["memory_not_estimable_reason"])
        self.assertEqual(observation["memory_estimable"].tolist(), [0.0])
        self.assertEqual(observation["memory_estimate_mib"].tolist(), [0.0])
        self.assertTrue(env.observation_space.contains(observation))

        _, reward, terminated, truncated, final_info = env.step(0)

        self.assertTrue(terminated or truncated)
        self.assertEqual(reward, env.MEMORY_INFEASIBLE_PENALTY)
        self.assertFalse(final_info["memory_estimable"])

    def test_vectorized_expression_exposes_estimate_and_estimable_flag(self):
        env = self.make_env(
            "(VecMul (Vec a_0 a_1 0) (Vec b_0 b_1 0))"
        )

        observation, info = env.reset(seed=1)

        self.assertTrue(info["memory_estimable"])
        self.assertIsNotNone(info["noise"])
        self.assertEqual(observation["memory_estimable"].tolist(), [1.0])
        self.assertGreater(observation["memory_estimate_mib"][0], 0)
        self.assertTrue(env.observation_space.contains(observation))


if __name__ == "__main__":
    unittest.main()
