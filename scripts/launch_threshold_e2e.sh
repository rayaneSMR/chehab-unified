#!/bin/bash
# Real compile + SEAL execution of the near-threshold dataset (60 programs of
# RL/fhe_rl/datasets/threshold_benchmarks.txt: lines 1-20 for B = 230, 21-40 for B = 236,
# 41-60 for B = 369), to measure the circuit execution time of the programs of the
# near-threshold table. Same protocol as the end-to-end evaluation of the 46 benchmarks
# (scripts/run_benchmarks_unified.py); the program is compiled by benchmarks/threshold_expr
# and the agent gets the dataset expression itself.
#
# Run from the root of the evaluation clone, after `bash scripts/build_e2e_benchmarks.sh`:
#   bash scripts/launch_threshold_e2e.sh MODEL [PREFERENCE]
#     MODEL       trained joint model .zip (absolute path), e.g.
#                 RL/fhe_rl/trained_models/unified_joint_noise_19038296_best_4.6M.zip
#     PREFERENCE  optional "w_ops,w_keys" (default 0.9,0.1)
#
# 9 jobs, 3 per group of 20 programs (as threshold_w0.9_2026-11-08):
#   cmorl          agent at the program's budget B, rollback at B
#   unconstrained  agent at budget 9000000, rollback still at B (AGENT_BUDGET=9000000)
#   input          no agent: the input program (baseline of the reductions)
# Optional 4th kind, not submitted by default (ONLY=unconstrained_norollback):
#   unconstrained_norollback   agent at budget 9000000, NO rollback: its final program
# The SEAL bound still applies to every compiled program (the input is compiled if it fails).
# Afterwards: python scripts/threshold_e2e_summary.py <OUT_DIR>
#   (no-rollback variant: add --unconstrained-dir unconstrained_norollback)
#
# Optional environment:
#   ONLY=unconstrained         submit only these kinds (comma-separated:
#                              cmorl,unconstrained,input,unconstrained_norollback)
#   OUT_ROOT=<dir>             results folder (default RL/test_results/threshold_e2e_<today>)

set -eo pipefail
MODEL="${1:?usage: bash scripts/launch_threshold_e2e.sh MODEL [PREFERENCE]}"
PREF="${2:-0.9,0.1}"
ONLY=",${ONLY:-cmorl,unconstrained,input},"

PROJ_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJ_ROOT"
mkdir -p logs
[ -f "$MODEL" ] || { echo "ERROR: model not found: $MODEL"; exit 1; }
MODEL="$(cd "$(dirname "$MODEL")" && pwd)/$(basename "$MODEL")"
[ -x build/benchmarks/threshold_expr/threshold_expr ] || { echo "ERROR: run 'bash scripts/build_e2e_benchmarks.sh' first"; exit 1; }

OUT_ROOT="${OUT_ROOT:-RL/test_results/threshold_e2e_$(date +%Y-%m-%d)}"
for kind in cmorl unconstrained input unconstrained_norollback; do
    [[ "$ONLY" == *,$kind,* ]] && mkdir -p "$OUT_ROOT/$kind"
done

declare -A LINES_OF=([230]="1-20" [236]="21-40" [369]="41-60")
for B in 230 236 369; do
    L="${LINES_OF[$B]}"
    # Job settings go through the environment of sbatch (--export=ALL copies it into the job)
    if [[ "$ONLY" == *,cmorl,* ]]; then
    jid=$(LINES="$L" METHOD=nato_sc ROLLBACK=1 AGENT_BUDGET= PASSTHROUGH=0 OUT_DIR="$OUT_ROOT/cmorl" \
        sbatch --parsable --export=ALL -J "thr-cmorl-$B" \
        scripts/eval_unified_e2e.sbatch "$B" "$MODEL" threshold "$PREF")
    echo "  submitted $jid   cmorl          lines $L   B=$B"
    fi
    if [[ "$ONLY" == *,unconstrained,* ]]; then
    jid=$(LINES="$L" METHOD=nato_sc ROLLBACK=1 AGENT_BUDGET=9000000 PASSTHROUGH=0 OUT_DIR="$OUT_ROOT/unconstrained" \
        sbatch --parsable --export=ALL -J "thr-unc-$B" \
        scripts/eval_unified_e2e.sbatch "$B" "$MODEL" threshold "$PREF")
    echo "  submitted $jid   unconstrained  lines $L   (agent budget 9000000, rollback at B=$B)"
    fi
    if [[ "$ONLY" == *,unconstrained_norollback,* ]]; then
    jid=$(LINES="$L" METHOD=nato_sc ROLLBACK=0 AGENT_BUDGET=9000000 PASSTHROUGH=0 OUT_DIR="$OUT_ROOT/unconstrained_norollback" \
        sbatch --parsable --export=ALL -J "thr-uncNR-$B" \
        scripts/eval_unified_e2e.sbatch "$B" "$MODEL" threshold "$PREF")
    echo "  submitted $jid   unconstrained, NO rollback   lines $L   (agent budget 9000000, B=$B)"
    fi
    if [[ "$ONLY" == *,input,* ]]; then
    jid=$(LINES="$L" METHOD=nato_sc ROLLBACK=1 AGENT_BUDGET= PASSTHROUGH=1 OUT_DIR="$OUT_ROOT/input" \
        sbatch --parsable --export=ALL -J "thr-input-$B" \
        scripts/eval_unified_e2e.sbatch "$B" "$MODEL" threshold "$PREF")
    echo "  submitted $jid   input          lines $L"
    fi
done
echo ""
echo "Check:   squeue -u \$USER"
echo "Logs:    logs/output.e2e.<jobid>.txt"
echo "Results: $OUT_ROOT/{cmorl,unconstrained,input}/e2e_threshold_L*_<jobid>.csv"
echo "Summary: python scripts/threshold_e2e_summary.py $OUT_ROOT"
