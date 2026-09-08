#!/usr/bin/env python3
"""中心的過程（厚→薄）の 14 本を、一本ずつ実体として確認する。

使い方
    python3.14 verify_process.py > verify_process.txt 2>&1
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


def layers() -> dict[str, str]:
    with open("U-011 seed v2a.json", encoding="utf-8") as fh:
        seed = json.load(fh)
    out: dict[str, str] = {}
    for motif, row in seed["motif_structure"].items():
        out[row["third"]] = "三階"
        out[row["peripheral"]] = "周縁"
        out[seed["role_unary"][motif]] = "役割"
        for name in row["subtrees"]:
            sub = seed["subtrees"][name]
            out[sub["higher"]] = "二階"
            for first in sub["first_order"]:
                out[first] = "一階"
    return out


LAYERS = layers()


def scan(path: str):
    """一走行から、定義ごとの m_live 軌跡と述語構成を拾う。"""
    opener = gzip.open if path.endswith(".gz") else open
    traj: dict[str, list[tuple[int, int]]] = collections.defaultdict(list)
    pred_of: dict[tuple[str, int], str] = {}
    dead_at: dict[str, list[tuple[int, str]]] = collections.defaultdict(list)
    prev_alive: dict[tuple[str, int, int], bool] = {}
    trial = 0

    with opener(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            if not isinstance(rec, dict) or rec.get("record_type") != "trial":
                continue
            trial = rec.get("trial", trial + 1)

            for ev in rec.get("reg_del_events") or []:
                if ev.get("kind") != "registration":
                    continue
                for i, con in enumerate(ev.get("constituents") or []):
                    pred = (con.get("relation") or {}).get("predicate") \
                        or con.get("predicate")
                    if pred:
                        pred_of[(ev["R"], con.get("slot_index", i))] = pred

            live = collections.Counter()
            for state in rec.get("constituent_states") or []:
                key = (state["R"], state["slot_index"], state["registered_at"])
                now = bool(state.get("alive"))
                if prev_alive.get(key, True) and not now:
                    pred = pred_of.get((state["R"], state["slot_index"]), "?")
                    dead_at[state["R"]].append((trial, pred))
                prev_alive[key] = now
                if now:
                    live[state["R"]] += 1
            for name, count in live.items():
                seq = traj[name]
                if not seq or seq[-1][1] != count:
                    seq.append((trial, count))
    return traj, dead_at, pred_of


def main() -> None:
    print("=" * 78)
    print("中心的過程（生存最大 ≥6 かつ 最終 ≤2）の実体確認")
    print("=" * 78)

    total = 0
    for arm in ARMS:
        base = f"runs/v2a_{arm}_2026-09-08"
        if not os.path.isdir(base):
            continue
        found = []
        for path in sorted(glob.glob(f"{base}/cells/*/seed*.jsonl*")):
            traj, dead_at, pred_of = scan(path)
            for name, seq in traj.items():
                if not seq:
                    continue
                counts = [c for _t, c in seq]
                if max(counts) >= 6 and counts[-1] <= 2:
                    found.append((path, name, seq, dead_at.get(name, []),
                                  pred_of))
        if not found:
            print(f"\n■ {LABEL[arm]}   ★ 該当なし")
            continue

        print(f"\n■ {LABEL[arm]}   ★ {len(found)} 本")
        for path, name, seq, deaths, pred_of in found:
            total += 1
            cell = os.path.basename(os.path.dirname(path))
            seed = os.path.basename(path).split(".")[0]
            counts = [c for _t, c in seq]
            print(f"\n  [{total}] {cell} / {seed}")
            print(f"      定義 {name[:22]}")
            print(f"      ★ 軌跡  {' → '.join(f'{c}(t{t})' for t, c in seq)}")
            print(f"      誕生 {counts[0]}  最大 {max(counts)}  最終 {counts[-1]}"
                  f"  変化 {len(seq)} 回")
            if deaths:
                by_layer = collections.Counter(
                    LAYERS.get(p, "他") for _t, p in deaths
                )
                order = " ／ ".join(
                    f"t{t}:{p}({LAYERS.get(p, '他')})" for t, p in deaths[:8]
                )
                print(f"      ★ 死んだ構成素 {dict(by_layer)}")
                print(f"      順序  {order}")

    print(f"\n{'=' * 78}")
    print(f"★ 合計 {total} 本")


if __name__ == "__main__":
    main()
