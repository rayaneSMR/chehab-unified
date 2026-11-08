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
# Optional environment (sbatch --export=ALL,...), all defaulting to the behaviour above:
#   METHOD=nato_sc|margin_barrier|noise_masking|none   constraint method the agent was trained with
#   ROLLBACK=1|0      0 = compile the agent's raw output (no safety rollback)
#   OUT_DIR=<dir>     folder for the CSV (default RL/test_results)
#   CONDA_ENV=<path>  conda env to activate first (default: chehabEnv)
# (used by scripts/ablation_unified/e2e_4pref.sh for the 4-preference ablation agents)

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

# System compiler for the generated SEAL programs, found before conda (see build_e2e_benchmarks.sh)
module load gcc 2>/dev/null || true
# cmake builds the generated SEAL programs; the fhe_rl conda env has none (base conda had it)
module load cmake/3.28.0 2>/dev/null || true
command -v cmake >/dev/null || { echo "ERROR: cmake not found (module load cmake/3.28.0 failed)"; exit 1; }
export FHE_E2E_CXX="${FHE_E2E_CXX:-$(which g++ 2>/dev/null || echo /usr/bin/g++)}"

set +u
set --   # arguments are already read above; otherwise conda's activate receives them (ArgumentError)
if [ -f "/share/apps/NYUAD5/miniconda/3-4.11.0/bin/activate" ]; then
    source /share/apps/NYUAD5/miniconda/3-4.11.0/bin/activate
fi
{ [ -n "${CONDA_ENV:-}" ] && conda activate "$CONDA_ENV" 2>/dev/null; } \
    || conda activate /scratch/${USER}/conda/envs/chehabEnv 2>/dev/null \
    || conda activate chehabEnv 2>/dev/null \
    || true
set -u
unset CXX CC CXXFLAGS CFLAGS CPPFLAGS LDFLAGS
export PYTHONUNBUFFERED=1
export PYTHON="$(which python)"     # the compiler calls $PYTHON -m fhe_rl (else /usr/bin/python3)

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

TAG="$(echo "$BENCHMARKS" | tr ',' '-')"
JOB="${SLURM_JOB_ID:-local}"
OUT_DIR="${OUT_DIR:-RL/test_results}"
mkdir -p "$OUT_DIR"
OUT="$OUT_DIR/e2e_${TAG}_b${BUDGET}_${JOB}.csv"
METHOD="${METHOD:-nato_sc}"
ROLLBACK="${ROLLBACK:-1}"
PREF_ARGS=()
[ -n "$PREFERENCES" ] && PREF_ARGS=(--prefs "$PREFERENCES")
EXTRA_ARGS=(--method "$METHOD")
[ "$ROLLBACK" = "0" ] && EXTRA_ARGS+=(--no-rollback)

echo "════════════════════════════════════════════════════════════"
echo "  UNIFIED AGENT: REAL COMPILE + SEAL EXECUTION"
echo "  Model:       $MODEL"
echo "  Benchmarks:  $BENCHMARKS"
echo "  Budget:      $BUDGET bits"
echo "  Method:      $METHOD   rollback: $([ "$ROLLBACK" = "0" ] && echo off || echo on)"
echo "  Python:      $PYTHON"
echo "  C++:         $FHE_E2E_CXX"
echo "  SEAL:        $SEAL_DIR"
echo "  Output:      $OUT"
echo "════════════════════════════════════════════════════════════"

python -u scripts/run_benchmarks_unified.py \
    --model "$MODEL" \
    --budget "$BUDGET" \
    --benchmarks "$BENCHMARKS" \
    ${PREF_ARGS[@]+"${PREF_ARGS[@]}"} \
    "${EXTRA_ARGS[@]}" \
    --work-dir "e2e_${TAG}_b${BUDGET}_${JOB}" \
    --seal-dir "$SEAL_DIR" \
    --cxx "$FHE_E2E_CXX" \
    --output "$OUT"
