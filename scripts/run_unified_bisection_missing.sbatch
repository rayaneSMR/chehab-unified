#!/bin/bash
# Bisection experiment (Algorithm 3) on the unified JOINT agent.
# For every benchmark x budget: coarse grid over w_ops in [W_LO, W_HI] -> bisection on
# key-count gaps (depth MAX_DEPTH) -> Pareto front + IC / HV / SP / EU / bisection yield.
#
# Same as run_unified_bisection.sbatch, on a given expressions file (default: the 9 benchmarks
# of the 46 end-to-end benchmarks that are not in fhe_rl/datasets/benchmarks.txt).
# Make the file first:  python scripts/dump_benchmark_expressions.py --model M.zip --output RL/benchmarks_missing9.txt
#
# Usage (use the SAME model as the 43-benchmark run, job 19038297: see the 'Model:' line of
# logs/unified_bisection_19038297.log):
#   sbatch scripts/run_unified_bisection_missing.sbatch /path/to/best_model.zip [expressions_file]

#SBATCH --reservation=c2
#SBATCH -p compute
#SBATCH --mem 32GB
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 8
#SBATCH -t 7-00:00:00

#SBATCH --mail-user=${USER}@nyu.edu
#SBATCH --mail-type=BEGIN,END,FAIL

#SBATCH -o logs/output.unified_bisection_missing.%j.txt
#SBATCH -e logs/error.unified_bisection_missing.%j.txt
#SBATCH -J unif-bisect-miss

ARGS=("$@")
set --        # otherwise conda's activate script reads the job's arguments as an environment name
set +u
if [ -f "/share/apps/NYUAD5/miniconda/3-4.11.0/bin/activate" ]; then
    source /share/apps/NYUAD5/miniconda/3-4.11.0/bin/activate
fi
CONDA_ENV="${CONDA_ENV:-$HOME/.conda/envs/fhe_rl}"   # same env as the training / eval scripts
conda activate "$CONDA_ENV" || { echo "ERROR: cannot activate the conda env $CONDA_ENV"; exit 1; }
set -u
set -- ${ARGS[@]+"${ARGS[@]}"}

export PYTHONUNBUFFERED=1

if [ -n "${SLURM_SUBMIT_DIR:-}" ] && [ -d "${SLURM_SUBMIT_DIR}/RL" ]; then
    PROJ_ROOT="$SLURM_SUBMIT_DIR"
elif [ -d "/scratch/${USER}/chehab-unified/RL" ]; then
    PROJ_ROOT="/scratch/${USER}/chehab-unified"
elif [ -d "/scratch/${NETID:-$(whoami)}/chehab-unified/RL" ]; then
    PROJ_ROOT="/scratch/${NETID:-$(whoami)}/chehab-unified"
else
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJ_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
fi

mkdir -p "$PROJ_ROOT/logs" "$PROJ_ROOT/RL/test_results"
cd "$PROJ_ROOT/RL"
export PYTHONPATH="$PROJ_ROOT/RL:$PROJ_ROOT/RL/pytrs:${PYTHONPATH:-}"

# Same setup as the joint training (train_unified_noise.sbatch)
CONSTRAINT="noise"
BUDGETS="230,236,369,9000000"
METHOD="nato_sc"
BENCHMARKS="${2:-$PROJ_ROOT/RL/benchmarks_missing9.txt}"
W_LO=0.1          # grid = the 10 training preferences w_ops = 0.1 ... 1.0
W_HI=1.0
MAX_DEPTH=3

# Joint model: required, so that the run matches the 43-benchmark run
MODEL="${1:-}"
if [ -z "$MODEL" ] || [ ! -f "$MODEL" ]; then
    echo "ERROR: joint model not found ('$MODEL')."
    echo "Usage: sbatch scripts/run_unified_bisection_missing.sbatch /path/to/best_model.zip [expressions_file]"
    exit 1
fi
if [ ! -f "$BENCHMARKS" ]; then
    echo "ERROR: expressions file not found ('$BENCHMARKS'). Run scripts/dump_benchmark_expressions.py first."
    exit 1
fi

OUT="$PROJ_ROOT/RL/test_results/bisection_unified_missing_${SLURM_JOB_ID:-local}.xlsx"

echo "════════════════════════════════════════════"
echo "  EXPERIMENT:   Bisection (Algorithm 3) - unified joint agent"
echo "  Model:        $MODEL"
echo "  Benchmarks:   $BENCHMARKS"
echo "  Constraint:   $CONSTRAINT  Budgets: $BUDGETS  Method: $METHOD"
echo "  w_ops range:  [$W_LO, $W_HI]  Max depth: $MAX_DEPTH"
echo "  Output:       $OUT"
echo "  Job ID:       ${SLURM_JOB_ID:-local}"
echo "════════════════════════════════════════════"

stdbuf -oL -eL python -u -m fhe_rl \
    --framework unified \
    --embedder gnn \
    bisection \
    --model "$MODEL" \
    --benchmarks "$BENCHMARKS" \
    --budgets "$BUDGETS" \
    --train_budgets "$BUDGETS" \
    --constraint "$CONSTRAINT" \
    --method "$METHOD" \
    --w_lo $W_LO \
    --w_hi $W_HI \
    --max_depth $MAX_DEPTH \
    --output "$OUT" \
    > "$PROJ_ROOT/logs/unified_bisection_missing_${SLURM_JOB_ID:-local}.log" 2>&1
