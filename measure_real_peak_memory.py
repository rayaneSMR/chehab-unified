#!/usr/bin/env python3
"""
Measure the REAL peak memory (process MaxRSS) of every expression in one or more dataset files.

    python3 measure_real_peak_memory.py --repo /path/to/chehab-unified \
        --inputs eval_general.txt eval_dnn.txt --out peak_memory_results.csv

HOW THE REPO MEASURES PEAK MEMORY (what this script reproduces; see RL/veclang_runner/run_pilot.py)
  1. expression  -> vectorized_code.txt / inputs.txt / fhe_io_example.txt   (random inputs 0..10, 1 ciphertext per variable)
  2. build/RL/veclang_runner/veclang_runner 1 1 1   (C++ CHEHAB code generator: CSE=1, const-folding=1, backend=1 Lattigo)
     -> generated_fhe.go   (Lattigo v5 CKKS: keygen, encrypt, evaluate the circuit, decrypt)
  3. go build, then run the binary in a FRESH process, 3 times.  The generated main() prints
        max_rss_(MB)            = getrusage(RUSAGE_SELF).ru_maxrss  -> kernel high-water mark of resident memory   <- REAL PEAK (primary)
        peak_ram_memory_(MB)    = polled /proc/self/statm sampler                                                  <- secondary
        rotation_keys_size_(MB)
  4. the median of the 3 max_rss values is the measured peak.  It includes everything resident in the process
     (Go runtime, parameters, keys, ciphertexts, GC slack), exactly what an OOM killer sees.
  The calibrated ESTIMATOR the RL agent trains on (RL/fhe_rl/memory.py: ckks_memory_estimator net bytes
  -> per-N-group calibration fitted on these measurements) is reported next to it for comparison.

INPUT FORMAT   one expression per line:  `<expr>:<name>`   (name optional)
OUTPUT         CSV, one row per expression (written incrementally; --resume continues an interrupted run).

REQUIREMENTS   Linux/macOS, Go >= 1.21 (internet on first run to fetch lattigo v5.0.7), cmake + a C++17 compiler
               (only if the code generator is not built yet: use --build), python3 + numpy (estimator columns).
NOTE           Run sequentially on an otherwise idle machine; RSS of deep N=32768 circuits can reach several GB.
"""
import argparse, csv, hashlib, json, os, re, shutil, statistics, subprocess, sys, tempfile, time
from pathlib import Path

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--repo", required=True, help="path to the chehab-unified checkout (branch peakModel-integration)")
ap.add_argument("--inputs", nargs="+", required=True, help="dataset files (expr:name per line)")
ap.add_argument("--out", default="peak_memory_results.csv")
ap.add_argument("--runs", type=int, default=3, help="fresh-process runs per expression (median is reported)")
ap.add_argument("--timeout", type=int, default=1200, help="seconds per run / per go build")
ap.add_argument("--limit", type=int, default=None, help="only the first N expressions of each file (smoke test)")
ap.add_argument("--only", default=None, help="regex on the expression name (e.g. 'multipoly|tree_')")
ap.add_argument("--resume", action="store_true", help="skip expressions already present in --out")
ap.add_argument("--build", action="store_true", help="build the veclang_runner code generator if it is missing")
ap.add_argument("--go_mod_extra", default=None,
                help="optional text file appended to the generated go.mod (e.g. `replace` lines behind a restrictive network)")
ap.add_argument("--gogc", default=os.environ.get("GOGC", "100"), help="GOGC for the measured runs (repo default 100)")
args = ap.parse_args()

REPO = Path(args.repo).resolve()
RL = REPO / "RL"
BUILD_DIR = REPO / "build" / "RL" / "veclang_runner"
BIN = BUILD_DIR / "veclang_runner"
BUDGETS = (1500, 2000, 2600)

# ------------------------------------------------------------------ estimator (optional columns)
est_mod = None
try:
    for p in (RL / "fhe_rl", RL / "pytrs", RL):
        sys.path.insert(0, str(p))
    import memory as est_mod  # noqa: E402
    from pytrs import parse_sexpr, get_multiplicative_depth, Var, Op  # noqa: E402
except Exception as ex:                                       # noqa: BLE001
    print(f"[warn] estimator not importable ({ex}); estimator columns will be empty", file=sys.stderr)
    from types import SimpleNamespace  # noqa: F401


