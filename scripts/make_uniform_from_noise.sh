#!/bin/bash
# Build scripts/train_unified_uniform_pref.sbatch from the CURRENT scripts/train_unified_noise.sbatch:
# same training config, only changes = uniform preferences (--n_cycle 0 --n_pref 11),
# job/log names, email, and the fhe_rl conda env.
# Usage (repo root):  bash scripts/make_uniform_from_noise.sh [--submit]
set -euo pipefail

ENV_NAME="fhe_rl"
EMAIL="rs10728@nyu.edu"
SRC="scripts/train_unified_noise.sbatch"
DST="scripts/train_unified_uniform_pref.sbatch"

cd "$(dirname "${BASH_SOURCE[0]}")/.."
[ -f "$SRC" ] || { echo "[FAIL] $SRC not found"; exit 1; }
mkdir -p logs

command -v conda >/dev/null || { echo "[FAIL] conda not on PATH"; exit 1; }
CONDA_BASE="$(conda info --base)"
ENV_PATH="$(conda env list | awk -v n="$ENV_NAME" '$1==n {print $NF}')"
[ -n "$ENV_PATH" ] && [ -x "$ENV_PATH/bin/python" ] || { echo "[FAIL] conda env '$ENV_NAME' not found"; exit 1; }

CONDA_BASE="$CONDA_BASE" ENV_PATH="$ENV_PATH" EMAIL="$EMAIL" python3 - "$SRC" "$DST" <<'PY'
import os, re, sys
src, dst = sys.argv[1], sys.argv[2]
s = open(src).read().replace("\r\n", "\n")
base, env, email = os.environ["CONDA_BASE"], os.environ["ENV_PATH"], os.environ["EMAIL"]

def sub1(pattern, repl, text, what, flags=re.M):
    new, n = re.subn(pattern, repl, text, count=1, flags=flags)
    if n != 1:
        sys.exit(f"[FAIL] could not patch: {what}")
    return new

# names: job, slurm logs, training log
s = re.sub(r"unified_noise", "unified_uniform_pref", s)
s = re.sub(r"^#SBATCH -J .*$", "#SBATCH -J unified-uniform-pref", s, count=1, flags=re.M)
s = re.sub(r"^#SBATCH --mail-user=.*$", f"#SBATCH --mail-user={email}", s, count=1, flags=re.M)

# conda activation -> fhe_rl, fail loudly if it does not activate
block = (
    "set +u\n"
    f'CONDA_BASE="{base}"\n'
    f'CONDA_ENV="{env}"\n'
    'source "$CONDA_BASE/bin/activate" || { echo "[FAIL] cannot source $CONDA_BASE/bin/activate"; exit 1; }\n'
    'conda activate "$CONDA_ENV" || { echo "[FAIL] cannot activate conda env $CONDA_ENV"; exit 1; }\n'
    "set -u\n"
    'echo "Python: $(which python)"\n'
)
s = sub1(r"^set \+u\n.*?^set -u\n", block, s, "conda activation block (set +u ... set -u)", re.M | re.S)

# the experiment: uniform sampling over the 10 preference vectors
for flag, val in (("--n_cycle", "0"), ("--n_pref", "11")):
    if re.search(rf"{flag}\s+\S+", s):
        s = re.sub(rf"{flag}\s+\S+", f"{flag} {val}", s)
    else:
        anchor = r"^(\s*)--fresh_start \\\n" if re.search(r"^\s*--fresh_start \\$", s, re.M) else r'^(\s*)"\$@" \\\n'
        s = sub1(anchor, lambda m: f"{m.group(1)}{flag} {val} \\\n{m.group(0)}", s, f"insert {flag}")

s = s.replace('echo "════════════════════════════════════════════"\necho "  Framework:',
              'echo "════════════════════════════════════════════"\necho "  EXPERIMENT:      uniform preferences (n_cycle=0, 10 vectors, p=1/10)"\necho "  Framework:', 1)

s += '''
# ── publish the trained model under the experiment name ──
RUN_MODEL="$(ls -t "$PROJ_ROOT"/RL/model_${SLURM_JOB_ID:-jobid}_*.zip 2>/dev/null | head -1 || true)"
mkdir -p "$PROJ_ROOT/RL/fhe_rl/trained_models"
if [ -n "$RUN_MODEL" ]; then
    cp "$RUN_MODEL" "$PROJ_ROOT/RL/fhe_rl/trained_models/unified_noise_uniform.zip"
    echo "[done] $RUN_MODEL -> RL/fhe_rl/trained_models/unified_noise_uniform.zip"
else
    echo "[warn] no final model found (training did not finish?); see RL/checkpoints/"
fi
'''
open(dst, "w").write(s)
PY

bash -n "$DST"
echo "[ OK ] wrote $DST from $SRC"
echo "──── differences vs $SRC (should be only names, email, conda env, n_cycle/n_pref, model copy) ────"
diff <(tr -d '\r' < "$SRC") "$DST" || true

if [ "${1:-}" = "--submit" ]; then
    sbatch "$DST"
else
    echo; echo "Submit with:  sbatch $DST"
fi
