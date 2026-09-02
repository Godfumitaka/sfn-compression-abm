#!/usr/bin/env python3
"""
checks3.py — 検算 5〜10（再走行なし。analysis3/per_def.jsonl だけを読む）

作成 2026-08-30 夜 ／ checks.py・checks2.py の後継。前二本は残しておくこと

なぜ要るか（2026-08-30 に判明したこと）
  ・E3（推定量 C）の吸収は不合格（0.5082）。E3 を使う量は主張に使いにくい
  ・τ_settle が θ′ で 58 → 3 と縮むので、神話率 M-002 の用量反応は窓の効果を含む
  ・OA_gstar は「言うことを減らすと外れにくい」を測っており、内側の沈黙指標だった
  → ★ E3 にも τ_settle にも依存しない量で、主張を組み直す必要がある

検算5   ★ U-071 を閉じる（台帳の ★最重要 未決）
        「薄化は m=4（真の定義）で止まるか、m=2（神話）まで行くか」
        台帳 U-071 は「本問いは本走行（40 seed × T=1,740）が答える」と明記している。
        ★ m_live の分布はこの問いの直接の答えであり、E3 を一切使わない。

検算6   ★ 神話率の E3 非依存版
        神話 ＝ m_live ≤ 2 の def（U-071 の定義。8/21 確定。★ 事後の閾値ではない）
        その採択が全採択に占める割合を f × θ′ の面で出す。
        ★ M-002（段階2 × E3）の代わりに主図へ出せるかを判定する。

検算7   OA_applied（＝ 1 −最頻モチーフ占有率）を θ′ と m_live で層別
        gstar が支持され具合であるのに対し、applied は ★ 適用の広がり を測る。
        「取りうる最小値」なので過大には出ない。★ 下限として読む。

検算8   ★ 削除は時間とともに積み上がるか（§2 の平坦さの検査）
        削除本数 ＝ m_alloc − m_live を、年齢 × θ′ で層別する。
        年齢とともに θ′ の差が開くなら、削除は効いている（時間がかかるだけ）。
        年齢によらず平坦なら、θ′ の効きは出生側にある。

検算9   ★ E3 は「停留」か「使われなくなっただけ」か
        E3 を確定した def と、確定後も動いた def で、採択の密度を比べる。
        停留した def の採択密度が低ければ、E3 は不使用の言い換えである。

検算10  ★ m_live に床があるか（D10(b) の検査）
        D10(b) は「def(R) に最低一本残す」のような免除・床を禁じている。
        m=1 と m=0（E2）の実数を数える。★ 床があれば禁止条項違反の疑い。

使い方
  python3 checks3.py --per-def analysis3/per_def.jsonl
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

KEEP = ("f", "theta_prime", "repair_scope", "adoptions", "m_live_final", "m_alloc",
        "born", "horizon", "n_changes", "change_times", "tau_settle", "thin",
        "stage2_b", "E3_C", "E2_time", "motif",
        "OA_supply", "OA_applied", "OA_gstar", "OA_gstar_frac")

MYTH_M = 2          # U-071（確定 2026-08-21）の「神話」＝ m=2。★ 事後に選んだ閾値ではない
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


def surface(rows, metric, label, thetas):
    """f × θ′ の面。metric は行 → 値 or None を返す関数。"""
    scope = sorted({r["repair_scope"] for r in rows if r.get("repair_scope")})[0]
    subset = [r for r in rows if r.get("repair_scope") == scope]
    print("\n### %s   射程 = %s" % (label, scope))
    print("            θ′ → " + "".join("%12.4f" % t for t in thetas))
    for value in sorted({r["f"] for r in subset if r["f"] is not None}):
        cells = []
        for theta in thetas:
            picked = [r for r in subset
                      if r["f"] == value and r["theta_prime"] == theta]
            cells.append(metric(picked))
        print("  f=%-9.4f%s" % (value, "".join(fmt(c) for c in cells)))


# ══════════════════════════════════════════════════════════════
def check5_u071(rows, thetas):
    print("\n" + "=" * 92)
    print("検算5  ★ U-071 を閉じる — 薄化は m=4 で止まるか、m=2 まで行くか")
    print("=" * 92)
    print("\n  種の設計では全モチーフが m=6（核3 ＋ 塔1 ＋ 周縁2）。")
    print("  真の定義は m=4（核3 ＋ 塔1）、神話は m=2 とされてきた（U-071・8/21）\n")

    print("  %-10s%10s%10s%10s%10s%10s%10s%10s"
          % ("θ′", "m=2 以下", "m=3", "m=4", "m=5 以上", "中央", "最頻", "n"))
    for theta in thetas:
        picked = [r["m_live_final"] for r in rows
                  if r["theta_prime"] == theta and r["m_live_final"] is not None]
        if not picked:
            continue
        counts = Counter(picked)
        n = len(picked)
        print("  %-10.4f%10.4f%10.4f%10.4f%10.4f%10.1f%10d%10d"
              % (theta,
                 sum(v for k, v in counts.items() if k <= 2) / n,
                 counts.get(3, 0) / n, counts.get(4, 0) / n,
                 sum(v for k, v in counts.items() if k >= 5) / n,
                 statistics.median(picked), counts.most_common(1)[0][0], n))

    print("\n  ★ 採択加重（実際に使われた def の重みで見る）")
    print("  %-10s%10s%10s%10s%10s%12s"
          % ("θ′", "m=2 以下", "m=3", "m=4", "m=5 以上", "採択総数"))
    for theta in thetas:
        picked = [r for r in rows if r["theta_prime"] == theta
                  and r["m_live_final"] is not None and r.get("adoptions")]
        total = sum(r["adoptions"] for r in picked)
        if not total:
            continue
        def share(test):
            return sum(r["adoptions"] for r in picked if test(r["m_live_final"])) / total
        print("  %-10.4f%10.4f%10.4f%10.4f%10.4f%12d"
              % (theta, share(lambda m: m <= 2), share(lambda m: m == 3),
                 share(lambda m: m == 4), share(lambda m: m >= 5), total))

    print("""
  読み方
    ★ 最頻が m=4       薄化は真の定義で止まる。U-071 の答えは「止まる」
    ★ 最頻が m=3 以下  m=4 を通り越している。★ 止まらない
    ★ m≤2 が θ′ で動く 神話まで落ちる割合を θ′ が支配している（機構主張の核）
    ★ 採択加重が def 平均より大きい  薄い def ほどよく使われる（神話は少数だが使われる）
