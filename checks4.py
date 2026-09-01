#!/usr/bin/env python3
"""
checks4.py — 検算11〜13（analysis4/per_def.jsonl。rev6 の alive_preds / dead_preds を使う）

作成 2026-08-30 夜

検算11  ★ 生き残るのは汎用述語か（神話の担い手の特定）
        台帳の読み（2026-08-22 検算F ／ 2026-08-28 実測）
          塔 allow(媒介, 核一階) は ★ 四モチーフ全部 にある（π_tower = 1.0）
          cause は M2・M3・M4 の三つにある（M1 だけ require）
          carry は M2 の核一階1・M1/M3 の周縁A（共有述語。q_share = 2/3）
          8/28 の縦断実測では、走行最頻の神話が m=2 で allow ＋ cause だった
        ★ 本検算はこの読みを 178,000 本の規模で検査する。
          述語ごとの生存率 ＝ 生存本数 /（生存 ＋ 墓石）を出す。
        ★ 汎用述語ほど生存率が高ければ、「薄化は汎用述語を残す」が機構として言える。

検算12  E2（R の忘却）が 2 件しかないのはなぜか
        該当する def の顔ぶれをそのまま出す。

検算13  モチーフ層別の薄化（★ 事後の当てはめではない）
        2026-08-22 の検算F が立てた予言：
          M1 は m=4 で止まる（OA 0.000。他モチーフと共有する核述語を持たない）
          M2 は共有述語 carry 経由で m=2 まで行く（OA 0.502）
        ★ 予言は走行前に台帳にあるので、これは事前登録された検査である。

★ 本スクリプトは E3・τ_settle・段階2 のいずれにも依存しない。

使い方
  python3 checks4.py --per-def analysis4/per_def.jsonl
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

KEEP = ("f", "theta_prime", "repair_scope", "adoptions", "m_live_final", "m_alloc",
        "motif", "thin", "alive_preds", "dead_preds", "E2_time", "R", "cell", "seed")

# 台帳 3-1 の最終四モチーフ表から。★ 走行前に確定している分類（2026-08-19 構造確定）
ROLE = {
    "allow": "塔（全4モチーフ）",
    "cause": "核高階（M2 M3 M4）",
    "require": "核高階（M1 のみ）",
    "carry": "共有述語（M2 核 ／ M1 M3 周縁A）",
    "hold": "核一階（M1）", "push": "核一階（M1 M4）",
    "lift": "核一階（M2）", "break": "核一階（M3）",
    "cut": "核一階（M3）", "turn": "核一階（M4）",
    "cold": "周縁A（M2）", "hard": "周縁A（M4）",
}
MYTH_M = 2          # U-071（確定 2026-08-21）


def load(path: Path):
    rows = []
    with open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                record = json.loads(line)
                rows.append({k: record.get(k) for k in KEEP})
    return rows


def fmt(value, width=12, digits=4):
    return "%*s" % (width, "—") if value is None else "%*.*f" % (width, digits, value)


# ══════════════════════════════════════════════════════════════
def check11(rows, thetas):
    print("\n" + "=" * 100)
    print("検算11  ★ 生き残るのは汎用述語か — 述語ごとの生存率")
    print("=" * 100)

    usable = [r for r in rows if r.get("alive_preds") is not None]
    if not usable:
        print("  ★ alive_preds がありません（rev6 の出力を使ってください）")
        return

    alive = Counter()
    dead = Counter()
    for record in usable:
        alive.update(record["alive_preds"] or ())
        dead.update(record["dead_preds"] or ())
    total = Counter()
    total.update(alive); total.update(dead)

    print("\n  全体（%d 本の def から）" % len(usable))
    print("  %-14s%12s%12s%12s   %s"
          % ("述語", "生存率", "生存本数", "墓石本数", "種における役"))
    for name, count in total.most_common(24):
        if count < 50:
            continue
        print("  %-14s%s%12d%12d   %s"
              % (name, fmt(alive[name] / count), alive[name], dead[name],
                 ROLE.get(name, "媒介の袋 ／ glue ／ 役割ユナリー")))

    print("\n  ★ θ′ 別の生存率（主要な述語だけ）")
    watch = [p for p in ("allow", "cause", "require", "carry", "hold",
                         "push", "lift", "break", "cut", "turn", "cold", "hard")
             if total.get(p, 0) >= 50]
    print("  %-14s%s" % ("述語", "".join("%12.4f" % t for t in thetas)))
    for name in watch:
        cells = []
        for theta in thetas:
            picked = [r for r in usable if r["theta_prime"] == theta]
            a = sum((r["alive_preds"] or ()).count(name) for r in picked)
            d = sum((r["dead_preds"] or ()).count(name) for r in picked)
            cells.append(a / (a + d) if (a + d) else None)
        print("  %-14s%s" % (name, "".join(fmt(c) for c in cells)))

    print("\n  ★ 神話（m_live ≤ %d）の def に残っている述語" % MYTH_M)
    myths = [r for r in usable
             if r.get("m_live_final") is not None and r["m_live_final"] <= MYTH_M]
    if myths:
        inside = Counter()
        weighted = Counter()
        for record in myths:
            inside.update(record["alive_preds"] or ())
            for name in (record["alive_preds"] or ()):
                weighted[name] += record.get("adoptions") or 0
        n = len(myths)
        wtotal = sum(weighted.values()) or 1
        print("  神話 def %d 本\n" % n)
        print("  %-14s%14s%14s   %s" % ("述語", "出現率", "採択加重", "種における役"))
        for name, count in inside.most_common(14):
            print("  %-14s%14.4f%14.4f   %s"
                  % (name, count / n, weighted[name] / wtotal,
                     ROLE.get(name, "媒介の袋 ／ glue ／ 役割ユナリー")))

        print("\n  ★ 神話 def の述語の組（上位 10）")
        pairs = Counter(tuple(r["alive_preds"] or ()) for r in myths)
        for combo, count in pairs.most_common(10):
            print("  %-46s%8d  (%.4f)" % (" + ".join(combo) or "（空）",
                                          count, count / n))

    print("""
  読み方
    ★ allow（四モチーフ全部にある塔）の生存率が他より高い
      → 「薄化は汎用述語を残す」が機構として言える。★ 賭けC の担い手の特定
    ★ 生存率が述語によらず一様
      → 削除は内容に無関係な淘汰であり、神話の担い手という話は立たない
    ★ 神話 def の組が allow ＋ cause に集中
      → 8/28 の縦断実測（走行最頻の神話）が 178,000 本の規模で再現されたことになる
