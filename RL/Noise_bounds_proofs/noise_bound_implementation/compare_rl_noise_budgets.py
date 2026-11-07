"""Compare measured RL BFV budgets with the strict noise-bound certificate.

The expression dataset is the source of truth for the bound.  Measured budgets
are joined from the RL end-to-end CSV files; a missing measurement is reported
as an empty CSV/XLSX cell rather than being estimated.

Example:
    python RL/Noise_bounds_proofs/noise_bound_implementation/compare_rl_noise_budgets.py ^
      --bound-executable build/bfv_noise_bound_cli.exe ^
      --output RL/Noise_bounds_proofs/noise_bound_implementation/rl_noise_budget_comparison.csv ^
      --excel-output RL/Noise_bounds_proofs/noise_bound_implementation/rl_noise_budget_comparison.xlsx
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


DEFAULT_BITS = "48,48,48,49,49,49,49,49,49"
SCRIPT_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = SCRIPT_DIR.parents[2]
DEFAULT_DATASET = REPOSITORY_ROOT / "RL" / "fhe_rl" / "datasets" / "benchmarks.txt"
DEFAULT_NAMES = DEFAULT_DATASET.with_name("benchmarks_names.xlsx")
DEFAULT_ACTUAL_DIR = REPOSITORY_ROOT / "RL" / "test_results" / "results_nov2" / "e2e"


def load_names(path: Path) -> dict[str, str]:
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise RuntimeError(
            "Reading --names requires openpyxl. Install it with: python -m pip install openpyxl"
        ) from exc
    workbook = load_workbook(path, read_only=True, data_only=True)
    sheet = workbook.active
    names: dict[str, str] = {}
    for row in sheet.iter_rows(min_row=2, values_only=True):
        if len(row) >= 2 and row[0] and row[1]:
            names[str(row[1]).strip()] = str(row[0]).strip()
    return names


def load_expressions(path: Path) -> list[str]:
    expressions = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    expressions = [line for line in expressions if line]
    if not expressions:
        raise ValueError(f"Dataset is empty: {path}")
    return expressions


def measured_budget_rows(directory: Path, requested_budget: int) -> dict[str, dict[str, Any]]:
    """Return one reproducible baseline measurement per benchmark.

    The historical RL files contain several policy rows.  We choose the
    baseline row (w_ops=1, w_keys=0), and reject conflicting duplicate values.
    """
    result: dict[str, dict[str, Any]] = {}
    for path in sorted(directory.glob("e2e_*.csv")):
        with path.open(newline="", encoding="utf-8-sig") as stream:
            rows = list(csv.DictReader(stream))
        baseline = [
            row for row in rows
            if row.get("w_ops") == "1.0" and row.get("w_keys") == "0.0"
            and row.get("budget") == str(requested_budget)
        ]
        if not baseline:
            continue
        by_benchmark: dict[str, list[float]] = {}
        for row in baseline:
            benchmark = row.get("benchmark", "").strip()
            value = row.get("Remaining_noise_budget", "").strip()
            if benchmark and value:
                by_benchmark.setdefault(benchmark, []).append(float(value))
        for benchmark, values in by_benchmark.items():
            if max(values) - min(values) > 1e-9:
                raise ValueError(f"Conflicting baseline measurements for {benchmark} in {path}")
            matching_row = next(row for row in baseline if row.get("benchmark", "").strip() == benchmark)
            result[benchmark] = {
                "actual_remaining_budget_bits": values[0],
                "actual_budget_bits": float(baseline[0].get("budget", "nan")),
                "actual_source": str(path),
                "actual_status": matching_row.get("status", ""),
                "actual_outputs_match": matching_row.get("outputs_match", ""),
            }
    return result


def actual_aliases(name: str) -> tuple[str, ...]:
    """Return historical benchmark spellings for a dataset benchmark name."""
    aliases = [name]
    tree = re.fullmatch(r"tree_(\d+-\d+)-(\d+)_poly", name)
    if tree:
        aliases.append(f"tree_{tree.group(1)}_{tree.group(2)}_1")
    return tuple(aliases)


def run_bound(executable: Path, expression: str, poly_degree: int, plain_modulus: int, bits: str) -> dict[str, Any]:
    command = [
        str(executable),
        "--poly-modulus-degree", str(poly_degree),
        "--plain-modulus", str(plain_modulus),
        "--coeff-modulus-bits", bits,
    ]
    completed = subprocess.run(
        command, input=expression, text=True, capture_output=True, check=False
    )
    if completed.returncode:
        raise RuntimeError(
            f"Bound executable failed for expression: {completed.stderr.strip() or expression[:100]}"
        )
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid bound output: {completed.stdout!r}") from exc
    return value


def write_excel(path: Path, rows: list[dict[str, Any]]) -> None:
    try:
        from openpyxl import Workbook
    except ImportError as exc:
        raise RuntimeError(
            "Writing --excel-output requires openpyxl. Install it with: python -m pip install openpyxl"
        ) from exc
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "comparison"
    columns = list(rows[0]) if rows else []
    sheet.append(columns)
    for row in rows:
        sheet.append([row.get(column) for column in columns])
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for column in sheet.columns:
        width = min(max(len(str(cell.value or "")) for cell in column) + 2, 60)
        sheet.column_dimensions[column[0].column_letter].width = width
    summary = workbook.create_sheet("summary")
    summary.append(["metric", "value"])
    summary.append(["rows", len(rows)])
    summary.append(["rows_with_actual_budget", sum(row["actual_remaining_budget_bits"] != "" for row in rows)])
    summary.append(["rows_with_bound_budget", sum(row["bound_remaining_budget_bits"] != "" for row in rows)])
    workbook.save(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--names", type=Path, default=DEFAULT_NAMES)
    parser.add_argument("--actual-csv-dir", type=Path, default=DEFAULT_ACTUAL_DIR)
    parser.add_argument(
        "--actual-budget", type=int, default=369,
        help="SEAL budget column to use when joining historical measurements (default: 369)",
    )
    parser.add_argument("--bound-executable", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=SCRIPT_DIR / "rl_noise_budget_comparison.csv")
    parser.add_argument("--excel-output", type=Path, default=None)
    parser.add_argument("--poly-modulus-degree", type=int, default=16384)
    parser.add_argument("--plain-modulus", type=int, default=786433)
    parser.add_argument("--coeff-modulus-bits", default=DEFAULT_BITS)
    args = parser.parse_args()

    for path in (args.dataset, args.names, args.actual_csv_dir, args.bound_executable):
        if not path.exists():
            parser.error(f"path does not exist: {path}")
    expressions = load_expressions(args.dataset)
    names = load_names(args.names)
    actual = measured_budget_rows(args.actual_csv_dir, args.actual_budget)
    rows: list[dict[str, Any]] = []
    for index, expression in enumerate(expressions):
        name = names.get(expression, f"dataset_{index}")
        bound = run_bound(
            args.bound_executable, expression, args.poly_modulus_degree,
            args.plain_modulus, args.coeff_modulus_bits,
        )
        measurement = next(
            (actual[alias] for alias in actual_aliases(name) if alias in actual),
            {},
        )
        actual_remaining = measurement.get("actual_remaining_budget_bits", "")
        bound_remaining = bound.get("remaining_noise_budget_bits", "")
        outputs_match = measurement.get("actual_outputs_match", "")
        actual_valid = outputs_match in ("", "True", True)
        rows.append({
            "actual_remaining_budget_bits": actual_remaining,
            "bound_remaining_budget_bits": bound_remaining,
            "actual_minus_bound_bits": (
                actual_remaining - bound_remaining
                if actual_remaining != "" and bound_remaining != "" and actual_valid else ""
            ),
            "bound_decryptable": bound.get("decryptable", ""),
            "expression": expression,
        })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    excel_output = args.excel_output or args.output.with_suffix(".xlsx")
    excel_output.parent.mkdir(parents=True, exist_ok=True)
    write_excel(excel_output, rows)
    print(f"Wrote {len(rows)} rows to {args.output}")
    print(f"Wrote {len(rows)} rows to {excel_output}")
    print(f"Measured rows joined: {sum(row['actual_remaining_budget_bits'] != '' for row in rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
