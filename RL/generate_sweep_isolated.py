import os
import subprocess
import csv
from pytrs.peak_ram import estimate_peak_ram, FHEParams, BackendConfig
from pytrs.expr import Op, Const, Var

def ast_deep_poly(depth):
    ast = Var("x")
    for _ in range(depth):
        ast = Op("*", [ast, ast])
    return ast, 1

def ast_dot_product(size):
    muls = [Op("*", [Var(f"c{i}"), Var(f"c{i+1}")]) for i in range(0, size, 2)]
    if not muls:
        return Var("x"), 1
    while len(muls) > 1:
        next_muls = []
        for i in range(0, len(muls), 2):
            if i+1 < len(muls):
                next_muls.append(Op("+", [muls[i], muls[i+1]]))
            else:
                next_muls.append(muls[i])
        muls = next_muls
    return muls[0], 1

def ast_conv(layers):
    ast = Var("x")
    rotations = set()
    currentWidth = 32
    for l in range(layers):
        for ki in range(3):
            for kj in range(3):
                rot = ki*currentWidth + kj
                if rot != 0:
                    rotations.add(rot)
        currentWidth -= 2
    
    for r in rotations:
        ast = Op("+", [ast, Op("<<", [Var("x"), Const(r)])])
    return ast, len(rotations)

os.chdir("/home/maroua/chehab-unified/lattigo_backend")
subprocess.run("go build -o sweep_runner sweep_runner.go", shell=True, executable='/bin/bash', check=True)

experiments = [
    {"type": 1, "name": "Deep Poly", "arg": 2, "N": 8192, "L": 4},
    {"type": 1, "name": "Deep Poly", "arg": 4, "N": 8192, "L": 4},
    {"type": 1, "name": "Deep Poly", "arg": 6, "N": 16384, "L": 6},
    {"type": 1, "name": "Deep Poly", "arg": 8, "N": 16384, "L": 6},
    {"type": 1, "name": "Deep Poly", "arg": 10, "N": 32768, "L": 8},
    {"type": 1, "name": "Deep Poly", "arg": 12, "N": 32768, "L": 10},
    {"type": 2, "name": "Dot Product", "arg": 4, "N": 8192, "L": 4},
    {"type": 2, "name": "Dot Product", "arg": 8, "N": 8192, "L": 4},
    {"type": 2, "name": "Dot Product", "arg": 16, "N": 16384, "L": 6},
    {"type": 2, "name": "Dot Product", "arg": 32, "N": 16384, "L": 6},
    {"type": 2, "name": "Dot Product", "arg": 64, "N": 16384, "L": 6},
    {"type": 2, "name": "Dot Product", "arg": 128, "N": 32768, "L": 8},
    {"type": 2, "name": "Dot Product", "arg": 256, "N": 32768, "L": 8},
    {"type": 3, "name": "Conv2D", "arg": 1, "N": 8192, "L": 4},
    {"type": 3, "name": "Conv2D", "arg": 2, "N": 16384, "L": 6},
    {"type": 3, "name": "Conv2D", "arg": 3, "N": 16384, "L": 6},
    {"type": 3, "name": "Conv2D", "arg": 4, "N": 32768, "L": 12},
    {"type": 3, "name": "Conv2D", "arg": 5, "N": 32768, "L": 12},
    {"type": 3, "name": "Conv2D", "arg": 6, "N": 32768, "L": 12},
]

# SEAL worker script content
seal_worker_code = """import sys, resource, tenseal as ts
try:
    N, L, keys = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
    seal_primes = [40]*L
    base_ram = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    context = ts.context(ts.SCHEME_TYPE.CKKS, poly_modulus_degree=N, coeff_mod_bit_sizes=seal_primes)
    if keys > 1:
        context.generate_galois_keys()
    context.generate_relin_keys()
    peak_ram = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    print(max(0, peak_ram - base_ram))
except Exception as e:
    print(0)
"""
with open("/mnt/c/Users/CC USER/.gemini/antigravity-ide/brain/72d30e96-47dc-46c5-98b8-938eff1a973a/scratch/seal_worker.py", "w") as f:
    f.write(seal_worker_code)

