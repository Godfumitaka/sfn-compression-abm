"""progress.tsv（外から 30 秒ごとに読んだ各本の今の試行）から、100 試行ごとの時間を出す。
区切りの時刻は、前後の標本のあいだで直線に割り振った見込み（標本の間隔 30 秒）。最初と最後の区切りは、全部を見られた区切りだけ。"""
import csv, datetime as dt, collections, sys
rows = list(csv.DictReader(open("progress.tsv"), delimiter="\t"))
by = collections.defaultdict(list)
for r in rows:
    if r["trial"] in ("", "None"): continue
    by[(r["arm"], r["seed"], r["version"])].append((dt.datetime.fromisoformat(r["time"]), int(r["trial"]), float(r["cpu_sec"]), int(r["n_running"]), float(r["load1"]), float(r["rss_gib"])))
def cross(s, k):
    """試行 k に初めて届いた時刻とその時の CPU 秒（直線で割り振る）"""
    for (t0, a, c0, *_), (t1, b, c1, *_) in zip(s, s[1:]):
        if a < k <= b:
            w = (k - a) / (b - a)
            return t0 + (t1 - t0) * w, c0 + (c1 - c0) * w
    return None, None
out = csv.writer(sys.stdout)
out.writerow(["arm", "seed", "version", "trial_start", "trial_end", "wall_sec", "cpu_sec", "cpu_over_wall", "mean_concurrent_runs", "mean_load1", "rss_gib_at_end", "start_time", "end_time"])
for key, s in sorted(by.items()):
    s.sort()
    lo, hi = s[0][1], s[-1][1]
    for b in range(0, 1800, 100):
        e = min(b + 100, 1740)
        if b <= lo or e - 1 > hi and e != 1740: continue
        ta, ca = cross(s, b); tb, cb = cross(s, e) if e < 1740 else cross(s, 1739)
        if e == 1740 and tb is None and hi >= 1739: tb, cb = s[-1][0], s[-1][2]
        if ta is None or tb is None: continue
        inside = [x for x in s if ta <= x[0] <= tb] or [s[-1]]
        w = (tb - ta).total_seconds()
        out.writerow([*key, b, e - 1, round(w, 1), round(cb - ca, 1), round((cb - ca) / w, 3) if w else "", round(sum(x[3] for x in inside) / len(inside), 2), round(sum(x[4] for x in inside) / len(inside), 2), inside[-1][5], f"{ta:%F %T}", f"{tb:%F %T}"])
