#!/usr/bin/env python3
"""probe3.py v2 — 賭けC の機構形（登録II）を台帳から直読する。

★ v1 からの変更（撤回58・59・60 を受けて）
  ・m_live はエージェント全体の総数だった → ★ 使わない
  ・constituent_states は全 def の一覧だった → ★ R_used でフィルタ（本版では未使用）
  ・reason の値は 5 種だった（充足／②／③／判定不能／①）→ ★ 実測の形を使う

★ 台帳 M-070（確定 2026-08-27）
  「判定不能（位置が特定できない行）は ③ と同じ扱いにする。分子 0・分母 +1・課金なし」
  → ★ ②         は 誤りで 課金される（★ 失敗信号が立つ）
  → ★ ③・判定不能 は 誤りだが 課金されない（★ 失敗信号が立たない）

★ 沈黙率  S = (③ + 判定不能) / (② + ③ + 判定不能)
          「相手が見つからなかったスロットのうち、失敗信号が立たなかった割合」

事前登録：事前登録_解離と機構_2026-09-01.md
  予測A   S は def の生存スロット数が小さいほど 高い       0.75
  予測A′  「充足が 0 の適用試行」での ② 発火率は
          全適用より 低い                                   0.70
  採用条件  「充足が 0」が全適用の 1% 以上なら A′ を判定する

使い方
    python3.14 probe3.py runs/ldecouple_2026-08-31 --max-cells 2
    python3.14 probe3.py runs/ldecouple_2026-08-31

★ 読むだけ。★ 走行中のディレクトリには使わないこと（.gz を開くため）。
"""

import sys
import gzip
import glob
import json
import collections

FAIL = "②"
SILENT = ("③", "判定不能")
OK = "充足"


