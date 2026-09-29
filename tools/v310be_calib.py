"""B＋E の較正の値（委任書 2・仕様 9 節）。★ 判断しない。較正の走行の side/<セル>/seedNNN.v39cands.f64（各試行の変換の前に列挙した正の V）を
全部集め、25・50・75・90 パーセンタイル（線形補間＝numpy.percentile の既定と同じ式：位置 (n−1)q/100 で前後を按分。デスクトップの v3.10 の較正と同じ。マックの python3.12 に numpy が無いので手で書く）を λ の 4 段階とする。
重複値は統合する（同じ値の段は一つにまとめ、どの段がまとまったかを書く）。正の点が無ければ「未較正」と書く。
使い方  python3.12 tools/v310be_calib.py <較正の走行根> <出力の .md> <出力の .json>"""
import glob
import json
import os
import sys

from array import array


def percentile(sorted_v, q):
    n = len(sorted_v)
    x = (n - 1) * q / 100.0
    i = int(x)
    f = x - i
    return sorted_v[i] if i + 1 >= n else sorted_v[i] + (sorted_v[i + 1] - sorted_v[i]) * f


root, out_md, out_js = sys.argv[1:4]
per = {}
vals = []
for p in sorted(glob.glob(os.path.join(root, "side", "*", "seed*.v39cands.f64"))):
    a = array("d")
    with open(p, "rb") as f:
        a.frombytes(f.read())
    per[os.path.basename(p)[:7]] = len(a)
    vals.extend(a)
man = [json.loads(l) for l in open(os.path.join(root, "manifest.jsonl"), encoding="utf-8")]
allv = sorted(vals)
res = {"走行": len(man), "点の数": len(allv), "種ごとの点の数": per,
       "コード": sorted({m.get("code_commit") for m in man}), "最小": allv[0] if allv else None,
       "正でない点": sum(1 for v in allv if v <= 0)}
if not allv:
    res["未較正"] = True
    lam = {}
else:
    q = {k: percentile(allv, k) for k in (25, 50, 75, 90)}
    lam = {}
    merged = {}
    for k, v in q.items():
        same = [k2 for k2, v2 in lam.items() if v2 == v]
        if same:
            merged.setdefault(same[0], []).append(k)
        else:
            lam[k] = v
    res.update(パーセンタイル=q, λ=lam, 統合した段=merged)
json.dump(res, open(out_js, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
L = [f"| L{k} | {k} | {v!r} |" for k, v in res.get("パーセンタイル", {}).items()]
print("\n".join(L))
