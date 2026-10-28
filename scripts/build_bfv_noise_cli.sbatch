#!/bin/bash
# Build SEAL 4.1 (if missing) + the BFV noise-bound certificate CLI on a compute node.
# Wraps scripts/build_bfv_noise_cli.sh (same steps, run through SLURM instead of the login node).
#
# Output: build_bfv_noise/bfv_noise_bound_cli   (used by `fhe_rl test --constraint noise`
#         via FHE_BFV_NOISE_BOUND_EXECUTABLE, e.g. in eval_pipeline_comparison.sbatch)
#
# If SEAL has to be built, its source is cloned to /scratch/$USER/opt/src/SEAL.
# Compute nodes may have no internet: clone it on the LOGIN node first:
#   git clone --depth 1 --branch v4.1.1 https://github.com/microsoft/SEAL.git /scratch/$USER/opt/src/SEAL
#
# Submit from the repo root:  mkdir -p logs && sbatch scripts/build_bfv_noise_cli.sbatch

#SBATCH -p compute
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 8
#SBATCH --mem 16GB
#SBATCH -t 02:00:00
#SBATCH -J build-bfv-noise
#SBATCH -o logs/build_bfv_noise.%j.out
#SBATCH -e logs/build_bfv_noise.%j.err

set -eo pipefail

if [ -n "${SLURM_SUBMIT_DIR:-}" ] && [ -f "${SLURM_SUBMIT_DIR}/scripts/build_bfv_noise_cli.sh" ]; then
    PROJ_ROOT="$SLURM_SUBMIT_DIR"
else
    PROJ_ROOT="/scratch/${USER}/chehab-unified"
fi
cd "$PROJ_ROOT"
echo "Project: $PROJ_ROOT   Node: $(hostname)   Job: ${SLURM_JOB_ID:-local}"

# Compiler + CMake from the module system (the build script also loads gcc itself).
module load gcc 2>/dev/null || true
module load cmake 2>/dev/null || true
command -v cmake >/dev/null || { echo "[FAIL] cmake not found (try: module avail cmake)"; exit 1; }
echo "cmake: $(cmake --version | head -1)"

# SEAL: installed already, or source present (cloned on the login node), or try to clone here.
SEAL_PREFIX="/scratch/${USER}/opt/SEAL-4.1"
SEAL_SRC="/scratch/${USER}/opt/src/SEAL"
if [ -z "${SEAL_DIR:-}" ] && ! find "$SEAL_PREFIX" -name SEALConfig.cmake 2>/dev/null | grep -q . && [ ! -d "$SEAL_SRC" ]; then
    echo "SEAL not installed and no source at $SEAL_SRC: trying to clone from this node ..."
    if ! timeout 120 git clone --depth 1 --branch v4.1.1 https://github.com/microsoft/SEAL.git "$SEAL_SRC"; then
        echo "[FAIL] cannot download SEAL from the compute node. On the login node run:"
        echo "  git clone --depth 1 --branch v4.1.1 https://github.com/microsoft/SEAL.git $SEAL_SRC"
        echo "then resubmit this job."
        exit 1
    fi
fi

bash scripts/build_bfv_noise_cli.sh

CLI="$PROJ_ROOT/build_bfv_noise/bfv_noise_bound_cli"
[ -x "$CLI" ] || { echo "[FAIL] $CLI not built"; exit 1; }
echo ""
echo "[ OK ] BFV noise certificate CLI: $CLI"
echo "Use it in eval jobs with:"
echo "  export FHE_BFV_NOISE_BOUND_EXECUTABLE=$CLI"
echo "  export FHE_BFV_POLY_MODULUS_DEGREE=16384"
echo "  export FHE_BFV_PLAIN_MODULUS=786433"
echo "  export FHE_BFV_COEFF_MODULUS_BITS=48,48,48,49,49,49,49,49,49"
