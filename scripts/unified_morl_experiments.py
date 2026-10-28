#!/usr/bin/env python3
"""
Redo the MORL thesis experiments (Chapter 5, Part B) with the UNIFIED agent
(MORL preference conditioning + BFV noise budget).

Every experiment of the MORL study is reproduced with one extra axis, the noise
budget B (used BFV bits, same unit as pytrs.NoiseEstimator):

  B1  single-objective baseline vs MORL vs unified, Direct Mode w=[1,0]
  B2  Pareto frontier: (a) trade-off curve, (b) 3-preference comparison,
      (c) frontier plots with bisection, (d) MORL metrics table (IC/HV/SP/EU)
  B4  exploration ablation: base vs KL bonus (1e-4) vs envelope bonus (0.05)
  B5  sensitivity: N_budget 5 vs 10
  A3  uniform (N_cycle=0) vs biased (N_cycle=1, 2) preference sampling
  +   noise-constraint satisfaction per budget (new, unified only)

Sub-commands (run from anywhere; paths are resolved from the repo root):

  plan       print which agents / budgets / preferences each experiment needs
  preflight  check build, SEAL runner, models and the known keys-cost bug
  train      write (and optionally sbatch) one training job per agent variant
  sweep      compile + run benchmarks on SEAL/BFV for one agent; resumable CSV
  slurm      write a SLURM array script that runs `sweep` in parallel shards
  metrics    compute IC / HV / SP / EU + constraint metrics from sweep CSVs
  report     tables + figures for B1, B2a-d, B4, B5, A3 and the noise constraint

Typical flow on the cluster:

  python scripts/unified_morl_experiments.py preflight
  python scripts/unified_morl_experiments.py train --variants base,kl,env,nbudget10,uniform --submit
  # ...when the models are in RL/fhe_rl/trained_models/unified_noise_<variant>.zip
  python scripts/unified_morl_experiments.py slurm --experiments all --shards 8 --submit
  python scripts/unified_morl_experiments.py metrics
  python scripts/unified_morl_experiments.py report
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import shutil
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RL_DIR = REPO / "RL"
MODELS_DIR = RL_DIR / "fhe_rl" / "trained_models"
OUT_DIR = REPO / "results" / "unified_morl"

# ════════════════════════════════════════════════════════════════════════════
# Configuration (mirrors the MORL thesis, Table 5.1 and the evaluation protocol)
# ════════════════════════════════════════════════════════════════════════════

NOISE_BUDGETS = [230, 236, 369, 9_000_000]          # 9e6 = unconstrained
TRAIN_BUDGETS = [230, 236, 369, 9_000_000]          # one-hot size the agent was trained with
NOISE_REFERENCE_BITS = 369                          # NoiseEstimator default: used = 369 - remaining
UNCONSTRAINED = 9_000_000

# 10 training preferences w_ops = 1.0 .. 0.1 (w = [0, 1] excluded on purpose)
PREFS = [round(1.0 - i / 10, 1) for i in range(10)]
B2B_PREFS = [1.0, 0.9, 0.8]
B4_PREFS = [1.0, 0.1]                                # exec time at [1,0], compile time at [0.1,0.9]

MAX_BISECT_DEPTH = 3
COMPILE_TIMEOUT_S = 7200
RUN_TIMEOUT_S = 1200

STRUCTURED = ["dot_product", "l2_distance", "hamming_dist", "lin_reg", "poly_reg",
              "matrix_mul", "box_blur", "gx_kernel", "gy_kernel", "roberts_cross"]
SIZES = [4, 8, 16, 32]
SPECIAL_SIZES = {"max": [3, 4, 5], "sort": [3]}
NO_GENERATOR = {"max", "sort"}                      # same exceptions as run_morl_benchmarks.py
POLY_TREES = [(5, "50-50"), (5, "100-50"), (10, "50-50")]   # (depth, regime), instance 1

# Benchmarks drawn in the thesis frontier figure (Fig. 5.7)
B2C_INSTANCES = ["hamming_dist_8", "hamming_dist_32", "dot_product_32", "sort_3"]


@dataclass
class Agent:
    name: str
    framework: str                 # value passed as the benchmark's <framework> argument
    model: str | None = None       # .zip (None = framework default)
    budgets: list = field(default_factory=lambda: list(NOISE_BUDGETS))
    train_flags: dict = field(default_factory=dict)   # only for trainable unified variants
    method: str = "nato_sc"
    note: str = ""


def _unified(variant, note, **flags):
    base = dict(n_cycle=1, n_budget=5, lambda_env=0.0, lambda_kl=0.0, timesteps=2_000_000,
                embedder="gnn", method="nato_sc", algo="lagrangian_pid",
                budget_encoding="film", policy_variant="film_a")
    base.update(flags)
    return Agent(name=variant, framework="unified",
                 model=str(MODELS_DIR / f"unified_noise_{variant}.zip"),
                 train_flags=base, method=base["method"], note=note)


AGENTS = {
    # ── unified agents (trained by `train`) ────────────────────────────────
    "base":      _unified("base", "Table 5.1 reference: N_budget=5, N_cycle=1, no bonuses"),
    "kl":        _unified("kl", "B4: KL specialization bonus", lambda_kl=1e-4),
    "env":       _unified("env", "B4: Pareto envelope bonus", lambda_env=0.05),
    "nbudget10": _unified("nbudget10", "B5: weaker key penalty", n_budget=10),
    "uniform":   _unified("uniform", "A3: uniform preference sampling", n_cycle=0),
    "cycle2":    _unified("cycle2", "A3: N_cycle=2 (thesis text example)", n_cycle=2),
    "trae":      _unified("trae", "optional: Transformer embedder like the MORL agent", embedder="trae"),
    # ── reference agents (already trained, budget-agnostic) ────────────────
    "morl":      Agent("morl", "morl", model=None, budgets=["none"],
                       note="MORL thesis agent (mo_agent_model = agent_pareto_2_full.zip)"),
    "original":  Agent("original", "baseline", model=None, budgets=["none"],
                       note="original CHEHAB single-objective RL, rotation heuristic off"),
}

# experiment -> list of (agent, preferences, bisection?)
EXPERIMENTS = {
    "B1":  [("base", [1.0], False), ("morl", [1.0], False), ("original", [1.0], False)],
    "B2":  [("base", PREFS, True), ("morl", PREFS, True)],
    "B4":  [("base", B4_PREFS, False), ("kl", B4_PREFS, False), ("env", B4_PREFS, False)],
    "B5":  [("base", PREFS, False), ("nbudget10", PREFS, False)],
    "A3":  [("base", PREFS, False), ("uniform", PREFS, False), ("cycle2", PREFS, False)],
}

CSV_FIELDS = [
    "agent", "benchmark", "family", "size", "budget", "w_ops", "w_keys", "source",
    "add", "sub", "multiply_plain", "rotate_rows", "negate", "multiply",
    "depth", "mult_depth", "compile_time_s", "rl_inference_s", "rl_steps",
    "circuit_execution_time_s", "galois_keys_generation_time_s", "total_execution_time_s",
    "rotation_keys_size_mb", "peak_ram_mb", "remaining_noise_budget", "measured_used_bits",
    "final_exec_cost", "final_keys_cost", "est_noise", "est_violated", "measured_violated",
    "rollback_used", "agent_est_noise", "status", "error",
]
OPS = ["add", "sub", "multiply_plain", "rotate_rows", "negate", "multiply"]


# ════════════════════════════════════════════════════════════════════════════
# Benchmark instances
# ════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Instance:
    family: str
    size: str           # slot count, or "<depth>_<regime>" for trees
    kind: str           # "std" | "poly"

    @property
    def name(self):
        if self.kind == "poly":
            depth, regime = self.size.split("_", 1)
            return f"tree_{regime}_{depth}"
        return f"{self.family}_{self.size}"

    @property
    def binary(self):
        return "polynomials_coyote" if self.kind == "poly" else self.family


def all_instances(filter_names=None):
    out = [Instance(f, str(n), "std") for f in STRUCTURED for n in SIZES]
    out += [Instance(f, str(n), "std") for f, ns in SPECIAL_SIZES.items() for n in ns]
    out += [Instance("poly_tree", f"{d}_{r}", "poly") for d, r in POLY_TREES]
    if filter_names:
        wanted = set(filter_names)
        out = [i for i in out if i.name in wanted or i.family in wanted]
    return out


# ════════════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════════════

ANSI = re.compile(r"\x1b\[[0-9;]*m")


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def agent_model(agent: Agent):
    if agent.model:
        return agent.model
    return None  # framework default from RL/fhe_rl/config.py


def csv_path(agent_name, shard=None):
    suffix = f".shard{shard}" if shard is not None else ""
    return OUT_DIR / "raw" / f"{agent_name}{suffix}.csv"


def read_rows(paths):
    rows = []
    for p in paths:
        if Path(p).is_file():
            with open(p, newline="") as f:
                rows.extend(csv.DictReader(f))
    return rows


def row_key(r):
    return (r["agent"], r["benchmark"], str(r["budget"]), f"{float(r['w_ops']):.6f}")


def append_row(path: Path, row: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.is_file()
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in CSV_FIELDS})


def fnum(v, default=None):
    try:
        if v in ("", None, "N/A"):
            return default
        x = float(v)
        return x if math.isfinite(x) else default
    except (TypeError, ValueError):
        return default


def run(cmd, cwd, timeout, env=None):
    return subprocess.run(cmd, cwd=str(cwd), shell=isinstance(cmd, str), env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          universal_newlines=True, timeout=timeout)


def fix_stale_cmake_cache(he_dir: Path):
    """A build dir copied for a shard keeps a CMakeCache pointing at the original path."""
    cache = he_dir / "build" / "CMakeCache.txt"
    if cache.is_file():
        txt = cache.read_text(errors="ignore")
        m = re.search(r"CMAKE_CACHEFILE_DIR:INTERNAL=(.*)", txt)
        if m and Path(m.group(1).strip()).resolve() != (he_dir / "build").resolve():
            cache.unlink()
            shutil.rmtree(he_dir / "build" / "CMakeFiles", ignore_errors=True)


# ════════════════════════════════════════════════════════════════════════════
# One measurement point: compile with the agent, then execute on SEAL (BFV)
# ════════════════════════════════════════════════════════════════════════════

def measure_point(agent: Agent, inst: Instance, w_ops: float, budget, build_dir: Path,
                  repeats: int, source: str, generated: set):
    bench_dir = build_dir / "benchmarks" / inst.binary
    he_dir = bench_dir / "he"
    w_ops = round(float(w_ops), 10)
    row = dict(agent=agent.name, benchmark=inst.name, family=inst.family, size=inst.size,
               budget=budget, w_ops=w_ops, w_keys=round(1.0 - w_ops, 10), source=source,
               status="ok", error="")
    if not bench_dir.is_dir():
        row.update(status="missing", error=f"{bench_dir} not found (build the repo first)")
        return row

    # Inputs: generated once per instance per sweep session so every preference sees the same data.
    if inst.kind == "std" and inst.family not in NO_GENERATOR and inst.name not in generated:
        gen = bench_dir / f"generate_{inst.family}.py"
        if gen.is_file():
            run([sys.executable, gen.name, "--slot_count", inst.size], bench_dir, 600)
        generated.add(inst.name)

    info_json = OUT_DIR / "info" / agent.name / f"{inst.name}_B{budget}_w{w_ops:.6f}.json"
    info_json.parent.mkdir(parents=True, exist_ok=True)
    if info_json.exists():
        info_json.unlink()
    env = dict(os.environ)
    env["PYTHONPATH"] = f"{RL_DIR}{os.pathsep}{RL_DIR / 'pytrs'}{os.pathsep}{env.get('PYTHONPATH', '')}"
    env["CHEHAB_RL_W_OPS"] = str(w_ops)
    env["CHEHAB_RL_INFO_JSON"] = str(info_json)
    env["CHEHAB_RL_CONSTRAINT"] = "noise"
    env["CHEHAB_RL_TRAIN_BUDGETS"] = ",".join(str(b) for b in TRAIN_BUDGETS)
    env["CHEHAB_RL_METHOD"] = agent.method
    if budget != "none":
        env["CHEHAB_RL_BUDGET"] = str(budget)
    model = agent_model(agent)
    if model:
        env["CHEHAB_RL_MODEL"] = model
    else:
        env.pop("CHEHAB_RL_MODEL", None)

    # Benchmark CLI (backend 0 = SEAL, scheme 0 = BFV, optimization_method 1 = RL)
    if inst.kind == "poly":
        depth, regime = inst.size.split("_", 1)
        # argv: depth inst regime vec framework opt window quant backend cse scheme w_ops
        cmd = f"./{inst.binary} {depth} 1 {regime} 1 {agent.framework} 1 0 1 0 1 0 {w_ops}"
    else:
        # argv: vec slot framework opt window quant cse cf backend w_ops scheme
        cmd = f"./{inst.binary} 1 {inst.size} {agent.framework} 1 0 1 1 1 0 {w_ops} 0"
    t0 = time.perf_counter()
    try:
        res = run(cmd, bench_dir, COMPILE_TIMEOUT_S, env=env)
    except subprocess.TimeoutExpired:
        row.update(status="compile_timeout", error=cmd)
        return row
    wall = time.perf_counter() - t0
    out = ANSI.sub("", res.stdout)
    compile_ms = None
    for line in out.splitlines():
        low = line.lower().strip()
        if "final exec cost" in low:
            row["final_exec_cost"] = fnum(low.split(":")[-1])
        elif "final keys cost" in low:
            row["final_keys_cost"] = fnum(low.split(":")[-1])
        elif compile_ms is None and re.match(r"^\s*[\d.]+\s+ms\b", line):
            compile_ms = fnum(line.split()[0])
    row["compile_time_s"] = round(compile_ms / 1000, 3) if compile_ms is not None else round(wall, 3)
    m = re.search(r"max:\s*\((\d+),\s*(\d+)\)", out)
    if m:
        row["depth"], row["mult_depth"] = int(m.group(1)), int(m.group(2))
    if info_json.is_file():
        info = json.loads(info_json.read_text())
        row.update(final_exec_cost=info.get("final_exec_cost", row.get("final_exec_cost")),
                   final_keys_cost=info.get("final_keys_cost", row.get("final_keys_cost")),
                   est_noise=info.get("final_constraint"), est_violated=info.get("final_violated"),
                   agent_est_noise=info.get("agent_constraint"), rollback_used=info.get("rollback_used"),
                   rl_inference_s=info.get("inference_time_s"), rl_steps=info.get("steps"))
    if res.returncode != 0:
        row.update(status="compile_failed", error=(res.stderr or out)[-300:].replace("\n", " "))
        return row

    # Operation counts from the generated SEAL source
    gen_cpp = he_dir / "_gen_he_fhe.cpp"
    if gen_cpp.is_file():
        src = gen_cpp.read_text(errors="ignore")
        for op in OPS:
            row[op] = len(re.findall(rf"\b{op}", src))

    # SEAL execution
    if not (he_dir / "main.cpp").is_file():
        row.update(status="no_seal_runner", error=f"{he_dir}/main.cpp missing")
        return row
    fix_stale_cmake_cache(he_dir)
    for step in (["cmake", "-S", ".", "-B", "build"], ["cmake", "--build", "build"]):
        r = run(step, he_dir, 1800)
        if r.returncode != 0:
            row.update(status="seal_build_failed", error=r.stderr[-300:].replace("\n", " "))
            return row
    samples = {k: [] for k in ("circuit", "keygen", "total", "keys_mb", "peak", "noise")}
    for _ in range(max(1, repeats)):
        try:
            r = run("./main", he_dir / "build", RUN_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            row.update(status="run_timeout")
            return row
        if r.returncode != 0:
            row.update(status="run_failed", error=r.stderr[-300:].replace("\n", " "))
            return row
        noise_vals = []
        for line in r.stdout.splitlines():
            parts = line.split()
            if len(parts) < 2:
                continue
            tag, val = parts[0], fnum(parts[1])
            if tag.startswith("circuit_execution_time_(ms)"):
                samples["circuit"].append(val)
            elif tag.startswith("galois_keys_generation_time_(ms)"):
                samples["keygen"].append(val)
            elif tag.startswith("total_execution_time_(ms)"):
                samples["total"].append(val)
            elif tag.startswith("rotation_keys_size_(MB)"):
                samples["keys_mb"].append(val)
            elif tag.startswith("peak_ram_memory_(MB)"):
                samples["peak"].append(val)
            elif tag.startswith("Remaining_noise_budget"):
                noise_vals.append(val)
        if noise_vals:
            samples["noise"].append(min(noise_vals))   # worst output ciphertext

    def med(k, scale=1.0):
        vals = [v for v in samples[k] if v is not None]
        return round(statistics.median(vals) * scale, 4) if vals else None

    row.update(circuit_execution_time_s=med("circuit", 1e-3), galois_keys_generation_time_s=med("keygen", 1e-3),
               total_execution_time_s=med("total", 1e-3), rotation_keys_size_mb=med("keys_mb"),
               peak_ram_mb=med("peak"), remaining_noise_budget=med("noise"))
    if row["remaining_noise_budget"] is not None:
        rem = row["remaining_noise_budget"]
        row["measured_used_bits"] = NOISE_REFERENCE_BITS - rem
        over_budget = budget != "none" and budget < UNCONSTRAINED and row["measured_used_bits"] > budget
        row["measured_violated"] = bool(rem <= 0 or over_budget)
    return row


# ════════════════════════════════════════════════════════════════════════════
# sweep (+ bisection over w_keys, MORL Algorithm 3)
# ════════════════════════════════════════════════════════════════════════════

def bisect_targets(agent, inst, budget, points, build_dir, repeats, out_csv, done, generated):
    """points: {w_ops: keys_level}. Search every missing integer key level between neighbours."""
    def probe(w):
        key = (agent.name, inst.name, str(budget), f"{w:.6f}")
        if key in done:
            return done[key]
        row = measure_point(agent, inst, w, budget, build_dir, repeats, "bisection", generated)
        append_row(out_csv, row)
        lvl = fnum(row.get("final_keys_cost"))
        done[key] = int(lvl) if lvl is not None else None
        log(f"    bisect w_ops={w:.6f} -> keys={done[key]} [{row['status']}]")
        return done[key]

    def rec(w_hi, ks_hi, w_lo, ks_lo, target, found, depth):
        if depth >= MAX_BISECT_DEPTH or target in found:
            return
        w_mid = round((w_hi + w_lo) / 2, 10)
        ks = probe(w_mid)
        if ks is None:
            return
        found.add(ks)
        if ks == target:
            return
        if ks < target:     # moving toward w_hi (more speed) raises keys
            rec(w_hi, ks_hi, w_mid, ks, target, found, depth + 1)
        else:
            rec(w_mid, ks, w_lo, ks_lo, target, found, depth + 1)

    ordered = sorted((w, k) for w, k in points.items() if k is not None)
    found = set(k for _, k in ordered)
    for (w_lo, ks_lo), (w_hi, ks_hi) in zip(ordered, ordered[1:]):
        lo, hi = sorted((ks_lo, ks_hi))
        for target in range(lo + 1, hi):
            if target not in found:
                rec(w_hi, ks_hi, w_lo, ks_lo, target, found, 0)


def cmd_sweep(args):
    jobs = plan_jobs(args)
    build_dir = (REPO / args.build_dir).resolve()
    all_inst = all_instances(args.benchmarks.split(",") if args.benchmarks else None)
    if args.num_shards > 1:
        all_inst = [i for n, i in enumerate(all_inst) if n % args.num_shards == args.shard]
    generated = set()
    for agent_name, prefs, bisect in jobs:
        agent = AGENTS[agent_name]
        out_csv = csv_path(agent.name, args.shard if args.num_shards > 1 else None)
        done = {}
        for r in read_rows([out_csv]):
            if r.get("status") == "ok" or not args.retry_failed:
                done[row_key(r)] = int(fnum(r["final_keys_cost"])) if fnum(r.get("final_keys_cost")) is not None else None
        budgets = agent.budgets if args.budgets is None else (
            ["none"] if agent.budgets == ["none"] else [int(b) for b in args.budgets.split(",")])
        for inst in all_inst:
            for budget in budgets:
                levels = {}
                for w in prefs:
                    key = (agent.name, inst.name, str(budget), f"{w:.6f}")
                    if key in done:
                        levels[w] = done[key]
                        continue
                    log(f"{agent.name} | {inst.name} | B={budget} | w_ops={w}")
                    if args.dry_run:
                        continue
                    row = measure_point(agent, inst, w, budget, build_dir, args.repeats, "grid", generated)
                    append_row(out_csv, row)
                    lvl = fnum(row.get("final_keys_cost"))
                    levels[w] = done[key] = int(lvl) if lvl is not None else None
                    log(f"    -> {row['status']} time={row.get('circuit_execution_time_s')}s "
                        f"keys={row.get('rotation_keys_size_mb')}MB noise_rem={row.get('remaining_noise_budget')}")
                if bisect and not args.no_bisect and not args.dry_run:
                    bisect_targets(agent, inst, budget, levels, build_dir, args.repeats, out_csv, done, generated)


def plan_jobs(args):
    """Merge the selected experiments into {agent: (prefs, bisect)} so shared runs happen once."""
    names = list(EXPERIMENTS) if args.experiments == "all" else args.experiments.split(",")
    merged = {}
    for exp in names:
        for agent, prefs, bisect in EXPERIMENTS[exp]:
            p, b = merged.get(agent, (set(), False))
            merged[agent] = (p | set(prefs), b or bisect)
    if args.agents:
        keep = set(args.agents.split(","))
        merged = {a: v for a, v in merged.items() if a in keep}
    return [(a, sorted(p, reverse=True), b) for a, (p, b) in merged.items()]


def cmd_plan(args):
    n_inst = len(all_instances(args.benchmarks.split(",") if args.benchmarks else None))
    print(f"Benchmark instances: {n_inst}   budgets: {NOISE_BUDGETS}   prefs: {PREFS}\n")
    total = 0
    for agent, prefs, bisect in plan_jobs(args):
        a = AGENTS[agent]
        n = n_inst * len(a.budgets) * len(prefs)
        total += n
        print(f"  {agent:<10} framework={a.framework:<9} budgets={len(a.budgets)} prefs={len(prefs):>2} "
              f"bisect={'yes' if bisect else 'no ':<3} grid points={n:>5}   {a.note}")
        shown = os.path.relpath(a.model, REPO) if a.model else "(config default)"
        print(f"  {'':<10} model: {shown}{'' if not a.model or Path(a.model).is_file() else '   [not trained yet]'}")
    print(f"\nGrid compile+run points (before bisection): {total}")
    print("Experiments selected:", args.experiments)


# ════════════════════════════════════════════════════════════════════════════
# preflight
# ════════════════════════════════════════════════════════════════════════════

def check_keys_cost_bug():
    """fheEnvUnified.get_split_costs must return a non-zero keys cost for a rotating expression."""
    code = (
        "import sys; sys.path[:0]=[{rl!r},{py!r}]\n"
        "import pytrs.config; pytrs.config.framework='constrained'\n"
        "from fhe_rl.env_unified import fheEnvUnified\n"
        "ops, keys = fheEnvUnified.get_split_costs(None, '(VecAdd (<< (Vec a b c d) 1) (<< (Vec a b c d) 2))')\n"
        "print(keys)\n"
    ).format(rl=str(RL_DIR), py=str(RL_DIR / "pytrs"))
    r = subprocess.run([sys.executable, "-c", code], cwd=str(RL_DIR), stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, universal_newlines=True, timeout=600)
    if r.returncode != 0:
        return None, r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "import failed"
    return fnum(r.stdout.strip().splitlines()[-1]), ""


def cmd_preflight(args):
    ok = True
    build_dir = (REPO / args.build_dir).resolve()
    print(f"repo: {REPO}\nbuild: {build_dir}\n")

    keys, err = check_keys_cost_bug()
    if keys is None:
        print(f"[WARN] could not import fheEnvUnified to check the keys cost: {err}")
    elif keys == 0:
        ok = False
        print("[FAIL] fheEnvUnified.get_split_costs() returns C_keys = 0 for an expression with 2 rotations.\n"
              "       r_keys is always 0, so the preference w has no effect and the MORL experiments are void.\n"
              "       Fix in RL/fhe_rl/env_unified.py, get_split_costs():\n"
              "           from pytrs.cost import get_unique_rotations\n"
              "           ops  = calculate_cost(parsed)\n"
              "           keys = get_unique_rotations(parsed)\n"
              "       (pytrs.config.framework cannot fix it: cost.py imports a different `config` module.)")
    else:
        print(f"[ OK ] unified keys cost works (C_keys = {keys:g} for 2 distinct rotations)")

    for name in ("base", "kl", "env", "nbudget10", "uniform", "cycle2"):
        p = Path(AGENTS[name].model)
        print(f"[{' OK ' if p.is_file() else 'TODO'}] model {name:<10} {p.relative_to(REPO)}")
    for key, fname in (("morl", "agent_pareto_2_full.zip"), ("original", "agent_dynamic_llm_data.zip")):
        p = MODELS_DIR / fname
        print(f"[{' OK ' if p.is_file() else 'FAIL'}] reference {key:<8} {p.relative_to(REPO)}")
        ok &= p.is_file()

    missing = [i.binary for i in all_instances() if not (build_dir / "benchmarks" / i.binary / i.binary).is_file()]
    if missing:
        ok = False
        print(f"[FAIL] benchmark binaries missing in {build_dir}: {sorted(set(missing))}\n"
              f"       cmake -S . -B {args.build_dir} && cmake --build {args.build_dir}")
    else:
        print("[ OK ] all benchmark binaries built")
    seal = subprocess.run("cmake --find-package -DNAME=SEAL -DCOMPILER_ID=GNU -DLANGUAGE=CXX -DMODE=EXIST",
                          shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    print(f"[{' OK ' if 'SEAL found' in seal.stdout else 'WARN'}] SEAL 4.1 visible to CMake "
          "(needed for backend 0 / real noise budget)")
    no_runner = [i.binary for i in all_instances()
                 if (build_dir / "benchmarks" / i.binary).is_dir()
                 and not (build_dir / "benchmarks" / i.binary / "he" / "main.cpp").is_file()]
    if no_runner:
        print(f"[WARN] no he/main.cpp yet for {sorted(set(no_runner))}; it must exist after a SEAL "
              "(backend 0) compile, otherwise those rows end with status=no_seal_runner")
    print("\nPREFLIGHT", "PASSED" if ok else "FAILED")
    return 0 if ok else 1


# ════════════════════════════════════════════════════════════════════════════
# train: one SLURM job per unified variant
# ════════════════════════════════════════════════════════════════════════════

SBATCH_HEADER = """#!/bin/bash
#SBATCH -J um-{variant}
#SBATCH -p {partition}
#SBATCH -c {cpus}
#SBATCH --mem {mem}
#SBATCH -t {time}
#SBATCH -o {logs}/train_{variant}.%j.out
#SBATCH -e {logs}/train_{variant}.%j.err
{extra}
set -eo pipefail
{activate}
export PYTHONUNBUFFERED=1
PROJ_ROOT="{repo}"
cd "$PROJ_ROOT/RL"
export PYTHONPATH="$PROJ_ROOT/RL:$PROJ_ROOT/RL/pytrs:${{PYTHONPATH:-}}"
"""


def cmd_train(args):
    if not args.force:
        keys, _ = check_keys_cost_bug()
        if keys == 0:
            print("Refusing to train: the unified keys cost is always 0 (run `preflight` for the fix). "
                  "Use --force to train anyway.")
            return 1
    jobs_dir = OUT_DIR / "jobs"
    logs = OUT_DIR / "logs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)
    budgets = ",".join(str(b) for b in TRAIN_BUDGETS)
    for variant in args.variants.split(","):
        a = AGENTS[variant]
        if not a.train_flags:
            print(f"skip {variant}: not a trainable unified variant")
            continue
        f = a.train_flags
        steps = args.timesteps or f["timesteps"]
        script = SBATCH_HEADER.format(variant=variant, partition=args.partition, cpus=args.cpus, mem=args.mem,
                                      time=args.time, logs=logs, extra=args.sbatch_extra or "",
                                      activate=args.activate, repo=REPO)
        script += f"""
