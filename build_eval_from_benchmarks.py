#!/usr/bin/env python3
"""
build_eval_from_benchmarks.py -- generate evaluation expressions from the circuits in ./benchmarks
=================================================================================================

Writes two files (the notation of the CHEHAB compiler: scalar VecLang, "(Vec e0 e1 ...)" with + - *):

    <out_dir>/eval_general.txt   (+ eval_general_meta.csv)
    <out_dir>/eval_dnn.txt       (+ eval_dnn_meta.csv)

one expression per line, "<expr>:<name>" (same layout as RL/fhe_rl/datasets/benchmarks.txt).

WHERE THE CIRCUITS COME FROM
  Every family below re-implements the fhe(...) function of a circuit in ./benchmarks (the C++ code only
  writes the circuit through the DSL, there is no expression file), for sizes of your choice:
    general : dot_product, lin_reg, hamming_dist, l2_distance, poly_reg, matrix_mul, box_blur, gx_kernel
    dnn     : conv2d            (benchmarks/conv2d/conv2d.cpp          fhe_conv2d)
              matmul chains     (benchmarks/matrix_mul                 A*B, (A*B)*B1, ...)
              mlconv            (benchmarks/deep_network               fhe_multilayer_conv)
              linear            (benchmarks/deep_network               fhe_deep_linear_chain)
              deeppoly          (benchmarks/deep_network               fhe_deep_polynomial, x^(2^depth) per lane)
  max / sort / tree_* are NOT generated: their C++ code hard-codes the cond-trees for a few sizes only,
  so there is no parametric circuit to scale.

CORRECTNESS GUARANTEE (--oracle)
  Before generating, every builder is checked against the reference expressions it can reproduce
  (benchmarks_names.xlsx + any --oracle files, e.g. your current eval files) by random evaluation of every
  lane, mod 2^61-1.  A single mismatch aborts the run.  Families with no reference expression at any size
  (deeppoly) are reported as "unverified".

NO OVERLAP WITH THE TRAINING SET
  Every candidate is compared with --final (final_llm_dataset.txt) and every --exclude file with
    1. exact match (whitespace-normalised, name stripped), and
    2. alpha-renamed match (same structure with variables renamed in order of first appearance).
  Matches are dropped.  The output files are re-read at the end and the overlap is recomputed (must be 0).
  Not detected: the same function written with a different association/commutation of + and *.

MEMORY TIER (optional, needs the repo)
  With --repo, each expression gets the estimate the agent trains against (fhe_rl.memory.peak_ram_breakdown,
  margin=False) and a tier:  inactive (<1200 MB) | near_1200 | over_1500 | over_2000 | over_2600.
  --active_only keeps only expressions with est >= 1200 MB (the budgets can bind).

Usage
  python3 build_eval_from_benchmarks.py --repo ~/chehab-unified --out_dir ./out_new
  python3 build_eval_from_benchmarks.py --repo ~/chehab-unified --out_dir ./out_new --active_only
"""
import argparse, csv, hashlib, os, random, re, sys, time
from collections import Counter, OrderedDict
from pathlib import Path

P = (1 << 61) - 1
ACTIVE_MB = 1200
TIERS = ((2600, "over_2600"), (2000, "over_2000"), (1500, "over_1500"), (ACTIVE_MB, "near_1200"))


def tier_of(mb):
    for thr, name in TIERS:
        if mb >= thr:
            return name
    return "inactive"


# ----------------------------------------------------------------------------------------------- expression core
# atom = str (variable) | int (constant);  node = tuple (op, *args)  with op in {"Vec", "+", "-", "*"}
def bal(op, terms):
    terms = list(terms)
    if len(terms) == 1:
        return terms[0]
    m = len(terms) // 2
    return (op, bal(op, terms[:m]), bal(op, terms[m:]))


def vec(lanes):
    return ("Vec",) + tuple(lanes)


def coef_term(v, c):
    return v if c == 1 else ("-", v) if c == -1 else ("*", v, c)


def csize(e, memo):
    """characters of the printed expression (shared sub-trees counted every time they are printed)"""
    if not isinstance(e, tuple):
        return len(str(e)) + 1
    k = id(e)
    if k not in memo:
        memo[k] = sum(csize(c, memo) for c in e[1:]) + len(e[0]) + 4
    return memo[k]


