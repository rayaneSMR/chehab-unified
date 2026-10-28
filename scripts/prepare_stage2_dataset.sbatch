#!/bin/bash

#SBATCH -p compute
#SBATCH --mem 32GB
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 4
#SBATCH -t 1-00:00:00

# Email notifications
#SBATCH --mail-user=${USER}@nyu.edu
#SBATCH --mail-type=BEGIN,END,FAIL

# Standard output and error logs
#SBATCH -o logs/output.prep_stage2_data.%j.txt
#SBATCH -e logs/error.prep_stage2_data.%j.txt
#SBATCH -J prep-stg2-data

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

cd "$PROJ_ROOT/RL"
export PYTHONPATH="$PROJ_ROOT/RL:$PROJ_ROOT/RL/pytrs:${PYTHONPATH:-}"

STAGE1_MODEL="${1:-}"

# Auto-detect latest trained Stage 1 ops model if not passed explicitly
if [ -z "$STAGE1_MODEL" ]; then
    LATEST_DIR=$(ls -td "$PROJ_ROOT/RL/eval/"*ops* 2>/dev/null | head -n 1)
    if [ -n "$LATEST_DIR" ] && [ -f "$LATEST_DIR/best_model.zip" ]; then
        STAGE1_MODEL="$LATEST_DIR/best_model.zip"
    fi
fi

if [ -z "$STAGE1_MODEL" ] || [ ! -f "$STAGE1_MODEL" ]; then
    echo "ERROR: Stage 1 Ops model not found at '$STAGE1_MODEL'!"
    echo "Usage: sbatch prepare_stage2_dataset.sbatch /path/to/stage1_best_model.zip"
    exit 1
fi

INPUT_DATASET="./fhe_rl/datasets/final_llm_dataset.txt"
OUTPUT_DATASET="./fhe_rl/datasets/final_llm_dataset_ops_preoptimized.txt"

echo "════════════════════════════════════════════"
echo "  PREPARING STAGE 2 ROTATIONS DATASET"
echo "  Stage 1 Model:   $STAGE1_MODEL"
echo "  Input Raw:       $INPUT_DATASET"
echo "  Output Pre-opt:  $OUTPUT_DATASET"
echo "════════════════════════════════════════════"

python -u -m fhe_rl.preoptimize_dataset \
    --input "$INPUT_DATASET" \
    --output "$OUTPUT_DATASET" \
    --model "$STAGE1_MODEL" \
    --embedder gnn \
    --budget 9000000 \
    --budget-options 230,236,369,9000000 \
    --preference 1.0,0.0 \
    --constraint noise \
    --method nato_sc

echo "Dataset preparation completed: $OUTPUT_DATASET"
