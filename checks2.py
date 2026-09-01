#!/usr/bin/env python3
"""
checks2.py — rev5 の新欄を使った検算（analysis3/per_def.jsonl を読む）

作成 2026-08-30 ／ checks.py の後継。checks.py は残しておくこと

検算1′  ★ 吸収の検査を「報告地平の窓の内側」で数え直す
        checks.py（rev4）は last_change を走行末まで見ていたので、
        地平 300 の外で動いた def も「汚れた」に数えていた。
        rev5 の change_times を使い、E3_C < t ≤ 段階2到達 + 300 の変化だけを数える。
        ★ rev4 の 0.5727 は上限、感度の 0.4037 は下限。真の値はこの間にある。

検算2′  ★ OA_gstar_frac（欠けた述語の割合）を m_live で層別する
        二値版 OA_gstar は m とともに 1 へ飽和する（和集合の効果）。
        E[二値] = 1 − (1−p)^m ／ E[割合] = p。割合版は m に依らないはず。
        ★ 割合版が m で平坦なら、二値版の m 依存は交絡だったと確定する。

検算4   ★ 薄化を年齢で層別する（born を使う）
        m_live_final は走行末の値なので、遅く生まれた def は薄くなる時間が短い。
        年齢（1739 − born）で層別して、θ′ の効きが年齢の交絡でないことを見る。

使い方
  python3 checks2.py --per-def analysis3/per_def.jsonl
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path

KEEP = ("f", "theta_prime", "repair_scope", "adoptions", "m_live_final", "m_alloc",
        "born", "n_changes", "change_times", "last_change", "tau_settle", "horizon",
        "stage2_b", "E3_C", "OA_gstar", "OA_gstar_frac", "OA_supply", "OA_applied",
        "n_alive_predicates")

HORIZON = 300


def load(path: Path):
    rows = []
    with open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                record = json.loads(line)
                rows.append({k: record.get(k) for k in KEEP})
    return rows


def mean(values):
    values = [v for v in values if v is not None]
    return statistics.fmean(values) if values else None


def fmt(value, width=12, digits=4):
    return "%*s" % (width, "—") if value is None else "%*.*f" % (width, digits, value)


# ══════════════════════════════════════════════════════════════
def check1_windowed(rows):
    print("\n" + "=" * 92)
    print("検算1′  U-089  吸収の検査 — ★ 報告地平の窓の内側で数え直す")
    print("=" * 92)

    scored = [r for r in rows
              if r.get("stage2_b") is not None and r.get("E3_C") is not None
              and r.get("change_times") is not None]
    if not scored:
        print("  ★ change_times がありません（rev5 の出力を使ってください）")
        return

    print("\n  分母 ＝ 段階2（b）に到達し、地平 300 の内側で E3（C）が確定した def")
    print("\n  %-10s%14s%14s%14s%10s"
          % ("θ′", "窓内で汚れた", "走行末まで", "変化の中央値", "n"))
    for theta in sorted({r["theta_prime"] for r in scored}):
        picked = [r for r in scored if r["theta_prime"] == theta
                  and r["E3_C"] <= r["stage2_b"] + HORIZON]
        if not picked:
            continue
        end = lambda r: r["stage2_b"] + HORIZON
        inside = sum(1 for r in picked
                     if any(r["E3_C"] < t <= end(r) for t in r["change_times"]))
        outside = sum(1 for r in picked
                      if any(t > r["E3_C"] for t in r["change_times"]))
        changes = [r["n_changes"] for r in picked if r.get("n_changes") is not None]
        print("  %-10.4f%14.4f%14.4f%14s%10d"
              % (theta, inside / len(picked), outside / len(picked),
                 "%.1f" % statistics.median(changes) if changes else "—", len(picked)))

    counted = [r for r in scored if r["E3_C"] <= r["stage2_b"] + HORIZON]
    inside = sum(1 for r in counted
                 if any(r["E3_C"] < t <= r["stage2_b"] + HORIZON
                        for t in r["change_times"]))
    print("\n  全体  窓内で汚れた割合 %.4f（%d / %d）"
          % (inside / len(counted), inside, len(counted)))
    print("""
  読み方（2026-08-30 に置いた基準をそのまま使う）
    0.10 未満   吸収の仮定は実質的に成り立つ。U-089 は (C) のまま閉じる
    0.10〜0.30  併記して判断
    0.30 超     E3 は状態述語である。★ 主推定量の再考が要る
  ★「窓内」が正しい数字。「走行末まで」は rev4 が出していた上限（参考）
