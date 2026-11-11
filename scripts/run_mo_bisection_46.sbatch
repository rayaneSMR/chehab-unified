#!/bin/bash
# Multi-objective metrics + bisection ablation on the 46 end-to-end benchmarks, in one job.
#
#   1. extract the scalar expressions of the 9 benchmarks missing from fhe_rl/datasets/benchmarks.txt
#      (gy_kernel 3/4/5, roberts_cross 3/4/5, matrix_mul 5, tree 100-50 d=10, tree 100-100 d=10)
#      by compiling each C++ benchmark once          -> RL/benchmarks_missing9.txt
#   2. run the bisection (grid of 10 preferences + bisection depth 3, budgets 230/236/369/inf)
#      on these 9, as in run_unified_bisection.sbatch -> RL/test_results/bisection_unified_missing_<job>.xlsx
#   3. merge with the 43-benchmark run (job 19038297), drop the synthetic programs and compute
#      IC / HV / SP / EU (manuscript definitions, scripts/recompute_mo_metrics.py) for the grid and
#      grid + bisection fronts -> RL/test_results/mo_metrics_46_<job>.xlsx
#      + LaTeX tables RL/test_results/mo_tables_46_<job>/{mo_quality,ablation_bisection,mo_quality_full}.tex
#
# Usage:
#   sbatch scripts/run_mo_bisection_46.sbatch                 # model read from logs/unified_bisection_19038297.log
#   sbatch scripts/run_mo_bisection_46.sbatch /path/to/best_model.zip
# Uses scripts/dump_benchmark_expressions.py and scripts/mo_metrics_46.py.
# Requires the CHEHAB build (scripts/build_e2e_benchmarks.sh).

#SBATCH --reservation=c2
#SBATCH -p compute
#SBATCH --mem 32GB
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 8
#SBATCH -t 7-00:00:00

#SBATCH --mail-user=${USER}@nyu.edu
#SBATCH --mail-type=BEGIN,END,FAIL

#SBATCH -o logs/output.mo_bisection_46.%j.txt
#SBATCH -e logs/error.mo_bisection_46.%j.txt
#SBATCH -J mo-bisect-46

MODEL_ARG="${1:-}"
set --        # otherwise conda's activate script reads the job's arguments as an environment name

# Same compiler module as the build (scripts/build_e2e_benchmarks.sh): the benchmark binaries
# need its libstdc++ (GLIBCXX_3.4.26), loaded before conda as in eval_unified_e2e.sbatch
module load gcc 2>/dev/null || true

set +u
if [ -f "/share/apps/NYUAD5/miniconda/3-4.11.0/bin/activate" ]; then
    source /share/apps/NYUAD5/miniconda/3-4.11.0/bin/activate
fi
CONDA_ENV="${CONDA_ENV:-$HOME/.conda/envs/fhe_rl}"   # same env as the training / eval scripts
conda activate "$CONDA_ENV" || { echo "ERROR: cannot activate the conda env $CONDA_ENV"; exit 1; }
set -u
set -o pipefail

export PYTHONUNBUFFERED=1

if [ -n "${SLURM_SUBMIT_DIR:-}" ] && [ -d "${SLURM_SUBMIT_DIR}/RL" ]; then
    PROJ_ROOT="$SLURM_SUBMIT_DIR"
elif [ -d "/scratch/${USER}/chehab-unified/RL" ]; then
    PROJ_ROOT="/scratch/${USER}/chehab-unified"
else
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJ_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
fi
JOB="${SLURM_JOB_ID:-local}"
mkdir -p "$PROJ_ROOT/logs" "$PROJ_ROOT/RL/test_results"
export PYTHONPATH="$PROJ_ROOT/RL:$PROJ_ROOT/RL/pytrs:${PYTHONPATH:-}"
export PYTHON="$(which python)"
unset CXX CC CXXFLAGS CFLAGS CPPFLAGS LDFLAGS

# SEAL noise-bound certificate, required by the agent's rollback when the compiler calls it in
# step 1 (same parameters as eval_unified_e2e.sbatch)
export FHE_BFV_NOISE_BOUND_EXECUTABLE="${FHE_BFV_NOISE_BOUND_EXECUTABLE:-$PROJ_ROOT/build_bfv_noise/bfv_noise_bound_cli}"
export FHE_BFV_POLY_MODULUS_DEGREE=16384
export FHE_BFV_PLAIN_MODULUS=786433
export FHE_BFV_COEFF_MODULUS_BITS=48,48,48,49,49,49,49,49,49
[ -x "$FHE_BFV_NOISE_BOUND_EXECUTABLE" ] || { echo "ERROR: noise-bound certificate not found: $FHE_BFV_NOISE_BOUND_EXECUTABLE (run scripts/build_bfv_noise_cli.sh)"; exit 1; }

