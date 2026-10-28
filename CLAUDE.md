# CLAUDE.md — navigation index for chehab-unified

## 1. Project overview
CHEHAB (CMake project name `FHECo`): a Fully Homomorphic Encryption compiler. Users write C++ DSL programs (`#include "fheco/fheco.hpp"`); the compiler vectorizes/optimizes them via an RL agent (Python, SB3/PyTorch) or e-graphs (Rust `egg`), then emits backend code for Lattigo v5 (Go, CKKS/BFV), SEAL, or HEonGPU (CUDA).
Entry points: `CMakeLists.txt` (builds `libfheco` + benchmarks + `RL/veclang_runner`), `benchmarks/<name>/<name>.cpp` (`main`), `python -m fhe_rl` (`RL/fhe_rl/__main__.py`), `cargo run` in `egraphs/`.

## 2. Repo map

### `src/fheco/` — C++ compiler core (library `fheco`)
- `fheco.hpp`: umbrella header that includes the whole public API.
- `dsl/compiler.{hpp,cpp}`: the central driver | `Compiler::create_func()`, `compile()`, `gen_vectorized_code()`, `call_vectorizer()`, `call_rl_vectorizer()`, `call_egraph_vectorizer()`, `gen_he_code()`, `gen_lattigo_code()`, `gen_heongpu_code()`, CSE/const-folding toggles | used by every benchmark; shells out to `python -m fhe_rl` and `cargo run` (egraphs).
- `dsl/`: DSL types and operator overloads that record ops into the IR (`ciphertext`, `plaintext`, `tensor`, `matmul`, `conv2d_optimized`, `ops_overloads`), plus `compiler_simplification.*` and `compiler_helper_functions.*`. `compiler_mine.cpp` is a legacy variant.
- `ir/` (`Func`, `Term`, `OpCode`); `trs/` (C++ TRS: `TRS`, `Rule`, `Ruleset`, the `*_ruleset.cpp` files; `reduct_order/` checks termination); `passes/` (`insert_relin`, `insert_rescale`, `reduce_rotation_keys`, `cse_commut`, `prepare_code_gen`, …).
- `ckks/` (CKKS params, scale manager, `level_dag` bootstrap placement); `param_select/` (active BFV param selector; `param_selector/` is an older copy).
- `code_gen/`: `gen_func.cpp` (SEAL C++), `gen_func_lattigo.cpp` (Go/Lattigo), `gen_func_heongpu.cpp` (CUDA); backend API strings in `constants*.hpp`.
- `util/`: `quantifier` (op/depth metrics), `expr_printer`, `draw_ir`, `eval_on_clear`.

### `benchmarks/` — DSL programs (box_blur, dot_product, conv2d, cryptonets, matrix_mul, sobel, poly_reg, dnn_tensor, gpu_benchmark, …)
- `<name>/<name>.cpp`: `main` parses `vectorize slot_count framework opt_method window quantifier cse cf backend w_ops [scheme]` (polynomials_coyote: `depth instance regime vectorize framework opt …`, w_ops is argv[12]) and calls `Compiler::gen_vectorized_code()` + codegen.
- `<name>/generate_<name>.py` (random inputs + plaintext reference → `fhe_io_example.txt`); `<name>/he/`, `heongpu/` (backend runner projects); `utils.{cpp,hpp}` (shared SEAL helpers, prints `Remaining_noise_budget`).