python -u -m fhe_rl --framework unified train \\
    --dataset {args.dataset} \\
    --constraint noise --budgets {budgets} \\
    --timesteps {steps} --num_envs {args.cpus} --eval_freq {args.eval_freq} \\
    --method {f['method']} --algo {f['algo']} \\
    --budget_encoding {f['budget_encoding']} --policy_variant {f['policy_variant']} \\
    --embedder {f['embedder']} --n_pref 11 \\
    --n_cycle {f['n_cycle']} --n_budget {f['n_budget']} \\
    --lambda_env {f['lambda_env']} --lambda_kl {f['lambda_kl']} \\
    --fresh_start

TAG={'gnn' if f['embedder'] == 'gnn' else 'trae'}
OUT="model_${{SLURM_JOB_ID:-jobid}}_{f['method']}_{f['policy_variant']}_${{TAG}}.zip"
cp "$OUT" "{a.model}"
echo "saved {a.model}"
"""
        path = jobs_dir / f"train_{variant}.sbatch"
        path.write_text(script)
        print(f"wrote {path.relative_to(REPO)}   ({a.note})")
        if args.submit:
            r = subprocess.run(["sbatch", str(path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               universal_newlines=True)
            print("   ", (r.stdout or r.stderr).strip())
    return 0


# ════════════════════════════════════════════════════════════════════════════
# slurm: parallel sweep shards (each shard uses its own copy of the build dir)
# ════════════════════════════════════════════════════════════════════════════

def cmd_slurm(args):
    jobs_dir = OUT_DIR / "jobs"
    logs = OUT_DIR / "logs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)
    extra = []
    for flag in ("experiments", "agents", "benchmarks", "budgets"):
        v = getattr(args, flag)
        if v:
            extra.append(f"--{flag} {v}")
    if args.no_bisect:
        extra.append("--no-bisect")
    script = f"""#!/bin/bash