""")


def check6_myth_free(rows, thetas):
    print("\n" + "=" * 92)
    print("検算6  ★ 神話率の E3 非依存版（神話 ＝ m_live ≤ %d。U-071・8/21 確定）" % MYTH_M)
    print("=" * 92)

    def myth_share(picked):
        used = [r for r in picked if r.get("adoptions")]
        total = sum(r["adoptions"] for r in used)
        if not total:
            return None
        return sum(r["adoptions"] for r in used
                   if r["m_live_final"] is not None
                   and r["m_live_final"] <= MYTH_M) / total

    surface(rows, myth_share, "★ 神話率（構造版・採択加重）", thetas)

    def myth_count(picked):
        valid = [r for r in picked if r["m_live_final"] is not None]
        if not valid:
            return None
        return sum(1 for r in valid if r["m_live_final"] <= MYTH_M) / len(valid)

    surface(rows, myth_count, "神話率（構造版・def 数）", thetas)

    print("""
  読み方
    ★ θ′ で上がり、f で上がらない → M-002 の代わりに主図へ出せる
      E3 にも τ_settle にも段階2 にも依存しないので、8/30 に見つかった交絡を受けない
    ★ f でも上がる → 「フィードバックは定義を薄くしない」がより強く言える
    ★ θ′ で動かない → 機構主張は現行の測り方では立たない
