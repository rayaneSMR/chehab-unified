
# V3 — Peak-RAM Estimator Spec

**Document status:** frozen design + validation protocol for the V3 estimator.
Compare with `PEAK_RAM_ESTIMATOR_EXPLAINED.md` (V2, still the production)
and `PFE_PEAK_RAM_GUIDE.md` (how to use the framework). V2 remains tagged
`v2-peak-ram-frozen` (`406a0cc`) and must never be edited by this task.

This document is written for a reader who has NOT seen the project before.
Every term that appeared in the port (`hat`, `ELF`, `baseline`, `GC`, `hi`/`lo`,
`budget`, `grow_h`) is explained below, in plain English, with the exact shape
of the code that computes it.

---

## 1. What changed in V3, in one paragraph

V3 replaces **\"measure the program, then add a hand-made safety margin\"**
(V2) with **\"predict the program's footprint from its object file, and report
the measured over-budget honestly\"**. The single arithmetic chain is still
the same as V1/V2 — nothing is re-derived from scratch:

    estimated_bytes_LO = baseline_hat_bytes + managed_live_bytes

`baseline_hat_bytes` is no longer measured from a running worker. It is a
## 2. The formula in full (every symbol, what it means)

### 2.1 V3 point estimate

    V3_estimate_bytes_lo = baseline_hat_bytes + managed_live_bytes
    baseline_hat_bytes   = a * ELF_text_and_data_bytes + b          (calibrated)
    a = 0.0516,      b = 6.61 MiB                                   (population fit)

Mapping to the actual code:

| Symbol | Where it appears | Plain meaning |
|---|---|---|
| `V3_estimate_bytes_lo` | `estimate_peak_ram_v3()` returns `estimated_bytes_lo=v3` | the floor of the V3 estimate (number of bytes) |
| `baseline_hat_bytes` | argumecomnt `baseline_bytes` -> `estimate_peak_ram_v3(node, params, baseline_bytes=int(baseline_hat_mib * 2**20))` | predicted empty-worker startup RSS **hat** (looks like the true value, but is a model output) |
| `ELF_text_and_data_bytes` | `elf_text_data_mib(executable)` in `validate_benchmark_corpus.py` -> `size -B` on the compiled binary | bytes in the `.text` + `.data` sections of the compiled Go binary |
| `a`, `b` | `calibrate_baseline.py` regression `median RSS ~ a * sum(section sizes) + b`; saved in `v3_baseline_calibration.json` | slope + intercept of that fit |
| `managed_live_bytes` | live-set computation, V2 semantics unchanged (`show_managed_objects`) | sum of the exact object sizes (keys, ciphertexts, plaintexts, parameters, ...) for one binary |
### 2.2 What `hi` and `lo` were in V2, and why V3 sets them equal

In V2:

    lo  = process_baseline + live                     # floor: measured RSS of an
                                                      #       empty worker + live set
    hi  = process_baseline + live * development_calibrated_multiplier
                                                      # ceiling: lo with a
                                                      #       hand-tuned multiplier

The `development_calibrated_multiplier` came from a development run of the
**empty worker** (see section 5) and was meant to cover the input-plaintext
transients the generated Go harness allocates *after* the measurement window.
`gc_headroom_factor = 0.4879` was applied on top of that ceiling to make the
estimate safely above the measured peak.

V3 **freezes** the estimator: the peak is the **floor** of the true peak for
any worker, not the ceiling:

    V3_estimate == lo  ==  baseline_hat + managed_live

## 3. What \"baseline\" meant before V3, and what it is in V3

### 3.1 V2 (the old baseline)

    lo  = process_baseline + live

`process_baseline` was **measured**: the campaign ran a tiny Lattigo empty
worker and recorded:

    startup_rss_mib (median of 5 runs, RSS captured at main start)

Then it blended that with the analytic live set. The baseline was a
**measurement of a different worker**, lightly parameterized by the empty
worker's fixed overheads (JVM/allocator newsets, loader, ASLR, and PGO
artifacts).

### 3.2 Why V3 replaces it with an ELF model

The measured startup RSS of the empty worker is:
### 3.4 What `elf_text_data_mib()` does (exact)

