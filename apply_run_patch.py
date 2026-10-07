#!/usr/bin/env python3
"""
apply_run_patch.py - adds the extra printed metrics to RL/fhe_rl/run.py
(initial cost/noise, agent result BEFORE safety rollback, rollback flag).

Usage (from the repo root):
    python3 apply_run_patch.py                       # patches RL/fhe_rl/run.py
    python3 apply_run_patch.py path/to/run.py

Works with LF or CRLF files, is idempotent (running it twice is safe), and
changes nothing if an anchor line is not found.
"""
import re
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "RL/fhe_rl/run.py"
raw = open(path, "rb").read().decode("utf-8")
nl = "\r\n" if "\r\n" in raw else "\n"
lines = raw.replace("\r\n", "\n").split("\n")

if any("rollback_applied" in l for l in lines):
    print("already patched, nothing to do")
    sys.exit(0)


def find(pred, what, start=0):
    for i in range(start, len(lines)):
        if pred(lines[i]):
            return i
    sys.exit(f"ERROR: anchor not found: {what}  (file left unchanged)")


i_viol = find(lambda l: re.match(r"\s*agent_violated\s*=\s*final_noise\s*>\s*noise_budget", l),
              "agent_violated = final_noise > noise_budget")
i_best = find(lambda l: re.match(r"\s*final_noise\s*=\s*best_safe\[[\"']noise[\"']\]", l),
              'final_noise = best_safe["noise"]', i_viol)
i_end = find(lambda l: "'VIOLATED'" in l, "final 'VIOLATED' print", i_best)

ind0 = re.match(r"\s*", lines[i_viol]).group(0)
ind1 = re.match(r"\s*", lines[i_best]).group(0)
# the final print spans several lines: take the indent of the line that starts the statement
i_stmt = max(i for i in range(i_best, i_end + 1) if "Final noise (est)" in lines[i])
ind2 = re.match(r"\s*", lines[i_stmt]).group(0)

# edit from the bottom up so earlier indices stay valid
tail = [
    f"{ind2}# parsed by evaluate_pfe_metrics.py / run_unified_benchmarks.py",
    f'{ind2}print(f"Initial exec cost : {{initial_ops}}")',
    f'{ind2}print(f"Initial noise (est) : {{initial_noise:.2f}}")',
    f'{ind2}print(f"Agent final exec cost : {{agent_final_exec}}")',
    f'{ind2}print(f"Agent final noise (est) : {{agent_final_noise:.2f}}")',
    f'{ind2}print(f"Rollback applied : {{rollback_applied}}")',
]
# the final print may be the last line of the file without trailing newline
lines[i_end + 1:i_end + 1] = tail
lines[i_best + 1:i_best + 1] = [f"{ind1}rollback_applied = 1"]
lines[i_viol:i_viol] = [
    f"{ind0}# --- extra metrics for the evaluation script (agent output BEFORE safety rollback) ---",
    f"{ind0}agent_final_exec, agent_final_noise = final_exec, final_noise",
    f"{ind0}rollback_applied = 0",
]
open(path, "wb").write(nl.join(lines).encode("utf-8"))
print(f"patched {path} ({'CRLF' if nl == chr(13) + chr(10) else 'LF'} line endings kept)")