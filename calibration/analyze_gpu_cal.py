import csv, sys, math, statistics as st
rows = []
for r in csv.DictReader(open(sys.argv[1])):
    try:
        rows.append(dict(id=r["id"], N=int(r["N"]), L=int(r["L"]), G=int(r["G"]),
                         est=float(r["est"]), real=float(r["real"]), match=r.get("match", "True") == "True"))
    except (ValueError, KeyError):
        pass
print("rows:", len(rows), " label-match:", sum(r["match"] for r in rows))
for r in rows:
    r["grp"] = f'N{r["N"]}_L{r["L"]}_G{"0" if r["G"] == 0 else ">0"}'
    r["err"] = 100.0 * (r["est"] - r["real"]) / r["real"]
    r["ratio"] = r["real"] / r["est"]

def pct(v, q):
    v = sorted(v); return v[min(len(v) - 1, int(q * len(v)))]

print("\n== error % = (est-real)/real, by group ==")
print(f'{"group":18s} {"n":>4s} {"median":>8s} {"min":>8s} {"max":>8s} {"real/est max":>13s}')
groups = {}
for r in rows: groups.setdefault(r["grp"], []).append(r)
for g, v in sorted(groups.items()):
    e = [x["err"] for x in v]
    print(f'{g:18s} {len(v):4d} {st.median(e):8.2f} {min(e):8.2f} {max(e):8.2f} {max(x["ratio"] for x in v):13.3f}')
e = [r["err"] for r in rows]
print(f'{"ALL":18s} {len(rows):4d} {st.median(e):8.2f} {min(e):8.2f} {max(e):8.2f}')
worst = sorted(rows, key=lambda r: r["err"])[:8]
print("\nworst under-estimates:", [(w["id"], w["grp"], round(w["err"], 1)) for w in worst])

print("\n== safety margin m (pred = est*m); leave-one-group-out ==")
def margin(v, q): return max(1.0, pct([x["ratio"] for x in v], q))
print("fit on ALL: max ratio = %.3f  p99 = %.3f  p95 = %.3f" %
      (margin(rows, 1.0), margin(rows, 0.99), margin(rows, 0.95)))
for q, name in ((1.0, "max"), (0.99, "p99")):
    print(f"\nLOGO with margin = {name} of real/est on the other groups:")
    print(f'{"held-out group":18s} {"n":>4s} {"m":>7s} {"worst err%":>11s} {"under-est":>10s}')
    for g, v in sorted(groups.items()):
        rest = [x for x in rows if x["grp"] != g]
        if not rest: continue
        m = margin(rest, q)
        errs = [100.0 * (x["est"] * m - x["real"]) / x["real"] for x in v]
        print(f'{g:18s} {len(v):4d} {m:7.3f} {min(errs):11.2f} {sum(x < 0 for x in errs):6d}/{len(v)}')
over = [100.0 * (r["est"] * margin(rows, 1.0) - r["real"]) / r["real"] for r in rows]
print("\nwith ALL-fit max margin: median over-estimate %.2f%%, max %.2f%%" % (st.median(over), max(over)))
