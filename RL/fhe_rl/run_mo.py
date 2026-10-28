from stable_baselines3 import PPO
import time
from .utils import load_expressions, create_rules, parse_sexpr, calc_vec_sizes
import sys
import importlib
from stable_baselines3.common.vec_env import DummyVecEnv
from .config import get_env_class, get_policy_class
from stable_baselines3.common.monitor import Monitor


def run_agent_mo(expressions_file: str, embeddings_model, model_filepath: str, output_file: str, w_ops: float, w_keys: float):
    start_time = time.perf_counter()
    # load_expressions() drops vector sizes 3/5 (max_3, max_5, sort_3); the MORL branch had
    # that filter disabled, so use the unfiltered named loader to evaluate the same benchmarks.
    from .utils import load_expressions_named
    expressions = [e for e, _ in load_expressions_named(expressions_file)]
    if not len(expressions):
        print("No valid expressions found in the file.")
        sys.exit(1)
        return
    
    from pathlib import Path
    rules_path = Path("rules.txt")
    if not rules_path.is_file():
        rules_path = Path(__file__).resolve().parent.parent / "rules.txt"
    rot_rules_path = Path("rotations_rules.txt")
    if not rot_rules_path.is_file():
        rot_rules_path = Path(__file__).resolve().parent.parent / "rotations_rules.txt"

    from pytrs.rules import _create_rules_mo
    rules_list = _create_rules_mo(str(rules_path), str(rot_rules_path))
    rules_list["END"] = None
    print(f"DEBUG: len(rules_list) = {len(rules_list)}")
    max_positions = 16
    
    EnvCls = get_env_class()
    PolicyCls = get_policy_class()
    
    env = DummyVecEnv([
        lambda: Monitor(EnvCls(rules_list, expressions, max_positions=max_positions, embeddings_model=embeddings_model))
    ])
    
    # LOCK the preference vector to the one provided by the user
    w = [w_ops, w_keys]
    env.env_method("set_preference_vector", w)

    sys.modules["fhe_rl_new"] = importlib.import_module("fhe_rl")
    import fhe_rl.policy
    # Monkey patch the policy class to ensure SB3 unpickles the correct MO class
    fhe_rl.policy.HierarchicalMaskablePolicy = PolicyCls
    
    model = PPO.load(
        model_filepath, 
        env=env, 
        custom_objects={
            "policy_class": PolicyCls,
        }
    )
    
    obs = env.reset()
    wrapper  = env.envs[0]
    fhe_env   = wrapper.env
    test_expr = fhe_env.initial_expression
    initial_cost = fhe_env.initial_cost
    done = False
    steps = 0
    
    while not done:
        last_expr = fhe_env.expression
        action, _ = model.predict(obs, deterministic=True)
        obs, rewards, dones, infos = env.step(action)
        done = bool(dones[0])
        steps += 1

    parsed = parse_sexpr(last_expr)
    vec_s = calc_vec_sizes(parsed)
    if vec_s:
        sz = vec_s[0]
        footer = f"{sz} {sz} 1 0"
    else:
        footer = "1 1 1 0"
    with open(output_file, "w") as f:
        f.write(last_expr + "\n" + footer + "\n")
    
    end_time = time.perf_counter()
    print(f"Elapsed inference time: {end_time - start_time} seconds")
