"""
Configuration file for FHE RL Agent
Contains model paths and other configuration parameters.
"""

import os
from pathlib import Path
import torch
import enum

class ConstraintMethod(enum.Enum):
    """Constraint enforcement method for multi-budget training."""
    NONE = "none"                                # Pure PPO, no constraint
    LAGRANGIAN_OD_OV = "lagrangian_od_ov"        # ON_DONE + ON_VIOLATION
    LAGRANGIAN_PERSTEP = "lagrangian_perstep"    # Per-step violation penalty
    LAGRANGIAN_ALWAYS_DONE = "lagrangian_always_done"  # Always penalize at terminal
    MARGIN_BARRIER = "margin_barrier"            # Margin obs + hard terminal penalty
    NOISE_MASKING = "noise_masking"              # Budget-aware action masking via noise estimation
    NATO_SC = "nato_sc"                          # Noise-Aware Trajectory Optimization + Safety Checkpointing
    LAGRANGIAN_PID = "lagrangian_pid"            # PID-controlled Lagrangian Penalty

# Base paths
PROJECT_ROOT = Path(__file__).parent.parent  # Go up to RL/ directory
FHE_RL_DIR = Path(__file__).parent

# Model paths configuration
MODEL_PATHS = {
    "agent_model": FHE_RL_DIR / "trained_models" / "agent_pareto_model.zip",
    "gnn_embeddings_model": FHE_RL_DIR / "trained_models" / "embeddings_gnn_model.pth",
}

# Agent configuration
AGENT_CONFIG = {
    "device": "cuda" if torch.cuda.is_available() else "cpu",
}

def get_model_path(model_key):
    """
    Get the path for a specific model
    """
    primary_path = MODEL_PATHS.get(model_key)

    if primary_path and primary_path.exists():
        return str(primary_path)
    elif primary_path:
        # Return the path even if it doesn't exist yet (e.g., for saving a new model)
        return str(primary_path)
    else:
        raise KeyError(f"Unknown model key: {model_key}")

def get_device():
    """
    Get the configured device
    """
    return AGENT_CONFIG["device"]

def print_config():
    """
    Print the current configuration
    """
    print("=== FHE RL Agent Configuration ===")
    print(f"Device: {get_device()}")
    print("\nModel paths:")
    for key, path in MODEL_PATHS.items():
        status = "✓" if path.exists() else "✗"
        print(f"  {key}: {status} {path}")