import argparse
import csv
import os
import re
import statistics
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
LATTIGO_DIR = ROOT / "lattigo_backend"
WORKER = LATTIGO_DIR / "ram_empty_microbench.go"
DEFAULT_PAIRS = ((8192, 5), (16384, 6), (16384, 8), (32768, 10))
PHASES = ("baseline", "parameters", "keys", "helpers", "one_input")
SNAPSHOT_PATTERN = re.compile(
    r"MEM_PHASE (?P<phase>\w+) vmrss=(?P<rss>\d+) kB "
    r"vmhwm=(?P<hwm>\d+) kB heap_alloc=(?P<alloc>\d+) "
    r"heap_inuse=(?P<inuse>\d+) heap_sys=(?P<heap_sys>\d+) "
    r"num_gc=(?P<num_gc>\d+) total_alloc=(?P<total_alloc>\d+)"
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Measure fixed Lattigo runtime/key/input costs at selected N,L pairs."
    )
    parser.add_argument(
        "--pairs",
        nargs="+",
        default=[f"{n}:{l}" for n, l in DEFAULT_PAIRS],
        help="N:L parameter pairs; defaults include two pairs outside the corpus",
    )
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "RL" / "lattigo_empty_microbench.csv",
    )
    return parser.parse_args()


def parse_snapshots(stdout):
    snapshots = {}
    for match in SNAPSHOT_PATTERN.finditer(stdout):
        phase = match.group("phase")
        snapshots[phase] = {
            key: int(value)
            for key, value in match.groupdict().items()
            if key != "phase"
        }
    if set(snapshots) != set(PHASES):
        raise ValueError(
            f"Missing phases: {sorted(set(PHASES) - set(snapshots))}"
        )
    return snapshots


def run():
    args = parse_args()
    if args.repeats < 1:
        raise SystemExit("--repeats must be positive")
    pairs = []
    for pair in args.pairs:
        try:
            n, l = (int(value) for value in pair.split(":"))
        except ValueError as error:
            raise SystemExit(f"invalid N:L pair {pair!r}") from error
        pairs.append((n, l))
    if len(set(pairs)) != len(pairs):
        raise SystemExit("parameter pairs must be unique")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "N",
        "L",
        "Repeat",
        "GOGC",
        "Peak RSS (MiB)",
    ] + [
        f"{phase} {metric} (MiB)"
        for phase in PHASES
        for metric in ("RSS", "HWM", "Heap Alloc", "Heap Inuse", "Heap Sys", "Total Alloc")
    ] + [f"{phase} NumGC" for phase in PHASES]

    with tempfile.TemporaryDirectory(prefix="lattigo-empty-") as temp:
        executable = Path(temp) / "ram_empty_microbench"
        subprocess.run(
            ["go", "build", "-mod=readonly", "-o", str(executable), str(WORKER)],
            cwd=LATTIGO_DIR,
            check=True,
            capture_output=True,
            text=True,
            timeout=300,
        )
        with args.output.open("w", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            output.flush()
            for n, l in pairs:
                for repeat in range(1, args.repeats + 1):
                    measured = subprocess.run(
                        [
                            "/usr/bin/time",
                            "-f",
                            "peak_rss_kib=%M",
                            str(executable),
                            str(n),
                            str(l),
                        ],
                        cwd=LATTIGO_DIR,
                        env={**os.environ, "GOGC": "100"},
                        check=True,
                        capture_output=True,
                        text=True,
                        timeout=180,
                    )
                    peak = re.search(r"peak_rss_kib=(\d+)", measured.stderr)
                    if peak is None:
                        raise RuntimeError("Missing /usr/bin/time peak RSS")
                    snapshots = parse_snapshots(measured.stdout)
                    row = {
                        "N": n,
                        "L": l,
                        "Repeat": repeat,
                        "GOGC": 100,
                        "Peak RSS (MiB)": int(peak.group(1)) / 1024,
                    }
                    for phase, values in snapshots.items():
                        row[f"{phase} RSS (MiB)"] = values["rss"] / 1024
                        row[f"{phase} HWM (MiB)"] = values["hwm"] / 1024
                        row[f"{phase} Heap Alloc (MiB)"] = values["alloc"] / 2**20
                        row[f"{phase} Heap Inuse (MiB)"] = values["inuse"] / 2**20
                        row[f"{phase} Heap Sys (MiB)"] = values["heap_sys"] / 2**20
                        row[f"{phase} Total Alloc (MiB)"] = values["total_alloc"] / 2**20
                        row[f"{phase} NumGC"] = values["num_gc"]
                    writer.writerow(row)
                    output.flush()
                    print(f"Measured N={n} L={l} repeat={repeat}", flush=True)

    with args.output.open(newline="") as source:
        grouped = {}
        for row in csv.DictReader(source):
            key = (int(row["N"]), int(row["L"]))
            grouped.setdefault(key, []).append(float(row["Peak RSS (MiB)"]))
    for (n, l), values in grouped.items():
        print(
            f"N={n} L={l}: median peak RSS={statistics.median(values):.2f} MiB "
            f"(min={min(values):.2f}, max={max(values):.2f})"
        )
    print(f"Measurements written to {args.output}")


if __name__ == "__main__":
    run()
