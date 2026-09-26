import os
import subprocess
import csv
import re
import statistics

benchmarks_folder = "benchmarks"
build_folder = os.path.join("build", "benchmarks")
operations = ["add", "sub", "multiply_plain", "rotate_rows", "negate", "multiply"]
infos = ["benchmark", "w_ops", "w_keys", "Depth", "Multiplicative Depth", "compile_time (s)",
         "circuit_execution_time (s)", 'galois_keys_generation_time (s)', 'total_execution_time (s)',
         "Remaining_noise_budget", 'rotation_keys_size (MB)', 'rotation_keys_count', 'final_ops_cost', 'final_keys_cost']
full_header = ["benchmark", "w_ops", "w_keys"] + operations + infos[3:]

benchmark_folders = [
    "lin_reg", "box_blur", "matrix_mul", "max", "sort",
    "dot_product", "gx_kernel", "gy_kernel", "hamming_dist",
    "l2_distance", "poly_reg", "roberts_cross"
]

# FIX 1: use an ops-inclusive preference list like Imed's.
# (w_ops=0, w_keys=1) is a valid point but yields scalar code -> all key metrics = 0 BY DESIGN.
pref_list = [[0.8, 0.2], [1.0, 0.0]]

depths = [5, 10]
regimes = ["50-50", "100-50", "100-100"]
number_instances_each_polynomial_configuration = 2

exceptions = ["max", "sort", "discrete_cosin_transform", "poly_derivative"]
benchmarks_slot_counts = {"max": [3, 4, 5], "sort": [3], "discrete_cosin_transform": [1], "poly_derivative": [1]}
slot_counts = [4, 8, 16, 32]

# FIX 2: build the project once at start (Imed's script does this; yours didn't)
try:
    print("run=> cmake -S . -B build")
    subprocess.run(['cmake', '-S', '.', '-B', 'build'], check=True,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    print("run=> cmake --build build")
    subprocess.run(['cmake', '--build', 'build'], check=True,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
except subprocess.CalledProcessError as e:
    print(f"CMake build failed:\n{e.stderr}")
    raise

with open("results_RL.csv", mode='w', newline='') as file:
    csv.writer(file).writerow(full_header)


def run_benchmark(subfolder_name, slot_count, w_ops, w_keys, build_path, poly_args=None):
    he_path = os.path.join(build_path, "he")
    build_he_path = os.path.join(he_path, "build")
    stats = {k: [] for k in operations + infos[3:]}

    if not poly_args and subfolder_name not in exceptions:
        if os.path.exists(os.path.join(build_path, f"generate_{subfolder_name}.py")):
            subprocess.Popen(['python3', f'generate_{subfolder_name}.py', '--slot_count', str(slot_count)], cwd=build_path).wait()

    # FIX 3: restored the missing backend argument '0' before w_ops/w_keys,
    # so w_ops -> argv[9], w_keys -> argv[10] as the benchmark main() expects.
    if poly_args:
        cmd = f"./{subfolder_name} {poly_args} 1 1 0 1 1 1 0 {w_ops} {w_keys}"
    else:
        cmd = f"./{subfolder_name} 1 {slot_count} 1 0 1 1 1 0 {w_ops} {w_keys}"

    try:
        res = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             universal_newlines=True, cwd=build_path, timeout=7200)

        if res.returncode != 0:
            print(f"\n[CRITICAL ERROR] benchmark {subfolder_name} crashed!")
            print(f"--- stderr ---\n{res.stderr.strip()}\n--------------")

        for line in res.stdout.splitlines():
            clean = re.sub(r'\x1b\[[0-9;]*m', '', line)

            ops_match = re.search(r'final\s*exec\s*cost\s*:\s*([\d\.]+)', clean, re.IGNORECASE)
            if ops_match:
                stats["final_ops_cost"].append(float(ops_match.group(1)))

            keys_match = re.search(r'final\s*keys\s*cost\s*:\s*([\d\.]+)', clean, re.IGNORECASE)
            if keys_match:
                stats["final_keys_cost"].append(float(keys_match.group(1)))

            if ' ms' in line:
                try:
                    stats["compile_time (s)"].append(float(line.split()[0]))
                except ValueError:
                    pass

        depth_m = re.search(r'max:\s*\((\d+),\s*(\d+)\)', res.stdout)
        if depth_m:
            stats["Depth"].append(int(depth_m.group(1)))
            stats["Multiplicative Depth"].append(int(depth_m.group(2)))

        if res.returncode == 0:
            subprocess.run(['cmake', '-S', '.', '-B', 'build'], cwd=he_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            subprocess.run(['cmake', '--build', 'build'], cwd=he_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            run_res = subprocess.run("./main", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     universal_newlines=True, cwd=build_he_path)
            for line in run_res.stdout.splitlines():
                if 'circuit_execution_time_(ms):' in line: stats["circuit_execution_time (s)"].append(float(line.split()[1]))
                if 'galois_keys_generation_time_(ms):' in line: stats["galois_keys_generation_time (s)"].append(float(line.split()[1]))
                if 'total_execution_time_(ms):' in line: stats["total_execution_time (s)"].append(float(line.split()[1]))
                if 'rotation_keys_size_(MB):' in line: stats["rotation_keys_size (MB)"].append(float(line.split()[1]))
                if 'rotation_keys_count_:' in line: stats["rotation_keys_count"].append(int(line.split()[1]))
                if 'Remaining_noise_budget:' in line: stats["Remaining_noise_budget"].append(int(line.split()[1]))

        cpp_file = os.path.join(he_path, "_gen_he_fhe.cpp")
        if os.path.exists(cpp_file):
            with open(cpp_file, "r") as f:
                content = f.read()
                for op in operations:
                    stats[op].append(len(re.findall(rf'\b{op}', content)))
    except Exception as e:
        print(f"Python exception while running {subfolder_name}: {e}")

    b_name = f"tree_{poly_args.replace(' ', '_')}" if poly_args else f"{subfolder_name}_{slot_count}"
    row = [b_name, w_ops, w_keys]

    for key in operations + infos[3:]:
        vals = stats[key]
        if not vals or None in vals:
            row.append("N/A")
        else:
            v = statistics.median(vals)
            if key in ["compile_time (s)", "circuit_execution_time (s)", "galois_keys_generation_time (s)", "total_execution_time (s)"]:
                v = format(v / 1000, ".3f")
            row.append(v)

    with open("results_RL.csv", mode='a', newline='') as f:
        csv.writer(f).writerow(row)


# FIX 4: loop over the preference list for each benchmark/slot, like Imed's coarse grid
for sub in benchmark_folders:
    b_path = os.path.join(build_folder, sub)
    if os.path.isdir(b_path):
        for sc in benchmarks_slot_counts.get(sub, slot_counts):
            for w_ops, w_keys in pref_list:
                print(f"*****run {sub} , slot : {sc} , w=({w_ops},{w_keys})******")
                run_benchmark(sub, sc, w_ops, w_keys, b_path)

poly_path = os.path.join(build_folder, "polynomials_coyote")
if os.path.isdir(poly_path):
    for reg in regimes:
        for d in depths:
            for inst in range(1, number_instances_each_polynomial_configuration + 1):
                for w_ops, w_keys in pref_list:
                    print(f"*****run tree_{reg}_{d}_{inst} , w=({w_ops},{w_keys})******")
                    run_benchmark("polynomials_coyote", 1, w_ops, w_keys, poly_path, poly_args=f"{d} {inst} {reg}")