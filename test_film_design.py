# test_film_design.py
import torch
from fhe_rl.policy import CustomFeaturesExtractor
import gymnasium as gym
from gymnasium import spaces
import numpy as np

def make_obs_space():
    return spaces.Dict({
        "observation": spaces.Box(-np.inf, np.inf, (256,)),
        "budget_one_hot_encoding": spaces.Box(0, 1, (3,)),
        "action_mask": spaces.Box(0, 1, (160,)),
        "preference_vector": spaces.Box(0, 1, (2,)),
        "noise_ratio": spaces.Box(0, 20, (1,)),
    })

# Design A: her code (load from repo directly)
obs_space = make_obs_space()
extractor_a = CustomFeaturesExtractor(obs_space, budget_encoding="film")
print("Design A features_dim:", extractor_a.features_dim)  # should be 256+32+1+2=291

# Design B: modified (you patch film_gamma input dim from 3 to 5)
class CustomFeaturesExtractorB(CustomFeaturesExtractor):
    def __init__(self, observation_space, budget_encoding="film"):
        # Override after parent init to change FiLM input dim
        super().__init__(observation_space, budget_encoding)
        if budget_encoding == "film":
            self.film_gamma = nn.Sequential(
                nn.Linear(self._budget_dim + self._pref_dim, self.BUDGET_EMBED_DIM),
                nn.ReLU(),
                nn.Linear(self.BUDGET_EMBED_DIM, self._embed_dim),
            )
            self.film_beta = nn.Sequential(
                nn.Linear(self._budget_dim + self._pref_dim, self.BUDGET_EMBED_DIM),
                nn.ReLU(),
                nn.Linear(self.BUDGET_EMBED_DIM, self._embed_dim),
            )
            nn.init.zeros_(self.film_gamma[-1].weight)
            nn.init.ones_(self.film_gamma[-1].bias)
            nn.init.zeros_(self.film_beta[-1].weight)
            nn.init.zeros_(self.film_beta[-1].bias)

extractor_b = CustomFeaturesExtractorB(obs_space, budget_encoding="film")
print("Design B features_dim:", extractor_b.features_dim)  # same: 291