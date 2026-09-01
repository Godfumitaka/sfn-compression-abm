#!/usr/bin/env python3
"""probe9.py — (B2)「照合に載らなくなる」に 対照 を取る。

★ 本 probe は 探索 のためのものである。★ 台帳を読むだけ。

★ probe8 で出たこと
   ② の後に 照合に載らなくなったスロットの 63.9%（★ 薄い定義では 95.8%）が
   ★ 生きたまま 残っている

★ ★ しかし 対照が無い
   ★ reason の長さと生存スロット数の一致率は 89% しかない
   ★ 「生きているのに reason に載らない」は 常時 2.8% 発生している
   → ★ ★ (B2) は 失敗の帰結 ではなく 通常運転 かもしれない

★ 本 probe が測ること
   ★ 同じスロットについて、直前の判定が
       ②（失敗）だった場合
       充足 だった場合
       ③  だった場合
   ★ ★ その後 W 試行のあいだに そのスロットが reason に 一度も載らない 率

★ ★ 差があれば  ★ (B2) は失敗の帰結。★ 新しい線
★ ★ 差が無ければ ★ (B2) は通常運転。★ 線を捨てる

★ 追加  ★ 「載らなくなった」あと、その def の 採択回数 がどう動くかも見る
        （★ そのスロットだけ降りたのか、★ def ごと使われなくなったのか）

使い方
    python3.14 probe9.py runs/main_2026-08-31 --max-cells 4

★ 走行中のディレクトリには使わないこと。
"""

import sys
import gzip
import glob
import json
import collections
import statistics

OK = "充足"
FAIL = "②"
SAN = "③"
HANTEI = "判定不能"
W = 300


def alive_slots(rec, R):
    cs = rec.get("constituent_states")
    if not cs:
        return None
    out = set()
    found = False
    for row in cs:
        if not isinstance(row, dict) or row.get("R") != R:
            continue
        found = True
        if row.get("alive") is False:
            continue
        si = row.get("slot_index")
        if si is not None:
            out.add(str(si))
    return out if found else None


