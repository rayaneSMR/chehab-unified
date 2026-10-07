# CHEHAB Peak-RAM Estimator: A Detailed Explanation

This document explains the estimator from the basic problem through its formulas,
measurements, tests, limitations, and current status. It is written as a learning
and presentation aid.

> **Status:** The corrected development-only Lattigo v2 calibration is
> complete for the 74 successful development candidates. The v2 holdout has
> been scored with the frozen model plus a targeted single-row parser
> correction (`max/4/scalar` only; see section 15b): v2 coverage 78.9%,
> median APE 28.62%, FA@64 0, FR@64 2/5. The frozen gates are not all met.
> Do not present v2 as a hard guarantee that a program will fit a memory
> budget.

## 1. The problem the estimator is meant to solve

CHEHAB's reinforcement-learning (RL) agent explores rewrites of a homomorphic
encryption program. A rewrite can change its operation count, rotations, keys,
and memory requirements. The estimator tries to answer:

> For this candidate expression and this encryption parameter set, approximately
> how much process memory will the generated program need?

The agent can use that estimate when deciding whether to allow a rewrite under a
memory budget. It would be too slow to compile and run every possible candidate
just to find out its memory use, so the estimator reasons from the expression
graph and encryption parameters.

The main implementation is `RL/pytrs/peak_ram.py`. Backend-specific size formulas
are in `RL/fhe_rl/memory_layout.py`. The RL environment calls the vectorized
estimator from `RL/fhe_rl/env.py`.

The current v2 work is specifically for **Lattigo's Go implementation of CKKS**.
Some graph ideas can transfer to another backend, but Lattigo-specific object
sizes, helpers, runtime behaviour, and calibration cannot simply be reused for
SEAL or a GPU library.

## 2. Terms for memory and measurements

These quantities are related but are not interchangeable:

- **RSS (Resident Set Size):** memory pages currently resident for the process.
  It includes more than ciphertext data: runtime state, stacks, code, allocator
  state, library objects, and other resident pages.
- **Peak RSS:** the maximum RSS reached during the process. The compiled-corpus
  runner records it using `/usr/bin/time`.
- **Go heap metrics:** Go's view of managed heap memory at a snapshot:
  - `HeapAlloc`: bytes allocated and not yet freed by the Go runtime at that
    instant.
  - `HeapInuse`: bytes in heap spans currently in use.
  - `HeapSys`: heap address space obtained from the operating system.
  - `TotalAlloc`: cumulative bytes allocated since process startup. It normally
    increases even if objects later become garbage.
  - `NumGC`: number of garbage collections completed.
- **Live set:** objects the estimator believes are simultaneously needed by the
  computation. This is a model, not an OS measurement.
- **Baseline:** process memory before the program-specific objects being
  studied are constructed. The v2 empty-worker baseline is measured before
  Lattigo parameters are created.
- **MiB:** mebibyte, 1,048,576 bytes (`2^20`). Some older reports label values
  “MB” loosely; the newer formulas and CSVs generally use MiB.

Go can collect an object from its managed heap without immediately returning the
corresponding physical pages to the operating system. Consequently, a lower
`HeapAlloc` does not necessarily mean RSS falls by the same amount.

## 3. Encryption parameters and the meaning of `N`, `L`, `nQ`, and `nP`

CKKS stores polynomial coefficients using an RNS (Residue Number System)
representation. Informally, coefficients are represented across several
moduli/primes. More primes and a larger polynomial mean larger ciphertexts and
keys.

- `N`: polynomial degree. The project commonly uses `N=16384`.
- `LogQ`: list of Q-prime bit sizes in generated Lattigo parameters.
- `LogP`: list of P-prime bit sizes.
- `nQ`: number of Q primes.
- `nP`: number of P primes.
- `L`: in this estimator's convention, total prime count, `nQ+nP`.

The checked-in generated Lattigo source includes `LogP: []int{45, 45}`. That
particular generated parameter set has two P primes, so `nP=2`. The corpus
parser counts the entries in `LogQ` and `LogP` to form `L`, but the current
`FHEParams` object stores only `L`; its Lattigo methods then assume `nP=2` and
calculate `nQ=L-2`.

Thus:

```text
nP = 2
nQ = L - 2
```

