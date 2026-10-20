import csv, re, statistics as st
rows = []
for r in csv.DictReader(open("set400_repacked_fix.csv")):
    est, real = float(r["est"]), float(r["real"])
    rows.append(dict(id=r["id"], fam=re.sub(r"\D", "", r["id"]), est=est, real=real,
                     ratio=real/est, err=100*(est-real)/real))

# 1. po/pr duplicate check
d = {r["id"]: r for r in rows}
same = sum(1 for k in d if k.startswith("po") and "pr"+k[2:] in d
           and abs(d[k]["real"]-d["pr"+k[2:]]["real"]) < 1e-9)
tot = sum(1 for k in d if k.startswith("po") and "pr"+k[2:] in d)
print(f"po/pr pairs: {tot}, identical real: {same}")

# 2. dedupe on (est, real), then leave-one-family-out
seen, uniq = set(), []
for r in rows:
    key = (round(r["est"], 4), round(r["real"], 4))
    if key not in seen:
        seen.add(key); uniq.append(r)
print("rows:", len(rows), " unique measurements:", len(uniq))

fams = sorted({r["fam"] for r in uniq}, key=int)
for rule, f in (("max", max), ("p99", lambda v: sorted(v)[min(len(v)-1, int(.99*len(v)))])):
    under, worst, n = 0, 0.0, 0
    for fam in fams:
        train = [r["ratio"] for r in uniq if r["fam"] != fam]
        m = f(train)
        for r in uniq:
            if r["fam"] == fam:
                n += 1
                e = 100*(r["est"]*m - r["real"])/r["real"]
                if e < 0: under += 1; worst = min(worst, e)
    print(f"LOFO families, margin={rule}: under-estimates {under}/{n}, worst {worst:.2f}%")
