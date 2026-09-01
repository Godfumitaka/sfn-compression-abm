#!/usr/bin/env python3
"""probe8.py — (B2)「スロットが照合に載らない」の実体を分ける。

★ 本 probe は 探索 のためのものである。★ 台帳を読むだけ。

★ probe7 で出たこと
   ② が回収されない理由のうち、★ (B2)「R は採択されたがスロットが reason に載らない」
   が 未回収の 31.8%。★ ★ 薄い定義（部分2個）では 69.7%

★ ★ しかし (B2) には少なくとも三通りの中身がありうる

   (a) ★ そのスロットが 削除された（★ probe7 の deletion_event で拾い漏れた）
       → ★ ★ (A) と同じ。★ 主張にならない

   (b) ★ 生きているのに 写像に載らなかった
       → ★ ★ 「間違えうる場面から外れる」の候補

   (c) ★ ★ そもそも reason が その def の全スロットを列挙していない回がある
       → ★ ★ 集計の副作用。★ 主張にならない

★ 本 probe の対処
   1  ★ (B2) の (R,q) が、★ 走行末の constituent_states に 生きて 残っているか
   2  ★ reason の長さと、★ その def の生存スロット数 が一致しているか（★ (c) の検査）
   3  ★ (B2) になる前後で、★ その def の 採択回数 と 生存スロット数 がどう動いたか

使い方
    python3.14 probe8.py runs/main_2026-08-31 --max-cells 4

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
W = 300


def del_keys(rec):
    out = []
    ev = rec.get("deletion_event")
    if not ev:
        return out
    if isinstance(ev, dict):
        ev = [ev]
    for e in ev:
        if not isinstance(e, dict):
            continue
        R = e.get("R") or e.get("R_name") or e.get("def") or e.get("name")
        q = e.get("slot_index", e.get("slot"))
        if R is not None and q is not None:
            out.append((str(R), str(q)))
    return out


def alive_slots(rec, R):
    """その試行時点で R の生きているスロット番号の集合。取れなければ None。"""
    cs = rec.get("constituent_states")
    if not cs:
        return None
    out = set()
    found = False
    for row in cs:
        if not isinstance(row, dict):
            continue
        if row.get("R") != R:
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
        print("使い方: python3.14 probe8.py <走行ディレクトリ> [--max-cells N]")
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

    verdict = collections.Counter()
    verdict_by_k = collections.defaultdict(collections.Counter)
    mismatch = collections.Counter()      # reason の長さ vs 生存スロット数
    n_cs_ok = n_cs_none = 0
    drop_ctx = []                          # (B2) 直後の生存スロット数の変化

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
            del_at = {}
            alive_at = collections.defaultdict(list)   # R → [(t, 生存スロット集合)]
            for t, rec in enumerate(rows, 1):
                for key in del_keys(rec):
                    del_at.setdefault(key, t)
                R = rec.get("R_used")
                if R is None:
                    continue
                used_at[R].append(t)
                reasons = (rec.get("constituent_reason_123") or {}).get(R) or {}
                for q, v in reasons.items():
                    reason_at[(R, str(q))].append((t, v))
                al = alive_slots(rec, R)
                if al is None:
                    n_cs_none += 1
                else:
                    n_cs_ok += 1
                    alive_at[R].append((t, al))
                    mismatch[(len(reasons), len(al))] += 1

            # 走行末の生存スロット
            final_alive = {}
            for R, lst in alive_at.items():
                if lst:
                    final_alive[R] = lst[-1][1]

            # (B2) を抽出して分類
            for key, seq in reason_at.items():
                R, q = key
                for t, v in seq:
                    if v != FAIL or t + W > T:
                        continue
                    later = [(tt, vv) for tt, vv in seq if t < tt <= t + W]
                    if any(vv == OK for _tt, vv in later):
                        continue
                    dt = del_at.get(key)
                    if dt is not None and t < dt <= t + W:
                        continue
                    after_use = [tt for tt in used_at.get(R, []) if t < tt <= t + W]
                    if not after_use or later:
                        continue
                    # ここからが (B2)
                    kk = len({qq for (RR, qq) in reason_at if RR == R})
                    fa = final_alive.get(R)
                    if fa is None:
                        c = "生死不明（constituent_states が無い）"
                    elif q in fa:
                        c = "★ 生きている"
                    else:
                        c = "消えている"
                    verdict[c] += 1
                    verdict_by_k[kk][c] += 1
                    # (B2) 直後の生存スロット数の変化
                    before = [a for (tt, a) in alive_at.get(R, []) if tt <= t]
                    after = [a for (tt, a) in alive_at.get(R, []) if t < tt <= t + W]
                    if before and after:
                        drop_ctx.append((len(before[-1]), len(after[-1])))

    print()
    print("=" * 82)
    print(f"probe8   {root}")
    print("=" * 82)
    print(f"constituent_states が取れた試行 {n_cs_ok} ／ 取れなかった {n_cs_none}")
    if n_cs_ok == 0:
        print("★ ★ 警告  constituent_states から R の行を一つも拾えていません")
        print("   ★ 判定は信用できません")

    print()
    print("=" * 82)
    print("★ 0  検査：reason の長さ と 生存スロット数 は一致するか（★ (c) の検査）")
    print("=" * 82)
    tot = sum(mismatch.values())
    same = sum(v for (a, b), v in mismatch.items() if a == b)
    print(f"  一致 {same} / {tot} = {same/tot*100:.2f}%" if tot else "  データなし")
    print("  ★ ずれの上位")
    for (a, b), v in sorted(mismatch.items(), key=lambda x: -x[1])[:8]:
        if a == b:
            continue
        print(f"    reason {a} 個 ／ 生存 {b} 個   {v} 件")

    print()
    print("=" * 82)
    print("★ 1  (B2) のスロットは、走行末に 生きているか")
    print("=" * 82)
    t2 = sum(verdict.values())
    for k, v in verdict.most_common():
        print(f"  {k:>32}  {v:8d}  = {v/t2*100:6.2f}%" if t2 else "")

    print()
    print("=" * 82)
    print("★ 2  スロット数別")
    print("=" * 82)
    print(f"{'スロット数':>10} {'(B2)の数':>10} {'★生きている':>12} {'消えている':>11} {'不明':>8}")
    for kk in sorted(verdict_by_k):
        c = verdict_by_k[kk]
        n = sum(c.values())
        if n == 0:
            continue
        print(f"{kk:10d} {n:10d} {c.get('★ 生きている',0)/n*100:11.1f}% "
              f"{c.get('消えている',0)/n*100:10.1f}% "
              f"{c.get('生死不明（constituent_states が無い）',0)/n*100:7.1f}%")

    if drop_ctx:
        print()
        print("=" * 82)
        print("★ 3  (B2) の前後で、その def の生存スロット数はどう動いたか")
        print("=" * 82)
        b = [x for x, _ in drop_ctx]
        a = [y for _, y in drop_ctx]
        print(f"  件数 {len(drop_ctx)} ／ 直前の生存スロット数 中央 {statistics.median(b):.0f} "
              f"／ 猶予後 中央 {statistics.median(a):.0f}")
        dec = sum(1 for x, y in drop_ctx if y < x)
        same2 = sum(1 for x, y in drop_ctx if y == x)
        print(f"  減った {dec/len(drop_ctx)*100:.1f}% ／ 変わらない {same2/len(drop_ctx)*100:.1f}% "
              f"／ 増えた {(len(drop_ctx)-dec-same2)/len(drop_ctx)*100:.1f}%")

    print()
    print("★ 読み方")
    print("  ★ ★ 「生きている」が大半 → ★ ★ 生きているのに 二度と照合に載らない")
    print("  ★ 「消えている」が大半 → ★ 削除の拾い漏れ。★ (A) に吸収。主張にならない")
    print("  ★ §0 の一致率が低ければ → ★ ★ (B2) は集計の副作用の可能性がある")
    print("★ 判定は書きません。★ 本 probe は探索のためのものです。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
