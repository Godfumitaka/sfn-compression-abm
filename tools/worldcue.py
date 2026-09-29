"""世界 v4（2026-09-29 夜の委任書「手がかりで中身が変わる世界（世界 v4）と、その世界での B＋E」）：旗 --world-cue。
★ abm/ は変えない（abm.world.generate_trial を外側から包む）。旗を切れば何もしない（今の世界と一字一句同じ）。

変更（委任書 1）
  1 手がかり：各場面に、物 a についての手がかりの関係を一本足す（一項の関係 cue_upright(a) 又は cue_lateral(a)）。
    どちらになるかは世界の乱数で、縦（upright）の確率 p（既定 0.8）、横（lateral）1−p。
    ★ 世界の乱数の、ほかと別の流れ（sha256(run_seed ‖ trial ‖ "cue")）から引く。場面のほかの乱数（周縁・糊・伏せ辺）の引き方は変えない。
    この関係は伏せる対象にしない（伏せ辺の候補に入れない）。
  2 中身が変わる席：部分木 T1〜T4 のそれぞれで、一階の関係を一本選び、その述語を手がかりで切り替える。
    ★ 位置は部分木ごとに固定：その T の最初の子の部分木の、最初の一階の関係（T1＝A の hold、T2＝C の break、T3＝E の pull、T4＝G の wrap）。
    縦のときは今の述語、横のときは部分木ごとに一つの新しい述語（hold_lat・break_lat・pull_lat・wrap_lat）。骨組み（関係の ID・引数・高階のつながり）は変えない。
  3 それ以外（型の出方、付随的な関係、伏せ方）は今のまま（伏せ辺は同じ ID が選ばれる。その関係が切り替わる席なら、切り替えた述語のもの）。
  4 研究者の側の記録：台帳の各試行に world_cue（"upright"／"lateral"）と held_out_switch（伏せ辺が中身の変わる席ならその T、そうでなければ null）を足す。
    エージェントには、手がかりの関係が見えるだけ。
固定辞書（v3.9 の費用の固定辞書の語数）：新しい述語六つ（手がかり二つ・横の述語四つ）を種の辞書の後ろに足す（82 語。ceil(log₂) は 7 のまま）。
"""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from random import Random

CUE_UP = "cue_upright"
CUE_LAT = "cue_lateral"
SWITCH_NEW = {"T1": "hold_lat", "T2": "break_lat", "T3": "pull_lat", "T4": "wrap_lat"}
NEW_PREDICATES = (CUE_UP, CUE_LAT) + tuple(SWITCH_NEW[k] for k in ("T1", "T2", "T3", "T4"))
INFO: dict = {}      # G_star.graph_id → {"cue", "switch": {T: relation_id}, "held_out_switch"}
CFG: dict = {}
STATS: dict = {}


def cue_rng(run_seed, trial_index) -> Random:
    return Random(int.from_bytes(sha256(f"{run_seed}\x1f{trial_index}\x1fcue".encode("utf-8")).digest(), "big"))


