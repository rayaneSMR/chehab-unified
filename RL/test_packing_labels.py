"""Regression: packing label counts + CPU/GPU backend switch.  Run: cd RL && python test_packing_labels.py"""
import importlib, os, sys
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "fhe_rl")); sys.path.insert(0, os.path.join(_HERE, "pytrs"))
import packing  # noqa: E402

NESTED = "(Vec (* a (+ b c)) (* d (+ e f)))"
FLAT = "(Vec (* a b) (* c d))"
UNARY = "(Vec (- a) (- b))"

def test_fixed_label_count_nested():
    ir, n_c, _, _ = packing.pack(NESTED, fix_labels=True)
    assert n_c == 3 and ir == "( * c0 ( + c1 c2 ) )", (ir, n_c)

def test_fixed_label_count_flat_and_unary():
    assert packing.pack(FLAT, fix_labels=True)[1] == 2
    assert packing.pack(UNARY, fix_labels=True)[1] == 1

def test_legacy_default_unchanged():
    assert packing.pack(NESTED)[1] == 2
    assert packing.pack(NESTED) == packing.pack(NESTED, fix_labels=False)

def _reload_memory(backend):
    old = os.environ.get("PEAK_RAM_BACKEND"); os.environ["PEAK_RAM_BACKEND"] = backend
    try:
        sys.modules.pop("memory", None); return importlib.import_module("memory")
    finally:
        os.environ.pop("PEAK_RAM_BACKEND", None) if old is None else os.environ.__setitem__("PEAK_RAM_BACKEND", old)

def test_backend_switch_uses_matching_packing():
    cpu, gpu = _reload_memory("cpu"), _reload_memory("gpu")
    assert cpu.BACKEND == "cpu" and gpu.BACKEND == "gpu"
    assert cpu._pack(NESTED) == packing.pack_expr_str(NESTED, fix_labels=False)
    assert gpu._pack(NESTED) == packing.pack_expr_str(NESTED, fix_labels=True)
    assert gpu.peak_ram_breakdown(NESTED, margin=False)["mb"] > 0

if __name__ == "__main__":
    for n, f in sorted(globals().items()):
        if n.startswith("test_"): f(); print("ok", n)
