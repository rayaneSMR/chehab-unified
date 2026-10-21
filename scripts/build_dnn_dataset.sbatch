#!/bin/bash
#
# One-time build of the DNN expression dataset for CHEHAB evaluation.
#
#   python scripts/build_dnn_dataset.py --benchmarks ...
#
# Just calls the builder; the .py script does the real work.  Used from the
# login node to a compute node (see the README workflow in the message you
# replied to).
#

#SBATCH -p compute
#SBATCH --time=04:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=16GB
#SBATCH -J dnn-dataset
#SBATCH -o build_dnn.log
#SBATCH -e build_dnn.err

set -euo pipefail

source /share/apps/NYUAD5/miniconda/3-4.11.0/bin/activate
conda activate chehab

cd /scratch/${NETID:-${LOGNAME}}/chehab-unified/RL
export NETID=${NETID:-$LOGNAME}

echo "[build] starting $(date) on \$HOSTNAME"
python scripts/build_dnn_dataset.py \
    --benchmarks conv2d,full_dnn,cryptonets,mlp,lola,lenet, \
       resnet20_relu,resnet20_silu,resnet34_relu,resnet34_silu, \
       resnet50_relu,resnet50_silu,alexnet \
    --timeout 600
echo "[build] done $(date)"
