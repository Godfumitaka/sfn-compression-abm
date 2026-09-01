#!/usr/bin/env python3
"""probe5.py — 時間的回収の探針。

★ 本 probe は 探索 のためのものである。★ 事前登録された確認ではない。
★ エージェントの振る舞いを一切変えない。★ 台帳を読むだけ。

★ 何を測るか

  ある試行で、定義 R のスロット q が ③（場面に相手がいなかった）になった。
  ★ その主張は「相手がいるはずだ」と言ったまま、★ 答え合わせされずに残る。

  ★ その後の試行で、★ 同じ R の 同じ q が 充足 になれば → ★ 回収された
  ★ 走行が終わるまで 一度も充足にならなければ → ★ ★ 一度も答え合わせされなかった

★ みくじの例
   みくじを捨てた         → 主張が立つ
   数ヶ月 何も起きない     → ③ が続く
   5 ヶ月後に骨折         → ★ 充足（ついに相手が現れた）
   ★ 一生 何も起きない     → ★ ★ 回収されない

★ probe4 のバグを修正
  ★ 旧：ファイル名（seed001.jsonl.gz）をキーにしていた
  ★ ★ セルをまたいで重複し、4 セル分が 1 本の def として合算されていた
  ★ 新：★ 台帳の run_id をキーにする

使い方
    python3.14 probe5.py runs/main_2026-08-31 --max-cells 4

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
HANTEI = "判定不能"


def main():
    if len(sys.argv) < 2:
        print("使い方: python3.14 probe5.py <走行ディレクトリ> [--max-cells N]")
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

    waits = []                                  # ③ → 充足 の待ち時間
    never = 0                                   # 回収されなかった ③
    resolved = 0
    waits_by_k = collections.defaultdict(list)
    never_by_k = collections.Counter()
    res_by_k = collections.Counter()
    # 比較用：② → 充足 の待ち時間
    waits2 = []
    never2 = 0
    resolved2 = 0
    runs_seen = set()
    n_trial = 0

    for pi, p in enumerate(paths, 1):
        if pi % 20 == 0:
            print(f"  {pi}/{len(paths)}")
        with gzip.open(p, "rt") as f:
            f.readline()
            # (R, q) → その主張が ③ になった時刻のリスト（未回収）
            open_san = collections.defaultdict(list)
            open_fail = collections.defaultdict(list)
            krec = {}          # (R, q) → 直近のスロット数
            T = 0
            for line in f:
                if not line.strip():
                    continue
                rec = json.loads(line)
                if rec.get("record_type") != "trial":
                    continue
                T += 1
                n_trial += 1
                rid = rec.get("run_id")
                if rid:
                    runs_seen.add(rid)
                R = rec.get("R_used")
                if R is None:
                    continue
                reasons = (rec.get("constituent_reason_123") or {}).get(R) or {}
                if not reasons:
                    continue
                k = len(reasons)
                for q, v in reasons.items():
                    key = (R, q)
                    krec[key] = k
                    if v == OK:
                        # 未回収の ③ をすべて回収する
                        for t0 in open_san.pop(key, []):
                            w = T - t0
                            waits.append(w)
                            waits_by_k[krec.get(key, k)].append(w)
                            res_by_k[krec.get(key, k)] += 1
                            resolved += 1
                        for t0 in open_fail.pop(key, []):
                            waits2.append(T - t0)
                            resolved2 += 1
                    elif v == SAN:
                        open_san[key].append(T)
                    elif v == FAIL:
                        open_fail[key].append(T)
                    # 判定不能は保留（★ M-070 で ③ と同扱いだが、別に数えたいので除く）
            # 走行終了時に残ったもの＝回収されなかった
            for key, lst in open_san.items():
                never += len(lst)
                never_by_k[krec.get(key, 0)] += len(lst)
            for lst in open_fail.values():
                never2 += len(lst)

    print()
    print("=" * 80)
    print(f"probe5   {root}")
    print("=" * 80)
    print(f"試行行 {n_trial} ／ ★ run_id の種類 {len(runs_seen)}（★ probe4 のバグ検査）")

    print()
    print("=" * 80)
    print("★ 1  ③（場面に相手がいなかった）は、その後 回収されるか")
    print("=" * 80)
    tot = resolved + never
    if tot:
        print(f"③ の総数            {tot}")
        print(f"  ★ 回収された        {resolved}  = {resolved/tot*100:.2f}%")
        print(f"  ★ ★ 回収されなかった {never}  = {never/tot*100:.2f}%")
    if waits:
        w = sorted(waits)
        print()
        print("★ 回収までの待ち時間（試行数）")
        print(f"  中央 {statistics.median(w):.0f} ／ 平均 {statistics.mean(w):.1f} "
              f"／ 四分位 {w[len(w)//4]}–{w[3*len(w)//4]} ／ 最大 {max(w)}")
        for th in (1, 10, 50, 100, 300):
            print(f"  {th:4d} 試行以内に回収  {sum(1 for x in w if x <= th)/len(w)*100:6.2f}%")

    print()
    print("=" * 80)
    print("★ 2  薄さ（スロット数）別の回収率")
    print("=" * 80)
    print(f"{'スロット数':>10} {'③の数':>9} {'回収':>9} {'★未回収':>9} {'★未回収率':>10} {'待ち中央':>9}")
    for k in sorted(set(res_by_k) | set(never_by_k)):
        r = res_by_k[k]
        n = never_by_k[k]
        if r + n == 0:
            continue
        med = statistics.median(waits_by_k[k]) if waits_by_k[k] else float("nan")
        print(f"{k:10d} {r+n:9d} {r:9d} {n:9d} {n/(r+n)*100:9.2f}% {med:9.0f}")

    print()
    print("=" * 80)
    print("★ 3  比較：②（相手がいたが違った）の場合")
    print("=" * 80)
    tot2 = resolved2 + never2
    if tot2:
        print(f"② の総数 {tot2} ／ 回収 {resolved2} = {resolved2/tot2*100:.2f}% "
              f"／ ★ 未回収 {never2} = {never2/tot2*100:.2f}%")
    if waits2:
        w2 = sorted(waits2)
        print(f"  回収までの待ち時間  中央 {statistics.median(w2):.0f} ／ "
              f"平均 {statistics.mean(w2):.1f} ／ 最大 {max(w2)}")

    print()
    print("★ 読み方")
    print("  ★ ③ の未回収率が高く、★ ② の未回収率が低ければ、")
    print("     ★ ★ 「相手がいなかった」主張だけが 答え合わせされずに残っている")
    print("  ★ 薄い def ほど未回収率が高ければ、★ ★ 時間的回収が神話を支えている")
    print("★ 判定は書きません。★ 本 probe は探索のためのものです。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
