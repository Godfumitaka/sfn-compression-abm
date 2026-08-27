"""SPEC B1 §C.3.4 のスロット履歴による充填。"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Mapping

from abm.definition import Constituent, FrequencyTable, NamedDefinition
from abm.domains import Relation, RelationGraph


@dataclass(frozen=True, slots=True)
class FillingResult:
    relations: tuple[Relation, ...]
    slot_indices: tuple[int, ...]
    ambiguous: bool = False
    used_fallback: bool = False


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
    """未充足かつ可視部に答えがない生存スロットを充填する。"""

    visible_content = {(item.predicate, item.arguments) for item in target.relations}
    all_predicates = tuple(p_hat.alive_vocab)
    relations: list[Relation] = []
    indices: list[int] = []
    ambiguous = False
    fallback_used = False
    definition_graph = RelationGraph("definition", relations=tuple(c.relation for c in definition.constituents))
    scene_relation_ids = {relation.relation_id for relation in target.relations}
    for constituent in definition.constituents:
        if not constituent.alive:
            continue
        mapped_to = relation_mapping.get(constituent.relation.relation_id)
        if mapped_to is not None and mapped_to in scene_relation_ids:
            continue
        mapped_arguments = _mapped_arguments(constituent.relation, entity_mapping, relation_mapping)
        if mapped_arguments is None:
            continue
        if (constituent.relation.predicate, mapped_arguments) in visible_content:
            continue
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
            continue
        relations.append(Relation(
            relation_id=f"filling__{definition.name}__{constituent.slot_index}",
            predicate=predicate,
            arguments=mapped_arguments,
        ))
        indices.append(constituent.slot_index)
    return FillingResult(tuple(relations), tuple(indices), ambiguous, fallback_used)


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
