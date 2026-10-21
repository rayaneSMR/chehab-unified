"""
Calibrated peak-memory model for the CHEHAB RL environment (Lattigo / CPU, HEonGPU / GPU).

Backend: env PEAK_RAM_BACKEND = "cpu" (default, unchanged) or "gpu" (HEonGPU A100): label-corrected
packing + estimator "gpu" coefficients, optional memory_calib_gpu.json {"scale","margin"} (default 1.0).

Single entry point used by env.py:   peak_ram_mb(expr) -> float   (MB of process peak RSS)

How it works
  1. CKKSMemoryEstimator terms provide the analytical cryptographic "net" memory.
  2. A per-N-group calibration maps net -> measured MaxRSS (fitted on the pilot, see fit_calib.py).
  3. A multiplicative safety margin (held-out p90 of measured/predicted) is applied by default,
     so the constraint rarely under-estimates.
  4. Circuits WITH rotations (G>0) are NOT validated against the pipeline: the calibration is
     applied to the non-key terms only, and Galois-key bytes are scaled by GALOIS_KEY_FACTOR
     (derived from synthetic Lattigo benchmarks: measured/estimated p90 = 1.35, N=32768 p90 = 1.13).
"""
import json, math, os, sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "pytrs"))
try:                                  # loaded as part of the package (python -m fhe_rl ...)
    from . import packing  # noqa: E402
except ImportError:                   # loaded as a plain module (scripts run from this folder)
    import packing  # noqa: E402
from ckks_memory_estimator import (estimate_expression_memory, estimate_peak_memory,  # noqa: E402
                                   ciphertext_bytes)

BACKEND = os.environ.get("PEAK_RAM_BACKEND", "cpu").strip().lower()
if BACKEND not in ("cpu", "gpu"):
    raise ValueError(f"PEAK_RAM_BACKEND must be cpu or gpu, got {BACKEND!r}")
MB = 1024.0 * 1024.0
GALOIS_KEY_FACTOR = 1.76  # measured by finish/rot_probe.py: RSS ~1.9x key size at (16384,4) and (32768,9); 1.76 = GC ratio of the deep group
CALIB_PATH = os.environ.get("PEAK_RAM_CALIB", os.path.join(_HERE, "memory_calib.json"))
GPU_CALIB_PATH = os.environ.get("PEAK_RAM_GPU_CALIB", os.path.join(_HERE, "memory_calib_gpu.json"))
# GPU estimate = pool peak (circuit-dependent) + fixed CUDA context (measured: +427 MiB device, A100)
GPU_CTX_MB = float(os.environ.get("PEAK_RAM_GPU_CTX_MB", "427"))
ESTIMATOR_VERSION = "calib-v3-packed" if BACKEND == "cpu" else "gpu-v2-ctx"

_calib = None
_gpu_calib = None
_cache = {}
_CACHE_MAX = 300_000


def _load():
    global _calib
    if _calib is None:
        if not os.path.exists(CALIB_PATH):
            raise FileNotFoundError(
                f"{CALIB_PATH} not found. Run fit_calib.py first (or set PEAK_RAM_CALIB).")
        _calib = json.load(open(CALIB_PATH))
    return _calib


def _gpu_params():
    global _gpu_calib
    if _gpu_calib is None:
        c = {"scale": 1.0, "margin": 1.0}
        if os.path.exists(GPU_CALIB_PATH):
            c.update({k: float(v) for k, v in json.load(open(GPU_CALIB_PATH)).items() if k in ("scale", "margin")})
        _gpu_calib = c
    return _gpu_calib


def _gpu_mult(margin):
    c = _gpu_params()
    return c["scale"] * (c["margin"] if margin else 1.0)


def _gpu_target_mb(raw_total_mb, margin):
    """GPU estimate = pool peak * scale * margin + fixed CUDA context (offset not scaled by margin)."""
    return raw_total_mb * _gpu_mult(margin) + GPU_CTX_MB


