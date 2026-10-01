"""f を振る格子（2026-10-01 夜の委任書）の報告の表。後づけの集計だけ。使い方：tables.py <腕…>  → 標準出力に markdown。
材料：tables/<腕>/trials.tsv.gz（全部の種の試行ごとの表：正誤・棄権・ドア・店の型・日・記憶のビット）、
  <腕>/side/*/seed*.answers.csv（答えた試行：答えた定義 R・R_born・支持の割合 support_ratio・当たり hit）、
  <腕>/side/*/seed*.shop.jsonl（シール・link の席の状態の変化：生まれた・F→H・H→U・U→H・定義ごと消えた。tools/shopworld.py）。
シールの席の状態（予測の時点）：その定義（名前＋生まれた試行）のシールの席について、その試行より前の最後の変化の行き先。
  変化はその試行の会計・誕生・削除の段で起きる（予測のあと）ので、同じ試行の変化は入れない。シールの席が生まれていない定義は「席なし」。
  席が二つ以上なら状態を / で並べる。
シールの席の状態の時間変化：各試行の予測の時点で生きているシールの席を状態ごとに数え、174 試行ずつ・種あたりの平均。"""
import csv
import glob
import gzip
import json
import os
import statistics
import sys
from collections import Counter, defaultdict

OUT = os.path.expanduser("~/fgrid")


def opn(p):
    return gzip.open(p, "rt", encoding="utf-8") if p.endswith(".gz") else open(p, encoding="utf-8")


def cwa(rows):
    n = len(rows)
    c = sum(1 for r in rows if r[3] == "c")
    w = sum(1 for r in rows if r[3] == "w")
    return f"{c:,}・{w:,}・{n - c - w:,}"


T1, T2, T3, T4 = [], [], [], []
for arm in sys.argv[1:]:
    rows = [l.rstrip("\n").split("\t") for l in gzip.open(f"{OUT}/tables/{arm}/trials.tsv.gz", "rt", encoding="utf-8")][1:]
    TR = {(int(r[0]), int(r[1])): r for r in rows}
    bits = statistics.fmean(float(r[9]) for r in rows)
    dn = [r for r in rows if r[5] == "1" and r[7] == "n"]
    de = [r for r in rows if r[5] == "1" and r[7] == "e"]
    T1.append(f"| {arm} | {bits:,.0f} | {cwa(rows)} | {cwa(dn)} | {cwa(de)} |")
    ratio = Counter()
    seal_w = Counter()
    seal_all = Counter()
    bins = defaultdict(Counter)
    nb = Counter()
    for sp in sorted(glob.glob(f"{OUT}/{arm}/side/*/seed*.shop.jsonl*")):
        seed = int(os.path.basename(sp)[4:7])
        ev = defaultdict(list)       # (R, reg, slot) → [(試行, 行き先)]
        for line in opn(sp):
            r = json.loads(line)
            if r.get("kind") == "shop_seat" and r.get("which") == "sig":
                ev[(r["R"], r["reg"], r["slot"])].append((r["trial"], r["to"]))
        by_def = defaultdict(list)
        for k in ev:
            by_def[(k[0], k[1])].append(k)

        def state_at(k, t):
            st = None
            for tt, to in ev[k]:
                if tt < t:
                    st = to
                else:
                    break
            return st

        # 時間変化：試行ごとの、生きているシールの席の状態
        trans = sorted((tt, k, to) for k, es in ev.items() for tt, to in es)
        cur = {}
        j = 0
        for t in range(1740):
            while j < len(trans) and trans[j][0] < t:
                _tt, k, to = trans[j]
                if to in ("F", "H", "U"):
                    cur[k] = to
                else:
                    cur.pop(k, None)
                j += 1
            b = min(t // 174, 9)
            cnt = Counter(cur.values())
            for s in ("F", "H", "U"):
                bins[b][s] += cnt[s]
            nb[b] += 1
        ap = os.path.join(os.path.dirname(sp), f"seed{seed:03d}.answers.csv")
        for a in csv.DictReader(open(ap, encoding="utf-8")):
            t = int(a["trial"])
            if a["hit"] != "0":
                continue
            r = TR[(seed, t)]
            ks = by_def.get((a["R"], int(a["R_born"])), [])
            sts = [state_at(k, t) for k in ks]
            sts = [s for s in sts if s in ("F", "H", "U")]
            sk = "席なし" if not sts else "／".join(sorted(sts))
            seal_all[sk] += 1
            if r[5] == "1" and r[7] == "e":
                sr = float(a["support_ratio"]) if a["support_ratio"] not in ("", None) else None
                ratio["1" if sr is not None and sr >= 1.0 - 1e-12 else "1 未満"] += 1
                seal_w[sk] += 1
    T2.append(f"| {arm} | {ratio['1']:,} | {ratio['1 未満']:,} | " + "、".join(f"{k} {v:,}" for k, v in sorted(seal_w.items())) +
              " | " + "、".join(f"{k} {v:,}" for k, v in sorted(seal_all.items())) + " |")
    T3.append(f"| {arm} | " + " | ".join(f"{bins[b]['F'] / nb[b]:.1f}／{bins[b]['H'] / nb[b]:.1f}／{bins[b]['U'] / nb[b]:.1f}" for b in range(10)) + " |")

print("### 学習期間中の平均の記憶のビットと、正解・誤答・棄権（種 1〜20 の和）\n")
print("| 腕 | 平均の記憶のビット | 全課題 正解・誤答・棄権 | ドア・通常 | ドア・例外 |\n|---|---:|---|---|---|")
print("\n".join(T1))
print("\n### 例外の日のドアの誤答：支持の割合と、誤答した定義のシールの席の状態\n")
print("| 腕 | 支持の割合 1 | 1 未満 | シールの席の状態（例外の日のドアの誤答） | シールの席の状態（全部の誤答、参考） |\n|---|---:|---:|---|---|")
print("\n".join(T2))
print("\n### シールの席の状態の時間変化（予測の時点で生きているシールの席の数 F／H／U、種あたり・試行あたりの平均、174 試行ずつ）\n")
print("| 腕 | " + " | ".join(f"{b*174}〜" for b in range(10)) + " |\n|---|" + "---|" * 10)
print("\n".join(T3))
