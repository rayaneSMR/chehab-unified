#!/bin/bash
# One benchmark of the threshold dataset, evaluated with the original CHEHAB RL agent.
#
#   sbatch scripts/eval_original_threshold_one.sbatch INDEX OUT_DIR [BUDGETS]
#     INDEX    0-based line index in RL/fhe_rl/datasets/threshold_benchmarks.txt
#     OUT_DIR  output folder (absolute path)
#     BUDGETS  optional, space-separated noise budgets (default: "230 236 369")
#
# Usually submitted by scripts/launch_original_threshold_eval.sh (one job per benchmark).
# Output: OUT_DIR/original_thr_<INDEX>.csv

#SBATCH -p compute
#SBATCH --mem 16GB
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 2
#SBATCH -t 06:00:00
#SBATCH -o logs/output.orig_thr.%j.txt
#SBATCH -e logs/error.orig_thr.%j.txt
#SBATCH -J orig-thr

set +u
if [ -f "/share/apps/NYUAD5/miniconda/3-4.11.0/bin/activate" ]; then
    source /share/apps/NYUAD5/miniconda/3-4.11.0/bin/activate
fi
conda activate /scratch/${USER}/conda/envs/chehabEnv 2>/dev/null \
    || conda activate chehabEnv 2>/dev/null \
    || true
set -u
export PYTHONUNBUFFERED=1

INDEX="${1:?usage: sbatch eval_original_threshold_one.sbatch INDEX OUT_DIR [BUDGETS]}"
OUT_DIR="${2:?missing OUT_DIR}"
BUDGETS="${3:-230 236 369}"

if [ -n "${SLURM_SUBMIT_DIR:-}" ]; then
    PROJ_ROOT="$SLURM_SUBMIT_DIR"
else
    PROJ_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi
cd "$PROJ_ROOT/RL"
export PYTHONPATH="$PROJ_ROOT/RL:$PROJ_ROOT/RL/pytrs:${PYTHONPATH:-}"
mkdir -p "$OUT_DIR"

echo "Benchmark index $INDEX | budgets: $BUDGETS | out: $OUT_DIR"
# shellcheck disable=SC2086
python -u "$PROJ_ROOT/scripts/eval_original_agent_metrics.py" \
    --benchmarks fhe_rl/datasets/threshold_benchmarks.txt \
    --indices "$INDEX" \
    --budgets $BUDGETS \
    --out "$OUT_DIR/original_thr_${INDEX}.csv"
