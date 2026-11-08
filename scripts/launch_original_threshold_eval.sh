#!/bin/bash
# Master launcher: evaluates the original CHEHAB RL agent on the threshold dataset,
# one Slurm job per benchmark (all in parallel), then merges the results.
#
#   bash scripts/launch_original_threshold_eval.sh [BUDGETS]
#     BUDGETS  optional, space-separated noise budgets (default: "230 236 369")
#
# Run from the repository root. Output:
#   RL/test_results/original_agent_threshold_<date>/original_thr_<index>.csv   (one per benchmark)
#   RL/test_results/original_agent_threshold_<date>/original_threshold_ALL.xlsx (merged)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJ_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJ_ROOT"

BUDGETS="${1:-230 236 369}"
BENCH="RL/fhe_rl/datasets/threshold_benchmarks.txt"
OUT_DIR="$PROJ_ROOT/RL/test_results/original_agent_threshold_$(date +%Y-%m-%d)"
N=$(grep -c ':' "$BENCH")

mkdir -p logs "$OUT_DIR"
echo "════════════════════════════════════════════════════════════"
echo "  Original CHEHAB RL on the threshold dataset"
echo "  Benchmarks: $N | Budgets: $BUDGETS"
echo "  Output:     $OUT_DIR"
echo "════════════════════════════════════════════════════════════"

JOBS=()
for ((i = 0; i < N; i++)); do
    JID=$(sbatch --parsable -J "orig-thr-$i" \
        scripts/eval_original_threshold_one.sbatch "$i" "$OUT_DIR" "$BUDGETS")
    JOBS+=("$JID")
    echo "  [$((i + 1))/$N] benchmark $i -> job $JID"
done

# Merge once every benchmark job has ended (afterany: also merges if some failed;
# the 'missing' sheet lists them).
DEPS=$(IFS=:; echo "${JOBS[*]}")
MERGE=$(sbatch --parsable -J orig-thr-merge -p compute -c 1 --mem 4GB -t 00:30:00 \
    -o logs/output.orig_thr_merge.%j.txt -e logs/error.orig_thr_merge.%j.txt \
    --dependency=afterany:"$DEPS" \
    --wrap="set +u; source /share/apps/NYUAD5/miniconda/3-4.11.0/bin/activate 2>/dev/null; \
conda activate /scratch/\$USER/conda/envs/chehabEnv 2>/dev/null || conda activate chehabEnv 2>/dev/null; \
python $PROJ_ROOT/scripts/merge_original_threshold.py $OUT_DIR $N")

echo ""
echo "  $N benchmark jobs submitted; merge job: $MERGE (runs after all of them)"
echo "  Monitor:  squeue -u \$USER"
echo "  Result:   $OUT_DIR/original_threshold_ALL.xlsx"
echo "  Re-merge by hand: python scripts/merge_original_threshold.py $OUT_DIR $N"