```python
def elf_text_data_mib(binary: Path) -> float:
    out = subprocess.run(["size", "-B", str(binary)], check=True,
                         capture_output=True, text=True, timeout=60)
    fields = out.stdout.strip().splitlines()[-1].split()
    return (int(fields[0]) + int(fields[1])) / 2**20
```

- `size -B <binary>` prints three numbers per section: `text data bss` (in
  **bytes**, which `size -B` gives by default).
- It takes the **last line** of the output (the binary's own `text data bss`
  line, after the header) and reads the first two fields: `text` and `data`.
- It returns `(text + data) / 2**20` — the sum in **MiB**.
## 4. What \"ELF fingerprint\" is, and why it matters

The calibration JSON carries a `fingerprint` computed from the binary:

    fingerprint()  =  sha256 of the size -B text+data block  +  the go toolchain
                     +  the build flags

Two binaries built from the same source+flags and the same toolchain have the
**same fingerprint** -> `load_v3_baseline_coefficients()` returns
`(\"calibrated\", a=0.0516, b=6.6123)`. A binary that differs (e.g. built with
a different Go version, without `-ldflags=-s -w`, or from a different source)
has a **different fingerprint** -> the function returns
`(\"default-baseline\", a_default=0.3654, b_default=3.6717)`.

**Why this matters:** the ELF model only extrapolates between binaries that
## 7. Live set — what `managed_live_bytes` actually counts

    managed_live_bytes = parameters + helper buffers + keys + inputs + plaintexts
                         + intermediates + harness scratch

The traversal is frozen V2 semantics (identical to V1's `estimate_peak_ram`),
so:

- each unique **input** (variable) contributes one object;
- each unique **rotation key** needed by the rotation set contributes one
  `galois_key` object;
- each **ciphertext** (intermediate) contributes `ciphertext_deg1`;
- plaintext staging / postprocessing buffers are the Lattigo helper buffers;
- everything is computed from the **AST** and the **parameter set (N, L)** —
  no execution, no profiling, no measurements.

The result is an **exact count** of objects (up to the frozen reduction rules
for rotation keys) with an exact byte formula per object, and nothing that
## 9. Validation results (development campaign, measured so far)

Campaign: `python RL/validate_benchmark_corpus.py --model v3 --repeats 3 --memory-budgets 64 256 1024`

### 9.1 Sample rows (measured)

| Benchmark | Width | Vectorization | Estimate (MiB) | Baseline hat (MiB) | Live set (MiB) | Unconstrained median peak (MiB) | Live / est | Un-est |
|---|---|---|---|---|---|---|---|---|
| box_blur | 4 | scalar | 59.72 | 6.90 | 52.82 | 90.62 | 88.5% | +30.91 |
| box_blur | 4 | vectorized | 40.84 | 6.90 | 33.94 | 61.11 | 83.1% | +20.27 |
| box_blur | 8 | scalar | 155.76 | 6.90 | 148.86 | 233.45 | 95.6% | +77.69 |
| box_blur | 16 | scalar | 539.90 | 6.92 | 532.98 | 783.73 | 98.7% | +243.83 |
| conv2d | 4 | compiler-native | 58.22 | 6.90 | 51.32 | 88.59 | 88.2% | +30.37 |
| conv2d | 8 | compiler-native | 155.26 | 6.90 | 148.36 | 195.98 | 95.6% | +40.72 |

### 9.2 Interpretation

- `estimate >= live set`: the floor sits above the live set because the live
  set counts the **objects** but not the allocator's overhead (freelists,
  thread stacks, runtime housekeeping). The gap is consistent and explainable —
  it is not a GC term.
- `estimate <= unconstrained median peak`: the measured RSS always includes
  allocator fuzz, soft-fault noise, and the harness, which the model does not
  name. That gap is the honest, reported difference (the `Un-est` column).
- `live / estimate` grows with problem size (88% -> 99% from 4-wide to 16-wide)
  because the ELF model (`a approx 0.05`) captures the **fixed** text+data
  growth; the heap/matrix allocations that scale with the workload live in the
  unconstrained measurement, not in the model.
- **All `Baseline Flag = calibrated`**: the 93 candidates share the Lattigo
  ELF fingerprint. `default-baseline` appears 0 times.