def run(cmd, cwd, timeout, env=None):
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout, env=env)


def preflight():
    if shutil.which("go") is None:
        sys.exit("Go is not installed / not in PATH (need go >= 1.21).")
    if not BIN.exists():
        if not args.build:
            sys.exit(f"{BIN} not found. Build it once:\n"
                     f"  cd {REPO} && mkdir -p build && cd build && cmake .. -DCMAKE_BUILD_TYPE=Release "
                     f"&& make veclang_runner -j$(nproc)\n(or re-run this script with --build)")
        b = REPO / "build"; b.mkdir(exist_ok=True)
        print("building veclang_runner (first time only, several minutes) ...", flush=True)
        for cmd in (["cmake", "..", "-DCMAKE_BUILD_TYPE=Release"], ["make", "veclang_runner", f"-j{os.cpu_count() or 2}"]):
            r = run(cmd, b, 7200)
            if r.returncode != 0:
                sys.exit("build failed:\n" + (r.stderr or r.stdout)[-1500:])
        if not BIN.exists():
            sys.exit("build finished but the veclang_runner binary is missing")
    gosum = REPO / "lattigo_backend" / "go.sum"
    return gosum


# ------------------------------------------------------------------ dataset reading
def read_dataset(path):
    rows = []
    for i, l in enumerate(open(path)):
        l = l.strip()
        if not l:
            continue
        head, sep, tail = l.rpartition(":")
        e, n = (head, tail) if sep and re.fullmatch(r"[\w\-.#]+", tail.strip()) else (l, f"expr_{i + 1}")
        rows.append((n.strip(), e.strip()))
    meta = {}
    mp = Path(path).with_name(Path(path).stem + "_meta.csv")
    if mp.exists():
        for r in csv.DictReader(open(mp)):
            meta[r["name"]] = r
    return rows, meta


# ------------------------------------------------------------------ one expression
def estimator_cols(expr):
    d = {}
    if est_mod is None:
        return d
    try:
        tree = parse_sexpr(expr)
        b = est_mod.peak_ram_breakdown(expr, margin=False)
        d.update(depth=get_multiplicative_depth(tree), lanes=len(tree.args), est_N=b["N"], est_L=b["L"],
                 est_live_cts=b["live_cts"], est_mb=round(float(b["mb"]), 1))
        d["est_mb_margin"] = round(float(est_mod.peak_ram_breakdown(expr, margin=True)["mb"]), 1)
    except Exception as ex:                                   # noqa: BLE001
        d["est_error"] = f"{type(ex).__name__}: {ex}"[:120]
    return d


def var_names(expr):
    names = set()
    def rec(n):
        if isinstance(n, Var):
            names.add(n.name)
        elif isinstance(n, Op):
            for a in n.args:
                rec(a)
    rec(parse_sexpr(expr))
    return sorted(names)


def first_vec_width(expr):
    w = []
    def rec(n):
        if isinstance(n, Op):
            if n.op == "Vec":
                w.append(len(n.args))
            else:
                for a in n.args:
                    rec(a)
    rec(parse_sexpr(expr))
    return w[0] if w else 1


def patch_neg_new(src):                                       # Lattigo v5.0.7 has no NegNew (same patch as run_pilot.py)
    return re.sub(r"(\w+),\s*_\s*=\s*eval\.NegNew\((\w+)\)",
                  lambda m: f"{m.group(1)}, _ = eval.SubNew({m.group(2)}, {m.group(2)})\n\t{m.group(1)}, _ = eval.SubNew({m.group(1)}, {m.group(2)})", src)


VMHWM_FN = """func getMaxRSS() uint64 {
\t// Peak resident set of THIS process only (VmHWM). getrusage(RUSAGE_SELF).ru_maxrss is NOT used because
\t// on Linux exec() folds the pre-exec (forked-parent) mm high-water mark into ru_maxrss, so a fat Python
\t// parent (torch, numpy, ...) adds a constant floor (~150 MB) to every measurement.
\tif data, err := os.ReadFile("/proc/self/status"); err == nil {
\t\tfor _, line := range strings.Split(string(data), "\\n") {
\t\t\tif strings.HasPrefix(line, "VmHWM:") {
\t\t\t\tf := strings.Fields(line)
\t\t\t\tif len(f) >= 2 {
\t\t\t\t\tif kb, err := strconv.ParseUint(f[1], 10, 64); err == nil {
\t\t\t\t\t\treturn kb * 1024
\t\t\t\t\t}
\t\t\t\t}
\t\t\t}
\t\t}
\t}
\tvar ru syscall.Rusage
\tif err := syscall.Getrusage(syscall.RUSAGE_SELF, &ru); err == nil {
\t\treturn uint64(ru.Maxrss) * 1024
\t}
\treturn 0
}"""


