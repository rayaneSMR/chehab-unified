#!/bin/bash
#SBATCH -p compute
#SBATCH --time=06:00:00
#SBATCH --cpus-per-task=8
#SBATCH --mem=64GB
#SBATCH -J dnn-dataset
#SBATCH -o build_dnn.%j.log
#SBATCH -e build_dnn.%j.err

set -euo pipefail

# Activate conda environment (support chehabEnv or chehab)
if [ -f /share/apps/NYUAD5/miniconda/3-4.11.0/bin/activate ]; then
    source /share/apps/NYUAD5/miniconda/3-4.11.0/bin/activate
elif [ -f ~/miniconda3/bin/activate ]; then
    source ~/miniconda3/bin/activate
fi

if conda info --envs | grep -q "chehabEnv"; then
    conda activate chehabEnv
elif conda info --envs | grep -q "chehab"; then
    conda activate chehab
fi

# Detect project root dynamically
NETID=${NETID:-$(whoami)}
PROJ_ROOT="/scratch/${NETID}/chehab-unified"
if [ ! -d "$PROJ_ROOT" ]; then
    PROJ_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi

cd "$PROJ_ROOT"
export PYTHONPATH="$PROJ_ROOT/RL:$PROJ_ROOT/RL/pytrs:${PYTHONPATH:-}"

echo "[build] starting $(date) on $HOSTNAME"
echo "[build] project root: $PROJ_ROOT"

python scripts/build_dnn_dataset.py \
    --benchmarks conv2d,full_dnn,cryptonets,mlp,lola,lenet,resnet20_relu,resnet20_silu,resnet34_relu,resnet34_silu,resnet50_relu,resnet50_silu,alexnet \
    --skip-existing \
    --timeout 1200

echo "[build] done $(date)"
ls -la "$PROJ_ROOT/RL/fhe_rl/datasets/dnn_full_benchmarks.txt"
