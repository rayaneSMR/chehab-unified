# CHEHAB — replacing the noise constraint with a peak-RAM constraint

## Implementation guide for a coding agent (and concept primer for the student)

---

## 0. Mission

In the RL-based rewriting optimizer of CHEHAB, candidates are currently rejected
or penalized when a **learned noise model** predicts the noise budget will be
exceeded. Replace that **scalar** with a **peak-RAM scalar** computed by a
**static, non-learned arithmetic model** over the candidate expression tree:

```javascript
peak_ram(E) = keys_ram(E) + inputs_ram(E) + intermediates_ram(E)
```

No dataset, no training, no runtime profiling, no scheduling search.

Deliverable: a function `estimate_peak_ram(candidate_tree, params) -> bytes`
that can be dropped into the same call sites where
`noise_estimator.estimate(...)` is used today.

---

## 1. Ground truth about the repository (from prior code inspection)

Facts below were read from the branch `merge-chehab-maroua`
(https://github.com/rayaneSMR/chehab-unified). **Re-verify each one before
relying on it — grep the file, read the function, do not assume.**

### Verified (read in full)

| File | What it contains |
| --- | --- |
| `RL/pytrs/expr.py` | Candidate expressions are **immutable trees** (`Const`/`Var`/`Op`), parsed from s-expressions. No sharing. |
| `RL/pytrs/noise_estimator.py` | `NoiseEstimator`: non-negative, no-intercept linear regression over op counts + depths. Trained on a CSV. Returns a scalar "used noise budget". |
| `RL/pytrs/cost.py` | `calculate_cost` = weighted sum (ops, rotations, tree depth, mult depth). `get_unique_rotations` counts distinct rotation offsets on the tree. |
| `RL/fhe_rl/env.py` | The estimator is consumed in `reset`, `step`, terminal penalties (`margin_barrier`, `nato_sc`, Lagrangian variants), the observation, and `get_action_mask` / `noise_masking`. Budgets `{230, 369, 9000}`. |
| `egraphs/src/cost.rs` | e-graph side: additive bottom-up `VecCostFn` per e-node. Noise hooks set to `usize::MAX` (inert). |
| `src/fheco/passes/reduce_rotation_keys.cpp` | When `#distinct rotation steps > threshold`, decomposes non-power-of-two steps into NAF sequences — trades **extra rotations** for **fewer distinct keys**. |
| `src/fheco/passes/prepare_code_gen.cpp` | Pipeline: CSE → `insert_relin` → `insert_rescale` → `reduce_rotation_keys` → `cse_commut`. |
| `src/fheco/code_gen/gen_func_lattigo.cpp` | Generated code is straight-line, in `get_top_sorted_terms` order. A `dep_count` per ciphertext frees a value after its last consumer and **reuses its object** for the result. Inputs are never freed. Constants are emitted up front. |
| `src/fheco/util/quantifier.cpp` (partial) | `rotation_keys_size = |

### Partially verified / must check

- `ir/expr.cpp` — how `get_top_sorted_terms` orders terms (tie-breaking!). The
fixed-order liveness estimate must use the **same** order, or it is not exact.
- Whether generated Lattigo code also allocates temporaries for
`RotateNew`-style ops (would add scratch not visible in the object pool).
- Whether `get_unique_rotations` counts steps before or after any reduction.
- Whether the e-graph path matters for your experiments (hooks looked inert).
- Exact field names in `pytrs` node classes (see Step 1 adapter).
- SEAL-style size formulas vs actual Lattigo serialization sizes — measure one
key and one ciphertext at the target parameter set and calibrate.

---

## 2. Concept primer (read this first — it is also the student's defense script)

### 2.1 What "peak RAM" means here

While the generated FHE program runs, RAM holds three kinds of things:

1. **Galois/rotation keys** — in CHEHAB all of them are generated **before**
evaluation and stay resident **forever**. Constant during the run.
2. **Inputs** — loaded once, never freed. Constant during the run.
3. **Intermediate ciphertexts** — born when an operation produces them, dead
after their **last** consuming operation. Their count rises and falls.

```javascript
peak RAM = keys + inputs + (maximum, over the whole run, of the number of
           simultaneously-live intermediates) x ciphertext size
```

Only term 3 varies during execution; only terms 1+3 vary between candidates.

### 2.2 Why NOT "sum everything" (the conservative trap)

The naive bound `total = (#ops) x ct_size + keys` counts every intermediate as
if it were alive at the same moment. On a small tree this overestimates the
true peak ~2–4x. Consequence: two very different candidates get almost the
same huge number, the constraint stops discriminating, and the optimizer learns
nothing. **A bound that is always huge is useless as a constraint.**
Term 3 must be a *peak live-set* quantity, not a cumulative one.

### 2.3 The liveness rule (exact, no search)

Take the expression tree and "execute" it **in the exact order the compiler
emits code** (children left-to-right). Rule: when an operation executes, its
output becomes live; a value dies when its **last** consumer executes (this is
precisely what the code generator's `dep_count` already does). The peak of the
live count is the exact peak intermediate memory **for the schedule that will
actually run**. Computing it is O(n) — it is simulation, not scheduling.
No order is chosen or optimized; the compiler's order is taken as given.

Recursive form (in "slots" = live-ciphertext count):

```javascript
slots(v) = 0                              if v is an input leaf
slots(v) = max over children c_i (in stored order):
                  slots(c_i) + (i - 1)   otherwise
```

The `+(i-1)` is the crucial part: while child `c_i` is being computed, the
outputs of children `c_1..c_{i-1}` are still sitting in RAM.

### 2.4 Exact vs upper bound vs lower bound (know which is which)

- **Exact** = provably equal to the true quantity under the stated model.
- **Upper bound** = guaranteed `>=` the true quantity. Safe for *enforcing* a
budget (if an upper bound fits, the true value fits) but may reject
feasible candidates. The *tighter* the better — a loose upper bound is
"conservative".
- **Lower bound** = guaranteed `<=` the true quantity. Can never wrongly reject;
if even the lower bound exceeds the budget, the candidate is infeasible under
**every** schedule. Useful as an infeasibility certificate.

Which of our quantities is which (under the current all-resident-keys runtime):

| Quantity | Status |
| --- | --- |
| ` | distinct steps |
| inputs term | **Exact** (inputs never freed) |
| `slots(root)` with children in compiler order | **Exact** peak for the emitted schedule |
| Sethi-Ullman number (children sorted big-first, same recurrence) | **Exact minimum over all orders for trees**; since min <= any fixed order's peak, it is a **lower bound** on the emitted schedule's peak — and a certificate of what is achievable |
| `(#ops) x ct_size` cumulative | Upper bound — **too loose, do not use** |
| uniform slot size (all ct = full size) while real levels shrink after rescale | mild **upper bound** on term 3 |

**Recommended default:** `order="fixed"` (exact for what will run) with
`keys="raw"` (upper bound on the final key set). Report the SU number
(`order="min"`) alongside as the achievable-peak certificate.

### 2.5 reduce_rotation_keys and NAF (why raw key count can overcount)

A rotation by `k` slots needs a Galois key for step `k`. Naively, an expression
using steps `{1..30}` needs 30 keys (~540 MiB at N=2^14, L=8). But rotations
**compose**: `rot(k1) then rot(k2) = rot(k1+k2)`. The non-adjacent form (NAF)
writes any `k` as a signed sum of powers of two with minimal digits, e.g.
`7 = 8 - 1`, `23 = 32 - 8 - 1`. So a rotation by any step can be emulated with
rotations by powers of two. Materializing only the building-block keys
`{1,2,4,8,16,32}` covers **all** steps 1..30 with **6 keys (~108 MiB)** — at the
price of 2–3 chained rotations instead of 1 (more runtime, more noise).

That is exactly what `reduce_rotation_keys(func, threshold)` does, and why it
only runs when the step count exceeds a threshold: for a *single* odd step
(e.g. only step 7), raw materialization (1 key) beats NAF ({1,8} = 2 keys).
**Consequence for the estimator:** counting `|raw distinct steps|` on the tree
is an upper bound on the final resident key set whenever the reduction pass
will fire; counting the NAF-union is closer to the post-pass set but can
*undercount* when the pass does not fire. The `keys="raw"|"reduced"` switch
exposes both; validate against the compiled artifact.

---

## 3. Step-by-step implementation plan

### Step 0 — verify the adapter targets (~half a day)

1. Read `RL/pytrs/expr.py`. Record the actual node classes, the field holding
the operator name, the field holding children, and how a rotation node
stores its step. Fill in this table (example answers shown):

| Adapter function | Expected source | Value found |
| --- | --- | --- |
| `is_input(node)` | class names `Const`, `Var` |  |
| `children(node)` | field e.g. `.args` / `.children` |  |
| `rotation_step(node)` | e.g. `.k`, `.step`, or trailing int arg |  |

2. `cd RL && python -c` a small script that parses one benchmark s-expression,
walks the tree with the adapter, and prints op counts — must match
`cost.py`'s counts for the same expression.
3. Read `ir/expr.cpp` `get_top_sorted_terms`: document the exact ordering rule
(DFS? BFS? tie-break by term id?). The `slots_fixed` recurrence assumes
children are evaluated in the order they appear in the tree; if the IR
order differs materially, note it as a limitation rather than silently
assuming.

### Step 1 — land `peak_ram.py` (~1 day)

Copy `peak_ram.py` (delivered with this guide) into `RL/pytrs/peak_ram.py`.
Adjust the three adapter functions to the real classes from Step 0. Keep
everything else untouched.

Properties to preserve:

- Pure function, no I/O, O(n) (`fixed`) / O(n log n) (`min`) per candidate.
- Deterministic: same tree + same params -> same bytes.
- Returns a breakdown (keys/inputs/intermediates), not just a total — the
breakdown is what makes the thesis figures interesting.

### Step 2 — unit tests (~1 day)

Hand-compute expected values for 4–5 tiny trees and assert:

| Tree | Expected slots (fixed) | Expected keys raw |
| --- | --- | --- |
| single input | 0 | 0 |
| `add(a, b)` | 0 (inputs only) | 0 |
| `mul(rot(add(a,b), 7), mul(c,d))` | 2 | 1 (step 7) |
| `add(mul(a,b), mul(c,d))` | 1 | 0 |
| left-deep chain of 5 ops | 1 | 0 |
| tree with rotations by {3, 5, 7} | (hand-sim) | 3 |

Also test: NAF correctness (`naf(7) == {0: -1, 3: 1}`), `reduced_steps({1..30})`.

### Step 3 — integrate into the RL environment (~1–2 days)

In `RL/fhe_rl/env.py`, find every call site of `noise_estimator.estimate`
(`reset`, `step`, terminal penalty functions, `get_action_mask`). Introduce a
config switch, e.g. `constraint_mode: "noise" | "memory"`, and in `memory`
mode call `estimate_peak_ram(candidate, self.fhe_params, order="fixed",
keys="raw").total_bytes` instead.

Mechanics that change:

- **Budget units**: old budgets `{230, 369, 9000}` are noise units. Memory mode
needs byte budgets tied to a machine, e.g. `{8, 16, 32} GiB`. Put them in the
config, not the code.
- **Feasibility test**: `mask = total_bytes <= budget` (same shape as today's
`noise_masking`). Optionally add the SU certificate: if the `order="min"`
estimate *also* exceeds budget, the candidate is infeasible under any
schedule — mark it hard-infeasible.
- **Observation**: if the raw noise estimate is part of the observation vector,
replace or augment with `total_bytes` (log-scale helps RL).
- **Non-monotonicity**: memory can increase after a rewrite that reduces noise
(e.g. a rewrite that removes a rotation but unbalances the tree). Expect
noisier RL dynamics; do not "fix" this by clipping, document it.
- **Fixed params**: one `FHEParams` instance for the whole run. Memory numbers
are only comparable within the same (N, L).

### Step 4 — the e-graph path (only if your experiments use it)

`egraphs/src/cost.rs`'s `VecCostFn` is additive bottom-up; peak memory is a
`max`-over-time quantity and **cannot** be expressed as a per-node additive
cost. Do not try to bend it. If needed, apply `estimate_peak_ram` as a
**post-extraction filter** on extracted candidates instead.

### Step 5 — validation against reality (~2–3 days; this is the thesis evidence)

1. Pick 5–10 benchmark programs. Compile each; record the final candidate.
2. Predict: `estimate_peak_ram(final_tree, params)` (+ inputs/keys breakdown).
3. Measure: run the generated Lattigo program under
`/usr/bin/time -v` (or Go's `runtime.ReadMemStats` injected into generated
code) and record **Maximum resident set size**.
4. Report a table predicted vs measured, plus the gap. Expected gap sources
(explain each in the write-up): Go runtime + GC headroom, key-switch
scratch temporaries, plaintext constants smaller than ciphertexts,
rescale level shrinkage (our uniform slot size is an upper bound).
5. Sensitivity: vary N and L over 2–3 parameter sets; show the estimator
tracks the measured scaling (keys grow ~quadratically in L, linearly in N).

### Step 6 — ablation for the write-up

Compare, on the same candidates:

- constraint OFF,
- noise constraint (baseline),
- memory constraint (`fixed` + raw keys),
- memory constraint (`fixed` + reduced keys).

Metrics: % feasible candidates, final program peak RSS, wall-clock, key count.
This table is the core experimental result of the PFE.

---

---

## 6. Serialized size vs real RAM (added after discussion with the supervisor/senior)

**Raised concern:** the Quantifier-style formulas (`|steps| * 2(L+1)L*N*8`) give
the *serialized* key size (storage/transmission). A key's footprint **in RAM**
is larger and set by the library's in-memory data structures — reportedly up
to ~130 MB in some measurements vs ~18 MB serialized. "We can't know the real
value until we execute." The constraint must be expressible as a real RAM
budget a user can set for their machine.

**Answer — this changes one constant, not the model:**

```javascript
RAM(E) = base + K(E) * key_ram_size + inputs * ct_ram_size + slots(E) * ct_ram_size
             \__/ fixed runtime cost      \____/ per-key RAM constant      \__ live-set peak (as before)
```

- `K(E)` (how many keys) and `slots(E)` (peak live intermediates) are still
computed statically, exactly as in Sections 2–3. The senior is right that
keys dominate and that all-resident keys make the key term constant in time.
- What replaces `2(L+1)L*N*8` is `key_ram_size`: the **in-RAM** size of one
resident key. It is a **constant of the library + parameter set**, not a
per-circuit quantity. Two non-learned ways to obtain it:

1. **Data-structure accounting (fully static):** read the library source
(Lattigo: `rlwe.GaloisKey` / `SwitchingKey`; SEAL: `KSwitchKeys`) and sum
the in-memory layout: (#polynomials) x (#limbs) x N x 8 bytes, plus known
per-object overhead. This is exact up to allocator behaviour.
2. **One-time calibration (two tiny runs — NOT a learned model):** compile
a program that materialises k1 keys and does nothing else, measure peak
RSS; repeat with k2 keys. `per_key = (RSS2-RSS1)/(k2-k1)`,
`base = RSS1 - k1*per_key`. This is measuring a constant of the system —
the same epistemic status as "an int is 4 bytes". No dataset, no training.
`RAMCalibration.from_measurements(...)` in `peak_ram.py` does the fit.

- Use `calibration=...` in `estimate_peak_ram`; until it is filled, the
estimator uses serialized sizes and **labels the key term explicitly as a
lower bound on RAM** (Section 2.4 honesty rule).

**On "global memory = peak memory":** true for the *key* component (all
resident, always). The intermediate component still has a genuine peak — but
when keys dominate, it is a second-order correction. The estimator's breakdown
(keys / inputs / intermediates) makes this visible: if intermediates are <5%
of the total on your benchmarks, say so; the ranking will then be driven
almost entirely by `K(E)`, which is the simplest possible static model and a
fine result.

**Calibration protocol (adds ~2 days, becomes a thesis experiment):**

1. Generate N trivial programs: `k` rotation steps only (k = 1, 2, 4, 8, 16),
one ciphertext input, no other ops. Measure peak RSS of each.
2. Fit `RAM = base + k * key_ram_size` (use `RAMCalibration.from_measurements`).
Report the fit quality (R^2). This settles the 18 MB vs 130 MB question
**for your actual library and parameters** — do not argue about it, measure it.
3. Generate P programs varying only the number of simultaneously-live
intermediates; fit `per_ct` similarly.
4. Then run Section 3 Step 5 validation on real benchmarks with the calibrated
model.

**Also settle:** which library the generated code actually uses — codegen is
`gen_func_lattigo.cpp` (Lattigo/CKKS) while the noise CSV was SEAL/BFV-style.
The calibration constants are library-specific; do the calibration on the
library that actually runs.

## 4. Pitfalls checklist

- [ ] Do not use cumulative `#ops x size` anywhere — it is the conservative
trap (Section 2.2).
- [ ] Do not call liveness "scheduling". No order is chosen; the compiler's
order is simulated as-is.
- [ ] Calibrate `ciphertext_size` / `galois_key_size` against the actual
backend serialization (MarshalBinary) at your parameter set; the
Quantifier formulas are SEAL-style and may drift from Lattigo.
- [ ] Rotation step `k` vs `N-k`/sign conventions: verify whether the backend
shares keys for `+k`/`-k` before trusting `reduced_steps`.
- [ ] The RL tree is pre-CSE/pre-relin; the IR later inserts relin/rescale ops
(extra intermediates). State clearly that the estimator models the
*rewritten candidate*, and validate end-to-end (Step 5) rather than
claiming bit-exactness.
- [ ] Serialized key size is a LOWER BOUND on RAM per key — never present it
as "the" RAM usage unless calibrated (Section 6).
- [ ] Calibration constants are tied to (library, version, N, L) — re-run the
two calibration programs if any of these change.
- [ ] Budgets must be bytes and machine-agnostic claims must say "relative
ranking", not "this will fit in X GB on any machine".

## 5. Definition of done

- [ ] `estimate_peak_ram` merged with adapter bound to real `pytrs` classes
- [ ] Unit tests pass (Section 3 Step 2 table)
- [ ] `env.py` runs in `constraint_mode="memory"` end-to-end on one benchmark
- [ ] Predicted-vs-measured RSS table for 5–10 programs
- [ ] Ablation table (Section 3 Step 6)
- [ ] Calibration experiment (Section 6): measured key_ram_size and base with
fit quality, on the library that actually executes
- [ ] One-page limitation statement: what is exact, what is an upper bound,
what was validated against measurements