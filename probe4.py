#!/usr/bin/env python3
"""probe4.py — 神話の「反証到着率 × 寿命」を def 単位で直接数える。

★ 本 probe は 探索 のためのものである。★ 事前登録された確認ではない。

★ 出すもの
  1  ★ def ごとの  λ_err（一適用あたり ② が立つ確率）と T（採択回数）
     ★ ★ 神話の条件  λ_err × T < 1（生涯を通じて期待訂正回数が 1 回未満）
  2  ★ 時間帯で層別した 充足率・沈黙率
     ★ ★ 平均試行番号が スロット数と逆相関しているため、交絡の分離が要る
  3  ★ ③（場面に相手がいなかった）が どの述語で 起きているか
     ★ ★ 「回収待ち」の席がどこにあるかを見る

★ 用語
  ②        場面に相手がいたが違っていた → ★ 失敗信号が立ち、課金される
  ③        場面に相手がいなかった       → ★ 課金されない（M-070）
  判定不能  位置が特定できない           → ★ ③ と同じ扱い（M-070）
  充足      場面に相手がいて一致した

使い方
    python3.14 probe4.py runs/main_2026-08-31 --max-cells 4
    python3.14 probe4.py runs/abstainA1_2026-09-01 --max-cells 4

★ 読むだけ。★ 走行中のディレクトリには使わないこと。
"""

import sys
import gzip
import glob
import json
import collections
import statistics

FAIL = "②"
OK = "充足"
SILENT = ("③", "判定不能")
NBAND = 4


def main():
    if len(sys.argv) < 2:
        print("使い方: python3.14 probe4.py <走行ディレクトリ> [--max-cells N]")
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

    # (走行, def) 単位の集計
    per_def = collections.defaultdict(lambda: collections.Counter())
    # 時間帯 × スロット数
    band = collections.defaultdict(collections.Counter)
    # ③ の述語別
    san_pred = collections.Counter()
    ok_pred = collections.Counter()
    fail_pred = collections.Counter()
    n_trial = n_applied = 0
    horizon = 0

    for pi, p in enumerate(paths, 1):
        if pi % 20 == 0:
            print(f"  {pi}/{len(paths)}")
        run = p.rsplit("/", 1)[1]
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
            horizon = max(horizon, T)
            for t, rec in enumerate(rows, 1):
                n_trial += 1
                R = rec.get("R_used")
                if R is None:
                    continue
                n_applied += 1
                reasons = (rec.get("constituent_reason_123") or {}).get(R) or {}
                if not reasons:
                    continue
                c = collections.Counter(reasons.values())
                k = len(reasons)

                d = per_def[(run, R)]
                d["T"] += 1
                d["fired"] += int(c[FAIL] > 0)
                d["ok"] += c[OK]
                d["slots"] += k
                d["k_sum"] += k
                d["san"] += c["③"]
                d["hantei"] += c["判定不能"]
                d["fail"] += c[FAIL]

                b = min(NBAND - 1, (t - 1) * NBAND // max(T, 1))
                g = band[(b, k)]
                g["trials"] += 1
                g["slots"] += k
                g["ok"] += c[OK]
                g["fail"] += c[FAIL]
                g["silent"] += c["③"] + c["判定不能"]

                # ③ がどの述語で起きたか（充填・投影の述語を手がかりに）
                for pred in (rec.get("filled_predicate") or []):
                    if c["③"]:
                        san_pred[pred] += 1
                pe = rec.get("predicted_edge")
                if isinstance(pe, dict) and pe.get("predicate"):
                    if c[FAIL]:
                        fail_pred[pe["predicate"]] += 1
                    elif c[OK] == k:
                        ok_pred[pe["predicate"]] += 1

    print()
    print("=" * 82)
    print(f"probe4   {root}")
    print("=" * 82)
    print(f"試行行 {n_trial} ／ 適用あり {n_applied} ／ def 実体 {len(per_def)} ／ 地平 {horizon}")

    # ---- 1. λ_err × T ----
    print()
    print("=" * 82)
    print("★ 1  反証到着率 λ_err と 寿命 T（★ def 単位で直接数えた）")
    print("     λ_err = ② が立った適用 / 全適用   T = 採択回数")
    print("     ★ 期待訂正回数 = λ_err × T = ② が立った適用の 実数")
    print("=" * 82)
    by_k = collections.defaultdict(list)
    for (_run, _R), d in per_def.items():
        k = round(d["k_sum"] / d["T"])
        by_k[k].append(d)
    print(f"{'代表スロット数':>13} {'def数':>7} {'T中央':>7} {'T平均':>8} "
          f"{'λ_err':>8} {'★λ×T中央':>10} {'★一度も②なし':>13}")
    for k in sorted(by_k):
        g = by_k[k]
        lam = sum(x["fired"] for x in g) / sum(x["T"] for x in g)
        prod = [x["fired"] for x in g]
        never = sum(1 for x in g if x["fired"] == 0) / len(g)
        print(f"{k:13d} {len(g):7d} {statistics.median([x['T'] for x in g]):7.0f} "
              f"{statistics.mean(x['T'] for x in g):8.1f} {lam:8.4f} "
              f"{statistics.median(prod):10.1f} {never*100:12.1f}%")

    print()
    print("★ 神話（代表スロット ≤ 2）と 真（≥ 3）")
    for lab, ks in [("神話", [1, 2]), ("真", [3, 4, 5, 6, 7])]:
        g = [x for k in ks for x in by_k.get(k, [])]
        if not g:
            continue
        never = sum(1 for x in g if x["fired"] == 0) / len(g)
        print(f"  {lab:>4}  def {len(g):6d}  T平均 {statistics.mean(x['T'] for x in g):7.1f}  "
              f"λ_err {sum(x['fired'] for x in g)/sum(x['T'] for x in g):.4f}  "
              f"★ 一度も ② を受けない {never*100:.1f}%")

    # ---- 2. 時間帯で層別 ----
    print()
    print("=" * 82)
    print("★ 2  時間帯で層別（★ 交絡の分離）  帯1 = 走行の最初の 1/4")
    print("=" * 82)
    print(f"{'帯':>3} {'スロット数':>10} {'適用':>8} {'★充足率':>9} {'②率':>8} {'★沈黙率S':>10}")
    for b in range(NBAND):
        for k in sorted({kk for (bb, kk) in band if bb == b}):
            g = band[(b, k)]
            if g["slots"] == 0:
                continue
            den = g["fail"] + g["silent"]
            S = g["silent"] / den if den else float("nan")
            print(f"{b+1:3d} {k:10d} {g['trials']:8d} {g['ok']/g['slots']:9.4f} "
                  f"{g['fail']/g['slots']:8.4f} {S:10.4f}")
        print()

    # ---- 3. ③ の述語 ----
    print("=" * 82)
    print("★ 3  述語別（★ 上位 12）  ★ 回収待ちの席がどこにあるか")
    print("=" * 82)
    print(f"{'述語':>10} {'③を伴う充填':>12} {'②を伴う出力':>12} {'全充足の出力':>12}")
    preds = set(san_pred) | set(fail_pred) | set(ok_pred)
    for pred in sorted(preds, key=lambda x: -(san_pred[x] + fail_pred[x] + ok_pred[x]))[:12]:
        print(f"{pred:>10} {san_pred[pred]:12d} {fail_pred[pred]:12d} {ok_pred[pred]:12d}")

    print()
    print("★ 判定は書きません。★ 本 probe は探索のためのものです。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
