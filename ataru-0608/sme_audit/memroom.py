"""新しい本（6e93e0b、最大 2.5GiB）を始めても、メモリの空きが 4GiB 以上残るかを見積もる。"ok" か "wait" を出す。--show で中身を出す。
走っている本：引数が tools/v3_run.py で出力先が ~/smeprod/sme/ の過程。その子（multiprocessing の子）の使用も足す。
版は、走っている本の作業場所（/proc/<pid>/cwd）で分ける：smerng＝6e93e0b（最大 2.5GiB）、それ以外（smefast・sme）は最大 4.3GiB。"""
import os
import sys

GIB = 1024 ** 3


def meminfo():
    d = {}
    for line in open("/proc/meminfo"):
        k, v = line.split(":")
        d[k] = int(v.split()[0]) * 1024
    return d


procs = {}
for p in os.listdir("/proc"):
    if not p.isdigit():
        continue
    try:
        args = open(f"/proc/{p}/cmdline", "rb").read().split(b"\0")
        st = open(f"/proc/{p}/stat").read().split()
        rss = int(st[23]) * 4096
        procs[int(p)] = (args, int(st[3]), rss)
    except Exception:
        continue
need = 0
runs = []
for pid, (args, ppid, rss) in procs.items():
    a = [x.decode(errors="ignore") for x in args]
    if len(a) > 1 and a[1] == "tools/v3_run.py" and any("/home/tatsu/smeprod/sme/" in x for x in a):
        tot = rss + sum(r for q, (_a, pp, r) in procs.items() if pp == pid)
        try:
            cwd = os.readlink(f"/proc/{pid}/cwd")
        except Exception:
            cwd = ""
        peak = 2.5 * GIB if cwd.endswith("smerng") else 4.3 * GIB
        need += max(0, peak - tot)
        runs.append((pid, round(tot / GIB, 2), "6e93e0b" if cwd.endswith("smerng") else "4.3GiB の版"))
avail = meminfo()["MemAvailable"]
left = avail - 2.5 * GIB - need
if "--show" in sys.argv:
    print(f"空き {avail / GIB:.1f}GiB、走っている本のこれからの増え {need / GIB:.1f}GiB、始めたあとに残る見込み {left / GIB:.1f}GiB")
else:
    print("ok" if left >= 4 * GIB else "wait")
