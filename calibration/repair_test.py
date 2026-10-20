import contextlib, io, statistics as st, signal
class TO(Exception): pass
def _h(a, b): raise TO()
signal.signal(signal.SIGALRM, _h)
timeouts = 0
import memory
ok = bad = 0; mbs = []
for l in open("/scratch/rs10728/heongpu-project/pilot/unparsed_lines.txt"):
    l = l.strip(); d = l.count("(") - l.count(")")
    if d <= 0: bad += 1; continue
    try:
        signal.alarm(10)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            mbs.append(memory.peak_ram_breakdown(l + ")" * d, margin=False)["mb"])
        signal.alarm(0); ok += 1
    except TO: timeouts += 1; bad += 1
    except BaseException as ex:
        signal.alarm(0)
        if isinstance(ex, KeyboardInterrupt): raise
        bad += 1
print("repaired ok", ok, "still failing", bad, "of which timeouts", timeouts)
if mbs: print("MiB median %.0f p90 %.0f max %.0f; above 1500: %d" % (st.median(mbs), sorted(mbs)[int(.9*len(mbs))], max(mbs), sum(m > 1500 for m in mbs)))
