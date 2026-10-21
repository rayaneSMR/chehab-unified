#!/usr/bin/env python3
"""
Fit and compare the extended HEonGPU memory targets against measurements.

Inputs : totals_circuits.csv (from run_total_mem.py, joined with est/real), totals_probe.csv (ctx_probe rows)
Targets: device = device-wide GPU peak delta (pool + context + driver + out-of-pool allocations)
         host   = process peak resident host memory (comparable with the Lattigo RSS target)
Model  : target_hat = (a + b * est) * margin   with est = raw estimator MB (before scale/margin)
         margin  = smallest value with zero in-sample under-estimates (max measured/predicted), like the
                   existing 1.05 rule, so it is reported together with leave-one-group-out numbers.
Output : memory_calib_gpu_full.json, fit_report.txt (also printed), circuits_with_pred.csv
"""
import argparse, csv, json, math, statistics, sys
from collections import defaultdict
import numpy as np

POOL_MARGIN = 1.05   # shipped pool margin, used to show what the current estimator reports


def f(x):
    try:
        return float(x)
    except Exception:
        return float("nan")


def load_agg(path):
    """One row per id: max over successful repetitions (conservative), plus median for reference."""
    g = defaultdict(list)
    for r in csv.DictReader(open(path)):
        if str(r.get("rc", "0")) not in ("0", "0.0"):
            continue
        g[r["id"]].append(r)
    out = []
    for i, rs in g.items():
        def mx(k): return max(f(r[k]) for r in rs)
        def md(k): return statistics.median(f(r[k]) for r in rs)
        r0 = rs[0]
        out.append(dict(id=i, N=int(f(r0["N"])) if r0["N"] else 0, L=int(f(r0["L"])) if r0["L"] else 0,
                        G=int(f(r0["G"])) if r0["G"] else 0, est=f(r0["est"]), pool=f(r0["pool_real"]),
                        pool_stdout=mx("pool_stdout") if any(r["pool_stdout"] for r in rs) else float("nan"),
                        dev=mx("dev_delta_mib"), dev_med=md("dev_delta_mib"), proc=mx("proc_peak_mib"),
                        host=mx("host_rss_mib"), host_med=md("host_rss_mib"), reps=len(rs)))
    return out


def stats(err):
    e = np.array(err)
    if not len(e):
        return "n/a"
    return (f"median {np.median(e)*100:+.1f}% [min {e.min()*100:+.1f}, max {e.max()*100:+.1f}] "
            f"under-est {int((e < 0).sum())}/{len(e)}")


def fit_line(est, y):
    b, a = np.polyfit(est, y, 1)
    return float(a), float(b)


def fit_target(rows, key):
    est = np.array([r["est"] for r in rows]); y = np.array([r[key] for r in rows])
    a, b = fit_line(est, y)
    pred = a + b * est
    ratio = y / np.maximum(pred, 1e-9)
    return dict(a=a, b=b, margin=float(math.ceil(ratio.max() * 1000) / 1000), max_ratio=float(ratio.max()))


