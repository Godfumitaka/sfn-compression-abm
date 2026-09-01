#!/usr/bin/env python3
"""probe6.py — 「修復が完了しない」を打ち切りの交絡を除いて測る。

★ 本 probe は 探索 のためのものである。★ 台帳を読むだけ。

★ probe5 で出たこと
   ③（相手がいなかった）  ★ 99.64% が 中央 5 試行 で回収される → ★ 一時的な欠落
   ②（相手はいたが違った） ★ 52% が 走行末まで 二度と充足しない

★ ★ しかし ② の未回収には 打ち切りの交絡 がある
   走行末に立った ② は、★ 回収する時間が無い

★ 本 probe の対処
   ★ 「立った時刻 + 猶予 W」が 走行末を超えるものを 除外 する
   ★ W を複数の値で出し、★ 未回収率が W に依存するかを見る
   ★ ★ W を大きくしても未回収率が下がらなければ、★ 打ち切りではなく 本物

★ 追加で出すもの
   ★ 未回収の ② が、★ どの定義・どの薄さ に集中しているか
   ★ ★ 同じ (R, q) が 何度 ② を繰り返すか（★ 反復失敗）

使い方
    python3.14 probe6.py runs/main_2026-08-31 --max-cells 4

★ 走行中のディレクトリには使わないこと。
"""

import sys
import gzip
import glob
import json
import collections
import statistics

OK = "充足"
SAN = "③"
FAIL = "②"

WINDOWS = (10, 30, 100, 300, 600)


def main():
    if len(sys.argv) < 2:
        print("使い方: python3.14 probe6.py <走行ディレクトリ> [--max-cells N]")
        return 2
    root = sys.argv[1]
    max_cells = None
    if "--max-cells" in sys.argv:
        max_cells = int(sys.argv[sys.argv.index("--max-cells") + 1])

    paths = sorted(glob.glob(f"{root}/cells/*/*.jsonl.gz"))
    if max_cells is not None:
        cells = sorted({p.rsplit("/", 2)[1] for p in paths})[:max_cells]
        paths = [p for p in paths if p.rsplit("/", 2)[1] in cells]
    print(f"台帳 {len(paths)} 本を読みます")

    # 各 ② イベント： (立った時刻, 走行の長さ, 回収までの待ち or None, スロット数)
    events = []
    repeat = collections.Counter()      # (R,q) ごとの ② の回数
    n_trial = 0
    runs = set()

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
            for r in rows[:1]:
                if r.get("run_id"):
                    runs.add(r["run_id"])
            n_trial += T

            open_fail = collections.defaultdict(list)   # (R,q) → [(時刻, k)]
            local_rep = collections.Counter()
            for t, rec in enumerate(rows, 1):
                R = rec.get("R_used")
                if R is None:
                    continue
                reasons = (rec.get("constituent_reason_123") or {}).get(R) or {}
                if not reasons:
                    continue
                k = len(reasons)
                for q, v in reasons.items():
                    key = (R, q)
                    if v == OK:
                        for (t0, k0) in open_fail.pop(key, []):
                            events.append((t0, T, t - t0, k0))
                    elif v == FAIL:
                        open_fail[key].append((t, k))
                        local_rep[key] += 1
            for key, lst in open_fail.items():
                for (t0, k0) in lst:
                    events.append((t0, T, None, k0))
            for key, c in local_rep.items():
                repeat[c] += 1

    print()
    print("=" * 80)
    print(f"probe6   {root}")
    print("=" * 80)
    print(f"試行行 {n_trial} ／ 走行 {len(runs)} ／ ② イベント {len(events)}")

    print()
    print("=" * 80)
    print("★ 1  ② の未回収率から 打ち切り を除く")
    print("   猶予 W：★ 立った時刻 + W が 走行末を超えるものを 除外 する")
    print("=" * 80)
    print(f"{'猶予W':>7} {'対象の②':>10} {'W以内に回収':>12} {'★W以内に未回収':>15} {'★未回収率':>11}")
    for W in WINDOWS:
        elig = [(t0, T, w, k) for (t0, T, w, k) in events if t0 + W <= T]
        if not elig:
            continue
        res = sum(1 for (_t, _T, w, _k) in elig if w is not None and w <= W)
        unres = len(elig) - res
        print(f"{W:7d} {len(elig):10d} {res:12d} {unres:15d} {unres/len(elig)*100:10.2f}%")

    print()
    print("★ 参考：猶予を置かない場合（★ probe5 と同じ数え方）")
    res = sum(1 for e in events if e[2] is not None)
    print(f"  ② 総数 {len(events)} ／ 回収 {res} = {res/len(events)*100:.2f}% "
          f"／ 未回収 {len(events)-res} = {(len(events)-res)/len(events)*100:.2f}%")

    print()
    print("=" * 80)
    print("★ 2  薄さ（スロット数）別（★ 猶予 W=300 で固定）")
    print("=" * 80)
    W = 300
    by_k = collections.defaultdict(lambda: [0, 0])
    for (t0, T, w, k) in events:
        if t0 + W > T:
            continue
        by_k[k][0] += 1
        if not (w is not None and w <= W):
            by_k[k][1] += 1
    print(f"{'スロット数':>10} {'対象の②':>10} {'★未回収':>9} {'★未回収率':>11}")
    for k in sorted(by_k):
        n, u = by_k[k]
        if n == 0:
            continue
        print(f"{k:10d} {n:10d} {u:9d} {u/n*100:10.2f}%")

    print()
    print("=" * 80)
    print("★ 3  回収までの待ち時間の分布（★ 回収されたものだけ）")
    print("=" * 80)
    w = sorted(e[2] for e in events if e[2] is not None)
    if w:
        print(f"  中央 {statistics.median(w):.0f} ／ 平均 {statistics.mean(w):.1f} "
              f"／ 四分位 {w[len(w)//4]}–{w[3*len(w)//4]} ／ 最大 {max(w)}")
        for th in (1, 5, 10, 30, 100, 300):
            print(f"  {th:4d} 試行以内  {sum(1 for x in w if x <= th)/len(w)*100:6.2f}%")

    print()
    print("=" * 80)
    print("★ 4  同じ (定義, スロット) が 何度 ② を繰り返すか")
    print("=" * 80)
    tot = sum(repeat.values())
    print(f"{'②の回数':>9} {'(R,q)の数':>11} {'割合':>9}")
    for c in sorted(repeat)[:12]:
        print(f"{c:9d} {repeat[c]:11d} {repeat[c]/tot*100:8.2f}%")
    if repeat:
        big = sum(v for c, v in repeat.items() if c >= 5)
        print(f"  ★ 5 回以上 ② を出した (R,q)  {big} = {big/tot*100:.2f}%")

    print()
    print("★ 読み方")
    print("  ★ 猶予 W を大きくしても 未回収率が 下がらなければ、")
    print("     ★ ★ 打ち切りではなく 本物の「修復されない失敗」である")
    print("  ★ W とともに下がるなら、★ probe5 の 52% は 打ち切りの人工物である")
    print("★ 判定は書きません。★ 本 probe は探索のためのものです。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
