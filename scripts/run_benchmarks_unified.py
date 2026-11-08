#!/usr/bin/env python3
"""Real compile + SEAL execution evaluation of the unified joint agent.

Same protocol as the original MORL and constrained `run_benchmarks.py`: every C++
benchmark is compiled by CHEHAB with the RL vectorizer, the generated SEAL program is
built and run, and the measured costs are written to a CSV. The unified agent gets
the preference w = [w_ops, 1 - w_ops] from the compiler and the noise budget / model
from the environment (FHE_RL_BUDGET / FHE_RL_MODEL, read by `fhe_rl run`).

    python scripts/run_benchmarks_unified.py --model M.zip --budget 369 \
        --benchmarks dot_product --output RL/test_results/e2e_dot_b369.csv

Each run works in its own copy of the built benchmarks, <repo>/e2e_<tag>/benchmarks/,
because the compiler exchanges files with the agent through ../expression.txt and the
generated program goes to he/: runs sharing a folder would overwrite each other.
Requires the CHEHAB build (build/benchmarks/<bench>/<bench>) and SEAL 4.1.
"""
import argparse
import csv
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Benchmarks and sizes reported by the original MORL evaluation (results/generate_graphs.py)
SUITE = {
    "box_blur": [3, 4, 5], "gx_kernel": [3, 4, 5], "gy_kernel": [3, 4, 5],
    "roberts_cross": [3, 4, 5], "matrix_mul": [3, 4, 5],
    "dot_product": [4, 8, 16, 32], "hamming_dist": [4, 8, 16, 32], "l2_distance": [4, 8, 16, 32],
    "lin_reg": [4, 8, 16, 32], "poly_reg": [4, 8, 16, 32],
    "max": [3, 4, 5], "sort": [3, 4],
}
POLY = "polynomials_coyote"
POLY_CONFIGS = [(regime, depth) for regime in ("50-50", "100-50", "100-100") for depth in (5, 10)]
POLY_INSTANCE = 1
OPERATIONS = ["add", "sub", "multiply_plain", "rotate_rows", "negate", "multiply"]
PREFS = [[round(1.0 - i / 10, 1), round(i / 10, 1)] for i in range(10)]   # generate_pref_list(11)

EXEC_METRICS = {   # line prefix printed by the generated main.cpp -> CSV column
    "circuit_execution_time_(ms):": "circuit_execution_time (s)",
    "galois_keys_generation_time_(ms):": "galois_keys_generation_time (s)",
    "total_execution_time_(ms):": "total_execution_time (s)",
    "rotation_keys_size_(MB):": "rotation_keys_size (MB)",
    "Remaining_noise_budget:": "Remaining_noise_budget",
    "peak_ram_memory_(MB):": "peak_ram (MB)",
}
RL_FIELDS = ["initial_ops", "initial_keys", "initial_noise_est", "agent_ops", "agent_keys",
             "agent_noise_est", "agent_violated", "safe_ops", "safe_keys", "safe_noise_est",
             "safety_activated", "best_valid_step", "rl_steps", "rl_time_ms"]
COLUMNS = (["benchmark", "slot_count", "w_ops", "w_keys", "budget", "status"] + OPERATIONS
           + ["Depth", "Multiplicative Depth", "compile_time (s)"] + list(EXEC_METRICS.values())
           + ["exec_runs", "outputs_match"] + RL_FIELDS
           + ["method", "rollback"])   # appended last so older CSV readers are unaffected

ANSI = re.compile(r"\x1b\[[0-9;]*m")


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def prepare_work_dir(work, benches):
    """Copy the built benchmarks into <work>/benchmarks (one level below the repo root,
    so the compiler still finds RL/ at ../../../RL)."""
    if work.parent.resolve() != REPO.resolve():
        sys.exit(f"--work-dir must be a direct child of the repo root ({REPO}), got {work}")
    for bench in benches:
        src = REPO / "build" / "benchmarks" / bench
        dst = work / "benchmarks" / bench
        if not (src / bench).is_file():
            sys.exit(f"Benchmark binary not built: {src / bench}  (run scripts/build_e2e_benchmarks.sh)")
        if not dst.exists():
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("build", "heongpu", "CMakeFiles"))
        # Use the io generator from the sources: `make` of a benchmark folder does not refresh
        # the copy in build/, so it can be outdated (it writes the expected outputs)
        gen = REPO / "benchmarks" / bench / f"generate_{bench}.py"
        if gen.is_file():
            shutil.copy2(gen, dst / gen.name)
    assert (work / "benchmarks" / benches[0] / ".." / ".." / ".." / "RL").resolve() == (REPO / "RL").resolve()