def to_str(e, memo=None):
    memo = {} if memo is None else memo
    if not isinstance(e, tuple):
        return str(e)
    k = id(e)
    if k not in memo:
        memo[k] = "( " + e[0] + " " + " ".join(to_str(c, memo) for c in e[1:]) + " )"
    return memo[k]


def vec_to_line(v, name):
    memo = {}
    return "(Vec " + " ".join(to_str(l, memo) for l in v[1:]) + "):" + name


def parse(s):
    tok = s.replace("(", " ( ").replace(")", " ) ").split()
    pos = 0

    def rd():
        nonlocal pos
        t = tok[pos]
        pos += 1
        if t == "(":
            op = tok[pos]
            pos += 1
            args = []
            while tok[pos] != ")":
                args.append(rd())
            pos += 1
            return (op,) + tuple(args)
        try:
            return int(t)
        except ValueError:
            return t

    return rd()


def atoms(e, acc):
    stack = [e]
    seen = set()
    while stack:
        x = stack.pop()
        if isinstance(x, tuple):
            if id(x) in seen:
                continue
            seen.add(id(x))
            stack.extend(x[1:])
        elif isinstance(x, str):
            acc.add(x)
    return acc


def ev(e, env, memo):
    if isinstance(e, int):
        return e % P
    if isinstance(e, str):
        return env[e]
    k = id(e)
    if k in memo:
        return memo[k]
    a = [ev(c, env, memo) for c in e[1:]]
    op = e[0]
    r = (a[0] + a[1]) % P if op == "+" else ((a[0] * a[1]) % P if op == "*" else ((a[0] - a[1]) % P if len(a) == 2 else (-a[0]) % P))
    memo[k] = r
    return r


def same_function(v1, v2, trials=3, seed=1234):
    if v1[0] != "Vec" or v2[0] != "Vec" or len(v1) != len(v2):
        return False
    names = atoms(v1, set()) | atoms(v2, set())
    rng = random.Random(seed)
    for _ in range(trials):
        env = {n: rng.randrange(1, 10 ** 6) for n in names}
        m1, m2 = {}, {}
        for a, b in zip(v1[1:], v2[1:]):
            if ev(a, env, m1) != ev(b, env, m2):
                return False
    return True


# ----------------------------------------------------------------------------------------------- general families
def dot_product(n):
    return vec([bal("+", [("*", f"v1_{i}", f"v2_{i}") for i in range(n)])])


def lin_reg(n):
    return vec([("+", f"v2_{i}", ("+", 2, ("*", f"v1_{i}", 5))) for i in range(n)])


def hamming_dist(n):
    t = []
    for i in range(n):
        a, b = f"v1_{i}", f"v2_{i}"
        t.append(("-", ("+", a, b), ("*", 2, ("*", a, b))))
    return vec([bal("+", t)])


def l2_distance(n):
    t = []
    for i in range(n):
        d = ("-", f"c2_{i}", f"c1_{i}")
        t.append(("*", d, d))
    return vec([bal("+", t)])


def poly_reg(n):
    L = []
    for i in range(n):
        c = [f"c{k}_{i}" for k in range(5)]
        L.append(("+", c[1], ("+", c[2], ("*", c[0], ("+", c[3], ("*", c[0], c[4]))))))
    return vec(L)


def matrix_mul(n):
    return vec([bal("+", [("*", f"a_{i}_{k}", f"b_{k}_{j}") for k in range(n)]) for i in range(n) for j in range(n)])


def box_blur(n):
    L = []
    for i in range(n):
        for j in range(n):
            L.append(bal("+", [f"in_{i + a}_{j + b}" for a in (-1, 0, 1) for b in (-1, 0, 1)
                               if 0 <= i + a < n and 0 <= j + b < n]))
    return vec(L)


def gx_kernel(n):
    row_w = {-1: 1, 0: 2, 1: 1}
    L = []
    for i in range(n):
        for j in range(n):
            t = []
            for a in (-1, 0, 1):
                for b, sgn in ((-1, -1), (1, 1)):
                    if 0 <= i + a < n and 0 <= j + b < n:
                        t.append(coef_term(f"in_{i + a}_{j + b}", sgn * row_w[a]))
            L.append(bal("+", t))
    return vec(L)


