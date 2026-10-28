#!/bin/bash

#SBATCH -p compute
#SBATCH --mem 64GB
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 33
#SBATCH -t 7-00:00:00

# Email notifications on start, completion, or failure
#SBATCH --mail-user=${USER}@nyu.edu
#SBATCH --mail-type=BEGIN,END,FAIL

# Standard output and error logs
#SBATCH -o logs/output.unified_noise.%j.txt
#SBATCH -e logs/error.unified_noise.%j.txt
#SBATCH -J unified-noise

# Pre-timeout checkpointing signal 5 minutes before kill
#SBATCH --signal=B:TERM@300

set +u
# Activate cluster conda environment safely
if [ -f "/share/apps/NYUAD5/miniconda/3-4.11.0/bin/activate" ]; then
    source /share/apps/NYUAD5/miniconda/3-4.11.0/bin/activate
fi
conda activate /scratch/${USER}/conda/envs/chehabEnv 2>/dev/null \
    || conda activate /scratch/${NETID:-$(whoami)}/conda/envs/chehabEnv 2>/dev/null \
    || conda activate chehabEnv 2>/dev/null \
    || true
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

# Ensure all target directories exist
mkdir -p "$PROJ_ROOT/logs" "$PROJ_ROOT/RL/eval" "$PROJ_ROOT/RL/checkpoints"

cd "$PROJ_ROOT/RL"
export PYTHONPATH="$PROJ_ROOT/RL:$PROJ_ROOT/RL/pytrs:${PYTHONPATH:-}"

CONSTRAINT="noise"
BUDGETS="230,236,369,9000000"
METHOD="nato_sc"
ALGO="lagrangian_pid"
ENCODING="film"
VARIANT="film_a"
DATASET="./fhe_rl/datasets/final_llm_dataset.txt"
TIMESTEPS=5000000
EVAL_FREQ=10000
NUM_ENVS=32
# Keep 16384 samples per PPO update (same as the old 8 envs x 2048 steps)
ROLLOUT_SIZE=16384
N_STEPS=$((ROLLOUT_SIZE / NUM_ENVS))

echo "════════════════════════════════════════════"
echo "  Framework:       unified"
echo "  Constraint:      $CONSTRAINT"
echo "  Budgets:         $BUDGETS (bits)"
echo "  Method:          $METHOD"
echo "  Algo:            $ALGO"
echo "  Budget Encoding: $ENCODING"
echo "  Policy Variant:  $VARIANT"
echo "  Embedder:        gnn"
echo "  Timesteps:       $TIMESTEPS"
echo "  Eval Freq:       Every $EVAL_FREQ timesteps"
echo "  Workers:         $NUM_ENVS parallel envs (${SLURM_CPUS_PER_TASK:-?} CPU cores)"
echo "  Rollout:         $N_STEPS steps/env x $NUM_ENVS envs = $((N_STEPS * NUM_ENVS)) samples per update"
echo "  Job ID:          ${SLURM_JOB_ID:-local}"
echo "  Alerts to:       ${USER:-$(whoami)}@nyu.edu"
echo "════════════════════════════════════════════"

stdbuf -oL -eL python -u -m fhe_rl \
    --framework unified train \
    --dataset "$DATASET" \
    --constraint "$CONSTRAINT" \
    --budgets "$BUDGETS" \
    --timesteps $TIMESTEPS \
    --eval_freq $EVAL_FREQ \
    --num_envs $NUM_ENVS \
    --n_steps $N_STEPS \
    --method "$METHOD" \
    --algo "$ALGO" \
    --budget_encoding "$ENCODING" \
    --policy_variant "$VARIANT" \
    --embedder gnn \
    --fresh_start \
    "$@" \
    > "$PROJ_ROOT/logs/train_unified_noise_${SLURM_JOB_ID:-local}.log" 2>&1
