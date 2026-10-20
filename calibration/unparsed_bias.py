import contextlib, io, multiprocessing as mp, re, sys, collections, statistics as st
import memory
def feat(e):
    d = m = 0
    for c in e:
        if c == "(": d += 1; m = max(m, d)
        elif c == ")": d -= 1
    return dict(chars=len(e), depth=m, ops=len(re.findall(r"\((?:[+*-]|Vec)\b", e)),
                inputs=len(set(re.findall(r"\b[A-Za-z_]\w*\d\w*\b", e))),
                neg=len(re.findall(r"\(- [A-Za-z0-9_]+\)|\(- \(", e)))
def one(e):
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            b = memory.peak_ram_breakdown(e, margin=False)
        return ("ok", b["mb"], feat(e), "")
    except Exception as ex:
        return ("fail", None, feat(e), type(ex).__name__ + ": " + str(ex)[:80])
if __name__ == "__main__":
    mp.set_start_method("fork")
    lines = [l.strip() for l in open("datasets/final_llm_dataset.txt") if l.strip()]
    with mp.Pool() as p: res = p.map(one, lines, chunksize=200)
    ok = [r for r in res if r[0] == "ok"]; bad = [r for r in res if r[0] == "fail"]
    print("lines", len(lines), "ok", len(ok), "fail", len(bad))
    print("failure reasons:", collections.Counter(r[3] for r in bad).most_common(6))
    for k in ("chars", "depth", "ops", "inputs", "neg"):
        a = [r[2][k] for r in ok]; b = [r[2][k] for r in bad]
        if b: print(f"{k:7s} ok median {st.median(a):8.1f} p90 {sorted(a)[int(.9*len(a))]:8.1f} | fail median {st.median(b):8.1f} p90 {sorted(b)[int(.9*len(b))]:8.1f}")
    with open("/scratch/rs10728/heongpu-project/pilot/unparsed_lines.txt", "w") as f:
        for (s, _, _, _), l in zip(res, lines):
            if s == "fail": f.write(l + "\n")