# ----------------------------------------------------------------------------------------------- dnn families
def conv2d(S, K):
    o = S - K + 1
    if o < 1:
        return None
    return vec([bal("+", [("*", f"img_{i + a}_{j + b}", f"kernel_{a}_{b}") for a in range(K) for b in range(K)])
                for i in range(o) for j in range(o)])


def matmul_chain(N, c):
    cur = [[bal("+", [("*", f"a_{i}_{k}", f"b_{k}_{j}") for k in range(N)]) for j in range(N)] for i in range(N)]
    for t in range(1, c):
        cur = [[bal("+", [("*", cur[i][k], f"b{t}_{k}_{j}") for k in range(N)]) for j in range(N)] for i in range(N)]
    return vec([cur[i][j] for i in range(N) for j in range(N)])


def mlconv(S, K, L):
    img = [[f"img_{i}_{j}" for j in range(S)] for i in range(S)]
    cs = S
    for l in range(L):
        o = cs - K + 1
        if o < 1:
            return None
        new = []
        for i in range(o):
            row = []
            for j in range(o):
                s = bal("+", [("*", img[i + a][j + b], f"k{l}_{a}_{b}") for a in range(K) for b in range(K)])
                row.append(("*", s, s))
            new.append(row)
        img, cs = new, o
    return vec([img[i][j] for i in range(cs) for j in range(cs)])


def linear_chain(S, L):
    cur = [f"x_{j}" for j in range(S)]
    for l in range(L):
        nxt = []
        for i in range(S):
            s = bal("+", [("*", f"w{l}_{i}_{j}", cur[j]) for j in range(S)])
            nxt.append(("*", s, s))
        cur = nxt
    return vec(cur)


def deeppoly(d, lanes):
    out = []
    for i in range(lanes):
        e = f"x_{i}"
        for _ in range(d):
            e = ("*", e, e)
        out.append(e)
    return vec(out)


def _fam(build, name, rx, grid):
    return dict(build=build, name=name, rx=re.compile(rx), grid=grid)


N_SMALL = [2, 3, 5, 6, 7, 9, 10, 12, 20, 24, 48, 64, 96, 128]
# scalar reductions create one input ciphertext per variable: these sizes cross the 1500/2000/2600 MB budgets
N_BIG = [160, 192, 256, 320, 384, 448, 512, 640]
GENERAL = OrderedDict([
    ("dot_product", _fam(lambda n: dot_product(n), lambda n: f"dot_product_{n}", r"^dot_product_(\d+)$", [(n,) for n in N_SMALL + N_BIG])),
    ("lin_reg", _fam(lambda n: lin_reg(n), lambda n: f"lin_reg_{n}", r"^lin_reg_(\d+)$", [(n,) for n in N_SMALL])),
    ("hamming_dist", _fam(lambda n: hamming_dist(n), lambda n: f"hamming_dist_{n}", r"^hamming_dist_(\d+)$", [(n,) for n in N_SMALL + N_BIG])),
    ("l2_distance", _fam(lambda n: l2_distance(n), lambda n: f"l2_distance_{n}", r"^l2_distance_(\d+)$", [(n,) for n in N_SMALL + N_BIG])),
    ("poly_reg", _fam(lambda n: poly_reg(n), lambda n: f"poly_reg_{n}", r"^poly_reg_(\d+)$", [(n,) for n in N_SMALL])),
    ("matrix_mul", _fam(lambda n: matrix_mul(n), lambda n: f"matrix_mul_{n}", r"^matrix_mul_(\d+)$", [(n,) for n in (2, 5, 6, 7, 8, 9, 10, 12)])),
    ("box_blur", _fam(lambda n: box_blur(n), lambda n: f"box_blur_{n}", r"^box_blur_(\d+)$", [(n,) for n in (2, 6, 7, 8, 9, 10, 12, 16)])),
    ("gx_kernel", _fam(lambda n: gx_kernel(n), lambda n: f"gx_kernel_{n}", r"^gx_kernel_(\d+)$", [(n,) for n in (2, 6, 7, 8, 9, 10, 12, 16)])),
])
DNN = OrderedDict([
    ("conv2d", _fam(conv2d, lambda S, K: f"conv2d_{S}x{S}_k{K}", r"^conv2d_(\d+)x\d+_k(\d+)$",
                    [(S, K) for S in (4, 5, 6, 7, 8, 9, 10, 12) for K in (2, 3, 4) if K < S])),
    ("matmul", _fam(matmul_chain, lambda N, c: f"matmul_{N}x{N}_chain{c}", r"^matmul_(\d+)x\d+_chain(\d+)$",
                    [(N, c) for N in (2, 3, 4, 5, 6, 7, 8) for c in (1, 2, 3, 4)])),
    ("mlconv", _fam(mlconv, lambda S, K, L: f"mlconv_{S}x{S}_k{K}_L{L}", r"^mlconv_(\d+)x\d+_k(\d+)_L(\d+)$",
                    [(S, K, L) for S in (4, 5, 6, 7, 8, 10) for K in (2, 3) for L in (1, 2, 3, 4, 5)])),
    ("linear", _fam(linear_chain, lambda S, L: f"linear_s{S}_L{L}", r"^linear_s(\d+)_L(\d+)$",
                    [(S, L) for S in (2, 3, 4, 5, 6, 8, 10, 12) for L in (1, 2, 3, 4, 5, 6)])),
    ("deeppoly", _fam(deeppoly, lambda d, l: f"deeppoly_d{d}_l{l}", r"^deeppoly_d(\d+)_l(\d+)$",
                      [(d, l) for d in range(2, 13) for l in (1, 4, 8, 16)])),
])
GROUPS = OrderedDict([("general", GENERAL), ("dnn", DNN)])


