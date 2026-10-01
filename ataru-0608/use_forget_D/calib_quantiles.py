"""腕 D の較正（2026-10-01 昼の予約の委任書 3 節）：τ＝−∞ の走行の side/*/seed*.useforget_S.f64（試行 100 以降の各試行の終わりの、
生きている全部の席の S）を集め、二つの世界を合わせた 25・50・75・90% 点と、世界ごとの値を出す。
分位点の定め方（仮の決定）：並べた値の線形補間（numpy の既定 type 7 と同じ）：位置 q·(n−1)。"""
import glob
import json
import sys
from array import array


def q7(v, q):
    h = q * (len(v) - 1)
    i = int(h)
    return v[i] if i + 1 >= len(v) else v[i] + (h - i) * (v[i + 1] - v[i])


def load(pattern):
    a = array("d")
    files = sorted(glob.glob(pattern))
    for f in files:
        with open(f, "rb") as fh:
            a.frombytes(fh.read())
    return a, files


out = {}
allv = array("d")
for w, d in (("世界 2", sys.argv[1]), ("世界 1", sys.argv[2])):
    a, files = load(f"{d}/side/*/seed*.useforget_S.f64")
    v = sorted(a)
    out[w] = {"走行": len(files), "値の数": len(v), "最小": v[0], "最大": v[-1],
              **{f"{int(q*100)}%": q7(v, q) for q in (0.25, 0.5, 0.75, 0.9)}}
    allv.extend(a)
    del v
v = sorted(allv)
out["合わせて"] = {"値の数": len(v), "最小": v[0], "最大": v[-1], **{f"{int(q*100)}%": q7(v, q) for q in (0.25, 0.5, 0.75, 0.9)}}
print(json.dumps(out, ensure_ascii=False, indent=1))