def main():
    if len(sys.argv) < 2:
        print("使い方: python3.14 probe3.py <走行ディレクトリ> [--max-cells N]")
        return 2
    root = sys.argv[1]
    max_cells = None
    if "--max-cells" in sys.argv:
        max_cells = int(sys.argv[sys.argv.index("--max-cells") + 1])

    paths = sorted(glob.glob(f"{root}/cells/*/*.jsonl.gz"))
    if max_cells is not None:
        cells = sorted({p.rsplit("/", 2)[1] for p in paths})[:max_cells]
        paths = [p for p in paths if p.rsplit("/", 2)[1] in cells]
    ncell = len({p.rsplit("/", 2)[1] for p in paths})
    print(f"台帳 {len(paths)} 本を読みます（{ncell} セル）")

    n_trial = 0
    n_applied = 0
    vals = collections.Counter()
    disagree = collections.Counter()

    by_k = collections.defaultdict(collections.Counter)   # 生存スロット数別
    tsum = collections.Counter()
    tcnt = collections.Counter()
    by_f = collections.defaultdict(collections.Counter)   # f 別（予測C）

    n_nohit = 0
    nohit_fired = 0
    all_fired = 0
    n_reasoned = 0

    for pi, p in enumerate(paths, 1):
        if pi % 20 == 0:
            print(f"  {pi}/{len(paths)}")
        with gzip.open(p, "rt") as f:
            f.readline()
            t = 0
            for line in f:
                if not line.strip():
                    continue
                rec = json.loads(line)
                if rec.get("record_type") != "trial":
                    continue
                n_trial += 1
                t += 1
                R = rec.get("R_used")
                if R is None:
                    continue
                n_applied += 1

                reasons = (rec.get("constituent_reason_123") or {}).get(R) or {}
                if not reasons:
                    continue
                n_reasoned += 1
                k = len(reasons)
                c = collections.Counter(reasons.values())
                for v in reasons.values():
                    vals[v] += 1

                fired = c[FAIL] > 0
                all_fired += int(fired)

                t2 = bool(rec.get("type2_fired"))
                if t2 != fired:
                    disagree[(t2, fired)] += 1

                b = by_k[k]
                b["trials"] += 1
                b["fired_trials"] += int(fired)
                b["ok"] += c[OK]
                b["fail"] += c[FAIL]
                b["san"] += c["③"]
                b["hantei"] += c["判定不能"]
                b["silent"] += c["③"] + c["判定不能"]
                tsum[k] += t
                tcnt[k] += 1

                fv = rec.get("f_realized")
                if fv is not None:
                    g = by_f[fv]
                    g["trials"] += 1
                    g["fail"] += c[FAIL]
                    g["silent"] += c["③"] + c["判定不能"]

                if c[OK] == 0:
                    n_nohit += 1
                    nohit_fired += int(fired)

    print()
    print("=" * 78)
    print(f"probe3 v2   {root}")
    print("=" * 78)
    print(f"試行行                     {n_trial}")
    print(f"適用あり（R_used 非null）   {n_applied}")
    print(f"reason が非空               {n_reasoned}")
    print(f"reason の値の分布           {dict(vals)}")
    print()
    print("★ type2_fired と reason の ② の食い違い")
    if not disagree:
        print("   なし")
    for (t2, fired), v in sorted(disagree.items()):
        print(f"   type2_fired={t2} / reasonに②={fired}  →  {v} 件")

    print()
    print("=" * 78)
    print("★ 予測A   沈黙率 S は def の生存スロット数が小さいほど 高いか")
    print("   S = (③ + 判定不能) / (② + ③ + 判定不能)")
    print("=" * 78)
    print(f"{'スロット数':>9} {'適用試行':>9} {'非充足':>8} {'②':>7} {'③':>6} "
          f"{'判定不能':>8} {'★沈黙率S':>10} {'平均試行番号':>12}")
    for k in sorted(by_k):
        b = by_k[k]
        den = b["fail"] + b["silent"]
        if den == 0:
            print(f"{k:9d} {b['trials']:9d} {0:8d} {0:7d} {0:6d} {0:8d} "
                  f"{'---':>10} {tsum[k]/tcnt[k]:12.1f}")
            continue
        print(f"{k:9d} {b['trials']:9d} {den:8d} {b['fail']:7d} {b['san']:6d} "
              f"{b['hantei']:8d} {b['silent']/den:10.4f} {tsum[k]/tcnt[k]:12.1f}")

    print()
    print("★ 参考：試行単位の沈黙率（★ ② が一つも立たなかった適用試行の割合）")
    print(f"{'スロット数':>9} {'適用試行':>9} {'②が立った':>10} {'★試行S':>9}")
    for k in sorted(by_k):
        b = by_k[k]
        if b["trials"] == 0:
            continue
        print(f"{k:9d} {b['trials']:9d} {b['fired_trials']:10d} "
              f"{1 - b['fired_trials']/b['trials']:9.4f}")

    print()
    print("=" * 78)
    print("★ 予測C   沈黙率は f に依存しないか（D8(b) の検査）")
    print("=" * 78)
    print(f"{'f':>9} {'適用試行':>9} {'②':>8} {'非充足':>8} {'沈黙率S':>9}")
    for fv in sorted(by_f):
        g = by_f[fv]
        den = g["fail"] + g["silent"]
        if den == 0:
            continue
        print(f"{fv:9.4f} {g['trials']:9d} {g['fail']:8d} {den:8d} {g['silent']/den:9.4f}")

    print()
    print("=" * 78)
    print("★ 案A   充足が 0 の適用試行（★ その def が何一つ当てていない）")
    print("=" * 78)
    if n_reasoned:
        share = n_nohit / n_reasoned
        print(f"件数 {n_nohit} / {n_reasoned} = {share*100:.3f}%")
        ok = "★ 採用" if share >= 0.01 else "★ 採用しない（判定量を捨てる）"
        print(f"★ 採用条件は 1% 以上 → {ok}")
        if n_nohit:
            print()
            print("★ 予測A′  充足0 の試行での ② 発火率は 全適用より 低いか")
            print(f"   全適用    ② 発火率 {all_fired/n_reasoned:.4f}  n={n_reasoned}")
            print(f"   ★ 充足0   ② 発火率 {nohit_fired/n_nohit:.4f}  n={n_nohit}")

    print()
    print("★ 判定は書きません。事前登録の判定規則に照らして読んでください。")
    print("★ ★ 平均試行番号の列は 時間交絡 の検査です。")
    print("   スロット数と平均試行番号が強く相関していれば、")
    print("   S の傾きは スロット数ではなく 時間 の効果かもしれません。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
