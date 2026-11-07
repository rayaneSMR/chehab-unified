#!/bin/bash
# ════════════════════════════════════════════════════════════════════════════
# 10-preference ablation agents — REAL compile + SEAL execution (measured exec time, rotation-key size)
#
# Same protocol as e2e_4pref.sh and as the evaluation of the unified agent (e2e_ALL):
#   scripts/eval_unified_e2e.sbatch -> run_benchmarks_unified.py, every C++ benchmark of the MORL
#   suite, the generated SEAL program built and run 3 times (median), outputs checked.
# Here: the 5 ten-preference agents (unconstrained v4_mb v4_nmask v4_mb_film v5_focops), their
# constraint method, with or without rollback, at the 4 preferences of the 4-pref agents
# w = [1.0,0.0] [0.9,0.1] [0.8,0.2] [0.6,0.4] (same points as e2e_4pref.sh, directly comparable).
# PREFERENCES=all evaluates the 10 training preferences instead (output in e2e_10pref_allprefs/).
#
# Model: each run's CURRENT best eval checkpoint, so it can start while training is still running.
# RL/eval/best_model_model_<jobid>_*_abl_<agent>/best_model.zip is frozen once into
# results/ablation_unified/e2e_10pref/models/<agent>.zip (training keeps overwriting the original);
# both modes then use the same frozen copy. Provenance (source, time, step, score): models/models.csv
#
#   bash scripts/ablation_unified/e2e_10pref.sh <agent|all> [ROLLBACK] [BUDGETS]
#     agent     unconstrained v4_mb v4_nmask v4_mb_film v5_focops, or all
#     ROLLBACK  1 (default) = safety rollback (Experiment 3), 0 = raw agent output (Experiment 2)
#     BUDGETS   default "230 236 369 9000000"
#   both modes for every agent:
#     bash scripts/ablation_unified/e2e_10pref.sh all 1 && bash scripts/ablation_unified/e2e_10pref.sh all 0
#   DRY_RUN=1 ... prints what it would freeze and submit
#   MODEL_SOURCE=final ... uses trained_models/unified_noise_abl_<agent>[_best].zip instead
#                          (after training), output in e2e_10pref_final/
#
# One Slurm job per budget x benchmark (13 benchmarks x 4 budgets = 52 jobs per agent and mode).
# Output: results/ablation_unified/e2e_10pref/<rollback|no_rollback>/<agent>/e2e_<bench>_b<budget>_<job>.csv
# Needs: build/ with all benchmarks (sbatch scripts/build_chehab_benchmarks.sbatch) and SEAL 4.1
# ════════════════════════════════════════════════════════════════════════════
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
PROJ_ROOT="$PWD"
mkdir -p logs

AGENT="${1:?usage: bash scripts/ablation_unified/e2e_10pref.sh <agent|all> [ROLLBACK] [BUDGETS]}"
ROLLBACK="${2:-1}"
BUDGETS="${3:-230 236 369 9000000}"
# default: the 4 preferences of e2e_4pref.sh; PREFERENCES=all -> the 10 training preferences
PREFERENCES="${PREFERENCES:-1.0,0.0;0.9,0.1;0.8,0.2;0.6,0.4}"
SUFFIX=""
if [ "$PREFERENCES" = "all" ]; then PREFERENCES=""; SUFFIX="_allprefs"; fi
CONDA_ENV="${CONDA_ENV:-/home/rs10728/.conda/envs/fhe_rl}"   # same env as the training / eval scripts
BENCHES=(box_blur gx_kernel gy_kernel roberts_cross matrix_mul dot_product hamming_dist
         l2_distance lin_reg poly_reg max sort polynomials_coyote)
case "$ROLLBACK" in 1) MODE=rollback ;; 0) MODE=no_rollback ;; *) echo "[FAIL] ROLLBACK must be 1 or 0"; exit 1 ;; esac
DRY="${DRY_RUN:-0}"

if [ "${MODEL_SOURCE:-best_now}" = "final" ]; then ROOT="results/ablation_unified/e2e_10pref_final$SUFFIX"
else ROOT="results/ablation_unified/e2e_10pref$SUFFIX"; fi
SNAP="$ROOT/models"

