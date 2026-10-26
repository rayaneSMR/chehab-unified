#!/bin/bash
# Master pipeline launcher: submits Job 1 (DNN Dataset Extraction)
# and chains Job 2 (Unified Memory Calibration v4) to start automatically
# immediately after Job 1 succeeds (--dependency=afterok:<Job1_ID>).

set -eo pipefail

echo "================================================================="
echo " CHEHAB: 2-JOB CHAINED PIPELINE LAUNCHER"
echo "================================================================="

PROJ_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJ_ROOT"

# Ensure output datasets directory exists
mkdir -p "$PROJ_ROOT/RL/fhe_rl/datasets"

JOB1_SCRIPT="$PROJ_ROOT/scripts/build_dnn_dataset.sbatch"
JOB2_SCRIPT="$PROJ_ROOT/scripts/run_unified_calibration.sbatch"

if [ ! -f "$JOB1_SCRIPT" ]; then
    echo "[ERROR] Job 1 script not found: $JOB1_SCRIPT" >&2
    exit 1
fi

if [ ! -f "$JOB2_SCRIPT" ]; then
    echo "[ERROR] Job 2 script not found: $JOB2_SCRIPT" >&2
    exit 1
fi

echo "[1/2] Submitting Job 1: DNN Dataset Extraction..."
JOB1_OUTPUT=$(sbatch "$JOB1_SCRIPT")
echo "$JOB1_OUTPUT"
JOB1_ID=$(echo "$JOB1_OUTPUT" | awk '{print $NF}')

if [ -z "$JOB1_ID" ] || ! [[ "$JOB1_ID" =~ ^[0-9]+$ ]]; then
    echo "[ERROR] Failed to obtain valid Slurm Job ID for Job 1. Output was: $JOB1_OUTPUT" >&2
    exit 1
fi
echo "      -> Job 1 successfully queued with Slurm ID: $JOB1_ID"

echo ""
echo "[2/2] Submitting Job 2: Unified Calibration v4 (Chained with dependency: afterok:$JOB1_ID)..."
JOB2_OUTPUT=$(sbatch --dependency=afterok:"$JOB1_ID" "$JOB2_SCRIPT")
echo "$JOB2_OUTPUT"
JOB2_ID=$(echo "$JOB2_OUTPUT" | awk '{print $NF}')

if [ -z "$JOB2_ID" ] || ! [[ "$JOB2_ID" =~ ^[0-9]+$ ]]; then
    echo "[ERROR] Failed to obtain valid Slurm Job ID for Job 2. Output was: $JOB2_OUTPUT" >&2
    exit 1
fi
echo "      -> Job 2 successfully queued with Slurm ID: $JOB2_ID"

echo ""
echo "================================================================="
echo " PIPELINE SUBMISSION SUMMARY"
echo "================================================================="
echo " Job 1 (DNN Extraction)   : ID $JOB1_ID (runs first)"
echo " Job 2 (Unified Calib v4) : ID $JOB2_ID (starts automatically after Job 1 completes)"
echo " Dependency Condition     : afterok:$JOB1_ID"
echo ""
echo " Log Files to Monitor:"
echo "   - Job 1 Output Log : $PROJ_ROOT/build_dnn.$JOB1_ID.log"
echo "   - Job 1 Error Log  : $PROJ_ROOT/build_dnn.$JOB1_ID.err"
echo "   - Job 2 Output Log : $PROJ_ROOT/calib_v4.$JOB2_ID.log"
echo "   - Job 2 Error Log  : $PROJ_ROOT/calib_v4.$JOB2_ID.err"
echo ""
echo " Helpful Monitoring Commands:"
echo "   squeue -u \$USER"
echo "   tail -f build_dnn.$JOB1_ID.log"
echo "================================================================="