def inject_vmhwm(src):
    """Replace the generated getMaxRSS() by a VmHWM reader. Returns (new_src, ok). Regex, whitespace-tolerant."""
    new, n = re.subn(r"func getMaxRSS\(\)\s*uint64\s*\{.*?\n\}", lambda m: VMHWM_FN, src, count=1, flags=re.S)
    if n == 0 or not all(f'"{i}"' in new for i in ("os", "strings", "strconv", "syscall")):
        return src, False
    return new, True


def parse_stdout(out):
    d = {}
    for line in out.splitlines():
        for key, name in (("max_rss_(MB):", "max_rss_MB"), ("peak_ram_memory_(MB):", "polled_MB"),
                          ("rotation_keys_size_(MB):", "rot_keys_MB"), ("galois_keys_generation_time_(ms):", "keygen_ms"),
                          ("circuit_execution_time_(ms):", "compute_ms"), ("total_execution_time_(ms):", "total_ms")):
            if key in line:
                try:
                    d[name] = float(line.split()[1])
                except (IndexError, ValueError):
                    pass
    m = re.search(r"BENCHMARK_METRICS\s+(\{[^\n]+\})", out)
    if m:
        try:
            d["galois_keys"] = json.loads(m.group(1)).get("galois_keys")
        except ValueError:
            pass
    return d


def go_params(src):
    d = {}
    m = re.search(r"LogN:\s*(\d+)", src)
    if m: d["go_N"] = 1 << int(m.group(1))
    m = re.search(r"LogQ:\s*\[\]int\{([^}]*)\}", src)
    if m: d["go_L"] = len([t for t in m.group(1).split(",") if t.strip()])
    return d


STATE = {"tidied": False}


