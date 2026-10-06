"""
Configuration file for FHE RL Agent
Contains model paths, tokenizer settings, and other configuration parameters.
"""

import importlib
import os
from pathlib import Path
import torch
import enum


class RLAlgorithm(enum.Enum):
    PPO = "PPO"
    LAGRANGIAN_PPO = "LAGRANGIAN_PPO"


class EmbeddingsModelType(enum.Enum):
    TRANSFORMER_AUTOENCODER = "TRANSFORMER_AUTOENCODER"
    GNN_AUTOENCODER = "GNN_AUTOENCODER"


class ConstraintMethod(enum.Enum):
    """Constraint enforcement method for multi-budget training."""
    NONE = "none"                                # Pure PPO, no constraint
    LAGRANGIAN_OD_OV = "lagrangian_od_ov"        # ON_DONE + ON_VIOLATION (current stable)
    LAGRANGIAN_PERSTEP = "lagrangian_perstep"    # Per-step violation penalty
    LAGRANGIAN_ALWAYS_DONE = "lagrangian_always_done"  # Always penalize at terminal
    MARGIN_BARRIER = "margin_barrier"            # Margin obs + hard terminal penalty
    NOISE_MASKING = "noise_masking"              # Budget-aware action masking via noise estimation
    NATO_SC = "nato_sc"                          # Noise-Aware Trajectory Optimization + Safety Checkpointing
    LAGRANGIAN_PID = "lagrangian_pid"            # VOTRE AJOUT MORL


# Base paths
PROJECT_ROOT = Path(__file__).parent.parent  # Go up to RL/ directory
FHE_RL_DIR = Path(__file__).parent

# Model paths configuration

MODEL_PATHS = {
   
    "agent_model": PROJECT_ROOT / "checkpoints" / "model_jobid_lagrangian_pid_film_a" / "rl_model_600000_steps.zip",
    "gnn_embeddings_model": PROJECT_ROOT / "trained_models" / "embeddings_gnn_model_epoch_100.pth",
    
  
    "mo_agent_model": FHE_RL_DIR / "trained_models" / "agent_pareto_2_full.zip",

    # Unified (MORL + constrained) agent. Edit the path below, or set FHE_UNIFIED_MODEL.
    "unified_agent_model": Path(os.environ.get(
        "FHE_UNIFIED_MODEL",
        PROJECT_ROOT / "checkpoints" / "model_jobid_lagrangian_pid_film_a" / "rl_model_600000_steps.zip",
    )),
    "gnn_agent_model": FHE_RL_DIR / "trained_models" / "agent_lppo_14848346.zip",
    "dynamic_embeddings_model": FHE_RL_DIR / "trained_models" / "embeddings_ROT_15_32_5m_10742576.pth",
    "bpe_embeddings_model": FHE_RL_DIR / "trained_models" / "model_Transformer_BPE_ddp_jobid_epoch_5000000.pth",
    "bpe_tokenizer": FHE_RL_DIR / "trained_models" / "bpe_tokenizer.pkl",
}

# Tokenizer configuration (Restauré d'Imed)
TOKENIZER_CONFIG = {
    "use_bpe": False,  
    "default_vocab_size": 1000, 
    "auto_detect_vocab": True,   
}

# Agent configuration (Restauré d'Imed)
AGENT_CONFIG = {
    "device": "cuda" if torch.cuda.is_available() else "cpu",
    "algorithm": RLAlgorithm.LAGRANGIAN_PPO,
    "embeddings_model_type": EmbeddingsModelType.GNN_AUTOENCODER,
   

}

# Dotted paths resolved at runtime. (Restauré d'Imed)
COMPONENT_CONFIG = {
    "env_class": "fhe_rl.env.fheEnv",
    "policy_class": "fhe_rl.policy.HierarchicalMaskablePolicy",
    "wrapper_class": "auto",
}

