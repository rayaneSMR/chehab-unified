#!/bin/bash
# Real compile + SEAL execution evaluation of the unified joint agent:
# one budget x one (or more) C++ benchmark(s), at every preference.
#
#   sbatch scripts/eval_unified_e2e.sbatch BUDGET MODEL BENCHMARKS [PREFERENCES]
#     BUDGET       noise budget in bits (230, 236, 369 or 9000000)
#     MODEL        trained joint model .zip (absolute path)
#     BENCHMARKS   comma-separated, e.g. dot_product or box_blur,gx_kernel (or "all")
#     PREFERENCES  optional "w_ops,w_keys;..." (default: the 10 training preferences)
#
# Usually submitted by scripts/launch_unified_e2e.sh. Needs a built clone
# (bash scripts/build_e2e_benchmarks.sh) and SEAL 4.1.
# Output: RL/test_results/e2e_<benchmarks>_b<budget>_<jobid>.csv
#
# Original CHEHAB RL agent instead of the unified one (single objective, no budget, no
# preference; agent_model in RL/fhe_rl/config.py): set FHE_E2E_FRAMEWORK=original. MODEL,
# BUDGET and the preference are then ignored by the agent; pass one preference to run each
# benchmark once. Output: RL/test_results/e2e_original_<benchmarks>_<jobid>.csv
#
# Separated pipeline (Stage 1 ops agent -> Stage 2 rotations agent): MODEL is the Stage 1
# model and FHE_E2E_MODEL_STAGE2 the Stage 2 model (absolute path).
# Output: RL/test_results/e2e_sep_<benchmarks>_b<budget>_<jobid>.csv
#
# Optional environment (sbatch --export=ALL,...):
#   METHOD=nato_sc|margin_barrier|noise_masking|none  constraint method of the agent (default nato_sc)
#   ROLLBACK=0      compile the agent's final program (no rollback; the SEAL bound still applies)
#   OUT_DIR=<dir>   folder for the CSV (default RL/test_results)
#   LINES=1-20      benchmark "threshold" (near-threshold dataset): dataset lines to run
#   PASSTHROUGH=1   no agent: compile and run the input program (baseline execution time)

#SBATCH --reservation=c2
#SBATCH -p compute
#SBATCH --mem 32GB
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 4
#SBATCH -t 2-00:00:00
#SBATCH -o logs/output.e2e.%j.txt
#SBATCH -e logs/error.e2e.%j.txt
#SBATCH -J e2e-unified

BUDGET="${1:?usage: sbatch eval_unified_e2e.sbatch BUDGET MODEL BENCHMARKS [PREFERENCES]}"
MODEL="${2:?missing MODEL}"
BENCHMARKS="${3:?missing BENCHMARKS}"
PREFERENCES="${4:-}"
set --        # otherwise conda's activate script reads the job's arguments as an environment name

# System compiler for the generated SEAL programs, found before conda (see build_e2e_benchmarks.sh)
module load gcc 2>/dev/null || true
# cmake builds the generated SEAL programs; some nodes (e.g. the c2 reservation) only have it as a module
command -v cmake >/dev/null 2>&1 || module load cmake 2>/dev/null || true
export FHE_E2E_CXX="${FHE_E2E_CXX:-$(which g++ 2>/dev/null || echo /usr/bin/g++)}"

set +u
if [ -f "/share/apps/NYUAD5/miniconda/3-4.11.0/bin/activate" ]; then
    source /share/apps/NYUAD5/miniconda/3-4.11.0/bin/activate
fi
CONDA_ENV="${CONDA_ENV:-$HOME/.conda/envs/fhe_rl}"   # same env as the training / eval scripts
conda activate "$CONDA_ENV" || { echo "ERROR: cannot activate the conda env $CONDA_ENV"; exit 1; }
set -u
unset CXX CC CXXFLAGS CFLAGS CPPFLAGS LDFLAGS
export PYTHONUNBUFFERED=1
export PYTHON="$(which python)"     # the compiler calls $PYTHON -m fhe_rl (else /usr/bin/python3)
if ! command -v cmake >/dev/null 2>&1; then
    echo "ERROR: cmake not found on $(hostname). Install it in the conda env once (on the login node):"
    echo "  conda activate $CONDA_ENV && pip install cmake"
    exit 1
fi

if [ -n "${SLURM_SUBMIT_DIR:-}" ] && [ -d "${SLURM_SUBMIT_DIR}/RL" ]; then
    PROJ_ROOT="$SLURM_SUBMIT_DIR"
else
    PROJ_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi
cd "$PROJ_ROOT"
export PYTHONPATH="$PROJ_ROOT/RL:$PROJ_ROOT/RL/pytrs:${PYTHONPATH:-}"
mkdir -p RL/test_results logs

# SEAL 4.1 for the generated programs (the one built by build_bfv_noise_cli.sh, or SEAL_DIR)
if [ -z "${SEAL_DIR:-}" ]; then
    SEAL_CONFIG="$(find /scratch/${USER}/opt/SEAL-4.1 ${CONDA_PREFIX:-} -maxdepth 6 -name SEALConfig.cmake -path '*SEAL-4.1*' 2>/dev/null | head -n 1 || true)"
    [ -n "$SEAL_CONFIG" ] && export SEAL_DIR="$(dirname "$SEAL_CONFIG")"
fi
if [ -z "${SEAL_DIR:-}" ]; then
    echo "ERROR: SEAL 4.1 not found. Run scripts/build_bfv_noise_cli.sh once, or set SEAL_DIR."
    exit 1
fi

