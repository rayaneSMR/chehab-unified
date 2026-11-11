# Threshold benchmarks at w = [0.9, 0.1]: end-to-end SEAL execution time (2026-11-11)

Circuit execution time, rotation key size and compile time of the programs of
`RL/test_results/threshold_w0.9_2026-11-08/`, measured by compiling each program with CHEHAB and
running it with SEAL. That run gives the agent-side results (noise, violations, cost reductions);
this one adds the measured times. Same dataset, agent, preference and rollback.

- **Dataset:** `RL/fhe_rl/datasets/threshold_benchmarks.txt` (lines 1-20 for B = 230, 21-40 for
  B = 236, 41-60 for B = 369), compiled by `benchmarks/threshold_expr`; the agent gets the dataset
  expression itself.
- **Agent:** `RL/fhe_rl/trained_models/unified_joint_noise_19038296_best_4.6M.zip`, method `nato_sc`,
  preference w = [0.9, 0.1].
- **cmorl/:** CMO-RL, agent runs with the test budget B, rollback at B.
- **unconstrained/:** agent runs with budget 9,000,000, rollback still at B (`AGENT_BUDGET=9000000`),
  as the unconstrained agent of `threshold_w0.9_2026-11-08`.
- **unconstrained_norollback/:** agent runs with budget 9,000,000, no rollback: the compiler gets
  the agent's final program. 5 of these programs cannot be compiled (`compile-failed`, CHEHAB:
  "backend does not support plain plain evaluation", an operation between two plaintexts in the
  agent's final program): L07, L10, L19 (B = 230) and L27, L39 (B = 236). The summary excludes
  them, so the no-rollback comparison uses 17 programs at B = 230 and 18 at B = 236 (20 at
  B = 369). The rollback runs compile an earlier checkpoint and have no failure.
- **input/:** no agent, the input program (baseline of the reductions).
- **Bound:** every compiled program must be certified by the SEAL noise bound (N = 16384,
  t = 786433, q = BFVDefault(16384)); if it is not, the input program is compiled instead.
  Corrected bound of `f4a48116`, as in `threshold_w0.9_2026-11-08`: `build_bfv_noise/bfv_noise_bound_cli`
  was rebuilt before the agent jobs below (program 1: 63 remaining bits, decryptable). A first
  run of the agent jobs used a binary built before `f4a48116`, which certified almost no program
  (the input was compiled instead); it is kept in `_old_bound/` and must not be used.
  B = 369: no program is certified, as in `threshold_w0.9_2026-11-08`, so the input is compiled.
- **Timing** (`he/main.cpp`): `circuit_execution_time` = encrypt the inputs + evaluate the circuit;
  `galois_keys_generation_time` = rotation keys; `total_execution_time` = both. 3 runs per program,
  the first is a warm-up, median of the other 2.
- **Code:** branch `threshold-e2e-exec-time` at `06181d8b` (`0f9f35ae` for
  `unconstrained_norollback/`, same code path), launched by `scripts/launch_threshold_e2e.sh` on the
  `c2` reservation, conda env `fhe_rl`.
- **Jobs:**

  | B | lines | cmorl | unconstrained | unconstrained_norollback | input |
  |---|---|---|---|---|---|
  | 230 | 1-20 | 19349049 | 19349050 | 19349051 | 19348934 |
  | 236 | 21-40 | 19349052 | 19349053 | 19349054 | 19348937 |
  | 369 | 41-60 | 19349055 | 19349056 | 19349057 | 19348941 |

  (`_old_bound/`: jobs 19348932, 19348933, 19348935, 19348936, 19348938, 19348939, 19348979-19348981.)

  Logs: `logs/output.e2e.<jobid>.txt`.

## Check against threshold_w0.9_2026-11-08

`threshold_e2e_summary.py` compares each program with the agent-only run: for both CMO-RL and
the unconstrained agent (with rollback), the agent's final program and the returned (compiled)
program have the same ops and keys for 60/60 programs. The violation rates before rollback are
identical (CMO-RL 55/55/55 %, unconstrained 70/55/65 % at B = 230/236/369), and the 20 programs
of B = 369 are not certified in either run (input compiled). The execution times of
`summary_rollback.xlsx` are therefore those of the programs of `threshold_w0.9_2026-11-08`.

## Files

- `<kind>/e2e_threshold_L<lines>[_input|_agent9000000]_b<B>_<jobid>.csv`: one row per program.

## Summary

```
# unconstrained agent with rollback at B
python scripts/threshold_e2e_summary.py RL/test_results/threshold_e2e_w0.9 --xlsx RL/test_results/threshold_e2e_w0.9/summary.xlsx
# unconstrained agent without rollback
python scripts/threshold_e2e_summary.py RL/test_results/threshold_e2e_w0.9 --unconstrained-dir unconstrained_norollback \
    --xlsx RL/test_results/threshold_e2e_w0.9/summary_norollback.xlsx
```

Reported on the programs whose input is within B: violations before and after rollback, rollback
rate, circuit and total execution time reduction w.r.t. the input program, rotation key size and
compile time.
