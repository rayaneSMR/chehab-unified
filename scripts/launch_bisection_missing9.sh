#!/bin/bash
# One bisection job per (budget, benchmark) of the 9 missing benchmarks.
#
#   bash scripts/launch_bisection_missing9.sh                       # budgets 236,369,9000000, lines 1-9
#   BUDGETS=9000000 LINES="8 9" bash scripts/launch_bisection_missing9.sh
#
# Budget 230 comes from job 19348949 (it saves after each benchmark).
# Then: python scripts/merge_bisection_parts.py
set -euo pipefail
cd "$(dirname "$0")/.."
BUDGETS="${BUDGETS:-236,369,9000000}"
LINES="${LINES:-1 2 3 4 5 6 7 8 9}"
mkdir -p logs
for b in ${BUDGETS//,/ }; do
    for l in $LINES; do
        id=$(sbatch --parsable -J "bis-b${b}-L${l}" scripts/run_bisection_one.sbatch "$b" "$l")
        echo "budget $b  line $l  -> job $id"
    done
done