""")


def check2_frac(rows):
    print("\n" + "=" * 92)
    print("検算2′  OA_gstar_frac（欠けた述語の割合）を m_live で層別する")
    print("=" * 92)

    scored = [r for r in rows if r.get("stage2_b") is not None]
    bins = defaultdict(list)
    for record in scored:
        m = record.get("m_live_final")
        if m is not None:
            bins["%d" % m if m <= 4 else "5+"].append(record)

    print("\n  %-8s%14s%12s%12s%12s%10s"
          % ("m_live", "★frac", "二値gstar", "supply", "applied", "n"))
    for key in sorted(bins, key=lambda k: (k == "5+", k)):
        picked = bins[key]
        print("  %-8s%s%s%s%s%10d"
              % (key,
                 fmt(mean([r.get("OA_gstar_frac") for r in picked]), 14),
                 fmt(mean([r.get("OA_gstar") for r in picked])),
                 fmt(mean([r.get("OA_supply") for r in picked])),
                 fmt(mean([r.get("OA_applied") for r in picked])),
                 len(picked)))

    print("\n  θ′ 別（★ 主張はこの向きで書く）")
    print("  %-10s%14s%12s%12s%10s" % ("θ′", "★frac", "二値gstar", "採択加重frac", "n"))
    for theta in sorted({r["theta_prime"] for r in scored}):
        picked = [r for r in scored if r["theta_prime"] == theta]
        weighted = [r for r in picked
                    if r.get("OA_gstar_frac") is not None and r.get("adoptions")]
        total = sum(r["adoptions"] for r in weighted)
        wmean = (sum(r["OA_gstar_frac"] * r["adoptions"] for r in weighted) / total
                 if total else None)
        print("  %-10.4f%s%s%s%10d"
              % (theta,
                 fmt(mean([r.get("OA_gstar_frac") for r in picked]), 14),
                 fmt(mean([r.get("OA_gstar") for r in picked])),
                 fmt(wmean), len(picked)))

    print("""
  読み方
    ★ frac が m_live に対して平坦 → 二値版の m 依存は和集合の交絡だったと確定
    ★ frac が θ′ とともに上がる   → 薄化と過剰適用が結びついている（機構主張）
    ★ frac も m とともに上がる    → 交絡ではなく実在の効果。二値版の読みが救われる
""")


def check4_age(rows):
    print("\n" + "=" * 92)
    print("検算4  薄化を年齢で層別する（born を使う）")
    print("=" * 92)

    scored = [r for r in rows
              if r.get("born") is not None and r.get("m_live_final") is not None
              and r.get("horizon") is not None]
    if not scored:
        print("  ★ born がありません（rev5 の出力を使ってください）")
        return
    thetas = sorted({r["theta_prime"] for r in scored})
    bands = [(0, 200), (200, 600), (600, 1200), (1200, 10 ** 9)]

    print("\n  m_live 平均（行 ＝ 年齢 ＝ horizon − born、列 ＝ θ′）")
    print("  %-14s%s" % ("年齢", "".join("%12.4f" % t for t in thetas)))
    for low, high in bands:
        cells, n = [], 0
        for theta in thetas:
            picked = [r["m_live_final"] for r in scored
                      if r["theta_prime"] == theta
                      and low <= (r["horizon"] - r["born"]) < high]
            n = max(n, len(picked))
            cells.append(mean(picked))
        label = "%d–%d" % (low, high) if high < 10 ** 9 else "%d+" % low
        print("  %-14s%s   (n≈%d)" % (label, "".join(fmt(c) for c in cells), n))

    print("""
  読み方
    ★ どの年齢帯でも θ′ が上がると m_live が下がる → 薄化は年齢の交絡ではない
    ★ 若い帯だけで差が出る                       → 出生の違い（Fable 2026-08-28）
      「薄いのは薄化ではなく出生の結果」という読みが優勢になる
""")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-def", required=True)
    args = parser.parse_args()
    rows = load(Path(args.per_def))
    print("読み込み  %s（def %d 行）" % (args.per_def, len(rows)))
    print("★ 追加走行なし。rev5 が足した欄を層別しているだけ")
    check1_windowed(rows)
    check2_frac(rows)
    check4_age(rows)


if __name__ == "__main__":
    main()
