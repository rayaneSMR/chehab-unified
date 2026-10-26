#!/bin/bash

# ═══════════════════════════════════════════════════════════════════════════
#  RUN 3 (v3) -- APPROVED  Fast-step validated: parity test PASSED
#  (bit-identical), A/B benchmark 1.98x (597.8 -> 302.5 ms/step).
#
#  Differences vs run-1 (train_unified_ram_film.sbatch):
#    * EVAL_FREQ  10,000 -> 30,000  (eval is now ~seconds thanks to
#                                    embedding/mask caches; ~167 evals total)
#    * START MODE (see START_ARGS below): default --fresh_start for an
#      independent run; optionally resume from ONE SPECIFIC checkpoint.
#      (Bare auto-resume is dangerous: glob model_*_nato_sc_film_a_gnn
#      matches ALL same-config jobs -> it can pick run-1/run-2 checkpoints,
#      incl. run-2's 8-pref lineage, or jump lineage on restart.)
#    * Code: env fast-step optimizations (duplicate GNN call removed,
#      embedding + action-mask LRU caches, gated heartbeat) -- verified
#      bit-identical by RL/test_step_parity.py.
#
#  RESTARTING run-3 itself after a cancel/timeout:
#    set START_ARGS="--checkpoint ./checkpoints/model_<RUN3_JOBID>_nato_sc_film_a_gnn/rl_model_<N>_steps.zip"
# ═══════════════════════════════════════════════════════════════════════════
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
#SBATCH -o logs/output.unified_ram_film_v3.%j.txt
#SBATCH -e logs/error.unified_ram_film_v3.%j.txt
#SBATCH -J unified-ram-v3
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
# Eval Freq:       30,000 timesteps (~167 evals; caches make each ~2s)
# Preference Pts:  10 (default n_pref=11 -> 10 vectors, same as run-1)
# Workers:         8 parallel environments across 16 CPU cores
# Resume:          --fresh_start (independent run; see header for restart how-to)
# ═══════════════════════════════════════════════════════════════
CONSTRAINT="mem"
BUDGETS="1500,2000,2600,1000000"
METHOD="nato_sc"
ALGO="lagrangian_pid"
ENCODING="film"
VARIANT="film_a"
TIMESTEPS=5000000
EVAL_FREQ=30000
NUM_ENVS=8

# ── START MODE (flip ONE line before sbatch) ──────────────────────────────
# (A) FRESH -- default, as approved: independent run from step 0.
START_ARGS="--fresh_start"
# (B) RESUME from a SPECIFIC checkpoint (e.g. run-1's latest, same science:
#     identical config + bit-identical code). Replace the line above with:
#     1) find it:  ls -t RL/checkpoints/model_*_nato_sc_film_a_gnn/rl_model_*_steps.zip | head
#     2) START_ARGS="--checkpoint ./checkpoints/model_<JOBID>_nato_sc_film_a_gnn/rl_model_<N>_steps.zip"
#     NEVER just delete --fresh_start: bare auto-resume globs
#     model_*_nato_sc_film_a_gnn and can silently pick RUN-2's 8-pref
#     checkpoints or jump lineage on a restart. And after a resume, scancel
#     the old job so the two lineages don't diverge while burning 2 nodes.
#     (Restarting run-3 itself: set START_ARGS to run-3's own latest zip.)

echo "════════════════════════════════════════════"
echo "  Framework:       unified (v3 fast-step)"
echo "  Constraint:      $CONSTRAINT"
echo "  Budgets:         $BUDGETS MB"
echo "  Method:          $METHOD"
echo "  Algo:            $ALGO"
echo "  Budget Encoding: $ENCODING"
echo "  Policy Variant:  $VARIANT"
echo "  Embedder:        gnn"
echo "  Timesteps:       $TIMESTEPS"
echo "  Eval Freq:       Every $EVAL_FREQ timesteps"
echo "  Preference Pts:  10 (run-1 baseline for comparability)"
echo "  Workers:         $NUM_ENVS parallel envs"
echo "  Start mode:      $START_ARGS"
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
    $START_ARGS \
    "$@" \
    > "$PROJ_ROOT/logs/train_unified_ram_film_v3_${SLURM_JOB_ID:-local}.log" 2>&1