def cue_trial(original, run_seed, trial_index, agent_ids, *, seed, holdout_include_second_order=False, p_upright=0.8):
    """今の場面（original が返す WorldTrial）に、手がかりと、中身の変わる席の切り替えを入れる。"""
    import abm.world as w
    from abm.domains import Entity, Relation, RelationGraph
    tr = original(run_seed, trial_index, agent_ids, seed=seed, holdout_include_second_order=holdout_include_second_order)
    cue = "upright" if cue_rng(run_seed, trial_index).random() < p_upright else "lateral"
    motif_row = seed.data["motif_structure"][tr.motif]
    switch = {}
    for i, tname in enumerate(motif_row["subtrees"]):
        if tname in SWITCH_NEW:
            switch[tname] = w.opaque_id(run_seed, trial_index, f"relation:tree:{i}.0.0")
    by_switch = {rid: t for t, rid in switch.items()}
    rels = []
    for r in tr.G_star.relations:
        if r.relation_id in by_switch and cue == "lateral":
            r = Relation(r.relation_id, SWITCH_NEW[by_switch[r.relation_id]], r.arguments)
        rels.append(r)
    ents = {e.entity_id for e in tr.G_star.entities}
    a = w.opaque_id(run_seed, trial_index, "entity:a")
    if a not in ents:
        raise ValueError("物 a が場面に無い")
    cue_rel = Relation(w.opaque_id(run_seed, trial_index, "relation:cue"), CUE_UP if cue == "upright" else CUE_LAT, (a,))
    # 役割ユナリーの直後に置く（並びは一意。照合は並びに依らない）
    k = next(i for i, r in enumerate(rels) if r.relation_id == w.opaque_id(run_seed, trial_index, "relation:role_unary")) + 1
    rels.insert(k, cue_rel)
    held_id = tr.held_out_edge.relation_id
    held = next(r for r in rels if r.relation_id == held_id)
    graph = RelationGraph(graph_id=tr.G_star.graph_id, entities=tr.G_star.entities, relations=tuple(rels))
    visible = tuple(r for r in rels if r.relation_id != held_id)
    rid_set = frozenset(r.relation_id for r in visible)
    reach = frozenset(x for r in visible for x in r.arguments if x not in rid_set and x in ents)
    partial = RelationGraph(graph_id=graph.graph_id, entities=tuple(e for e in graph.entities if e.entity_id in reach),
                            relations=visible)
    INFO[graph.graph_id] = {"cue": cue, "switch": switch, "held_out_switch": by_switch.get(held_id)}
    STATS["trials"] = STATS.get("trials", 0) + 1
    STATS[cue] = STATS.get(cue, 0) + 1
    return replace(tr, G_star=graph, target_graph_partial=partial, held_out_edge=held)


def install(p_upright: float = 0.8) -> None:
    """abm.world.generate_trial を包む（generate_world が名前で引くので、そこから効く）。台帳の各試行に研究者用の二欄を足す。"""
    import abm.ledger as ledger
    import abm.loop as loop
    import abm.world as w
    INFO.clear()
    STATS.clear()
    CFG.clear()
    CFG.update(p_upright=float(p_upright))
    original = w.generate_trial

    def generate_trial(run_seed, trial_index, agent_ids, *, seed, holdout_include_second_order=False):
        return cue_trial(original, run_seed, trial_index, agent_ids, seed=seed,
                         holdout_include_second_order=holdout_include_second_order, p_upright=CFG["p_upright"])

    w.generate_trial = generate_trial

    real_record = loop._ledger_record

    def _ledger_record(agent_id, trial, *a, **k):
        rec, snap, h = real_record(agent_id, trial, *a, **k)
        info = INFO.get(trial.G_star.graph_id) or {}
        rec = dict(rec)
        rec["world_cue"] = info.get("cue")
        rec["held_out_switch"] = info.get("held_out_switch")
        return rec, snap, h

    loop._ledger_record = _ledger_record

    real_append = ledger.Ledger.append

    def append(self, record):
        extra = {k: record[k] for k in ("world_cue", "held_out_switch") if k in record}
        base = {k: v for k, v in record.items() if k not in extra}
        if not extra:
            return real_append(self, base)
        keys = frozenset(base)
        expected = frozenset(ledger.LEDGER_FIELDS)
        if keys != expected:
            raise ValueError(f"台帳欄が不一致: missing={sorted(expected - keys)}, extra={sorted(keys - expected)}")
        null_fields = sorted(f for f in ledger.NON_NULL_FIELDS if base[f] is None)
        if null_fields:
            raise ValueError(f"毎試行 non-null 欄が null: {null_fields}")
        self._write_line({"record_type": "trial", **base, **extra})

    ledger.Ledger.append = append


def extend_dictionary() -> None:
    """v3.9 の費用の固定辞書に、新しい述語を後ろから足す（v39.install のあとで呼ぶ）。"""
    import v39
    if not v39.CFG.get("dict_index"):
        return
    idx = dict(v39.CFG["dict_index"])
    for p in NEW_PREDICATES:
        if p not in idx:
            idx[p] = len(idx)
    v39.CFG["dict_index"] = idx
    v39.CFG["D"] = len(idx)