# ----------------------------------------------------------------------------------------------- oracle check
def load_oracle(paths, xlsx):
    ref = OrderedDict()
    if xlsx and Path(xlsx).exists():
        try:
            import openpyxl
            ws = openpyxl.load_workbook(xlsx, read_only=True).active
            for r in list(ws.iter_rows(values_only=True))[1:]:
                if r and r[0] and r[1]:
                    ref[str(r[0])] = str(r[1])
        except Exception as ex:
            print(f"[oracle] cannot read {xlsx}: {ex}")
    for p in paths:
        for l in open(p, errors="replace"):
            m = re.match(r"^(\(Vec.*\)):([\w\-.#]+)\s*$", l.strip())
            if m:
                ref.setdefault(m.group(2), m.group(1))
    return ref


def verify(ref):
    stats = {}
    bad = []
    for gname, fams in GROUPS.items():
        for fam, spec in fams.items():
            ok = n = 0
            for name, expr in ref.items():
                m = spec["rx"].match(name)
                if not m:
                    continue
                params = tuple(int(x) for x in m.groups())
                if spec["name"](*params) != name:      # e.g. rectangular 4x5 names: not ours
                    continue
                n += 1
                built = spec["build"](*params)
                if built is not None and same_function(built, parse(expr)):
                    ok += 1
                else:
                    bad.append(name)
            stats[fam] = (ok, n)
    return stats, bad


# ----------------------------------------------------------------------------------------------- training-set filter
def toks_of(line):
    line = re.sub(r":[\w\-.#]+\s*$", "", line.strip())
    return line.replace("(", " ( ").replace(")", " ) ").split()


def keys_of(tokens):
    exact = hashlib.md5(" ".join(tokens).encode()).hexdigest()
    ren, out, prev = {}, [], None
    for t in tokens:
        if prev == "(" or t in ("(", ")") or not re.search(r"[A-Za-z_]", t):
            out.append(t)
        else:
            out.append(ren.setdefault(t, f"v{len(ren)}"))
        prev = t
    return exact, hashlib.md5(" ".join(out).encode()).hexdigest()


_VAL = {}


def _val(name):
    v = _VAL.get(name)
    if v is None:
        v = _VAL[name] = int.from_bytes(hashlib.md5(name.encode()).digest()[:8], "big") % P
    return v


def func_key(tokens):
    try:
        return _func_key(tokens)
    except (IndexError, TypeError):      # malformed line (unbalanced parentheses...) -> no fingerprint
        return None


