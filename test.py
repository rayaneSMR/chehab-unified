import numpy as np, pandas as pd
import matplotlib.pyplot as plt

BASE = "experiments/results/All_Methods"
MAP = {"nsga2":"NSGA-II","firefly":"Firefly (RB-IFA)","abc":"HiveNAS (ABC)",
       "pso":"MOPSO","mowso":"MOWSO","random":"Random Search"}
CTX = {1:"CIFAR-10",7:"CIFAR-100",13:"ImageNet16-120"}   # EdgeGPU only
COL = {"NSGA-II":"#1f77b4","Firefly (RB-IFA)":"#cc79a7","HiveNAS (ABC)":"#d55e00",
       "MOPSO":"#e69f00","MOWSO":"#009e73","Random Search":"#7f7f7f"}
order = list(MAP.values())

cm, br = {}, {}
for k, name in MAP.items():
    cm[name] = pd.read_csv(f"{BASE}/{k}/{k}_context_metrics.csv").set_index("context_id")
    br[name] = pd.read_csv(f"{BASE}/{k}/{k}_metrics_by_run.csv")

sky = pd.read_csv("experiments/results/optimal_pareto_fronts.csv")
sky_acc = {c: sky[(sky.context_id==c)]["accuracy"].max() for c in CTX}
sky_lat = {c: sky[(sky.context_id==c)]["latency"].min() for c in CTX}

def med(name, col, c):  # median over runs (random lacks median cols -> compute from by_run)
    if col in cm[name].columns:
        return cm[name].loc[c, col]
    m = {"hv":"hv","igd_plus":"igd_plus","runtime_sec":"runtime_sec"}[col]
    return br[name][(br[name].context_id==c)][m].median()

# ---- Figure 4.1 & 4.2 ----
for fig, vals, sk, xlabel, log in [
    ("fig41_accuracy", lambda n,c: cm[n].loc[c,"best_accuracy_mean"], sky_acc,
     "Best accuracy on the front (%)", False),
    ("fig42_latency",  lambda n,c: cm[n].loc[c,"best_latency_mean"], sky_lat,
     "Best latency on the front (ms, log scale)", True)]:
    fig_, axes = plt.subplots(3, 1, figsize=(7.5, 8))
    for ax, (c, ds) in zip(axes, CTX.items()):
        for i, n in enumerate(order):
            v = vals(n, c)
            ax.hlines(i, 0 if log else ax.get_xlim()[0], v, color=COL[n], lw=3)
            ax.plot(v, i, "o", color=COL[n], ms=8)
            ax.text(v, i, f"  {v:.2f}", va="center", fontsize=9)
        ax.axvline(sk[c], ls="--", c="k")
        ax.set_yticks(range(len(order))); ax.set_yticklabels(order)
        if log: ax.set_xscale("log")
        ax.set_title(ds); ax.set_xlabel(xlabel); ax.grid(axis="x", alpha=.3)
    fig_.tight_layout(); fig_.savefig(f"{fig}.png", dpi=300)

# ---- Figure 4.3 ----
nhv = [float(np.median([med(n,"hv",c) for c in CTX])) for n in order]
igd = [float(np.median([med(n,"igd_plus",c) for c in CTX])) for n in order]
rt  = [float(np.median([med(n,"runtime_sec",c) for c in CTX])) for n in order]

fig, axes = plt.subplots(1, 3, figsize=(13, 4))
for ax, data, title, log in [
    (axes[0], nhv, "Normalized hypervolume (nHV)\nhigher is better", False),
    (axes[1], igd, "IGD$^+$\nlower is better (log scale)", True),
    (axes[2], rt,  "Runtime\nlower is better (log scale)", True)]:
    bars = ax.bar(range(6), data, color=[COL[n] for n in order])
    for b, v in zip(bars, data):
        ax.text(b.get_x()+b.get_width()/2, v, f"{v:.4g}", ha="center",
                va="bottom", fontsize=9)
    if log: ax.set_yscale("log")
    ax.set_xticks(range(6)); ax.set_xticklabels(order, rotation=20, ha="right")
    ax.set_title(title, fontsize=10); ax.grid(axis="y", alpha=.3)
axes[0].axhline(1.0, ls="--", c="k"); axes[0].text(5, 1.0, "Skyline (nHV = 1)",
                 fontsize=8, va="bottom", ha="right")
fig.tight_layout(); fig.savefig("fig43_nhv_igd_runtime.png", dpi=300)
print("done")