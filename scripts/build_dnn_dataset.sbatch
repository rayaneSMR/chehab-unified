#!/bin/bash
#SBATCH -p compute
#SBATCH --time=24:00:00
#SBATCH --cpus-per-task=8
#SBATCH --mem=0
#SBATCH -J dnn-dataset
#SBATCH -o build_dnn.%j.log
#SBATCH -e build_dnn.%j.err
#SBATCH --mail-type=BEGIN,END,FAIL

# Trap any uncaught error and log detailed context
set -eo pipefail
trap 'echo "[ERROR] Job 1 (DNN Dataset Extraction) failed at line $LINENO with exit code $? at $(date)" >&2' ERR

echo "================================================================="
echo "[JOB 1: DNN Dataset Extraction] STARTING"
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

# Detect project root dynamically (portable across scratch and home workspaces)
NETID=${NETID:-$(whoami)}
PROJ_ROOT="/scratch/${NETID}/chehab-unified"
if [ ! -d "$PROJ_ROOT" ]; then
    PROJ_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi

cd "$PROJ_ROOT"
export PYTHONPATH="$PROJ_ROOT/RL:$PROJ_ROOT/RL/pytrs:${PYTHONPATH:-}"

echo "[build] Project Root: $PROJ_ROOT"
echo "[build] Python Interpreter: $(which python3 2>/dev/null || which python)"
python3 -c "import sys; print('[build] Python Version:', sys.version.split()[0])" || true

# Verify Go toolchain
if command -v go >/dev/null 2>&1; then
    echo "[build] Go toolchain: $(go version)"
else
    echo "[build] WARNING: Go toolchain not found on standard PATH, checking /usr/local/go/bin"
    export PATH="/usr/local/go/bin:$PATH"
fi

# Ensure datasets directory exists
mkdir -p "$PROJ_ROOT/RL/fhe_rl/datasets"

echo "[build] Launching DNN benchmark extraction..."
python3 scripts/build_dnn_dataset.py \
    --benchmarks conv2d,full_dnn,cryptonets,mlp,lola,lenet,resnet20_relu,resnet20_silu,resnet34_relu,resnet34_silu,resnet50_relu,resnet50_silu,alexnet \
    --skip-existing \
    --timeout 7200

echo "================================================================="
echo "[JOB 1: DNN Dataset Extraction] COMPLETED SUCCESSFULLY"
echo "Timestamp: $(date)"
echo "Generated Artifacts:"
ls -lh "$PROJ_ROOT/RL/fhe_rl/datasets/"*dnn* "$PROJ_ROOT/RL/fhe_rl/datasets/"*conv2d* 2>/dev/null || true
echo "================================================================="