# ----------------------------------------------------------------------------
# Framework registry.  `--framework X` selects ONE complete stack:
#   env class, policy class, checkpoint key, pytrs mode and preference mode.
#   constrained : constrained RL only      (single preference [1, 0])
#   morl        : original multi-objective RL (env_mo / policy_mo)
#   unified     : MORL + constrained RL    (Pareto preferences + noise budgets)
# ----------------------------------------------------------------------------
FRAMEWORKS = {
    "constrained": dict(
        env="fhe_rl.env.fheEnv",
        policy="fhe_rl.policy.HierarchicalMaskablePolicy",
        wrapper="auto",
        model_key="agent_model",
        pytrs="constrained",
        pref_mode="single",
    ),
    "morl": dict(
        env="fhe_rl.env_mo.fheEnvMO",
        policy="fhe_rl.policy_mo.HierarchicalMaskablePolicyMO",
        wrapper=None,
        model_key="mo_agent_model",
        pytrs="morl",
        pref_mode="pareto",
    ),
    "unified": dict(
        env="fhe_rl.env_unified.fheEnvUnified",
        policy="fhe_rl.policy.HierarchicalMaskablePolicy",
        wrapper="auto",
        model_key="unified_agent_model",
        pytrs="constrained",
        pref_mode="pareto",
    ),
}
_CURRENT_FRAMEWORK = "constrained"   # matches the default COMPONENT_CONFIG above


def set_framework(framework_name: str):
    """
    Select the framework ('constrained', 'morl' or 'unified').
    The legacy alias 'mo' is still accepted and means 'morl'.
    """
    global _CURRENT_FRAMEWORK
    if framework_name == "mo":
        framework_name = "morl"
    if framework_name not in FRAMEWORKS:
        raise ValueError(
            f"Unknown framework: {framework_name}. Choose from {list(FRAMEWORKS)}"
        )
    spec = FRAMEWORKS[framework_name]
    COMPONENT_CONFIG["env_class"] = spec["env"]
    COMPONENT_CONFIG["policy_class"] = spec["policy"]
    COMPONENT_CONFIG["wrapper_class"] = spec["wrapper"]
    _CURRENT_FRAMEWORK = framework_name


def get_framework() -> str:
    return _CURRENT_FRAMEWORK


def get_framework_spec() -> dict:
    return FRAMEWORKS[_CURRENT_FRAMEWORK]


def get_model_path(model_key):
    """
    VOTRE MODIFICATION : Utilise la logique permissive pour ne pas crasher si le fichier n'est pas encore téléchargé
    """
    primary_path = MODEL_PATHS.get(model_key)
    if primary_path and primary_path.exists(): 
        return str(primary_path)
    elif primary_path: 
        return str(primary_path)
    else: 
        raise KeyError(f"Unknown model key: {model_key}")

def get_tokenizer_type():
    return "bpe" if TOKENIZER_CONFIG["use_bpe"] else "dynamic"

def set_tokenizer_type(tokenizer_type):
    if tokenizer_type not in ["dynamic", "bpe"]:
        raise ValueError(f"Invalid tokenizer type: {tokenizer_type}. Must be 'dynamic' or 'bpe'")
    TOKENIZER_CONFIG["use_bpe"] = (tokenizer_type == "bpe")

def get_vocab_size():
    return TOKENIZER_CONFIG["default_vocab_size"]

def get_device():
    return AGENT_CONFIG["device"]

def get_rl_algorithm() -> RLAlgorithm:
    return AGENT_CONFIG["algorithm"]

def get_embeddings_model_type() -> EmbeddingsModelType:
    return AGENT_CONFIG["embeddings_model_type"]

def _resolve_class(dotted_path: str):
    module_path, class_name = dotted_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)

def get_env_class():
    return _resolve_class(COMPONENT_CONFIG["env_class"])

def get_policy_class():
    return _resolve_class(COMPONENT_CONFIG["policy_class"])

def get_wrapper_class():
    value = COMPONENT_CONFIG.get("wrapper_class", "auto")
    if value is None or value == "auto":
        return value
    return _resolve_class(value)

def print_config():
    print("=== FHE RL Agent Configuration ===")
    print(f"Framework: {get_framework()}")
    print(f"Tokenizer type: {get_tokenizer_type()}")
    print(f"Device: {get_device()}")
    print(f"Env class: {COMPONENT_CONFIG['env_class']}")
    print(f"Policy class: {COMPONENT_CONFIG['policy_class']}")
    print("\nModel paths:")
    for key, path in MODEL_PATHS.items():
        status = "✓" if path.exists() else "✗"
        print(f"  {key}: {status} {path}")