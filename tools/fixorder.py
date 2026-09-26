"""名前の順番の直し（2026-09-26 夜、アストラさんの指示。調べの係の報告 sme.py:323・:326・:125-127）。旗 --fix-order（既定オフ）。★ abm/ は変えない。

今の動き（旗オフ、abm/sme.py:105-205）
  写しの候補（述語が同じ行どうしの対）は、引数の数の多い順 → 述語の名前 → 行 ID の順に並ぶ（sme.py:323・:326-327）。
  その順に採っていくとき、親の行の対を採ると、親の引数の子の関係も一緒に写る（relation_pairs、sme.py:133-135）。
  子の番が来ると、子はもう写像に入っているので飛ばされる（sme.py:126-127）。そのため子は「述語一致」と「引数の対応」の点を持たない。
  子が親より先の番なら、子は自分の対として点を持つ。→ 同じ二つのグラフでも、述語の名前の付け方で点が変わる。
直し（旗オン）
  親の中身として一緒に対になった子も、述語が一致していれば（＝子自身の候補の対が、すでに写った相手と同じ対としてある）、
  自分の番で対にしたのと同じ点を数える：その番で、子の候補の対が今の写像と矛盾しなければ（sme.py:330-347 と同じ判定）、
  対として採る（述語一致 1・引数の対応・引数の写像の追加。採った対の並びにも入る）。
  ★ 子の番で矛盾すれば採らない（今と同じく点は無い）。これは、先に採った別の対との実体の食い違いで起こりうる（名前の順に残る違いの元）。
  ★ 体系性・対にならなかった行の罰・伝播・投影の候補の作り方は今のまま（sme.py:140-205 をそのまま写した）。
入れる所：map_graphs を差し替え、読み込み済みのモジュールで map_graphs の名前が元の関数を指していれば、すべて張り替える
  （abm.sme・abm.agent_runtime：土台の選び方 :80 と話す定義の支持 :217、abm.abstraction：同定 :38-52 と m1 の履歴 :125、abm.loop：反実仮想 :410）。
  tools/v31.py・fix2.py・v32.py は呼ぶときに abm.sme.map_graphs を読むので、この差し替えがそのまま効く。
  → 共通構造（土台と今の場面の写しから作る）・話す定義の支持・同定・旗A の「相手の側だけの点」（点(相手,相手) の割り振りは、
    採った対の並びから作るので、この直しで子にも述語一致と引数の対応の点が付く）に、同じ直しが入る。
"""
from __future__ import annotations

import sys

STATS: dict = {}
FIX = True   # ★ 確かめ用：False にすると直しの所を通らない（元と同じ写しになるはず）


