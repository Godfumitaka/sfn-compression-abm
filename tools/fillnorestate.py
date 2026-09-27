"""v3.5 の穴埋めの直し（2026-09-27、control/判断_0927_1250.md の 1、案 B）。旗 --fill-norestate（既定オフ）。★ abm/ は変えない。
v3.4 の --fill-unseen（tools/fillunseen.py）とは別の旗。二つを一緒には使わない（tools/v3_run.py で止める）。

今の動き（旗オフ、abm/filling.py:168-255 の fill）
  席（墓石の席・空いた席）について、メモ帳（slot_history）か署名適合から述語を選び（:201-240）、写した位置（写した引数の組）に関係を作って埋める（:241-255）。
  選んだ述語が、その位置で見えている関係と同じでも埋める（場面で見えている関係の言い直しになる）。
  行の元の述語と同じ関係がその位置に見えているときは、その関係を返して埋めない（:190-200）。これは今のまま。
直し（旗オン）
  選んだ述語が、写した位置で見えている関係と同じ（述語も引数の組も同じ）なら、その席は埋めない（None を返す。選び直さない）。
  同じ物の組にほかの述語の関係が見えていても、選んだ述語そのものが見えていなければ、今までどおり埋める（伏せ辺を当てる穴埋めは残る）。
  述語を選ぶ段（候補の分布・同点・乱数の引き）は今のまま。同点のときは今も述語を選ばない（most_frequent が None）ので、そこは変わらない。
  埋めなかった席を引数に持つ上の階の行は、その席を使えないので埋まらない（v3.4 と同じ扱い）。その数を STATS["skipped_with_parent_waiting"] に数える（記録だけ）。
入れ方：下の fill_missing_slots は abm/filling.py:118-263 の写し（md5 39837cf1d3fa33bb33324302853ad554 の版）に、上の判定の 9 行（説明の 3 行を含む）と数えの 1 行を足しただけ。
  install() で abm.filling・abm.agent_runtime・abm.loop の名前 fill_missing_slots をこの写しに差し替える（予測・穴埋め・反実仮想の予測のすべて）。
  ★ tools/projfirst.py は install の時点の agent_runtime.fill_missing_slots を包むので、この install を先に入れる（tools/v3_run.py）。
"""
from __future__ import annotations

from typing import Mapping

from abm.definition import Constituent, FrequencyTable, NamedDefinition
from abm.domains import Relation, RelationGraph
from abm.filling import (
    RNG, FillingResult, _distribution, _is_higher, _mapped_arguments_recursive, _predicate_has_signature,
    _same_order, most_frequent, sample_predicate, slot_signature,
)

STATS: dict = {"calls": 0, "skipped_restatement": 0, "skipped_with_parent_waiting": 0}


