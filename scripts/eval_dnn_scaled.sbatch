#!/bin/bash
#SBATCH -p compute
#SBATCH --mem 32GB
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 8
#SBATCH -t 06:00:00
#SBATCH -J eval-dnn-scaled
#SBATCH -o logs/output.eval_scaled.%j.txt
#SBATCH -e logs/error.eval_scaled.%j.txt

set +u
if [ -f "/share/apps/NYUAD5/miniconda/3-4.11.0/bin/activate" ]; then
    source /share/apps/NYUAD5/miniconda/3-4.11.0/bin/activate
elif [ -f "$HOME/miniconda3/bin/activate" ]; then
    source "$HOME/miniconda3/bin/activate"
fi

conda activate /scratch/${USER}/conda/envs/chehabEnv 2>/dev/null || \
conda activate /scratch/${USER}/conda/envs/chehabEnv 2>/dev/null || \
conda activate chehabEnv 2>/dev/null || \
conda activate chehab 2>/dev/null || true
set -u

set -eo pipefail
export PYTHONUNBUFFERED=1

NETID=${NETID:-$(whoami)}
PROJ_ROOT="/scratch/${NETID}/chehab-unified"
if [ ! -d "$PROJ_ROOT/RL" ]; then
    PROJ_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi

cd "$PROJ_ROOT/RL"
export PYTHONPATH="$PROJ_ROOT/RL:$PROJ_ROOT/RL/pytrs:${PYTHONPATH:-}"

mkdir -p "$PROJ_ROOT/logs"
mkdir -p "$PROJ_ROOT/RL/test_results"

TARGET_JOB="18848453"

if [ -n "${1:-}" ] && [ -f "$1" ]; then
    MODEL_PATH="$1"
else
    echo "Auto-detecting latest checkpoint for job $TARGET_JOB..."
    CKPT=$(ls -t checkpoints/model_*${TARGET_JOB}*/rl_model_*_steps.zip 2>/dev/null | head -1 || true)
    if [ -z "$CKPT" ]; then
        CKPT=$(ls -t eval/best_model_model_*${TARGET_JOB}*/best_model.zip 2>/dev/null | head -1 || true)
    fi
    if [ -z "$CKPT" ]; then
        CKPT=$(ls -t checkpoints/model_*nato_sc_film_a*/rl_model_*_steps.zip 2>/dev/null | head -1 || true)
    fi
    MODEL_PATH="$CKPT"
fi

if [ -z "$MODEL_PATH" ] || [ ! -f "$MODEL_PATH" ]; then
    echo "ERROR: No checkpoint found for job $TARGET_JOB!"
    exit 1
fi

BUDGETS="1500,2000,2600,1000000"
CKPT_NAME=$(basename "$MODEL_PATH" .zip)
CKPT_DIR=$(basename "$(dirname "$MODEL_PATH")")
DATASET="./fhe_rl/datasets/dnn_benchmarks_scaled.txt"
OUT_FILE="$PROJ_ROOT/RL/test_results/eval_dnn_scaled_${CKPT_DIR}_${CKPT_NAME}.xlsx"

echo "============================================================"
echo "  EVALUATING: DNN Benchmarks Scaled (12 expressions)"
echo "  Model:      $MODEL_PATH"
echo "  Dataset:    $DATASET"
echo "  Output:     $OUT_FILE"
echo "  Budgets:    $BUDGETS"
echo "============================================================"

stdbuf -oL -eL python -u -m fhe_rl \
    --framework unified \
    --embedder gnn \
    test \
    --model "$MODEL_PATH" \
    --dataset "$DATASET" \
    --budgets "$BUDGETS" \
    --train_budgets "$BUDGETS" \
    --method nato_sc \
    --budget_encoding film \
    --policy_variant film_a \
    --v2 \
    --output "$OUT_FILE"

echo "Evaluation completed successfully. Result saved to: $OUT_FILE"
