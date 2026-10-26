#!/bin/bash
#SBATCH -p compute
#SBATCH --mem 32GB
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 8
#SBATCH -t 03:00:00
#SBATCH -J eval-unified-latest
#SBATCH -o logs/output.eval_latest.%j.txt
#SBATCH -e logs/error.eval_latest.%j.txt

# Disable strict unbound variable checking during conda activation
set +u
if [ -f "/share/apps/NYUAD5/miniconda/3-4.11.0/bin/activate" ]; then
    source /share/apps/NYUAD5/miniconda/3-4.11.0/bin/activate
elif [ -f "$HOME/miniconda3/bin/activate" ]; then
    source "$HOME/miniconda3/bin/activate"
fi

conda activate /scratch/${USER}/conda/envs/chehabEnv 2>/dev/null || \
conda activate /scratch/mo3135/conda/envs/chehabEnv 2>/dev/null || \
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

# ═══════════════════════════════════════════════════════════════
# 1. Detect the latest checkpoint of the training job (18848453)
# ═══════════════════════════════════════════════════════════════
TARGET_JOB="18848453"

if [ -n "${1:-}" ] && [ -f "$1" ]; then
    MODEL_PATH="$1"
    echo "Using manually specified model checkpoint: $MODEL_PATH"
else
    echo "Auto-detecting latest checkpoint for training job: $TARGET_JOB..."
    # 1. Check checkpoints directory for job 18848453
    CKPT=$(ls -t checkpoints/model_*${TARGET_JOB}*/rl_model_*_steps.zip 2>/dev/null | head -1 || true)
    # 2. Check eval best_model directory for job 18848453
    if [ -z "$CKPT" ]; then
        CKPT=$(ls -t eval/best_model_model_*${TARGET_JOB}*/best_model.zip 2>/dev/null | head -1 || true)
    fi
    # 3. Fallback: newest checkpoint across any unified-ram-film job
    if [ -z "$CKPT" ]; then
        CKPT=$(ls -t checkpoints/model_*nato_sc_film_a*/rl_model_*_steps.zip 2>/dev/null | head -1 || true)
    fi
    if [ -z "$CKPT" ]; then
        CKPT=$(ls -t eval/best_model_model_*nato_sc_film_a*/best_model.zip 2>/dev/null | head -1 || true)
    fi

    MODEL_PATH="$CKPT"
fi

if [ -z "$MODEL_PATH" ] || [ ! -f "$MODEL_PATH" ]; then
    echo "ERROR: No checkpoint found for job $TARGET_JOB in $PROJ_ROOT/RL!"
    echo "Available checkpoints in checkpoints/:"
    ls -la checkpoints/ 2>/dev/null || true
    exit 1
fi

BUDGETS="1500,2000,2600,1000000"
CKPT_NAME=$(basename "$MODEL_PATH" .zip)
CKPT_DIR=$(basename "$(dirname "$MODEL_PATH")")

echo "════════════════════════════════════════════════════════════"
echo "  EVALUATING LATEST TRAINING CHECKPOINT"
echo "  Target Job:      $TARGET_JOB"
echo "  Model Path:      $MODEL_PATH"
echo "  RAM Budgets:     $BUDGETS MB"
echo "  Framework:       unified"
echo "  Method:          nato_sc"
echo "  Encoding/Policy: film / film_a"
echo "  Embedder:        gnn"
echo "  Evaluation Mode: v2 (Safety Rollback + Feasible Split)"
echo "════════════════════════════════════════════════════════════"

# ═══════════════════════════════════════════════════════════════
# 2. Evaluate on the 4 requested benchmark sets
# ═══════════════════════════════════════════════════════════════
BENCHMARKS=(
    "benchmarks.txt"
    "dnn_benchmarks.txt"
    "dnn_benchmarks_scaled.txt"
    "benchmarks_69_augmented.txt"
)

TOTAL=${#BENCHMARKS[@]}
SUCCESS_COUNT=0

for i in "${!BENCHMARKS[@]}"; do
    BENCH_NAME="${BENCHMARKS[$i]}"
    BENCH_FILE="./fhe_rl/datasets/${BENCH_NAME}"
    NUM=$((i + 1))
    TAG=$(echo "$BENCH_NAME" | sed 's/\.txt$//')
    OUT_FILE="$PROJ_ROOT/RL/test_results/eval_${TAG}_${CKPT_DIR}_${CKPT_NAME}.xlsx"

    echo ""
    echo "────────────────────────────────────────────────────────────"
    echo "  [$NUM/$TOTAL] Evaluating on: $BENCH_NAME"
    echo "  Dataset Path: $BENCH_FILE"
    echo "  Output Excel: $OUT_FILE"
    echo "────────────────────────────────────────────────────────────"

    if [ ! -f "$BENCH_FILE" ]; then
        echo "  WARNING: Dataset $BENCH_FILE not found! Skipping..."
        continue
    fi

    stdbuf -oL -eL python -u -m fhe_rl \
        --framework unified \
        --embedder gnn \
        test \
        --model "$MODEL_PATH" \
        --dataset "$BENCH_FILE" \
        --budgets "$BUDGETS" \
        --train_budgets "$BUDGETS" \
        --method nato_sc \
        --budget_encoding film \
        --policy_variant film_a \
        --v2 \
        --output "$OUT_FILE"

    if [ -f "$OUT_FILE" ]; then
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        echo "  SUCCESS: Generated $OUT_FILE ($(stat -c%s "$OUT_FILE" 2>/dev/null || echo "ok") bytes)"
    else
        echo "  FAILED: Evaluation on $BENCH_NAME did not produce output Excel."
    fi
done

echo ""
echo "════════════════════════════════════════════════════════════"
echo "  EVALUATION COMPLETE: $SUCCESS_COUNT / $TOTAL succeeded"
echo "  Results directory: $PROJ_ROOT/RL/test_results/"
echo "════════════════════════════════════════════════════════════"
ls -lh "$PROJ_ROOT/RL/test_results"/eval_*_"${CKPT_NAME}".xlsx 2>/dev/null || true
