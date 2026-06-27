"""BUILD ORDER 第5段の撹乱オペレータ。

各オペレータは世界の完全 target、伏せる一階関係、公開 target 関係集合だけを
決める。公開入力は必ず ``redact`` で生成し、検証用の統合世界は ``OracleView``
だけに入れる。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from abm.agent_runtime import redact
from abm.domains import AgentInput, Entity, OracleView, Relation, RelationGraph, TargetType
from abm.seeds import SeedGraphs


@dataclass(frozen=True, slots=True)
class PerturbationParams:
    """刺激世界の作り方だけを保持する設定。"""

    instance_id: str = "layer_a_step5"
    surface_predicates: tuple[str, ...] = ("resembles", "same_surface_label")
    surface_argument_pairs: tuple[tuple[str, str], ...] = ()
    reversible_predicates: tuple[str, ...] = (
        "more_massive_than",
        "greater_potential_than",
        "flows_from_to",
        "revolves_around",
    )
    hidden_binding_predicates: tuple[str, ...] = (
        "central_body",
        "orbiting_body",
        "source_role",
        "sink_role",
    )
    discriminating_predicates: tuple[str, ...] = (
        "central_body",
        "orbiting_body",
        "source_role",
        "sink_role",
    )
    surplus_predicate: str = "irrelevant_marker"
    surplus_entity_count: int = 2


@dataclass(frozen=True, slots=True)
class PerturbationResult:
    agent_input: AgentInput
    oracle_view: OracleView


PerturbationOperator = Callable[[SeedGraphs, PerturbationParams], PerturbationResult]


def isomorphic(seed: SeedGraphs, params: PerturbationParams) -> PerturbationResult:
    target_full = _copy_graph(seed.target_graph, _graph_id(seed, params, "isomorphic"))
    held_out_edge = _primary_held_out_edge(seed, target_full)
    return _result(seed, target_full, held_out_edge, TargetType.ISOMORPHIC)


def anti_analogy(seed: SeedGraphs, params: PerturbationParams) -> PerturbationResult:
    base_target = _copy_graph(seed.target_graph, _graph_id(seed, params, "anti_analogy"))
    surface_relations = _surface_relations(base_target, params)
    tempting_graph = _replace_relations(
        base_target,
        (*base_target.relations, *surface_relations),
    )
    target_full = _break_first_higher_order_premise(tempting_graph, surface_relations)
    held_out_edge = _primary_held_out_edge(seed, target_full)
    return _result(seed, target_full, held_out_edge, TargetType.ANTI_ANALOGY)


def role_reversal(seed: SeedGraphs, params: PerturbationParams) -> PerturbationResult:
    target_full = _copy_graph(seed.target_graph, _graph_id(seed, params, "role_reversal"))
    target_full = _reverse_first_matching_relation(target_full, params.reversible_predicates)
    held_out_edge = _primary_held_out_edge(seed, target_full)
    hidden_ids = _relation_ids_by_predicate(target_full, params.hidden_binding_predicates)
    visible_ids = _visible_ids(target_full, held_out_edge, hidden_ids)
    return _result(seed, target_full, held_out_edge, TargetType.ROLE_REVERSAL, visible_ids)


def role_divergence(seed: SeedGraphs, params: PerturbationParams) -> PerturbationResult:
    _require_two_discriminating_relations(seed.target_graph, params.discriminating_predicates)
    target_full = _copy_graph(seed.target_graph, _graph_id(seed, params, "role_divergence"))
    target_full = _swap_first_two_discriminating_arguments(
        target_full,
        params.discriminating_predicates,
    )
    held_out_edge = _primary_held_out_edge(seed, target_full)
    return _result(seed, target_full, held_out_edge, TargetType.ROLE_DIVERGENCE)


def surplus(seed: SeedGraphs, params: PerturbationParams) -> PerturbationResult:
    target_full = _copy_graph(seed.target_graph, _graph_id(seed, params, "surplus"))
    target_full = _add_surplus_subgraph(target_full, params)
    held_out_edge = _primary_held_out_edge(seed, target_full)
    return _result(seed, target_full, held_out_edge, TargetType.SURPLUS)


def opaque(seed: SeedGraphs, params: PerturbationParams) -> PerturbationResult:
    target_full = _copy_graph(seed.target_graph, _graph_id(seed, params, "opaque"))
    held_out_edge = _primary_held_out_edge(seed, target_full)
    hidden_ids = _relation_ids_by_predicate(target_full, params.discriminating_predicates)
    visible_ids = _visible_ids(target_full, held_out_edge, hidden_ids)
    return _result(seed, target_full, held_out_edge, TargetType.OPAQUE, visible_ids)


def perturbations() -> tuple[PerturbationOperator, ...]:
    """第5段で作る六オペレータを固定順で返す。"""

    return (isomorphic, anti_analogy, role_reversal, role_divergence, surplus, opaque)


def _result(
    seed: SeedGraphs,
    target_full: RelationGraph,
    held_out_edge: Relation,
    target_type: TargetType,
    visible_relation_ids: frozenset[str] | None = None,
) -> PerturbationResult:
    if visible_relation_ids is None:
        visible_relation_ids = _visible_ids(target_full, held_out_edge, frozenset())
    agent_input = redact(
        G_star=target_full,
        held_out_edge=held_out_edge,
        visibility_spec={
            "base_graph": seed.base_graph,
            "visible_relation_ids": tuple(sorted(visible_relation_ids)),
        },
    )
    oracle_view = OracleView(
        G_star=_integrated_world(seed.base_graph, target_full),
        held_out_edge=held_out_edge,
        target_type=target_type,
        seed_id=seed.seed_id,
    )
    return PerturbationResult(agent_input=agent_input, oracle_view=oracle_view)


def _primary_held_out_edge(seed: SeedGraphs, target_full: RelationGraph) -> Relation:
    by_id = {relation.relation_id: relation for relation in target_full.relations}
    for candidate in seed.held_out_candidates:
        relation = by_id.get(candidate.relation_id)
        if relation is not None and _is_first_order(relation, target_full):
            return relation
    raise ValueError(f"seed has no first-order held-out candidate: {seed.seed_id}")


def _is_first_order(relation: Relation, graph: RelationGraph) -> bool:
    relation_ids = {item.relation_id for item in graph.relations}
    return all(argument not in relation_ids for argument in relation.arguments)


def _visible_ids(
    graph: RelationGraph,
    held_out_edge: Relation,
    hidden_relation_ids: frozenset[str],
) -> frozenset[str]:
    ids = {relation.relation_id for relation in graph.relations}
    ids.discard(held_out_edge.relation_id)
    ids.difference_update(hidden_relation_ids)
    return frozenset(ids)


def _copy_graph(graph: RelationGraph, graph_id: str) -> RelationGraph:
    return RelationGraph(graph_id=graph_id, entities=tuple(graph.entities), relations=tuple(graph.relations))


def _replace_relations(graph: RelationGraph, relations: tuple[Relation, ...]) -> RelationGraph:
    return RelationGraph(graph_id=graph.graph_id, entities=tuple(graph.entities), relations=relations)


def _integrated_world(base_graph: RelationGraph, target_full: RelationGraph) -> RelationGraph:
    return RelationGraph(
        graph_id=f"{base_graph.graph_id}__{target_full.graph_id}",
        entities=(*base_graph.entities, *target_full.entities),
        relations=(*base_graph.relations, *target_full.relations),
    )


def _graph_id(seed: SeedGraphs, params: PerturbationParams, suffix: str) -> str:
    return f"{params.instance_id}__{seed.target_graph.graph_id}__{suffix}"


def _surface_relations(graph: RelationGraph, params: PerturbationParams) -> tuple[Relation, ...]:
    entity_ids = tuple(entity.entity_id for entity in graph.entities)
    pairs = params.surface_argument_pairs or tuple(zip(entity_ids, entity_ids[1:]))
    predicates = params.surface_predicates or ("resembles",)
    relations: list[Relation] = []
    for index, pair in enumerate(pairs):
        if len(pair) != 2:
            raise ValueError("surface_argument_pairs must contain binary pairs")
        if pair[0] not in entity_ids or pair[1] not in entity_ids:
            raise ValueError("surface_argument_pairs must refer to target entities")
        predicate = predicates[index % len(predicates)]
        relations.append(
            Relation(
                f"{graph.graph_id}_surface_{index + 1}",
                predicate,
                (pair[0], pair[1]),
            )
        )
    return tuple(relations[:1])


def _break_first_higher_order_premise(
    graph: RelationGraph,
    surface_relations: tuple[Relation, ...],
) -> RelationGraph:
    if not surface_relations:
        return graph
    relation_ids = {relation.relation_id for relation in graph.relations}
    decoy_id = surface_relations[0].relation_id
    changed: list[Relation] = []
    replaced = False
    for relation in graph.relations:
        if not replaced and any(argument in relation_ids for argument in relation.arguments):
            changed.append(
                Relation(
                    relation.relation_id,
                    relation.predicate,
                    (decoy_id, *relation.arguments[1:]),
                    relation.attributes,
                )
            )
            replaced = True
        else:
            changed.append(relation)
    return _replace_relations(graph, tuple(changed))


def _reverse_first_matching_relation(
    graph: RelationGraph,
    predicates: tuple[str, ...],
) -> RelationGraph:
    changed: list[Relation] = []
    replaced = False
    for relation in graph.relations:
        if not replaced and relation.predicate in predicates and len(relation.arguments) >= 2:
            changed.append(
                Relation(
                    relation.relation_id,
                    relation.predicate,
                    (relation.arguments[1], relation.arguments[0], *relation.arguments[2:]),
                    relation.attributes,
                )
            )
            replaced = True
        else:
            changed.append(relation)
    return _replace_relations(graph, tuple(changed))


def _relation_ids_by_predicate(graph: RelationGraph, predicates: tuple[str, ...]) -> frozenset[str]:
    return frozenset(
        relation.relation_id for relation in graph.relations if relation.predicate in predicates
    )


def _require_two_discriminating_relations(
    graph: RelationGraph,
    predicates: tuple[str, ...],
) -> None:
    if len(_discriminating_relations(graph, predicates)) < 2:
        raise ValueError("role_divergence requires at least two discriminating relations")


def _discriminating_relations(
    graph: RelationGraph,
    predicates: tuple[str, ...],
) -> tuple[Relation, ...]:
    return tuple(
        relation
        for relation in graph.relations
        if relation.predicate in predicates and len(relation.arguments) == 1
    )


def _swap_first_two_discriminating_arguments(
    graph: RelationGraph,
    predicates: tuple[str, ...],
) -> RelationGraph:
    discriminators = _discriminating_relations(graph, predicates)
    first, second = discriminators[0], discriminators[1]
    replacements = {
        first.relation_id: Relation(
            first.relation_id,
            first.predicate,
            second.arguments,
            first.attributes,
        ),
        second.relation_id: Relation(
            second.relation_id,
            second.predicate,
            first.arguments,
            second.attributes,
        ),
    }
    return _replace_relations(
        graph,
        tuple(replacements.get(relation.relation_id, relation) for relation in graph.relations),
    )


def _add_surplus_subgraph(graph: RelationGraph, params: PerturbationParams) -> RelationGraph:
    count = max(params.surplus_entity_count, 1)
    entities = tuple(
        Entity(f"{graph.graph_id}_dummy_{index + 1}", "dummy") for index in range(count)
    )
    relations = tuple(
        Relation(
            f"{graph.graph_id}_surplus_{index + 1}",
            params.surplus_predicate,
            (entity.entity_id,),
        )
        for index, entity in enumerate(entities)
    )
    return RelationGraph(
        graph_id=graph.graph_id,
        entities=(*graph.entities, *entities),
        relations=(*graph.relations, *relations),
    )
