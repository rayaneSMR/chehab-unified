from .env import fheEnv


class fheEnvUnified(fheEnv):
    """Unified environment: MORL (preference vector, Pareto sampling, keys cost)
    + constrained RL (noise budgets, budget encoding, Lagrangian/PID methods).

    It currently behaves exactly like `fheEnv` (which already contains both
    sets of features). It is a separate class so that `--framework unified`
    has its own environment and can diverge from `fheEnv` (constrained
    baseline) without touching the constrained checkpoint's observation
    layout. If you later change the observation or reward for the unified
    agent, copy the full body of `fheEnv` here instead of inheriting.
    """
    pass