#!/bin/bash

#SBATCH -p compute
#SBATCH --mem 32GB
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 4
#SBATCH -t 7-00:00:00

# Email notifications
#SBATCH --mail-user=${USER}@nyu.edu
#SBATCH --mail-type=BEGIN,END,FAIL

# Standard output and error logs
#SBATCH -o logs/output.eval_pipeline_comp.%j.txt
#SBATCH -e logs/error.eval_pipeline_comp.%j.txt
#SBATCH -J eval-pipe-comp

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

mkdir -p "$PROJ_ROOT/RL/test_results"

# Models can be passed as args:
#   sbatch eval_pipeline_comparison.sbatch [MODEL_JOINT] [MODEL_SEP_OPS] [MODEL_SEP_ROT]
MODEL_JOINT="${1:-}"
MODEL_SEP_OPS="${2:-}"
MODEL_SEP_ROT="${3:-}"

# Auto-detect fallback if not passed
if [ -z "$MODEL_JOINT" ]; then
    LATEST_JOINT=$(ls -td "$PROJ_ROOT/RL/eval/"*film_a_gnn 2>/dev/null | grep -v "ops" | grep -v "rot" | head -n 1)
    [ -n "$LATEST_JOINT" ] && MODEL_JOINT="$LATEST_JOINT/best_model.zip"
fi

if [ -z "$MODEL_SEP_OPS" ]; then
    LATEST_OPS=$(ls -td "$PROJ_ROOT/RL/eval/"*ops* 2>/dev/null | head -n 1)
    [ -n "$LATEST_OPS" ] && MODEL_SEP_OPS="$LATEST_OPS/best_model.zip"
fi

if [ -z "$MODEL_SEP_ROT" ]; then
    LATEST_ROT=$(ls -td "$PROJ_ROOT/RL/eval/"*rot* 2>/dev/null | head -n 1)
    [ -n "$LATEST_ROT" ] && MODEL_SEP_ROT="$LATEST_ROT/best_model.zip"
fi

BUDGETS="230,236,369,9000000"
BENCHMARK="./fhe_rl/datasets/benchmarks.txt"   # same file as the training evaluations and the bisection
METHOD="nato_sc"
CONSTRAINT="noise"

# ── BFV rollback certificate (required by `test --constraint noise`) ─────────
# Parameters of CHEHAB's generated SEAL programs (gen_func.cpp, veclang_runner.cpp):
#   N = 16384, plain modulus = PlainModulus::Batching(16384, 20) = 786433,
#   coeff modulus = CoeffModulus::BFVDefault(16384) = 48,48,48,49,49,49,49,49,49 bits
#   (initial budget 389 - 20 = 369 bits). Build the CLI once with:
#   bash scripts/build_bfv_noise_cli.sh
export FHE_BFV_NOISE_BOUND_EXECUTABLE="$PROJ_ROOT/build_bfv_noise/bfv_noise_bound_cli"
export FHE_BFV_POLY_MODULUS_DEGREE=16384
export FHE_BFV_PLAIN_MODULUS=786433
export FHE_BFV_COEFF_MODULUS_BITS=48,48,48,49,49,49,49,49,49
if [ ! -x "$FHE_BFV_NOISE_BOUND_EXECUTABLE" ]; then
    echo "ERROR: BFV noise-bound CLI not found at $FHE_BFV_NOISE_BOUND_EXECUTABLE"
    echo "Build it first: bash scripts/build_bfv_noise_cli.sh"
    exit 1
fi

echo "════════════════════════════════════════════════════════════"
echo "  EXPERIMENT 3: JOINT VS. SEPARATED PIPELINE COMPARISON"
echo "  Joint Model:          $MODEL_JOINT"
echo "  Separated Stage 1:    $MODEL_SEP_OPS"
echo "  Separated Stage 2:    $MODEL_SEP_ROT"
echo "  Benchmark:            $BENCHMARK"
echo "  Budgets:              $BUDGETS"
echo "  Constraint:           $CONSTRAINT ($METHOD)"
echo "  BFV certificate:      N=$FHE_BFV_POLY_MODULUS_DEGREE t=$FHE_BFV_PLAIN_MODULUS q_bits=$FHE_BFV_COEFF_MODULUS_BITS"
echo "════════════════════════════════════════════════════════════"

# ── 1. Evaluate Joint Pipeline ──────────────────────────────────────────
OUT_JOINT="$PROJ_ROOT/RL/test_results/eval_pipeline_joint_${SLURM_JOB_ID:-local}.xlsx"
if [ -f "$MODEL_JOINT" ]; then
    echo ""
    echo ">> Running Joint Pipeline Evaluation..."
    stdbuf -oL -eL python -u -m fhe_rl \
        --framework unified \
        --embedder gnn \
        test \
        --model "$MODEL_JOINT" \
        --pipeline joint \
        --benchmark "$BENCHMARK" \
        --budgets "$BUDGETS" \
        --train_budgets "$BUDGETS" \
        --method "$METHOD" \
        --constraint "$CONSTRAINT" \
        --v2 \
        --output "$OUT_JOINT"
else
    echo "WARNING: Joint model '$MODEL_JOINT' not found. Skipping Joint evaluation."
fi

# ── 2. Evaluate Separated Pipeline ──────────────────────────────────────
OUT_SEP="$PROJ_ROOT/RL/test_results/eval_pipeline_separated_${SLURM_JOB_ID:-local}.xlsx"
if [ -f "$MODEL_SEP_OPS" ] && [ -f "$MODEL_SEP_ROT" ]; then
    echo ""
    echo ">> Running Separated Pipeline Evaluation (Stage 1 -> Stage 2)..."
    stdbuf -oL -eL python -u -m fhe_rl \
        --framework unified \
        --embedder gnn \
        test \
        --model "$MODEL_SEP_OPS" \
        --model-stage2 "$MODEL_SEP_ROT" \
        --pipeline separated \
        --benchmark "$BENCHMARK" \
        --budgets "$BUDGETS" \
        --train_budgets "$BUDGETS" \
        --method "$METHOD" \
        --constraint "$CONSTRAINT" \
        --v2 \
        --output "$OUT_SEP"
else
    echo "WARNING: Separated models not both found (Ops: $MODEL_SEP_OPS, Rot: $MODEL_SEP_ROT). Skipping Separated evaluation."
fi

echo ""
echo "════════════════════════════════════════════════════════════"
echo "  EVALUATION COMPLETE!"
echo "  Joint Results:     $OUT_JOINT (and .csv)"
echo "  Separated Results: $OUT_SEP (and .csv)"
echo "════════════════════════════════════════════════════════════"