def run(cmd, cwd, env=None, timeout=None):
    return subprocess.run(cmd, cwd=cwd, env=env, timeout=timeout, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def compile_point(bench, bdir, slot, w_ops, env, timeout, poly_cfg=None):
    """Compile once with the RL vectorizer. Returns (ok, compile_s, depth, mult_depth, output)."""
    if poly_cfg:
        regime, depth = poly_cfg
        cmd = [f"./{bench}", str(depth), str(POLY_INSTANCE), regime, "1", "unified", "1", "0", "1", "0", "1", "0", str(w_ops)]
    else:
        gen = bdir / f"generate_{bench}.py"
        if gen.is_file():
            run([sys.executable, gen.name, "--slot_count", str(slot)], cwd=bdir, timeout=600)
        cmd = [f"./{bench}", "1", str(slot), "unified", "1", "0", "1", "1", "1", "0", str(w_ops)]
    gen_cpp = bdir / "he" / "_gen_he_fhe.cpp"
    for f in (gen_cpp, bdir / "he" / "_gen_he_fhe.hpp"):   # never measure a stale circuit
        f.unlink(missing_ok=True)
    t0 = time.perf_counter()
    proc = run(cmd, cwd=bdir, env=env, timeout=timeout)
    wall = time.perf_counter() - t0
    out = ANSI.sub("", proc.stdout)
    compile_ms = None
    for line in out.splitlines():
        m = re.match(r"^\s*([0-9.]+) ms\s*$", line)
        if m:
            compile_ms = float(m.group(1))
    dm = re.search(r"max:\s*\((\d+),\s*(\d+)\)", out)
    ok = proc.returncode == 0 and gen_cpp.is_file() and gen_cpp.stat().st_size > 0
    return (ok, (compile_ms / 1000.0) if compile_ms is not None else wall,
            int(dm.group(1)) if dm else None, int(dm.group(2)) if dm else None, out)


def build_and_execute(bdir, seal_dir, cxx, repeats):
    """Build the generated SEAL program and run it `repeats` times (first run = warm-up)."""
    he = bdir / "he"
    build = he / "build"
    if not (build / "Makefile").is_file():
        cfg = ["cmake", "-S", ".", "-B", "build", "-DCMAKE_BUILD_TYPE=Release"]
        if seal_dir:
            cfg.append(f"-DSEAL_DIR={seal_dir}")
        if cxx:
            cfg.append(f"-DCMAKE_CXX_COMPILER={cxx}")
        p = run(cfg, cwd=he, timeout=1800)
        if p.returncode != 0:
            return None, "he-configure-failed: " + p.stdout[-400:]
    p = run(["cmake", "--build", "build", "-j", str(os.cpu_count() or 2)], cwd=he, timeout=3600)
    if p.returncode != 0:
        return None, "he-build-failed: " + p.stdout[-400:]

    samples = {col: [] for col in EXEC_METRICS.values()}
    outputs_match = None
    for i in range(repeats):
        p = run(["./main"], cwd=build, timeout=7200)
        if p.returncode != 0:
            return None, "execution-failed: " + p.stdout[-400:]
        if i == 0 and repeats > 1:
            continue
        for line in p.stdout.splitlines():
            for prefix, col in EXEC_METRICS.items():
                if line.strip().startswith(prefix):
                    try:
                        samples[col].append(float(line.split(":", 1)[1].split()[0]))
                    except (IndexError, ValueError):
                        pass
        outputs_match = check_outputs(bdir, p.stdout)
    res = {}
    for col, vals in samples.items():
        if vals:
            v = statistics.median(vals)
            res[col] = round(v / 1000.0, 4) if col.endswith("(s)") else v
    res["exec_runs"] = max(repeats - 1, 1)
    res["outputs_match"] = outputs_match
    return res, "ok"


PLAIN_MODULUS = 786433   # PlainModulus::Batching(16384, 20) in the generated programs


def check_outputs(bdir, stdout):
    """Decrypted outputs printed by main vs the expected values of the benchmark.

    Expected values: output lines of fhe_io_example.txt ("<name> <is_cipher> <values...>").
    Printed values: lines "<name> <is_cipher> <is_signed> <values...>" for the output
    names of the compiler's he/fhe_io_example_adapted.txt (the compiler renames outputs,
    e.g. output -> c8). Values are compared modulo the plain modulus (negative results).
    The outputs are matched one by one when their number is unchanged; when the
    vectorizer packed several scalar outputs into one vector (e.g. box blur: 9 outputs ->
    1 vector of 9 slots), all expected values, in order, are compared with the packed slots.
    Returns True / False, or None when there are no expected values (polynomial trees:
    their generator writes no expected result).
    """
    if bdir.name == POLY:
        return None
    try:
        orig = (bdir / "fhe_io_example.txt").read_text().split("\n")
        n_in, n_out = int(orig[0].split()[1]), int(orig[0].split()[2])
        expected = [[int(float(x)) % PLAIN_MODULUS for x in line.split()[2:]]
                    for line in orig[1 + n_in:1 + n_in + n_out] if len(line.split()) > 2]
        adapted = (bdir / "he" / "fhe_io_example_adapted.txt").read_text().split("\n")
        a_in, a_out = int(adapted[0].split()[1]), int(adapted[0].split()[2])
        out_names = {line.split()[0] for line in adapted[1 + a_in:1 + a_in + a_out] if line.split()}
        got = [[int(float(x)) % PLAIN_MODULUS for x in line.split()[3:]]
               for line in stdout.splitlines() if line.split() and line.split()[0] in out_names]
        if not expected or not got:
            return None
        if len(got) != len(expected):          # outputs packed into vector(s) by the vectorizer
            flat_exp = [v for e in expected for v in e]
            flat_got = [v for g in got for v in g]
            return flat_got[:len(flat_exp)] == flat_exp
        remaining = list(got)
        for exp in expected:
            hit = next((g for g in remaining if g[:len(exp)] == exp), None)
            if hit is None:
                return False
            remaining.remove(hit)
        return True
    except Exception:
        return None


def count_ops(bdir):
    code = (bdir / "he" / "_gen_he_fhe.cpp").read_text()
    return {op: len(re.findall(rf"\b{op}", code)) for op in OPERATIONS}


def last_rl_record(log_path, n_before):
    try:
        lines = log_path.read_text().splitlines()
    except FileNotFoundError:
        return {}
    return json.loads(lines[-1]) if len(lines) > n_before else {}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True, help="unified joint agent .zip")
    ap.add_argument("--budget", type=int, required=True, help="noise budget (bits)")
    ap.add_argument("--train_budgets", default="230,236,369,9000000")
    ap.add_argument("--method", default="nato_sc",
                    help="constraint method the agent was trained with (nato_sc, margin_barrier, noise_masking, none)")
    ap.add_argument("--no-rollback", action="store_true",
                    help="compile the agent's final expression instead of the safety-rollback one")
    ap.add_argument("--benchmarks", default="all",
                    help=f"comma-separated subset of {list(SUITE) + [POLY]} (default: all)")
    ap.add_argument("--slots", default=None, help="override the sizes, e.g. '4,8'")
    ap.add_argument("--prefs", default=None, help="'w_ops,w_keys;...' (default: the 10 training preferences)")
    ap.add_argument("--exec_repeats", type=int, default=3, help="runs of the SEAL program; the first is a warm-up")
    ap.add_argument("--compile_timeout", type=int, default=7200)
    ap.add_argument("--work-dir", default=None, help="folder directly under the repo root (default: e2e_<tag>)")
    ap.add_argument("--seal-dir", default=os.environ.get("SEAL_DIR"), help="folder containing SEALConfig.cmake")
    ap.add_argument("--cxx", default=os.environ.get("FHE_E2E_CXX"), help="C++ compiler for the SEAL programs")
    ap.add_argument("--output", required=True, help="CSV file (appended row by row)")
    args = ap.parse_args()

    benches = list(SUITE) + [POLY] if args.benchmarks == "all" else [b.strip() for b in args.benchmarks.split(",")]
    unknown = [b for b in benches if b not in SUITE and b != POLY]
    if unknown:
        sys.exit(f"Unknown benchmarks: {unknown}")
    prefs = ([[float(x) for x in p.split(",")] for p in args.prefs.split(";")] if args.prefs else PREFS)
    model = str(Path(args.model).resolve())
    if not Path(model).is_file():
        sys.exit(f"Model not found: {model}")

    tag = f"b{args.budget}_{os.environ.get('SLURM_JOB_ID', 'local')}"
    work = REPO / (args.work_dir or f"e2e_{tag}")
    prepare_work_dir(work, benches)
    rl_log = work / "rl_log.jsonl"

    env = dict(os.environ)
    env.update({
        "FHE_RL_MODEL": model,
        "FHE_RL_BUDGET": str(args.budget),
        "FHE_RL_TRAIN_BUDGETS": args.train_budgets,
        "FHE_RL_CONSTRAINT": "noise",
        "FHE_RL_METHOD": args.method,
        "FHE_RL_ROLLBACK": "0" if args.no_rollback else "1",
        "FHE_RL_RUN_LOG": str(rl_log),
        "PYTHON": env.get("PYTHON") or sys.executable,   # otherwise the compiler may pick /usr/bin/python3
        "PYTHONPATH": f"{REPO / 'RL'}:{REPO / 'RL' / 'pytrs'}:{env.get('PYTHONPATH', '')}",
    })

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    new_file = not out.exists()
    fh = open(out, "a", newline="")
    writer = csv.DictWriter(fh, fieldnames=COLUMNS, extrasaction="ignore")
    if new_file:
        writer.writeheader()

    points = []
    for bench in benches:
        if bench == POLY:
            points += [(bench, None, cfg) for cfg in POLY_CONFIGS]
        else:
            sizes = [int(s) for s in args.slots.split(",")] if args.slots else SUITE[bench]
            points += [(bench, s, None) for s in sizes]

    log(f"Model {model} | budget {args.budget} | {len(points)} benchmark configs x {len(prefs)} preferences"
        f" | method {args.method} | rollback {'off' if args.no_rollback else 'on'}")
    log(f"Work dir {work} | output {out}")
    t_start = time.perf_counter()
    for bench, slot, poly_cfg in points:
        bdir = work / "benchmarks" / bench
        name = f"tree_{poly_cfg[0]}_{poly_cfg[1]}_{POLY_INSTANCE}" if poly_cfg else f"{bench}_{slot}"
        for w_ops, w_keys in prefs:
            row = {"benchmark": name, "slot_count": slot, "w_ops": w_ops, "w_keys": w_keys, "budget": args.budget,
                   "method": args.method, "rollback": not args.no_rollback}
            n_before = len(rl_log.read_text().splitlines()) if rl_log.exists() else 0
            try:
                ok, compile_s, depth, mdepth, cout = compile_point(
                    bench, bdir, slot, w_ops, env, args.compile_timeout, poly_cfg)
            except subprocess.TimeoutExpired:
                ok, cout = False, "compile-timeout"
            row.update(last_rl_record(rl_log, n_before))
            if not ok:
                row["status"] = "compile-failed" if cout != "compile-timeout" else "compile-timeout"
                log(f"{name} w={w_ops}: {row['status']}\n{cout[-1500:]}")
            else:
                row.update({"compile_time (s)": round(compile_s, 3), "Depth": depth, "Multiplicative Depth": mdepth})
                row.update(count_ops(bdir))
                try:
                    res, status = build_and_execute(bdir, args.seal_dir, args.cxx, args.exec_repeats)
                except subprocess.TimeoutExpired:
                    res, status = None, "execution-timeout"
                row["status"] = "ok" if res is not None else status.split(":")[0]
                if res:
                    row.update(res)
                else:
                    log(f"{name} w={w_ops}: {status}")
            writer.writerow(row)
            fh.flush()
            log(f"{name} w=[{w_ops},{w_keys}] {row['status']}: exec {row.get('circuit_execution_time (s)')} s, "
                f"keys {row.get('rotation_keys_size (MB)')} MB, noise left {row.get('Remaining_noise_budget')}, "
                f"rotations {row.get('rotate_rows')}, rollback {row.get('safety_activated')}")
    fh.close()
    log(f"Done in {(time.perf_counter() - t_start) / 60:.1f} min -> {out}")


if __name__ == "__main__":
    main()
