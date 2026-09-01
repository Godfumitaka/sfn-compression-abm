#!/usr/bin/env python3
"""probe2.py — 判断1 と U-09h の材料を台帳から出す（読むだけ）
  A  def ごとの p_R と (1-p_R)/p_R の分布   ← Pro の検算8・9
  B  棄権理由の 試行あたり絶対数            ← U-09h
"""
import gzip, json, sys, glob, os, statistics
from collections import Counter, defaultdict

runs = sys.argv[1] if len(sys.argv) > 1 else "runs/main_2026-08-31"
cells = sorted({os.path.basename(os.path.dirname(p))
                for p in glob.glob(os.path.join(runs, "cells", "*", "*.jsonl.gz"))})
sample = []
for c in cells:
    sample += sorted(glob.glob(os.path.join(runs, "cells", c, "*.jsonl.gz")))[:3]
print("%s   標本 %d 本 / %d セル" % (runs, len(sample), len(cells)))

def rows_of(path):
    with gzip.open(path, "rt") as fh:
        first = json.loads(fh.readline())
        if "code_commit" not in first:
            yield first
        for line in fh:
            yield json.loads(line)

# ── A. p_R の分布 ────────────────────────────────
allratio, topratio, restratio = [], [], []
for p in sample:
    used = Counter(); n = 0
    for r in rows_of(p):
        n += 1
        ru = r.get("R_used")
        if ru:
            used[ru if isinstance(ru, str) else str(ru)] += 1
    if not n or not used:
        continue
    rank = used.most_common()
    for i, (name, c) in enumerate(rank):
        pr = c / n
        if pr <= 0 or pr >= 1:
            continue
        v = (1 - pr) / pr
        allratio.append(v)
        (topratio if i < 5 else restratio).append(v)

def show(label, xs):
    if not xs:
        print("  %-14s（該当なし）" % label); return
    xs = sorted(xs)
    q = lambda f: xs[min(len(xs) - 1, int(len(xs) * f))]
    print("  %-14s n=%6d  中央 %8.2f  四分位 %8.2f–%8.2f  最小 %7.3f  最大 %9.1f"
          % (label, len(xs), q(.5), q(.25), q(.75), xs[0], xs[-1]))

print("\n" + "=" * 96)
print("A  (1−p_R)/p_R の分布   ★ Pro の推定：上位 7.1〜8.1 ／ 非上位 289〜419")
print("=" * 96)
show("全 def", allratio); show("★ 上位5本", topratio); show("★ 6位以下", restratio)
print("\n  ★ β 項が第一項を上回る条件  D_β = β·((1−p_R)/p_R)·(P_ext/P) > 1")
for label, xs in (("上位5本", topratio), ("6位以下", restratio)):
    if xs:
        m = sorted(xs)[len(xs)//2]
        print("    %-10s 中央 %8.2f  →  β=1 で P_ext/P > %.4f ／ β=0.5 で > %.4f"
              % (label, m, 1/m, 2/m))

# ── B. 棄権理由の絶対数 ──────────────────────────
print("\n" + "=" * 96)
print("B  棄権理由の 試行あたり件数   ★ U-09h（割合ではなく絶対数で見る）")
print("=" * 96)
per = defaultdict(lambda: [Counter(), 0])
for p in sample:
    c = os.path.basename(os.path.dirname(p))
    for r in rows_of(p):
        per[c][1] += 1
        rs = r.get("abstain_reason")
        if rs:
            per[c][0][rs] += 1
keys = ("no_projectable_relation", "below_tau", "no_definition", "no_prototype")
print("\n  %-30s%9s%12s%12s%10s%10s" % ("セル", "試行", "no_proj", "below_tau", "no_def", "no_proto"))
for c in sorted(per):
    cnt, n = per[c]
    print("  %-30s%9d%12.4f%12.4f%10.4f%10.4f"
          % (c, n, *[cnt[k] / n for k in keys]))