def logo(rows, key, groupfn):
    """Leave one group out: fit on the others, margin = max ratio of the others, test on the held-out group."""
    groups = defaultdict(list)
    for r in rows:
        groups[groupfn(r)].append(r)
    errs = []
    for g, held in groups.items():
        train = [r for r in rows if groupfn(r) != g]
        if len(train) < 5:
            continue
        m = fit_target(train, key)
        for r in held:
            pred = (m["a"] + m["b"] * r["est"]) * m["margin"]
            errs.append((pred - r[key]) / r[key])
    return errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--circuits", required=True)
    ap.add_argument("--probe", default=None)
    ap.add_argument("--out", default="memory_calib_gpu_full.json")
    ap.add_argument("--report", default="fit_report.txt")
    ap.add_argument("--eval-only", default=None, help="existing JSON: evaluate it on --circuits, no refit")
    a = ap.parse_args()

    rows = [r for r in load_agg(a.circuits) if r["est"] == r["est"] and r["est"] > 0 and r["dev"] > 0]
    L = []
    P = L.append
    P(f"circuits with measurements: {len(rows)}  (G>0: {sum(r['G']>0 for r in rows)})")
    ctx = {}
    if a.probe:
        pr = [r for r in load_agg(a.probe)]
        if pr:
            ctx = dict(ctx_dev_mib=statistics.median(r["dev"] for r in pr),
                       ctx_host_mib=statistics.median(r["host"] for r in pr))
            P(f"CUDA context probe (bare program): device +{ctx['ctx_dev_mib']:.0f} MiB, host RSS {ctx['ctx_host_mib']:.0f} MiB")

    # --- what the pool number leaves out --------------------------------------------------------
    have_pool = [r for r in rows if r["pool"] == r["pool"] and r["pool"] > 0]
    if have_pool:
        extra = np.array([r["dev"] - r["pool"] for r in have_pool])
        ratio = np.array([r["dev"] / r["pool"] for r in have_pool])
        P("\n== Device-wide peak vs HEonGPU pool peak (same circuits) ==")
        P(f"outside-pool device MiB: median {np.median(extra):.0f}, min {extra.min():.0f}, max {extra.max():.0f}")
        P(f"device/pool ratio:       median {np.median(ratio):.3f}, min {ratio.min():.3f}, max {ratio.max():.3f}")
        small = [r for r in have_pool if r["pool"] < 100]
        if small:
            P(f"circuits with pool < 100 MiB: {len(small)}; median device/pool there = "
              f"{np.median([r['dev']/r['pool'] for r in small]):.2f}  (context dominates small circuits)")
        ps = [r for r in have_pool if r["pool_stdout"] == r["pool_stdout"]]
        if ps:
            d = np.array([(r["pool_stdout"] - r["pool"]) / r["pool"] for r in ps])
            P(f"pool re-measured in same run vs CSV 'real': median {np.median(d)*100:+.1f}% [{d.min()*100:+.1f}, {d.max()*100:+.1f}]")
    hp = np.array([r["host"] for r in rows])
    P(f"host RSS MiB: min {hp.min():.0f}, median {np.median(hp):.0f}, max {hp.max():.0f}")
    pp = [r for r in rows if r["proc"] > 0]
    if pp:
        d = np.array([(r["proc"] - r["dev"]) / r["dev"] for r in pp])
        P(f"NVML per-process vs device-wide delta: median {np.median(d)*100:+.1f}% [{d.min()*100:+.1f}, {d.max()*100:+.1f}]")

    # --- calibration ---------------------------------------------------------------------------
    if a.eval_only:
        calib = json.load(open(a.eval_only))
    else:
        calib = dict(dev=fit_target(rows, "dev"), host=fit_target(rows, "host"), **ctx,
                     n_circuits=len(rows), has_rotations=any(r["G"] > 0 for r in rows))
        calib = {"device": calib.pop("dev"), "host": calib.pop("host"), **calib}
        json.dump(calib, open(a.out, "w"), indent=2)
        P(f"\nwrote {a.out}")

    P("\n== Comparison: estimate vs measured, error = (estimate - measured) / measured ==")
    out_rows = []
    for name, key in (("device", "dev"), ("host", "host")):
        c = calib[name]
        P(f"\n[{name}]  fit: ({c['a']:.1f} MiB + {c['b']:.4f} * est) * margin {c['margin']}")
        old = [(r["est"] * POOL_MARGIN - r[key]) / r[key] for r in rows]
        P(f"  current pool estimator (est*{POOL_MARGIN}) vs {name} measurement: {stats(old)}")
        e0 = [((c["a"] + c["b"] * r["est"]) - r[key]) / r[key] for r in rows]
        e1 = [((c["a"] + c["b"] * r["est"]) * c["margin"] - r[key]) / r[key] for r in rows]
        P(f"  new model, margin 1.0:  {stats(e0)}")
        P(f"  new model, margin {c['margin']}: {stats(e1)}")
        for Nn in sorted({r["N"] for r in rows}):
            sub = [e for e, r in zip(e1, rows) if r["N"] == Nn]
            P(f"    N={Nn}: {stats(sub)}")
        if not a.eval_only:
            P(f"  leave-one-(N,L)-group-out, max-ratio margin: {stats(logo(rows, key, lambda r: (r['N'], r['L'])))}")
            P(f"  leave-one-circuit-family-out:               {stats(logo(rows, key, lambda r: ''.join(ch for ch in r['id'] if ch.isdigit()) or r['id']))}")
        for r, e in zip(rows, e1):
            r.setdefault("pred_" + name, (calib[name]["a"] + calib[name]["b"] * r["est"]) * calib[name]["margin"])
    if any(r["G"] > 0 for r in rows):
        for name, key in (("device", "dev"), ("host", "host")):
            e = [(r["pred_" + name] - r[key]) / r[key] for r in rows if r["G"] > 0]
            P(f"\nROTATION circuits only [{name}]: {stats(e)}  <- first real check of the (G+1) key term")
    else:
        P("\nNOTE: no circuit with G>0 -> Galois-key memory is still NOT validated for any target.")

    with open("circuits_with_pred.csv", "w", newline="") as fo:
        w = csv.writer(fo)
        w.writerow(["id", "N", "L", "G", "est", "pool", "dev", "host", "pred_device", "pred_host"])
        for r in rows:
            w.writerow([r["id"], r["N"], r["L"], r["G"], r["est"], r["pool"], r["dev"], r["host"],
                        round(r["pred_device"], 2), round(r["pred_host"], 2)])
    text = "\n".join(L)
    print(text)
    open(a.report, "w").write(text + "\n")


if __name__ == "__main__":
    main()