def main():
    if len(sys.argv) < 2:
        print("使い方: python3.14 probe9.py <走行ディレクトリ> [--max-cells N]")
        return 2
    root = sys.argv[1]
    max_cells = None
    if "--max-cells" in sys.argv:
        max_cells = int(sys.argv[sys.argv.index("--max-cells") + 1])

    paths = sorted(glob.glob(f"{root}/cells/*/*.jsonl.gz"))
    if max_cells is not None:
        cells = sorted({p.rsplit("/", 2)[1] for p in paths})[:max_cells]
        paths = [p for p in paths if p.rsplit("/", 2)[1] in cells]
    print(f"台帳 {len(paths)} 本を読みます（猶予 W={W}）")

    # 直前の判定 → その後の挙動
    stat = collections.defaultdict(collections.Counter)
    stat_k = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    use_after = collections.defaultdict(list)   # 判定 → 直後 W の R 採択回数

    for pi, p in enumerate(paths, 1):
        if pi % 20 == 0:
            print(f"  {pi}/{len(paths)}")
        with gzip.open(p, "rt") as f:
            f.readline()
            rows = []
            for line in f:
                if not line.strip():
                    continue
                rec = json.loads(line)
                if rec.get("record_type") == "trial":
                    rows.append(rec)
            T = len(rows)

            used_at = collections.defaultdict(list)
            reason_at = collections.defaultdict(list)
            alive_last = {}
            for t, rec in enumerate(rows, 1):
                R = rec.get("R_used")
                if R is None:
                    continue
                used_at[R].append(t)
                reasons = (rec.get("constituent_reason_123") or {}).get(R) or {}
                for q, v in reasons.items():
                    reason_at[(R, str(q))].append((t, v))
                al = alive_slots(rec, R)
                if al is not None:
                    alive_last[R] = al

            for key, seq in reason_at.items():
                R, q = key
                kk = len({qq for (RR, qq) in reason_at if RR == R})
                for t, v in seq:
                    if v not in (OK, FAIL, SAN):
                        continue
                    if t + W > T:
                        continue
                    after_use = [tt for tt in used_at.get(R, []) if t < tt <= t + W]
                    if not after_use:
                        continue          # R が使われないなら「載らない」を判定できない
                    later = [vv for tt, vv in seq if t < tt <= t + W]
                    dropped = (len(later) == 0)
                    alive = (q in alive_last.get(R, set()))
                    stat[v]["対象"] += 1
                    stat[v]["載らなくなった"] += int(dropped)
                    stat[v]["載らず かつ 生存"] += int(dropped and alive)
                    stat_k[kk][v]["対象"] += 1
                    stat_k[kk][v]["載らなくなった"] += int(dropped)
                    stat_k[kk][v]["載らず かつ 生存"] += int(dropped and alive)
                    use_after[v].append(len(after_use))

    print()
    print("=" * 82)
    print(f"probe9   {root}")
    print("=" * 82)

    print()
    print("=" * 82)
    print("★ 1  直前の判定別 — その後 W 試行のあいだ そのスロットが照合に載らない率")
    print("     ★ 対象は「R がその後 一度以上 採択された」場合のみ")
    print("=" * 82)
    print(f"{'直前の判定':>10} {'対象':>10} {'★載らない':>11} {'★載らない率':>12} "
          f"{'★載らず生存':>12} {'★生存率':>10}")
    for v in (OK, FAIL, SAN):
        c = stat.get(v)
        if not c or c["対象"] == 0:
            continue
        n = c["対象"]
        d = c["載らなくなった"]
        a = c["載らず かつ 生存"]
        print(f"{v:>10} {n:10d} {d:11d} {d/n*100:11.2f}% {a:12d} "
              f"{(a/d*100 if d else float('nan')):9.1f}%")

    print()
    print("★ ★ 差の読み方")
    if stat.get(FAIL, {}).get("対象") and stat.get(OK, {}).get("対象"):
        rf = stat[FAIL]["載らなくなった"] / stat[FAIL]["対象"]
        ro = stat[OK]["載らなくなった"] / stat[OK]["対象"]
        print(f"  ② の後 {rf*100:.2f}%  ／  充足の後 {ro*100:.2f}%  "
              f"／  ★ 比 {rf/ro:.2f} 倍" if ro else "")

    print()
    print("=" * 82)
    print("★ 2  スロット数別（★ ② の後 と 充足の後 を並べる）")
    print("=" * 82)
    print(f"{'スロット数':>10} {'②の後 対象':>11} {'②の後 載らない':>15} "
          f"{'充足の後 対象':>13} {'充足の後 載らない':>17} {'★比':>8}")
    for kk in sorted(stat_k):
        cf = stat_k[kk].get(FAIL, {})
        co = stat_k[kk].get(OK, {})
        nf, no = cf.get("対象", 0), co.get("対象", 0)
        if nf == 0 or no == 0:
            continue
        rf = cf["載らなくなった"] / nf
        ro = co["載らなくなった"] / no
        print(f"{kk:10d} {nf:11d} {rf*100:14.2f}% {no:13d} {ro*100:16.2f}% "
              f"{(rf/ro if ro else float('nan')):7.2f}")

    print()
    print("=" * 82)
    print("★ 3  直後 W のあいだ、その def が何回採択されたか（★ 交絡の検査）")
    print("=" * 82)
    for v in (OK, FAIL, SAN):
        lst = use_after.get(v)
        if not lst:
            continue
        print(f"  {v:>6}  件数 {len(lst):8d}  中央 {statistics.median(lst):6.0f}  "
              f"平均 {statistics.mean(lst):7.1f}")

    print()
    print("★ 読み方")
    print("  ★ ★ ② の後の「載らない率」が 充足の後より 明確に高ければ")
    print("     → ★ ★ 失敗したスロットが 照合から降りる。★ ★ 新しい線")
    print("  ★ 差が無ければ → ★ (B2) は通常運転。★ 線を捨てる")
    print("  ★ §3 で採択回数が判定によって違えば → ★ そこが交絡")
    print("★ 判定は書きません。★ 本 probe は探索のためのものです。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
