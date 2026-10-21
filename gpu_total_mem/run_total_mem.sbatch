#!/bin/bash
#SBATCH -p condo
#SBATCH -q c2
#SBATCH --gres=gpu:a100:1
#SBATCH -c 4
#SBATCH --mem=16G
#SBATCH -t 02:00:00
#SBATCH -J totalmem
#SBATCH -o /scratch/rs10728/heongpu-project/logs/%x.%j.out
set -uo pipefail
module purge
module load gcc/11.5.0 cuda/12.2.0
export GMP_ROOT=/share/apps/NYUAD5/spack/0.16.2/opt/spack/linux-centos8-zen2/gcc-9.2.0/gmp-6.1.2-um4b3iiuzr3erc4d75ak5pv5islj2kjj
export LD_LIBRARY_PATH=$HOME/local/heongpu/lib64:$HOME/local/heongpu/lib:$GMP_ROOT/lib:${LD_LIBRARY_PATH:-}
PY=/home/rs10728/.conda/envs/fhe_rl/bin/python
cd /scratch/rs10728/heongpu-project/src/chehab-unified/gpu_total_mem
REPS=${REPS:-3}; LIMIT=${LIMIT:-0}
POOL_REGEX='peak_gpu_memory_\(MB\): ([0-9.]+)'
echo "host: $(hostname) start: $(date)"
nvidia-smi -L
nvidia-smi --query-gpu=name,memory.used,memory.total,driver_version --format=csv
GPUIDX=0
if [ "$(nvidia-smi -L | wc -l)" -gt 1 ] && [[ "${CUDA_VISIBLE_DEVICES:-}" =~ ^[0-9]+$ ]]; then GPUIDX=$CUDA_VISIBLE_DEVICES; fi
echo "using NVML gpu index $GPUIDX"
nvcc --version | tail -n 2
nvcc -O2 -arch=sm_80 ctx_probe.cu -o ctx_probe || exit 1
echo "id,binary" > manifest_probe.csv
for i in 1 2 3; do echo "ctx_probe_$i,$PWD/ctx_probe" >> manifest_probe.csv; done
$PY run_total_mem.py --manifest manifest_probe.csv --out totals_probe.csv --reps 3 --gpu-index $GPUIDX
$PY run_total_mem.py --manifest manifest.csv --ref set400_repacked_fix.csv --ref negate_compare.csv \
    --pool-regex "$POOL_REGEX" --reps $REPS --limit $LIMIT --gpu-index $GPUIDX --out totals_circuits.csv
if [ "$LIMIT" = "0" ]; then
  $PY fit_gpu_full.py --circuits totals_circuits.csv --probe totals_probe.csv --out memory_calib_gpu_full.json
  echo "DONE: send back totals_circuits.csv totals_probe.csv memory_calib_gpu_full.json fit_report.txt"
else
  echo "SMOKE TEST DONE (fit skipped)"; head -5 totals_circuits.csv; cat totals_probe.csv | head -5
fi