#SBATCH -J um-sweep
#SBATCH -p {args.partition}
#SBATCH -c 1
#SBATCH --mem {args.mem}
#SBATCH -t {args.time}
#SBATCH --array=0-{args.shards - 1}
#SBATCH -o {logs}/sweep.%A_%a.out
#SBATCH -e {logs}/sweep.%A_%a.err
{args.sbatch_extra or ''}
set -eo pipefail
{args.activate}
export PYTHONUNBUFFERED=1
cd "{REPO}"
SHARD=${{SLURM_ARRAY_TASK_ID}}
BUILD="build_shard${{SHARD}}"
# benchmarks write ../expression.txt into their build dir, so shards cannot share one
if [ ! -d "$BUILD" ]; then cp -r build "$BUILD"; fi
python -u scripts/unified_morl_experiments.py sweep --build-dir "$BUILD" \\
    --shard "$SHARD" --num-shards {args.shards} --repeats {args.repeats} {' '.join(extra)}
"""
    path = jobs_dir / "sweep_array.sbatch"
    path.write_text(script)
    print(f"wrote {path.relative_to(REPO)} ({args.shards} shards)")
    if args.submit:
        r = subprocess.run(["sbatch", str(path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           universal_newlines=True)
        print((r.stdout or r.stderr).strip())
    return 0


# ════════════════════════════════════════════════════════════════════════════
# metrics: IC, normalized HV, normalized SP, EU (+ constraint metrics)
# ════════════════════════════════════════════════════════════════════════════

def pareto_front(points):
    """points: list of (t, k) minimisation; returns sorted unique non-dominated points."""
    pts = sorted(set(points))
    front, best_k = [], math.inf
    for t, k in pts:                       # sorted by t then k
        if k < best_k:
            front.append((t, k))
            best_k = k
    return front


def hypervolume_2d(front, ref=(1.1, 1.1)):
    hv, prev_k = 0.0, ref[1]
    for t, k in sorted(front):
        if t >= ref[0] or k >= prev_k:
            continue
        hv += (ref[0] - t) * (prev_k - k)
        prev_k = k
    return hv


def sparsity(front):
    if len(front) < 2:
        return 0.0
    total = 0.0
    for j in range(2):
        vals = sorted(p[j] for p in front)
        total += sum((a - b) ** 2 for a, b in zip(vals[1:], vals[:-1]))
    return total / (len(front) - 1)


def expected_utility(front, prefs=PREFS):
    if not front:
        return None
    return statistics.mean(min(w * t + (1 - w) * k for t, k in front) for w in prefs)


def time_value(r, time_col):
    return fnum(r.get(time_col))


def compute_bounds(rows, time_col):
    """Per-benchmark normalisation bounds (T_min, T_max, K_max), shared by every agent and budget."""
    bounds = {}
    for r in rows:
        t, k = time_value(r, time_col), fnum(r.get("rotation_keys_size_mb"))
        if r.get("status") != "ok" or t is None or k is None:
            continue
        b = bounds.setdefault(r["benchmark"], [math.inf, -math.inf, 0.0])
        b[0], b[1], b[2] = min(b[0], t), max(b[1], t), max(b[2], k)
    return bounds


def normalise(t, k, bnd):
    tmin, tmax, kmax = bnd
    nt = (t - tmin) / (tmax - tmin) if tmax > tmin else 0.0
    nk = k / kmax if kmax > 0 else 0.0
    return nt, nk


def cmd_metrics(args):
    rows = read_rows(sorted((OUT_DIR / "raw").glob("*.csv")))
    if not rows:
        print(f"no sweep CSVs in {OUT_DIR / 'raw'}")
        return 1
    bounds = compute_bounds(rows, args.time_col)
    groups = {}
    for r in rows:
        groups.setdefault((r["agent"], r["benchmark"], r["budget"]), []).append(r)
    out_rows = []
    for (agent, bench, budget), rs in sorted(groups.items()):
        ok = [r for r in rs if r.get("status") == "ok"]
        bnd = bounds.get(bench)
        norm = []
        for r in ok:
            t, k = time_value(r, args.time_col), fnum(r.get("rotation_keys_size_mb"))
            if t is not None and k is not None and bnd:
                norm.append(normalise(t, k, bnd))
        front = pareto_front(norm)
        def rate(col):
            vals = [str(r.get(col)).lower() == "true" for r in ok if r.get(col) not in ("", None)]
            return round(sum(vals) / len(vals), 4) if vals else ""
        out_rows.append({
            "agent": agent, "benchmark": bench, "budget": budget, "points": len(rs), "ok_points": len(ok),
            "IC": len(front),
            "HV": round(hypervolume_2d(front) / 1.21, 4) if front else "",
            "SP": round(sparsity(front) / 2, 4) if front else "",
            "EU": round(expected_utility(front), 4) if front else "",
            "T_min": bnd[0] if bnd else "", "T_max": bnd[1] if bnd else "", "K_max": bnd[2] if bnd else "",
            "est_violation_rate": rate("est_violated"),
            "measured_violation_rate": rate("measured_violated"),
            "rollback_rate": rate("rollback_used"),
            "min_remaining_noise": min((fnum(r.get("remaining_noise_budget")) for r in ok
                                        if fnum(r.get("remaining_noise_budget")) is not None), default=""),
        })
    path = OUT_DIR / "metrics.csv"
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0]))
        w.writeheader()
        w.writerows(out_rows)
    with open(OUT_DIR / "bounds.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["benchmark", "T_min", "T_max", "K_max"])
        for b, (tmin, tmax, kmax) in sorted(bounds.items()):
            w.writerow([b, tmin, tmax, kmax])
    print(f"wrote {path.relative_to(REPO)} ({len(out_rows)} agent x benchmark x budget groups) "
          f"and bounds.csv (time column: {args.time_col})")
    return 0


# ════════════════════════════════════════════════════════════════════════════
# report: tables + figures per experiment
# ════════════════════════════════════════════════════════════════════════════

def cmd_report(args):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = [r for r in read_rows(sorted((OUT_DIR / "raw").glob("*.csv"))) if r.get("status") == "ok"]
    if not rows:
        print("no successful rows yet")
        return 1
    fig_dir = OUT_DIR / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    tc = args.time_col
    md = ["# Unified (noise budget) vs MORL — experiment report", "",
          f"Time column: `{tc}`. Budgets in used BFV bits; `none` = budget-agnostic reference agent.", ""]

    def sel(agent=None, w=None, budget=None, bench=None, source=None):
        out = rows
        if agent is not None:
            out = [r for r in out if r["agent"] == agent]
        if w is not None:
            out = [r for r in out if abs(float(r["w_ops"]) - w) < 1e-9]
        if budget is not None:
            out = [r for r in out if str(r["budget"]) == str(budget)]
        if bench is not None:
            out = [r for r in out if r["benchmark"] == bench]
        if source is not None:
            out = [r for r in out if r["source"] == source]
        return out

    def mean(vals):
        vals = [v for v in vals if v is not None]
        return statistics.mean(vals) if vals else None

    budgets = [b for b in NOISE_BUDGETS if sel(agent="base", budget=b)]

    # ── B1: Direct Mode w=[1,0] ───────────────────────────────────────────
    md += ["## B1 — Direct Mode at w = [1, 0]", "",
           "| benchmark | original t (s) | original keys (MB) | MORL t | MORL keys | "
           + " | ".join(f"unified B={b} t | keys" for b in budgets) + " |",
           "|" + "---|" * (5 + 2 * len(budgets))]
    benches = sorted({r["benchmark"] for r in sel(w=1.0)})
    for bench in benches:
        cells = [bench]
        for agent, budget in [("original", "none"), ("morl", "none")] + [("base", b) for b in budgets]:
            r = sel(agent=agent, w=1.0, budget=budget, bench=bench, source="grid")
            cells += [r[0].get(tc, "") if r else "", r[0].get("rotation_keys_size_mb", "") if r else ""]
        md.append("| " + " | ".join(str(c) for c in cells) + " |")
    md.append("")

    # ── B2a: trade-off curve per budget ───────────────────────────────────
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    for label, agent, budget in [("MORL", "morl", "none")] + [(f"unified B={b}", "base", b) for b in budgets]:
        xs, ts, ks = [], [], []
        for w in PREFS:
            rs = sel(agent=agent, w=w, budget=budget, source="grid")
            if rs:
                xs.append(round(1 - w, 1))
                ts.append(mean(fnum(r.get(tc)) for r in rs))
                ks.append(mean(fnum(r.get("rotation_keys_size_mb")) for r in rs))
        if xs:
            ax[0].plot(xs, ts, marker="o", label=label)
            ax[1].plot(xs, ks, marker="o", label=label)
    ax[0].set_xlabel("w_keys"); ax[0].set_ylabel("mean execution time (s)")
    ax[1].set_xlabel("w_keys"); ax[1].set_ylabel("mean rotation-key size (MB)")
    ax[0].legend(fontsize=7)
    fig.tight_layout(); fig.savefig(fig_dir / "B2a_tradeoff_curve.png", dpi=150); plt.close(fig)
    md += ["## B2a — trade-off curve", "", "![](figures/B2a_tradeoff_curve.png)", ""]

    # ── B2b: three-preference comparison per budget ───────────────────────
    md += ["## B2b — w_ops ∈ {1.0, 0.9, 0.8}", ""]
    for budget in budgets:
        md += [f"**Budget {budget}**", "", "| benchmark | " + " | ".join(f"w={w} t | keys" for w in B2B_PREFS) + " |",
               "|" + "---|" * (1 + 2 * len(B2B_PREFS))]
        for bench in sorted({r["benchmark"] for r in sel(agent="base", budget=budget)}):
            cells = [bench]
            for w in B2B_PREFS:
                r = sel(agent="base", w=w, budget=budget, bench=bench, source="grid")
                cells += [r[0].get(tc, "") if r else "", r[0].get("rotation_keys_size_mb", "") if r else ""]
            md.append("| " + " | ".join(str(c) for c in cells) + " |")
        md.append("")

    # ── B2c: frontier plots (Menu Mode incl. bisection) ───────────────────
    md += ["## B2c — Pareto frontiers (grid + bisection)", ""]
    for bench in B2C_INSTANCES:
        fig, ax = plt.subplots(figsize=(5, 4))
        drawn = False
        for label, agent, budget in [("MORL", "morl", "none")] + [(f"B={b}", "base", b) for b in budgets]:
            pts = [(fnum(r.get(tc)), fnum(r.get("rotation_keys_size_mb")), float(r["w_ops"]))
                   for r in sel(agent=agent, budget=budget, bench=bench)]
            pts = [p for p in pts if p[0] is not None and p[1] is not None]
            if not pts:
                continue
            front = pareto_front([(t, k) for t, k, _ in pts])
            ax.scatter([p[0] for p in pts], [p[1] for p in pts], s=12, alpha=0.4)
            ax.plot([p[0] for p in front], [p[1] for p in front], marker="o", label=label)
            drawn = True
        if drawn:
            ax.set_title(bench); ax.set_xlabel("execution time (s)"); ax.set_ylabel("rotation keys (MB)")
            ax.legend(fontsize=7); fig.tight_layout()
            fig.savefig(fig_dir / f"B2c_front_{bench}.png", dpi=150)
            md += [f"![](figures/B2c_front_{bench}.png)", ""]
        plt.close(fig)

    # ── B2d + constraint: metrics table ───────────────────────────────────
    mpath = OUT_DIR / "metrics.csv"
    if mpath.is_file():
        mrows = read_rows([mpath])
        md += ["## B2d — MORL metrics (Menu Mode) and noise constraint", "",
               "| agent | budget | benchmark | IC | HV | SP | EU | est. viol. | measured viol. | rollback | min rem. noise |",
               "|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in mrows:
            if r["agent"] in ("base", "morl"):
                md.append("| " + " | ".join(str(r[c]) for c in (
                    "agent", "budget", "benchmark", "IC", "HV", "SP", "EU", "est_violation_rate",
                    "measured_violation_rate", "rollback_rate", "min_remaining_noise")) + " |")
        md.append("")
    else:
        md += ["_Run `metrics` first for the B2d table._", ""]

    # ── B4 / B5 / A3: agent comparisons ───────────────────────────────────
    def agent_compare(title, agents, w_values, col, fname, ylabel):
        nonlocal md
        md += [f"## {title}", ""]
        for budget in budgets:
            fig, ax = plt.subplots(figsize=(7, 3.5))
            any_line = False
            for agent in agents:
                xs, ys = [], []
                for w in w_values:
                    rs = sel(agent=agent, w=w, budget=budget, source="grid")
                    if rs:
                        xs.append(round(1 - w, 1)); ys.append(mean(fnum(r.get(col)) for r in rs))
                if xs:
                    ax.plot(xs, ys, marker="o", label=agent); any_line = True
            if any_line:
                ax.set_xlabel("w_keys"); ax.set_ylabel(ylabel); ax.set_title(f"budget {budget}")
                ax.legend(fontsize=7); fig.tight_layout()
                fig.savefig(fig_dir / f"{fname}_B{budget}.png", dpi=150)
                md.append(f"![](figures/{fname}_B{budget}.png)")
            plt.close(fig)
        md.append("")

    agent_compare("B4 — exploration bonuses: execution time", ["base", "kl", "env"], B4_PREFS, tc,
                  "B4_exec_time", "mean execution time (s)")
    agent_compare("B4 — exploration bonuses: compile time", ["base", "kl", "env"], B4_PREFS, "compile_time_s",
                  "B4_compile_time", "mean compile time (s)")
    agent_compare("B5 — N_budget 5 vs 10: execution time", ["base", "nbudget10"], PREFS, tc,
                  "B5_exec_time", "mean execution time (s)")
    agent_compare("B5 — N_budget 5 vs 10: key size", ["base", "nbudget10"], PREFS, "rotation_keys_size_mb",
                  "B5_keys", "mean rotation-key size (MB)")
    agent_compare("A3 — preference sampling: execution time", ["base", "uniform", "cycle2"], PREFS, tc,
                  "A3_exec_time", "mean execution time (s)")

    # ── noise: estimated vs measured ──────────────────────────────────────
    est = [(fnum(r.get("est_noise")), fnum(r.get("measured_used_bits"))) for r in sel(agent="base")]
    est = [p for p in est if None not in p]
    if est:
        fig, ax = plt.subplots(figsize=(4.5, 4))
        ax.scatter([p[1] for p in est], [p[0] for p in est], s=10)
        lim = max(max(p) for p in est)
        ax.plot([0, lim], [0, lim], "k--", lw=1)
        ax.set_xlabel("measured used bits (369 - remaining)"); ax.set_ylabel("estimated used bits")
        fig.tight_layout(); fig.savefig(fig_dir / "noise_estimated_vs_measured.png", dpi=150); plt.close(fig)
        mae = statistics.mean(abs(a - b) for a, b in est)
        md += ["## Noise estimator vs SEAL", "", f"MAE = {mae:.2f} bits over {len(est)} circuits.", "",
               "![](figures/noise_estimated_vs_measured.png)", ""]

    path = OUT_DIR / "REPORT.md"
    path.write_text("\n".join(md))
    print(f"wrote {path.relative_to(REPO)} and {len(list(fig_dir.glob('*.png')))} figures")
    return 0


# ════════════════════════════════════════════════════════════════════════════
# CLI
# ════════════════════════════════════════════════════════════════════════════

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def selection(sp):
        sp.add_argument("--experiments", default="all", help="all or comma list of " + ",".join(EXPERIMENTS))
        sp.add_argument("--agents", default=None, help="restrict to these agents (comma list)")
        sp.add_argument("--benchmarks", default=None, help="instance names or families, e.g. dot_product,sort_3")
        sp.add_argument("--budgets", default=None, help="override budgets for unified agents, e.g. 236,9000000")

    def cluster(sp, mem, time_):
        sp.add_argument("--partition", default="compute")
        sp.add_argument("--mem", default=mem)
        sp.add_argument("--time", default=time_)
        sp.add_argument("--activate", default="source ~/miniconda3/bin/activate && conda activate chehabEnv",
                        help="shell line that activates the Python env inside the job")
        sp.add_argument("--sbatch-extra", default="", help="extra #SBATCH lines, e.g. '#SBATCH -q c2'")
        sp.add_argument("--submit", action="store_true", help="call sbatch on the written script")

    sp = sub.add_parser("plan"); selection(sp)
    sp = sub.add_parser("preflight"); sp.add_argument("--build-dir", default="build")

    sp = sub.add_parser("train")
    sp.add_argument("--variants", default="base,kl,env,nbudget10,uniform,cycle2")
    sp.add_argument("--timesteps", type=int, default=None, help="override 2M timesteps (Table 5.1)")
    sp.add_argument("--cpus", type=int, default=8)
    sp.add_argument("--eval-freq", type=int, default=30000)
    sp.add_argument("--dataset", default="./fhe_rl/datasets/final_llm_dataset.txt")
    sp.add_argument("--force", action="store_true", help="train even if the keys-cost bug is detected")
    cluster(sp, "128GB", "4-00:00:00")

    sp = sub.add_parser("sweep"); selection(sp)
    sp.add_argument("--build-dir", default="build")
    sp.add_argument("--repeats", type=int, default=1, help="SEAL executions per point (median)")
    sp.add_argument("--shard", type=int, default=0)
    sp.add_argument("--num-shards", type=int, default=1)
    sp.add_argument("--no-bisect", action="store_true")
    sp.add_argument("--retry-failed", action="store_true", help="re-run points whose status is not ok")
    sp.add_argument("--dry-run", action="store_true")

    sp = sub.add_parser("slurm"); selection(sp)
    sp.add_argument("--shards", type=int, default=8)
    sp.add_argument("--repeats", type=int, default=1)
    sp.add_argument("--no-bisect", action="store_true")
    cluster(sp, "64GB", "7-00:00:00")

    for name in ("metrics", "report"):
        sp = sub.add_parser(name)
        sp.add_argument("--time-col", default="circuit_execution_time_s",
                        choices=["circuit_execution_time_s", "total_execution_time_s"])

    args = p.parse_args(argv)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    handler = {"plan": cmd_plan, "preflight": cmd_preflight, "train": cmd_train, "sweep": cmd_sweep,
               "slurm": cmd_slurm, "metrics": cmd_metrics, "report": cmd_report}[args.cmd]
    return handler(args) or 0


if __name__ == "__main__":
    sys.exit(main())
