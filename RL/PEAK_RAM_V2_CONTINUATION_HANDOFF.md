# Lattigo Peak-RAM v2: Current Handoff

This note records the current state of the Lattigo-only peak-RAM validation.
It supersedes the earlier continuation note that described the development
retry as still running.

## Constraints That Still Matter

- Diagnose and calibrate only on the development split.
- The frozen protocol is `RL/compiled_corpus_protocol.json`
  (`gc_headroom_factor = 0.48789950971366136`, dev-only p95).
- Use `conda run -n chehabEnv ...`; do not install packages into `base`.
- Keep program-dependent terms analytic; do not add per-benchmark or per-width
  fitted constants.
- Preserve historical v1 results and disclose that the v1 aggregate holdout was
  already seen. Stale v1 `lo/hi` columns in scored CSVs are a frozen reference
  baseline only; v2 gates never read them.
- Do not sweep unrelated dirty/generated files into a commit.

## Completed Development Work

- The corrected development retry finished.
- Corrected data was merged and deduplicated:
  - `RL/compiled_corpus_v2_dev_complete_summary.csv`: 74 successful candidates.
  - `RL/compiled_corpus_v2_dev_complete_runs.csv`: 222 raw runs.
  - `RL/compiled_corpus_v2_dev_complete_failures.csv`: 8 expected development
    failures.
- The first failed retry's `NameError` rows were not merged.
- The current p95 development calibration is
  `gc_headroom_factor = 0.48789950971366136`.
- `RL/compiled_corpus_v2_dev_lobo.csv` contains development
  leave-one-benchmark-out diagnostics.
- `RL/compiled_corpus_v2_dev_phase_diagnostics.csv` contains corrected phase
  delta diagnostics from the complete merged development runs.
- `RL/compiled_corpus_v2_dev_failure_audit.csv` summarizes the eight development
  failures in a compact, parseable form.

## Parser SSA Fix (single source-order pass)

- `parse_compiler_program` previously ran binary ops first, then `NegNew` in a
  second pass. Generated Go reuses variable names SSA-style, so a destination
  later overwritten by `NegNew` retroactively corrupted earlier ops that had
  already consumed the old value (stale subtrees kept, true `-x` path orphaned,
  inputs dropped).
- Fix: combined single source-order regex with inline `NegNew` handling plus
  `resolve_operand` helper in `RL/validate_benchmark_corpus.py`.
- Regression test `test_parser_preserves_ssa_values_when_names_are_reused` in
  `tests/test_compiled_corpus_runner.py`.
- Full 93-program regen disentangle (`/tmp/disentangle.log`,
  `/tmp/negnew_scan.csv`): only **1 row** has nonzero parser effect
  (`holdout max/4/scalar`, lo +13.75 MiB, drift 0.00). The other 9 CHANGED rows
  are e-graph codegen drift (parser_effect 0.00), not the bug. Dev needs zero
  estimate changes; the frozen gc factor recomputes identically
  (0.48789951).

## Current Development Results

The corrected v2 development metrics, computed from 74 successful candidates at
`GOGC=100`, are:

- Interval coverage: 91.9% (68/74).
- Median absolute error of `lo`: 17.92 MiB.
- Median absolute percentage error of `lo`: 24.25%.
- Mean signed `lo` error: -24.38%.
- Mean within-benchmark Spearman: 0.926.
- Pairwise ranking accuracy: 92.59% (175/189).
- False accepts at 64/256/1024 MiB: 0/0/0.
- False rejects: 13/35 at 64 MiB, 3/63 at 256 MiB, 0/73 at 1024 MiB.

LOBO interval coverage ranges from 66.7% to 100% across development benchmarks.
The weakest LOBO coverage is `gy_kernel` (4/6), followed by `box_blur`,
`gx_kernel`, `lin_reg` (5/6 each), and `deep_network` (8/9). This supports a
more conservative v2 than v1 on development, but it is not a physical RSS bound.

## Code And Docs Updated

