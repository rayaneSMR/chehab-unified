#!/usr/bin/env python3
"""
Measure the FULL memory footprint of generated HEonGPU programs (not only the HEonGPU pool peak).

For every circuit binary in a manifest it records, per repetition:
  dev_delta_mib  device-wide GPU memory peak minus the idle baseline just before launch
                 (= pool + CUDA context + driver + cuFFT/NTT workspaces + anything outside the pool;
                  needs a GPU that no other job is using -> request it exclusively)
  proc_peak_mib  NVML per-process peak GPU memory (includes the context; may be missing in containers)
  host_rss_mib   peak resident host memory of the process (wait4 ru_maxrss: exact, not sampled)
  host_vmhwm_mib VmHWM polled from /proc (cross-check)
  pool_stdout    HEonGPU pool peak parsed from stdout with --pool-regex (optional, same run)

Manifest CSV:  id,binary[,args]      (one row per circuit; add rows 'ctx_probe_*' for the bare-CUDA probe)
Ref CSV (optional, e.g. set400_repacked_fix.csv / negate_compare.csv): columns id,N,L,G,est,real
  are joined by id so the output is ready for fit_gpu_full.py.
"""
import argparse, csv, os, re, shlex, statistics, subprocess, sys, tempfile, threading, time

MIB = 1024.0 * 1024.0
try:
    import pynvml
    pynvml.nvmlInit()
    HAVE_NVML = True
except Exception:
    HAVE_NVML = False


class DevMon(threading.Thread):
    """Polls device-wide used memory (and this pid's usage) until stopped."""

    def __init__(self, idx, pid, interval):
        super().__init__(daemon=True)
        self.idx, self.pid, self.iv = idx, pid, interval
        self.stop_ev = threading.Event()
        self.dev_peak = 0.0
        self.proc_peak = 0.0
        if HAVE_NVML:
            self.h = pynvml.nvmlDeviceGetHandleByIndex(idx)

    def _dev_used(self):
        if HAVE_NVML:
            return pynvml.nvmlDeviceGetMemoryInfo(self.h).used / MIB
        out = subprocess.run(["nvidia-smi", f"--id={self.idx}", "--query-gpu=memory.used",
                              "--format=csv,noheader,nounits"], capture_output=True, text=True).stdout
        return float(out.strip().splitlines()[0])

    def run(self):
        while not self.stop_ev.is_set():
            try:
                self.dev_peak = max(self.dev_peak, self._dev_used())
                if HAVE_NVML:
                    for p in pynvml.nvmlDeviceGetComputeRunningProcesses(self.h):
                        if p.pid == self.pid and p.usedGpuMemory is not None:
                            self.proc_peak = max(self.proc_peak, p.usedGpuMemory / MIB)
            except Exception:
                pass
            time.sleep(self.iv)


def idle_baseline(idx, n=7):
    mon = DevMon(idx, -1, 0)
    vals = []
    for _ in range(n):
        vals.append(mon._dev_used())
        time.sleep(0.05)
    return statistics.median(vals)


def read_status_kb(pid, key):
    try:
        with open(f"/proc/{pid}/status") as f:
            for line in f:
                if line.startswith(key):
                    return int(line.split()[1])
    except Exception:
        pass
    return 0


def run_one(cmd, idx, poll_dev, timeout):
    idle = idle_baseline(idx)
    out = tempfile.NamedTemporaryFile("w+", suffix=".out", delete=False)
    t0 = time.time()
    p = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT)
    mon = DevMon(idx, p.pid, poll_dev)
    mon.start()
    hwm = 0
    ru = None
    rc = -1
    while True:
        wpid, status, ru = os.wait4(p.pid, os.WNOHANG)
        if wpid:
            rc = os.waitstatus_to_exitcode(status)
            break
        hwm = max(hwm, read_status_kb(p.pid, "VmHWM:"))
        if time.time() - t0 > timeout:
            p.kill()
        time.sleep(0.002)
    p.returncode = rc
    time.sleep(0.05)
    mon.stop_ev.set()
    mon.join()
    out.flush(); out.seek(0)
    text = out.read(); out.close(); os.unlink(out.name)
    return dict(dev_idle_mib=idle, dev_peak_mib=mon.dev_peak,
                dev_delta_mib=max(0.0, mon.dev_peak - idle), proc_peak_mib=mon.proc_peak,
                host_rss_mib=ru.ru_maxrss / 1024.0, host_vmhwm_mib=hwm / 1024.0,
                rc=rc, wall_s=time.time() - t0), text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--ref", action="append", default=[], help="reference CSV(s) with id,N,L,G,est,real")
    ap.add_argument("--out", default="totals_raw.csv")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--gpu-index", type=int, default=0)
    ap.add_argument("--poll-ms", type=float, default=5.0, help="device polling interval")
    ap.add_argument("--timeout", type=float, default=900)
    ap.add_argument("--pool-regex", default=None, help="regex with 1 group: pool peak MiB in stdout")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    ref = {}
    for path in a.ref:
        for r in csv.DictReader(open(path)):
            ref[r["id"]] = r
    rows = list(csv.DictReader(open(a.manifest)))
    if a.limit:
        rows = rows[:a.limit]
    rx = re.compile(a.pool_regex) if a.pool_regex else None
    if HAVE_NVML:
        print("GPU:", pynvml.nvmlDeviceGetName(pynvml.nvmlDeviceGetHandleByIndex(a.gpu_index)))
    else:
        print("WARNING: pynvml missing, using nvidia-smi polling (coarse, may miss short peaks)")
    fields = ["id", "N", "L", "G", "est", "pool_real", "rep", "dev_idle_mib", "dev_peak_mib", "dev_delta_mib",
              "proc_peak_mib", "host_rss_mib", "host_vmhwm_mib", "pool_stdout", "rc", "wall_s"]
    with open(a.out, "w", newline="") as fo:
        w = csv.DictWriter(fo, fieldnames=fields)
        w.writeheader()
        for i, r in enumerate(rows):
            cmd = [r["binary"]] + shlex.split(r.get("args") or "")
            rf = ref.get(r["id"], {})
            for rep in range(a.reps):
                m, text = run_one(cmd, a.gpu_index, a.poll_ms / 1000.0, a.timeout)
                pool = ""
                if rx:
                    ms = rx.findall(text)
                    if ms:
                        pool = max(float(x) for x in ms)
                row = dict(id=r["id"], N=rf.get("N", ""), L=rf.get("L", ""), G=rf.get("G", ""),
                           est=rf.get("est", ""), pool_real=rf.get("real", ""), rep=rep, pool_stdout=pool, **m)
                row = {k: (round(v, 3) if isinstance(v, float) else v) for k, v in row.items()}
                w.writerow(row); fo.flush()
                print(f"[{i+1}/{len(rows)}] {r['id']} rep{rep} dev+{row['dev_delta_mib']} MiB "
                      f"host {row['host_rss_mib']} MiB rc={m['rc']}", flush=True)


if __name__ == "__main__":
    main()
