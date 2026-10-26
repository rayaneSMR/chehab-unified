#!/bin/bash

#SBATCH -p compute
#SBATCH --mem 64GB
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 16
#SBATCH -t 7-00:00:00

# Email notifications on start, completion, or failure
#SBATCH --mail-user=${USER}@nyu.edu
#SBATCH --mail-type=BEGIN,END,FAIL

# Standard output and error logs (labeled with SLURM Job ID %j)
#SBATCH -o logs/output.unified_ram_film.%j.txt
#SBATCH -e logs/error.unified_ram_film.%j.txt
#SBATCH -J unified-ram-film
# Graceful pre-timeout / pre-cancel checkpoint: SIGTERM 5 min before kill
#SBATCH --signal=B:TERM@300

set +u
# Activate cluster conda environment
if [ -f "/share/apps/NYUAD5/miniconda/3-4.11.0/bin/activate" ]; then
    source /share/apps/NYUAD5/miniconda/3-4.11.0/bin/activate
fi
conda activate /scratch/${USER}/conda/envs/chehabEnv 2>/dev/null || conda activate /scratch/${USER}/conda/envs/chehabEnv 2>/dev/null || conda activate chehabEnv 2>/dev/null || true
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
# Task:            Unified RL (MORL + Constrained Optimization)
# Framework:       Unified (fheEnvUnified + HierarchicalMaskablePolicy)
# Constraint:      mem (Process Peak RAM via calibrated v3 model)
# Budgets:         1500, 2000, 2600, 1000000 (MB)
# Method:          nato_sc (Safety Checkpointing + Quadratic Terminal Penalty)
# Algo:            lagrangian_pid (PID Adaptive Multiplier Wrapper)
# Budget Encoding: film (Feature-wise Linear Modulation)
# Policy Variant:  film_a (FiLM on budget features, Pareto-fused)
# Timesteps:       5,000,000
# Eval Freq:       10,000 timesteps
# Workers:         8 parallel environments across 16 CPU cores
# ═══════════════════════════════════════════════════════════════
CONSTRAINT="mem"
BUDGETS="1500,2000,2600,1000000"
METHOD="nato_sc"
ALGO="lagrangian_pid"
ENCODING="film"
VARIANT="film_a"
TIMESTEPS=5000000
EVAL_FREQ=10000
NUM_ENVS=8

echo "════════════════════════════════════════════"
echo "  Framework:       unified"
echo "  Constraint:      $CONSTRAINT"
echo "  Budgets:         $BUDGETS MB"
echo "  Method:          $METHOD"
echo "  Algo:            $ALGO"
echo "  Budget Encoding: $ENCODING"
echo "  Policy Variant:  $VARIANT"
echo "  Embedder:        gnn"
echo "  Timesteps:       $TIMESTEPS"
echo "  Eval Freq:       Every $EVAL_FREQ timesteps"
echo "  Workers:         $NUM_ENVS parallel envs"
echo "  Job ID:          ${SLURM_JOB_ID:-local}"
echo "  Alerts to:       ${USER:-$(whoami)}@nyu.edu"
echo "════════════════════════════════════════════"

stdbuf -oL -eL python -u -m fhe_rl \
    --framework unified train \
    --dataset ./fhe_rl/datasets/final_llm_dataset.txt \
    --constraint "$CONSTRAINT" \
    --budgets "$BUDGETS" \
    --timesteps $TIMESTEPS \
    --eval_freq $EVAL_FREQ \
    --num_envs $NUM_ENVS \
    --method "$METHOD" \
    --algo "$ALGO" \
    --budget_encoding "$ENCODING" \
    --policy_variant "$VARIANT" \
    --embedder gnn \
    "$@" \
    > "$PROJ_ROOT/logs/train_unified_ram_film_${SLURM_JOB_ID:-local}.log" 2>&1