is a project-specific assumption based on the generated parameter sets inspected
so far. It is **not** a universal rule for CKKS or Lattigo. If CHEHAB emits a
different number of P primes, the estimator should carry the actual Q and P
counts separately rather than infer them from `L`.

For example, when `L=6`, the current convention gives `nQ=4` and `nP=2`.

### Basic size formulas

Each polynomial coefficient is modelled as an 8-byte `uint64`. A ciphertext has
two polynomials, so the model uses:

```text
ciphertext bytes = 2 × remaining_Q_primes × N × 8
```

At the top level, `remaining_Q_primes=nQ`. With `N=16384`, `nQ=4`:

```text
2 × 4 × 16384 × 8 = 1,048,576 bytes = 1 MiB
```

The Lattigo key formula in `memory_layout.py` is:

```text
one modelled Galois/relinearization key
  = ceil(nQ / nP) × 2 × (nQ+nP) × N × 8 bytes
```

For `nQ=4`, `nP=2`, `N=16384`, this is 3 MiB. Secret and public keys are
modelled separately. These formulas estimate polynomial storage; they do not
automatically include all object headers, allocator rounding, temporary buffers,
or pages retained by the process.

## 4. Expression graphs, live intermediates, and traversal order

The estimator reconstructs or receives an expression tree and treats it as a
DAG: a directed acyclic graph. A DAG can represent common work used by multiple
later operations. A shared node should not be counted as if its value were
recomputed independently for every parent.

The estimator simulates value lifetimes:

1. Count how many later nodes depend on each value (`dep_count`).
2. Visit operations in the intended compiler evaluation order: depth-first,
   left-to-right, post-order.
3. When an operation produces a ciphertext, add that intermediate to the live
   set.
4. When an input value has been consumed by its last dependent operation,
   remove it from the intermediate live set.
5. Keep the maximum number of simultaneously live intermediate ciphertexts.

The maximum count is called `slots_fixed` in the estimate. Here, “slots” means
the estimator's count of live intermediate objects; it does **not** mean CKKS
packed slots. The count is multiplied by a ciphertext size to estimate
intermediate memory.

Order matters. If a small branch is evaluated first and must stay alive while a
large branch is evaluated, the peak may differ from evaluating the large branch
first. The traversal in `peak_ram.py` is iterative to avoid Python recursion
limits on deep expressions and is intended to match CHEHAB's left-to-right
code-generation order.

### What the tests check

`tests/test_peak_ram_dfs.py` includes:

- An asymmetric tree whose left-to-right and right-to-left traversal have
  different peaks.
- Comparison against a recursive reference on 400 deterministic generated
  trees.
- A 5,000-operation chain to check that traversal avoids Python recursion
  overflow.
- A check that vector elements and lane-specific input names are retained.
- Checks for v1 and v2 formula components.

These tests provide evidence that the implementation follows its intended graph
algorithm. They do not prove that all generated-program lifetimes or library
temporaries are represented correctly.

## 5. Vectorized versus scalar programs

In packed CKKS computation, one ciphertext can contain multiple values in its
slots. A lane is a value/position inside that ciphertext, not necessarily a
separate ciphertext.

- In a **scalar/unpacked representation**, separate encrypted variables can
  correspond to separate ciphertext inputs.
- In a **packed/vectorized representation**, multiple logical values can be
  encoded into one ciphertext. Operations may also need rotations to move
  values among slots.

The AST uses a `Vec` node to group vector elements. The estimator retains every
element and its name; it does not discard later lanes. The wrapper itself is a
structural AST node, however, and is not an additional ciphertext allocated by
Lattigo. Therefore it is not charged as another ciphertext.

There are separate input-counting paths in the estimator:

- Scalar counting treats distinct encrypted variable names as ciphertext
  inputs.
- Packed-vector counting groups a `Vec` containing encrypted variables as one
  packed input ciphertext.

This is an important representation assumption. It must agree with what CHEHAB
actually emits for the candidate. Merely naming an AST node `Vec` does not prove
that the generated program stores it as one packed ciphertext. The corpus
includes scalar and vectorized forms, but vectorized corpus programs were often
produced through the e-graph path, not by the RL agent. The estimator does not
use e-graphs; they were one way of generating test programs.

The RL estimator path accepts only fully vectorized ASTs. A scalar or partially
vectorized expression returns `NotEstimable`, rather than pretending that its
packed-memory estimate is valid. The environment's action mask treats a
not-estimable candidate as available; memory is not being certified for that
candidate by this estimator.