# Same settings as the 43-benchmark run (run_unified_bisection.sbatch)
CONSTRAINT="noise"
BUDGETS="230,236,369,9000000"
METHOD="nato_sc"
W_LO=0.1
W_HI=1.0
MAX_DEPTH=3

RUN43="$PROJ_ROOT/RL/test_results/hpc_done/bisection_unified_19038297.xlsx"
EXPR9="$PROJ_ROOT/RL/benchmarks_missing9.txt"
RUN9="$PROJ_ROOT/RL/test_results/bisection_unified_missing_${JOB}.xlsx"
OUT="$PROJ_ROOT/RL/test_results/mo_metrics_46_${JOB}.xlsx"
TABLES="$PROJ_ROOT/RL/test_results/mo_tables_46_${JOB}"

# Model: argument, else the one of the 43-benchmark run (so both runs use the same policy)
MODEL="$MODEL_ARG"
if [ -z "$MODEL" ] && [ -f "$PROJ_ROOT/logs/unified_bisection_19038297.log" ]; then
    MODEL=$(grep -m1 "Model:" "$PROJ_ROOT/logs/unified_bisection_19038297.log" | sed 's/.*Model:[[:space:]]*//')
fi
if [ -z "$MODEL" ] || [ ! -f "$MODEL" ]; then
    echo "ERROR: model not found ('$MODEL'). Give the model of job 19038297:"
    echo "  sbatch scripts/run_mo_bisection_46.sbatch /path/to/best_model.zip"
    exit 1
fi
[ -f "$RUN43" ] || { echo "ERROR: 43-benchmark run not found: $RUN43"; exit 1; }

echo "════════════════════════════════════════════"
echo "  EXPERIMENT:  MO metrics + bisection on the 46 benchmarks"
echo "  Model:       $MODEL"
echo "  Budgets:     $BUDGETS   w_ops: [$W_LO, $W_HI]   depth: $MAX_DEPTH"
echo "  43-run:      $RUN43"
echo "  Output:      $OUT"
echo "  Job ID:      $JOB"
echo "════════════════════════════════════════════"

# ── 1. expressions of the 9 missing benchmarks ───────────────────────────────
echo "[1/3] Extracting the expressions of the 9 missing benchmarks"
cd "$PROJ_ROOT"
python -u scripts/dump_benchmark_expressions.py \
    --model "$MODEL" --output "$EXPR9" --work-dir "e2e_dump_expr_${JOB}" \
    || { echo "ERROR in step 1: check the 'CHECK:' lines above"; exit 1; }
[ "$(grep -c . "$EXPR9")" -eq 9 ] || { echo "ERROR: expected 9 expressions in $EXPR9"; exit 1; }

# ── 2. bisection on the 9 ────────────────────────────────────────────────────
echo "[2/3] Bisection on the 9 benchmarks"
cd "$PROJ_ROOT/RL"
stdbuf -oL -eL python -u -m fhe_rl \
    --framework unified \
    --embedder gnn \
    bisection \
    --model "$MODEL" \
    --benchmarks "$EXPR9" \
    --budgets "$BUDGETS" \
    --train_budgets "$BUDGETS" \
    --constraint "$CONSTRAINT" \
    --method "$METHOD" \
    --w_lo $W_LO \
    --w_hi $W_HI \
    --max_depth $MAX_DEPTH \
    --output "$RUN9" \
    > "$PROJ_ROOT/logs/unified_bisection_missing_${JOB}.log" 2>&1 \
    || { echo "ERROR in step 2: see logs/unified_bisection_missing_${JOB}.log"; exit 1; }

# ── 3. metrics on the 46 ─────────────────────────────────────────────────────
echo "[3/3] Metrics on the 46 benchmarks"
cd "$PROJ_ROOT"
python -u scripts/mo_metrics_46.py --run43 "$RUN43" --run9 "$RUN9" --output "$OUT" --tables-dir "$TABLES"

echo "Done. Results: $OUT   LaTeX tables: $TABLES/"