def install() -> None:
    import abm.sme as sme

    original = sme.map_graphs
    STATS.clear()
    STATS.update(calls=0, child_accepted=0, child_conflict=0)

    def map_graphs(base_graph, target_graph_partial, params=None, *, prototype=None, prototype_prior_weight=0.0):
        """sme.py:105-205 の写し。★ の所だけが違う。"""
        STATS["calls"] += 1
        weights = params or sme.SMEParams()
        base_relation_ids = sme._relation_ids(base_graph)
        partial_relation_ids = sme._relation_ids(target_graph_partial)
        pairs = sme._alignment_candidates(base_graph, target_graph_partial)
        entity_mapping: dict[str, str] = {}
        used_entities: dict[str, str] = {}
        relation_mapping: dict[str, str] = {}
        used_relations: dict[str, str] = {}
        accepted = []
        accepted_ids: set[str] = set()

        for pair in pairs:
            if pair.base_relation_id in relation_mapping or pair.partial_relation_id in used_relations:
                if not FIX:
                    continue
                # ★ 直し：親の中身として同じ相手に写った子で、まだ対として採っていないもの
                if not (relation_mapping.get(pair.base_relation_id) == pair.partial_relation_id
                        and used_relations.get(pair.partial_relation_id) == pair.base_relation_id
                        and pair.base_relation_id not in accepted_ids):
                    continue
                if not sme._candidate_fits(pair, entity_mapping, used_entities, relation_mapping, used_relations):
                    STATS["child_conflict"] += 1
                    continue
                STATS["child_accepted"] += 1
            elif not sme._candidate_fits(pair, entity_mapping, used_entities, relation_mapping, used_relations):
                continue
            for left, right in pair.entity_pairs:
                entity_mapping[left] = right
                used_entities[right] = left
            for left, right in pair.relation_pairs:
                relation_mapping[left] = right
                used_relations[right] = left
            relation_mapping[pair.base_relation_id] = pair.partial_relation_id
            used_relations[pair.partial_relation_id] = pair.base_relation_id
            accepted.append(pair)
            accepted_ids.add(pair.base_relation_id)

        # ★ ここから下は sme.py:140-205 と同じ
        _bid = {r.relation_id: r for r in base_graph.relations}
        _tid = {r.relation_id: r for r in target_graph_partial.relations}
        changed = True
        while changed:
            changed = False
            for lrel, rrel in sorted(relation_mapping.items()):
                lb, rb = _bid.get(lrel), _tid.get(rrel)
                if lb is None or rb is None or len(lb.arguments) != len(rb.arguments):
                    continue
                for la, ra in zip(lb.arguments, rb.arguments):
                    if la in base_relation_ids or ra in partial_relation_ids:
                        continue
                    if la in entity_mapping or ra in used_entities:
                        continue
                    entity_mapping[la] = ra; used_entities[ra] = la; changed = True

        systematicity = sme._systematicity_score(base_graph, target_graph_partial, relation_mapping)
        matched = len(accepted)
        unmatched = sme._unmatched_count(base_graph, relation_mapping)
        argument_score = sum(len(pair.entity_pairs) + len(pair.relation_pairs) for pair in accepted)
        structural_score = (
            weights.predicate_match_weight * matched
            + weights.argument_consistency_weight * argument_score
            + weights.higher_order_weight * systematicity
            - weights.unmatched_penalty * unmatched
        )
        candidate_projections = sme._projectable_base_relation_ids(
            base_graph, target_graph_partial, entity_mapping, relation_mapping,
            base_relation_ids, partial_relation_ids,
        )
        prior = sme.prototype_prior_score(
            entity_mapping=entity_mapping,
            candidate_projections=candidate_projections,
            prototype=prototype,
            base_graph=base_graph,
            target_graph_partial=target_graph_partial,
            enabled=prototype_prior_weight != 0.0,
        )
        total = structural_score + prototype_prior_weight * prior.total
        alignment = sme.Alignment(
            entity_mapping=entity_mapping,
            relation_mapping=relation_mapping,
            total_score=total,
            score_breakdown={
                "predicate_match": weights.predicate_match_weight * matched,
                "argument_consistency": weights.argument_consistency_weight * argument_score,
                "systematicity": weights.higher_order_weight * systematicity,
                "unmatched_penalty": weights.unmatched_penalty * unmatched,
                "structural_score": structural_score,
                "prototype_prior_score": prior.total,
                "prototype_prior_weight": prototype_prior_weight,
                "prototype_prior_contribution": prototype_prior_weight * prior.total,
                "total_score": total,
            },
            systematicity_contribution=systematicity,
            matched_predicates_count=matched,
            unmatched_count=unmatched,
            candidate_projections=candidate_projections,
            prototype_prior_terms=prior.per_candidate,
        )
        return sme.MappingResult(alignment=alignment, candidates=tuple(accepted))

    n = 0
    for mod in list(sys.modules.values()):
        if mod is not None and getattr(mod, "map_graphs", None) is original:
            setattr(mod, "map_graphs", map_graphs)
            n += 1
    STATS["rebound_modules"] = n