""")


def check7_applied(rows, thetas):
    print("\n" + "=" * 92)
    print("検算7  OA_applied（適用の広がり）を θ′ と m_live で層別")
    print("=" * 92)

    print("\n  %-10s%12s%12s%14s%10s"
          % ("θ′", "OA_applied", "OA_supply", "採択加重applied", "n"))
    for theta in thetas:
        picked = [r for r in rows if r["theta_prime"] == theta]
        weighted = [r for r in picked
                    if r.get("OA_applied") is not None and r.get("adoptions")]
        total = sum(r["adoptions"] for r in weighted)
        wmean = (sum(r["OA_applied"] * r["adoptions"] for r in weighted) / total
                 if total else None)
        values = [r["OA_applied"] for r in picked if r.get("OA_applied") is not None]
        print("  %-10.4f%s%s%s%10d"
              % (theta, fmt(mean(values)),
                 fmt(mean([r.get("OA_supply") for r in picked])),
                 fmt(wmean, 14), len(values)))

    print("\n  ★ θ′ × m_live（m_live を揃えて θ′ の効きを見る）")
    print("  %-10s%s" % ("θ′", "".join("%12s" % ("m=%s" % k)
                                       for k in ("2以下", "3", "4", "5+"))))
    for theta in thetas:
        cells = []
        for test in (lambda m: m <= 2, lambda m: m == 3, lambda m: m == 4,
                     lambda m: m >= 5):
            values = [r["OA_applied"] for r in rows
                      if r["theta_prime"] == theta and r.get("OA_applied") is not None
                      and r["m_live_final"] is not None and test(r["m_live_final"])]
            cells.append(mean(values))
        print("  %-10.4f%s" % (theta, "".join(fmt(c) for c in cells)))

    print("""
  読み方
    ★ m_live を揃えても θ′ で applied が上がる → 薄化とは別に θ′ が広がりを増やす
    ★ m_live を揃えると平坦        → θ′ の効きは m_live 経由（それでも因果の鎖は繋がる）
    ★ m_live が小さいほど applied が大きい → ★ 薄い定義ほど広く当たる（過汎化の直接の証拠）
""")


def check8_deletion_by_age(rows, thetas):
    print("\n" + "=" * 92)
    print("検算8  ★ 削除は時間とともに積み上がるか（削除本数 ＝ m_alloc − m_live）")
    print("=" * 92)

    scored = [r for r in rows
              if r.get("m_alloc") and r.get("m_live_final") is not None
              and r.get("born") is not None and r.get("horizon") is not None]
    if not scored:
        print("  ★ m_alloc / born がありません（rev5 の出力を使ってください）")
        return
    bands = [(0, 200), (200, 600), (600, 1200), (1200, 10 ** 9)]

    print("\n  削除本数の平均（行 ＝ 年齢、列 ＝ θ′）")
    print("  %-14s%s%12s" % ("年齢", "".join("%12.4f" % t for t in thetas), "差(最上-最下)"))
    for low, high in bands:
        cells, n = [], 0
        for theta in thetas:
            picked = [r["m_alloc"] - r["m_live_final"] for r in scored
                      if r["theta_prime"] == theta
                      and low <= (r["horizon"] - r["born"]) < high]
            n = max(n, len(picked))
            cells.append(mean(picked))
        label = "%d–%d" % (low, high) if high < 10 ** 9 else "%d+" % low
        gap = (cells[-1] - cells[0]) if (cells[0] is not None
                                         and cells[-1] is not None) else None
        print("  %-14s%s%s   (n≈%d)"
              % (label, "".join(fmt(c) for c in cells), fmt(gap), n))

    print("\n  m_alloc の平均（行 ＝ 年齢、列 ＝ θ′）★ 出生側が動いているかの対照")
    print("  %-14s%s" % ("年齢", "".join("%12.4f" % t for t in thetas)))
    for low, high in bands:
        cells = []
        for theta in thetas:
            picked = [r["m_alloc"] for r in scored
                      if r["theta_prime"] == theta
                      and low <= (r["horizon"] - r["born"]) < high]
            cells.append(mean(picked))
        label = "%d–%d" % (low, high) if high < 10 ** 9 else "%d+" % low
        print("  %-14s%s" % (label, "".join(fmt(c) for c in cells)))

    print("""
  読み方
    ★ 年齢とともに θ′ の差が開く   削除は効いている（積み上がるのに時間がかかるだけ）
    ★ どの年齢でも差が平坦         θ′ の効きは削除ではなく出生側にある
    ★ m_alloc が θ′ で下がる       ★ 枚の寿命 floor(θ′⁻²)+1 が材料を絞っている疑い
                                    → L を θ′ から切り離す腕が決定実験になる