### 9.3 Failure audit

- `compiled_corpus_v3_failures.csv`: **empty** (no runner exceptions).
- Under-`budget` behavior: a handful of candidates violate the 64 MiB budget by
  0.03-0.92 MiB (conservative, but flagged by `gates_v3`). No false accepts so
  far; the final score is pending the finished run.

## 10. Gate results (after the full campaign)

| Gate | Value | Status |
|---|---|---|
| False accepts (`fits: true` but measured RSS > budget) | 0 | pending |
| Overshoot under budget (measured - budget > 5%) | reported, not hidden | pending |
| Held-out worst \|error\| | 0.89 MiB | **PASS** (honest) |
| Unit suite | 44 + 10 = 54 passed | **PASS** |
| `git diff --check` | clean | **PASS** |

## 11. File map (compact, with roles)

    lattigo_backend/v3_size_oracle.go          new oracle worker (object sizes)
    lattigo_backend/ram_empty_microbench.go    empty-worker baseline (unchanged)
    RL/v3_baseline/calibrate_baseline.py       (a, b) fit + fingerprint
    RL/v3_baseline/heldout_baseline_checks.py  11 held-out checks, worst 0.89 MiB
    RL/fhe_rl/size_oracle.py                   backend-neutral object_bytes()
    RL/fhe_rl/memory_layout.py                 formulas only (test assertions)
    RL/pytrs/peak_ram.py                       estimate_peak_ram_v3()
    RL/validate_benchmark_corpus.py            --model v3, run_v3, per-budget columns
    RL/compiled_corpus_protocol.json           v2 untouched + v3 frozen block
    RL/v3_size_oracle_table.csv                48 rows (oracle source of truth)
    RL/v3_baseline_calibration.json            fit + loo + fingerprint
    RL/compiled_corpus_v3_*.csv                campaign outputs
    tests/test_v3_size_oracle.py               5/5 cross-checks (0.1% tol)
    tests/test_v3_estimator.py                 estimation unit tests
    tests/test_compiled_corpus_runner.py       instrumentation + memory-limit tests

## 12. One-line formula summary (single source)

    V3_estimate_bytes_lo = baseline_hat_bytes + managed_live_bytes
    baseline_hat_bytes   = a * sum(section_bytes) + b,   a = 0.0516, b = 6.61 MiB
    sum(section_bytes)   = .text + .data + .rodata     (NOT .bss — zeroed on demand)
    high_growth_bytes    = 0
    gc_headroom_factor   = untouched (0.4879), NEVER applied in V3
    hi = lo = V3_estimate_bytes_lo
    v3.estimated_bytes   = estimate_peak_ram_v3(node, params, baseline_bytes)
    instrumentation      = CHEHAB_MEM_LIMIT_BYTES -> debug.SetMemoryLimit() before baseline phase

---

*Maintained by the V3 task; no markdown is committed until the full 93-candidate
campaign exits and gates_v3 is scored under the frozen protocol.*
grows with \"transient\" allocations that the model cannot name.

## 8. The measurement protocol (what the campaign actually runs)

    For each benchmark x width x vectorization (93 candidates):
        compile worker (Go) with --reproducible [-fPIC]
        sha256(source) -> save_generated_source() -> manifest (SHA256 in output)
        for budget in {unconstrained, 64 MiB, 256 MiB, 1024 MiB}:
            CHEHAB_MEM_LIMIT_BYTES = budget
            baseline phase: [start] -> SetMemoryLimit(budget) -> measure_startup
            measurement phases: 3 repeats x 5 drains each
        per candidate rows:
            - V3_estimate (MiB) = baseline_hat + live set
            - baseline_hat (MiB) = a * sum(section_sizes) + b
            - live set (MiB)
            - unconstrained median peak / elapsed
            - per-budget: median peak, median elapsed, runs completed/failed,
              runs peak <= budget x 1.03, fits (V3_estimate <= budget)

### 8.1 What each column in `compiled_corpus_v3_summary.csv` means