""")


def check12(rows):
    print("\n" + "=" * 100)
    print("検算12  E2（R の忘却）に該当した def の顔ぶれ")
    print("=" * 100)
    dead = [r for r in rows if r.get("E2_time") is not None]
    print("\n  該当 %d 本" % len(dead))
    for record in dead[:20]:
        print("  cell=%s seed=%s R=%s  θ′=%s f=%s  m_alloc=%s 採択=%s"
              % (record.get("cell"), record.get("seed"), record.get("R"),
                 record.get("theta_prime"), record.get("f"),
                 record.get("m_alloc"), record.get("adoptions")))
        print("      墓石述語 %s" % (record.get("dead_preds") or "—"))
    print("""
  読み方
    ★ 178,000 本中この本数しか無いことは、M-048（終端は E2 と E3 の競合）の
      前提が経験的に成り立っていないことを意味する。競合事象になっていない
    ★ 顔ぶれに規則性があれば、床の性質（検算10）と突き合わせる
""")


def check13(rows, thetas):
    print("\n" + "=" * 100)
    print("検算13  モチーフ層別の薄化（★ 2026-08-22 検算F の予言の検査）")
    print("=" * 100)
    print("\n  予言  M1 は m=4 で止まる（共有する核述語を持たない）")
    print("        M2 は共有述語 carry 経由で m=2 まで行く\n")

    motifs = sorted({r["motif"] for r in rows if r.get("motif")})
    if not motifs:
        print("  ★ motif 欄がありません")
        return
    print("  %-8s%s%10s" % ("モチーフ", "".join("%12.4f" % t for t in thetas), "n"))
    print("  （値 ＝ m_live ≤ %d の割合）" % MYTH_M)
    for motif in motifs:
        cells, n = [], 0
        for theta in thetas:
            picked = [r["m_live_final"] for r in rows
                      if r["motif"] == motif and r["theta_prime"] == theta
                      and r["m_live_final"] is not None]
            n += len(picked)
            cells.append(sum(1 for m in picked if m <= MYTH_M) / len(picked)
                         if picked else None)
        print("  %-8s%s%10d" % (motif, "".join(fmt(c) for c in cells), n))

    print("\n  m_live 平均")
    print("  %-8s%s" % ("モチーフ", "".join("%12.4f" % t for t in thetas)))
    for motif in motifs:
        cells = []
        for theta in thetas:
            picked = [r["m_live_final"] for r in rows
                      if r["motif"] == motif and r["theta_prime"] == theta
                      and r["m_live_final"] is not None]
            cells.append(statistics.fmean(picked) if picked else None)
        print("  %-8s%s" % (motif, "".join(fmt(c) for c in cells)))

    print("""
  読み方
    ★ M1 だけ m≤2 の割合が低い    予言どおり。★ 走行前に立てた予言が当たったことになる
    ★ モチーフ間で差が無い        予言は外れ。共有述語の効きは薄化には出ていない
    ★ モチーフは供給場面の最頻値で割り当てている（M-067 の下では一意でない）。
      Fable の依頼L (1) は「モチーフは場面側の列であって def の属性ではない」と述べている。
      → ★ この層別は探索であり、確定的な検査ではない
""")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-def", required=True)
    args = parser.parse_args()
    rows = load(Path(args.per_def))
    thetas = sorted({r["theta_prime"] for r in rows if r["theta_prime"] is not None})
    print("読み込み  %s（def %d 行）" % (args.per_def, len(rows)))
    print("★ E3・τ_settle・段階2 のいずれにも依存しない")
    check11(rows, thetas)
    check13(rows, thetas)
    check12(rows)


if __name__ == "__main__":
    main()
