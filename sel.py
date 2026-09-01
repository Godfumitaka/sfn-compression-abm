#!/usr/bin/env python3
"""
sel.py — Sel（選択性）を電池と照らして計算する

★ このスクリプトを走らせることは「Sel を採る」ことを意味しない（T-041 は保留のまま）。
  走行後に Sel を使う選択を残すための計算である（規範13）。

出所
  依頼K返答_fable（2026-08-21）§2   Sel の定義と はしご
  依頼L返答_Fable（2026-08-28）§4-2 層の壊し方
  統合決定台帳 T-041                  Sel・電池・収量は保留。★ 採否は未判断
  build_battery.py の PREREGISTERED   走行前に固定した規約

Sel の定義
  Sel(R) = log2 [ P(照合成立 | 実場面) / P(照合成立 | 周辺保存シャッフル) ]  （ビット）

  ★ 符号つきで読む（sel_sign = "signed"）。絶対値にしない。
    負は「世界より狭く共起している」という別の現象であり、絶対値にすると潰れる。

はしご
  L0  実生成（λ=1）
  L1  共起を壊す（述語を大域プールから引き直す）
  L2  引数共有を壊す（共起は保つ）
  L3  役割ユナリーとの対応だけ壊す（共起も引数共有も保つ）

  → Sel は L0 対 各層 の三本になる。どれを分母に採るかは ★ 未判断

★ 費用について
  全 2,560 走行 × def 60〜70 本 × 場面 3,000 × 4 層 は現実的でない。
  既定では格子点ごとに --seeds 本だけ拾う（代表セル）。
  --measure で 1 def あたりの費用を実測してから広げること。

使い方
  python3 sel.py --runs runs/main_2026-08-31 --battery battery_v1.json --measure
  python3 sel.py --runs runs/main_2026-08-31 --battery battery_v1.json \
                 --out analysis --seeds 2 --scenes 400
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from abm.domains import Entity, Relation, RelationGraph
from abm.sme import map_graphs

LAYERS = ("L0_real", "L1_cooccurrence", "L2_argument_sharing", "L3_role_correspondence")


# ══════════════════════════════════════════════════════════════
def load_battery(path: Path):
    payload = json.loads(Path(path).read_bytes())
    scenes = {}
    for name in LAYERS:
        scenes[name] = [
            RelationGraph(
                graph_id=g["graph_id"],
                entities=tuple(Entity(entity_id=e) for e in g["entities"]),
                relations=tuple(
                    Relation(r["relation_id"], r["predicate"], tuple(r["arguments"]))
                    for r in g["relations"]
                ),
            )
            for g in payload["layers"][name]
        ]
    return payload, scenes


def definition_graph(registration):
    """登録イベントから def(R) のグラフを組む。★ 墓石（alive=False）は入れない。"""
    relations = tuple(
        Relation(
            "def:%s:%s:%s" % (registration["R"], c["slot_index"], c["registered_at"]),
            c["predicate"], tuple(c["arguments"]),
        )
        for c in (registration.get("constituents") or ()) if c.get("alive")
    )
    if len(relations) < 2:
        return None
    ids = {r.relation_id for r in relations}
    entities = tuple(
        Entity(entity_id=a) for a in
        sorted({a for r in relations for a in r.arguments if a not in ids})
    )
    return RelationGraph("def:%s" % registration["R"], entities, relations)


def match_rate(graph, scenes, tau_acc):
    """照合成立率。★ 事前登録の主基準は「写像の成立（tau_acc を通ること）」。"""
    if graph is None or not scenes:
        return None
    total = len(graph.relations)
    hits = 0
    for scene in scenes:
        alignment = map_graphs(graph, scene).alignment
        if len(alignment.relation_mapping) / total >= tau_acc:
            hits += 1
    return hits / len(scenes)


def sel_bits(p1, p0, floor):
    """log2(p1/p0)。★ 符号つき。p0 = 0 は床で置き換え、床を使ったことを記録する。"""
    if p1 is None or p0 is None:
        return None, False
    if p1 <= 0.0:
        return None, False
    used_floor = p0 <= 0.0
    return math.log2(p1 / (floor if used_floor else p0)), used_floor


# ══════════════════════════════════════════════════════════════
def read_ledger(path: Path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle if line.strip()]
    return (rows[0], rows[1:]) if rows else (None, [])


def pick_runs(root: Path, per_cell: int):
    """格子点ごとに先頭 per_cell 本だけ拾う（代表セル）。"""
    by_cell = defaultdict(list)
    for path in sorted((root / "cells").rglob("seed*")):
        if path.suffix in (".gz", ".jsonl"):
            by_cell[path.parent.name].append(path)
    return [p for paths in by_cell.values() for p in paths[:per_cell]]


def analyse_run(path, scenes, tau_acc, floor):
    header, trials = read_ledger(path)
    if header is None or not trials:
        return []
    registrations, used = {}, Counter()
    for row in trials:
        for event in row.get("reg_del_events") or ():
            if event.get("kind") == "registration":
                registrations[event["R"]] = event
        if row.get("R_used"):
            used[row["R_used"]] += 1

    rows = []
    for name, registration in registrations.items():
        graph = definition_graph(registration)
        if graph is None:
            continue
        rates = {layer: match_rate(graph, scenes[layer], tau_acc) for layer in LAYERS}
        record = {
            "cell": path.parent.name, "seed": header.get("run_seed"),
            "f": header.get("f_setting"), "theta_prime": header.get("theta_prime"),
            "repair_scope": header.get("arm_repair_scope"),
            "R": name, "adoptions": used.get(name, 0),
            "m_live": sum(1 for c in registration["constituents"] if c.get("alive")),
            "p1": rates["L0_real"],
        }
        for layer in LAYERS[1:]:
            record["p0_" + layer] = rates[layer]
            bits, floored = sel_bits(rates["L0_real"], rates[layer], floor)
            record["Sel_" + layer] = bits
            record["floored_" + layer] = floored
        rows.append(record)
    return rows


# ══════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", required=True)
    parser.add_argument("--battery", required=True)
    parser.add_argument("--out", default="analysis")
    parser.add_argument("--seeds", type=int, default=2,
                        help="格子点ごとに拾う走行の本数（既定 2）")
    parser.add_argument("--scenes", type=int, default=400,
                        help="各層から使う場面数（既定 400。電池は 3,000 ある）")
    parser.add_argument("--measure", action="store_true",
                        help="★ 1 def あたりの費用を実測して終わる")
    args = parser.parse_args()

    payload, scenes = load_battery(Path(args.battery))
    prereg = payload["preregistered"]
    tau_acc = float(prereg["tau_acc"])
    if args.scenes:
        scenes = {k: v[:args.scenes] for k, v in scenes.items()}
    floor = 0.5 / max(len(scenes["L0_real"]), 1)          # p0 = 0 のときの床

    print("電池      %s（版 %s ／ 場面 %d 本中 %d 本を使用）"
          % (args.battery, payload["version"], payload["n_scenes"], len(scenes["L0_real"])))
    print("規約      tau_acc=%s ／ 基準=%s ／ 符号=%s"
          % (tau_acc, prereg["match_criterion"], prereg["sel_sign"]))
    print("★ p0=0 の床  %.5f（= 0.5/場面数）" % floor)

    root = Path(args.runs)
    files = pick_runs(root, args.seeds)
    if not files:
        raise SystemExit("★ 台帳が見つかりません: %s" % (root / "cells"))

    if args.measure:
        print("\n★ 費用の実測（1 走行だけ回します）")
        start = time.time()
        rows = analyse_run(files[0], scenes, tau_acc, floor)
        elapsed = time.time() - start
        if not rows:
            raise SystemExit("★ def が取れませんでした")
        print("  %s  def %d 本  %.1f 秒 → 1 def あたり %.2f 秒"
              % (files[0].parent.name, len(rows), elapsed, elapsed / len(rows)))
        print("  ★ 代表セル %d 本（格子点ごとに %d 本）なら %.1f 分"
              % (len(files), args.seeds, elapsed * len(files) / 60))
        print("  ★ 全 2,560 走行なら %.1f 時間"
              % (elapsed * 2560 / 3600))
        print("\n  → 費用を見てから --seeds と --scenes を決めてください")
        return

    print("\n代表セル %d 本を読みます（格子点ごとに %d 本）\n" % (len(files), args.seeds))
    rows = []
    start = time.time()
    for index, path in enumerate(files, 1):
        try:
            rows.extend(analyse_run(path, scenes, tau_acc, floor))
        except Exception as exc:
            print("  ★ 失敗 %s: %r" % (path, exc))
        if index % 10 == 0 or index == len(files):
            print("  %d/%d  （%.1f 分経過）" % (index, len(files), (time.time() - start) / 60),
                  flush=True)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "sel.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")

    print("\n" + "=" * 100)
    print("★ Sel（選択性）  log2(p1/p0)。符号つき。★ T-041 は保留のまま")
    print("=" * 100)
    print("\n%-28s%10s%10s%10s%10s%12s"
          % ("分母の層", "中央", "平均", "最小", "最大", "床を使った"))
    for layer in LAYERS[1:]:
        values = [r["Sel_" + layer] for r in rows if r.get("Sel_" + layer) is not None]
        floored = sum(1 for r in rows if r.get("floored_" + layer))
        if not values:
            continue
        print("%-28s%10.3f%10.3f%10.3f%10.3f%12d"
              % (layer, statistics.median(values), statistics.fmean(values),
                 min(values), max(values), floored))

    print("\n★ 照合成立率（p1 と p0）")
    print("%-28s%12s" % ("層", "成立率の平均"))
    p1 = [r["p1"] for r in rows if r.get("p1") is not None]
    if p1:
        print("%-28s%12.4f" % ("L0_real（p1）", statistics.fmean(p1)))
    for layer in LAYERS[1:]:
        values = [r["p0_" + layer] for r in rows if r.get("p0_" + layer) is not None]
        if values:
            print("%-28s%12.4f" % (layer + "（p0）", statistics.fmean(values)))

    print("""
★ 読み方
  Sel が大きい      その def は実世界の構造に選択的に反応している
  Sel が 0 に近い   周辺分布だけで説明がつく（構造を見ていない）
  ★ Sel が負       世界より狭く共起している。★ 絶対値にしない（事前登録の規約）
  床を使った件数    p0 = 0 だった def。★ 多いなら場面数か層の設計を疑う

★ どの層を分母に採るかは未判断
  L1 共起まで壊す ／ L2 引数共有まで ／ L3 役割対応だけ
  → 三本とも出してあるので、走行後に選べる
""")
    print("出力  %s（def %d 行）" % (out / "sel.jsonl", len(rows)))


if __name__ == "__main__":
    main()
