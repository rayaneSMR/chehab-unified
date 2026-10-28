#!/bin/bash
# Bisection experiment (Algorithm 3) on the unified JOINT agent.
# For every benchmark x budget: coarse grid over w_ops in [W_LO, W_HI] -> bisection on
# key-count gaps (depth MAX_DEPTH) -> Pareto front + IC / HV / SP / EU / bisection yield.
#
# Usage:
#   sbatch scripts/run_unified_bisection.sbatch                       # newest joint model in RL/eval
#   sbatch scripts/run_unified_bisection.sbatch /path/to/best_model.zip

#SBATCH -p compute
#SBATCH --mem 32GB
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 8
#SBATCH -t 7-00:00:00

#SBATCH --mail-user=${USER}@nyu.edu
#SBATCH --mail-type=BEGIN,END,FAIL

#SBATCH -o logs/output.unified_bisection.%j.txt
#SBATCH -e logs/error.unified_bisection.%j.txt
#SBATCH -J unif-bisect

set +u
if [ -f "/share/apps/NYUAD5/miniconda/3-4.11.0/bin/activate" ]; then
    source /share/apps/NYUAD5/miniconda/3-4.11.0/bin/activate
fi
conda activate /scratch/${USER}/conda/envs/chehabEnv 2>/dev/null \
    || conda activate /scratch/${NETID:-$(whoami)}/conda/envs/chehabEnv 2>/dev/null \
    || conda activate chehabEnv 2>/dev/null \
    || true
set -u

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
BENCHMARKS="./fhe_rl/datasets/benchmarks.txt"
W_LO=0.1          # grid = the 10 training preferences w_ops = 0.1 ... 1.0
W_HI=1.0
MAX_DEPTH=3

# Joint model: first argument, or the newest joint best_model in RL/eval (not ops / rot stages)
MODEL="${1:-}"
if [ -z "$MODEL" ]; then
    LATEST_JOINT=$(ls -td "$PROJ_ROOT/RL/eval/"*film_a_gnn 2>/dev/null | grep -v "ops" | grep -v "rot" | head -n 1)
    [ -n "$LATEST_JOINT" ] && MODEL="$LATEST_JOINT/best_model.zip"
fi
if [ -z "$MODEL" ] || [ ! -f "$MODEL" ]; then
    echo "ERROR: joint model not found ('$MODEL')."
    echo "Usage: sbatch scripts/run_unified_bisection.sbatch /path/to/best_model.zip"
    exit 1
fi

OUT="$PROJ_ROOT/RL/test_results/bisection_unified_${SLURM_JOB_ID:-local}.xlsx"

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
    > "$PROJ_ROOT/logs/unified_bisection_${SLURM_JOB_ID:-local}.log" 2>&1
