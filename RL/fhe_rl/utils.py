import os
import sys
from pytrs import (
    create_rules as _create_rules, parse_sexpr,
    Expr, Const, Var, Op, VARIABLE_RANGE, CONST_OFFSET,
    PAREN_CLOSE, PAREN_OPEN, node_to_id
)
import torch
import torch.nn as nn

from .config import get_model_path, get_device

DEVICE = get_device()

def load_embeddings_from_config():
    """
    GNNAE is integrated directly into the policy network's CustomFeaturesExtractor.
    Returning None, None to satisfy legacy unpacked signatures in __main__.py.
    """
    return None, None

def create_rules(rules_path: str, rotations_rules_path: str = None):
    return _create_rules(rules_path=rules_path, rotations_rules_path=rotations_rules_path)

def get_token_sequence(exp_str: str):
    expr = parse_sexpr(exp_str)
    flat = flatten_expr(expr)
    node_ids = tuple(entry["node_id"] for entry in flat)
    return node_ids

def dfs_traverse(expr, depth=0, node_list=None):
    if node_list is None:
        node_list = []
    if isinstance(expr, Op):
        node_list.append((PAREN_OPEN, depth))
        node_list.append((expr, depth))
        for child in expr.args:
            dfs_traverse(child, depth + 1, node_list)
        node_list.append((PAREN_CLOSE, depth))
    else:
        node_list.append((expr, depth))
    return node_list

def flatten_expr(expr):
    node_list = dfs_traverse(expr, 0)
    results = []
    varmap = {}
    intmap = {}
    next_var_id = VARIABLE_RANGE[0]
    next_int_id = CONST_OFFSET
    for node_or_paren, depth in node_list:
        if node_or_paren in (PAREN_OPEN, PAREN_CLOSE):
            nid = node_or_paren
        else:
            nid, next_var_id, next_int_id, _ = node_to_id(
                node_or_paren, varmap, intmap, next_var_id, next_int_id
            )
        results.append({"node_id": nid})
    return results

def load_expressions(file_path: str, validation_exprs=[]):
    validation_token_set = set()
    for val in validation_exprs:
        exp_str = val.split(":")[0].strip()
        token_seq = get_token_sequence(exp_str)
        validation_token_set.add(token_seq)
        
    unique_expressions = {}
    with open(file_path, "r") as f:
        for line in f:
            exp_str = line.split(":")[0].strip()
            if not exp_str:
                continue
            try:
                expr = parse_sexpr(exp_str)
                token_seq = get_token_sequence(exp_str)
                if token_seq in validation_token_set:
                    continue
                if token_seq not in unique_expressions:
                    unique_expressions[token_seq] = exp_str
            except Exception as e:
                print(e)
                continue
    print("Number of unique valid expressions (excluding validation):", len(unique_expressions))
    return list(unique_expressions.values())

def load_expressions_named(file_path: str):
    """Load expressions with their names from a benchmark file.
    Returns list of (expression_str, name) tuples, preserving order."""
    results = []
    with open(file_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if ":" in line:
                exp_str, name = line.rsplit(":", 1)
                exp_str = exp_str.strip()
                name = name.strip()
            else:
                exp_str = line
                name = f"expr_{len(results)}"
            try:
                expr = parse_sexpr(exp_str)
                results.append((exp_str, name))
            except Exception as e:
                print(f"Skipping invalid expression '{name}': {e}")
                continue
    print(f"Loaded {len(results)} named expressions from {file_path}")
    return results

def mlp(in_dim, hidden_dims, out_dim, *,
        act=nn.GELU, layernorm=True, dropout=0.0,
        residual=False, seed=None):
    """
    Build an MLP: [in_dim] → hidden_dims* → [out_dim]
    """
    if seed is not None:
        torch.manual_seed(seed)
        torch.cuda.manual_seed(seed)

    layers, prev = [], in_dim
    for i, h in enumerate(hidden_dims):
        layers.append(nn.Linear(prev, h))
        if layernorm:
            layers.append(nn.LayerNorm(h))
        layers.append(act())
        if dropout > 0:
            layers.append(nn.Dropout(dropout))
        prev = h
    layers.append(nn.Linear(prev, out_dim))
    return nn.Sequential(*layers)

def predict_method(
        self,
        observation,
        state=None,
        episode_start=None,
        deterministic: bool = False,
    ):
        device = next(self.parameters()).device
        if isinstance(observation, dict):
            obs = {k: torch.as_tensor(v, device=device) for k, v in observation.items()}
        else:
            obs = torch.as_tensor(observation, device=device)
        actions, _, _ = self.forward(obs, deterministic=deterministic)
        return actions.cpu().numpy(), state

def calc_vec_sizes(expr:Expr):
    vec_sizes=[]
    def rec(node:Expr):
        if isinstance(node, (Const, Var)):
            return
        if isinstance(node, Op):
            if node.op == "Vec":
                vec_sizes.append(len(node.args))
            else:
                for arg in node.args:
                    rec(arg)
            
    rec(expr)
    return vec_sizes