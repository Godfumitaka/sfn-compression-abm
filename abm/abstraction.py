"""SPEC B1 §C.6.2 のm1（登録と更新）。"""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from typing import Mapping

from abm.accounting import freeze_price, initial_merit
from abm.definition import Constituent, EmbedState, ExceptionAccumulator, NamedDefinition
from abm.domains import AgentState, Relation, RelationGraph
from abm.filling import observe_slot
from abm.sme import Alignment, map_graphs


def _identify_definition(
    state: AgentState,
    scene: RelationGraph,
    threshold: float,
    self_score_cache: dict[str, float] | None = None,
) -> str | None:
    """SEQL/GEL の NSIM 閾値を最初に満たす生存 def(R) を同定する。"""

    cache = self_score_cache if self_score_cache is not None else {}
    definitions = sorted(
        (definition for definition in state.definitions.values() if definition.m_live > 0),
        key=lambda definition: (-definition.assimilation_count, -definition.registered_at),
    )
    for definition in definitions:
        graph = _definition_graph(definition)
        live_signature = tuple(
            (row.slot_index, row.registered_at)
            for row in definition.constituents
            if row.alive
        )
        cache_key = repr((definition.name, live_signature))
        self_score = cache.get(cache_key)
        if self_score is None:
            self_score = map_graphs(graph, graph).alignment.total_score
            cache[cache_key] = self_score
        if self_score <= 0:
            continue
        score = map_graphs(graph, scene).alignment.total_score
        if score / self_score >= threshold:
            return definition.name
    return None


def m1(
    state: AgentState,
    base: RelationGraph,
    target: RelationGraph,
    alignment: Alignment,
    trial: int,
    *,
    name: str | None = None,
    base_written_at: int,
    horizon: int,
) -> tuple[AgentState, dict[str, object] | None]:
    """整列の共通部分からサイズ2以上の def(R) を登録・更新する。"""

    base_by_id = {relation.relation_id: relation for relation in base.relations}
    target_by_id = {relation.relation_id: relation for relation in target.relations}
    raw_pairs = [
        (base_by_id[left], target_by_id[right])
        for left, right in sorted(alignment.relation_mapping.items())
        if left in base_by_id and right in target_by_id
    ]
    structural_ids = _structural_relation_ids(base)
    pairs = [
        pair for pair in raw_pairs
        if pair[0].relation_id in structural_ids and pair[0].predicate == pair[1].predicate
    ]
    if len(pairs) < 2:
        return state, None
    definition_name = name or _definition_name(pairs)
    old = state.definitions.get(definition_name)
    if old is None:
        common_relations = tuple(left for left, _ in pairs)
        constituents = tuple(
            _constituent(index, trial, left, common_relations, state, len(pairs))
            for index, (left, _) in enumerate(pairs)
        )
        definition = NamedDefinition(definition_name, constituents, len(constituents), trial)
    else:
        definition = _extend_definition(old, pairs, state, trial)
        definition = replace(
            definition,
            assimilation_count=old.assimilation_count + 1,
        )

    definitions = dict(state.definitions)
    definitions[definition_name] = definition
    merit = dict(state.merit)
    embed = dict(state.embed)
    exceptions = dict(state.exceptions)
    history = dict(state.slot_history)
    for constituent in definition.constituents:
        key = (definition_name, constituent.slot_index)
        if constituent.registered_at == trial:
            merit[key] = initial_merit(
                constituent.slot_index, trial, trial - base_written_at, horizon
            )
            embed[key] = EmbedState(constituent.slot_index, 0.0, 0.0)
            exceptions[key] = ExceptionAccumulator((0.0,) * 16, 0.0, 0)
        matching = next(
            (right for left, right in pairs if left.relation_id == constituent.relation.relation_id),
            None,
        )
        if matching is not None:
            history = observe_slot(history, definition_name, constituent.slot_index, matching.predicate)
    event_id = _alignment_event_id(alignment)
    next_state = replace(
        state, definitions=definitions, merit=merit, embed=embed,
        exceptions=exceptions, slot_history=history,
    )
    return next_state, {
        "kind": "registration",
        "R": definition_name,
        "alignment_event_id": event_id,
        "trial": trial,
    }


def _constituent(
    index: int,
    trial: int,
    relation: Relation,
    relations: tuple[Relation, ...],
    state: AgentState,
    m_alloc: int,
) -> Constituent:
    new_slots = _new_slot_count(relation, relations)
    price = freeze_price(state.p_hat, relation, new_slots, m_alloc)
    return Constituent(index, trial, relation, price)


def _extend_definition(
    old: NamedDefinition,
    pairs: list[tuple[Relation, Relation]],
    state: AgentState,
    trial: int,
) -> NamedDefinition:
    existing = {constituent.relation.predicate for constituent in old.constituents if constituent.alive}
    additions = [left for left, _ in pairs if left.predicate not in existing]
    tombstones = [row for row in old.constituents if not row.alive]
    if not additions or not tombstones:
        return old
    rows = list(old.constituents)
    for relation, tombstone in zip(additions, tombstones):
        price = freeze_price(
            state.p_hat,
            relation,
            _new_slot_count(relation, tuple(additions)),
            old.m_alloc,
        )
        rows.append(Constituent(tombstone.slot_index, trial, relation, price))
    return NamedDefinition(
        old.name,
        tuple(rows),
        old.m_alloc,
        old.registered_at,
        old.assimilation_count,
    )


def _new_slot_count(relation: Relation, relations: tuple[Relation, ...]) -> int:
    return sum(
        1 for argument in relation.arguments
        if sum(argument in item.arguments for item in relations) == 1
    )


def _definition_name(pairs: list[tuple[Relation, Relation]]) -> str:
    material = "\x1f".join(sorted(left.predicate for left, _ in pairs)).encode()
    return f"R_{sha256(material).hexdigest()[:16]}"


def _alignment_event_id(alignment: Alignment) -> str:
    material = repr(sorted(alignment.relation_mapping.items())).encode()
    return sha256(material).hexdigest()[:16]


def _structural_relation_ids(graph: RelationGraph) -> frozenset[str]:
    relation_ids = {relation.relation_id for relation in graph.relations}
    higher_order = {
        relation.relation_id
        for relation in graph.relations
        if any(argument in relation_ids for argument in relation.arguments)
    }
    referenced = {
        argument
        for relation in graph.relations
        if relation.relation_id in higher_order
        for argument in relation.arguments
        if argument in relation_ids
    }
    return frozenset(higher_order | referenced)


def _definition_graph(definition: NamedDefinition) -> RelationGraph:
    """墓石を含む def(R) を SME 入力グラフへ変換する。"""

    relation_ids = {row.relation.relation_id for row in definition.constituents}
    entity_ids = sorted({
        argument
        for row in definition.constituents
        for argument in row.relation.arguments
        if argument not in relation_ids
    })
    from abm.domains import Entity

    return RelationGraph(
        graph_id=f"definition:{definition.name}",
        entities=tuple(Entity(entity_id) for entity_id in entity_ids),
        relations=tuple(row.relation for row in definition.constituents),
    )
