#!/bin/bash
#SBATCH --mem 64GB
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 16
#SBATCH -t 7-00:00:00
#SBATCH --mail-user=rs10728@nyu.edu
#SBATCH --mail-type=BEGIN,END,FAIL
#SBATCH -o /scratch/rs10728/heongpu-project/logs/output.gpu_ctx.%j.txt
#SBATCH -e /scratch/rs10728/heongpu-project/logs/error.gpu_ctx.%j.txt
#SBATCH -J gpu_ctx
#SBATCH -p compute
#SBATCH --signal=B:TERM@300

module load gcc/11.5.0 cuda/12.2.0
export PYTHONUNBUFFERED=1
export PEAK_RAM_BACKEND=gpu          # estimator = HEonGPU (A100) + label-fixed packing
export ROT_LOG=/scratch/rs10728/heongpu-project/logs/rot_nonzero_${SLURM_JOB_ID:-local}.log
PY=/home/rs10728/.conda/envs/fhe_rl/bin/python
PROJ_ROOT=/scratch/rs10728/heongpu-project/src/chehab-unified
mkdir -p /scratch/rs10728/heongpu-project/logs
cd "$PROJ_ROOT/RL"
export PYTHONPATH="$PROJ_ROOT/RL:$PROJ_ROOT/RL/pytrs:${PYTHONPATH:-}"

CONSTRAINT="mem"
BUDGETS="${BUDGETS:-1000,1500,2000,3000,1000000}"
METHOD="nato_sc"; ALGO="lagrangian_pid"; ENCODING="film"; VARIANT="film_a"
TIMESTEPS="${TIMESTEPS:-5000000}"; EVAL_FREQ="${EVAL_FREQ:-30000}"; NUM_ENVS="${NUM_ENVS:-8}"
START_ARGS="${START_ARGS:---fresh_start}"

echo "==== unified GPU run | backend check ===="
$PY -c "import sys; sys.path[:0]=['fhe_rl','pytrs']; import memory; print('BACKEND:', memory.BACKEND, memory.ESTIMATOR_VERSION, memory._gpu_params(), memory.GPU_CTX_MB)"
echo "budgets=$BUDGETS timesteps=$TIMESTEPS eval_freq=$EVAL_FREQ envs=$NUM_ENVS start=$START_ARGS job=${SLURM_JOB_ID:-local}"

exec stdbuf -oL -eL $PY -u -m fhe_rl \
    --framework unified train \
    --dataset ./fhe_rl/datasets/final_llm_dataset.txt \
    --constraint "$CONSTRAINT" --budgets "$BUDGETS" \
    --timesteps $TIMESTEPS --eval_freq $EVAL_FREQ --num_envs $NUM_ENVS \
    --method "$METHOD" --algo "$ALGO" \
    --budget_encoding "$ENCODING" --policy_variant "$VARIANT" \
    --embedder gnn \
    $START_ARGS "$@" \
    > "/scratch/rs10728/heongpu-project/logs/train_gpu_ctx_${SLURM_JOB_ID:-local}.log" 2>&1
