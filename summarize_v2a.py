#!/usr/bin/env python3
"""v2a 本走行の集計 — 中心的過程と主要指標を腕ごとに出す。

使い方
    python3.14 summarize_v2a.py

前提
    runs/v2a_{t067,t200}_{w00,w10}_2026-09-07/cells/*/seed*.jsonl(.gz)
    ★ analyze_rev6.py の出力は使わない（台帳から直接読む）
"""
from __future__ import annotations

import collections
import glob
import gzip
import json
import os
import statistics as st
import sys

ARMS = ["t067_w00", "t067_w10", "t200_w00", "t200_w10"]
LABEL = {
    "t067_w00": "比読み τ=0.67  w=0.0",
    "t067_w10": "比読み τ=0.67  w=1.0",
    "t200_w00": "絶対 k=1      w=0.0",
    "t200_w10": "絶対 k=1      w=1.0",
}


def load_seed_layers() -> dict[str, str]:
    """述語 → 次数 の対応表を種から作る。"""
    with open("U-011 seed v2a.json", encoding="utf-8") as fh:
        seed = json.load(fh)
    layer: dict[str, str] = {}
    for motif, row in seed["motif_structure"].items():
        layer[row["third"]] = "三階"
        layer[row["peripheral"]] = "周縁"
        layer[seed["role_unary"][motif]] = "役割"
        for name in row["subtrees"]:
            sub = seed["subtrees"][name]
            layer[sub["higher"]] = "二階"
            for first in sub["first_order"]:
                layer[first] = "一階"
    return layer


def read_run(path: str):
    """一走行の台帳を読み、必要な集計だけ返す。"""
    opener = gzip.open if path.endswith(".gz") else open
    header = None
    # 定義ごとの m_live 軌跡（変化点のみ）
    traj: dict[str, list[int]] = collections.defaultdict(list)
    alive_last: dict[tuple[str, int, int], tuple[str, bool]] = {}
    alive_now: dict[tuple, bool] = {}
    pred_of: dict[tuple, str] = {}
    n_trials = 0
    hits = misses = pending = spoke = 0
    fills = 0
    tie = 0

    with opener(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            if not isinstance(rec, dict):
                continue
            if rec.get("record_type") == "run_header":
                header = rec
                continue
            n_trials += 1
            cat = rec.get("outcome_category")
            if cat in ("的中", "hit"):
                hits += 1
            elif cat in ("失敗", "miss"):
                misses += 1
            elif cat in ("保留", "pending"):
                pending += 1
            if rec.get("predicted_edge") is not None:
                spoke += 1
            filled = rec.get("filled_predicate") or []
            fills += len(filled) if isinstance(filled, list) else 0
            tie += int(rec.get("n_tie_candidates") or 0)

            # ★ constituent_states から m_live の軌跡を作る
            # （reg_del_events は登録時の値しか持たない）
            live = collections.Counter()
            for state in rec.get("constituent_states") or []:
                if state.get("alive"):
                    live[state["R"]] += 1
                key = (state["R"], state["slot_index"], state["registered_at"])
                alive_now[key] = bool(state.get("alive"))

            # 述語は登録イベントの constituents にある
            for ev in rec.get("reg_del_events") or []:
                if ev.get("kind") != "registration":
                    continue
                for i, con in enumerate(ev.get("constituents") or []):
                    pred = (con.get("relation") or {}).get("predicate") \
                        or con.get("predicate")
                    if pred:
                        pred_of[(ev["R"], con.get("slot_index", i))] = pred
            for name, count in live.items():
                seq = traj[name]
                if not seq or seq[-1] != count:
                    seq.append(count)

    alive_by_layer: collections.Counter = collections.Counter()
    dead_by_layer: collections.Counter = collections.Counter()
    for (name, slot, _reg), is_alive in alive_now.items():
        pred = pred_of.get((name, slot))
        if not pred:
            continue
        layer_name = LAYERS.get(pred, "他")
        (alive_by_layer if is_alive else dead_by_layer)[layer_name] += 1

    return {
        "header": header,
        "traj": traj,
        "n_trials": n_trials,
        "hits": hits,
        "misses": misses,
        "pending": pending,
        "spoke": spoke,
        "fills": fills,
        "tie": tie,
        "alive": alive_by_layer,
        "dead": dead_by_layer,
    }


LAYERS = load_seed_layers()


def main() -> None:
    print("=" * 78)
    print("v2a 本走行の集計 — 2026-09-08")
    print("=" * 78)

    for arm in ARMS:
        base = f"runs/v2a_{arm}_2026-09-07"
        if not os.path.isdir(base):
            print(f"\n{LABEL[arm]}  ★ ディレクトリが無い: {base}")
            continue

        by_cell: dict[str, list[dict]] = collections.defaultdict(list)
        for path in sorted(glob.glob(f"{base}/cells/*/seed*.jsonl*")):
            cell = os.path.basename(os.path.dirname(path))
            by_cell[cell].append(read_run(path))

        print(f"\n{'─' * 78}")
        print(f"■ {LABEL[arm]}")
        print(f"{'─' * 78}")
        print(
            f"{'セル':<44}{'走行':>4}{'被覆':>8}{'的中率':>8}"
            f"{'的中数':>7}{'★厚→薄':>8}{'定義':>6}"
        )

        arm_proc = arm_defs = 0
        for cell in sorted(by_cell):
            runs = by_cell[cell]
            cov = st.mean(r["spoke"] / r["n_trials"] for r in runs)
            acc = st.mean(
                (r["hits"] / r["spoke"]) if r["spoke"] else 0.0 for r in runs
            )
            hits = st.mean(r["hits"] for r in runs)
            proc = defs = 0
            for r in runs:
                for seq in r["traj"].values():
                    if not seq:
                        continue
                    defs += 1
                    if max(seq) >= 6 and seq[-1] <= 2:
                        proc += 1
            arm_proc += proc
            arm_defs += defs
            print(
                f"{cell:<44}{len(runs):>4}{cov:>8.3f}{acc:>8.3f}"
                f"{hits:>7.1f}{proc:>8}{defs:>6}"
            )

        alive = collections.Counter()
        dead = collections.Counter()
        for runs in by_cell.values():
            for r in runs:
                alive.update(r["alive"])
                dead.update(r["dead"])
        parts = []
        for layer_name in ("一階", "二階", "三階"):
            a, d = alive[layer_name], dead[layer_name]
            if a + d:
                parts.append(f"{layer_name} {a / (a + d):.3f}")
        if parts:
            print(f"{'':<44}次数別の生存率  " + " ／ ".join(parts))

        rate = 100 * arm_proc / arm_defs if arm_defs else 0.0
        print(f"{'★ 腕の合計':<44}{'':>4}{'':>8}{'':>8}{'':>7}{arm_proc:>8}{arm_defs:>6}")
        print(f"{'':<44}★ 厚→薄の発生率 {rate:.2f}%")


if __name__ == "__main__":
    main()
