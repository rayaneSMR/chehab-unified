#!/bin/bash
#SBATCH --job-name=heongpu_totalmem
#SBATCH --gres=gpu:a100:1
#SBATCH --exclusive              # device-wide measurement: no other job may touch this GPU
#SBATCH --cpus-per-task=8
#SBATCH --time=06:00:00
#SBATCH --output=totalmem_%j.log
##SBATCH --partition=<your A100 partition>

# ---- edit these -------------------------------------------------------------
MANIFEST=${MANIFEST:-manifest.csv}            # id,binary[,args]  (compiled generated_fhe.cu per circuit)
REFS=${REFS:-"set400_repacked_fix.csv negate_compare.csv"}
POOL_REGEX=${POOL_REGEX:-}                    # optional, e.g. 'pool_peak_MiB=([0-9.]+)'
REPS=${REPS:-3}
# module load cuda python   # <- whatever Jubail uses
# -----------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")"
python - <<'EOF' || pip install --user nvidia-ml-py
import pynvml
EOF
nvidia-smi --query-gpu=name,memory.total,memory.used,driver_version --format=csv
nvcc --version | tail -n 2

# 1) bare CUDA probe -> context cost
nvcc -O2 -arch=sm_80 ctx_probe.cu -o ctx_probe
{ [ -f manifest_probe.csv ] && rm manifest_probe.csv; } || true
echo "id,binary" > manifest_probe.csv
for i in 1 2 3; do echo "ctx_probe_$i,$PWD/ctx_probe" >> manifest_probe.csv; done
python run_total_mem.py --manifest manifest_probe.csv --out totals_probe.csv --reps 3

# 2) the circuits
REFARGS=""; for r in $REFS; do REFARGS="$REFARGS --ref $r"; done
RX=""; [ -n "$POOL_REGEX" ] && RX="--pool-regex $POOL_REGEX"
python run_total_mem.py --manifest "$MANIFEST" $REFARGS $RX --reps "$REPS" --out totals_circuits.csv

# 3) fit + compare (CPU-only, fast)
python fit_gpu_full.py --circuits totals_circuits.csv --probe totals_probe.csv --out memory_calib_gpu_full.json
echo "DONE: send back totals_circuits.csv totals_probe.csv memory_calib_gpu_full.json fit_report.txt"