def group_of(N):
    return "16384" if N <= 16384 else "32768"


def _apply(group, net_mb, L, margin):
    c = _load()["groups"][group]
    if c["model"] == "ratio":
        pred = c["ratio"] * net_mb
    else:  # loglog:  log rss = a + b*log(net) + cL*L
        pred = math.exp(c["a"] + c["b"] * math.log(max(net_mb, 1e-6)) + c["cL"] * L)
    if "cap_ratio" in c:   # optional plateau of RSS/net (set by finish/analyze_top.py only if validated)
        pred = min(pred, c["cap_ratio"] * net_mb)
    return pred * (c["margin"] if margin else 1.0)


def _raw_floor_mb(N, L, K, margin):
    """Calibrated floor of an (almost) empty circuit, WITHOUT the monotone clamp."""
    t = estimate_peak_memory(N, L, K, 0, 2 * ciphertext_bytes(N, L - 1), BACKEND)
    if BACKEND == "gpu":
        return _gpu_target_mb(sum(t.values()) / MB, margin)
    return _apply(group_of(N), sum(t.values()) / MB, L, margin)


# The N=16384 log-log fit extrapolates steeply in L (only 3 pilot rows at L=8), so its floor at
# (16384, L=8) used to exceed the floor of (32768, L=9): predicted RAM could DROP when depth
# crosses the N boundary, while measured RSS rises ~5x. Fix: any N>=32768 circuit is predicted
# at least 1.05 x the largest N=16384 floor (the L=8 tier). Only affects the bottom of the
# N=32768 distribution; conservative direction.
_MONO_FACTOR = 1.05
_MAX_L_16384 = 8


def _lower_bound(group, margin):
    if BACKEND == "gpu":
        return 0.0
    if group == "32768":
        return _MONO_FACTOR * _raw_floor_mb(16384, _MAX_L_16384, 2, margin)
    return 0.0


def _pack(expr):
    return packing.pack_expr_str(expr, fix_labels=(BACKEND == "gpu"))


def peak_ram_breakdown(expr, margin=True):
    try:
        expr_used = _pack(expr)
        packed_ok = True
    except Exception:
        expr_used = expr
        packed_ok = False
    est = estimate_expression_memory(expr_used, BACKEND)
    p = est.params
    gal_mb = est.terms.get("galois_keys", 0.0) / MB
    non_key_mb = est.total_mb - gal_mb
    g = group_of(p.N)
    if BACKEND == "gpu":
        return dict(mb=_gpu_target_mb(est.total_mb, margin), clamped=False, N=p.N, L=p.L, K=p.K, G=est.rotation_steps,
                    group=g, raw_net_mb=est.total_mb, galois_mb=gal_mb, live_cts=est.peak_live_ciphertexts,
                    validated=True, packed=packed_ok)
    mult = _load()["groups"][g]["margin"] if margin else 1.0
    pred_raw = _apply(g, non_key_mb, p.L, margin) + gal_mb * GALOIS_KEY_FACTOR * mult
    pred = max(pred_raw, _lower_bound(g, margin))
    return dict(mb=pred, clamped=pred > pred_raw, N=p.N, L=p.L, K=p.K, G=est.rotation_steps, group=g,
                raw_net_mb=est.total_mb, galois_mb=gal_mb, live_cts=est.peak_live_ciphertexts,
                validated=(est.rotation_steps == 0), packed=packed_ok)


def peak_ram_mb(expr, margin=True):
    """Calibrated peak RSS estimate in MB. Cached by expression string."""
    key = (BACKEND, expr, margin)
    v = _cache.get(key)
    if v is None:
        if len(_cache) > _CACHE_MAX:
            _cache.clear()
        v = peak_ram_breakdown(expr, margin)["mb"]
        _cache[key] = v
    return v


_rot_cache = {}


