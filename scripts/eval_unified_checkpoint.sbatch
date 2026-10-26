#!/bin/bash

#SBATCH -p compute
#SBATCH --mem 32GB
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 8
#SBATCH -t 02:00:00

# Email notifications
#SBATCH --mail-user=mo3135@nyu.edu
#SBATCH --mail-type=END,FAIL

# Standard output and error logs
#SBATCH -o logs/output.eval_unified.%j.txt
#SBATCH -e logs/error.eval_unified.%j.txt
#SBATCH -J eval-unified

set +u
# Activate cluster conda environment
if [ -f "/share/apps/NYUAD5/miniconda/3-4.11.0/bin/activate" ]; then
    source /share/apps/NYUAD5/miniconda/3-4.11.0/bin/activate
fi
conda activate /scratch/${USER}/conda/envs/chehabEnv 2>/dev/null || conda activate /scratch/mo3135/conda/envs/chehabEnv 2>/dev/null || conda activate chehabEnv 2>/dev/null || conda activate chehab 2>/dev/null || true
set -u

export PYTHONUNBUFFERED=1

# Determine project root dynamically
if [ -n "${SLURM_SUBMIT_DIR:-}" ] && [ -d "${SLURM_SUBMIT_DIR}/RL" ]; then
    PROJ_ROOT="$SLURM_SUBMIT_DIR"
elif [ -d "/scratch/${USER}/chehab-unified/RL" ]; then
    PROJ_ROOT="/scratch/${USER}/chehab-unified"
elif [ -d "/scratch/mo3135/chehab-unified/RL" ]; then
    PROJ_ROOT="/scratch/mo3135/chehab-unified"
else
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJ_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
fi

mkdir -p "$PROJ_ROOT/logs"

cd "$PROJ_ROOT/RL"
export PYTHONPATH="$PROJ_ROOT/RL:$PROJ_ROOT/RL/pytrs:${PYTHONPATH:-}"

# Check for explicit checkpoint passed as argument, else find best_model or latest checkpoint
if [ -n "${1:-}" ] && [ -f "$1" ]; then
    MODEL_PATH="$1"
else
    BEST_MODEL=$(ls -t eval/best_model_*/*.zip 2>/dev/null | head -1)
    LATEST_CKPT=$(ls -t checkpoints/model_*/*.zip 2>/dev/null | head -1)
    FINAL_MODEL=$(ls -t model_*.zip 2>/dev/null | head -1)
    MODEL_PATH="${BEST_MODEL:-${FINAL_MODEL:-$LATEST_CKPT}}"
fi

if [ -z "$MODEL_PATH" ] || [ ! -f "$MODEL_PATH" ]; then
    echo "ERROR: No checkpoint found to evaluate in $PROJ_ROOT/RL"
    exit 1
fi

BUDGETS="1500,2000,2600,1000000"
OUTPUT_FILE="$PROJ_ROOT/RL/eval_results_${SLURM_JOB_ID:-manual}.xlsx"

echo "════════════════════════════════════════════"
echo "  EVALUATING UNIFIED CHECKPOINT ON COMPUTE NODE"
echo "  Model Path:    $MODEL_PATH"
echo "  Budgets:       $BUDGETS MB"
echo "  Output Excel:  $OUTPUT_FILE"
echo "  Job ID:        ${SLURM_JOB_ID:-local}"
echo "════════════════════════════════════════════"

stdbuf -oL -eL python -u -m fhe_rl \
    --framework unified test \
    --embedder gnn \
    --model "$MODEL_PATH" \
    --dataset ./fhe_rl/datasets/benchmarks.txt \
    --budgets "$BUDGETS" \
    --method nato_sc \
    --output "$OUTPUT_FILE" \
    2>&1 | tee -a "$PROJ_ROOT/logs/eval_unified_${SLURM_JOB_ID:-manual}.log"
