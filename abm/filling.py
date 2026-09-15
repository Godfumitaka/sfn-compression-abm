"""SPEC B1 §C.3.4 のスロット履歴による充填。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Mapping, Protocol

from abm.definition import Constituent, FrequencyTable, NamedDefinition
from abm.domains import Relation, RelationGraph


@dataclass(frozen=True, slots=True)
class FillingResult:
    relations: tuple[Relation, ...]
    slot_indices: tuple[int, ...]
    ambiguous: bool = False
    used_fallback: bool = False
    source_by_slot: tuple[str, ...] = ()
    slot_history_size: int = 0
    n_tie_candidates: int = 0
    candidate_distribution: tuple[dict[str, object], ...] = ()
    # ★ 記録専用。充填した各行の構成素が生存していたか（relations と同じ並び）。
    alive_by_slot: tuple[bool, ...] = ()
    # ★ 記録専用。階数の制約（2-B）で候補が全部落ち、埋まらなかったスロット数。
    empty_pool_slots: int = 0


class RNG(Protocol):
    def random(self) -> float: ...


def slot_signature(relation: Relation, graph: RelationGraph) -> tuple[int, tuple[str, ...]]:
    """アリティと引数型（entity/relation）だけから署名を作る。"""

    relation_ids = {item.relation_id for item in graph.relations}
    argument_types = tuple("relation" if arg in relation_ids else "entity" for arg in relation.arguments)
    return len(relation.arguments), argument_types


def _weights(
    names: list[str], p_hat: FrequencyTable,
    local_lambda: float = 0.0, local_counts: Mapping[str, int] | None = None,
) -> list[tuple[str, float]]:
    """正規化前の重み  (局所相対頻度)^λ × p̂（U-085 v1・SPEC:588 改訂）。

    ★ λ = 0.0 のときは p̂ そのものを返す。正規化を挟まないので、
      most_frequent の argmax と同点判定が 現行と浮動小数点まで一致する。
    ★ 署名適合フォールバック（SPEC:589）は回数を持たないので λ を効かせない。
    """

    if local_lambda == 0.0 or not local_counts:
        return [(predicate, p_hat.prob(predicate)) for predicate in names]
    denominator = sum(local_counts.get(predicate, 0) for predicate in names)
    if denominator <= 0:
        return [(predicate, p_hat.prob(predicate)) for predicate in names]
    return [
        (predicate,
         ((local_counts.get(predicate, 0) / denominator) ** local_lambda) * p_hat.prob(predicate))
        for predicate in names
    ]


def most_frequent(
    candidates: Iterable[str], p_hat: FrequencyTable,
    local_lambda: float = 0.0, local_counts: Mapping[str, int] | None = None,
) -> tuple[str | None, bool]:
    """重みの最頻を返す。最大値が同点なら内容を選ばない。
    ★ SPEC:588 改訂（仮U-41）。λ=0 は従来の p̂ 最頻と厳密に一致する。
    ★ 並び順（sorted）と同点の扱いは変えていない。"""

    unique = sorted(set(candidates))
    if not unique:
        return None, False
    scored = [(weight, predicate) for predicate, weight in
              _weights(unique, p_hat, local_lambda, local_counts)]
    maximum = max(score for score, _ in scored)
    winners = [predicate for score, predicate in scored if score == maximum]
    if len(winners) != 1:
        return None, True
    return winners[0], False


def _distribution(
    candidates: Iterable[str], p_hat: FrequencyTable,
    local_lambda: float = 0.0, local_counts: Mapping[str, int] | None = None,
) -> tuple[tuple[str, float], ...]:
    """U-085 v1  重み ＝ (局所相対頻度)^λ × p̂。
    ★ λ = 0.0 のとき (局所)^0 = 1 なので、現行と厳密に一致する経路を通す。
    ★ 局所相対頻度 ＝ そのスロットでの出現回数 ÷ そのスロットの総出現回数。
    ★ 履歴に載る＝回数 1 以上 なのでゼロ確率は起きない。
      署名適合フォールバック（SPEC:589）は回数を持たないので λ を効かせない。"""
    names = sorted(set(candidates))
    weighted = tuple(_weights(names, p_hat, local_lambda, local_counts))
    total = sum(weight for _, weight in weighted)
    if total == 0:
        return tuple((predicate, 0.0) for predicate, _ in weighted)
    return tuple((predicate, weight / total) for predicate, weight in weighted)


def sample_predicate(
    distribution: tuple[tuple[str, float], ...], rng: RNG
) -> str | None:
    """正規化済みの候補分布から一本を抽出する。"""

    if not distribution or sum(weight for _, weight in distribution) == 0:
        return None
    if len(distribution) == 1:
        return distribution[0][0]
    draw = rng.random()
    cumulative = 0.0
    for predicate, weight in distribution:
        cumulative += weight
        if draw < cumulative:
            return predicate
    return distribution[-1][0]


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


def observe_slot(
    history: Mapping[tuple[str, int], object],
    name: str,
    slot_index: int,
    predicate: str,
    local_lambda: float = 0.0,
) -> dict[tuple[str, int], object]:
    """★ local_lambda == 0.0 のときは従来どおり frozenset に add する。
    λ > 0 のときだけ出現回数のカウンタに積む（U-085 の v1）。
    ★ 型を λ で切り替えるのは、λ=0 の台帳を既存走行とバイト一致させるため。"""
    updated = dict(history)
    key = (name, slot_index)
    current = updated.get(key)
    if local_lambda == 0.0:
        base = current if isinstance(current, frozenset) else frozenset(current or ())
        updated[key] = frozenset((*base, predicate))
        return updated
    counts = dict(current) if isinstance(current, Mapping) else {q: 1 for q in (current or ())}
    counts[predicate] = counts.get(predicate, 0) + 1
    updated[key] = counts
    return updated


def _mapped_arguments(
    relation: Relation,
    entity_mapping: Mapping[str, str],
    relation_mapping: Mapping[str, str],
) -> tuple[str, ...] | None:
    mapped: list[str] = []
    for argument in relation.arguments:
        target = relation_mapping.get(argument, entity_mapping.get(argument))
        if target is None:
            return None
        mapped.append(target)
    return tuple(mapped)


def _mapped_arguments_recursive(
    relation: Relation,
    entity_mapping: Mapping[str, str],
    relation_mapping: Mapping[str, str],
    definition_by_id: Mapping[str, Constituent],
    scene_relation_ids: set[str],
    fill: Callable[[Constituent], Relation | None],
) -> tuple[str, ...] | None:
    """削除済み関係への参照を先に充填し、上位の引数へ接続する。"""

    mapped: list[str] = []
    for argument in relation.arguments:
        referenced = definition_by_id.get(argument)
        scene_id = relation_mapping.get(argument)
        if referenced is not None and (scene_id is None or scene_id not in scene_relation_ids):
            filled = fill(referenced)
            if filled is None:
                return None
            mapped.append(filled.relation_id)
            continue
        target_id = scene_id if scene_id is not None else entity_mapping.get(argument)
        if target_id is None:
            return None
        mapped.append(target_id)
    return tuple(mapped)


def _is_higher(relation: Relation, graph_relation_ids: set[str]) -> bool:
    """高階かどうか。引数に同じグラフの関係IDを含むなら高階（SPEC_B1:247/316）。"""

    return any(argument in graph_relation_ids for argument in relation.arguments)


def _same_order(
    predicate: str, want_higher: bool, higher_order_predicates: frozenset[str]
) -> bool:
    """候補の述語の階数が、そのスロットの階数と一致するか。

    higher_order_predicates はその走行の種から作る（abm/seed.py higher_order_predicates）。
    ★ 観測は要求しない。充填が埋めようとしているのは「いま場面に見えていない」位置
      であり、そこに入れる述語が場面に現れていることを求めるのは趣旨に反する。
      2026-09-12 以前はこの関数が target と definition_graph への観測を課しており、
      落とされた 116 件のうち 76 件は一階の述語だった（analysis_layeronly_2026-09-12 §4）。
    """

    return (predicate in higher_order_predicates) == want_higher


def _predicate_has_signature(
    predicate: str,
    signature: tuple[int, tuple[str, ...]],
    target: RelationGraph,
    definition_graph: RelationGraph,
) -> bool:
    occurrences = [
        relation for relation in (*target.relations, *definition_graph.relations)
        if relation.predicate == predicate
    ]
    return not occurrences or any(slot_signature(relation, target) == signature for relation in occurrences)
