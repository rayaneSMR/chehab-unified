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
#
# Optional: SEAL_DIR=/path/to/lib/cmake/SEAL-4.1 bash scripts/build_bfv_noise_cli.sh

set -eo pipefail

PROJ_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJ_ROOT"

# System compiler from the gcc module, found BEFORE conda is activated (the conda
# env's own compiler wrapper is incomplete: "cannot execute 'cc1plus'").
module load gcc 2>/dev/null || true
SYSTEM_GXX="$(which g++ 2>/dev/null || echo /usr/bin/g++)"

set +u
if [ -f "/share/apps/NYUAD5/miniconda/3-4.11.0/bin/activate" ]; then
    source /share/apps/NYUAD5/miniconda/3-4.11.0/bin/activate
fi
conda activate /scratch/${USER}/conda/envs/chehabEnv 2>/dev/null \
    || conda activate chehabEnv 2>/dev/null \
    || true
set -u 2>/dev/null || true

# Drop the conda compiler settings so CMake uses the system g++.
unset CXX CC CXXFLAGS CFLAGS CPPFLAGS LDFLAGS DEBUG_CXXFLAGS DEBUG_CFLAGS
echo "Compiler: $SYSTEM_GXX ($("$SYSTEM_GXX" --version | head -1))"

# Locate SEAL (find_package(SEAL 4.1 REQUIRED) in the CLI's CMakeLists).
if [ -z "${SEAL_DIR:-}" ]; then
    SEAL_CONFIG="$(find ${CONDA_PREFIX:-} "$HOME/.local" /usr/local /usr/lib64 /scratch/${USER} \
                    -maxdepth 7 -name "SEALConfig.cmake" 2>/dev/null | head -n 1 || true)"
    if [ -n "$SEAL_CONFIG" ]; then
        SEAL_DIR="$(dirname "$SEAL_CONFIG")"
    fi
fi
if [ -z "${SEAL_DIR:-}" ]; then
    echo "ERROR: SEAL (SEALConfig.cmake) not found in the conda env, ~/.local, /usr/local or /scratch/${USER}." >&2
    echo "Find it with:  find / -name SEALConfig.cmake 2>/dev/null | head" >&2
    echo "then run:      SEAL_DIR=<folder containing SEALConfig.cmake> bash scripts/build_bfv_noise_cli.sh" >&2
    exit 1
fi
echo "SEAL:     $SEAL_DIR"

rm -rf build_bfv_noise   # a previous failed configure caches the broken compiler
cmake -S benchmarks/bfv_noise_upper_bound -B build_bfv_noise \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_CXX_COMPILER="$SYSTEM_GXX" \
    -DSEAL_DIR="$SEAL_DIR"
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