def fill_missing_slots(
    definition: NamedDefinition,
    target: RelationGraph,
    entity_mapping: Mapping[str, str],
    relation_mapping: Mapping[str, str],
    slot_history: Mapping[tuple[str, int], frozenset[str]],
    p_hat: FrequencyTable,
    fill_selection: str = "most_frequent",
    rng: RNG | None = None,
    *,
    higher_order_predicates: frozenset[str] | None,
    local_lambda: float = 0.0,
) -> FillingResult:
    """可視部に答えがないスロットを、依存先から再帰的に充填する。

    higher_order_predicates は、その走行の種から作った高階の述語の集合。
    ★ キーワード必須で既定値を置かない。渡し忘れは TypeError で落ちる。
      None が渡された場合もここで落とす。黙って空集合として扱わない（C-33）。
    """

    if higher_order_predicates is None:
        raise ValueError(
            "higher_order_predicates が渡されていない。"
            "abm.seed.higher_order_predicates(seed) から作って渡すこと（C-33）"
        )
    STATS["calls"] += 1
    all_predicates = tuple(p_hat.alive_vocab)
    relations: list[Relation] = []
    indices: list[int] = []
    ambiguous = False
    fallback_used = False
    sources: list[str] = []
    alive_flags: list[bool] = []
    empty_pool_slots = 0
    history_size = 0
    tie_candidates = 0
    distributions: list[dict[str, object]] = []
    if fill_selection not in {"most_frequent", "sample"}:
        raise ValueError(f"未知の fill_selection: {fill_selection}")
    if fill_selection == "sample" and rng is None:
        raise ValueError("fill_selection='sample' には rng が必要です")
    definition_graph = RelationGraph("definition", relations=tuple(c.relation for c in definition.constituents))
    definition_relation_ids = {c.relation.relation_id for c in definition.constituents}
    scene_relation_ids = {relation.relation_id for relation in target.relations}
    definition_by_id = {
        constituent.relation.relation_id: constituent
        for constituent in definition.constituents
    }
    filled_by_id: dict[str, Relation] = {}
    visiting: set[str] = set()

    def fill(constituent: Constituent) -> Relation | None:
        nonlocal ambiguous, fallback_used, history_size, tie_candidates, empty_pool_slots
        relation_id = constituent.relation.relation_id
        if relation_id in filled_by_id:
            return filled_by_id[relation_id]
        if relation_id in visiting:
            raise ValueError("def(R) の充填依存に循環がある")
        mapped_to = relation_mapping.get(constituent.relation.relation_id)
        if mapped_to is not None and mapped_to in scene_relation_ids:
            return None
        visiting.add(relation_id)
        mapped_arguments = _mapped_arguments_recursive(
            constituent.relation,
            entity_mapping,
            relation_mapping,
            definition_by_id,
            scene_relation_ids,
            fill,
        )
        if mapped_arguments is None:
            visiting.remove(relation_id)
            return None
        visible = next(
            (
                item for item in target.relations
                if item.predicate == constituent.relation.predicate
                and item.arguments == mapped_arguments
            ),
            None,
        )
        if visible is not None:
            visiting.remove(relation_id)
            return visible
        raw_history = slot_history.get((definition.name, constituent.slot_index))
        pool = raw_history if raw_history else frozenset()
        local_counts = raw_history if isinstance(raw_history, Mapping) else None
        used_fallback = not pool
        if used_fallback:
            local_counts = None   # ★ 署名適合には回数が無い
            signature = slot_signature(constituent.relation, definition_graph)
            pool = frozenset(
                predicate for predicate in all_predicates
                if _predicate_has_signature(predicate, signature, target, definition_graph)
            )
        # 階数を揃える。高階＝その構成素の引数が定義グラフの関係IDを含む（Gentner 1983）
        pool_before_order = pool
        want_higher = _is_higher(constituent.relation, definition_relation_ids)
        pool = frozenset(
            predicate for predicate in pool
            if _same_order(predicate, want_higher, higher_order_predicates)
        )
        if pool_before_order and not pool:
            empty_pool_slots += 1  # ★ 記録専用。階数の制約で候補が全部落ちた
        distribution = _distribution(pool, p_hat, local_lambda, local_counts)
        maximum = max((weight for _, weight in distribution), default=0.0)
        tied_count = sum(weight == maximum for _, weight in distribution) if maximum > 0 else 0
        history_size += len(pool)
        tie_candidates += tied_count if tied_count > 1 else 0
        distributions.append({
            "slot_index": constituent.slot_index,
            "candidates": [[predicate, weight] for predicate, weight in distribution],
        })
        if fill_selection == "sample":
            assert rng is not None
            predicate = sample_predicate(distribution, rng)
            tied = False
        else:
            predicate, tied = most_frequent(pool, p_hat, local_lambda, local_counts)
            ambiguous = ambiguous or tied
        fallback_used = fallback_used or used_fallback
        if predicate is None:
            visiting.remove(relation_id)
            return None
        # ★ v3.5 --fill-norestate（2026-09-27 判断 1、案 B）：選んだ述語が、写した位置（引数の組）で見えている関係と同じ
        #   （述語も引数の組も同じ）なら、その席は埋めない（選び直さない）。同じ物の組にほかの述語の関係が見えていても、
        #   選んだ述語そのものが見えていなければ、今までどおり埋める。
        if any(item.predicate == predicate and item.arguments == mapped_arguments for item in target.relations):
            visiting.remove(relation_id)
            STATS["skipped_restatement"] += 1
            if visiting:
                STATS["skipped_with_parent_waiting"] += 1   # ★ 記録だけ。この席を引数に持つ上の階の行が、埋めるのを待っていた
            return None
        filled = Relation(
            relation_id=(
                f"filling__{definition.name}__{constituent.slot_index}"
                f"__{constituent.registered_at}"
            ),
            predicate=predicate,
            arguments=mapped_arguments,
        )
        filled_by_id[relation_id] = filled
        relations.append(filled)
        indices.append(constituent.slot_index)
        sources.append("signature_fallback" if used_fallback else "slot_history")
        alive_flags.append(bool(constituent.alive))  # ★ 記録専用
        visiting.remove(relation_id)
        return filled

    for constituent in sorted(definition.constituents, key=lambda row: row.slot_index):
        fill(constituent)
    return FillingResult(
        tuple(relations), tuple(indices), ambiguous, fallback_used, tuple(sources),
        history_size, tie_candidates, tuple(distributions),
        tuple(alive_flags), empty_pool_slots,
    )


def install() -> None:
    import abm.agent_runtime as ar
    import abm.filling as fl
    import abm.loop as lp

    STATS.update(calls=0, skipped_restatement=0, skipped_with_parent_waiting=0)
    fl.fill_missing_slots = fill_missing_slots
    ar.fill_missing_slots = fill_missing_slots
    lp.fill_missing_slots = fill_missing_slots
