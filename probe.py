#!/usr/bin/env python3
"""probe.py — 台帳を直接読み、三つを一度に出す（読むだけ・書き込みなし）
  1  再構成試験   棄権した試行に「言えたはずのこと」が残っているか
  2  適用あたりの棄権率   SPEC §4.6.0 の 0.79 の壁との照合
  3  六種の棄権の内訳     被覆率の低下が「候補が無い」か「基準を割る」か
"""
import gzip, json, sys, glob, os
from collections import Counter

runs = sys.argv[1] if len(sys.argv) > 1 else "runs/arm0ext_2026-08-31"
files = sorted(glob.glob(os.path.join(runs, "cells", "*", "*.jsonl.gz")))
print("走行ディレクトリ %s   台帳 %d 本" % (runs, len(files)))
if not files:
    sys.exit("★ 台帳が見つかりません")

# ── 1. 欄の実態（1 本目の先頭 400 試行）──────────────────
with gzip.open(files[0], "rt") as fh:
    first = json.loads(fh.readline())
    header = first if "code_commit" in first else None
    rows = []
    if header is None:
        rows.append(first)
    for line in fh:
        rows.append(json.loads(line))
        if len(rows) >= 400:
            break

print("\n" + "=" * 92)
print("1  欄の実態   %s" % files[0])
print("=" * 92)
if header:
    print("  ヘッダ欄 %d 本   code_commit=%s" % (len(header), header.get("code_commit")))
print("  試行行の欄 %d 本" % len(rows[0]))
print("  全欄名:\n    %s" % ", ".join(sorted(rows[0].keys())))

def nonempty(v):
    return v not in (None, [], {}, "", False)

spoke = [r for r in rows if nonempty(r.get("predicted_edge"))]
absta = [r for r in rows if nonempty(r.get("abstain_reason"))]
print("\n  口を開いた %d ／ 棄権 %d ／ 合計 %d" % (len(spoke), len(absta), len(rows)))

watch = ("predicted_edge", "predictions_all_slots", "filled_predicate",
         "slot_signature", "constituent_reason_123", "oracle_verdict",
         "R_used", "abstain_reason", "expansion_and_filling_all",
         "n_tie_candidates", "support_at_adoption")
print("\n  %-28s%12s%12s%12s" % ("欄", "全体", "口を開いた", "★ 棄権した"))
for k in watch:
    if k not in rows[0]:
        print("  %-28s%12s   ★ 欄が存在しない" % (k, "—"))
        continue
    a = sum(1 for r in rows if nonempty(r.get(k)))
    b = sum(1 for r in spoke if nonempty(r.get(k)))
    c = sum(1 for r in absta if nonempty(r.get(k)))
    print("  %-28s%12d%12d%12d" % (k, a, b, c))

print("\n  ★ 棄権した試行の実例（最大 3 件）")
for r in absta[:3]:
    print("    reason=%s  R_used=%s" % (r.get("abstain_reason"), repr(r.get("R_used"))[:40]))
    for k in ("filled_predicate", "slot_signature", "predictions_all_slots"):
        print("      %-24s %s" % (k, repr(r.get(k))[:80]))

# ── 2・3. 棄権の内訳（サンプル：各セル 3 seed）────────────
cells = sorted({os.path.basename(os.path.dirname(p)) for p in files})
sample = []
for c in cells:
    sample += sorted(glob.glob(os.path.join(runs, "cells", c, "*.jsonl.gz")))[:3]

print("\n" + "=" * 92)
print("2・3  棄権の内訳   標本 %d 本（各セル 3 seed）" % len(sample))
print("=" * 92)

per_cell = {}
commits = Counter()
for p in sample:
    c = os.path.basename(os.path.dirname(p))
    d = per_cell.setdefault(c, {"trials": 0, "rused": 0, "reasons": Counter()})
    with gzip.open(p, "rt") as fh:
        fst = json.loads(fh.readline())
        if "code_commit" in fst:
            commits[fst.get("code_commit")] += 1
            it = fh
        else:
            it = None
        lines = ([fst] if it is None else []) 
        for line in fh:
            lines.append(json.loads(line))
    for r in lines:
        d["trials"] += 1
        if nonempty(r.get("R_used")):
            d["rused"] += 1
        rs = r.get("abstain_reason")
        if rs:
            d["reasons"][rs] += 1

CHARGED = ("no_projectable_relation", "ambiguous_projection")
print("\n  %-26s%10s%10s%12s%12s" % ("セル", "試行", "R適用", "★課金対象", "★適用あたり"))
for c in sorted(per_cell):
    d = per_cell[c]
    ch = sum(d["reasons"][k] for k in CHARGED)
    rate = ch / d["rused"] if d["rused"] else float("nan")
    print("  %-26s%10d%10d%12d%12.4f" % (c, d["trials"], d["rused"], ch, rate))

print("\n  ★ SPEC §4.6.0 の壁 0.79 ／ 設計値 0.392〜0.397")

tot = Counter()
for d in per_cell.values():
    tot.update(d["reasons"])
n_ab = sum(tot.values())
print("\n  ★ 六種の内訳（標本全体 棄権 %d 件）" % n_ab)
for k, v in tot.most_common():
    print("    %-28s%8d  (%.4f)" % (k, v, v / n_ab if n_ab else 0))

print("\n  code_commit  %s" % dict(commits))