# SEAL noise-bound certificate for the agent's rollback (read by `fhe_rl run` through the
# compiler's subprocess). Same parameters as the generated SEAL programs:
#   N = 16384, t = PlainModulus::Batching(16384, 20) = 786433, q = BFVDefault(16384).
export FHE_BFV_NOISE_BOUND_EXECUTABLE="${FHE_BFV_NOISE_BOUND_EXECUTABLE:-$PROJ_ROOT/build_bfv_noise/bfv_noise_bound_cli}"
export FHE_BFV_POLY_MODULUS_DEGREE=16384
export FHE_BFV_PLAIN_MODULUS=786433
export FHE_BFV_COEFF_MODULUS_BITS=48,48,48,49,49,49,49,49,49
if [ "${FHE_E2E_FRAMEWORK:-unified}" != "original" ] && [ ! -x "$FHE_BFV_NOISE_BOUND_EXECUTABLE" ]; then
    echo "ERROR: noise-bound certificate not found: $FHE_BFV_NOISE_BOUND_EXECUTABLE (run scripts/build_bfv_noise_cli.sh)"
    exit 1
fi

TAG="$(echo "$BENCHMARKS" | tr ',' '-')"
JOB="${SLURM_JOB_ID:-local}"
FRAMEWORK="${FHE_E2E_FRAMEWORK:-unified}"
MODEL2="${FHE_E2E_MODEL_STAGE2:-}"
STAGE2_ARGS=()
OUT_DIR="${OUT_DIR:-RL/test_results}"
mkdir -p "$OUT_DIR"
METHOD="${METHOD:-nato_sc}"
ROLLBACK="${ROLLBACK:-1}"
STAGE2_ARGS+=(--method "$METHOD")
[ "$ROLLBACK" = "0" ] && STAGE2_ARGS+=(--no-rollback)
# AGENT_BUDGET=9000000: the agent runs with this budget, the rollback still uses BUDGET
AGENT_BUDGET="${AGENT_BUDGET:-}"
[ -n "$AGENT_BUDGET" ] && STAGE2_ARGS+=(--agent-budget "$AGENT_BUDGET")
# FOLD_CONSTANTS=1: fold the constant-only subexpressions before compiling (plaintext-plaintext ops)
FOLD_CONSTANTS="${FOLD_CONSTANTS:-0}"
[ "$FOLD_CONSTANTS" = "1" ] && STAGE2_ARGS+=(--fold-constants)
LINES="${LINES:-}"
PASSTHROUGH="${PASSTHROUGH:-0}"
[ -n "$LINES" ] && STAGE2_ARGS+=(--lines "$LINES") && TAG="${TAG}_L${LINES//,/_}"
[ "$PASSTHROUGH" = "1" ] && STAGE2_ARGS+=(--passthrough) && TAG="${TAG}_input"
[ -n "$AGENT_BUDGET" ] && TAG="${TAG}_agent${AGENT_BUDGET}"
[ "$FOLD_CONSTANTS" = "1" ] && TAG="${TAG}_fold"
if [ "$FRAMEWORK" = "original" ]; then
    OUT="$OUT_DIR/e2e_original_${TAG}_${JOB}.csv"
elif [ -n "$MODEL2" ]; then
    OUT="$OUT_DIR/e2e_sep_${TAG}_b${BUDGET}_${JOB}.csv"
    STAGE2_ARGS+=(--model-stage2 "$MODEL2")
else
    OUT="$OUT_DIR/e2e_${TAG}_b${BUDGET}_${JOB}.csv"
fi
PREF_ARGS=()
[ -n "$PREFERENCES" ] && PREF_ARGS=(--prefs "$PREFERENCES")

echo "════════════════════════════════════════════════════════════"
echo "  UNIFIED AGENT: REAL COMPILE + SEAL EXECUTION"
echo "  Framework:   $FRAMEWORK"
echo "  Model:       $MODEL"
[ -n "$MODEL2" ] && echo "  Stage 2:     $MODEL2 (separated pipeline)"
echo "  Method:      $METHOD   rollback: $([ "$ROLLBACK" = "0" ] && echo off || echo on)"
echo "  Benchmarks:  $BENCHMARKS${LINES:+   lines $LINES}$([ "$PASSTHROUGH" = "1" ] && echo '   PASSTHROUGH (input program)')"
[ -n "$AGENT_BUDGET" ] && echo "  Agent budget: $AGENT_BUDGET (rollback at $BUDGET)"
[ "$FOLD_CONSTANTS" = "1" ] && echo "  Constant folding: ON"
echo "  cmake:       $(command -v cmake)"
echo "  Budget:      $BUDGET bits"
echo "  Python:      $PYTHON"
echo "  C++:         $FHE_E2E_CXX"
echo "  SEAL:        $SEAL_DIR"
echo "  Certificate: $FHE_BFV_NOISE_BOUND_EXECUTABLE"
echo "  Output:      $OUT"
echo "════════════════════════════════════════════════════════════"

python -u scripts/run_benchmarks_unified.py \
    --framework "$FRAMEWORK" \
    --model "$MODEL" \
    ${STAGE2_ARGS[@]+"${STAGE2_ARGS[@]}"} \
    --budget "$BUDGET" \
    --benchmarks "$BENCHMARKS" \
    ${PREF_ARGS[@]+"${PREF_ARGS[@]}"} \
    --work-dir "e2e_${TAG}_b${BUDGET}_${JOB}" \
    --seal-dir "$SEAL_DIR" \
    --cxx "$FHE_E2E_CXX" \
    --output "$OUT"
