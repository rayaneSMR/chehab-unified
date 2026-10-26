import sys
import unittest
import numpy as np
import torch
from pathlib import Path

# Set up paths
REPO_ROOT = Path("/home/maroua/chehab-unified")
RL_DIR = REPO_ROOT / "RL"
sys.path.insert(0, str(RL_DIR))
sys.path.insert(0, str(RL_DIR / "pytrs"))

from pytrs import parse_sexpr, NoiseEstimator
from fhe_rl.utils import create_rules, load_embeddings_from_config
from fhe_rl.env_unified import fheEnvUnified
from fhe_rl.policy import HierarchicalMaskablePolicy


class TestUnifiedModelNoiseConstraint(unittest.TestCase):
    """Verify that the unified model works end-to-end with noise as the constraint metric."""

    @classmethod
    def setUpClass(cls):
        rules_path = str(RL_DIR / "rules.txt")
        cls.rules = create_rules(rules_path)
        
        cls.sample_exprs = [
            "(+ (* x0 x1) (* x2 x3))",
            "(+ (+ x0 x1) (* x2 x3))",
            "(* (+ x0 x1) (+ x2 x3))",
        ]

        cls.embedder, _ = load_embeddings_from_config("bpe", embedder_type="gnn")

    def test_noise_estimator_direct(self):
        """Verify NoiseEstimator returns positive noise in bits for test expressions."""
        estimator = NoiseEstimator()
        for expr in self.sample_exprs:
            noise_val = estimator.estimate(expr)
            self.assertGreater(noise_val, 0.0, f"Noise must be positive, got {noise_val} for {expr}")
            print(f"Expression: {expr} -> Noise: {noise_val:.2f} bits")

    def test_unified_env_noise_configuration(self):
        """Verify fheEnvUnified correctly configures noise metric, units, and estimator."""
        noise_budgets = [230, 236, 369, 9_000_000]
        env = fheEnvUnified(
            rules_list=self.rules,
            expressions=self.sample_exprs,
            embeddings_model=self.embedder,
            budget_options=noise_budgets,
            constraint_metric="noise",
            constraint_method="nato_sc",
            verbose=False,
        )

        self.assertEqual(env.constraint_metric, "noise")
        self.assertEqual(env.metric_name, "Noise")
        self.assertEqual(env.metric_unit, "bits")
        self.assertIsInstance(env.estimator, NoiseEstimator)
        self.assertEqual(env.budget_options, noise_budgets)

        # Test reset
        obs, info = env.reset()
        self.assertIn("observation", obs)
        self.assertIn("budget_one_hot_encoding", obs)
        self.assertIn("action_mask", obs)
        self.assertIn("preference_vector", obs)
        self.assertIn("noise_ratio", obs)
        self.assertIn(env.budget, noise_budgets)
        self.assertGreater(env.curr_constraint, 0.0)
        print(f"Reset initial constraint: {env.curr_constraint:.2f} bits | Budget: {env.budget} bits | Ratio: {obs['noise_ratio'][0]:.4f}")

        # Test step
        action = 0
        action_mask = obs["action_mask"]
        valid_actions = np.where(action_mask > 0)[0]
        if len(valid_actions) > 0:
            action = int(valid_actions[0])

        next_obs, reward, terminated, truncated, step_info = env.step(action)
        self.assertIn("constraint_value", step_info)
        self.assertGreater(step_info["constraint_value"], 0.0)
        print(f"Step completed: reward={reward:.4f}, constraint_value={step_info['constraint_value']:.2f} bits")

    def test_film_policy_forward_pass_with_noise_budget(self):
        """Verify HierarchicalMaskablePolicy forward pass works with FiLM conditioning on noise budgets."""
        noise_budgets = [230, 236, 369, 9_000_000]
        env = fheEnvUnified(
            rules_list=self.rules,
            expressions=self.sample_exprs,
            embeddings_model=self.embedder,
            budget_options=noise_budgets,
            constraint_metric="noise",
            constraint_method="nato_sc",
            verbose=False,
        )

        obs, _ = env.reset()
        
        policy = HierarchicalMaskablePolicy(
            observation_space=env.observation_space,
            action_space=env.action_space,
            lr_schedule=lambda _: 3e-4,
            budget_encoding="film",
            policy_variant="film_a",
            num_budgets=len(noise_budgets),
            rule_dim=len(self.rules),
            max_positions=env.max_positions,
        )

        obs_tensor = {k: torch.as_tensor(v).unsqueeze(0) for k, v in obs.items()}
        actions, values, log_probs = policy(obs_tensor)
        
        self.assertEqual(actions.shape, (1,))
        self.assertEqual(values.squeeze().shape, ())
        self.assertEqual(log_probs.shape, (1,))
        self.assertTrue(torch.isfinite(values).all())
        self.assertTrue(torch.isfinite(log_probs).all())
        print(f"FiLM policy forward pass succeeded: action={actions.item()}, value={values.item():.4f}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