def _func_key(tokens):
    """Order-insensitive functional fingerprint: value of every lane at a fixed point (variable value = hash of
    its name), mod 2^61-1.  Catches the same function written with another association/commutation of + and *.
    Iterative (expressions can be very deep).  Returns None for unsupported operators."""
    frames, res, expect_op = [], None, False
    for t in tokens:
        if t == "(":
            frames.append([None, []])
            expect_op = True
        elif expect_op:
            frames[-1][0] = t
            expect_op = False
        elif t == ")":
            op, args = frames.pop()
            if op == "Vec":
                r = tuple(args)
            elif op == "+" and len(args) == 2:
                r = (args[0] + args[1]) % P
            elif op == "*" and len(args) == 2:
                r = (args[0] * args[1]) % P
            elif op == "-" and len(args) == 2:
                r = (args[0] - args[1]) % P
            elif op == "-" and len(args) == 1:
                r = (-args[0]) % P
            else:
                return None
            if frames:
                frames[-1][1].append(r)
            else:
                res = r
        else:
            try:
                x = int(t) % P
            except ValueError:
                x = _val(t)
            if frames:
                frames[-1][1].append(x)
    if res is None:
        return None
    lanes = res if isinstance(res, tuple) else (res,)
    return hashlib.md5(repr(sorted(lanes)).encode()).hexdigest()


def load_forbidden(paths, use_func=True):
    ex, ca, fu = set(), set(), set()
    n = 0
    for p in paths:
        t0 = time.time()
        k = 0
        for l in open(p, errors="replace"):
            if not l.lstrip().startswith("(Vec"):
                continue                               # markdown fences, blank lines, noise
            tk = toks_of(l)
            a, b = keys_of(tk)
            ex.add(a)
            ca.add(b)
            if use_func:
                f = func_key(tk)
                if f:
                    fu.add(f)
            k += 1
        n += k
        print(f"[filter] {p}: {k} expressions indexed ({time.time() - t0:.1f}s)")
    return ex, ca, fu, n


# ----------------------------------------------------------------------------------------------- estimator (optional)
def load_estimator(repo):
    if not repo:
        return None
    try:
        sys.path.insert(0, str(Path(repo).expanduser() / "RL"))
        from fhe_rl.memory import peak_ram_breakdown
        peak_ram_breakdown("(Vec ( + a b ) )", margin=False)
        return peak_ram_breakdown
    except Exception as ex:
        print(f"[estimator] unavailable ({type(ex).__name__}: {ex}); est_* columns left empty")
        return None


