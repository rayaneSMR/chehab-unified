#!/usr/bin/env python3
"""Build a unified, diverse calibration expression pool.

Combines:
  1. Base expressions from final_llm_dataset.txt (covering all base operators, depths, and ring dimensions).
  2. Extracted deep neural network (DNN) expressions (mandatory for calibration).
  3. Persistent top-level rotation expressions where Galois keys (G > 0) cannot be optimized away.
  4. Randomly rewritten expressions at intermediate optimization trajectory steps.

Outputs:
  RL/fhe_rl/datasets/unified_calibration_pool.jsonl
  RL/fhe_rl/datasets/unified_calibration_pool.txt
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
RL_DIR = REPO_ROOT / "RL"
DATASETS_DIR = RL_DIR / "fhe_rl" / "datasets"
PYTRS_DIR = RL_DIR / "pytrs"

sys.path.insert(0, str(PYTRS_DIR))

try:
    from parser import parse_sexpr
    from cost import get_multiplicative_depth
    from ckks_memory_estimator import chehab_params, estimate_expression_memory
    from expr import Expr, Op, Const, Var
    from rewrite_rule import RewriteRule
    from rule_parser import parse_rules_from_text
except ImportError as err:
    print(f"[ERROR] Import failure in build_unified_calib_pool: {err}", file=sys.stderr)
    sys.exit(1)


def structural_hash(expr_str: str) -> str:
    """Compute a tree structure hash invariant to leaf variable names."""
    try:
        tree = parse_sexpr(expr_str)
        def _canon(node: Expr) -> str:
            if isinstance(node, (Const, Var)):
                return "v"
            if isinstance(node, Op):
                return f"({node.op} " + " ".join(_canon(c) for c in node.args) + ")"
            return "x"
        canon_str = _canon(tree)
        return hashlib.sha256(canon_str.encode("utf-8")).hexdigest()[:16]
    except Exception:
        return hashlib.sha256(expr_str.encode("utf-8")).hexdigest()[:16]


def build_persistent_rotation_expression(family: str, g: int, slots: int = 64) -> str:
    """Build expressions with explicit top-level rotations that cannot be eliminated."""
    def vec(prefix: str, n: int = slots) -> str:
        return "(Vec " + " ".join(f"{prefix}{i}" for i in range(n)) + ")"

    if family == "shallow":
        acc = vec("a")
    elif family == "medium":
        acc = f"(VecMul {vec('m1_')} {vec('m2_')})"
        acc = f"(VecMul {acc} {vec('m3_')})"
    else:  # deep
        acc = vec("m1_")
        for i in range(2, 8):
            acc = f"(VecMul {acc} {vec(f'm{i}_')})"

    rot_src = vec("r")
    for j in range(1, g + 1):
        step = (1 << (j - 1)) if j <= 6 else j
        acc = f"(VecAdd {acc} (<< {rot_src} {step}))"
    return acc


def load_dnn_expressions() -> List[Dict[str, Any]]:
    """Load all available extracted deep neural network benchmark expressions."""
    dnn_records: List[Dict[str, Any]] = []
    seen_exprs: Set[str] = set()

    candidate_files = [
        DATASETS_DIR / "dnn_benchmarks.txt",
        DATASETS_DIR / "dnn_benchmarks_scaled.txt",
        DATASETS_DIR / "conv2d.txt",
        DATASETS_DIR / "conv2d_only.txt",
    ]
    # Add files from tmp_dnn_dataset if they exist and are reasonable size (< 5MB)
    tmp_dnn_dir = REPO_ROOT / "build" / "benchmarks" / "tmp_dnn_dataset"
    if tmp_dnn_dir.is_dir():
        for p in tmp_dnn_dir.glob("*/*.txt"):
            if p.is_file() and p.stat().st_size < 5_000_000:
                candidate_files.append(p)

    for path in candidate_files:
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                expr = line.split(":", 1)[0].strip() if ":" in line else line
                label = line.split(":", 1)[1].strip() if ":" in line else path.stem
                if expr in seen_exprs or len(expr) < 10 or not expr.startswith("("):
                    continue
                try:
                    tree = parse_sexpr(expr)
                    depth = get_multiplicative_depth(tree)
                    params = chehab_params(depth)
                    est = estimate_expression_memory(tree, backend="cpu", params=params)
                    seen_exprs.add(expr)
                    dnn_records.append({
                        "expr": expr,
                        "kind": "dnn",
                        "label": label,
                        "depth": depth,
                        "N": params.N,
                        "L": params.L,
                        "G": est.rotation_steps,
                        "est_net_mb": round(est.total_mb, 3),
                        "struct_hash": structural_hash(expr),
                    })
                except Exception:
                    continue
        except Exception:
            continue

    return dnn_records


def load_ruleset() -> List[RewriteRule]:
    """Load rules directly from rules.txt and rotations_rules.txt without torch."""
    rules_list: List[RewriteRule] = []
    for r_name in ["rules.txt", "rotations_rules.txt"]:
        for candidate in [REPO_ROOT / r_name, RL_DIR / r_name, RL_DIR / "pytrs" / r_name]:
            if candidate.is_file():
                try:
                    parsed = parse_rules_from_text(candidate.read_text(encoding="utf-8", errors="ignore"))
                    rules_list.extend(parsed)
                    break
                except Exception:
                    pass
    return rules_list


def generate_rewrites_from_base(
    expr_str: str,
    rules: List[RewriteRule],
    max_steps: int = 4,
    trials: int = 2
) -> List[Dict[str, Any]]:
    """Generate intermediate rewritten expressions using the TRS ruleset."""
    rewrites: List[Dict[str, Any]] = []
    if not rules:
        return rewrites

    for _ in range(trials):
        current = expr_str
        for step in range(1, max_steps + 1):
            try:
                tree = parse_sexpr(current)
                applicable = []
                for rule_obj in rules:
                    matches = rule_obj.find_matching_subexpressions(tree)
                    if matches:
                        applicable.append((rule_obj, matches))
                if not applicable:
                    break
                rule_obj, matches = random.choice(applicable)
                path, _ = random.choice(matches[:4])
                new_tree = rule_obj.apply_rule(tree, path=path)
                from expr import expr_to_str
                candidate_str = expr_to_str(new_tree)
                if candidate_str != current and len(candidate_str) > 10:
                    current = candidate_str
                    depth = get_multiplicative_depth(new_tree)
                    params = chehab_params(depth)
                    est = estimate_expression_memory(new_tree, backend="cpu", params=params)
                    rewrites.append({
                        "expr": current,
                        "kind": "rewrite_trajectory",
                        "label": f"rewrite_step_{step}",
                        "depth": depth,
                        "N": params.N,
                        "L": params.L,
                        "G": est.rotation_steps,
                        "est_net_mb": round(est.total_mb, 3),
                        "struct_hash": structural_hash(current),
                    })
            except Exception:
                break
    return rewrites


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-dataset", type=Path, default=DATASETS_DIR / "final_llm_dataset.txt",
                        help="Path to final LLM base dataset file")
    parser.add_argument("--output-pool", type=Path, default=DATASETS_DIR / "unified_calibration_pool.jsonl",
                        help="Output JSONL path for the calibration pool")
    parser.add_argument("--output-txt", type=Path, default=DATASETS_DIR / "unified_calibration_pool.txt",
                        help="Output TXT path (one expression per line)")
    parser.add_argument("--target-size", type=int, default=600,
                        help="Target total calibration pool size (default: 600)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducibility")
    args = parser.parse_args()

    random.seed(args.seed)
    print("=" * 70)
    print("BUILDING UNIFIED EMPIRICAL CALIBRATION POOL")
    print(f"Base Dataset: {args.base_dataset}")
    print(f"Target Pool Size: {args.target_size}")
    print("=" * 70)

    # 1. Load DNN benchmark expressions (Mandatory for calibration training)
    print("\n[Phase 1] Harvesting Deep Neural Network (DNN) expressions...")
    dnn_records = load_dnn_expressions()
    print(f"  Found {len(dnn_records)} valid DNN benchmark expressions.")

    # 2. Synthesize Persistent Top-Level Rotation Expressions (G > 0)
    print("\n[Phase 2] Synthesizing Persistent Top-Level Rotation expressions (G > 0)...")
    rot_records: List[Dict[str, Any]] = []
    g_steps = [1, 2, 4, 8, 12, 16, 24, 32, 48, 64]
    for family in ("shallow", "medium", "deep"):
        for g in g_steps:
            for slots in (32, 64, 128):
                try:
                    expr = build_persistent_rotation_expression(family, g, slots=slots)
                    tree = parse_sexpr(expr)
                    depth = get_multiplicative_depth(tree)
                    params = chehab_params(depth)
                    est = estimate_expression_memory(tree, backend="cpu", params=params)
                    rot_records.append({
                        "expr": expr,
                        "kind": "persistent_rotation",
                        "label": f"rot_{family}_g{g}_s{slots}",
                        "depth": depth,
                        "N": params.N,
                        "L": params.L,
                        "G": est.rotation_steps,
                        "est_net_mb": round(est.total_mb, 3),
                        "struct_hash": structural_hash(expr),
                    })
                except Exception:
                    continue
    print(f"  Synthesized {len(rot_records)} persistent rotation circuits (G in {min(g_steps)}..{max(g_steps)}).")

    # 3. Load and parse expressions from final_llm_dataset.txt
    print(f"\n[Phase 3] Stratified sampling from base dataset: {args.base_dataset}...")
    base_records: List[Dict[str, Any]] = []
    if not args.base_dataset.is_file():
        print(f"[ERROR] Base dataset not found: {args.base_dataset}", file=sys.stderr)
        return 1

    lines = args.base_dataset.read_text(encoding="utf-8", errors="ignore").splitlines()
    print(f"  Total lines in base dataset: {len(lines):,}")

    random.shuffle(lines)
    sample_budget = max(args.target_size * 2, 2000)
    for idx, raw_line in enumerate(lines[:sample_budget]):
        expr = raw_line.strip()
        if not expr or len(expr) < 10 or not expr.startswith("("):
            continue
        try:
            tree = parse_sexpr(expr)
            depth = get_multiplicative_depth(tree)
            params = chehab_params(depth)
            est = estimate_expression_memory(tree, backend="cpu", params=params)
            base_records.append({
                "expr": expr,
                "kind": "base_llm",
                "label": f"llm_base_{idx}",
                "depth": depth,
                "N": params.N,
                "L": params.L,
                "G": est.rotation_steps,
                "est_net_mb": round(est.total_mb, 3),
                "struct_hash": structural_hash(expr),
            })
        except Exception:
            continue

    print(f"  Parsed {len(base_records)} valid base expressions across parameter tiers.")

    # 4. Generate Random Trajectory Rewrites
    print("\n[Phase 4] Generating intermediate rewrite trajectory variants...")
    rules = load_ruleset()
    rewrite_records: List[Dict[str, Any]] = []
    for base in base_records[:100]:
        r_list = generate_rewrites_from_base(base["expr"], rules, max_steps=3, trials=2)
        rewrite_records.extend(r_list)
    print(f"  Generated {len(rewrite_records)} rewritten trajectory expressions.")

    # 5. Assemble, Deduplicate, and Stratify Balance
    print("\n[Phase 5] Assembling and balancing the unified calibration pool...")
    pool: List[Dict[str, Any]] = []
    seen_hashes: Set[str] = set()

    # Priority 1: All DNN expressions MUST be included
    for r in dnn_records:
        if r["struct_hash"] not in seen_hashes:
            seen_hashes.add(r["struct_hash"])
            pool.append(r)

    # Priority 2: High-diversity persistent rotations
    for r in rot_records:
        if r["struct_hash"] not in seen_hashes:
            seen_hashes.add(r["struct_hash"])
            pool.append(r)

    # Priority 3: Stratified base LLM expressions across (N, L)
    buckets: Dict[Tuple[int, int], List[Dict[str, Any]]] = {}
    for r in base_records + rewrite_records:
        key = (r["N"], r["L"])
        buckets.setdefault(key, []).append(r)

    remaining_slots = max(args.target_size - len(pool), 50)
    per_bucket_quota = max(remaining_slots // max(len(buckets), 1), 10)

    for (N_val, L_val), items in buckets.items():
        random.shuffle(items)
        added = 0
        for it in items:
            if it["struct_hash"] not in seen_hashes:
                seen_hashes.add(it["struct_hash"])
                pool.append(it)
                added += 1
                if added >= per_bucket_quota:
                    break

    print(f"\nFinal Unified Calibration Pool Size: {len(pool)} circuits")
    kinds_count: Dict[str, int] = {}
    n_count: Dict[int, int] = {}
    g_nonzero = 0
    for r in pool:
        kinds_count[r["kind"]] = kinds_count.get(r["kind"], 0) + 1
        n_count[r["N"]] = n_count.get(r["N"], 0) + 1
        if r["G"] > 0:
            g_nonzero += 1

    print("\nComposition Breakdown:")
    for k, v in sorted(kinds_count.items()):
        print(f"  • Kind '{k}': {v} circuits ({v/len(pool)*100:.1f}%)")
    print("Ring Dimension (N) Coverage:")
    for n, v in sorted(n_count.items()):
        print(f"  • N = {n}: {v} circuits ({v/len(pool)*100:.1f}%)")
    print(f"Circuits with Persistent Rotation Keys (G > 0): {g_nonzero} ({g_nonzero/len(pool)*100:.1f}%)")

    args.output_pool.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output_pool, "w", encoding="utf-8") as f_json:
        for r in pool:
            f_json.write(json.dumps(r) + "\n")

    with open(args.output_txt, "w", encoding="utf-8") as f_txt:
        for r in pool:
            f_txt.write(f"{r['expr']}:{r['label']}\n")

    print(f"\nSaved JSONL pool: {args.output_pool}")
    print(f"Saved TXT pool:   {args.output_txt}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
