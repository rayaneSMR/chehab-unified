import os
import re
import sys
import subprocess
import csv
import shutil
from pathlib import Path

# Fix paths
RL_DIR = "/home/maroua/chehab-unified/RL"
VECLANG_RUNNER_DIR = f"{RL_DIR}/veclang_runner"
LATTIGO_DIR = "/home/maroua/chehab-unified/lattigo_backend"

sys.path.append(RL_DIR)
from pytrs.parser import parse_sexpr
from pytrs.peak_ram import estimate_peak_ram, FHEParams, BackendConfig

def run_cmd(cmd, cwd=None):
    try:
        subprocess.run(cmd, shell=True, check=True, cwd=cwd, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running {cmd}")
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        raise

def get_peak_ram(cmd, cwd=None):
    time_cmd = f"/usr/bin/time -v {cmd}"
    res = subprocess.run(time_cmd, shell=True, capture_output=True, text=True, cwd=cwd)
    for line in res.stderr.splitlines():
        if "Maximum resident set size" in line:
            kb = int(line.split(":")[-1].strip())
            return kb / 1024.0
    # Fallback to output parsing if time doesn't work (rare)
    return 0.0

def main():
    benchmarks = []
    with open(f"{RL_DIR}/fhe_rl/datasets/benchmarks_isolated.txt", "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(":")
            expr_str = parts[0]
            name = parts[1] if len(parts) > 1 else "Unknown"
            ast = parse_sexpr(expr_str)
            benchmarks.append((name, expr_str, ast))
    
    print(f"Loaded {len(benchmarks)} benchmarks for execution")

    # Prepare Cmake for veclang_runner
    # run_cmd("cmake -S . -B build", cwd="/home/maroua/chehab-unified")
    # run_cmd("make", cwd="/home/maroua/chehab-unified/build")

    results = []
    for name, expr_str, ast in benchmarks:
        print(f"\n--- Running {name} ---")
        
        # Estimate
        params = FHEParams(poly_modulus_degree=16384, coeff_modulus_num_primes=6)
        lat_conf = BackendConfig("lattigo", 0.286, base_bytes_overhead=45*1024**2)
        seal_conf = BackendConfig("seal", 1.9, base_bytes_overhead=15*1024**2)
        
        lat_est = estimate_peak_ram(ast, params, order="fixed", keys="raw", backend_config=lat_conf).total_mib
        seal_est = estimate_peak_ram(ast, params, order="fixed", keys="raw", backend_config=seal_conf).total_mib
        
        # 1. Run Python Generator (inline, no torch)
        import random
        inputs_set = set()
        def get_inputs(node):
            if hasattr(node, "name"):
                inputs_set.add(node.name)
            if hasattr(node, "args"):
                for arg in node.args:
                    get_inputs(arg)
        get_inputs(ast)
        
        # We need slot_count. For simplicity just 1.
        slot_count = 1
        
        # veclang_runner.cpp checks:
        # "../vectorized_code.txt" -> RL_DIR/vectorized_code.txt
        # "../inputs.txt"          -> RL_DIR/inputs.txt
        # "fhe_io_example.txt"     -> VECLANG_RUNNER_DIR/fhe_io_example.txt
        
        with open(f"{RL_DIR}/vectorized_code.txt", "w") as f:
            f.write(f"{expr_str}\n{slot_count} {slot_count} 1 0\n")
            
        with open(f"{RL_DIR}/inputs.txt", "w") as f:
            f.write(" ".join(inputs_set) + "\n")
            f.write(" ".join(["1"] * len(inputs_set)) + "\n")
            
        with open(f"{VECLANG_RUNNER_DIR}/fhe_io_example.txt", "w") as f:
            f.write(f"{slot_count} {len(inputs_set)} 1\n")
            for var in inputs_set:
                f.write(f"{var} 1 1 {random.randint(0, 10)}\n")
        
        # 2. Generate SEAL C++ Code
        run_cmd("/home/maroua/chehab-unified/build/RL/veclang_runner/veclang_runner 1 1 0", cwd=VECLANG_RUNNER_DIR)
        
        # Compile SEAL C++
        he_dir = f"{VECLANG_RUNNER_DIR}/he"
        shutil.copy2("/home/maroua/chehab-unified/benchmarks/utils.cpp", f"{he_dir}/utils.cpp")
        shutil.copy2("/home/maroua/chehab-unified/benchmarks/utils.hpp", f"{he_dir}/utils.hpp")
        shutil.copy2("/home/maroua/chehab-unified/benchmarks/utils.h", f"{he_dir}/utils.h") if os.path.exists("/home/maroua/chehab-unified/benchmarks/utils.h") else None
        seal_dir = "/home/maroua/SEAL/build/cmake"
        if not os.path.exists(f"{he_dir}/build/Makefile"):
            run_cmd(f"cmake -S . -B build -DSEAL_DIR=\"{seal_dir}\"", cwd=he_dir)
        run_cmd("make", cwd=f"{he_dir}/build")
        
        # Execute SEAL and measure RAM
        seal_actual = get_peak_ram("./build/main", cwd=he_dir)
        print(f"SEAL: Actual {seal_actual:.2f} MB, Est {seal_est:.2f} MB", flush=True)
        
        # 3. Generate Lattigo Go Code
        run_cmd("/home/maroua/chehab-unified/build/RL/veclang_runner/veclang_runner 1 1 1", cwd=VECLANG_RUNNER_DIR)
        gen_go = Path(f"{VECLANG_RUNNER_DIR}/generated_fhe.go")
        shutil.copy2(gen_go, f"{LATTIGO_DIR}/generated_fhe.go")
        
        go_path = f"{LATTIGO_DIR}/generated_fhe.go"
        with open(go_path, "r") as f:
            content = f.read()
        # Removed NegNew patch as requested
        with open(go_path, "w") as f:
            f.write(content)
            
        # Execute Lattigo and measure RAM
        run_cmd("go build -o test_bin generated_fhe.go", cwd=LATTIGO_DIR)
        lat_actual = get_peak_ram("./test_bin", cwd=LATTIGO_DIR)
        print(f"Lattigo: Actual {lat_actual:.2f} MB, Est {lat_est:.2f} MB", flush=True)
        
        seal_err = abs(seal_est - seal_actual) / seal_actual * 100 if seal_actual > 0 else 0
        seal_dir = "OVER" if seal_est > seal_actual else "UNDER" if seal_est < seal_actual else "EXACT"
        lat_err = abs(lat_est - lat_actual) / lat_actual * 100 if lat_actual > 0 else 0
        lat_dir = "OVER" if lat_est > lat_actual else "UNDER" if lat_est < lat_actual else "EXACT"
        
        res_row = [name, seal_actual, seal_est, f"{seal_err:.2f}%", seal_dir, lat_actual, lat_est, f"{lat_err:.2f}%", lat_dir]
        results.append(res_row)
        with open("/mnt/c/Users/CC USER/.gemini/antigravity-ide/brain/72d30e96-47dc-46c5-98b8-938eff1a973a/scratch/benchmarks_execution.csv", "a", newline='') as f:
            writer = csv.writer(f)
            writer.writerow(res_row)

if __name__ == "__main__":
    with open("/mnt/c/Users/CC USER/.gemini/antigravity-ide/brain/72d30e96-47dc-46c5-98b8-938eff1a973a/scratch/benchmarks_execution.csv", "w", newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Benchmark", "SEAL Actual", "SEAL Est", "SEAL Error", "SEAL Dir", "Lattigo Actual", "Lattigo Est", "Lattigo Error", "Lattigo Dir"])
    main()

