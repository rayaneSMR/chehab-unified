#!/usr/bin/env python3
"""
run_unified_benchmarks.py
-------------------------
Runs the benchmarks in `unified` mode only and writes, in ONE CSV row, the MORL
metrics (w_ops/w_keys, ops & keys cost, rotation keys) next to the constrained
metrics (noise budget, estimated/measured noise).

Run from the repo root (same place as run_morl_benchmarks_budget.py):

    python3 run_unified_benchmarks.py
    python3 run_unified_benchmarks.py --benchmarks dot_product lin_reg --slots 4 8 \
        --budgets 240 300 1000000

Output: results_unified.csv  (one row per run)

Fixes vs run_morl_benchmarks_budget.py
  * the CSV header had 20 columns but each row had 26: `operations` was appended
    twice in the row (`operations + infos[4:]`, and infos[4:] already contains them).
  * `rotation_keys_count` was read from main's output but never declared in the stats
    dict (KeyError) nor in the header.
  * noise is reported in BOTH views: estimated-consumed (optimizer) and
    measured-consumed (SEAL), so they can be compared directly.
"""
import argparse
import csv
import os
import re
import statistics
import subprocess

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
BUILD_FOLDER = os.path.join("build", "benchmarks")
OPERATIONS = ["add", "sub", "multiply_plain", "rotate_rows", "negate", "multiply"]

# SEAL budget the NoiseEstimator was calibrated against (RL/pytrs/noise_estimator.py,
# noise_budget=369).  measured_used = INITIAL_NOISE_BUDGET - Remaining_noise_budget.
INITIAL_NOISE_BUDGET = 369

DEFAULT_FRAMEWORKS = ["unified"]  # one run gives both agents' metrics
DEFAULT_BENCHMARKS = ["dot_product"]
DEFAULT_SLOTS = [4]
DEFAULT_BUDGETS = [240, 300, 1000000]
DEFAULT_PREFS = [(1.0, 0.0), (0.8, 0.2), (0.5, 0.5), (0.2, 0.8)]

EXCEPTIONS = {"max": [3, 4, 5], "sort": [3], "discrete_cosin_transform": [1], "poly_derivative": [1]}
TIMEOUT_S = 7200
REPEATS = 1  # >1 -> median over repeats

COLUMNS = (
    ["benchmark"]
    # --- MORL metrics (multi-objective: ops cost vs keys cost) ---
    + ["w_ops", "w_keys", "final_ops_cost", "final_keys_cost",
       "rotation_keys_count", "rotation_keys_static", "rotation_keys_size (MB)"]
    # --- Constrained metrics (noise budget constraint) ---
    + ["noise_budget", "noise_used_estimated", "noise_budget_status",
       "Remaining_noise_budget", "noise_used_measured"]
    # --- Common: circuit + timings ---
    + OPERATIONS
    + ["Depth", "Multiplicative Depth",
       "optimizer_time (s)", "compile_time (s)", "circuit_execution_time (s)",
       "galois_keys_generation_time (s)", "total_execution_time (s)"]
)

ANSI = re.compile(r"\x1b\[[0-9;]*m")
NUM = r"([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)"


# --------------------------------------------------------------------------- #
# Parsing (pure functions, easy to test)
# --------------------------------------------------------------------------- #
def parse_compile_output(stdout: str) -> dict:
    """Metrics printed by the C++ driver + fhe_rl.run (compile / optimisation phase)."""
    out = {}
    text = ANSI.sub("", stdout)
    for raw in text.splitlines():
        line = raw.strip()
        low = line.lower()

        m = re.match(rf"final (?:exec|ops) cost\s*:\s*{NUM}", low)
        if m:
            out["final_ops_cost"] = float(m.group(1))
        m = re.match(rf"final keys cost\s*:\s*{NUM}", low)
        if m:
            out["final_keys_cost"] = float(m.group(1))
        m = re.match(rf"final noise \(est\)\s*:\s*{NUM}\s*/\s*budget\s*{NUM}\s*\[(\w+)\]", low)
        if m:
            out["noise_used_estimated"] = float(m.group(1))
            out["noise_budget_status"] = m.group(3).upper()
        m = re.match(rf"optimization completed in\s*{NUM}\s*seconds", low)
        if m:
            out["optimizer_time (s)"] = float(m.group(1))
        # whole-compile time: a line that is just "<number> ms"
        m = re.match(rf"^{NUM}\s*ms$", low)
        if m:
            out["compile_time_ms"] = float(m.group(1))
        # static quantifier summary: "|rotation_keys|: 1"
        m = re.match(r"\|rotation_keys\|\s*:\s*(\d+)", line)
        if m:
            out["rotation_keys_static"] = int(m.group(1))

    d = re.search(r"max:\s*\((\d+),\s*(\d+)\)", text)
    if d:
        out["Depth"] = int(d.group(1))
        out["Multiplicative Depth"] = int(d.group(2))
    return out


