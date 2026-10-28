#!/bin/bash
# Build the SEAL BFV noise-bound CLI used by `fhe_rl test --constraint noise`
# (rollback certificate). Run once on the login node:
#     bash scripts/build_bfv_noise_cli.sh
#
# Builds only benchmarks/bfv_noise_upper_bound -> build_bfv_noise/bfv_noise_bound_cli
# (separate from the main build/ folder), then checks it on a test expression with
# the parameters of CHEHAB's generated SEAL programs:
#   N = 16384, plain modulus = PlainModulus::Batching(16384, 20) = 786433,
#   coeff modulus = CoeffModulus::BFVDefault(16384) = 48,48,48,49,49,49,49,49,49 bits
#   (initial budget 389 - 20 = 369 bits).

set -eo pipefail

PROJ_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJ_ROOT"

module load gcc 2>/dev/null || true
set +u
if [ -f "/share/apps/NYUAD5/miniconda/3-4.11.0/bin/activate" ]; then
    source /share/apps/NYUAD5/miniconda/3-4.11.0/bin/activate
fi
conda activate /scratch/${USER}/conda/envs/chehabEnv 2>/dev/null \
    || conda activate chehabEnv 2>/dev/null \
    || true
set -u 2>/dev/null || true

CXX="${CXX:-$(which g++)}"
echo "Compiler: $CXX"

# SEAL is found with find_package(SEAL 4.1); also look in the conda env if active.
PREFIX_ARGS=()
if [ -n "${CONDA_PREFIX:-}" ]; then
    PREFIX_ARGS=(-DCMAKE_PREFIX_PATH="$CONDA_PREFIX")
fi

cmake -S benchmarks/bfv_noise_upper_bound -B build_bfv_noise \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_CXX_COMPILER="$CXX" \
    "${PREFIX_ARGS[@]}"
cmake --build build_bfv_noise --target bfv_noise_bound_cli -j4

CLI="$PROJ_ROOT/build_bfv_noise/bfv_noise_bound_cli"
if [ ! -x "$CLI" ]; then
    echo "ERROR: $CLI was not built" >&2
    exit 1
fi

echo ""
echo "Check: (VecAdd (VecMul (Vec a b) (Vec c d)) (<< (Vec e f) 1))"
echo "(VecAdd (VecMul (Vec a b) (Vec c d)) (<< (Vec e f) 1))" | "$CLI" \
    --poly-modulus-degree 16384 \
    --plain-modulus 786433 \
    --coeff-modulus-bits 48,48,48,49,49,49,49,49,49
echo ""
echo "OK: $CLI"
echo "Expected: JSON with remaining_noise_budget_bits (a bit below 369) and \"decryptable\":true"
