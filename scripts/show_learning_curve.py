#!/usr/bin/env python3
"""
show_learning_curve.py -- Terminal ASCII Learning Curve & Convergence Analyzer
Works with pure standard library (no dependencies needed), parses logs & evaluations.npz.
"""

import os
import re
import sys
import glob

def parse_training_log(log_path):
    """Parse step progress and rollout metrics from training log."""
    if not os.path.isfile(log_path):
        return []

    # Pattern: [Step Progress] 3,120,000 / 5,000,000 (62.40%) | Elapsed: ... | FPS: ... | Cost Red: +79.0% | Compl: 100.0%
    prog_re = re.compile(
        r"\[Step Progress\]\s+([\d,]+)\s+/\s+([\d,]+)\s+\(([\d\.]+)%\).*?Cost Red:\s*([+\-]?[\d\.]+)%.*?Compl:\s*([\d\.]+)%"
    )
    # Pattern: ep_rew_mean | 63.4
    rew_re = re.compile(r"\|\s+ep_rew_mean\s+\|\s+([\d\.\-]+)\s+\|")
    step_re = re.compile(r"\|\s+total_timesteps\s+\|\s+(\d+)\s+\|")

    data = []
    current_rew = None

    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            rm = rew_re.search(line)
            if rm:
                try:
                    current_rew = float(rm.group(1))
                except ValueError:
                    pass

            pm = prog_re.search(line)
            if pm:
                step = int(pm.group(1).replace(",", ""))
                pct = float(pm.group(3))
                cost_red = float(pm.group(4))
                compl = float(pm.group(5))
                data.append({
                    "step": step,
                    "pct": pct,
                    "cost_red": cost_red,
                    "compl": compl,
                    "reward": current_rew,
                })
    return data

def parse_eval_npz():
    """Try to read evaluations.npz if numpy is available."""
    try:
        import numpy as np
    except ImportError:
        return None

    files = glob.glob("RL/eval/best_model_model_*18848453*/evaluations.npz") or \
            glob.glob("eval/best_model_model_*18848453*/evaluations.npz") or \
            glob.glob("**/evaluations.npz", recursive=True)
    if not files:
        return None

    try:
        npz = np.load(files[0])
        timesteps = npz["timesteps"].tolist()
        results = npz["results"]
        means = results.mean(axis=1).tolist()
        mins = results.min(axis=1).tolist()
        maxs = results.max(axis=1).tolist()
        return [{"step": t, "reward_mean": m, "reward_min": mn, "reward_max": mx}
                for t, m, mn, mx in zip(timesteps, means, mins, maxs)]
    except Exception:
        return None

def ascii_chart(series, width=50, height=12, label="Metric"):
    """Render a clean ASCII line chart in terminal."""
    if not series or len(series) < 2:
        return ""
    vals = [s[1] for s in series]
    min_v, max_v = min(vals), max(vals)
    if max_v == min_v:
        max_v += 1.0

    lines = []
    lines.append(f"\n  ^ {label} (max: {max_v:.1f})")
    n_pts = len(series)

    # Sample width points
    sample_indices = [int(i * (n_pts - 1) / (width - 1)) for i in range(width)]
    sampled_vals = [vals[idx] for idx in sample_indices]

    for h in range(height, -1, -1):
        threshold = min_v + (max_v - min_v) * (h / height)
        row = []
        for v in sampled_vals:
            norm = (v - min_v) / (max_v - min_v) * height
            if abs(norm - h) < 0.5:
                row.append("█" if h == int(round(norm)) else "•")
            elif norm > h:
                row.append("│")
            else:
                row.append(" ")
        prefix = f"{threshold:>6.1f} |" if h in (height, height // 2, 0) else "       |"
        lines.append(f"  {prefix}{''.join(row)}")

    lines.append(f"       +{'-'*width}> Time / Steps")
    start_step = series[0][0]
    end_step = series[-1][0]
    lines.append(f"       {start_step:<15,d}{' '*(width - 30)}{end_step:>15,d}\n")
    return "\n".join(lines)

def main():
    log_candidates = (
        glob.glob("logs/train_unified_ram_film_v3_18848453.log") or
        glob.glob("logs/train_unified_ram_film_v3_*.log") or
        glob.glob("*.log")
    )
    log_path = log_candidates[0] if log_candidates else "train.log"

    print("=" * 70)
    print("   UNIFIED-RAM-FILM TRAINING CONVERGENCE & LEARNING CURVE")
    print("=" * 70)

    data = parse_training_log(log_path)
    eval_data = parse_eval_npz()

    if not data and not eval_data:
        print(f"No log data found in {log_path} or evaluations.npz.")
        return

    if data:
        latest = data[-1]
        print(f"\n[CURRENT TRAINING STATUS]")
        print(f"  • Timestep:           {latest['step']:,} / 5,000,000 ({latest['pct']:.2f}%)")
        print(f"  • Cost Reduction:     +{latest['cost_red']:.1f}%")
        print(f"  • Safe Compliance:    {latest['compl']:.1f}%")
        if latest['reward'] is not None:
            print(f"  • Episode Reward:     {latest['reward']:.2f}")

        # Subsample progression for tabular display
        step_interval = 200_000
        milestones = {}
        for d in data:
            bucket = (d["step"] // step_interval) * step_interval
            milestones[bucket] = d

        print(f"\n{'-'*70}")
        print(f" {'Step':>11} | {'Progress':>8} | {'Cost Reduction':>15} | {'Compliance':>11} | {'Reward':>8}")
        print(f"{'-'*70}")
        for b in sorted(milestones.keys()):
            m = milestones[b]
            rew_str = f"{m['reward']:.1f}" if m['reward'] is not None else "  N/A"
            print(f" {m['step']:>11,d} | {m['pct']:>7.1f}% | {m['cost_red']:>+14.1f}% | {m['compl']:>10.1f}% | {rew_str:>8}")
        print(f"{'-'*70}")

        # Render ASCII Curve for Cost Reduction %
        cost_series = [(d["step"], d["cost_red"]) for d in data[::max(1, len(data)//100)]]
        print(ascii_chart(cost_series, width=54, height=10, label="Cost Reduction %"))

    if eval_data:
        print("\n" + "=" * 70)
        print("   VALIDATION EVALUATION MILESTONES (Unseen Evaluation Set)")
        print("=" * 70)
        print(f" {'Step':>11} | {'Mean Reward':>14} | {'Min Reward':>12} | {'Max Reward':>12}")
        print(f"{'-'*70}")
        for e in eval_data[-12:]:
            print(f" {e['step']:>11,d} | {e['reward_mean']:>14.2f} | {e['reward_min']:>12.2f} | {e['reward_max']:>12.2f}")
        print(f"{'-'*70}")

        eval_series = [(e["step"], e["reward_mean"]) for e in eval_data]
        if len(eval_series) >= 2:
            print(ascii_chart(eval_series, width=54, height=10, label="Validation Mean Reward"))

if __name__ == "__main__":
    main()
