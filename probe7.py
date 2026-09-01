#!/usr/bin/env python3
"""probe7.py — 未回収の ② が「削除」なのか「未修復」なのかを分ける。

★ 本 probe は 探索 のためのものである。★ 台帳を読むだけ。

★ probe6 で出たこと
   ② の 53% が、★ 猶予 600 試行を置いても 二度と充足しない（★ 打ち切りではない）
   ★ 部分 2 個の定義では 74%
   ★ 65% の (定義, スロット) が 2 回以上 同じ場所で失敗している

★ ★ しかし 中身が二通りありうる

   (A) ★ 削除された   ★ 失敗した構成素が θ′ で消えた
       → ★ ★ 正常な動作。★ 主張にならない

   (B) ★ ★ 未修復     ★ 構成素は生きているのに、二度と充足しない
       → ★ ★ ★ 「エラーは届くが直らない」の直接の証拠

   (C) ★ 使われなくなった  ★ その定義が二度と採択されなかった
       → ★ ★ 訂正の機会が来なかった。★ (え) と同じ話

★ ★ 本 probe は (A)(B)(C) を分ける。

★ 分け方
   ★ ② が立った (R, q) について、走行末までを追う
     ・deletion_event に (R, q) が現れる      → ★ (A) 削除
     ・その後 R が一度も採択されない          → ★ (C) 不使用
     ・R は採択されるが (R,q) が充足しない    → ★ ★ (B) 未修復
       ★ ★ さらに その間 (R,q) が reason に現れたか も数える
         現れた → ★ ★ 直る機会があったのに直らなかった（★ 強い証拠）
         現れない → ★ そのスロットが照合に載らなかった

使い方
    python3.14 probe7.py runs/main_2026-08-31 --max-cells 4

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
W = 300      # 猶予。probe6 と揃える


def del_keys(rec):
    """deletion_event から (R, slot_index) を取り出す。★ 形が不明なので広く拾う。"""
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
        q = e.get("slot_index")
        if q is None:
            q = e.get("slot")
        if R is not None and q is not None:
            out.append((str(R), str(q)))
    return out


def main():
    if len(sys.argv) < 2:
        print("使い方: python3.14 probe7.py <走行ディレクトリ> [--max-cells N]")
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

    cat = collections.Counter()
    cat_by_k = collections.defaultdict(collections.Counter)
    del_seen = 0
    del_shape = collections.Counter()
    n_trial = 0
    reappear = []          # (B) のうち、その後 reason に現れた回数

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
            n_trial += T

            # 事前に索引を作る
            used_at = collections.defaultdict(list)      # R → [t]
            reason_at = collections.defaultdict(list)    # (R,q) → [(t, 値)]
            del_at = {}                                  # (R,q) → t
            for t, rec in enumerate(rows, 1):
                for key in del_keys(rec):
                    del_seen += 1
                    del_shape[type(rec.get("deletion_event")).__name__] += 1
                    if key not in del_at:
                        del_at[key] = t
                R = rec.get("R_used")
                if R is None:
                    continue
                used_at[R].append(t)
                reasons = (rec.get("constituent_reason_123") or {}).get(R) or {}
                for q, v in reasons.items():
                    reason_at[(R, str(q))].append((t, v))

            # ② イベントを分類
            for key, seq in reason_at.items():
                R, q = key
                k = None
                for t, v in seq:
                    if v != FAIL:
                        continue
                    if t + W > T:
                        continue                    # 打ち切りを除く
                    # その後 W 以内に充足したか
                    later = [(tt, vv) for tt, vv in seq if t < tt <= t + W]
                    if any(vv == OK for _tt, vv in later):
                        cat["回収された"] += 1
                        continue
                    # 未回収。原因を分ける
                    dt = del_at.get(key)
                    if dt is not None and t < dt <= t + W:
                        cat["(A) 削除された"] += 1
                        c = "(A) 削除された"
                    else:
                        after_use = [tt for tt in used_at.get(R, []) if t < tt <= t + W]
                        if not after_use:
                            cat["(C) R が二度と使われない"] += 1
                            c = "(C) R が二度と使われない"
                        elif later:
                            cat["(B1) 照合に載ったが充足せず"] += 1
                            c = "(B1) 照合に載ったが充足せず"
                            reappear.append(len(later))
                        else:
                            cat["(B2) R は使われたがスロットが載らず"] += 1
                            c = "(B2) R は使われたがスロットが載らず"
                    # スロット数の代表値
                    kk = len({qq for (RR, qq) in reason_at if RR == R})
                    cat_by_k[kk][c] += 1

    print()
    print("=" * 82)
    print(f"probe7   {root}")
    print("=" * 82)
    print(f"試行行 {n_trial} ／ deletion_event で拾えた行 {del_seen}")
    if del_seen == 0:
        print("★ ★ 警告  deletion_event から (R, slot) を一つも拾えていません")
        print("   ★ 欄の形が想定と違います。★ (A) の判定は 信用できません")
    else:
        print(f"   deletion_event の型 {dict(del_shape)}")

    print()
    print("=" * 82)
    print("★ 1  ② が回収されなかった理由の内訳")
    print("=" * 82)
    tot = sum(cat.values())
    unres = tot - cat["回収された"]
    for k in ["回収された", "(A) 削除された", "(C) R が二度と使われない",
              "(B1) 照合に載ったが充足せず", "(B2) R は使われたがスロットが載らず"]:
        v = cat.get(k, 0)
        share = v / tot * 100 if tot else 0
        share2 = v / unres * 100 if unres and k != "回収された" else float("nan")
        if k == "回収された":
            print(f"{k:>30}  {v:8d}  全体の {share:6.2f}%")
        else:
            print(f"{k:>30}  {v:8d}  全体の {share:6.2f}%  ／ 未回収のうち {share2:6.2f}%")

    print()
    print("=" * 82)
    print("★ 2  スロット数別（★ 未回収のうちの内訳）")
    print("=" * 82)
    keys = ["(A) 削除された", "(C) R が二度と使われない",
            "(B1) 照合に載ったが充足せず", "(B2) R は使われたがスロットが載らず"]
    print(f"{'スロット数':>10} {'未回収':>8} " + "".join(f"{k[:6]:>10}" for k in keys))
    for kk in sorted(cat_by_k):
        c = cat_by_k[kk]
        n = sum(c.get(k, 0) for k in keys)
        if n == 0:
            continue
        print(f"{kk:10d} {n:8d} " + "".join(f"{c.get(k,0)/n*100:9.1f}%" for k in keys))

    if reappear:
        print()
        print("=" * 82)
        print("★ 3  (B1) — 直る機会があったのに直らなかった回数")
        print("=" * 82)
        r = sorted(reappear)
        print(f"  件数 {len(r)} ／ その後 照合に載った回数  中央 {statistics.median(r):.0f} "
              f"／ 平均 {statistics.mean(r):.1f} ／ 最大 {max(r)}")
        print(f"  ★ 5 回以上 載ったのに充足しなかった  "
              f"{sum(1 for x in r if x >= 5)} = {sum(1 for x in r if x >= 5)/len(r)*100:.1f}%")

    print()
    print("★ 読み方")
    print("  ★ (A) が大半  → ★ 失敗した構成素は 消える。★ 正常な動作。主張にならない")
    print("  ★ (C) が大半  → ★ 訂正の機会が来ない。★ (え) と同じ話")
    print("  ★ ★ (B1) が大きい → ★ ★ 直る機会があったのに直らない。★ ★ 新しい主張になる")
    print("★ 判定は書きません。★ 本 probe は探索のためのものです。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