def rotation_steps(expr):
    """Number of distinct rotation steps (= Galois keys) of the packed expression; -1 if the estimator fails. Cached."""
    v = _rot_cache.get((BACKEND, expr))
    if v is None:
        if len(_rot_cache) > _CACHE_MAX:
            _rot_cache.clear()
        try:
            v = int(peak_ram_breakdown(expr, margin=False)["G"])
        except Exception:
            v = -1
        _rot_cache[(BACKEND, expr)] = v
    return v


def floor_mb(N, L, K, margin=True):
    """Memory of an (almost) empty circuit with these params: the smallest value a rewrite can reach."""
    return max(_raw_floor_mb(N, L, K, margin), _lower_bound(group_of(N), margin))

def _components(expr):
    """Analytical component breakdown of the (packed) expression, MB. Uncalibrated estimator terms."""
    if not isinstance(expr, str):
        from serializer import expr_to_str
        expr = expr_to_str(expr)
    try:
        used = _pack(expr)
    except Exception:
        used = expr
    est = estimate_expression_memory(used, BACKEND)
    t = {k: v / MB for k, v in est.terms.items()}
    return dict(N=est.params.N, L=est.params.L, K=est.params.K, G=est.rotation_steps,
                galois=t.get("galois_keys", 0.0), cts=t.get("ciphertexts", 0.0),
                ctx=t.get("public_secret_key", 0.0) + t.get("context_evaluator", 0.0) + t.get("key_switching_scratch", 0.0),
                relin=t.get("relinearization_key", 0.0), live=est.peak_live_ciphertexts)


def extra_metrics(initial_expr, final_expr, initial_mb, final_mb, budget, prefix=""):
    """Evaluation metrics of the peak-RAM spec (section 7) that are not plain columns yet. Never raises."""
    unb = budget > 100_000                      # 1_000_000 = unconstrained
    started_infeasible = (not unb) and initial_mb > budget
    feasible = unb or final_mb <= budget
    out = {
        "RAM Expansion (%)": round(100.0 * (final_mb - initial_mb) / initial_mb, 2) if initial_mb > 0 else 0.0,
        "Feasibility": "FEASIBLE" if feasible else "VIOLATED (OOM)",
        "Started Infeasible": bool(started_infeasible),
        "Recovered": bool(started_infeasible and feasible),
    }
    try:
        i, f = _components(initial_expr), _components(final_expr)
        out.update({
            "Initial G": i["G"], "Initial Peak Live Cts": i["live"],
            "Final N": f["N"], "Final L": f["L"], "Final K": f["K"], "Final G": f["G"],
            "Final Galois Keys (est MB)": round(f["galois"], 2),
            "Final Live Ciphertexts (est MB)": round(f["cts"], 2),
            "Final Peak Live Cts": f["live"],
            "Final Context+Scratch (est MB)": round(f["ctx"], 2),
            "Final Relin Key (est MB)": round(f["relin"], 2),
        })
    except Exception as e:                      # diagnostics must never break an evaluation run
        out["Metrics Error"] = f"{type(e).__name__}: {e}"[:120]
    if prefix:      # secondary view (e.g. the rollback-picked expression): shorter, every column prefixed
        for k in ("Started Infeasible", "Initial G", "Initial Peak Live Cts"):
            out.pop(k, None)
        out = {prefix + k: v for k, v in out.items()}
    return out


class MemoryEstimator:
    """Drop-in replacement of NoiseEstimator: .estimate(expr_or_tree) -> peak RAM in MB.
    Training uses margin=False (central estimate); keep the margin for deployment checks only."""

    def __init__(self, margin=False):
        self.margin = margin

    def estimate(self, expr):
        if not isinstance(expr, str):
            from serializer import expr_to_str      # pytrs is on sys.path (see top of this file)
            expr = expr_to_str(expr)
        return peak_ram_mb(expr, margin=self.margin)
