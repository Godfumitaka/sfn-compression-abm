"""新しい本（最大 NEWPEAK GiB、引数）を始めても、メモリの空きが 4GiB 以上残るかを見積もる。"ok" か "wait" を出す。--show で中身。
走っている本：引数の二つめが tools/v3_run.py の過程すべて（出力先を問わない）と、SME の係の観測の包み（observe_cpu_01.py）。子の過程の使用も足す。
各本の最大：作業場所の名前で ~/queue/peaks.json（{"作業場所の名前": GiB}）を引き、無ければ NEWPEAK と同じとみなす。"""
import json
import os
import sys

GIB = 1024 ** 3
new = float(sys.argv[1]) * GIB
try:
    peaks = json.load(open(os.path.expanduser("~/queue/peaks.json")))
except Exception:
    peaks = {}
procs = {}
for p in os.listdir("/proc"):
    if not p.isdigit():
        continue
    try:
        a = open(f"/proc/{p}/cmdline", "rb").read().split(b"\0")
        st = open(f"/proc/{p}/stat").read().rsplit(")", 1)[1].split()
        procs[p] = (a, st[1], int(st[21]) * 4096)
    except Exception:
        continue
need = 0
for p, (a, pp, rss) in procs.items():
    if len(a) > 1 and (a[1] == b"tools/v3_run.py" or a[1].endswith(b"observe_cpu_01.py")):
        tot = rss + sum(r for q, (_a, ppq, r) in procs.items() if ppq == p)
        try:
            cwd = os.path.basename(os.readlink(f"/proc/{p}/cwd"))
        except Exception:
            cwd = ""
        need += max(0, peaks.get(cwd, new / GIB) * GIB - tot)
avail = next(int(l.split()[1]) * 1024 for l in open("/proc/meminfo") if l.startswith("MemAvailable:"))
left = avail - new - need
if "--show" in sys.argv:
    print(f"空き {avail / GIB:.1f}GiB、走っている本のこれからの増え {need / GIB:.1f}GiB、始めたあとに残る見込み {left / GIB:.1f}GiB")
else:
    print("ok" if left >= 4 * GIB else "wait")
