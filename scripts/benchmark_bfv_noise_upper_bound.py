import argparse
import os
from pathlib import Path
import subprocess
import tempfile


def run(command, cwd=None):
    subprocess.run(command, cwd=cwd, check=True)


def main():
    parser = argparse.ArgumentParser(
        description="Write per-scenario integer trial means for actual and certified BFV noise budgets."
    )
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--excel-output", type=Path, default=None)
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--build-dir", type=Path, default=None)
    parser.add_argument("--seal-dir", type=Path, default=None)
    parser.add_argument(
        "--suite",
        choices=("synthetic", "workloads"),
        default="synthetic",
        help="workloads runs all supported static BFV benchmark operation graphs",
    )
    arguments = parser.parse_args()

    if arguments.trials < 1:
        parser.error("--trials must be positive")

    root = Path(__file__).resolve().parents[1]
    source = root / "benchmarks" / "bfv_noise_upper_bound"
    build_dir = arguments.build_dir or Path(tempfile.mkdtemp(prefix="bfv_noise_upper_bound_"))
    output_name = "bfv_noise_bound_workloads.csv" if arguments.suite == "workloads" else "bfv_noise_upper_bound.csv"
    output = (arguments.output or Path(output_name)).resolve()
    excel_output = (arguments.excel_output or output.with_suffix(".xlsx")).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    excel_output.parent.mkdir(parents=True, exist_ok=True)

    configure = ["cmake", "-S", str(source), "-B", str(build_dir)]
    seal_dir = arguments.seal_dir or os.environ.get("SEAL_DIR")
    if seal_dir:
        seal_dir = Path(seal_dir).expanduser().resolve()
        if not (seal_dir / "SEALConfig.cmake").is_file():
            parser.error(
                f"SEAL configuration not found in {seal_dir}. "
                "Pass --seal-dir to the directory containing SEALConfig.cmake."
            )
        configure.append(f"-DSEAL_DIR={seal_dir}")
    run(configure)
    target = "bfv_noise_bound_workloads" if arguments.suite == "workloads" else "bfv_noise_upper_bound_benchmark"
    run(["cmake", "--build", str(build_dir), "--target", target])

    executable = build_dir / target
    if os.name == "nt":
        executable = executable.with_suffix(".exe")
    run([str(executable), "--output", str(output), "--trials", str(arguments.trials)])
    dependencies = Path(os.environ.get(
        "CODEX_RUNTIME_DEPENDENCIES",
        Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies",
    ))
    node = Path(os.environ.get("CODEX_ARTIFACT_NODE", dependencies / "node" / "bin" / "node.exe"))
    node_modules = Path(os.environ.get("CODEX_ARTIFACT_NODE_MODULES", dependencies / "node" / "node_modules"))
    if not node.is_file() or not node_modules.is_dir():
        parser.error("Artifact Tool runtime is unavailable; set CODEX_ARTIFACT_NODE and CODEX_ARTIFACT_NODE_MODULES.")
    export_environment = os.environ.copy()
    export_environment["NODE_PATH"] = str(node_modules)
    subprocess.run(
        [str(node), str(root / "scripts" / "export_bfv_noise_results.mjs"), str(output), str(excel_output)],
        check=True,
        env=export_environment,
    )
    print(output)
    print(excel_output)
    print("CSV rows contain integer trial means, difference_bits, and difference_percent_of_initial_budget.")


if __name__ == "__main__":
    main()
