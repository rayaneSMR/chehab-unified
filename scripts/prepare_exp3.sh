#!/bin/bash
# Prepare Experiment 3 (uniform preference) for submission on Jubail.
# Usage (from the repo root):  bash scripts/prepare_exp3.sh [--submit]
set -euo pipefail

ENV_NAME="fhe_rl"
EMAIL="rs10728@nyu.edu"
SCRIPT="scripts/train_unified_uniform_pref.sbatch"

cd "$(dirname "${BASH_SOURCE[0]}")/.."
[ -f "$SCRIPT" ] || { echo "[FAIL] $SCRIPT not found (run from the chehab-unified repo)"; exit 1; }

mkdir -p logs
sed -i 's/\r$//' "$SCRIPT"
echo "[ OK ] logs/ ready, line endings fixed"

# ── find the conda env ───────────────────────────────────────────────────────
command -v conda >/dev/null || { echo "[FAIL] conda not on PATH (activate your base env first)"; exit 1; }
CONDA_BASE="$(conda info --base)"
ENV_PATH="$(conda env list | awk -v n="$ENV_NAME" '$1==n {print $NF}')"
[ -n "$ENV_PATH" ] && [ -x "$ENV_PATH/bin/python" ] \
    || { echo "[FAIL] conda env '$ENV_NAME' not found. conda env list:"; conda env list; exit 1; }
echo "[ OK ] conda base: $CONDA_BASE"
echo "[ OK ] env $ENV_NAME: $ENV_PATH"

# ── patch the sbatch file ────────────────────────────────────────────────────
CONDA_BASE="$CONDA_BASE" ENV_PATH="$ENV_PATH" EMAIL="$EMAIL" python3 - "$SCRIPT" <<'PY'
import os, re, sys
path = sys.argv[1]
s = open(path).read()
base, env, email = os.environ["CONDA_BASE"], os.environ["ENV_PATH"], os.environ["EMAIL"]

s = re.sub(r"^#SBATCH --mail-user=.*$", f"#SBATCH --mail-user={email}", s, count=1, flags=re.M)

block = (
    "set +u\n"
    f'CONDA_BASE="{base}"\n'
    f'CONDA_ENV="{env}"\n'
    'source "$CONDA_BASE/bin/activate" || { echo "[FAIL] cannot source $CONDA_BASE/bin/activate"; exit 1; }\n'
    'conda activate "$CONDA_ENV" || { echo "[FAIL] cannot activate conda env $CONDA_ENV"; exit 1; }\n'
    "set -u\n"
    'echo "Python: $(which python)"\n'
)
new, n = re.subn(r"^set \+u\n.*?^set -u\n(?:echo \"Python: .*\n)?", block, s, count=1, flags=re.M | re.S)
if n != 1:
    sys.exit("[FAIL] could not find the conda activation block (set +u ... set -u)")
open(path, "w").write(new)
print("[ OK ] activation block now uses", env)
PY

bash -n "$SCRIPT" && echo "[ OK ] $SCRIPT syntax check passed"
echo "──── activation + mail lines now in $SCRIPT ────"
grep -nE 'mail-user|CONDA_BASE=|CONDA_ENV=|conda activate|DATASET=|N_CYCLE=' "$SCRIPT"

# ── quick import check in the env (a few seconds, no training) ───────────────
cd RL
if PYTHONPATH="$PWD:$PWD/pytrs" "$ENV_PATH/bin/python" -c \
    "import torch, stable_baselines3, gymnasium; from fhe_rl.env_unified import fheEnvUnified" 2>/tmp/exp3_import_$$.err; then
    echo "[ OK ] env $ENV_NAME has torch, stable_baselines3, gymnasium and imports fhe_rl"
else
    echo "[FAIL] imports failed in $ENV_NAME:"; tail -5 /tmp/exp3_import_$$.err; rm -f /tmp/exp3_import_$$.err; exit 1
fi
rm -f /tmp/exp3_import_$$.err
cd ..

if [ "${1:-}" = "--submit" ]; then
    sbatch "$SCRIPT"
else
    echo; echo "Ready. Submit with:  sbatch $SCRIPT"
fi
