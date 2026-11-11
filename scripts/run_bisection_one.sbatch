#!/bin/bash
# Bisection of ONE of the 9 missing benchmarks at ONE budget (same settings as step 2 of
# run_mo_bisection_46.sbatch), so the budgets / benchmarks run in parallel.
#
#   sbatch scripts/run_bisection_one.sbatch BUDGET LINE
#     BUDGET  230, 236, 369 or 9000000
#     LINE    line 1-9 of RL/benchmarks_missing9.txt (written by step 1 of job 19348949)
#
# Usually submitted by scripts/launch_bisection_missing9.sh.
# Output: RL/test_results/bisection_missing9_parts/b<BUDGET>_L<LINE>_<job>.xlsx
# Merge: python scripts/merge_bisection_parts.py (then scripts/mo_metrics_46.py)

#SBATCH --reservation=c2
#SBATCH -p compute
#SBATCH --mem 16GB
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 4
#SBATCH -t 7-00:00:00
#SBATCH -o logs/output.bisect1.%j.txt
#SBATCH -e logs/error.bisect1.%j.txt
#SBATCH -J bisect1

BUDGET="${1:?usage: sbatch run_bisection_one.sbatch BUDGET LINE}"
LINE="${2:?missing LINE (1-9)}"
set --        # otherwise conda's activate script reads the job's arguments as an environment name

module load gcc 2>/dev/null || true
set +u
if [ -f "/share/apps/NYUAD5/miniconda/3-4.11.0/bin/activate" ]; then
    source /share/apps/NYUAD5/miniconda/3-4.11.0/bin/activate
fi
CONDA_ENV="${CONDA_ENV:-$HOME/.conda/envs/fhe_rl}"
conda activate "$CONDA_ENV" || { echo "ERROR: cannot activate the conda env $CONDA_ENV"; exit 1; }
set -u
set -o pipefail
export PYTHONUNBUFFERED=1

if [ -n "${SLURM_SUBMIT_DIR:-}" ] && [ -d "${SLURM_SUBMIT_DIR}/RL" ]; then
    PROJ_ROOT="$SLURM_SUBMIT_DIR"
else
    PROJ_ROOT="/scratch/${USER}/chehab-unified"
fi
JOB="${SLURM_JOB_ID:-local}"
export PYTHONPATH="$PROJ_ROOT/RL:$PROJ_ROOT/RL/pytrs:${PYTHONPATH:-}"
export PYTHON="$(which python)"
unset CXX CC CXXFLAGS CFLAGS CPPFLAGS LDFLAGS

# Same settings and model as run_mo_bisection_46.sbatch (job 19348949)
MODEL="${MODEL:-$PROJ_ROOT/RL/fhe_rl/trained_models/unified_joint_noise_19038296_best_4.6M.zip}"
TRAIN_BUDGETS="230,236,369,9000000"
EXPR9="$PROJ_ROOT/RL/benchmarks_missing9.txt"
PARTS="$PROJ_ROOT/RL/test_results/bisection_missing9_parts"
mkdir -p "$PARTS" "$PROJ_ROOT/logs"
[ -f "$MODEL" ] || { echo "ERROR: model not found: $MODEL"; exit 1; }
[ -f "$EXPR9" ] || { echo "ERROR: $EXPR9 not found (step 1 of run_mo_bisection_46.sbatch)"; exit 1; }

# one-expression file with line LINE (non-empty lines, as load_expressions_named reads them)
ONE="$PARTS/expr_L${LINE}_${JOB}.txt"
grep -v '^[[:space:]]*$' "$EXPR9" | sed -n "${LINE}p" > "$ONE"
[ -s "$ONE" ] || { echo "ERROR: no line $LINE in $EXPR9"; exit 1; }
NAME="$(sed 's/.*://' "$ONE" | tr -d '[:space:]')"
OUT="$PARTS/b${BUDGET}_L${LINE}_${JOB}.xlsx"

echo "════════════════════════════════════════════"
echo "  BISECTION: $NAME (line $LINE) at budget $BUDGET"
echo "  Model:  $MODEL"
echo "  Output: $OUT"
echo "════════════════════════════════════════════"

cd "$PROJ_ROOT/RL"
stdbuf -oL -eL python -u -m fhe_rl \
    --framework unified \
    --embedder gnn \
    bisection \
    --model "$MODEL" \
    --benchmarks "$ONE" \
    --budgets "$BUDGET" \
    --train_budgets "$TRAIN_BUDGETS" \
    --constraint noise \
    --method nato_sc \
    --w_lo 0.1 \
    --w_hi 1.0 \
    --max_depth 3 \
    --output "$OUT"
