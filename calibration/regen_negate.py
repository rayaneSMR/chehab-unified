import os, sys, re, csv, shutil
from pathlib import Path
sys.argv = ["x"]
exec(open("/scratch/rs10728/heongpu-project/pilot/prep_set.py").read().split("items = []")[0])

exprs = {}
for i, l in enumerate(x.strip() for x in open(TEMP / "pilot_expressions.txt") if x.strip()):
    exprs[f"e{i}"] = l
for r in csv.DictReader(open(TEMP / "pilot_rotation_pairs.csv")):
    exprs[f"po{r['pair_id']}"] = r["orig_expr"]
    exprs[f"pr{r['pair_id']}"] = r["rewritten_expr"]

ids = [l.strip() for l in open(PILOT / "set400_buildfail.txt") if l.strip()]
bk = PILOT / "circuits_backup_negate"; bk.mkdir(exist_ok=True)
ok, mism = [], 0
for pid in ids:
    expr = exprs[pid]
    old = PILOT / "circuits" / pid / "expr.txt"
    if old.exists() and old.read_text().strip() != expr.strip():
        mism += 1; print(pid, "EXPR MISMATCH with old expr.txt, skipped"); continue
    names = sorted(set(re.findall(r"[A-Za-z_]\w*", expr)) - {"Vec"})
    r = codegen(expr, names)
    if "heongpu_output: generated_fhe.cu" not in r.stdout:
        print(pid, "CODEGEN FAIL", (r.stderr or r.stdout)[-150:].replace("\n", " ")); continue
    src = (RUNNER / "generated_fhe.cu").read_text()
    bad = len(re.findall(r"negate_inplace\([^,()]+,", src))
    if bad:
        print(pid, "STILL 2-ARG NEGATE:", bad); continue
    d = PILOT / "circuits" / pid
    if d.exists(): shutil.copytree(d, bk / pid, dirs_exist_ok=True)
    d.mkdir(parents=True, exist_ok=True)
    shutil.copy2(RUNNER / "generated_fhe.cu", d / "generated_fhe.cu")
    (d / "expr.txt").write_text(expr)
    ok.append(pid); print(pid, "ok", flush=True)
(PILOT / "regen_ok.txt").write_text("\n".join(ok) + "\n")
print("regenerated:", len(ok), "of", len(ids), " expr mismatches:", mism)
