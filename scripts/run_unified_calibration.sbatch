#!/bin/bash
#SBATCH -p compute
#SBATCH --time=24:00:00
#SBATCH --cpus-per-task=8
#SBATCH --mem=0
#SBATCH -J unified-calib
#SBATCH -o calib_v4.%j.log
#SBATCH -e calib_v4.%j.err
#SBATCH --mail-type=BEGIN,END,FAIL

# Trap any uncaught error and log detailed context
set -eo pipefail
trap 'echo "[ERROR] Job 2 (Unified Calibration) failed at line $LINENO with exit code $? at $(date)" >&2' ERR

echo "================================================================="
echo "[JOB 2: Unified Memory Calibration v4] STARTING"
echo "Timestamp : $(date)"
echo "Node      : ${SLURMD_NODENAME:-$HOSTNAME}"
echo "Job ID    : ${SLURM_JOB_ID:-"local"}"
echo "User      : ${USER:-$(whoami)}"
echo "================================================================="

# Disable strict unbound variable checking during conda activation
set +u
if [ -f /share/apps/NYUAD5/miniconda/3-4.11.0/bin/activate ]; then
    source /share/apps/NYUAD5/miniconda/3-4.11.0/bin/activate
elif [ -f ~/miniconda3/bin/activate ]; then
    source ~/miniconda3/bin/activate
fi

conda activate /scratch/${USER}/conda/envs/chehabEnv 2>/dev/null || \
conda activate chehabEnv 2>/dev/null || \
conda activate chehab 2>/dev/null || true
set -u

# Detect project root dynamically
NETID=${NETID:-$(whoami)}
PROJ_ROOT="/scratch/${NETID}/chehab-unified"
if [ ! -d "$PROJ_ROOT" ]; then
    PROJ_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi

cd "$PROJ_ROOT"
export PYTHONPATH="$PROJ_ROOT/RL:$PROJ_ROOT/RL/pytrs:${PYTHONPATH:-}"

echo "[calib] Project Root: $PROJ_ROOT"
echo "[calib] Python Interpreter: $(which python3 2>/dev/null || which python)"
python3 -c "import sys; print('[calib] Python Version:', sys.version.split()[0])" || true

# Verify Go toolchain for Lattigo native compilation
if command -v go >/dev/null 2>&1; then
    echo "[calib] Go toolchain: $(go version)"
else
    echo "[calib] WARNING: Go toolchain not found on standard PATH, checking /usr/local/go/bin"
    export PATH="/usr/local/go/bin:$PATH"
fi

# Ensure datasets directory exists
mkdir -p "$PROJ_ROOT/RL/fhe_rl/datasets"

# STEP 1: Build the unified diverse calibration pool
echo ""
echo "-----------------------------------------------------------------"
echo "[calib] STEP 1/3: Building Unified Diverse Calibration Pool"
echo "-----------------------------------------------------------------"
python3 scripts/build_unified_calib_pool.py \
    --target-size 600

POOL_FILE="$PROJ_ROOT/RL/fhe_rl/datasets/unified_calibration_pool.jsonl"
if [ ! -f "$POOL_FILE" ]; then
    echo "[calib] ERROR: Pool file $POOL_FILE was not created!" >&2
    exit 1
fi
echo "[calib] Pool created successfully: $(wc -l < "$POOL_FILE") circuits registered"

# STEP 2: Multi-trial empirical measurement harness (5 runs per circuit)
echo ""
echo "-----------------------------------------------------------------"
echo "[calib] STEP 2/3: Running Multi-Trial Empirical Profiling (>= 5 runs/circuit)"
echo "-----------------------------------------------------------------"
python3 scripts/measure_calib_hpc.py \
    --pool "$POOL_FILE" \
    --output-csv "$PROJ_ROOT/RL/fhe_rl/datasets/unified_calib_measurements_5runs.csv" \
    --failures-log "$PROJ_ROOT/RL/fhe_rl/datasets/calib_measurements_failures.log" \
    --runs 5 \
    --timeout 600

CSV_FILE="$PROJ_ROOT/RL/fhe_rl/datasets/unified_calib_measurements_5runs.csv"
if [ ! -f "$CSV_FILE" ]; then
    echo "[calib] ERROR: Measurements CSV $CSV_FILE was not created!" >&2
    exit 1
fi
echo "[calib] Empirical profiling complete: $(wc -l < "$CSV_FILE") records measured"

# STEP 3: Fit unified calibration model (v4) and run literature validation battery
echo ""
echo "-----------------------------------------------------------------"
echo "[calib] STEP 3/3: Fitting Unified Calibration Model & Literature Validation Battery"
echo "-----------------------------------------------------------------"
python3 scripts/fit_unified_calib_v4.py \
    --measurements-csv "$CSV_FILE" \
    --output-json "$PROJ_ROOT/RL/fhe_rl/memory_calib_v4.json" \
    --report-md "$PROJ_ROOT/RL/fhe_rl/UNIFIED_CALIBRATION_V4_REPORT.md"

CALIB_JSON="$PROJ_ROOT/RL/fhe_rl/memory_calib_v4.json"
REPORT_MD="$PROJ_ROOT/RL/fhe_rl/UNIFIED_CALIBRATION_V4_REPORT.md"

if [ ! -f "$CALIB_JSON" ]; then
    echo "[calib] ERROR: Calibration output $CALIB_JSON was not created!" >&2
    exit 1
fi

echo "================================================================="
echo "[JOB 2: Unified Memory Calibration v4] COMPLETED SUCCESSFULLY"
echo "Timestamp: $(date)"
echo "Artifacts generated:"
echo "  - Calibration Parameters : $CALIB_JSON"
echo "  - Validation Report      : $REPORT_MD"
echo "  - Raw Empirical Data     : $CSV_FILE"
echo "================================================================="