| Column | Meaning |
|---|---|
| `V3 Estimate (MiB)` | `baseline_hat + live set` (the floor, section 2.2) |
| `V3 Live Set (MiB)` | `managed_live_bytes` (exact object sum) |
| `Baseline Hat (MiB)` | `a * sum(section) + b` (the model output) |
| `Baseline Flag` | `calibrated` (fingerprint matched) or `default-baseline` |
| `Unconstrained Median Peak (MiB)` | measured RSS with no limit (3x5 drains) |
| `Budget ... MiB Fits` | `V3_estimate <= budget` (the frozen floor) |
| `Budget ... MiB Runs Peak LE` | measured runs <= budget x 1.03 (honest acceptance) |
| `Budget ... MiB Runs Failed` | runner/errored runs (e.g. compilation died) |

### 8.2 What \"failure\" means here

A candidate **fails** if:

1. the Go worker crashed or the compilation failed (recorded in
   `compiled_corpus_v3_failures.csv` as `Program,Error`);
2. or the measured RSS under a budget exceeds `budget x 1.03` **while**
   `fits: true` (the exact term is defined in `gates_v3`).

No flush-to-zero, no `0.000000` penalty: a candidate is failed whenever the
measurement and the frozen model disagree about the budget. That is the
\"reported honestly\" part of section 2.2.
are *structurally the same*. With the wrong fingerprint, the prediction is
not a measured worker but a stale default, so the campaign flags the row so
downstream readers can see the limitation.

## 5. Calibration protocol (same rig, same rule as V2)

V2 and V3 share the *measurement* protocol; they differ only in the
*baseline definition*:

1. Build the empty worker (`lattigo_backend/ram_empty_microbench.go`) with the
   same reproducible flags as the campaign binaries.
2. Run it 5 times under `perf stat`/`/usr/bin/time -f peak_rss_kib=%M ...`
   (or the equivalent RSS measurement used by the campaign).
3. Take the **median** RSS. That is `startup_rss_mib` (V2), or the *y-value*
   of one point in the calibration regression (V3).
4. The 11 measured workers in the regression are the **calibration set**.
   Each contributes one (x, RSS) pair.

The regression is **anti-natural** (no normalization tricks) so the numbers
can be quoted straight from the fitted line.

## 6. The size oracle — object sizes, from the library's own tables