## 6. Rotation keys and the reduction pass

A packed rotation shifts values among ciphertext slots. Lattigo needs Galois
key material for the rotation steps used by the program.

CHEHAB has a C++ pass in `src/fheco/passes/reduce_rotation_keys.cpp`. In broad
terms it:

1. Scans the program's rotation operations and counts each distinct step's
   frequency.
2. Leaves steps unchanged if the number of distinct steps is already within the
   supplied key threshold.
3. For non-power-of-two steps, computes a NAF (non-adjacent form)
   decomposition. NAF represents an integer as a signed sum of powers of two,
   often using fewer nonzero terms than ordinary binary.
4. Assigns a greedy cost based on
   `frequency × (number of NAF terms - 1)`.
5. Decomposes selected rotations into simpler rotations and returns the set of
   distinct keys that remain.

The Python estimator has a corresponding function. It scans the candidate each
time it estimates that candidate. In RL masking, estimating multiple possible
actions can therefore repeat the scan for each proposed next expression. This
is not a one-time scan at the beginning of training. CHEHAB separately runs its
C++ pass when generating code.

The estimator charges for the returned distinct Galois-key set. For Lattigo v2
it also models an automorphism index per Galois key (see Section 8).

### Threshold caveat

Thresholds must match between estimator and compiler to claim they use the same
key set:

- Python's estimator default is `keys_threshold=9999`.
- CHEHAB's Lattigo code-generation API defaults to the maximum `size_t` value,
  effectively disabling reduction for ordinary-sized key sets.
- The standalone C++ reduction function has a different default of 29.

The compiler and estimator do not automatically share one explicit threshold
through the current corpus validator. The conservative next step is to select
one intended setting, pass it explicitly to both sides, and compare the
resulting rotation sets on generated programs. Until that is done, do not state
that the estimated reduced key set is always exactly the compiled key set.
With the very large defaults, the practical behavior for normal programs is
usually simply to count distinct rotation steps without decomposing them.

Tests in `tests/test_reduce_rotations.py` cover selected expected key sets,
unchanged steps under the threshold, powers of two, and an unattainable
threshold. They are useful examples, not exhaustive equivalence testing over all
programs.

## 7. Historical v1 estimate and the origin of `1.6` and `1.1`

The legacy v1 configuration is retained to reproduce previous estimates. In
simplified notation:

```text
A = number of allocating operations × one ciphertext size
live = keys + inputs + plaintexts + peak live intermediates
extra = min(A, 1.6 × live)
lo = base + live
hi = 1.1 × (lo + extra)
```

The intent was to allow additional memory for temporary allocations and runtime
overhead. The factors `1.6` and `1.1` are hard-coded historical heuristics. The
available project evidence does not show that they came from a Lattigo
mathematical derivation, a Go guarantee, or a documented held-out calibration.
They should be described as heuristic choices, not physical constants.

This explains why ranking and absolute accuracy can disagree. If program A
really uses more memory than program B, the estimator can rank A above B while
underestimating both programs by a large amount. A useful ranking does not prove
that the estimate is safe for a hard memory budget.

For compatibility, `PeakRAMEstimate.total_bytes` aliases `estimated_bytes_lo`.
It is not the high estimate. The RL memory-budget check compares
`estimated_bytes_hi` with its budget. Neither estimate is a guaranteed RSS
bound.

## 8. Proposed structural v2 terms

V2 tries to make resident Lattigo costs more explicit:

```text
managed_live =
    parameter tables
  + helper buffers
  + rotation indexes
  + keys
  + encrypted inputs
  + plaintexts
  + live intermediate ciphertexts
  + input staging
  + postprocessing buffers
```

The terms and their current derivations are:

