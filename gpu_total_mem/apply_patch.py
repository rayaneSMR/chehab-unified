#!/usr/bin/env python3
"""
Wire the extended targets into RL/fhe_rl/memory.py (idempotent, keeps memory.py.bak).
Usage:  python apply_patch.py /path/to/chehab-unified/RL/fhe_rl
Result: PEAK_RAM_GPU_TARGET=pool|device|host (default pool = behaviour unchanged).
"""
import os, shutil, sys

d = sys.argv[1] if len(sys.argv) > 1 else "RL/fhe_rl"
mem = os.path.join(d, "memory.py")
src = open(mem).read()
if "GPU_TARGET" in src:
    print("already patched"); sys.exit(0)
shutil.copy(mem, mem + ".bak")
shutil.copy(os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory_gpu_full.py"),
            os.path.join(d, "memory_gpu_full.py"))

def rep(old, new):
    global src
    assert src.count(old) == 1, f"anchor not found exactly once: {old[:60]!r}"
    src = src.replace(old, new)

rep('ESTIMATOR_VERSION = "calib-v3-packed" if BACKEND == "cpu" else "gpu-v1-packfix"',
    'GPU_TARGET = os.environ.get("PEAK_RAM_GPU_TARGET", "pool").strip().lower()\n'
    'if GPU_TARGET not in ("pool", "device", "host"):\n'
    '    raise ValueError(f"PEAK_RAM_GPU_TARGET must be pool, device or host, got {GPU_TARGET!r}")\n'
    'ESTIMATOR_VERSION = "calib-v3-packed" if BACKEND == "cpu" else "gpu-v1-packfix"\n'
    'if BACKEND == "gpu" and GPU_TARGET != "pool":\n'
    '    ESTIMATOR_VERSION += "-" + GPU_TARGET')
rep('def group_of(N):',
    'def _gpu_target_mb(raw_total_mb, margin):\n'
    '    """GPU estimate for the selected target (pool = historical behaviour)."""\n'
    '    if GPU_TARGET == "pool":\n'
    '        return raw_total_mb * _gpu_mult(margin)\n'
    '    try:\n'
    '        from . import memory_gpu_full as _full\n'
    '    except ImportError:\n'
    '        import memory_gpu_full as _full\n'
    '    return _full.predict(raw_total_mb, GPU_TARGET, margin)\n\n\n'
    'def group_of(N):')
rep('        return sum(t.values()) / MB * _gpu_mult(margin)',
    '        return _gpu_target_mb(sum(t.values()) / MB, margin)')
rep('        mult = _gpu_mult(margin)\n        return dict(mb=est.total_mb * mult, clamped=False,',
    '        return dict(mb=_gpu_target_mb(est.total_mb, margin), clamped=False,')
open(mem, "w").write(src)
print("patched", mem, "(backup: memory.py.bak); copied memory_gpu_full.py")
