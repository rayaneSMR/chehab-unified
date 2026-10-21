#!/usr/bin/env python3
"""
Master runner script that executes DNN benchmarks across all 5 optimizers:
  1. Without optimization ('none')
  2. Greedy TRS ('trs')
  3. Original RL ('original_rl')
  4. Constrained RL ('constrained_rl')
  5. Multi-Objective RL ('morl')

Outputs:
  - 1 unified Excel workbook with a separate sheet for each optimizer
  - Individual Excel files for each optimizer (.xlsx)
  - Individual CSV files matching run_all_benchmarks.py (.csv)
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import pandas as pd
except ImportError:
    pd = None


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
RESULTS_DIR = REPO_ROOT / "results"
RUNNER_SCRIPT = SCRIPTS_DIR / "run_all_benchmarks.py"

DEFAULT_DNNS = [
    "conv2d", "full_dnn", "cryptonets", "mlp", "lola", "lenet",
    "resnet20_relu", "resnet20_silu", "resnet34_relu", "resnet34_silu",
    "resnet50_relu", "resnet50_silu", "alexnet",
]

OPTIMIZERS_CONFIG = [
    {
        "key": "none",
        "sheet_name": "Without",
        "label": "Without Optimization",
        "cli_opt": "none",
    },
    {
        "key": "trs",
        "sheet_name": "Greedy_TRS",
        "label": "Greedy TRS",
        "cli_opt": "trs",
    },
    {
        "key": "original_rl",
        "sheet_name": "Original_RL",
        "label": "Original RL",
        "cli_opt": "original_rl",
    },
    {
        "key": "constrained_rl",
        "sheet_name": "Constrained_RL",
        "label": "Constrained RL",
        "cli_opt": "constrained_rl",
    },
    {
        "key": "morl",
        "sheet_name": "MORL",
        "label": "Multi-Objective RL (MORL)",
        "cli_opt": "morl",
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run DNN benchmarks across all VecLang optimizers and generate Excel sheets"
    )
    parser.add_argument(
        "--benchmarks",
        default=",".join(DEFAULT_DNNS),
        help=f"comma-separated DNN benchmarks (default: {','.join(DEFAULT_DNNS)})",
    )
    parser.add_argument(
        "--optimizers",
        default="none,trs,original_rl,constrained_rl,morl",
        help="comma-separated list of optimizers to run: none,trs,original_rl,constrained_rl,morl",
    )
    parser.add_argument(
        "--repetitions",
        type=int,
        default=1,
        help="encrypted inference repetitions per benchmark (default: 1)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="per-benchmark timeout in seconds (default: 600)",
    )
    parser.add_argument(
        "--w-ops",
        type=float,
        default=0.5,
        help="weight for operations in MORL (default: 0.5)",
    )
    parser.add_argument(
        "--bsgs-base",
        default="global",
        help="BSGS base (default: global)",
    )
    parser.add_argument(
        "--naf",
        action="store_true",
        help="enable NAF rotation-key reduction during Lattigo code generation",
    )
    parser.add_argument(
        "--naf-threshold",
        type=int,
        default=0,
        help="maximum rotation-key count targeted by NAF reduction; 0 selects the smallest possible budget",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=RESULTS_DIR,
        help="directory for output files (default: results/)",
    )
    parser.add_argument(
        "--excel-filename",
        default="all_optimizers_dnn_benchmarks.xlsx",
        help="name of the combined Excel workbook (default: all_optimizers_dnn_benchmarks.xlsx)",
    )
    parser.add_argument(
        "--backend",
        choices=("lattigo", "heongpu"),
        default="lattigo",
        help="cryptographic backend: lattigo (default) or heongpu",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="skip initial compilation of the benchmark runner executable",
    )
    return parser.parse_args()


def format_excel_sheet(worksheet: Any) -> None:
    """Apply auto-fit column widths and clean formatting to an openpyxl worksheet."""
    from openpyxl.styles import Alignment, Font, PatternFill

    header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
    regular_font = Font(name="Segoe UI", size=10)

    for cell in worksheet[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")

    worksheet.row_dimensions[1].height = 24

    for row in worksheet.iter_rows(min_row=2):
        for cell in row:
            cell.font = regular_font

    for col in worksheet.columns:
        max_len = 0
        col_letter = col[0].column_letter
        for cell in col:
            val_str = str(cell.value or "")
            if len(val_str) > max_len:
                max_len = len(val_str)
        worksheet.column_dimensions[col_letter].width = max(max_len + 4, 12)


def main() -> int:
    args = parse_args()
    if args.naf_threshold < 0:
        print("--naf-threshold must be non-negative", file=sys.stderr)
        return 1
    args.output_dir.mkdir(parents=True, exist_ok=True)

    selected_opt_keys = [k.strip() for k in args.optimizers.split(",") if k.strip()]
    configs_to_run = [c for c in OPTIMIZERS_CONFIG if c["key"] in selected_opt_keys]

    if not configs_to_run:
        print(f"Error: No valid optimizers selected from '{args.optimizers}'", file=sys.stderr)
        return 1

    print("=" * 80)
    print("CHEHAB DNN BENCHMARK RUNNER ACROSS ALL OPTIMIZERS")
    print(f"Benchmarks  : {args.benchmarks}")
    print(f"Repetitions : {args.repetitions}")
    print(f"Timeout     : {args.timeout}s per benchmark")
    print(f"Optimizers  : {', '.join(c['label'] for c in configs_to_run)}")
    print(f"Output Dir  : {args.output_dir.resolve()}")
    print("=" * 80)

    # Initial build if requested
    if not args.skip_build:
        print("\n[Step 0] Ensuring runner executable is built...")
        build_cmd = [
            sys.executable,
            str(RUNNER_SCRIPT),
            "--benchmarks", "conv2d",
            "--optimizer", "none",
            "--repetitions", "1",
            "--timeout", "120",
        ]
        # Run dummy check with --repetitions 1 to trigger build_target
        # We can directly invoke cmake build for the runner
        cmake_build = subprocess.run(
            ["cmake", "--build", str(REPO_ROOT / "build"), "--target", "dnn_tensor_benchmarks_runner_bin"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if cmake_build.returncode != 0:
            print(f"Build failed:\n{cmake_build.stderr or cmake_build.stdout}", file=sys.stderr)
            return 1
        print("  Build completed successfully.")

    dfs_by_sheet: dict[str, pd.DataFrame] = {}
    overall_success = True

    for idx, opt_cfg in enumerate(configs_to_run, start=1):
        opt_key = opt_cfg["key"]
        sheet_name = opt_cfg["sheet_name"]
        label = opt_cfg["label"]
        cli_opt = opt_cfg["cli_opt"]

        csv_file = args.output_dir / f"metrics_{opt_key}.csv"
        xlsx_file = args.output_dir / f"metrics_{opt_key}.xlsx"

        print(f"\n[{idx}/{len(configs_to_run)}] Running Optimizer: {label} ({opt_key})...")

        cmd = [
            sys.executable,
            str(RUNNER_SCRIPT),
            "--benchmarks", args.benchmarks,
            "--backend", args.backend,
            "--optimizer", cli_opt,
            "--repetitions", str(args.repetitions),
            "--timeout", str(args.timeout),
            "--bsgs-base", args.bsgs_base,
            "--skip-build",
            "--output-csv", str(csv_file),
        ]
        if cli_opt == "morl":
            cmd.extend(["--w-ops", str(args.w_ops)])
        if args.naf:
            cmd.extend(["--naf", "--naf-threshold", str(args.naf_threshold)])

        proc = subprocess.run(cmd, cwd=REPO_ROOT, check=False)
        if proc.returncode != 0:
            print(f"  Warning: Run for {opt_key} finished with exit code {proc.returncode}")
            overall_success = False

        if csv_file.is_file():
            if pd is not None:
                try:
                    df = pd.read_csv(csv_file)
                    dfs_by_sheet[sheet_name] = df
                    with pd.ExcelWriter(xlsx_file, engine="openpyxl") as writer:
                        df.to_excel(writer, sheet_name=sheet_name, index=False)
                        format_excel_sheet(writer.sheets[sheet_name])
                    print(f"  Saved individual sheet: {xlsx_file.name} ({len(df)} rows)")
                except Exception as e:
                    print(f"  Warning: Could not write Excel file {xlsx_file}: {e}")
            else:
                print(f"  Saved CSV: {csv_file.name} (install pandas & openpyxl for Excel export)")
        else:
            print(f"  Error: Output CSV {csv_file} was not generated!", file=sys.stderr)

    # Save combined multi-sheet Excel workbook
    if dfs_by_sheet and pd is not None:
        try:
            combined_xlsx = args.output_dir / args.excel_filename
            print(f"\nWriting combined multi-sheet Excel workbook: {combined_xlsx}...")
            with pd.ExcelWriter(combined_xlsx, engine="openpyxl") as writer:
                for sheet_name, df in dfs_by_sheet.items():
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
                    format_excel_sheet(writer.sheets[sheet_name])
            print(f"Combined Excel saved successfully: {combined_xlsx}")
        except Exception as e:
            print(f"  Warning: Could not write combined Excel file: {e}")

    print("\n" + "=" * 80)
    print("ALL RUNS COMPLETED")
    print(f"Output Excel Workbook : {args.output_dir / args.excel_filename}")
    for opt_cfg in configs_to_run:
        sheet = opt_cfg["sheet_name"]
        key = opt_cfg["key"]
        print(f"  - Sheet '{sheet}': {args.output_dir / f'metrics_{key}.xlsx'}")
    print("=" * 80)

    return 0 if overall_success else 1


if __name__ == "__main__":
    sys.exit(main())
