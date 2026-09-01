#!/usr/bin/env python3
"""
mlive.py — ★ E3 をまったく使わない薄化の指標（(A)。再走行なし）

作成 2026-08-30

なぜ要るか
  神話率 M-002 は「段階2 × E3」で定義されるが、E3 の窓 τ_settle が
  θ′ とともに 58 → 3 と縮む（2026-08-30 実測）。
  → θ′ をまたぐ神話率の比較は、異なる時間尺度で定義された事象の比較になる
  → 「薄化が増えた」のか「E3 が取りやすくなった」のかを分けられない

  m_live（生存構成素数）は E3 にも τ_settle にも依らない。
  ★ θ′ を上げて m_live が下がるなら、機構主張は交絡なしで書ける。

★ 既知の弱み（結果を見る前に書く）
  m_live_final は走行末（または def が尽きる直前）の値なので、
  遅く生まれた def は薄くなる時間が短い。年齢の交絡が残る。
  → rev5 で born を足せば年齢層別ができる。本スクリプトは全 def の分布を見るだけ。

使い方
  python3 mlive.py --per-def analysis2/per_def.jsonl
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path

KEEP = ("f", "theta_prime", "repair_scope", "adoptions", "m_live_final",
        "m_alloc", "born", "thin", "stage2_b", "n_changes")


def load(path: Path):
    rows = []
    with open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                record = json.loads(line)
                rows.append({k: record.get(k) for k in KEEP})
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-def", required=True)
    args = parser.parse_args()

    rows = load(Path(args.per_def))
    print("読み込み  %s（def %d 行）" % (args.per_def, len(rows)))
    print("★ E3・τ_settle・段階2 のいずれにも依存しない量だけを見る\n")

    thetas = sorted({r["theta_prime"] for r in rows if r["theta_prime"] is not None})

    # ── 1. θ′ 別の m_live 分布 ──────────────────────────────
    print("=" * 92)
    print("1  θ′ 別の m_live（生存構成素数）の分布 — ★ 交絡なしの薄化指標")
    print("=" * 92)
    print("\n  %-10s%10s%10s%10s%10s%10s%12s%10s"
          % ("θ′", "平均", "中央", "m≤2 の率", "m≤3 の率", "採択加重", "m_alloc", "n"))
    for theta in thetas:
        picked = [r for r in rows if r["theta_prime"] == theta
                  and r["m_live_final"] is not None]
        if not picked:
            continue
        values = [r["m_live_final"] for r in picked]
        weighted = [r for r in picked if r.get("adoptions")]
        total = sum(r["adoptions"] for r in weighted)
        wmean = (sum(r["m_live_final"] * r["adoptions"] for r in weighted) / total
                 if total else float("nan"))
        allocs = [r["m_alloc"] for r in picked if r.get("m_alloc")]
        print("  %-10.4f%10.3f%10.1f%10.4f%10.4f%10.3f%12s%10d"
              % (theta, statistics.fmean(values), statistics.median(values),
                 sum(1 for v in values if v <= 2) / len(values),
                 sum(1 for v in values if v <= 3) / len(values),
                 wmean,
                 "%.3f" % statistics.fmean(allocs) if allocs else "—",
                 len(picked)))

    # ── 2. m_live のヒストグラム ────────────────────────────
    print("\n" + "=" * 92)
    print("2  m_live のヒストグラム（列は θ′。★ 分布の形が動くか）")
    print("=" * 92)
    counts = defaultdict(lambda: defaultdict(int))
    for record in rows:
        m = record.get("m_live_final")
        if m is not None:
            counts[min(m, 7)][record["theta_prime"]] += 1
    print("\n  %-10s%s" % ("m_live", "".join("%12.4f" % t for t in thetas)))
    for m in sorted(counts):
        totals = [sum(counts[k][t] for k in counts) for t in thetas]
        label = "%d" % m if m < 7 else "7+"
        print("  %-10s%s" % (label, "".join(
            "%12.4f" % (counts[m][t] / n if n else 0.0)
            for t, n in zip(thetas, totals))))

    # ── 3. f × θ′ の面（★ f で動かないことの確認）──────────
    print("\n" + "=" * 92)
    print("3  m_live 平均の面（f × θ′）")
    print("=" * 92)
    scope = sorted({r["repair_scope"] for r in rows if r.get("repair_scope")})[0]
    subset = [r for r in rows if r.get("repair_scope") == scope]
    print("\n### m_live 平均   射程 = %s" % scope)
    print("            θ′ → " + "".join("%12.4f" % t for t in thetas))
    for value in sorted({r["f"] for r in subset if r["f"] is not None}):
        cells = []
        for theta in thetas:
            picked = [r["m_live_final"] for r in subset
                      if r["f"] == value and r["theta_prime"] == theta
                      and r["m_live_final"] is not None]
            cells.append(statistics.fmean(picked) if picked else float("nan"))
        print("  f=%-9.4f%s" % (value, "".join("%12.4f" % c for c in cells)))

    print("""
★ 読み方（結果を見る前に置く）
  θ′ が上がるほど m_live が下がる     機構主張は交絡なしで書ける。
                                      ★ 神話率 M-002 の代わりに主図へ出せる
  θ′ で m_live が動かない             神話率の用量反応は E3 の窓が縮んだ効果である
                                      ★ その場合、機構主張は現行の測り方では立たない
  f で m_live が動かない              薄化はフィードバックに応答しない（水位の補強）

★ 注意  m_alloc は最後の登録イベント時点の総数（墓石を含む）。
        m_alloc − m_live が「削除された本数」だが、m_alloc 自体が θ′ で動くなら
        出生の違い（Fable 2026-08-28：薄いのは薄化ではなく出生の結果）と混ざる
""")


if __name__ == "__main__":
    main()