def measure(expr, gowork, env):
    row = {"status": "ok", "status_detail": ""}
    row.update(estimator_cols(expr))
    try:
        names = var_names(expr)
        slot = first_vec_width(expr)
        with tempfile.TemporaryDirectory(prefix="mem_") as td:
            td = Path(td)
            (td / "vectorized_code.txt").write_text(expr + f"\n{slot} {slot} 1 0")
            (td / "inputs.txt").write_text(" ".join(names) + "\n" + " ".join(["1"] * len(names)) + "\n")
            with open(td / "fhe_io_example.txt", "w") as f:
                f.write(f"1 {len(names)} 1\n")
                for i, nme in enumerate(names):
                    f.write(f"{nme} 1 1 {(i * 7) % 11}\n")        # deterministic inputs 0..10
            gen = BUILD_DIR / "generated_fhe.go"
            if gen.exists():
                gen.unlink()                                      # never read a stale file
            for fn in ("vectorized_code.txt", "inputs.txt", "fhe_io_example.txt"):
                shutil.copy2(td / fn, BUILD_DIR / fn)
                if fn != "fhe_io_example.txt":
                    shutil.copy2(td / fn, BUILD_DIR.parent / fn)
            r = run(["./veclang_runner", "1", "1", "1"], BUILD_DIR, 600)
            if "lattigo_output: generated_fhe.go" not in r.stdout or not gen.exists():
                row.update(status="codegen_fail", status_detail=((r.stderr or r.stdout).strip()[-300:]))
                return row
            src = gen.read_text()
            if "NegNew" in src:
                src = patch_neg_new(src)
            src, ok = inject_vmhwm(src)
            row["rss_source"] = "vmhwm" if ok else "rusage_INFLATED"
            row.update(go_params(src))
    except subprocess.TimeoutExpired:
        row.update(status="codegen_fail", status_detail="code generator timeout"); return row
    except Exception as ex:                                       # noqa: BLE001
        row.update(status="codegen_fail", status_detail=f"{type(ex).__name__}: {ex}"[:300]); return row

    (gowork / "main.go").write_text(src)
    t0 = time.time()
    if not STATE["tidied"]:                                   # first expression: fetch/resolve Lattigo once (needs internet)
        tr = run(["go", "mod", "tidy"], gowork, 1800, env)
        STATE["tidied"] = True
        if tr.returncode != 0:
            print("[warn] go mod tidy failed:\n" + (tr.stderr or tr.stdout)[-600:], file=sys.stderr)
    r = run(["go", "build", "-o", "bin_measure", "."], gowork, args.timeout, env)
    if r.returncode != 0 and re.search(r"go mod tidy|go\.sum|no required module|missing|updates to go\.mod", r.stderr):
        run(["go", "mod", "tidy"], gowork, 1800, env)
        r = run(["go", "build", "-o", "bin_measure", "."], gowork, args.timeout, env)
    if r.returncode != 0:
        row.update(status="build_fail", status_detail=("go build: " + (r.stderr or r.stdout))[-300:]); return row
    row["build_s"] = round(time.time() - t0, 1)

    rss, polled = [], []
    last = {}
    for _ in range(args.runs):
        try:
            r = run(["./bin_measure", "-repetitions=1"], gowork, args.timeout, env)
        except subprocess.TimeoutExpired:
            row.update(status="timeout", status_detail=f"run exceeded {args.timeout}s"); break
        if r.returncode != 0:
            killed = r.returncode in (-9, 137)
            row.update(status="oom_killed" if killed else "run_fail",
                       status_detail=("killed by SIGKILL (very likely out of memory)" if killed else
                                      f"exit {r.returncode}: {(r.stderr or r.stdout)[-250:]}"))
            break
        p = parse_stdout(r.stdout)
        if "max_rss_MB" not in p:
            row.update(status="run_fail", status_detail="max_rss_(MB) missing from output"); break
        rss.append(p["max_rss_MB"]); last = p
        if "polled_MB" in p: polled.append(p["polled_MB"])
    if row.get("go_N") and row.get("est_N"):
        row["param_match"] = int(row["go_N"] == row["est_N"] and row.get("go_L") == row.get("est_L"))
    if rss:
        row["real_peak_MB"] = round(statistics.median(rss), 1)
        row["real_peak_min_MB"], row["real_peak_max_MB"] = round(min(rss), 1), round(max(rss), 1)
        row["runs"] = len(rss)
        if polled: row["polled_peak_MB"] = round(statistics.median(polled), 1)
        for k in ("rot_keys_MB", "galois_keys", "keygen_ms", "compute_ms", "total_ms"):
            if k in last: row[k] = last[k]
        if row.get("est_mb"):
            row["est_error_pct"] = round(100.0 * (row["est_mb"] - row["real_peak_MB"]) / row["real_peak_MB"], 1)
        for B in BUDGETS:
            row[f"real_over_{B}"] = int(row["real_peak_MB"] > B)
        if row["status"] != "ok":
            row["status_detail"] += " (partial: some runs completed)"
    return row


FIELDS = ["dataset", "name", "tier", "status", "status_detail", "real_peak_MB", "real_peak_min_MB", "real_peak_max_MB", "runs",
          "polled_peak_MB", "est_mb", "est_mb_margin", "est_error_pct", "real_over_1500", "real_over_2000", "real_over_2600",
          "depth", "lanes", "est_N", "est_L", "go_N", "go_L", "param_match", "rss_source", "est_live_cts", "rot_keys_MB", "galois_keys",
          "keygen_ms", "compute_ms", "total_ms", "build_s", "est_error", "expr_sha1", "expr"]


