"""走っている本番の本を外から読むだけ：30 秒ごとに、各本の今の試行（side の seed*.jsonl の最後の行の trial）、CPU 時間（/proc の utime＋stime、子の過程を足す）、常駐（子を足す）、
同時の本数、loadavg を progress.tsv に書く。本番の計算・出力には触れない（読むだけ）。"""
import glob, json, os, time
OUT = os.path.expanduser("~/slow_2026-10-06/progress.tsv"); TCK = os.sysconf("SC_CLK_TCK")
def last_trial(path):
    with open(path, "rb") as f:
        f.seek(0, 2); n = f.tell(); f.seek(max(0, n - 65536))
        lines = f.read().split(b"\n")
    for l in reversed(lines):
        try: return json.loads(l)["trial"]
        except Exception: continue
new = not os.path.exists(OUT)
with open(OUT, "a") as out:
    if new: out.write("time\tpid\tarm\tseed\tversion\ttrial\tcpu_sec\trss_gib\tn_running\tload1\n")
    while True:
        rows = []
        kids = {}
        for q in os.listdir("/proc"):
            if not q.isdigit(): continue
            try:
                sq = open(f"/proc/{q}/stat").read().rsplit(")", 1)[1].split()
                kids.setdefault(sq[1], []).append(((int(sq[11]) + int(sq[12])) / TCK, int(sq[21]) * 4096 / 2**30))
            except Exception: continue
        for p in os.listdir("/proc"):
            if not p.isdigit(): continue
            try:
                a = open(f"/proc/{p}/cmdline", "rb").read().split(b"\0")
                if len(a) < 4 or a[1] != b"tools/v3_run.py" or b"/smeprod_a/sme/" not in a[3]: continue
                st = open(f"/proc/{p}/stat").read().rsplit(")", 1)[1].split()
                cpu = (int(st[11]) + int(st[12])) / TCK + sum(c for c, _ in kids.get(p, [])); rss = int(st[21]) * 4096 / 2**30 + sum(r for _, r in kids.get(p, []))
                outdir = a[3].decode(); arm, seed = outdir.split("/")[-2], outdir.split("/")[-1]
                ver = os.path.basename(os.readlink(f"/proc/{p}/cwd"))
                side = glob.glob(f"{outdir}/side/*/seed*[0-9].jsonl")
                tr = last_trial(side[0]) if side else None
                rows.append((p, arm, seed, ver, tr, cpu, rss))
            except Exception: continue
        t = time.strftime("%F %T"); load = open("/proc/loadavg").read().split()[0]
        for r in rows: out.write(f"{t}\t{r[0]}\t{r[1]}\t{r[2]}\t{r[3]}\t{r[4]}\t{r[5]:.2f}\t{r[6]:.2f}\t{len(rows)}\t{load}\n")
        out.flush(); time.sleep(30)
