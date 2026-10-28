#!/bin/bash
# Master pipeline launcher for Experiment 3 (Separated Pipeline Architecture).
# Automatically chains:
#   1. Stage 1 (Ops Training)
#   2. Dataset Pre-optimization (--dependency=afterok:JOB1_ID)
#   3. Stage 2 (Rotations Training) (--dependency=afterok:JOB2_ID)
#   4. Final Pipeline Comparison (--dependency=afterok:JOB3_ID)

set -eo pipefail

echo "================================================================="
echo " CHEHAB UNIFIED: SEPARATED PIPELINE CHAINED LAUNCHER"
echo "================================================================="

PROJ_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJ_ROOT"

JOB1_SCRIPT="$PROJ_ROOT/scripts/train_unified_separated_ops.sbatch"
JOB2_SCRIPT="$PROJ_ROOT/scripts/prepare_stage2_dataset.sbatch"
JOB3_SCRIPT="$PROJ_ROOT/scripts/train_unified_separated_rotations.sbatch"
JOB4_SCRIPT="$PROJ_ROOT/scripts/eval_pipeline_comparison.sbatch"

for f in "$JOB1_SCRIPT" "$JOB2_SCRIPT" "$JOB3_SCRIPT" "$JOB4_SCRIPT"; do
    if [ ! -f "$f" ]; then
        echo "[ERROR] Required script not found: $f" >&2
        exit 1
    fi
done

# ── 1. Submit Stage 1: Ops-only Agent Training ─────────────────────────
echo "[1/4] Submitting Stage 1: Ops Agent Training (w=[1.0, 0.0])..."
JOB1_OUTPUT=$(sbatch "$JOB1_SCRIPT")
echo "      $JOB1_OUTPUT"
JOB1_ID=$(echo "$JOB1_OUTPUT" | awk '{print $NF}')

if [ -z "$JOB1_ID" ] || ! [[ "$JOB1_ID" =~ ^[0-9]+$ ]]; then
    echo "[ERROR] Failed to obtain Slurm Job ID for Stage 1. Output: $JOB1_OUTPUT" >&2
    exit 1
fi
echo "      -> Stage 1 successfully queued with Slurm ID: $JOB1_ID"

# ── 2. Submit Stage 2 Dataset Pre-optimization ────────────────────────
echo ""
echo "[2/4] Chaining Dataset Pre-optimization (dependency: afterok:$JOB1_ID)..."
JOB2_OUTPUT=$(sbatch --dependency=afterok:"$JOB1_ID" "$JOB2_SCRIPT")
echo "      $JOB2_OUTPUT"
JOB2_ID=$(echo "$JOB2_OUTPUT" | awk '{print $NF}')

if [ -z "$JOB2_ID" ] || ! [[ "$JOB2_ID" =~ ^[0-9]+$ ]]; then
    echo "[ERROR] Failed to obtain Slurm Job ID for Dataset Prep. Output: $JOB2_OUTPUT" >&2
    exit 1
fi
echo "      -> Dataset Prep queued with Slurm ID: $JOB2_ID (held until Job $JOB1_ID succeeds)"

# ── 3. Submit Stage 2: Rotations Agent Training ───────────────────────
echo ""
echo "[3/4] Chaining Stage 2: Rotations Agent Training (dependency: afterok:$JOB2_ID)..."
JOB3_OUTPUT=$(sbatch --dependency=afterok:"$JOB2_ID" "$JOB3_SCRIPT")
echo "      $JOB3_OUTPUT"
JOB3_ID=$(echo "$JOB3_OUTPUT" | awk '{print $NF}')

if [ -z "$JOB3_ID" ] || ! [[ "$JOB3_ID" =~ ^[0-9]+$ ]]; then
    echo "[ERROR] Failed to obtain Slurm Job ID for Stage 2. Output: $JOB3_OUTPUT" >&2
    exit 1
fi
echo "      -> Stage 2 Training queued with Slurm ID: $JOB3_ID (held until Job $JOB2_ID succeeds)"

# ── 4. Submit Final Comparison Evaluation ─────────────────────────────
echo ""
echo "[4/4] Chaining Pipeline Comparison Evaluation (dependency: afterok:$JOB3_ID)..."
JOB4_OUTPUT=$(sbatch --dependency=afterok:"$JOB3_ID" "$JOB4_SCRIPT")
echo "      $JOB4_OUTPUT"
JOB4_ID=$(echo "$JOB4_OUTPUT" | awk '{print $NF}')

if [ -z "$JOB4_ID" ] || ! [[ "$JOB4_ID" =~ ^[0-9]+$ ]]; then
    echo "[ERROR] Failed to obtain Slurm Job ID for Evaluation. Output: $JOB4_OUTPUT" >&2
    exit 1
fi
echo "      -> Final Evaluation queued with Slurm ID: $JOB4_ID (held until Job $JOB3_ID succeeds)"

echo ""
echo "================================================================="
echo " SEPARATED PIPELINE SUBMISSION SUMMARY"
echo "================================================================="
echo " [Step 1] Stage 1 Ops Training       : Job ID $JOB1_ID (RUNS FIRST)"
echo " [Step 2] Dataset Pre-optimization   : Job ID $JOB2_ID (WAITS FOR $JOB1_ID)"
echo " [Step 3] Stage 2 Rotations Training : Job ID $JOB3_ID (WAITS FOR $JOB2_ID)"
echo " [Step 4] Final Evaluation           : Job ID $JOB4_ID (WAITS FOR $JOB3_ID)"
echo ""
echo " SLURM guarantees that each step runs ONLY after the previous step"
echo " completes successfully (afterok). If any step fails, subsequent"
echo " jobs will not execute."
echo ""
echo " Monitor all jobs with:"
echo "   squeue -u \$USER"
echo "================================================================="