| Term | What it represents | Current model |
|---|---|---|
| Parameter tables | Forward and backward NTT tables for Q/P rings. | `(nQ+nP) × 2 × N × 8` bytes. |
| Helper buffers | Working memory held by evaluator, encryptor, decryptor, encoder, and basis extenders. | Sum of source-inspected polynomial and encoder buffers in `memory_layout.py`. |
| Rotation indexes | Lookup/rearrangement index data used for automorphisms in rotations. | Assumed `N` `uint64` entries per Galois key: `key count × N × 8`. |
| Keys | Secret key, public key, relinearization key when needed, Galois keys. | Analytic object sizes × inferred key counts. |
| Inputs | Encrypted inputs. | Ciphertext size × input count, or packed-vector count for the packed path. |
| Plaintexts | Encoded constants and plaintext operands counted by the AST. | Plaintext size × counted plaintexts. |
| Intermediates | Operation outputs simultaneously live at the modelled peak. | DAG live count × ciphertext size. |
| Input staging | Float64 values staged while encoding a generated input. | `(N/2) × 8` bytes. |
| Postprocessing | Decrypted plaintext and decoded output array. | `nQ × N × 8 + (N/2) × 8` bytes. |

### The automorphism index array

Lattigo's evaluator maintains automorphism indexes used to permute polynomial
coefficients for rotations. The source in the installed Lattigo version stores
indexes as `[]uint64`; the estimator assumes one `N`-element array per Galois
key:

```text
index bytes per key = N × 8
```

For `N=16384`, this is 131,072 bytes, or 0.125 MiB per key. Eight indexes would
be about 1 MiB. It is smaller than the modelled key, but can be relevant when
there are many rotations. The model counts it because it is evaluator state
separate from the key material. The empty-worker benchmark includes an
automorphism key/index, but it does not isolate the index array's memory from
all other allocations; its exact standalone contribution is therefore not
independently measured.

### Evidence for the helper-buffer model

The source-derived helper-buffer formula was checked against a microbenchmark.
At four `(N,L)` pairs the guide records modelled static helper buffers of about
6.09, 15.44, 22.69, and 61.88 MiB. Measured median `HeapInuse` changes from the
keys phase to the helpers phase were about 5.91, 15.03, 22.27, and 61.05 MiB.
This agreement supports the order of magnitude of those buffers; it does not
prove that `HeapInuse`, RSS, and the analytic sum are identical.

## 9. The empty-worker baseline and microbenchmark

The v2 baseline is not guessed from the corpus. A small Go worker,
`lattigo_backend/ram_empty_microbench.go`, is run by
`RL/measure_lattigo_empty.py`. It records phases before parameters, after
parameters, after keys, after helpers, and after one encrypted input.

It was run three times at each pair:

```text
(N,L) = (8192,5), (16384,6), (16384,8), (32768,10)
```

Two parameter pairs are outside the usual corpus parameter sets. The starting
RSS was around 7.76–7.90 MiB, and the model rounds that to 8 MiB:

```text
baseline = 8 × 1024 × 1024 bytes
```

This is a measured process/runtime baseline for that worker and environment. It
is not a universal Go constant. OS, CPU/runtime configuration, Go version,
Lattigo version, and build choices can change it; deployments on materially
different environments should remeasure it.

## 10. GC, `GOGC`, and why it does not directly give the v2 multiplier

The Go garbage collector reclaims heap objects that are no longer reachable.
`GOGC` controls the heap-growth target that triggers collection. Approximately,
ignoring other controls:

```text
heap target after a collection ≈ live heap × (1 + GOGC/100)
```

Therefore:

- `GOGC=100`: target can be roughly twice the live heap before the next
  collection.
- `GOGC=10`: smaller growth target and generally more frequent collection.
- `GOGC=off`: automatic GC disabled; allocations can accumulate and memory can
  grow substantially.

The usual Go default is `GOGC=100` unless overridden by the environment or
program. The diagnostic runner deliberately sets `GOGC` to `10`, `100`, or
`off` to examine sensitivity.

The formula describes a Go heap target, not process RSS. RSS also includes
non-heap memory, allocator and runtime behaviour, and pages not immediately
returned to the OS. Thus `GOGC=100` does **not** imply that RSS is exactly twice
the live set.

## 11. The GC headroom factor and the meaning of p95

The candidate v2 formulas are:

```text
lo = baseline + managed_live
hi = baseline + managed_live + input_plaintext_transient
     + managed_live × gc_headroom_factor
```

For each development program, one proposed ratio is:

```text
(measured median peak RSS - estimated baseline
 - managed_live - input_plaintext_transient)
------------------------------------------------
                 managed_live
```

Example:

```text
measured peak RSS = 88 MiB
estimated baseline = 8 MiB
managed_live = 50 MiB
input_plaintext_transient = 5 MiB

ratio = (88 - 8 - 50 - 5) / 50 = 0.5
```

