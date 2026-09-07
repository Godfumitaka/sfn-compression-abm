"""SPEC B1 §C.3.4 のスロット履歴による充填。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Mapping

from abm.definition import Constituent, FrequencyTable, NamedDefinition
from abm.domains import Relation, RelationGraph


@dataclass(frozen=True, slots=True)
class FillingResult:
    relations: tuple[Relation, ...]
    slot_indices: tuple[int, ...]
    ambiguous: bool = False
    used_fallback: bool = False
    source_by_slot: tuple[str, ...] = ()


def slot_signature(relation: Relation, graph: RelationGraph) -> tuple[int, tuple[str, ...]]:
    """アリティと引数型（entity/relation）だけから署名を作る。"""

    relation_ids = {item.relation_id for item in graph.relations}
    argument_types = tuple("relation" if arg in relation_ids else "entity" for arg in relation.arguments)
    return len(relation.arguments), argument_types


def most_frequent(candidates: Iterable[str], p_hat: FrequencyTable) -> tuple[str | None, bool]:
    """p-hat 最頻を返す。最大値が同点なら内容を選ばない。"""

    unique = sorted(set(candidates))
    if not unique:
        return None, False
    scored = [(p_hat.prob(predicate), predicate) for predicate in unique]
    maximum = max(score for score, _ in scored)
    winners = [predicate for score, predicate in scored if score == maximum]
    if len(winners) != 1:
        return None, True
    return winners[0], False


def fill_missing_slots(
    definition: NamedDefinition,
    target: RelationGraph,
    entity_mapping: Mapping[str, str],
    relation_mapping: Mapping[str, str],
    slot_history: Mapping[tuple[str, int], frozenset[str]],
    p_hat: FrequencyTable,
) -> FillingResult:
    """可視部に答えがないスロットを、依存先から再帰的に充填する。"""

    all_predicates = tuple(p_hat.alive_vocab)
    relations: list[Relation] = []
    indices: list[int] = []
    ambiguous = False
    fallback_used = False
    sources: list[str] = []
    definition_graph = RelationGraph("definition", relations=tuple(c.relation for c in definition.constituents))
    scene_relation_ids = {relation.relation_id for relation in target.relations}
    definition_by_id = {
        constituent.relation.relation_id: constituent
        for constituent in definition.constituents
    }
    filled_by_id: dict[str, Relation] = {}
    visiting: set[str] = set()

    def fill(constituent: Constituent) -> Relation | None:
        nonlocal ambiguous, fallback_used
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
        pool = slot_history.get((definition.name, constituent.slot_index), frozenset())
        used_fallback = not pool
        if used_fallback:
            signature = slot_signature(constituent.relation, definition_graph)
            pool = frozenset(
                predicate for predicate in all_predicates
                if _predicate_has_signature(predicate, signature, target, definition_graph)
            )
        predicate, tied = most_frequent(pool, p_hat)
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
        visiting.remove(relation_id)
        return filled

    for constituent in definition.constituents:
        fill(constituent)
    return FillingResult(
        tuple(relations), tuple(indices), ambiguous, fallback_used, tuple(sources)
    )


def observe_slot(
    history: Mapping[tuple[str, int], frozenset[str]],
    name: str,
    slot_index: int,
    predicate: str,
) -> dict[tuple[str, int], frozenset[str]]:
    updated = dict(history)
    key = (name, slot_index)
    updated[key] = frozenset((*updated.get(key, frozenset()), predicate))
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