# ----------------------------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default=None, help="chehab-unified root (enables estimator, default final/xlsx paths)")
    ap.add_argument("--out_dir", default="./out_new")
    ap.add_argument("--final", default=None, help="final_llm_dataset.txt (default: <repo>/RL/fhe_rl/datasets/final_llm_dataset.txt)")
    ap.add_argument("--exclude", nargs="*", default=[], help="extra files whose expressions must not appear in the output")
    ap.add_argument("--oracle", nargs="*", default=[], help="extra files with reference ':name' lines to verify builders against")
    ap.add_argument("--only", choices=["general", "dnn", "both"], default="both")
    ap.add_argument("--families", nargs="*", default=None, help="restrict to these families")
    ap.add_argument("--max_chars", type=int, default=300000, help="skip expressions printing longer than this")
    ap.add_argument("--no_est", action="store_true")
    ap.add_argument("--active_only", action="store_true", help="keep only est >= 1200 MB (needs the estimator)")
    ap.add_argument("--min_est_mb", type=float, default=None)
    ap.add_argument("--skip_verify", action="store_true")
    ap.add_argument("--no_func", action="store_true", help="skip the functional-fingerprint check (faster, weaker)")
    a = ap.parse_args()

    repo = Path(a.repo).expanduser() if a.repo else None
    final = a.final or (str(repo / "RL/fhe_rl/datasets/final_llm_dataset.txt") if repo else None)
    if not final or not Path(final).exists():
        sys.exit("final_llm_dataset.txt not found: pass --final or --repo")
    forbid_files = [final] + [str(Path(p).expanduser()) for p in a.exclude]

    # 1) builders vs reference expressions
    xlsx = str(repo / "RL/fhe_rl/datasets/benchmarks_names.xlsx") if repo else None
    stats = {}
    ref = load_oracle([str(Path(p).expanduser()) for p in a.oracle], xlsx)
    if not a.skip_verify:
        stats, bad = verify(ref)
        print("[verify] builder vs reference (random evaluation of every lane):")
        for fam, (ok, n) in stats.items():
            print(f"   {fam:13s} {ok}/{n} reproduced" + ("" if n else "   (no reference expression: UNVERIFIED)"))
        if bad:
            sys.exit(f"[verify] MISMATCH on {bad[:10]} -> builder does not reproduce the reference; aborting")

    # 2) forbidden set
    fx, fc, ff, nforb = load_forbidden(forbid_files, use_func=not a.no_func)
    est_fn = None if a.no_est else load_estimator(repo)
    min_est = ACTIVE_MB if a.active_only else a.min_est_mb
    if min_est is not None and est_fn is None:
        sys.exit("--active_only / --min_est_mb need the estimator: pass --repo (and no --no_est)")

    out_dir = Path(a.out_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    seen_ex, seen_ca, seen_fu = set(), set(), set()
    report = {}

    for gname, fams in GROUPS.items():
        if a.only not in ("both", gname):
            continue
        lines, meta = [], []
        for fam, spec in fams.items():
            if a.families and fam not in a.families:
                continue
            cnt = Counter()
            for params in spec["grid"]:
                name = spec["name"](*params)
                v = spec["build"](*params)
                if v is None:
                    cnt["invalid_params"] += 1
                    continue
                if csize(v, {}) > a.max_chars:
                    cnt["too_long"] += 1
                    continue
                line = vec_to_line(v, name)
                tk = toks_of(line)
                kx, kc = keys_of(tk)
                kf = None if a.no_func else func_key(tk)
                if kx in fx or kc in fc:
                    cnt["in_final(textual)"] += 1
                    continue
                if kf and kf in ff:
                    cnt["in_final(same function)"] += 1
                    continue
                if kx in seen_ex or kc in seen_ca or (kf and kf in seen_fu):
                    cnt["duplicate_in_output"] += 1
                    continue
                row = dict(name=name, family=fam, params="x".join(map(str, params)), lanes=len(v) - 1, chars=len(line),
                           est_mb="", est_N="", est_L="", est_G="", live_cts="", tier="",
                           reference_checked=("yes" if stats.get(fam, (0, 0))[0] else "no") if not a.skip_verify else "")
                if est_fn:
                    try:
                        r = est_fn(line.rsplit(":", 1)[0], margin=False)
                        row.update(est_mb=round(r["mb"], 1), est_N=r["N"], est_L=r["L"], est_G=r["G"],
                                   live_cts=r["live_cts"], tier=tier_of(r["mb"]))
                    except Exception as ex:
                        cnt["estimator_error"] += 1
                        continue
                    if min_est is not None and r["mb"] < min_est:
                        cnt["below_min_est"] += 1
                        continue
                seen_ex.add(kx)
                seen_ca.add(kc)
                if kf:
                    seen_fu.add(kf)
                lines.append(line)
                meta.append(row)
                cnt["kept"] += 1
            report[(gname, fam)] = cnt
        (out_dir / f"eval_{gname}.txt").write_text("\n".join(lines) + ("\n" if lines else ""))
        with open(out_dir / f"eval_{gname}_meta.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["name", "family", "params", "lanes", "chars", "est_mb", "est_N", "est_L", "est_G", "live_cts", "tier", "reference_checked"])
            w.writeheader()
            w.writerows(meta)
        tiers = Counter(m["tier"] for m in meta if m["tier"])
        print(f"\n[{gname}] {len(lines)} expressions -> {out_dir / ('eval_' + gname + '.txt')}")
        if tiers:
            print("   tiers:", dict(tiers))

    print("\n[per family]  kept / dropped (reason)")
    for (g, fam), c in report.items():
        drop = {k: v for k, v in c.items() if k != "kept"}
        print(f"   {g:7s} {fam:13s} kept {c['kept']:3d}   dropped {drop if drop else '-'}")

    # 3) final self-check: re-read the files and recompute the overlap
    over = 0
    for gname in GROUPS:
        p = out_dir / f"eval_{gname}.txt"
        if p.exists():
            for l in open(p):
                if l.strip():
                    tk = toks_of(l)
                    kx, kc = keys_of(tk)
                    kf = None if a.no_func else func_key(tk)
                    over += (kx in fx) or (kc in fc) or bool(kf and kf in ff)
    print(f"\n[check] overlap of output files with {len(forbid_files)} forbidden file(s) ({nforb} expressions): {over}")
    if over:
        sys.exit("overlap found -- should never happen")


if __name__ == "__main__":
    main()