def parse_main_output(stdout: str) -> dict:
    """Metrics printed by the generated ./main (real SEAL execution)."""
    out = {}
    keymap = {
        "circuit_execution_time_(ms):": ("circuit_execution_time_ms", float),
        "galois_keys_generation_time_(ms):": ("galois_ms", float),
        "total_execution_time_(ms):": ("total_ms", float),
        "rotation_keys_size_(MB):": ("rotation_keys_size (MB)", float),
        "rotation_keys_count_:": ("rotation_keys_count", float),
        "Remaining_noise_budget:": ("Remaining_noise_budget", float),
    }
    for raw in stdout.splitlines():
        parts = raw.split()
        if len(parts) >= 2 and parts[0] in keymap:
            name, cast = keymap[parts[0]]
            try:
                out[name] = cast(parts[1])
            except ValueError:
                pass
    return out


def count_generated_ops(cpp_path: str) -> dict:
    counts = {}
    if os.path.exists(cpp_path):
        with open(cpp_path, "r") as f:
            content = f.read()
        for op in OPERATIONS:
            counts[op] = len(re.findall(rf"\b{op}", content))
    return counts


def build_row(framework, bench, w_ops, w_keys, budget, samples):
    """samples: list of dicts (one per repeat). Medians; missing -> 'N/A'."""
    def med(key):
        vals = [s[key] for s in samples if key in s and s[key] is not None]
        return statistics.median(vals) if vals else None

    def sec(key):
        v = med(key)
        return format(v / 1000.0, ".3f") if v is not None else None

    merged = {
        "benchmark": bench, "w_ops": w_ops, "w_keys": w_keys,
        "noise_budget": budget if budget is not None else "N/A",
        "Depth": med("Depth"), "Multiplicative Depth": med("Multiplicative Depth"),
        "compile_time (s)": sec("compile_time_ms"),
        "circuit_execution_time (s)": sec("circuit_execution_time_ms"),
        "galois_keys_generation_time (s)": sec("galois_ms"),
        "total_execution_time (s)": sec("total_ms"),
        "noise_used_estimated": med("noise_used_estimated"),
        "Remaining_noise_budget": med("Remaining_noise_budget"),
        "rotation_keys_size (MB)": med("rotation_keys_size (MB)"),
        "rotation_keys_count": med("rotation_keys_count"),
        "rotation_keys_static": med("rotation_keys_static"),
        "final_ops_cost": med("final_ops_cost"),
        "final_keys_cost": med("final_keys_cost"),
        "optimizer_time (s)": med("optimizer_time (s)"),
    }
    for op in OPERATIONS:
        merged[op] = med(op)
    statuses = [s["noise_budget_status"] for s in samples if "noise_budget_status" in s]
    merged["noise_budget_status"] = statuses[-1] if statuses else None
    rem = merged["Remaining_noise_budget"]
    merged["noise_used_measured"] = (INITIAL_NOISE_BUDGET - rem) if rem is not None else None

    return [("N/A" if merged.get(c) is None else merged[c]) for c in COLUMNS]


