# Multi-objective quality and bisection ablation on the 46 benchmarks (2026-11-11)

Completes the multi-objective evaluation (IC, HV, SP, EU) and the bisection ablation, computed so
far on the 43 benchmarks of `fhe_rl/datasets/benchmarks.txt` (job 19038297), with the 9 end-to-end
benchmarks that were missing:

    Gy 3x3, 4x4, 5x5 | Roberts Cross 3x3, 4x4, 5x5 | Mat. Mul. 5x5 | Tree 100-50-10, 100-100-10

- **Job:** 19348949 (`scripts/run_mo_bisection_46.sbatch`), three steps:
  1. compile each of the 9 C++ benchmarks once and save the expression the compiler gives the agent
     (`scripts/dump_benchmark_expressions.py`) -> `RL/benchmarks_missing9.txt`;
  2. bisection on these 9, with the settings of the 43-benchmark run: 10 grid preferences
     w_ops = 0.1 ... 1.0, bisection depth 3, budgets 230, 236, 369, 9,000,000, method `nato_sc`
     -> `RL/test_results/bisection_unified_missing_19348949.xlsx`;
  3. merge with `RL/test_results/hpc_done/bisection_unified_19038297.xlsx`, drop the 26 synthetic
     programs and compute the indicators (`scripts/mo_metrics_46.py`).
- **Agent:** the model of job 19038297, `RL/fhe_rl/trained_models/unified_joint_noise_19038296_best_4.6M.zip`.
- **Indicators:** definitions of the manuscript, as `scripts/recompute_mo_metrics.py` (which
  reproduces the current 43-benchmark tables). Normalization per benchmark over its feasible
  probes of all budgets: T = (C_exec - T_min) / (T_max - T_min) with T_max the cost of the input
  program, K = C_keys / K_max. HV w.r.t. (1.1, 1.1) divided by 1.21; SP divided by 2; EU over 101
  preferences. Grid front = the 10 grid preferences; full front = grid + bisection, same
  normalization.
- **Code:** branch `threshold-e2e-exec-time` at `06181d8b`, `c2` reservation, conda env `fhe_rl`.
  Log: `logs/output.mo_bisection_46.19348949.txt`, bisection log
  `logs/unified_bisection_missing_19348949.log`.

## Files

- `RL/test_results/mo_metrics_46_19348949.xlsx`: sheets `per_benchmark` (indicators of the grid and
  full fronts per benchmark and budget), `bisection_ablation` (averages per budget, policy runs),
  `mo_quality_B369` (per family at B = 369).
- `RL/test_results/mo_tables_46_19348949/`: LaTeX tables `mo_quality.tex` (Table tab:mo-quality),
  `ablation_bisection.tex` (Table tab:ablation-bisection), `mo_quality_full.tex` (per-benchmark
  appendix table).
- The job log ends with the numbers of the text (extra policy runs, extra circuits, sparsity
  change, HV gain, EU change).
