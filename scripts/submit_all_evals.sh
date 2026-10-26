#!/bin/bash
# Master launcher to submit all evaluations in parallel across separate compute nodes

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

echo "════════════════════════════════════════════════════════════"
echo "  SUBMITTING ALL EVALUATIONS IN PARALLEL"
echo "════════════════════════════════════════════════════════════"

echo "[1/3] Submitting DNN Benchmarks Scaled (12 exprs)..."
JOB1=$(sbatch scripts/eval_dnn_scaled.sbatch | awk '{print $4}')
echo "      -> Job ID: $JOB1"

echo "[2/3] Submitting 69 Augmented Benchmarks (69 exprs)..."
JOB2=$(sbatch scripts/eval_augmented_69.sbatch | awk '{print $4}')
echo "      -> Job ID: $JOB2"

echo "[3/3] Submitting Extracted Full DNNs (conv2d, cryptonets, full_dnn, lola)..."
JOB3=$(sbatch scripts/eval_dnn_extracted.sbatch | awk '{print $4}')
echo "      -> Job ID: $JOB3"

echo ""
echo "════════════════════════════════════════════════════════════"
echo "  All 3 jobs submitted! They will run in parallel on separate nodes."
echo "  Monitor queue with:  squeue -u \$USER"
echo "  Monitor logs with:   tail -f logs/output.eval_scaled.*.txt"
echo "                       tail -f logs/output.eval_aug69.*.txt"
echo "                       tail -f logs/output.eval_extracted.*.txt"
echo "════════════════════════════════════════════════════════════"
