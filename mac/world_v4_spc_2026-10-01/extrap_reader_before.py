"""外挿の印の解析の読み手（2026-09-30 夕方、委任書「外挿の印」）。★ 台帳・side・記録を読むだけ。模型は変えない。版を問わない。
一本の走行（<腕の走行根>/ledgers/cells/<セル>/seed<種>.jsonl.gz と side）を、試行ごとに次の形で返す：
  t（試行）・row（台帳の行）・pre（予測の直前の状態＝一つ前の試行の終わりの状態。abm/loop.py の _canonical の形の dict）・post（この試行の終わりの状態）
  world（作り直した世界の試行：G_star＝完全な場面・target_graph_partial＝提示・held_out_edge＝伏せた関係・motif）
  disclosed（開示の有無）・side（その試行の side の記録。kind ごとの list）・routing（--dump-routing の記録。kind ごとの list）・answer（--dump-answers の行、答えた試行だけ）
確かめ：状態は台帳の差分を abm/loop.py _apply で当て直し、各試行の sha256 を台帳の agent_state_snapshot_hash と比べる（合わなければ止める）。
  世界は台帳の見出しから abm/world.py generate_world で作り直し、世界の指紋と、試行ごとの提示・伏せた関係・場面の ID を台帳と比べる（合わなければ止める）。
使い方（コードの作業場所 W を sys.path の先頭に置いてから）：
  from extrap_reader import iter_run
  for tr in iter_run(arm_root, cell, seed): ...
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import os
from collections import defaultdict


def _side_by_trial(path):
    out = defaultdict(lambda: defaultdict(list))
    if path and os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            d = json.loads(line)
            t = d.get("trial")
            if t is not None:
                out[t][d.get("kind")].append(d)
    return out


def _answers_by_trial(path):
    out = {}
    if path and os.path.exists(path):
        with open(path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                out[int(r["trial"])] = r
    return out


def iter_run(arm_root, cell, seed, *, check_hash=True, check_world=True):
    from abm.loop import _apply, _json_bytes
    from abm.seed import load_seed
    from abm.world import generate_world
    root = arm_root
    fl = json.load(open(os.path.join(root, "flag.json"), encoding="utf-8"))
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__import__("abm").__file__)))
    cfg = json.load(open(os.path.join(repo, fl["config"]), encoding="utf-8"))
    seedf = os.path.join(repo, cfg.get("seed_file", "seeds/U-011_seed_v3a2.json"))
    sd = f"seed{int(seed):03d}"
    led = os.path.join(root, "ledgers", "cells", cell, f"{sd}.jsonl.gz")
    side = _side_by_trial(os.path.join(root, "side", cell, f"{sd}.jsonl"))
    routing = _side_by_trial(os.path.join(root, "side", cell, f"{sd}.routing.jsonl"))
    answers = _answers_by_trial(os.path.join(root, "side", cell, f"{sd}.answers.csv"))
    with gzip.open(led, "rt", encoding="utf-8") as f:
        header = json.loads(next(f))
        world = generate_world(header["run_seed"], header["trial_count"], ["agent"], seed=load_seed(seedf),
                               holdout_include_second_order=bool(header.get("arm_holdout_second_order") or False))
        if check_world and world.world_hash != header["world_hash"]:
            raise RuntimeError(f"世界の指紋が合わない {led}")
        state = None
        for line, wt in zip(f, world.trials):
            row = json.loads(line)
            if row.get("record_type", "trial") != "trial":
                continue
            t = row["prediction_order"]
            if check_world and ([r.relation_id for r in wt.target_graph_partial.relations] != row["observable_mask_edges"]
                                or wt.held_out_edge.to_dict() != row["held_out_content"] or wt.G_star.graph_id != row["instance_id"]):
                raise RuntimeError(f"試行 {t} の場面が台帳と合わない {led}")
            pre = state
            ss = row["state_snapshot"]
            if ss["kind"] == "full":
                state = ss["value"]
            elif ss["kind"] == "delta":
                state = _apply(state, ss["changes"])
            else:
                raise RuntimeError(f"試行 {t} の状態の控えが {ss['kind']}（当て直せない） {led}")
            if check_hash and hashlib.sha256(_json_bytes(state)).hexdigest() != row["agent_state_snapshot_hash"]:
                raise RuntimeError(f"試行 {t} の状態の sha256 が台帳と合わない {led}")
            yield {"t": t, "row": row, "pre": pre, "post": state, "world": wt, "disclosed": bool(row.get("f_fired")),
                   "side": side.get(t, {}), "routing": routing.get(t, {}), "answer": answers.get(t), "header": header}