# --------------------------------------------------------------------------- #
# Execution
# --------------------------------------------------------------------------- #
def run_once(bench, slot, framework, w_ops, w_keys, budget, build_path):
    he_path = os.path.join(build_path, "he")
    sample = {}

    gen = f"generate_{bench}.py"
    if bench not in EXCEPTIONS and os.path.exists(os.path.join(build_path, gen)):
        subprocess.run(["python3", gen, "--slot_count", str(slot)], cwd=build_path)

    cmd = f"./{bench} 1 {slot} {framework} 1 0 1 1 1 0 {w_ops} {w_keys}"
    env = os.environ.copy()
    if budget is not None:                       # constrained / unified only
        env["FHECO_NOISE_BUDGET"] = str(budget)
    else:
        env.pop("FHECO_NOISE_BUDGET", None)

    res = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         universal_newlines=True, cwd=build_path, timeout=TIMEOUT_S, env=env)
    if res.returncode != 0:
        print(f"[ERROR] {cmd} crashed:\n{res.stderr.strip()[-800:]}")
        return None
    sample.update(parse_compile_output(res.stdout))

    for step in (["cmake", "-S", ".", "-B", "build"], ["cmake", "--build", "build"]):
        subprocess.run(step, cwd=he_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    run = subprocess.run("./main", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         universal_newlines=True, cwd=os.path.join(he_path, "build"), env=env)
    sample.update(parse_main_output(run.stdout))
    sample.update(count_generated_ops(os.path.join(he_path, "_gen_he_fhe.cpp")))
    return sample


def plan_runs(framework, prefs, budgets):
    """Which (w_ops, w_keys, budget) combinations make sense for each framework."""
    if framework == "constrained":      # single objective, noise-budget constrained
        return [(1.0, 0.0, b) for b in budgets]
    if framework == "morl":             # multi-objective, no noise budget
        return [(wo, wk, None) for wo, wk in prefs]
    return [(wo, wk, b) for b in budgets for wo, wk in prefs]   # unified


def get_prefs():
    try:
        from RL.fhe_rl.pareto import generate_pref_list
        return [tuple(map(float, p)) for p in generate_pref_list(3)]
    except Exception:
        return DEFAULT_PREFS


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--benchmarks", nargs="+", default=DEFAULT_BENCHMARKS)
    ap.add_argument("--slots", nargs="+", type=int, default=None)
    ap.add_argument("--frameworks", nargs="+", default=DEFAULT_FRAMEWORKS,
                    choices=DEFAULT_FRAMEWORKS)
    ap.add_argument("--budgets", nargs="+", type=int, default=DEFAULT_BUDGETS)
    ap.add_argument("--out", default="results_unified.csv")
    ap.add_argument("--skip-build", action="store_true", help="skip the top-level cmake build")
    args = ap.parse_args()

    if not args.skip_build:
        for step in (["cmake", "-S", ".", "-B", "build"], ["cmake", "--build", "build"]):
            print("run=>", " ".join(step))
            subprocess.run(step, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    prefs = get_prefs()
    with open(args.out, "w", newline="") as f:
        csv.writer(f).writerow(COLUMNS)

    for bench in args.benchmarks:
        build_path = os.path.join(BUILD_FOLDER, bench)
        if not os.path.isdir(build_path):
            print(f"[skip] {build_path} not found")
            continue
        slots = EXCEPTIONS.get(bench, args.slots or DEFAULT_SLOTS)
        for slot in slots:
            for fw in args.frameworks:
                for w_ops, w_keys, budget in plan_runs(fw, prefs, args.budgets):
                    print(f"***** {fw} | {bench}_{slot} | w=({w_ops},{w_keys}) | budget={budget}")
                    samples = []
                    for _ in range(REPEATS):
                        try:
                            s = run_once(bench, slot, fw, w_ops, w_keys, budget, build_path)
                        except subprocess.TimeoutExpired:
                            print("  timeout")
                            s = None
                        if s:
                            samples.append(s)
                    if not samples:
                        continue
                    row = build_row(fw, f"{bench}_{slot}", w_ops, w_keys, budget, samples)
                    assert len(row) == len(COLUMNS)
                    with open(args.out, "a", newline="") as f:
                        csv.writer(f).writerow(row)
    print(f"done -> {args.out}")


if __name__ == "__main__":
    main()
    