- `RL/pytrs/peak_ram.py`
  - Uses `gc_headroom_factor` rather than the obsolete high-live multiplier.
  - Current `LATTIGO_CONFIG` includes structural v2 terms and the corrected
    development factor.
- `RL/validate_benchmark_corpus.py`
  - Keeps subset split assignment anchored to the full benchmark list.
  - Records corrected phase snapshots and input plaintext fallback placement.
  - Provides p95 GC headroom and LOBO helpers.
  - Metrics helpers now accept both live numeric rows and CSV-loaded string rows.
- `tests/test_compiled_corpus_runner.py`
  - Covers split stability, LOBO exclusion, headroom floor, phase parsing, and
    CSV-loaded metrics.
- `RL/compiled_corpus_protocol.json`
  - Documents the corrected `gc_headroom_factor` and v2 `hi` formula.
- `RL/PFE_PEAK_RAM_GUIDE.md` and `RL/PEAK_RAM_ESTIMATOR_EXPLAINED.md`
  - Updated with corrected development results, LOBO summary, failures, and
    holdout limitations.

## Validation Run

The following passed after the latest changes:

```bash
conda run -n chehabEnv python -m unittest tests.test_compiled_corpus_runner tests.test_peak_ram_dfs
conda run -n chehabEnv python -m unittest discover -s tests
git diff --check
```

The full unittest run prints an expected action-masking warning and several
`cmake`/`libcurl` version warnings, but exits successfully.

## Remaining Work

1. Targeted holdout correction applied (parser fix, v2 only):
   - `RL/compiled_corpus_v2_holdout_summary_fixed.csv`: identical to the frozen
     holdout summary except the single proven row `max/4/scalar`
     (lo 42.94 -> 56.69, hi 61.23 -> 86.69, live 34.94 -> 48.69,
     inputs 2.5 -> 12.5, leaves 2 -> 10; measured med RSS 89.01 untouched).
   - `RL/compiled_corpus_v2_holdout_metrics_fixed.csv` (v2 only) and
     `RL/compiled_corpus_v2_holdout_benchmark_metrics_fixed.csv` (v2 only).
   - Original `RL/compiled_corpus_v2_holdout_summary.csv`,
     `RL/compiled_corpus_v2_holdout_metrics.csv` (with stale v1+v2 rows) and
     `RL/compiled_corpus_v2_holdout_benchmark_metrics.csv` are preserved
     untouched; stale v1 columns are reference only.
   - Corrected v2 holdout score: coverage 15/19 = 78.9% (gate >= 90%: FAIL),
     median APE 28.62% (gate <= 20%: FAIL),
     mean signed lo error -30.81% (gate <= 10% abs: FAIL),
     pairwise rank accuracy 1.0 (gate >= 0.80: PASS),
     FA@64 1 -> 0 (gate 0: PASS), FR@64 2/5 = 40% (gate <= 10%: FAIL),
     FA@256/1024 0 (PASS), FR@1024 1/19 = 5.3% (PASS).
   - No dev changes, no recalibration (dev p95 recomputes identically).
2. Decide whether the current development evidence is good enough to freeze v2.
   The main risk is high false rejection at 64 MiB and LOBO coverage as low as
   66.7% on `gy_kernel`.
3. If the model is accepted, make a scoped commit containing only RAM-task
   changes and relevant CSV/docs. Do not include unrelated generated binaries,
   `SEAL_calib/`, `RL/veclang_runner/*`, or other dirty files unless explicitly
   reviewed as part of this task.
4. Do not widen `hi` just to pass coverage; identify a structural missing term
   first. Remaining holdout misses: sobel scalar w4/w8 (GC allocation-churn
   tail, residuals 0.55/0.58 vs p95 0.49) and max/4/scalar (narrow -2.3 MiB
   after fix, plus only L=7 case in holdout).

## Safe Current Summary

V2 improves development absolute estimates and removes development false accepts
at the checked budgets, but it is still an estimate. The parser fix eliminates
the v2 holdout false accept at 64 MiB, but the corrected holdout still fails
the frozen coverage/APE/bias/false-reject gates, and `hi` must not be described
as a guaranteed RSS upper bound.
