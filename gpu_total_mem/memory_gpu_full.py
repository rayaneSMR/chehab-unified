"""
Extended HEonGPU memory targets for the peak-memory estimator.

Target (env PEAK_RAM_GPU_TARGET, read in memory.py):
  pool   (default) HEonGPU device-pool peak            = est * scale * margin          (unchanged)
  device           device-wide GPU peak (pool + CUDA context + driver + non-pool allocations)
                   = (a + b*est) * margin             fitted by fit_gpu_full.py
  host             process peak host RSS, comparable with the Lattigo target
                   = (a + b*est) * margin             fitted by fit_gpu_full.py

est is the raw estimator total in MB (before scale/margin). Calibration file:
memory_calib_gpu_full.json (override with PEAK_RAM_GPU_FULL_CALIB).
"""
import json, os

_HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.environ.get("PEAK_RAM_GPU_FULL_CALIB", os.path.join(_HERE, "memory_calib_gpu_full.json"))
TARGETS = ("pool", "device", "host")
_c = None


def load():
    global _c
    if _c is None:
        if not os.path.exists(PATH):
            raise FileNotFoundError(f"{PATH} not found: run fit_gpu_full.py on the HPC measurements first "
                                    f"(or set PEAK_RAM_GPU_FULL_CALIB).")
        _c = json.load(open(PATH))
    return _c


def predict(est_mb, target, margin=True):
    """est_mb: raw estimator total (MB). Returns MiB-like MB for the chosen target."""
    c = load()[target]
    v = c["a"] + c["b"] * est_mb
    return v * (c["margin"] if margin else 1.0)
