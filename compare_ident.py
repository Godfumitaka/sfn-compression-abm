#!/usr/bin/env python3
"""識別軸の3条件比較 — 2026-09-09

  条件(a) 旧cached全行   runs/v2a_<腕>_2026-09-08          （既存480）
  条件(b) fresh全行      runs/ident_2026-09-08/b_<腕>      （新480）
  条件(c) fresh live     runs/ident_2026-09-08/c_<腕>      （新480）

  (a)→(b) 自己点数キャッシュ（NSIM の分母の使い回し）を切った効果
  (b)→(c) 識別グラフから墓石（削除済みで台帳に残る構成素行）を外した効果

★ 既存の集計3本には手を触れない。新規の比較のみ。
★ 中心的過程 ＝ 生存最大 >=6 かつ 最終 <=2。計数は完全キー (条件,腕,セル,seed,R)。
★ 厚みは constituent_states の alive 行数から数える（診断で方式REGと一致・不一致0）。

使い方
  python3.12 compare_ident.py
  python3.12 compare_ident.py --cells th1.2000
  python3.12 compare_ident.py --arms t067_w00 --limit 20
"""

from __future__ import annotations

import argparse
import collections
import glob
import gzip
import json
import os

ARMS = ("t067_w00", "t067_w10", "t200_w00", "t200_w10")

CONDS = (
    ("a", "旧cached全行", "runs/v2a_{arm}_2026-09-08"),
    ("b", "fresh全行", "runs/ident_2026-09-08/b_{arm}"),
    ("c", "fresh live", "runs/ident_2026-09-08/c_{arm}"),
)


def scan(path):
    """一走行を読む。定義ごとの厚み軌跡と、走行全体の予測集計を返す。"""
    opener = gzip.open if path.endswith(".gz") else open
    traj = collections.defaultdict(list)
    rows_final = {}          # R -> 最終の総行数（生存＋墓石）
    hit = miss = abstain = 0
    with opener(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            if not isinstance(rec, dict) or rec.get("record_type") != "trial":
                continue

            live = collections.Counter()
            total = collections.Counter()
            for st in rec.get("constituent_states") or []:
                total[st["R"]] += 1
                if st.get("alive"):
                    live[st["R"]] += 1
            for name, count in live.items():
                seq = traj[name]
                if not seq or seq[-1] != count:
                    seq.append(count)
            rows_final.update(total)

            if rec.get("abstain_reason"):
                abstain += 1
            elif rec.get("hit") is not None:
                if int(rec["hit"]) == 1:
                    hit += 1
                else:
                    miss += 1
    return traj, rows_final, (hit, miss, abstain)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", default="")
    ap.add_argument("--arms", default="")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    arms = tuple(a for a in ARMS if not args.arms or a in args.arms.split(","))

    agg = {}
    for key, label, tmpl in CONDS:
        defs = 0
        birth = collections.Counter()
        thin = collections.Counter()          # 誕生厚み -> 最終<=2
        central = 0
        reached = 0                            # 一度でも <=2 へ到達
        refilled = 0                           # 到達後、最終 >2
        rows_gt7 = 0
        rows_max = 0
        hit = miss = abstain = 0
        nfiles = 0

        for arm in arms:
            base = tmpl.format(arm=arm)
            if not os.path.isdir(base):
                continue
            paths = sorted(glob.glob(f"{base}/cells/*/seed*.jsonl*"))
            if args.cells:
                paths = [p for p in paths if args.cells in os.path.dirname(p)]
            if args.limit:
                paths = paths[: args.limit]
            for path in paths:
                nfiles += 1
                traj, rows_final, (h, m, ab) = scan(path)
                hit += h
                miss += m
                abstain += ab
                for name, seq in traj.items():
                    if not seq:
                        continue
                    defs += 1
                    birth[seq[0]] += 1
                    if seq[-1] <= 2:
                        thin[seq[0]] += 1
                    if max(seq) >= 6 and seq[-1] <= 2:
                        central += 1
                    if min(seq) <= 2 and max(seq) >= 6:
                        reached += 1
                        if seq[-1] > 2:
                            refilled += 1
                    tot = rows_final.get(name, 0)
                    if tot > 7:
                        rows_gt7 += 1
                    rows_max = max(rows_max, tot)

        agg[key] = dict(
            label=label, nfiles=nfiles, defs=defs, birth=birth, thin=thin,
            central=central, reached=reached, refilled=refilled,
            rows_gt7=rows_gt7, rows_max=rows_max,
            hit=hit, miss=miss, abstain=abstain,
        )

    print("=" * 78)
    print("識別軸の3条件比較 — 2026-09-09")
    if args.cells:
        print(f"セル絞り {args.cells}")
    if args.arms:
        print(f"腕絞り   {args.arms}")
    print("=" * 78)

    def row(title, fn, fmt="{:>14}"):
        cells = "".join(fmt.format(fn(agg[k])) for k, _, _ in CONDS)
        print(f"   {title:<26}{cells}")

    print()
    print(f"   {'':<26}{'(a) 旧cached':>14}{'(b) fresh全行':>14}{'(c) fresh live':>14}")
    print("   " + "-" * 68)
    row("台帳の本数", lambda d: d["nfiles"])
    row("定義数（走行×R）", lambda d: d["defs"])
    row("★ 中心的過程", lambda d: d["central"])
    row("厚→<=2 に到達", lambda d: d["reached"])
    row("  うち補充で最終>2", lambda d: d["refilled"])
    row("誕生6 の定義数", lambda d: d["birth"][6])
    row("  うち最終<=2", lambda d: d["thin"][6])
    row("  到達率", lambda d: f"{d['thin'][6] / d['birth'][6]:.4f}"
        if d["birth"][6] else "-")
    row("誕生7 の定義数", lambda d: d["birth"][7])
    row("  うち最終<=2", lambda d: d["thin"][7])
    row("総行数>7 の定義", lambda d: d["rows_gt7"])
    row("総行数の最大", lambda d: d["rows_max"])
    row("的中", lambda d: d["hit"])
    row("誤答", lambda d: d["miss"])
    row("棄権", lambda d: d["abstain"])
    row("的中率", lambda d: f"{d['hit'] / (d['hit'] + d['miss']):.4f}"
        if (d["hit"] + d["miss"]) else "-")
    row("被覆率", lambda d: f"{(d['hit'] + d['miss']) / (d['hit'] + d['miss'] + d['abstain']):.4f}"
        if (d["hit"] + d["miss"] + d["abstain"]) else "-")

    print()
    print("   ★ (a)→(b) が自己点数キャッシュの効果、(b)→(c) が墓石を識別から外す効果。")
    print("   ★ 予測の欄が全て0なら台帳の欄名が想定と違う。scan() の out.get を確認すること。")


if __name__ == "__main__":
    main()
