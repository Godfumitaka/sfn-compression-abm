"""較正の下見（世界 1、受け箱の指示 9）の二本を外から読むだけ。30 秒ごとに、各本の今の試行（side の seed041.jsonl の最後の trial）と、
木の常駐（v3_run.py の過程に子の過程を足す）を progress.tsv に書く。模型には触れない。二本とも終わって 10 分たったら抜ける。"""
import glob
import json
import os
import time

OUT = "/home/tatsu/calib_w1/progress.tsv"


def last_trial(p):
    with open(p, "rb") as f:
        f.seek(0, 2)
        n = f.tell()
        f.seek(max(0, n - 200000))
        data = f.read().split(b"\n")
    for line in reversed(data):
        try:
            return json.loads(line)["trial"]
        except Exception:
            pass


new = not os.path.exists(OUT)
idle_since = None
with open(OUT, "a") as out:
    if new:
        out.write("time\tcase\tpid\ttrial\trss_tree_bytes\n")
    while True:
        procs = {}
        for p in os.listdir("/proc"):
            if not p.isdigit():
                continue
            try:
                a = open(f"/proc/{p}/cmdline", "rb").read().split(b"\0")
                st = open(f"/proc/{p}/stat").read().rsplit(")", 1)[1].split()
                procs[p] = (a, st[1], int(st[21]) * 4096)
            except Exception:
                pass
        alive = 0
        for p, (a, pp, rss) in procs.items():
            if len(a) > 3 and a[1] == b"tools/v3_run.py" and b"/calib_w1/" in a[3]:
                case = a[3].decode().split("/")[-2]
                tot = rss + sum(r for q, (_a, ppq, r) in procs.items() if ppq == p)
                side = glob.glob(f"/home/tatsu/calib_w1/{case}/output/side/*/seed041.jsonl")
                t = last_trial(side[0]) if side else ""
                out.write(f"{time.strftime('%F %T')}\t{case}\t{p}\t{t}\t{tot}\n")
                alive += 1
        out.flush()
        if alive == 0:
            idle_since = idle_since or time.time()
            if time.time() - idle_since > 600:
                break
        else:
            idle_since = None
        time.sleep(30)
