#!/bin/bash
# ════════════════════════════════════════════════════════════════════════════
# Experiment: unified agent trained with a UNIFORM preference distribution
#
# Every episode draws its preference uniformly from the 10-point sweep grid
#   w = [1.0,0.0] [0.9,0.1] ... [0.1,0.9]      (generate_pref_list(11); [0,1] excluded)
# i.e. P(w) = 1/10 each   (--n_cycle 0 in fheEnvUnified._sample_preference).
#
# Control = the base agent from train_unified_noise.sbatch (n_cycle=1: ~55% of
# episodes at [1,0]). Every other setting below is IDENTICAL to that script, so
# the preference distribution is the only thing that changes.
#
# Output model: RL/fhe_rl/trained_models/unified_noise_uniform.zip
#   (the name scripts/unified_morl_experiments.py expects for the 'uniform' agent)
#
# Submit from the repo root:   sbatch scripts/train_unified_uniform_pref.sbatch
# ════════════════════════════════════════════════════════════════════════════

#SBATCH -p compute
#SBATCH --mem 64GB
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 33
#SBATCH -t 7-00:00:00

#SBATCH --mail-user=${USER}@nyu.edu
#SBATCH --mail-type=BEGIN,END,FAIL

#SBATCH -o logs/output.unified_uniform_pref.%j.txt
#SBATCH -e logs/error.unified_uniform_pref.%j.txt
#SBATCH -J unified-uniform-pref

# Pre-timeout checkpointing signal 5 minutes before kill (train.py saves rl_model_emergency.zip)
#SBATCH --signal=B:TERM@300

set +u
if [ -f "/share/apps/NYUAD5/miniconda/3-4.11.0/bin/activate" ]; then
    source /share/apps/NYUAD5/miniconda/3-4.11.0/bin/activate
fi
conda activate /scratch/${USER}/conda/envs/chehabEnv 2>/dev/null \
    || conda activate /scratch/${NETID:-$(whoami)}/conda/envs/chehabEnv 2>/dev/null \
    || conda activate chehabEnv 2>/dev/null \
    || true
set -u

export PYTHONUNBUFFERED=1

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

mkdir -p "$PROJ_ROOT/logs" "$PROJ_ROOT/RL/eval" "$PROJ_ROOT/RL/checkpoints" "$PROJ_ROOT/RL/fhe_rl/trained_models"

cd "$PROJ_ROOT/RL"
export PYTHONPATH="$PROJ_ROOT/RL:$PROJ_ROOT/RL/pytrs:${PYTHONPATH:-}"

# ── Experiment settings (same as train_unified_noise.sbatch except N_CYCLE) ──
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
ROLLOUT_SIZE=16384
N_STEPS=$((ROLLOUT_SIZE / NUM_ENVS))
N_CYCLE=0          # 0 = uniform sampling over the preference grid (the experiment)
N_PREF=11          # 11 points -> 10 vectors [1.0,0.0] .. [0.1,0.9]
N_BUDGET=5
LAMBDA_ENV=0.0
LAMBDA_KL=0.0

JOB="${SLURM_JOB_ID:-local}"
RUN_NAME="model_${JOB}_${METHOD}_${VARIANT}_gnn"
FINAL_MODEL="$PROJ_ROOT/RL/fhe_rl/trained_models/unified_noise_uniform.zip"
TRAIN_LOG="$PROJ_ROOT/logs/train_unified_uniform_pref_${JOB}.log"

echo "════════════════════════════════════════════"
echo "  EXPERIMENT:      uniform preference distribution"
echo "  Preferences:     $((N_PREF - 1)) vectors, each p=1/$((N_PREF - 1)) (n_cycle=$N_CYCLE)"
echo "  Constraint:      $CONSTRAINT  budgets=$BUDGETS"
echo "  Method / Algo:   $METHOD / $ALGO"
echo "  Policy:          $ENCODING / $VARIANT / gnn"
echo "  Timesteps:       $TIMESTEPS  (eval every $EVAL_FREQ)"
echo "  Rollout:         $N_STEPS steps/env x $NUM_ENVS envs = $((N_STEPS * NUM_ENVS))"
echo "  Job ID:          $JOB"
echo "  Train log:       $TRAIN_LOG"
echo "  Final model:     $FINAL_MODEL"
echo "════════════════════════════════════════════"

# ── Preflight 1: keys cost must be non-zero (otherwise w has no effect) ─────
# ── Preflight 2: n_cycle=0 really samples the 10 grid points uniformly ─────
python - <<PY
import sys, numpy as np
import pytrs.config; pytrs.config.framework = "constrained"
from fhe_rl.env_unified import fheEnvUnified
from fhe_rl.pareto import generate_pref_list

ops, keys = fheEnvUnified.get_split_costs(None, "(VecAdd (<< (Vec a b c d) 1) (<< (Vec a b c d) 2))")
if keys == 0:
    sys.exit("[FAIL] C_keys == 0 for an expression with 2 rotations: preference vector has no effect. Fix before training.")
print(f"[ OK ] keys cost works (C_keys={keys})")

env = fheEnvUnified.__new__(fheEnvUnified)
env.n_cycle = $N_CYCLE
env.episode_count = 0
env.pref_list = [np.array(p, dtype=np.float32) for p in generate_pref_list($N_PREF)]
env.np_random = np.random.default_rng(0)
n = 20000
draws = [round(float(env._sample_preference()[0][0]), 1) for _ in range(n)]
vals, counts = np.unique(draws, return_counts=True)
freqs = counts / n
for v, f in zip(vals, freqs):
    print(f"       w_ops={v:.1f}  p={f:.3f}")
k = len(env.pref_list)
if len(vals) != k or np.max(np.abs(freqs - 1.0 / k)) > 0.02:
    sys.exit(f"[FAIL] sampling is not uniform over the {k} preference vectors")
print(f"[ OK ] uniform sampling over {k} preference vectors (expected p={1.0/k:.3f})")
PY

# ── Train ────────────────────────────────────────────────────────────────────
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
    --n_pref $N_PREF \
    --n_cycle $N_CYCLE \
    --n_budget $N_BUDGET \
    --lambda_env $LAMBDA_ENV \
    --lambda_kl $LAMBDA_KL \
    --fresh_start \
    "$@" \
    > "$TRAIN_LOG" 2>&1

# ── Publish the model under the experiment name ─────────────────────────────
if [ -f "$PROJ_ROOT/RL/${RUN_NAME}.zip" ]; then
    cp "$PROJ_ROOT/RL/${RUN_NAME}.zip" "$FINAL_MODEL"
    echo "[done] final model     -> $FINAL_MODEL"
else
    echo "[warn] ${RUN_NAME}.zip not found (training did not finish?). Latest checkpoints: $PROJ_ROOT/RL/checkpoints/${RUN_NAME}/"
fi
BEST="$PROJ_ROOT/RL/eval/best_model_${RUN_NAME}/best_model.zip"
if [ -f "$BEST" ]; then
    cp "$BEST" "${FINAL_MODEL%.zip}_best.zip"
    echo "[done] best eval model -> ${FINAL_MODEL%.zip}_best.zip"
fi
echo "TensorBoard: $PROJ_ROOT/RL/tensorboard/${RUN_NAME}"