This says that this particular measured program needed 0.5 additional
managed-live equivalents above the analytic live objects and input plaintext
transient. Both numerator and denominator are memory quantities, so the units
cancel. It does not mean every future program will have the same ratio.

The procedure takes the 95th percentile (p95) of these ratios across corrected
development programs and uses it as one shared factor. P95 was proposed as
a compromise: the median would leave roughly half the development observations
above it, while the maximum could be dominated by one unusual/noisy case. But
p95 only summarizes the sample observed. It is **not** a guarantee of 95%
coverage on new programs. Also, the protocol's desired holdout interval
coverage is 90%; p95 is not automatically justified by that acceptance target.

The corrected development data gives
`gc_headroom_factor = 0.48789950971366136` from 74 successful development
programs at `GOGC=100`. This is a development calibration rule/value, not a
physical RSS bound and not a new holdout score.

### Avoiding overfitting and checking generalization

The intention is not to fit a different model for each program. Keys, inputs,
and live intermediates are calculated analytically per candidate; at most, a
single shared environment multiplier is calibrated. Still, one shared factor
can generalize poorly if the development programs do not represent future
programs or if the model omits an operation-specific allocation.

The development check is **leave-one-benchmark-out (LOBO)**:

1. Hold out one entire development benchmark.
2. Select the multiplier using the other development benchmarks.
3. Evaluate on the omitted benchmark.
4. Repeat for each development benchmark and report each benchmark's errors.

This tests whether calibration transfers across benchmark families rather than
merely between widths of the same program. If performance varies widely by
benchmark, one global multiplier may be inadequate. The right conclusion may be
that the model is not reliable enough—not to keep widening `hi`.

“Choose/freeze the model” means settling and recording the structural terms,
measurement protocol, parameter assumptions, rotation threshold, GC policy,
and calibration rule/value. It is not only choosing one coefficient. The frozen
code should be committed before a new holdout score is calculated. Historical
v1 aggregate holdout results were already seen, which must be disclosed; no new
v2 holdout should be run until the v2 freeze.

## 12. Historical synthetic sweep and High-Churn

The **synthetic sweep** was an earlier experiment with deliberately selected
arithmetic workloads, run separately from the later CHEHAB compiled corpus. It
included additions, multiplications, dot products, and Lattigo workloads such
as Deep Polynomial, Conv2D, and High-Churn. Its values were baseline-subtracted
memory deltas. The historical sweep reported interval coverage of 15/18 for
Lattigo and 0/10 for SEAL. Those results are not absolute-RSS corpus results
and should not be mixed with them. The generator is
`RL/generate_sweep_isolated.py`.

**High-Churn** is a synthetic Lattigo workload: one ciphertext multiplication
followed by 128 additions. “Churn” means many results/temporaries are allocated
over time even though only a small number of intermediate ciphertexts may be
logically live at one time. It probes whether a live-object model misses
allocation and GC/allocator effects.

The guide records one case where the modelled peak was `lo=7.51 MiB`,
`hi=12.22 MiB`, while the measured evaluation-phase RSS grew substantially
more above baseline. A separate measurement differed, illustrating variability.
This is an unresolved limitation: the model counts logical live objects, but
does not fully predict every temporary allocation or retained RSS page.

## 13. Compiled corpus, development split, and holdout

The corpus runner is `RL/validate_benchmark_corpus.py`; candidate scope and
calibration rules are in `RL/compiled_corpus_protocol.json`.

The planned corpus has 108 candidates over 17 benchmark names:

- Regular benchmarks: scalar and vectorized forms at widths 4, 8, and 16.
- `dot_product`, `hamming_dist`, `l2_distance`: additional width 32.
- `conv2d`: compiler-native cases at supported requested widths.
- `deep_network`: Deep Poly, Deep Conv, and Deep Linear variants at configured
  depths/sizes.

Some planned candidates failed generation, parsing, or execution in the
historical run. A failed case is recorded as a failure, not silently counted as
zero memory.

The benchmark names are sorted and every fourth benchmark (1-based position)
is assigned to holdout before measurement. The holdout names are:

- `discrete_cosin_transform`
- `hamming_dist`
- `max`
- `sobel`

All other benchmark names are development. The split is by whole benchmark:
every measured width/form for `hamming_dist`, for example, remains holdout.
This avoids calibrating on width 4 of a benchmark and testing on its related
width 8 variant. Those related widths are not independent samples from a new
program family.