results = []
for exp in experiments:
    print(f"Running {exp['name']} (Arg: {exp['arg']}, N: {exp['N']}, L: {exp['L']})...")
    if exp['type'] == 1:
        ast, keys = ast_deep_poly(exp['arg'])
    elif exp['type'] == 2:
        ast, keys = ast_dot_product(exp['arg'])
    else:
        ast, keys = ast_conv(exp['arg'])
        
    logN = {8192: 13, 16384: 14, 32768: 15}[exp['N']]
    
    # Lattigo Subprocess
    cmd = f"/usr/bin/time -v ./sweep_runner {exp['type']} {logN} {exp['L']} {exp['arg']} 2>&1"
    try:
        out = subprocess.check_output(cmd, shell=True, executable='/bin/bash').decode('utf-8')
        lat_ram = 0
        for line in out.splitlines():
            if "Maximum resident set size" in line:
                lat_ram = int(line.split(":")[1].strip()) * 1024
    except Exception:
        lat_ram = 0
        
    # SEAL Subprocess (Isolates RAM pool per run)
    seal_cmd = f"/home/maroua/miniconda3/bin/python3 /mnt/c/Users/CC\\ USER/.gemini/antigravity-ide/brain/72d30e96-47dc-46c5-98b8-938eff1a973a/scratch/seal_worker.py {exp['N']} {exp['L']} {keys}"
    try:
        out = subprocess.check_output(seal_cmd, shell=True, executable='/bin/bash').decode('utf-8')
        seal_ram = int(out.strip())
    except Exception:
        seal_ram = 0
        
    from pytrs.peak_ram import SEAL_CONFIG, LATTIGO_CONFIG
    params = FHEParams(poly_modulus_degree=exp['N'], coeff_modulus_num_primes=exp['L'])
    lat_est = estimate_peak_ram(ast, params, keys_threshold=13, backend_config=LATTIGO_CONFIG).total_bytes
    
    seal_keys = 13
    seal_est = estimate_peak_ram(ast, params, keys_threshold=seal_keys, backend_config=SEAL_CONFIG).total_bytes
    
    seal_err = abs(seal_est - seal_ram) / seal_ram * 100 if seal_ram > 0 else 0
    seal_dir = "OVER" if seal_est > seal_ram else "UNDER" if seal_est < seal_ram else "EXACT"
    lat_err = abs(lat_est - lat_ram) / lat_ram * 100 if lat_ram > 0 else 0
    lat_dir = "OVER" if lat_est > lat_ram else "UNDER" if lat_est < lat_ram else "EXACT"

    res = {
        "Benchmark": exp['name'],
        "Variant": exp['arg'],
        "N": exp['N'],
        "L": exp['L'],
        "Total Keys": keys,
        "SEAL Actual (MB)": round(seal_ram / 1024**2, 2),
        "SEAL Est (MB)": round(seal_est / 1024**2, 2),
        "SEAL Error (%)": round(seal_err, 2),
        "SEAL Dir": seal_dir,
        "Lattigo Actual (MB)": round(lat_ram / 1024**2, 2),
        "Lattigo Est (MB)": round(lat_est / 1024**2, 2),
        "Lattigo Error (%)": round(lat_err, 2),
        "Lattigo Dir": lat_dir,
    }
    results.append(res)

csv_path = "/mnt/c/Users/CC USER/.gemini/antigravity-ide/brain/72d30e96-47dc-46c5-98b8-938eff1a973a/artifacts/sweep_results_isolated.csv"
with open(csv_path, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=results[0].keys())
    writer.writeheader()
    writer.writerows(results)
print("Done! Results written to CSV.")
