"""世界 v4（型の変種、2026-09-30 深夜の追記 B-2）：旗 --world-cue。
★ abm/ は変えない（abm.world.generate_trial を外側から包む）。旗を切れば何もしない（今の世界と一字一句同じ）。
（2026-09-29 夜の v4w-main の --world-cue ＝手がかりの関係を足す版とは別物。ここでは手がかりの関係は足さない）

変更（追記 B-2）
  1 場面ごとに「型の変種」を一つ決める：変種 A（確率 p、既定 0.8）又は変種 B（1−p）。
    ★ 世界の乱数の、ほかと別の流れ（sha256(run_seed ‖ trial ‖ "variant")）から引く。場面のほかの乱数（周縁・糊・伏せ辺）の引き方は変えない。
  2 型の二つの部分木のそれぞれで、最初の一階の葉の関係（部分木 i の経路 i.0.0：T1＝hold、T2＝break、T3＝pull、T4＝wrap）の述語を、
    変種 A なら今の述語のまま、変種 B なら部分木ごとの新しい述語（hold_b・break_b・pull_b・wrap_b）にする。二つの部分木で同時に切り替わる。
    骨組み（関係の ID・引数・高階のつながり）は変えない。
  3 それ以外（型の出方、付随的な関係、伏せ方）は今のまま。伏せ辺は同じ ID が選ばれる。その関係が切り替わる関係なら、切り替えた述語のもの。
  4 研究者の側の記録：台帳の各試行に world_variant（"A"／"B"）と held_out_switch（伏せ辺が切り替わる関係ならその部分木の名 T1〜T4、
    そうでなければ null）を足す。エージェントには何も足さない（場面の述語が変わるだけ）。
固定辞書（v3.9 の費用の固定辞書の語数）：新しい述語四つを種の辞書の後ろに足す（extend_dictionary、v39.install のあとで呼ぶ）。
"""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from random import Random

SWITCH_NEW = {"T1": "hold_b", "T2": "break_b", "T3": "pull_b", "T4": "wrap_b"}
NEW_PREDICATES = tuple(SWITCH_NEW[k] for k in ("T1", "T2", "T3", "T4"))
INFO: dict = {}      # G_star.graph_id → {"variant", "switch": {T: relation_id}, "held_out_switch"}
CFG: dict = {}
STATS: dict = {}


def variant_rng(run_seed, trial_index) -> Random:
    return Random(int.from_bytes(sha256(f"{run_seed}\x1f{trial_index}\x1fvariant".encode("utf-8")).digest(), "big"))


def variant_trial(original, run_seed, trial_index, agent_ids, *, seed, holdout_include_second_order=False, p_a=0.8):
    """今の場面（original が返す WorldTrial）の、二つの部分木の最初の一階の葉を、場面の変種で切り替える。"""
    import abm.world as w
    from abm.domains import Relation, RelationGraph
    tr = original(run_seed, trial_index, agent_ids, seed=seed, holdout_include_second_order=holdout_include_second_order)
    variant = "A" if variant_rng(run_seed, trial_index).random() < p_a else "B"
    motif_row = seed.data["motif_structure"][tr.motif]
    switch = {}
    for i, tname in enumerate(motif_row["subtrees"]):
        if tname not in SWITCH_NEW:
            raise ValueError(f"切り替えの述語が決まっていない部分木 {tname}")
        switch[tname] = w.opaque_id(run_seed, trial_index, f"relation:tree:{i}.0.0")
    by_switch = {rid: t for t, rid in switch.items()}
    ids = {r.relation_id for r in tr.G_star.relations}
    if not set(by_switch) <= ids:
        raise ValueError("切り替える関係が場面に無い")
    if variant == "A":
        rels = list(tr.G_star.relations)
    else:
        rels = [Relation(r.relation_id, SWITCH_NEW[by_switch[r.relation_id]], r.arguments) if r.relation_id in by_switch else r
                for r in tr.G_star.relations]
    held_id = tr.held_out_edge.relation_id
    held = next(r for r in rels if r.relation_id == held_id)
    graph = RelationGraph(graph_id=tr.G_star.graph_id, entities=tr.G_star.entities, relations=tuple(rels))
    visible = tuple(r for r in rels if r.relation_id != held_id)
    if tuple(r.relation_id for r in visible) != tuple(r.relation_id for r in tr.target_graph_partial.relations):
        raise ValueError("見えている関係の並びが今の世界と違う")
    partial = RelationGraph(graph_id=tr.target_graph_partial.graph_id, entities=tr.target_graph_partial.entities, relations=visible)
    INFO[graph.graph_id] = {"variant": variant, "switch": switch, "held_out_switch": by_switch.get(held_id)}
    STATS["trials"] = STATS.get("trials", 0) + 1
    STATS[variant] = STATS.get(variant, 0) + 1
    STATS["held_out_switch"] = STATS.get("held_out_switch", 0) + (held_id in by_switch)
    return replace(tr, G_star=graph, target_graph_partial=partial, held_out_edge=held)


def install(p_a: float = 0.8) -> None:
    """abm.world.generate_trial を包む（generate_world が名前で引くので、そこから効く）。台帳の各試行に研究者用の二欄を足す。"""
    import abm.ledger as ledger
    import abm.loop as loop
    import abm.world as w
    INFO.clear()
    STATS.clear()
    CFG.clear()
    CFG.update(p_a=float(p_a))
    original = w.generate_trial

    def generate_trial(run_seed, trial_index, agent_ids, *, seed, holdout_include_second_order=False):
        return variant_trial(original, run_seed, trial_index, agent_ids, seed=seed,
                             holdout_include_second_order=holdout_include_second_order, p_a=CFG["p_a"])

    w.generate_trial = generate_trial

    real_record = loop._ledger_record

    def _ledger_record(agent_id, trial, *a, **k):
        rec, snap, h = real_record(agent_id, trial, *a, **k)
        info = INFO.get(trial.G_star.graph_id) or {}
        rec = dict(rec)
        rec["world_variant"] = info.get("variant")
        rec["held_out_switch"] = info.get("held_out_switch")
        return rec, snap, h

    loop._ledger_record = _ledger_record

    real_append = ledger.Ledger.append

    def append(self, record):
        extra = {k: record[k] for k in ("world_variant", "held_out_switch") if k in record}
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