### `RL/fhe_rl/` — RL vectorization agent (Python package, `python -m fhe_rl`)
- `__main__.py`: CLI | `parse_arguments()`, `main()`; subcommands `train`, `test`, `run`, `interactive` (morl); `--framework constrained|morl|unified|baseline` (put before the subcommand). Train: `--constraint noise|mem`, `--budgets`, `--method`, `--algo`, `--n_cycle/--n_budget/--lambda_env/--lambda_kl`, `--n_steps`, `--rules-subset all|ops|rotations`. Test: `--pipeline joint|separated`, `--model-stage2`, `--test_mode v1|v2`. Run (unified): `--model --budget --train_budgets --method --constraint --no_rollback --info_json`.
- `config.py`: model paths, `FRAMEWORKS` registry (env/policy/wrapper/embedder per framework; constrained and unified default to the GNN embedder, morl and baseline use TRAE), enums `RLAlgorithm`, `ConstraintMethod`, `EmbeddingsModelType` | `set_framework()`, `get_env_class()`, `get_policy_class()`, `get_model_path()`.
- Gym envs (actions = pytrs rewrite rules): `env.py` (constrained `fheEnv`, cost `cost_constrained`), `env_mo.py` (`fheEnvMO`, `exec_cost_mo` + `keys_cost`, no constraint), `env_unified.py` (`fheEnvUnified`: MORL preference + noise/peak-RAM budget; `get_split_costs()` → `split_cost_mo`; reward = w·[r_exec, r_keys] + NATO-SC/Lagrangian terms; `_end_action()`).
- `policy.py` (`HierarchicalMaskablePolicy`; appends `preference_vector` to the features for unified), `policy_mo.py`, `policy_film_b.py` (FiLM-conditioned): SB3 policies.
- `train.py` (`train_agent()`, `rules_subset`, `n_steps`), `train_mo.py` (MORL only, no budgets), `test.py` (`test_agent()`, `test_agent_v2()` with safety rollback and `pipeline="separated"`), `run.py` / `run_mo.py` (single-expression inference called by the C++ compiler).
- `preoptimize_dataset.py`: runs the stage-1 (ops) agent over a dataset to build the stage-2 (rotations) training set for the separated pipeline.
- `run_unified.py`: unified-agent inference for `fhe_rl --framework unified run` | `run_agent_unified()`, `resolve_run_settings()`; locks the preference, sets the noise budget, safety rollback, writes an info JSON; settings via CLI or `CHEHAB_RL_*` env vars (model, w_ops, budget, train budgets, method, rules subset).
- `wrappers.py`, `algos/` (`lagrangian_pid.py`, `focops.py`), `callbacks.py`, `schedules.py`: constrained-RL machinery and training callbacks.
- `TRAE.py`, `TRAE_bpe.py` (transformer autoencoders), `GNNAE.py`, `gnn_embeddings.py`: expression embedders.
- `memory.py` (`peak_ram_mb()`, `MemoryEstimator`, uses `memory_calib*.json`), `packing.py` (`pack()`, `pack_expr_str()`), `seal_noise_bound.py`, `budget_percentiles.py`: cost, noise and memory models.
- `morl/`: interactive MORL driver (`morl.py`), Pareto frontier, bisection, benchmark runner.
- `baseline/`: baseline env/policy/train/run. `cv_strict.py`, `audit_pack_dataset.py`, `check_*.py`: validation utilities.
- `datasets/`: training/eval expression sets (large; don't read). `trained_models/`: checkpoints (binary).

### `RL/pytrs/` — Python term-rewriting library (pip `-e` install)
- `expr.py` (`Expr`, `Const`, `Var`, `Op`), `parser.py` (`parse_sexpr()`), `serializer.py` (`expr_to_str()`, `expr_to_tok()`), `pattern.py`, `rule_parser.py`, `rules.py` (`create_rules()`).
- `rewrite_rule.py`: `RewriteRule.apply()` plus the vectorize and rotation-vectorize variants; the core action implementation for the envs.
- `cost.py`: per-framework costs `cost_constrained()`, `exec_cost_mo()`, `keys_cost()` (= `get_unique_rotations`), `split_cost_mo()`; legacy `calculate_cost()` dispatches on `pytrs.config.framework`; helpers `get_multiplicative_depth()`, `rotations_cost()`. `noise_estimator.py` (`NoiseEstimator`, NNLS = `LinearRegression(positive=True, fit_intercept=False)`), `ckks_memory_estimator.py`, `vectorization_analyzer.py`.
- `RL/rules.txt`, `RL/rotations_rules.txt`: rule definitions.

### Other `RL/`
- `veclang_runner/` (`VeclangRunner`: compile + run an expression file on SEAL/Lattigo), `veclang_generator/` (LLM/random training expressions), `demo/` (demo scripts).
- `profile_*.py`, `test_step_parity.py`, `test_unified_ram_film.py`, `tools/`: profiling and parity checks against the frozen `.diffref/`. `PEAK_RAM_INTEGRATION_AND_BUDGET_ANALYSIS.md`: peak-RAM constraint notes.

### Other top-level code
- `egraphs/` (Rust, egg 0.9.5): `src/main.rs` CLI `<expr_file> <vector_width> <rule_family_index>`; `rules.rs` (`rules::run()`), `veclang.rs`, `cost.rs`, `extractor*.rs`.
- `ufhe/`: unified FHE C++ API (`src/ufhe/api/` interfaces; `seal_backend/` incl. `bfv_noise_estimator.*`, `heongpu_backend/`; `seal/` is vendored, don't edit).
- `lattigo_backend/` (Lattigo benchmarks, `run_instrumented.py`); `he/` (generated DNN `tensor_*_auto.go`, up to 60 MB, never read them).

### Root drivers
- `run_benchmarks.py`: sweeps benchmarks over Pareto preferences and writes CSVs of op counts, depth, times and key sizes (uses `RL/fhe_rl/pareto.py`).
- `run_morl_benchmarks.py` (SEAL; `bisect_search()`), `run_morl_lattigo_benchmarks.py`, `run_morl_heongpu_{bfv,ckks}_benchmarks.py`, `run_benchmarks_constrained.py`, `run_baseline_lattigo_benchmarks.py`: per-backend and per-framework sweeps.

### `scripts/` — HPC (Slurm) jobs and analysis
- `unified_morl_experiments.py`: redoes the MORL thesis experiments (B1, B2a-d, B4, B5, A3) for the unified agent across noise budgets | subcommands `plan`, `preflight`, `train`, `sweep`, `slurm`, `metrics`, `report`; `measure_point()` (compile + SEAL run), `bisect_targets()`, `hypervolume_2d()`, `sparsity()`, `expected_utility()`; writes `results/unified_morl/`.
- `train_unified_noise.sbatch`: base unified agent with noise budgets. Separated pipeline: `train_unified_separated_ops.sbatch` (stage 1) → `prepare_stage2_dataset.sbatch` (`preoptimize_dataset.py`) → `train_unified_separated_rotations.sbatch` (stage 2) → `eval_pipeline_comparison.sbatch` (joint vs separated).
- Other `train_*.sbatch` / `test_*.sbatch` / `eval_*.sbatch`: one per ablation variant (v2–v5, budgets, constraint methods). `launch_full_pipeline.sh`: chains dataset build, then calibration.
- Python: datasets (`build_dnn_dataset.py`, `augment_benchmarks.py`), RAM calibration (`*_calib*.py`), plots and ablations (`generate_ablation_*.py`, `plot_*.py`), `run_all_*benchmarks.py`; setup with `setup_heongpu.sh`.

### `tests/`
- `frontend_tests/test*.cpp` (DSL/IR), `backend_tests/` (`bfv_noise_estimator_smoke.cpp`), `test_calibration_pipeline.py`, `test_unified_noise_constraint.py`.

## 3. Main flows
- **Compile a benchmark:** `benchmarks/X/X.cpp main` → DSL ops (`dsl/ops_overloads`) build the `ir::Func` → `Compiler::gen_vectorized_code()` writes `../expression.txt` → `call_vectorizer()` → RL or e-graph → reads back `../vectorized_code.txt` → passes (`passes/`) → `code_gen/gen_func_lattigo.cpp` emits `generated_fhe.go`.
- **RL vectorizer call:** `Compiler::call_rl_vectorizer()` runs `python -m fhe_rl --framework F run expr.txt vect.txt [--w_ops w]` → `__main__.main()` → `config.set_framework()` → `run.py`/`run_mo.py` loads the agent from `trained_models/` → the env (`env*.py`) applies `pytrs.RewriteRule`s → writes the vectorized expression.
- **E-graph vectorizer:** `Compiler::call_egraph_vectorizer()` runs `cargo run --release --manifest-path ../../../egraphs/Cargo.toml -- expr width family` → `main.rs` → `rules::run()` + extractor → stdout appended to `vectorized_code.txt`.
- **Training:** `python -m fhe_rl --framework unified train --constraint noise …` → `train.train_agent()` → `fheEnvUnified` + `HierarchicalMaskablePolicy` + PID Lagrangian wrapper; costs from `pytrs/cost.py` (`split_cost_mo`), noise from `noise_estimator.py`, RAM from `memory.py`. Saved as `RL/model_<SLURM_JOB_ID>_<method>_<policy_variant>_<gnn|trae>[_ops|_rotations].zip`. On HPC: `scripts/train_*.sbatch`.
- **Separated pipeline (thesis B3):** train an ops agent (`--rules-subset ops`) → `preoptimize_dataset.py` → train a rotations agent (`--rules-subset rotations`) → `test --pipeline separated --model <ops.zip> --model-stage2 <rot.zip>`.
- **MORL-thesis experiments on the unified agent:** `scripts/unified_morl_experiments.py preflight → train → slurm/sweep → metrics → report` (sets the `CHEHAB_RL_*` env vars, so the C++ benchmarks call `run_unified.py`).
- **Execution / measurement:** run `go run generated_fhe.go` in the benchmark's build folder (Lattigo v5); root `run_*benchmarks.py` automates compile + run + CSV collection.

## 4. Conventions and commands
- **Build:** `cmake -S . -B build && cmake --build build` (C++17; option `-DFHECO_LOGGING=ON`). Benchmarks must be registered in the root `CMakeLists.txt` (cryptonets is commented out).
- **Env:** `conda env create -f environment.yml -n chehabEnv`, then `pip install -e RL/pytrs`. Run Python from `RL/` with `PYTHONPATH=RL:RL/pytrs`.
- **Run:** `cd build/benchmarks/dot_product && python3 generate_dot_product.py --slot_count 4 && ./dot_product 1 4 morl 1 0 1 1 1 1 0.8` (opt_method 0 = e-graph, 1 = RL; backend 0 = SEAL, 1 = Lattigo, 2 = HEonGPU), then `go mod init dot_product && go get github.com/tuneinsight/lattigo/v5/... && go run generated_fhe.go`. The README and `scripts/run.sh` omit the `framework` argument and are out of date.
- **Tests:** `tests/build_tests.sh` then `tests/run_tests.sh` (C++); `pytest tests/test_*.py`.
- **Style:** `.clang-format` (2-space indent, 120 columns, custom braces); C++ uses snake_case with namespaces `fheco::{ir,trs,passes,code_gen,util}`; Python env classes are named `fheEnv*`.
- **The compiler uses relative paths:** it reads and writes `../expression.txt`, `../vectorized_code.txt` and `../inputs.txt` relative to the benchmark build dir, so run benchmarks from `build/benchmarks/<name>/`.
- **Do not touch or read:** `build/`, `build-metrics/`, `CMakeFiles/`, `__pycache__/`, `ufhe/src/ufhe/seal/` (vendored), `RL/fhe_rl/trained_models/`, `RL/fhe_rl/datasets/`, `scripts/dataset_noise.txt`, `he/tensor_*_auto.go`, `lattigo_backend/generated_fhe`, `RL/.diffref/` (parity reference), and the result folders (`results*`, `hpc_results/`, `test_results*/`, `RL/test_results/`, `generate_statistics_graphs/`, `finish/`, `demo_outputs/`, `PPO_1/`, root CSVs).
- **Git:** working branch `unified-ram-film` tracks remote `rayane-unified` (github.com/rayaneSMR/chehab-unified); `base` = mokraneimed/CHEHAB (MORL `chehab_morl`). The Windows working copy uses CRLF endings, so compare and diff with endings normalised.
- **pytrs import history:** `pytrs/__init__.py` loads `cost`, `rules` and `parser` as top-level modules. Before commit `786da10` (2026-10-28) they read a separate copy of `config`, so `pytrs.config.framework` never reached them and the unified env had C_keys ≡ 0; the unified policy also ignored `preference_vector`. Both are fixed upstream, and the envs now call explicit per-framework cost functions. Unified checkpoints from before `786da10` are invalid (wrong reward, different feature size): retrain.
- **Known issues:** `config.py`'s default `unified_agent_model` zip is not in the repo; `*_mine.cpp`, `param_selector/`, `llm_logger_2.py`, `*.cpp.old` look legacy; `scripts/train.sbatch` and `test.sbatch` have twins with an invisible Unicode character in the name.

## 5. Maintenance rule
At the end of any session that adds, removes, renames or significantly changes files, update this index (repo map lines, flows and commands) so it stays accurate. Keep it under ~3,000 tokens.
