import csv, statistics as st
rows = []
for f, tag in (("set400_repacked_fix.csv", "base"), ("negate_compare.csv", "negate")):
    for r in csv.DictReader(open(f)):
        est, real = float(r["est"]), float(r["real"])
        rows.append(dict(id=r["id"], tag=tag, N=int(r["N"]), L=int(r["L"]), G=int(r["G"]), est=est, real=real, ratio=real/est))
print("pooled rows:", len(rows))
rs = sorted(x["ratio"] for x in rows)
mx = rs[-1]; p99 = rs[int(.99*len(rs))]
print("max ratio %.3f  p99 %.3f" % (mx, p99))
print("under-estimates: no margin %d, margin 1.05 %d" % (sum(x["ratio"] > 1 for x in rows), sum(x["ratio"] > 1.05 for x in rows)))
groups = sorted({(x["N"], x["L"]) for x in rows})
for rule, f in (("max", max), ("p99", lambda v: sorted(v)[min(len(v)-1, int(.99*len(v)))])):
    under = n = 0; worst = 0.0
    for g in groups:
        m = f([x["ratio"] for x in rows if (x["N"], x["L"]) != g])
        for x in rows:
            if (x["N"], x["L"]) == g:
                n += 1; e = 100*(x["est"]*m - x["real"])/x["real"]
                if e < 0: under += 1; worst = min(worst, e)
    print("LOGO (N,L) margin=%s: under-estimates %d/%d, worst %.2f%%" % (rule, under, n, worst))
for N in (16384, 32768):
    v = [x for x in rows if x["N"] == N]
    print("N=%d n=%d real range %.0f-%.0f MiB, max ratio %.3f" % (N, len(v), min(x["real"] for x in v), max(x["real"] for x in v), max(x["ratio"] for x in v)))
