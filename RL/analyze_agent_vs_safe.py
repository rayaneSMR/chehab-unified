"""Compare RAW agent behaviour vs post-rollback (safety) behaviour per preference.

Decides whether the "inverse DNN curve" (lower w_exec -> better exec reduction)
comes from the policy itself or from the MORL safety rollback in test.py.

Stdlib-only xlsx reader (openpyxl not installed in this env).
"""

import re
import sys
import zipfile
import xml.etree.ElementTree as ET

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def read_sheet(path, sheet_name="all_results"):
    z = zipfile.ZipFile(path)
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    relmap = {r.get("Id"): r.get("Target") for r in rels}

    target = None
    for s in wb.iter(NS + "sheet"):
        if s.get("name") == sheet_name:
            target = relmap[s.get(REL_NS + "id")]
    if target is None:
        raise SystemExit(f"sheet {sheet_name!r} not found in {path}")
    if not target.startswith("xl/"):
        target = target.lstrip("/")
    if not target.startswith("xl/"):
        target = "xl/" + target

    try:
        ss = ET.fromstring(z.read("xl/sharedStrings.xml"))
        strings = [
            "".join(t.text or "" for t in si.iter(NS + "t"))
            for si in ss.iter(NS + "si")
        ]
    except KeyError:
        strings = []

    root = ET.fromstring(z.read(target))
    rows = []
    for row in root.iter(NS + "row"):
        vals = {}
        for c in row.iter(NS + "c"):
            col = re.match(r"[A-Z]+", c.get("r")).group(0)
            t = c.get("t")
            v = c.find(NS + "v")
            if t == "s":
                val = strings[int(v.text)]
            elif t == "inlineStr":
                isx = c.find(NS + "is")
                val = "".join(x.text or "" for x in isx.iter(NS + "t")) if isx is not None else ""
            else:
                val = v.text if v is not None else ""
            vals[col] = val
        rows.append(vals)

    hdr = rows[0]
    cols = sorted(hdr, key=lambda c: (len(c), c))
    header = [hdr[c] for c in cols]
    out = []
    for r in rows[1:]:
        out.append({h: r.get(c, "") for c, h in zip(cols, header)})
    return out


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def truthy(x):
    return str(x).strip().lower() in ("1", "true", "yes")


def main(paths):
    for path in paths:
        rows = read_sheet(path)
        print("=" * 100)
        print(f"{path}   rows={len(rows)}")
        print("=" * 100)

        groups = {}
        for r in rows:
            if not truthy(r.get("Is Feasible", "")):
                continue  # keep the same population as the workbook's feasible_summary
            key = (num(r.get("Budget", 0)), round(num(r.get("w_exec", 0)), 3))
            groups.setdefault(key, []).append(r)

        print(
            f"{'budget':>8} {'w_exec':>6} {'n':>3} | "
            f"{'AGENT red%':>10} {'SAFE red%':>9} {'gap':>7} | "
            f"{'safety%':>7} {'BVS':>5} {'steps':>6} {'viol%':>6}"
        )
        print("-" * 100)
        for (budget, w), g in sorted(groups.items()):
            n = len(g)
            agent = sum(num(r.get("Agent Cost Reduction (%)")) for r in g) / n
            safe = sum(num(r.get("Safe Cost Reduction (%)")) for r in g) / n
            sact = 100.0 * sum(truthy(r.get("Safety Activated")) for r in g) / n
            bvs = sum(num(r.get("Best Valid Step")) for r in g) / n
            steps = sum(num(r.get("Total Steps")) for r in g) / n
            viol = 100.0 * sum(truthy(r.get("Agent Violated")) for r in g) / n
            print(
                f"{budget:>8} {w:>6} {n:>3} | "
                f"{agent:>10.2f} {safe:>9.2f} {agent - safe:>7.2f} | "
                f"{sact:>7.1f} {bvs:>5.1f} {steps:>6.1f} {viol:>6.1f}"
            )
        print()


if __name__ == "__main__":
    main(sys.argv[1:] or ["resultsABench_500k_sweep.xlsx", "resultsABench_500k_dnn.xlsx"])
