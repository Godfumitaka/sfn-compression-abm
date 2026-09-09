#!/usr/bin/env python3
"""誕生時の厚みの測り方を突き合わせる診断 — 2026-09-09

★ 既存の測り方を変えない。二つの測り方を並べて出すだけ。
★ この結果で変わる判断：台帳追記10 の C-44前半・C-46・C-47 を確定行にしてよいか。

  方式CS   constituent_states の alive だけから m_live 軌跡を作る（★ 現行3本と同じ）
  方式REG  reg_del_events の kind=registration を軌跡の起点に入れる（★ 引き継ぎ §7-3）

使い方
  python3.12 diag_thickness.py
  python3.12 diag_thickness.py --cells th1.2000 --limit 40
"""

from __future__ import annotations

import argparse
import collections
import glob
import gzip
import json
import os

ARMS = ("t067_w00", "t067_w10", "t200_w00", "t200_w10")


def scan(path):
    """一走行を読み、方式CS と方式REG の軌跡を両方返す。"""
    opener = gzip.open if path.endswith(".gz") else open
    seq_cs = collections.defaultdict(list)
    seq_reg = collections.defaultdict(list)
    reg_seen = collections.defaultdict(list)   # R -> [(trial, 構成素数)]
    kinds = collections.Counter()
    trial = 0

    with opener(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            if not isinstance(rec, dict) or rec.get("record_type") != "trial":
                continue
            trial = rec.get("trial", trial + 1)

            for ev in rec.get("reg_del_events") or []:
                kinds[ev.get("kind")] += 1
                if ev.get("kind") != "registration":
                    continue
                name = ev.get("R")
                cons = ev.get("constituents") or []
                reg_seen[name].append((trial, len(cons)))
                if not seq_reg[name]:
                    seq_reg[name].append(len(cons))

            live = collections.Counter()
            for st in rec.get("constituent_states") or []:
                if st.get("alive"):
                    live[st["R"]] += 1
            for name, count in live.items():
                for seq in (seq_cs[name], seq_reg[name]):
                    if not seq or seq[-1] != count:
                        seq.append(count)

    return seq_cs, seq_reg, reg_seen, kinds


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", default="", help="セル名に含まれる文字列で絞る")
    ap.add_argument("--limit", type=int, default=0, help="読む台帳の本数上限")
    args = ap.parse_args()

    paths = []
    for arm in ARMS:
        paths += sorted(glob.glob(f"runs/v2a_{arm}_2026-09-08/cells/*/seed*.jsonl*"))
    if args.cells:
        paths = [p for p in paths if args.cells in os.path.dirname(p)]
    if args.limit:
        paths = paths[: args.limit]

    print("=" * 74)
    print("誕生時の厚み — 方式CS と 方式REG の突き合わせ")
    print(f"台帳 {len(paths)} 本" + (f" / セル絞り {args.cells}" if args.cells else ""))
    print("=" * 74)

    kinds = collections.Counter()
    pair = collections.Counter()        # (REG起点, CS起点) -> 件数
    multi_reg = collections.Counter()   # 同一Rへの registration 回数
    birth_cs = collections.Counter()
    birth_reg = collections.Counter()
    thin_cs = collections.Counter()     # 誕生厚み -> 最終<=2 の件数
    thin_reg = collections.Counter()
    central_cs = 0
    central_reg = 0

    for path in paths:
        cs, reg, reg_seen, k = scan(path)
        kinds += k
        for name, s_cs in cs.items():
            s_reg = reg[name]
            if not s_cs or not s_reg:
                continue
            pair[(s_reg[0], s_cs[0])] += 1
            multi_reg[len(reg_seen.get(name, []))] += 1
            birth_cs[s_cs[0]] += 1
            birth_reg[s_reg[0]] += 1
            if s_cs[-1] <= 2:
                thin_cs[s_cs[0]] += 1
            if s_reg[-1] <= 2:
                thin_reg[s_reg[0]] += 1
            if max(s_cs) >= 6 and s_cs[-1] <= 2:
                central_cs += 1
            if max(s_reg) >= 6 and s_reg[-1] <= 2:
                central_reg += 1

    print("\n■ reg_del_events の kind")
    for name, n in kinds.most_common():
        print(f"   {str(name):24s} {n:8d}")

    print("\n■ 同一 R への registration 回数（再登録の有無）")
    for n, c in sorted(multi_reg.items()):
        print(f"   {n:3d} 回   {c:7d} 定義")

    print("\n■ 起点の対応  (方式REG, 方式CS) -> 定義数")
    diff = same = 0
    for (r, c), n in sorted(pair.items()):
        mark = "" if r == c else "   ★ 不一致"
        print(f"   REG {r:2d} / CS {c:2d}   {n:7d}{mark}")
        if r == c:
            same += n
        else:
            diff += n
    tot = same + diff
    if tot:
        print(f"\n   一致 {same} / 不一致 {diff} / 合計 {tot}"
              f"   （不一致率 {diff / tot:.4f}）")

    print("\n■ 誕生厚みの分布")
    print(f"   {'厚み':>4} {'方式CS':>10} {'方式REG':>10}")
    for m in sorted(set(birth_cs) | set(birth_reg)):
        print(f"   {m:4d} {birth_cs[m]:10d} {birth_reg[m]:10d}")

    print("\n■ 誕生厚み別の 最終<=2 到達率")
    print(f"   {'厚み':>4} {'CS到達/母数':>16} {'率':>8}   {'REG到達/母数':>16} {'率':>8}")
    for m in sorted(set(birth_cs) | set(birth_reg)):
        rc = thin_cs[m] / birth_cs[m] if birth_cs[m] else 0.0
        rr = thin_reg[m] / birth_reg[m] if birth_reg[m] else 0.0
        print(f"   {m:4d} {thin_cs[m]:7d}/{birth_cs[m]:<8d} {rc:8.4f}   "
              f"{thin_reg[m]:7d}/{birth_reg[m]:<8d} {rr:8.4f}")

    print("\n■ 中心的過程（生存最大>=6 かつ 最終<=2）")
    print(f"   方式CS   {central_cs}")
    print(f"   方式REG  {central_reg}")
    print("\n★ 台帳ごとの計数。掃引軸をまたいだ重複除去は行っていない（D-23 とは別）。")


if __name__ == "__main__":
    main()