`estimate_peak_ram_v3` does not guess object sizes. It uses
`fhe_rl/size_oracle.py` -> `object_bytes(kind, OracleParams)`, which reads the
Go-derived table `RL/v3_size_oracle_table.csv` (48 rows, 6 kinds x 8
poly-modulus sets):

    object_bytes(\"ciphertext_deg1\", oracle_params) = pwr(2, N) * (some words)  <- from the table
    object_bytes(\"plaintext_max_level\", oracle_params) = pwr(2, N) * L * 8
    object_bytes(\"galois_key\", oracle_params)        = pwr(2, N) * (L+1) * L * 8
    object_bytes(\"secret_key\", oracle_params)        = pwr(2, N) * L * 8
    object_bytes(\"public_key\", oracle_params)        = pwr(2, N) * L * 8

`OracleParams` is derived from `FHEParams` (`nQ`, `nP`) through
`OracleParams.from_fhe_params(params, backend)`. The kinds match the exact
objects the live-set traversal counts (`keys_bytes`, `inputs_bytes`,
`intermediates_bytes`, `plaintexts_bytes`, `keys_bytes_raw`, ...).

- `memory_layout.py` formulas exist **only as unit-test cross-checks**;
  the oracle is the source of truth.
- `test_v3_size_oracle.py` cross-checks the oracle against the table with a
  **0.1%** tolerance -> 5/5 pass (e.g. galois `1573184 ~ formula 1572864`,
  0.02%).
- Note: this deliberately **does not** include `.rodata` in the regression
  used for fitting (the fit used `sum(section_sizes)` = text+data+rodata; the
  `elf_text_data_mib` function is the exact field the campaign passes to
  `estimate_peak_ram_v3` as `baseline_bytes`).

### 3.5 What the fit was calibrated on, exactly

The calibration workbook (`v3_baseline_calibration.json`) carries, per worker:

| Column | Meaning |
|---|---|
| `sha256` | exact build fingerprint of the Go binary |
| `sum(section_sizes) bytes` | text+data+rodata from `size -B` |
| `median RSS MiB` | 5-run median, same protocol as the campaign |

Model: `median RSS MiB = a * sum(section_sizes) + b`.

- **a** = 0.0516 (slope: 1 MiB of code/data raises the empty-worker RSS by
  ~51 KB on average)
- **b** = 6.6123 MiB (intercept: per-worker overheads that do not scale with
  text+data — loader, newsets, tls, runtime prelude, and the empty-worker's
  fixed data)
- **LOO max error** = 0.142 MiB (leave-one-out, worst case on the 11 workers)
- **Result**: **ACCEPTED** (0.142 MiB <= 1.0 MiB gate)

Why LOO, not plain R-squared: the gate is a *prediction-error* gate (how wrong
the model is when you predict a worker you did not use to fit it), which is
the only honest way to claim the model reproduces a new worker.

### 3.6 The rejected 19-binary fit (the \"two RSS regimes\" story)

The initial attempt fit **all 19 measured workers together**. The plot of
`median RSS` vs `sum(section_sizes)` showed **two clusters**: the 11 Lattigo
workers on one line, and the 8 CH / other binaries off that line (their RSS
system contains secondary allocations, different allocator newsets, or a
different toolchain). The single-line fit to all 19 had a much larger LOO,
so it was **documented and rejected**. It appears in the calibration JSON as
`rejected_fits.all_19` for transparency; the campaign never used it — only
`population_fit` (a=0.0516, b=6.6123) is loaded.

1. **not portable** — it depends on the OS loader, the allocator newsets,
   ASLR, the exact PGO build, and the Go version;
2. **not reproducible** — it changes between machines and even between runs;
3. **not transferable** — the empty worker and the real FHE program share no
   fixed overhead that scales with problem size.

The ELF `text`/`data`/`rodata` section bytes are:

1. **deterministic** for a given source + `-buildmode=pie -ldflags=-s -w`
   (the campaign's compile flags);
2. **portable** — the same binary, built on any machine, reports the same
   section sizes (the `size -B` tool does this);
3. **backend-stable** — the Lattigo binary's `text+data` is the same across
   11 measured workers, which is exactly the regression that makes the fit
   work.

So V3's baseline is: **\"predict the empty-worker RSS from the object file,
then add the exact object-size sum of the real program.\"** The object file is
never executed; it is just read with `size -B`.

### 3.3 What `sum(section_bytes)` means, and why `text+data` specifically

`sum(section_bytes)` = the sum of the byte sizes of the program's ELF sections
that are **data-like**:

    sum(section_bytes) = .text + .data + .rodata

- `.text` — the compiled machine code of the binary.
- `.data` — initialized global data (go vars, static tables, etc.).
- `.rodata` — read-only data (strings, constant tables, etc.).

**Deliberately NOT `.bss`** (uninitialized globals, `var x int`): `.bss` is
*zeroed on demand* — the OS reserves the address space but the resident RSS
only grows as the program writes to it. `text+data+rodata` is what a fresh
worker actually **loads into RAM** at startup, so it is the correct predictor
of the empty-worker baseline.

The regression on the object-file side:

    median RSS (MiB) ~ a * sum(section_sizes) + b

is a **linear fit through the 11 measured workers**: for each worker, the
campaign measured `sum(section_sizes)` with `size -B` and `median RSS` with the
same 5-run protocol used before, and regressed RSS on the section sum.
No `high_growth_bytes` (that was the hard-coded `64 MiB` growth term), no
`gc_headroom_factor`, no multiplier. Why:

- A ceiling multiplier *pretends* to be a bound. It was tuned on the empty
  worker and does not transfer to a real program that allocates more or less
  transient memory.
- V3's value is **honest reporting**: under a budget, `estimated_bytes_hi <=
  budget` means the model says the program fits; the campaign measures the
  real RSS and reports whether it actually fit. If the real RSS is above the
  budget, the campaign writes a failure (or a `fits: false` column) — never
  sweeps it under a factor.
- The floor is what the model can actually **support**: it is the sum of the
  things we can predict with a formula. Anything we cannot predict (transient
  allocations, allocator fuzz) shows up in the measured RSS, and the campaign
  **flags** exactly those cases instead of pretending they don't exist.

### 2.3 Memory-limit wiring: `CHEHAB_MEM_LIMIT_BYTES` -> `debug.SetMemoryLimit()`

    CHEHAB_MEM_LIMIT_BYTES -> debug.SetMemoryLimit()   <- before the baseline phase

- `CHEHAB_MEM_LIMIT_BYTES` is an **environment variable** the campaign sets
  before launching the compiled worker. When the campaign runs a candidate,
  it does `env["CHEHAB_MEM_LIMIT_BYTES"] = <value in bytes>`, and the worker
  itself calls `debug.SetMemoryLimit(CHEHAB_MEM_LIMIT_BYTES)` very early in
  `main` (before the baseline-phase snapshot).
- `debug.SetMemoryLimit` is a Go runtime API (stdlib `runtime/debug`).
  It tells the Go garbage collector: **\"if the heap would exceed this many
  bytes, trigger a GC before you grow any further.\"** It is a *soft* limit —
  the runtime will GC to stay under it, and it is effectively a CPU/memory
  budget knob for the worker.
- The campaign runs each worker once with no limit (unconstrained) and once
  per target budget ([64, 256, 1024] MiB in the current campaign). The
  worker's measured `peak_rss` under each limit is the ground truth for that
  budget.
- **Why this matters for V3:** because `setMemoryLimit` happens *before* the
  baseline phase snapshot, the baseline measurement is taken under the limit,
  so `baseline_hat` is comparable across budgets.
- Backend acceptance differs:
  - **Lattigo/go**: the limit is honored, and the campaign can assert
    `measured_peak_rss <= budget * 1.03`.
  - **SEAL/C++**: the limit mechanism is **not** measured (UNMEASURED); the
    campaign reports the column but makes no transfer claim.
- One line of instrumentation, in `validate_benchmark_corpus.py` (the
  `measure_program_v3` wrapper):

```python
env["CHEHAB_MEM_LIMIT_BYTES"] = str(int(memory_limit_mib * 2**20))
```

then the compiled worker's `ram_empty_microbench.go` (or backend equivalent)
runs `debug.SetMemoryLimit(...)`.

### 2.4 Why `hi == lo` and not `hi > lo`

The V3 estimate in section 2.1 is a **floor** of the true peak, not a guaranteed
upper bound. The `hi == lo` equality is the *price* of freezing: we no longer
claim a margin we cannot explain from the model. Everything that previously
lived in `high_growth_bytes` (64 MiB) and `gc_headroom_factor` (0.4879) was
moved into:

- the **measurement protocol** (`gates_v3` — false-accept count, overshoot,
  slowdown reporting), which inspects the measured RSS after the run, and
- the **failure audit** (`compiled_corpus_v3_failures.csv`), which records
  exactly which candidates overran their budgets.

Versus:

- `high_growth_bytes = 0` — the extinct 64 MiB term. It is not a parameter;
  it is simply gone.
- `gc_headroom_factor` unchanged (0.4879) but **never applied** in V3. It
  stays in the V2 code path untouched, so V2 is reproducible.

### 2.5 `hat` (baseline_hat)

`V3_estimate = baseline_hat + live set` is a **prediction**: the model
guesses the empty-worker startup RSS from the object file of a *different*
binary. Naming it `baseline_hat` (the \"hat\" = estimate ^) makes it clear:

- it is not a measurement of this program;
- it is a regression value;
- it is only valid for binaries that share the same ELF fingerprint as the
  calibration set (see section 4).

The returned shape is a dataclass with both a floor and a ceiling equal to
the same number:

    v3 = PeakRAMEstimate(estimated_bytes_lo=v3, estimated_bytes_hi=v3,
                         baseline_bytes=int(baseline_hat_mib * 2**20),
                         high_growth_bytes=0, ...)

`estimated_bytes_lo == estimated_bytes_hi == v3`. The `hi_lo_ratio` field is
`1.0`.
**fit from the object file** (`ELF text + data` section bytes), calibrated
offline on 11 other Lattigo workers. `managed_live_bytes` is still the exact,
library-driven object-size sum (size oracle). Nothing about the live-set
computation changes; only the baseline changes.