- **Development split:** used to diagnose errors and select/calibrate a model.
- **Holdout split:** reserved to evaluate the frozen model, without tuning it.

Historical v1 corpus: 93 successful programs total, comprising 74 development
and 19 holdout; 15 of 108 planned cases failed. The old aggregate holdout result
was seen earlier and is not a new, blind v2 score.

### Runs and phase snapshots

Each measured repetition starts a fresh operating-system process. It does not
reuse a previous process's heap. The candidate's executable is built and then
executed repeatedly; each process exits after its run.

Inside each process, instrumentation records checkpoints:

1. `baseline`: start of `main`.
2. `parameters`: after Lattigo parameters are constructed.
3. `keys`: after keys are generated.
4. `helpers`: after encoder, encryptor, decryptor, and evaluator construction.
5. `inputs`: after input preparation, just before evaluation.
6. `evaluation`: after the main computation.
7. `postprocess`: after output/decryption processing.

At snapshots, the runner records RSS/HWM and Go heap statistics. `/usr/bin/time`
separately records the whole-process peak RSS. A snapshot is only a checkpoint;
it can miss a brief peak between phases. The CSVs also record phase-to-phase
deltas. Those deltas are diagnostic, not exact object sizes, because GC can run
between snapshots.

### Fallback plaintext inputs

Some generated programs refer to an encoded plaintext input that the benchmark
execution did not supply. To let the program run, the instrumentation creates
and encodes a vector of `1.0` values if that input is missing. This is a
measurement convenience, not the benchmark's real input data.

Initially those fallback values were created **after** the `inputs` snapshot,
so the phase labelled `inputs` omitted their allocation. The corrected code
creates them before that snapshot. The corrected complete development run has
74 successful candidates and 222 raw repetitions; phase diagnostics are in
`RL/compiled_corpus_v2_dev_phase_diagnostics.csv`.

## 14. Where phase measurements and result files are recorded

The current working tree contains these files:

- `RL/compiled_corpus_v2_dev_runs.csv`: one row per candidate repetition at
  `GOGC=100`, with peak RSS and all phase metrics.
- `RL/compiled_corpus_v2_dev_summary.csv`: one row per measured candidate, with
  medians, estimates, errors, and phase summaries.
- `RL/compiled_corpus_v2_dev_metrics.csv`: aggregate development metrics.
- `RL/compiled_corpus_v2_dev_benchmark_metrics.csv`: benchmark-level error
  summaries.
- `RL/compiled_corpus_v2_dev_failures.csv`: failures for the first partial run.
- `RL/compiled_corpus_v2_dev_complete_summary.csv`: corrected merged
  development summary, 74 successful candidates.
- `RL/compiled_corpus_v2_dev_complete_runs.csv`: corrected merged raw
  repetitions, 222 rows.
- `RL/compiled_corpus_v2_dev_complete_failures.csv`: eight expected
  development failures.
- `RL/compiled_corpus_v2_dev_lobo.csv`: leave-one-benchmark-out diagnostics.
- `RL/compiled_corpus_v2_dev_phase_diagnostics.csv`: phase delta diagnostics
  from the corrected merged runs.
- `RL/compiled_corpus_v1_gc_dev_runs.csv`: separate GC-policy diagnostic raw
  runs.
- `RL/compiled_corpus_v1_gc_dev_summary.csv`: summaries for that GC diagnostic.
- `RL/compiled_corpus_v1_gc_dev_failures.csv`: its failed/timed-out candidates.
- `RL/lattigo_empty_microbench.csv`: empty-worker microbenchmark measurements.

The corrected v2 complete development summary has 74 candidates and 222 raw
repetitions (three per candidate), all `GOGC=100` and all development. The
remaining eight development candidates are recorded as failures rather than
counted as memory measurements. The separate GC diagnostic contains 72 programs
times three repeats times three GOGC settings = 648 raw runs, and 10 failed
candidates. That diagnostic's earlier phase placement means it should not be
used as a clean corrected v2 calibration.

These results complete the development-only calibration evidence. They are not
a new v2 holdout score.

## 15. Metrics and how to interpret them

For each successful corpus candidate, `Actual` is the median of repeated
whole-process peak RSS measurements.

- **Interval coverage:** fraction satisfying `lo <= Actual <= hi`. This checks
  whether the interval enclosed these measurements; it does not prove future
  coverage.