method_of() {
    case "$1" in
        unconstrained) echo none ;;
        v4_mb|v4_mb_film) echo margin_barrier ;;
        v4_nmask) echo noise_masking ;;
        v5_focops) echo nato_sc ;;
        *) return 1 ;;
    esac
}

if [ "$AGENT" = "all" ]; then
    AGENTS="unconstrained v4_mb v4_nmask v4_mb_film v5_focops"
else
    method_of "$AGENT" > /dev/null || { echo "[FAIL] unknown agent '$AGENT'"; exit 1; }
    AGENTS="$AGENT"
fi

for b in "${BENCHES[@]}"; do
    [ -x "build/benchmarks/$b/$b" ] || { echo "[FAIL] build/benchmarks/$b/$b missing (sbatch scripts/build_chehab_benchmarks.sbatch)"; exit 1; }
done

# model for agent $1 -> prints its path (freezing the current best checkpoint the first time)
model_for() {
    local a="$1" src dst="$PROJ_ROOT/$SNAP/$1.zip"
    if [ "${MODEL_SOURCE:-best_now}" = "final" ]; then
        local t="$PROJ_ROOT/RL/fhe_rl/trained_models/unified_noise_abl_${a}"
        if [ -f "${t}_best.zip" ]; then echo "${t}_best.zip"; elif [ -f "${t}.zip" ]; then echo "${t}.zip"; fi
        return 0
    fi
    if [ -f "$dst" ]; then echo "$dst"; return 0; fi
    src="$(ls -td RL/eval/best_model_model_*_abl_${a}/ 2>/dev/null | head -n 1 || true)"
    src="${src%/}/best_model.zip"
    [ -f "$src" ] || return 0
    local log step="" score=""
    log="$(ls -t results/ablation_unified/${a}/train_*.log 2>/dev/null | head -n 1 || true)"
    if [ -n "$log" ]; then
        step="$(grep -B 30 "New Best" "$log" | grep -oE "Step [0-9,]+" | tail -n 1 | tr -d 'Step ,' || true)"
        score="$(grep "New Best" "$log" | tail -n 1 | grep -oE "[0-9]+\.[0-9]+" || true)"
    fi
    echo "   freeze $a: $src (saved $(date -r "$src" '+%Y-%m-%d %H:%M'), step ${step:-?}, score ${score:-?})" >&2
    if [ "$DRY" = "1" ]; then echo "$src"; return 0; fi
    mkdir -p "$PROJ_ROOT/$SNAP"
    [ -f "$PROJ_ROOT/$SNAP/models.csv" ] || echo "agent,source,saved_at,best_step,best_score" > "$PROJ_ROOT/$SNAP/models.csv"
    cp "$src" "$dst"
    echo "$a,$src,$(date -r "$src" '+%Y-%m-%d %H:%M'),$step,$score" >> "$PROJ_ROOT/$SNAP/models.csv"
    echo "$dst"
}

for a in $AGENTS; do
    MODEL="$(model_for "$a")"
    [ -n "$MODEL" ] || { echo "[skip] $a: no model found"; continue; }
    METHOD="$(method_of "$a")"
    OUT_DIR="$ROOT/$MODE/$a"
    [ "$DRY" = "1" ] || { mkdir -p "$OUT_DIR"; echo "$MODEL" > "$OUT_DIR/model.txt"; }
    echo "== $a  method=$METHOD  mode=$MODE  prefs=${PREFERENCES:-10 training}  model=$MODEL  -> $OUT_DIR/"
    for budget in $BUDGETS; do
        for bench in "${BENCHES[@]}"; do
            if [ "$DRY" = "1" ]; then
                echo "   [dry-run] sbatch e2e10-${a}-${MODE}-${bench}-${budget}"; continue
            fi
            jid=$(sbatch --parsable -J "e2e10-${a}-${MODE}-${bench}-${budget}" \
                --export=ALL,METHOD="$METHOD",ROLLBACK="$ROLLBACK",OUT_DIR="$OUT_DIR",CONDA_ENV="$CONDA_ENV" \
                scripts/eval_unified_e2e.sbatch "$budget" "$MODEL" "$bench" "$PREFERENCES")
            echo "   $jid  $bench  B=$budget"
        done
    done
done
echo "Monitor: squeue -u \$USER    logs: logs/output.e2e.<jobid>.txt"
