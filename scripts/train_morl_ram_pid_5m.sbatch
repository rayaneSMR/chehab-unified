#!/bin/bash

#SBATCH -p compute
#SBATCH --mem 64GB
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 16
#SBATCH -t 7-00:00:00

# Email notifications on completion or failure
#SBATCH --mail-user=${USER}@nyu.edu
#SBATCH --mail-type=END,FAIL

# Standard output and error logs (labeled with SLURM Job ID %j)
#SBATCH -o logs/output.morl_ram_pid_5m.%j.txt
#SBATCH -e logs/error.morl_ram_pid_5m.%j.txt
#SBATCH -J morl-ram-pid-5m

set +u
# Activate cluster conda environment
if [ -f "/share/apps/NYUAD5/miniconda/3-4.11.0/bin/activate" ]; then
    source /share/apps/NYUAD5/miniconda/3-4.11.0/bin/activate
fi
conda activate /scratch/${USER}/conda/envs/chehabEnv 2>/dev/null || conda activate /scratch/${USER}/conda/envs/chehabEnv 2>/dev/null || conda activate chehabEnv 2>/dev/null || conda activate chehab 2>/dev/null || true
set -u

export PYTHONUNBUFFERED=1

# Determine project root dynamically from SLURM_SUBMIT_DIR or fallback
if [ -n "${SLURM_SUBMIT_DIR:-}" ] && [ -d "${SLURM_SUBMIT_DIR}/RL" ]; then
    PROJ_ROOT="$SLURM_SUBMIT_DIR"
elif [ -d "/scratch/${USER}/chehab-unified/RL" ]; then
    PROJ_ROOT="/scratch/${USER}/chehab-unified"
elif [ -d "/scratch/${NETID:-$(whoami)}/chehab-unified/RL" ]; then
    PROJ_ROOT="/scratch/${NETID:-$(whoami)}/chehab-unified"
else
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJ_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
fi

mkdir -p "$PROJ_ROOT/logs"

cd "$PROJ_ROOT/RL"
export PYTHONPATH="$PROJ_ROOT/RL:$PROJ_ROOT/RL/pytrs:${PYTHONPATH:-}"

# ═══════════════════════════════════════════════════════════════
# Task:       RAM-constrained Multi-Objective RL (Latency + Keys)
# Framework:  MORL (Multi-Objective)
# Method:     nato_sc (Safety Checkpointing + Quadratic Penalty)
# Algo:       lagrangian_pid (PID Adaptive Multiplier)
# Budgets:    1500, 2000, 2600, 1000000 (MB)
# Timesteps:  5,000,000
# Eval Freq:  10,000 timesteps
# Workers:    8 parallel environments across 16 CPU cores
# ═══════════════════════════════════════════════════════════════
METHOD="nato_sc"
ALGO="lagrangian_pid"
BUDGETS="1500,2000,2600,1000000"
TIMESTEPS=5000000
EVAL_FREQ=10000
NUM_ENVS=8

echo "════════════════════════════════════════════"
echo "  Framework:   MORL"
echo "  Algorithm:   $ALGO"
echo "  Method:      $METHOD"
echo "  Budgets:     $BUDGETS"
echo "  Timesteps:   $TIMESTEPS"
echo "  Eval Freq:   Every $EVAL_FREQ timesteps"
echo "  Workers:     $NUM_ENVS parallel envs (16 CPUs)"
echo "  Job ID:      ${SLURM_JOB_ID:-local}"
echo "  User:        ${USER:-$(whoami)} (alert to ${USER:-$(whoami)}@nyu.edu)"
echo "════════════════════════════════════════════"

stdbuf -oL -eL python -u -m fhe_rl \
    --framework morl train \
    --timesteps $TIMESTEPS \
    --eval_freq $EVAL_FREQ \
    --algo "$ALGO" \
    --method "$METHOD" \
    --budgets "$BUDGETS" \
    --num_envs $NUM_ENVS \
    "$@" \
    2>&1 | tee -a "$PROJ_ROOT/logs/train_morl_ram_pid_5m_${SLURM_JOB_ID:-local}.log"