def summarize(path):
    rows = list(csv.DictReader(open(path)))
    print("\n================ SUMMARY ================")
    for ds in sorted({r["dataset"] for r in rows}):
        R = [r for r in rows if r["dataset"] == ds]
        ok = [r for r in R if r["real_peak_MB"]]
        print(f"\n{ds}: {len(R)} expressions, {len(ok)} measured, failures: "
              f"{ {s: sum(r['status'] == s for r in R) for s in {r['status'] for r in R} if s != 'ok'} }")
        if not ok:
            continue
        v = sorted(float(r["real_peak_MB"]) for r in ok)
        print(f"  real peak MB: min {v[0]:.0f} | median {v[len(v)//2]:.0f} | p90 {v[int(.9*(len(v)-1))]:.0f} | max {v[-1]:.0f}")
        for B in BUDGETS:
            print(f"  real peak > {B} MB: {sum(float(r['real_peak_MB']) > B for r in ok)} / {len(ok)}")
        pm = [r for r in ok if r["param_match"] != ""]
        if pm:
            print(f"  (N, L) chosen by the compiler differs from the estimator's: {sum(r['param_match'] == '0' for r in pm)} / {len(pm)} "
                  f"(the compiler simplifies the circuit, CSE/const-folding, before choosing parameters)")
        e = [float(r["est_error_pct"]) for r in ok if r["est_error_pct"] not in ("", None)]
        if e:
            ae = sorted(abs(x) for x in e)
            print(f"  estimator vs real (est-real)/real: median |err| {ae[len(ae)//2]:.1f}% | p90 {ae[int(.9*(len(ae)-1))]:.1f}% | "
                  f"mean signed {sum(e)/len(e):+.1f}% | under-estimates (> -10%): {sum(x < -10 for x in e)}")
            worst = sorted(ok, key=lambda r: float(r["est_error_pct"] or 0))[:3]
            print("  largest under-estimates:", [(r["name"], r["est_mb"], r["real_peak_MB"]) for r in worst])


def main():
    gosum = preflight()
    env = dict(os.environ); env["GOGC"] = str(args.gogc)
    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    gowork = out.parent / "go_work"; gowork.mkdir(exist_ok=True)
    extra = Path(args.go_mod_extra).read_text() if args.go_mod_extra else ""
    (gowork / "go.mod").write_text("module pilot\n\ngo 1.21\n\nrequire github.com/tuneinsight/lattigo/v5 v5.0.7\n" + extra)
    if gosum.exists():
        shutil.copy2(gosum, gowork / "go.sum")

    items = []
    for p in args.inputs:
        rows, meta = read_dataset(p)
        ds = Path(p).stem
        if args.only:
            rows = [(n, e) for n, e in rows if re.search(args.only, n)]
        if args.limit:
            rows = rows[:args.limit]
        items += [(ds, n, e, meta.get(n, {}).get("tier", "")) for n, e in rows]
    print(f"{len(items)} expressions from {len(args.inputs)} file(s); runs/expr = {args.runs}; GOGC={args.gogc}", flush=True)

    done, kept = set(), []
    if args.resume and out.exists():
        for r in csv.DictReader(open(out)):
            if r.get("status") in ("ok", "oom_killed", "timeout", "run_fail"):     # build/codegen failures are retried
                kept.append(r); done.add((r["dataset"], r["name"], r["expr_sha1"]))
        print(f"resume: keeping {len(kept)} finished rows, retrying the rest", flush=True)
    consecutive_fail = 0
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for r in kept:
            w.writerow({k: r.get(k, "") for k in FIELDS})
        fh.flush()
        for i, (ds, n, e, tier) in enumerate(items, 1):
            sha = hashlib.sha1(e.encode()).hexdigest()[:12]
            if (ds, n, sha) in done:
                continue
            t0 = time.time()
            row = measure(e, gowork, env)
            row.update(dataset=ds, name=n, tier=tier, expr_sha1=sha, expr=e)
            w.writerow({k: row.get(k, "") for k in FIELDS}); fh.flush()
            consecutive_fail = consecutive_fail + 1 if row["status"] in ("build_fail", "codegen_fail") else 0
            if consecutive_fail >= 5:
                sys.exit(f"\nStopping: 5 consecutive {row['status']} -- this is an environment problem, not the expressions.\n"
                         f"Last error: {row['status_detail']}\nFix it (see the message above; for Go try `cd {gowork} && go mod tidy`) "
                         f"and re-run with --resume.")
            print(f"[{i}/{len(items)}] {ds}/{n}: {row['status']}"
                  + (f"  real={row['real_peak_MB']} MB  est={row.get('est_mb', '')} MB" if row.get("real_peak_MB") else
                     f"  ({row['status_detail'][:80]})") + f"  [{time.time() - t0:.0f}s]", flush=True)
    summarize(out)
    print(f"\nresults: {out.resolve()}")


if __name__ == "__main__":
    main()