- **Median absolute error:** median `abs(lo-Actual)` in MiB.
- **Median absolute percentage error:** median
  `abs((lo-Actual)/Actual) × 100`. Smaller is better.
- **Mean signed error:** mean `(lo-Actual)/Actual × 100`. Negative means `lo`
  underestimates; positive means it overestimates.
- **Spearman rank correlation:** whether candidates ordered by estimated `lo`
  are also ordered by measured RSS within a benchmark. Near 1 means good
  ordering, not accurate memory amounts.
- **Pairwise rank accuracy:** among candidate pairs within the same benchmark,
  fraction where estimate and measured RSS agree about which is larger.
- **False accept:** estimator says a program fits a budget but measured RSS
  exceeds it. This is the dangerous error for a hard memory limit.
- **False reject:** estimator says it does not fit but measured RSS is within
  budget. This wastes capacity, but is usually less dangerous.

The historical v1 compiled-corpus results in the guide were:

| Metric | Development | Historical holdout |
|---|---:|---:|
| `[lo,hi]` coverage | 35.1% (26/74) | 31.6% (6/19) |
| Median absolute percentage error of `lo` | 54.95% | 53.60% |
| Mean signed error of `lo` | -52.85% | -55.30% |
| Mean within-benchmark Spearman | 0.944 | 0.958 |
| Pairwise ranking accuracy | 96.26% | 95.35% |

This is a clear example of strong ranking and poor absolute estimates. The
historical holdout had four false accepts at 64 MiB. These numbers belong to v1,
not to a newly evaluated v2.

The corrected v2 development results are:

| Metric | Development |
|---|---:|
| `[lo,hi]` coverage | 91.9% (68/74) |
| Median absolute percentage error of `lo` | 24.25% |
| Mean signed error of `lo` | -24.38% |
| Mean within-benchmark Spearman | 0.926 |
| Pairwise ranking accuracy | 92.59% |

At the configured budgets, v2 has zero development false accepts at 64, 256,
and 1024 MiB. Its false reject rates are 13/35 = 37.1% at 64 MiB, 3/63 = 4.8%
at 256 MiB, and 0/73 = 0% at 1024 MiB. The 64 MiB result is conservative but
costly: many actually fitting development programs would be rejected.

## 15b. Targeted parser correction and corrected v2 holdout score

`parse_compiler_program` previously ran binary ops first, then `NegNew` in a
second pass. Generated Go reuses variable names SSA-style, so an overwritten
destination retroactively corrupted earlier ops (stale subtrees, orphaned
`-x` path, dropped inputs). The fix is a single source-order pass with inline
`NegNew` plus a regression test
(`test_parser_preserves_ssa_values_when_names_are_reused`).

A full 93-program regen disentangle proves isolation: only **1 row** has a
nonzero parser effect (`holdout max/4/scalar`, lo +13.75 MiB, drift 0.00);
the other 9 changed rows are e-graph codegen drift (parser effect 0.00). Dev
needs zero changes; the frozen gc factor recomputes identically (0.48789951).

Files: `RL/compiled_corpus_v2_holdout_summary_fixed.csv` (frozen holdout plus
only the `max/4/scalar` row: lo 42.94 -> 56.69, hi 61.23 -> 86.69,
live 34.94 -> 48.69, inputs 2.5 -> 12.5, leaves 2 -> 10; measured med RSS
89.01 untouched), `RL/compiled_corpus_v2_holdout_metrics_fixed.csv` (v2 only),
`RL/compiled_corpus_v2_holdout_benchmark_metrics_fixed.csv` (v2 only).
Original holdout CSVs are preserved; their v1 columns are a frozen reference
only and v2 gates never read them.

| Metric | Corrected v2 holdout | Prefixed gate |
|---|---:|---|
| `[lo,hi]` coverage | 78.9% (15/19) | >= 90% — FAIL |
| Median absolute percentage error of `lo` | 28.62% | <= 20% — FAIL |
| Mean signed error of `lo` | -30.81% | abs <= 10% — FAIL |
| Pairwise ranking accuracy | 100% (42/42) | >= 80% — PASS |

