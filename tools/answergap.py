"""欠けた位置にだけ答える（2026-09-30 夜の委任書「欠けた位置にだけ答える」旗の実装）：旗 --answer-gap。
★ 話す答えを選ぶ所（tools/v39.py fill_decision）だけを包む。学習・採点・忘却・E・門・定義の選び方は変えない。旗を切れば何もしない。

用語
  欠けた位置の集合 D：本人の見た場面（提示の関係）の関係の引数に現れる ID のうち、提示の関係の ID でも場面の物の ID でもないもの。
    予測のたびに提示の場面だけから作る（研究者の伏せ辺は使わない）。何本あってもよい。
  対応先：tools/v310be.py role_target（席の親が対応した場面の関係の、同じ位置の子の ID）。照合は予測に使った定義の照合（definition_alignment）。
  適格な候補：対応先が D のどれかである候補（投影・穴埋めの候補のどちらも）。
決まり（委任書の「決めてある細部」1〜7）
  ・投影も穴埋めの候補も、対応先が D に入るものだけを残す。残った候補に今の決まり（fill_decision：投影を優先、次に穴埋めの候補を
    今の並びの順で、--amb-local の扱いも今のまま）をそのまま当てる。先に絞ってから選ぶ。
  ・投影が適格でなければ投影を捨て、適格な穴埋めの候補に進む。
  ・適格な候補が一つも無ければ棄権し、理由を no_gap_candidate にする（下の「未決」を参照）。
  ・U 常時棄権は、今の U の扱い（fill_v39 の中で U の席を埋めない）が先に効き、そのあとに絞る。
未決（control/ に書いた、アストラさんの決定待ち）：絞る前から候補が一本も無かった試行（例：投影なし・穴埋めの候補 0 本）の棄権の理由。
  この版では、絞って候補が減り、かつ適格な候補が一つも残らなかったときだけ no_gap_candidate にし、それ以外は今の決まりの理由のまま
  （GAP_REASON_RULE＝"removed"）。棄権の課金は設定で切られており（config の abstain_charge＝false、abm/loop.py:312-317）、
  理由の名前は状態に効かない。
"""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

GAP_REASON_RULE = "removed"
STATS: dict = {}
CTX: dict = {}


def gap_ids(scene) -> frozenset:
    """欠けた位置の集合 D（提示の場面だけから）。"""
    rel_ids = {r.relation_id for r in scene.relations}
    ent_ids = {e.entity_id for e in scene.entities}
    return frozenset(a for r in scene.relations for a in r.arguments if a not in rel_ids and a not in ent_ids)


def _bump(k, n=1):
    STATS[k] = STATS.get(k, 0) + n


def install() -> None:
    import v39
    import v310be
    from abm.domains import Abstain, EdgePrediction
    STATS.clear()
    CTX.clear()

    real_fill = v39.fill_v39

    def fill_v39(definition, target, entity_mapping, relation_mapping, *a, **k):
        # 予測で使った定義・場面・照合（definition_alignment の関係の写し）を控える（fill_decision の直前に呼ばれる、tools/v39.py:618-629）
        CTX.update(d=definition, scene=target, rm=relation_mapping)
        return real_fill(definition, target, entity_mapping, relation_mapping, *a, **k)

    v39.fill_v39 = fill_v39

    real_decision = v39.fill_decision

    def fill_decision(prediction, filling, prediction_path):
        d, scene, rm = CTX.get("d"), CTX.get("scene"), CTX.get("rm")
        CTX.clear()
        if d is None:
            return real_decision(prediction, filling, prediction_path)
        D = gap_ids(scene)
        al = SimpleNamespace(relation_mapping=rm)     # role_target が読むのは relation_mapping だけ（tools/v310be.py:78-97）
        rows = {row.slot_index: row for row in d.constituents}
        by_id = {row.relation.relation_id: row for row in d.constituents}

        def ok(row):
            return row is not None and v310be.role_target(d, row, al, scene)[0] in D

        _bump("decisions")
        _bump(f"D_size_{min(len(D), 3)}")
        removed = 0
        pred = prediction
        if isinstance(prediction, EdgePrediction):
            rid = prediction.edge.relation_id
            base = rid[len("sme_projection__"):] if rid.startswith("sme_projection__") else None
            if not ok(by_id.get(base)):
                pred = Abstain(reason="no_gap_projection")    # fill_decision は種類（Abstain か）しか見ない。理由は下で決まる
                removed += 1
                _bump("proj_dropped")
        keep = [k for k, s in enumerate(filling.slot_indices) if ok(rows.get(s))]
        removed += len(filling.relations) - len(keep)
        _bump("fill_dropped", len(filling.relations) - len(keep))
        pick = lambda xs: tuple(xs[k] for k in keep) if len(xs) == len(filling.relations) else xs  # noqa: E731
        filtered = replace(filling, relations=pick(filling.relations), slot_indices=pick(filling.slot_indices),
                           alive_by_slot=pick(filling.alive_by_slot), source_by_slot=pick(filling.source_by_slot))
        out, path = real_decision(pred, filtered, prediction_path)
        eligible = isinstance(pred, EdgePrediction) or bool(filtered.relations)
        if isinstance(out, Abstain) and not eligible and (removed > 0 or GAP_REASON_RULE == "all"):
            out = Abstain(reason="no_gap_candidate")
            path = None
            _bump("no_gap_candidate")
        if isinstance(out, EdgePrediction):
            _bump("spoke")
        return out, path

    v39.fill_decision = fill_decision