""")


def check9_e3_or_disuse(rows):
    print("\n" + "=" * 92)
    print("検算9  ★ E3 は「停留」か「使われなくなっただけ」か")
    print("=" * 92)

    scored = [r for r in rows
              if r.get("stage2_b") is not None and r.get("E3_C") is not None
              and r.get("change_times") is not None and r.get("born") is not None
              and r.get("horizon") is not None]
    if not scored:
        print("  ★ 必要な欄がありません")
        return

    def density(record):
        span = max(1, record["horizon"] - record["born"])
        return (record.get("adoptions") or 0) / span

    clean = [r for r in scored if not any(t > r["E3_C"] for t in r["change_times"])]
    dirty = [r for r in scored if any(t > r["E3_C"] for t in r["change_times"])]

    print("\n  %-24s%14s%14s%14s%12s"
          % ("", "採択密度", "採択総数", "m_live", "n"))
    for label, picked in (("★ E3 後に動かない（停留）", clean),
                          ("E3 後に動いた（汚れ）", dirty)):
        if not picked:
            continue
        print("  %-24s%s%s%s%12d"
              % (label,
                 fmt(mean([density(r) for r in picked]), 14, 5),
                 fmt(mean([r.get("adoptions") for r in picked]), 14, 2),
                 fmt(mean([r.get("m_live_final") for r in picked]), 14, 3),
                 len(picked)))

    print("""
  読み方
    ★ 停留側の採択密度が明らかに低い  E3 は「使われなくなった」の言い換えである
      → 神話の主張が弱まる。使われていない定義は誰も誤らせない
    ★ 採択密度が同程度            E3 は「使われながら動かない」を捉えている
      → ★ 神話の主張がそのまま立つ。使われているのに更新されない定義
""")


def check10_floor(rows, thetas):
    print("\n" + "=" * 92)
    print("検算10  ★ m_live に床があるか（D10(b)：免除・床を置かない）")
    print("=" * 92)

    print("\n  %-10s%12s%12s%12s%14s%10s"
          % ("θ′", "m=0（E2）", "m=1", "m=2", "m=1 の実数", "n"))
    for theta in thetas:
        picked = [r for r in rows if r["theta_prime"] == theta]
        alive = [r["m_live_final"] for r in picked if r["m_live_final"] is not None]
        e2 = sum(1 for r in picked if r.get("E2_time") is not None)
        ones = sum(1 for m in alive if m == 1)
        twos = sum(1 for m in alive if m == 2)
        n = len(alive)
        print("  %-10.4f%12.6f%12.6f%12.6f%14d%10d"
              % (theta, e2 / max(n, 1), ones / n, twos / n, ones, n))

    print("""
  読み方
    ★ m=1 が m=2 より二桁以上少なく、m=0 がほぼ皆無  → 床がある疑い
      D10(b) は「def(R) に最低一本残す」を禁じている。実装に床があれば禁止条項違反
      ★ 床が emergent（m=1 でも照合が通り功績を稼ぐので落ちない）なら違反ではない
      → どちらかは実装の grep で決める。この表だけでは判定しない
    ★ E2 がほぼ皆無であることは、M-048（E2 と E3 の競合）の前提を崩している
""")


# ══════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-def", required=True)
    args = parser.parse_args()
    rows = load(Path(args.per_def))
    thetas = sorted({r["theta_prime"] for r in rows if r["theta_prime"] is not None})
    print("読み込み  %s（def %d 行）" % (args.per_def, len(rows)))
    print("★ 追加走行なし。★ 検算5・6・8・10 は E3 にも τ_settle にも依存しない")

    check5_u071(rows, thetas)
    check6_myth_free(rows, thetas)
    check7_applied(rows, thetas)
    check8_deletion_by_age(rows, thetas)
    check9_e3_or_disuse(rows)
    check10_floor(rows, thetas)


if __name__ == "__main__":
    main()
