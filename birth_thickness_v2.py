#!/usr/bin/env python3
"""誕生時の厚みごとに、薄化の到達点を集計する。

★ 定義は (腕, セル, seed, 定義名) で一意に数える。
★ 掃引軸をまたいだ同一定義の重複は数えない。

使い方
    python3.14 birth_thickness.py > birth_thickness.txt 2>&1
"""
from __future__ import annotations

import collections
import glob
import gzip
import json
import os

ARMS = ["t067_w00", "t067_w10", "t200_w00", "t200_w10"]
LABEL = {
    "t067_w00": "比読み τ=0.67  w=0.0",
    "t067_w10": "比読み τ=0.67  w=1.0",
    "t200_w00": "絶対 k=1      w=0.0",
    "t200_w10": "絶対 k=1      w=1.0",
}


def scan(path: str) -> dict[str, list[int]]:
    """一走行から、定義ごとの m_live 軌跡（変化点のみ）を返す。"""
    opener = gzip.open if path.endswith(".gz") else open
    traj: dict[str, list[int]] = collections.defaultdict(list)
    with opener(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            if not isinstance(rec, dict) or rec.get("record_type") != "trial":
                continue
            live = collections.Counter()
            for state in rec.get("constituent_states") or []:
                if state.get("alive"):
                    live[state["R"]] += 1
            for name, count in live.items():
                seq = traj[name]
                if not seq or seq[-1] != count:
                    seq.append(count)
    return traj


def main() -> None:
    print("=" * 78)
    print("誕生時の厚みごとの薄化 — 2026-09-08")
    print("=" * 78)

    for arm in ARMS:
        base = f"runs/v2a_{arm}_2026-09-08"
        if not os.path.isdir(base):
            continue

        # (θ′, 充填規則) ごとに集計
        by_cell: dict[str, list[tuple[int, int, int]]] = collections.defaultdict(list)
        for path in sorted(glob.glob(f"{base}/cells/*/seed*.jsonl*")):
            cell = os.path.basename(os.path.dirname(path))
            for _name, seq in scan(path).items():
                if seq:
                    by_cell[cell].append((seq[0], max(seq), seq[-1]))

        print(f"\n{'─' * 78}")
        print(f"■ {LABEL[arm]}")
        print(f"{'─' * 78}")

        for cell in sorted(by_cell):
            rows = by_cell[cell]
            by_birth: dict[int, list[tuple[int, int, int]]] = collections.defaultdict(list)
            for row in rows:
                by_birth[row[0]].append(row)

            print(f"\n  {cell}   定義 {len(rows)} 本")
            print(f"    {'誕生':>4}{'本数':>6}{'最終≤2':>8}{'★率':>8}"
                  f"{'最終≤3':>8}{'率':>8}{'最大>誕生':>10}")
            for birth in sorted(by_birth):
                group = by_birth[birth]
                n = len(group)
                le2 = sum(1 for _b, _m, f in group if f <= 2)
                le3 = sum(1 for _b, _m, f in group if f <= 3)
                grew = sum(1 for b, m, _f in group if m > b)
                print(f"    {birth:>4}{n:>6}{le2:>8}{100 * le2 / n:>7.1f}%"
                      f"{le3:>8}{100 * le3 / n:>7.1f}%{grew:>10}")

        # 腕の合計
        allrows = [r for rows in by_cell.values() for r in rows]
        thick = [r for r in allrows if r[1] >= 6]
        proc = [r for r in thick if r[2] <= 2]
        print(f"\n  ★ 腕の合計")
        print(f"    全定義 {len(allrows)}")
        print(f"    ★ 生存最大 ≥6 だった定義 {len(thick)}"
              f"（{100 * len(thick) / len(allrows) if allrows else 0:.1f}%）")
        print(f"    ★ そのうち 最終 ≤2 : {len(proc)}"
              f"（{100 * len(proc) / len(thick) if thick else 0:.1f}%）")
        le3 = [r for r in thick if r[2] <= 3]
        print(f"    ★ そのうち 最終 ≤3 : {len(le3)}"
              f"（{100 * len(le3) / len(thick) if thick else 0:.1f}%）")


if __name__ == "__main__":
    main()
