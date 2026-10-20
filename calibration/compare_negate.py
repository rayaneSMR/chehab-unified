import csv, re, sys, statistics as st
R = "/scratch/rs10728/heongpu-project"; P = R + "/pilot"; RL = R + "/src/chehab-unified/RL"
sys.path[:0] = [RL + "/pytrs", RL + "/fhe_rl"]
import packing_fix as packing
from ckks_memory_estimator import estimate_expression_memory as est_fn

def cu_params(src):
    o = {}
    m = re.search(r"poly_modulus_degree\s*=\s*(\d+)", src); o["N"] = int(m.group(1)) if m else None
    for k, nm in (("L", "q_bits"), ("K", "p_bits")):
        m = re.search(nm + r"\s*=\s*\{([^}]*)\}", src)
        o[k] = len([x for x in m.group(1).split(",") if x.strip()]) if m else None
    m = re.search(r"getRotationSteps\(\)\s*\{\s*return\s*\{([^}]*)\}", src)
    s = {int(x) for x in m.group(1).split(",") if x.strip()} if m else set()
    o["G"] = len(s - {0}) if m else None
    return o

rows, skipped = [], []
for r in csv.DictReader(open(P + "/negate_raw.csv")):
    i = r["id"]
    if r["rc"] != "0" or r["pool_MB"] == "NA":
        skipped.append((i, "run rc=" + r["rc"])); continue
    d = P + "/circuits/" + i
    expr = open(d + "/expr.txt").read().strip(); src = open(d + "/generated_fhe.cu").read()
    try:
        packed = packing.pack_expr_str(expr); e = est_fn(packed, backend="gpu")
    except Exception as ex:
        skipped.append((i, "estimator: " + str(ex)[:80])); continue
    c = cu_params(src); p = e.params; real = float(r["pool_MB"])
    rows.append(dict(id=i, N=p.N, L=p.L, G=e.rotation_steps, est=e.total_mb, real=real,
        err=100*(e.total_mb-real)/real, ratio=real/e.total_mb,
        lab_est=len(set(re.findall(r"\bc\d+\b", packed))),
        lab_cu=len(set(re.findall(r'encryptedInputs.at\("(c\d+)"\)', src))),
        match=(p.N, p.L, p.K, e.rotation_steps) == (c["N"], c["L"], c["K"], c["G"])))
with open(P + "/negate_compare.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
print("measured ok:", len(rows), " skipped:", len(skipped))
for s in skipped[:10]: print("  skip", s)
print("labels agree:", sum(x["lab_est"] == x["lab_cu"] for x in rows), "/", len(rows))
print("params match:", sum(x["match"] for x in rows), "/", len(rows))
e = [x["err"] for x in rows]
print(f"err%: min {min(e):.2f} median {st.median(e):.2f} max {max(e):.2f}")
print("max real/est ratio:", round(max(x["ratio"] for x in rows), 3), " (current margin 1.05)")
print("under-estimates, no margin:", sum(v < 0 for v in e), " with 1.05:",
      sum(100*(x["est"]*1.05-x["real"])/x["real"] < 0 for x in rows))
g = {}
for x in rows: g.setdefault((x["N"], x["L"]), []).append(x["err"])
for k in sorted(g): print(k, "n", len(g[k]), "median %.2f min %.2f max %.2f" % (st.median(g[k]), min(g[k]), max(g[k])))
