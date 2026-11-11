#!/usr/bin/env python3
"""Multi-objective metrics (IC, HV, SP, EU) and the bisection ablation on the 46 benchmarks.

Merges two bisection runs made with the same joint agent and settings:
  * the 43-benchmark run (job 19038297) on fhe_rl/datasets/benchmarks.txt, whose probes are
    named expr_<line>; the 26 unnamed (synthetic) lines are dropped, and
  * the run on the 9 missing benchmarks (scripts/run_mo_bisection_46.sbatch), already named.

The indicators use the definitions of the manuscript, i.e. the functions of
scripts/recompute_mo_metrics.py (that script reproduces the current 43-benchmark tables):
  normalization  per benchmark, over its feasible probes of all budgets and both phases:
                 T_hat = (C_exec - T_min) / (T_max - T_min), T_max = exec cost of the input
                 K_hat = C_keys / K_max
  grid front     non-dominated circuits of the 10 grid preferences
  full front     grid + bisection probes (same normalization, so both are comparable)

    python scripts/mo_metrics_46.py \
        --run43 RL/test_results/hpc_done/bisection_unified_19038297.xlsx \
        --run9  RL/test_results/bisection_unified_missing_<job>.xlsx \
        --output RL/test_results/mo_metrics_46.xlsx --tables-dir tables

Without --run9 it recomputes the 43-benchmark values (to check against the current tables).
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from recompute_mo_metrics import expected_utility, hypervolume, pareto, sparsity  # noqa: E402

RL = Path(__file__).resolve().parent.parent / "RL" / "fhe_rl" / "datasets"
FAMILY = [("dot_product", "Dot Product"), ("l2_distance", "L2 Distance"), ("hamming_dist", "Hamming Dist."),
          ("lin_reg", "Linear Reg."), ("poly_reg", "Poly. Reg."), ("box_blur", "Box Blur"),
          ("gx_kernel", "Gx"), ("gy_kernel", "Gy"), ("roberts_cross", "Rob. Cross"),
          ("matrix_mul", "Mat. Mul."), ("max", "Max"), ("sort", "Sort"), ("tree", "Tree")]
BUDGET_LABEL = {9000000: r"$\infty$"}

# The 46 end-to-end benchmarks (SUITE of scripts/run_benchmarks_unified.py + the 6 polynomial trees)
_SIZES = {"box_blur": [3, 4, 5], "gx_kernel": [3, 4, 5], "gy_kernel": [3, 4, 5],
          "roberts_cross": [3, 4, 5], "matrix_mul": [3, 4, 5],
          "dot_product": [4, 8, 16, 32], "hamming_dist": [4, 8, 16, 32], "l2_distance": [4, 8, 16, 32],
          "lin_reg": [4, 8, 16, 32], "poly_reg": [4, 8, 16, 32], "max": [3, 4, 5], "sort": [3, 4]}
SUITE46 = ({f"{b}_{n}" for b, sizes in _SIZES.items() for n in sizes}
           | {f"tree_{r}-{d}_poly" for r in ("50-50", "100-50", "100-100") for d in (5, 10)})
assert len(SUITE46) == 46


def family(name):
    return next(label for prefix, label in FAMILY if name.startswith(prefix))


def pretty(name):
    """dot_product_16 -> 16, gy_kernel_3 -> 3x3, tree_100-50-10_poly -> 100-50-10."""
    if name.startswith("tree_"):
        return name[len("tree_"):].replace("_poly", "")
    size = name.rsplit("_", 1)[1]
    sq = ("box_blur", "gx_kernel", "gy_kernel", "roberts_cross", "matrix_mul")
    return rf"{size}$\times${size}" if name.startswith(sq) else size


def load_run43(path, benchmarks, names_xlsx):
    p = pd.read_excel(path, sheet_name="probes")
    exprs = [l.strip() for l in open(benchmarks) if l.strip()]
    nd = pd.read_excel(names_xlsx)
    by_expr = {str(e).strip(): n for n, e in zip(nd["Name"], nd["Expression"])}
    name_of = {f"expr_{i}": by_expr.get(e) for i, e in enumerate(exprs)}
    p["Expression"] = p["Expression"].map(name_of)
    return p[p["Expression"].notna()]          # drops the synthetic programs


def front_metrics(g, t_min, t_max, k_max):
    span = max(t_max - t_min, 1e-9)
    pts = [((t - t_min) / span, (k / k_max) if k_max > 0 else 0.0)
           for t, k in zip(g["final_exec_cost"], g["final_keys_cost"])]
    front = pareto(pts)
    if not front:
        return dict(IC=0, HV=float("nan"), SP=float("nan"), EU=float("nan"))
    return dict(IC=len(front), HV=hypervolume(front), SP=sparsity(front), EU=expected_utility(front))


def compute(probes):
    rows = []
    for name, g_all in probes.groupby("Expression"):
        feas = g_all[g_all["feasible"].astype(bool)]
        if feas.empty:
            continue
        t_max = float(g_all["Initial Ops"].iloc[0])
        t_min = float(feas["final_exec_cost"].min())
        k_max = float(feas["final_keys_cost"].max())
        for budget, g in g_all.groupby("Budget"):
            f = g[g["feasible"].astype(bool)]
            row = {"Budget": budget, "Benchmark": name, "Family": family(name),
                   "Grid Probes": int((g.phase == "grid").sum()),
                   "Bisection Probes": int((g.phase == "bisection").sum())}
            for tag, sub in (("grid", f[f.phase == "grid"]), ("full", f)):
                row.update({f"{k} ({tag})": v for k, v in front_metrics(sub, t_min, t_max, k_max).items()})
            rows.append(row)
    return pd.DataFrame(rows).sort_values(["Budget", "Family", "Benchmark"])


def ablation(per):
    g = per.groupby("Budget")
    abl = pd.DataFrame({"Benchmarks": g.size(), "Probes (grid)": g["Grid Probes"].sum(),
                        "Probes (bisection)": g["Bisection Probes"].sum()})
    for m in ("IC", "HV", "SP", "EU"):
        for tag in ("grid", "full"):
            abl[f"{m} ({tag})"] = g[f"{m} ({tag})"].mean()
    abl["Extra runs (%)"] = 100 * abl["Probes (bisection)"] / abl["Probes (grid)"]
    abl["SP change (%)"] = 100 * (abl["SP (full)"] / abl["SP (grid)"] - 1)
    return abl.reset_index()


def tex_mo_quality(fam, n, budget):
    lines = [r"\begin{table}[t]", r"  \centering",
             rf"  \caption{{Multi-objective quality per benchmark family at $B = {budget}$ bits "
             rf"(grid + bisection, averaged over the benchmarks of each family; {n} benchmarks). "
             r"IC: cardinality; HV: hypervolume ($\uparrow$); SP: sparsity ($\downarrow$); "
             r"EU: expected utility ($\downarrow$).}",
             r"  \label{tab:mo-quality}", r"  \fontsizefortables",
             r"  \begin{tabular}{@{}l c cccc@{}}", r"    \toprule",
             r"    Family & \# & IC & HV & SP & EU \\", r"    \midrule"]
    for fam_name, r in fam.iterrows():
        lines.append(f"    {fam_name:<14} & {int(r['N'])} & {r['IC']:.2f} & {r['HV']:.2f} & {r['SP']:.2f} & {r['EU']:.2f} \\\\")
    lines += [r"    \bottomrule", r"  \end{tabular}", r"\end{table}", ""]
    return "\n".join(lines)


def tex_ablation(abl, n):
    lines = [r"\begin{table}[t]", r"  \centering",
             rf"  \caption{{Pareto front of the preference grid alone (Grid) and with the bisection search "
             rf"(+Bis.), averaged over the {n} benchmarks. Runs: policy runs over all benchmarks.}}",
             r"  \label{tab:ablation-bisection}", r"  \fontsizefortables", r"  \setlength{\tabcolsep}{3pt}",
             r"  \begin{tabular}{@{}l cc cc cc cc cc@{}}", r"    \toprule",
             r"    & \multicolumn{2}{c}{Runs} & \multicolumn{2}{c}{IC $\uparrow$} & \multicolumn{2}{c}{HV $\uparrow$}"
             r" & \multicolumn{2}{c}{SP $\downarrow$} & \multicolumn{2}{c}{EU $\downarrow$} \\",
             r"    \cmidrule(lr){2-3}\cmidrule(lr){4-5}\cmidrule(lr){6-7}\cmidrule(lr){8-9}\cmidrule(l){10-11}",
             r"    $B$ & Grid & +Bis. & Grid & +Bis. & Grid & +Bis. & Grid & +Bis. & Grid & +Bis. \\",
             r"    \midrule"]
    for _, r in abl.iterrows():
        b = BUDGET_LABEL.get(int(r["Budget"]), str(int(r["Budget"])))
        runs_full = int(r["Probes (grid)"] + r["Probes (bisection)"])
        lines.append(f"    {b} & {int(r['Probes (grid)'])} & {runs_full}"
                     + "".join(f" & {r[f'{m} (grid)']:.3f} & {r[f'{m} (full)']:.3f}" for m in ("IC", "HV", "SP", "EU"))
                     + r" \\")
    lines += [r"    \bottomrule", r"  \end{tabular}", r"\end{table}", ""]
    return "\n".join(lines)


def tex_appendix(per, budget):
    sub = per[per.Budget == budget]
    lines = [r"\begin{longtable}{@{}l l cccc@{}}",
             rf"  \caption{{Multi-objective quality per benchmark at $B = {budget}$ bits (grid + bisection).}}"
             r"\label{tab:mo-quality-full} \\",
             r"  \toprule", r"  Family & Size & IC & HV & SP & EU \\", r"  \midrule", r"  \endfirsthead",
             r"  \toprule", r"  Family & Size & IC & HV & SP & EU \\", r"  \midrule", r"  \endhead"]
    order = {lbl: i for i, (_, lbl) in enumerate(FAMILY)}
    sub = sub.assign(_o=sub.Family.map(order), _s=sub.Benchmark.map(_size_key)).sort_values(["_o", "_s"])
    prev = None
    for _, r in sub.iterrows():
        fam = r.Family if r.Family != prev else ""
        prev = r.Family
        lines.append(f"  {fam} & {pretty(r.Benchmark)} & {int(r['IC (full)'])} & {r['HV (full)']:.2f} & "
                     f"{r['SP (full)']:.2f} & {r['EU (full)']:.2f} \\\\")
    lines += [r"  \bottomrule", r"\end{longtable}", ""]
    return "\n".join(lines)


def _size_key(name):
    nums = [int(x) for x in name.replace("_poly", "").replace("-", "_").split("_") if x.isdigit()]
    return tuple(nums)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run43", required=True)
    ap.add_argument("--run9", help="bisection run on the 9 missing benchmarks (names in the probes)")
    ap.add_argument("--benchmarks43", default=str(RL / "benchmarks.txt"), help="expressions file of the 43-run")
    ap.add_argument("--names43", default=str(RL / "benchmarks_names.xlsx"), help="xlsx with columns Name, Expression")
    ap.add_argument("--output", required=True)
    ap.add_argument("--tables-dir", help="write mo_quality.tex, ablation_bisection.tex, mo_quality_full.tex here")
    ap.add_argument("--budget", type=int, default=369, help="budget of the per-family table")
    args = ap.parse_args()

    probes = [load_run43(args.run43, args.benchmarks43, args.names43)]
    if args.run9:
        p9 = pd.read_excel(args.run9, sheet_name="probes")
        dup = set(p9.Expression) & set(probes[0].Expression)
        if dup:
            sys.exit(f"Benchmarks in both runs: {sorted(dup)}")
        probes.append(p9)
    probes = pd.concat(probes, ignore_index=True)
    if args.run9:
        # the 43-run also has sizes 3 and 5 of dot_product / hamming_dist / l2_distance, which are
        # not in the 46-benchmark suite (scripts/run_benchmarks_unified.py SUITE + 6 trees)
        extra = sorted(set(probes.Expression) - SUITE46)
        if extra:
            print(f"Not in the 46-benchmark suite, dropped: {extra}")
        probes = probes[probes.Expression.isin(SUITE46)]
    per = compute(probes)
    n = per.Benchmark.nunique()
    print(f"{n} benchmarks")
    if args.run9 and n != 46:
        print("WARNING: expected 46 benchmarks")

    abl = ablation(per)
    sub = per[per.Budget == args.budget]
    fam = sub.groupby("Family").agg(N=("Benchmark", "size"), IC=("IC (full)", "mean"), HV=("HV (full)", "mean"),
                                    SP=("SP (full)", "mean"), EU=("EU (full)", "mean"))
    fam = fam.reindex([lbl for _, lbl in FAMILY]).dropna(how="all")

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(out) as w:
        per.to_excel(w, sheet_name="per_benchmark", index=False)
        abl.round(4).to_excel(w, sheet_name="bisection_ablation", index=False)
        fam.round(4).to_excel(w, sheet_name=f"mo_quality_B{args.budget}")
    if args.tables_dir:
        td = Path(args.tables_dir)
        td.mkdir(parents=True, exist_ok=True)
        (td / "mo_quality.tex").write_text(tex_mo_quality(fam, n, args.budget))
        (td / "ablation_bisection.tex").write_text(tex_ablation(abl, n))
        (td / "mo_quality_full.tex").write_text(tex_appendix(per, args.budget))

    pd.set_option("display.width", 200)
    print("\nBisection ablation (averaged over benchmarks):\n", abl.round(4).to_string(index=False))
    print(f"\nMO quality per family, B = {args.budget}:\n", fam.round(3).to_string())
    d = abl
    print("\nNumbers for the text:")
    print(f"  benchmarks: {n}; grid runs per budget: {int(d['Probes (grid)'].iloc[0])}")
    print(f"  extra policy runs: {d['Extra runs (%)'].min():.1f}% to {d['Extra runs (%)'].max():.1f}%")
    dic = d["IC (full)"] - d["IC (grid)"]
    print(f"  extra circuits:    {dic.min():.3f} to {dic.max():.3f}")
    print(f"  sparsity change:   {d['SP change (%)'].max():.1f}% to {d['SP change (%)'].min():.1f}%")
    print(f"  max HV gain:       {(d['HV (full)'] - d['HV (grid)']).max():.4f}")
    print(f"  max |EU change|:   {(d['EU (full)'] - d['EU (grid)']).abs().max():.4f}")
    print(f"\nWrote {out}" + (f" and {args.tables_dir}/*.tex" if args.tables_dir else ""))


if __name__ == "__main__":
    main()
