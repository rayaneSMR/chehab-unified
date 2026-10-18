"""Replay a captured hang_<jobid>_<pid>.expr under cProfile (offline root-cause).

The .expr file is written by fhe_rl/env_unified.py when the apply_rule watchdog
fires (rule + path + stats header, then the raw expression after ---).

Usage:
    python replay_hang.py logs/hang_18825478_12345.expr
    python replay_hang.py logs/hang_...expr --rule rotate_2 --path 0,1
    python replay_hang.py logs/hang_...expr --top 40 --repeat 3

Output: cProfile sorted by tottime (to separate loop cost vs _replace_expr's
per-node structural == vs validate_expression's deep recursion), plus timing of
expr_to_str alone (stringification of a shared/DAG tree can itself blow up).
"""
import argparse
import cProfile
import io
import os
import pstats
import sys
import time

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
RL_DIR = os.path.dirname(TOOLS_DIR)            # one level up: RL/
if RL_DIR not in sys.path:
    sys.path.insert(0, RL_DIR)
PYTRS = os.path.join(RL_DIR, "pytrs")
if PYTRS not in sys.path:
    sys.path.insert(0, PYTRS)
os.chdir(RL_DIR)

from pytrs import parse_sexpr, expr_to_str  # noqa: E402
from pytrs.rules import create_rules  # noqa: E402
from pytrs.rewrite_rule import (  # noqa: E402
    count_nodes, count_nodes_unrolled, diag_snapshot)


def load_expr_file(path):
    """Return (rule_name, path_list, expr_str) from a captured .expr file."""
    rule_name, apply_path, lines = None, None, []
    in_header = True
    with open(path) as f:
        for line in f:
            line = line.rstrip("\n")
            if in_header:
                if line.startswith("rule:"):
                    rule_name = line.split(":", 1)[1].strip()
                elif line.startswith("path:"):
                    try:
                        apply_path = list(eval(line.split(":", 1)[1].strip()))
                    except Exception:
                        apply_path = None
                elif line == "---":
                    in_header = False
                continue
            lines.append(line)
    return rule_name, apply_path, "\n".join(lines).strip()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("expr_file", help="captured hang_<jobid>_<pid>.expr")
    ap.add_argument("--rule", default=None, help="override rule name")
    ap.add_argument("--path", default=None,
                    help="override apply path, e.g. 0,1,2 (empty string = root)")
    ap.add_argument("--top", type=int, default=30, help="cProfile entries shown")
    ap.add_argument("--repeat", type=int, default=1, help="run N times")
    args = ap.parse_args()

    rule_name, apply_path, expr_str = load_expr_file(args.expr_file)
    if args.rule:
        rule_name = args.rule
    if args.path is not None:
        apply_path = [int(x) for x in args.path.split(",") if x != ""] or []

    rules = create_rules(os.path.join(RL_DIR, "rules.txt"),
                         os.path.join(RL_DIR, "rotations_rules.txt"))
    rules["END"] = None
    if not rule_name or rule_name not in rules or rules[rule_name] is None:
        print(f"ERROR: rule {rule_name!r} not found. Available: "
              f"{sorted(k for k, v in rules.items() if v is not None)}")
        sys.exit(1)

    tree = parse_sexpr(expr_str)
    n_unique, n_unrolled, chars = count_nodes(tree), count_nodes_unrolled(tree), len(expr_str)
    print(f"rule={rule_name} path={apply_path}")
    print(f"input: chars={chars} unique_nodes={n_unique} unrolled_nodes={n_unrolled}")

    # Stringify alone first: on a shared DAG this is where exponential cost shows.
    t0 = time.perf_counter()
    s = expr_to_str(tree)
    t_str = time.perf_counter() - t0
    print(f"expr_to_str: {t_str:.3f}s (len={len(s)})")

    rule = rules[rule_name]
    d0 = diag_snapshot()
    pr = cProfile.Profile()
    t0 = time.perf_counter()
    pr.enable()
    for _ in range(args.repeat):
        out = rule.apply_rule(tree, path=apply_path)
    pr.disable()
    t_apply = time.perf_counter() - t0
    d1 = diag_snapshot()

    print(f"apply_rule x{args.repeat}: {t_apply:.3f}s "
          f"({t_apply / args.repeat:.3f}s/call)")
    print(f"  _apply_via_path: calls={d1['path_calls'] - d0['path_calls']} "
          f"time={d1['path_s'] - d0['path_s']:.3f}s")
    print(f"  _replace_expr:   calls={d1['replace_calls'] - d0['replace_calls']} "
          f"time={d1['replace_s'] - d0['replace_s']:.3f}s "
          f"eq_calls={d1['replace_eq_calls'] - d0['replace_eq_calls']}")
    try:
        print(f"  output: unique_nodes={count_nodes(out)} "
              f"unrolled_nodes={count_nodes_unrolled(out)}")
    except Exception as e:
        print(f"  output count failed: {e}")

    buf = io.StringIO()
    st = pstats.Stats(pr, stream=buf).sort_stats("tottime")
    st.print_stats(args.top)
    print("\n=== cProfile by tottime (loop vs == vs validate) ===")
    print(buf.getvalue())

    buf2 = io.StringIO()
    pstats.Stats(pr, stream=buf2).sort_stats("cumulative").print_stats(args.top)
    print("=== cProfile by cumulative ===")
    print(buf2.getvalue())


if __name__ == "__main__":
    main()