At budgets: **0 false accepts at 64 MiB** (the fix moves `max/4/scalar` hi
61.23 -> 86.69 above budget; 1 -> 0), 0 at 256/1024 MiB; false rejects 2/5 =
40% at 64 MiB (FAIL), 0/17 at 256 MiB, 1/19 = 5.3% at 1024 MiB. Remaining
misses: sobel scalar w4/w8 (GC allocation-churn tail, residuals 0.55/0.58 vs
p95 0.49) and max/4/scalar (narrow -2.3 MiB post-fix, only L=7 holdout case).
`hi` must not be described as a guaranteed RSS bound.

## 16. The 64, 256, and 1024 MiB budgets

The default memory-budget options are defined in `RL/fhe_rl/env.py`:

```text
64 MiB, 256 MiB, 1024 MiB
```

They are configured RL/evaluation thresholds, not values derived from the
estimator or corpus. The environment can also accept custom budgets. They let
the validation report assess budget decisions at three scales. The key safety
question is whether `hi <= budget` ever says “fits” when measured peak RSS
exceeds that budget.

## 17. e-graph and RL candidate generation

The estimator itself does not invoke an e-graph, Stable-Baselines3, or code
generation. It takes an expression and calculates an estimate.

However, some vectorized corpus benchmark cases were generated using CHEHAB's
e-graph route. That makes them compiled CHEHAB programs, but not necessarily
programs visited by the RL agent. Therefore the corpus validates the estimator
on a useful set of compiler-generated programs, but does not establish
accuracy on the actual candidate distribution explored by the agent.

An additional validation would need to collect actual RL candidates, compile
and run those candidates, and compare estimated RAM with measured RSS. That is
separate from the basic estimator and corpus campaign.

## 18. Machine dependence and other backends, including GPU memory

The analytical polynomial/key formulas depend on parameters and backend
representations. The fixed process baseline and high-live behaviour also
depend on environment details such as OS, runtime, library version, allocator,
and build.

The graph-liveness algorithm can be reused conceptually for another backend.
The Lattigo-specific object terms cannot be assumed for SEAL, HEonGPU, or another
GPU library. A GPU estimator would need to account for that backend's:

- device-side ciphertext and key layouts;
- host versus device memory;
- temporary GPU workspaces and kernels;
- allocator/memory-pool behaviour;
- synchronization and lifetime rules;
- device model and runtime configuration.

This does not necessarily mean starting entirely from zero: the expression
graph and operation counting may transfer. But the physical memory model,
instrumentation, calibration, and validation would be a substantial separate
backend effort. A Lattigo RAM estimate is not a GPU RAM estimate.

## 19. Current state and what remains before a defensible v2 result

Established or implemented:

- Analytic basic ciphertext/key size formulas.
- Iterative DAG liveness traversal and regression tests.
- Rotation-key reduction logic with selected unit tests.
- Lattigo v2 source-derived parameter/helper/staging/postprocess terms.
- An empty-worker microbenchmark and its 8 MiB rounded baseline.
- A corrected phase-instrumentation order for synthesized fallback plaintexts.
- Complete corrected v2 development CSVs with three repeats per successful
  candidate.
- Development p95 `gc_headroom_factor = 0.48789950971366136`.
- Development LOBO diagnostics and per-benchmark spread.

Not yet established:

- A frozen/committed v2 model (protocol values frozen, commit pending).
- A passing v2 holdout score: corrected v2 holdout (section 15b) fails
  coverage/APE/bias/false-reject gates; FA@64 is now 0. The historical v1
  holdout was seen previously and must be disclosed.
- Accuracy on actual RL-generated candidates.
- A guarantee that `hi` bounds RSS or prevents every false accept.
- Exact agreement between Python and C++ rotation-key sets for every
  compilation path unless a common threshold is explicitly wired and compared.
- A general parameter path that preserves distinct Q/P counts when generated
  parameter sets differ from the assumed `nP=2`.
- A GPU-memory estimator.

The safest presentation is:

> “The estimator calculates program-dependent costs from encryption parameters,
> keys, and the expression graph. We added source-derived Lattigo runtime
> components and measured an empty-worker baseline. The existing v1 corpus
> showed good relative ranking but substantial absolute underestimation. The
> corrected v2 development run improves absolute estimates and avoids
> development false accepts at the checked budgets. The targeted parser
> correction removes the v2 holdout false accept at 64 MiB, but the corrected
> holdout still misses the frozen coverage/APE/bias/false-reject gates. We
> will not claim a hard memory bound.”
