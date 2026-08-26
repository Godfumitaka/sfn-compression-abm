"""BUILD ORDER 第2段のエージェント実行境界。

このモジュールは SPEC §3.2 の二フェーズ契約だけを実装する。
`redact` は信頼済み境界として完全グラフを読むが、`predict` は redaction 後の
`AgentInput`・凍結状態・設定・RNG だけを受け取り、oracle 由来値を受け取らない。
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from random import Random
from typing import Any, Iterable, Mapping, Protocol, TypeAlias

from abm.domains import (
    Abstain,
    AgentConfig,
    AgentInput,
    AgentOutput,
    AgentState,
    CorrectnessBit,
    Feedback,
    Relation,
    RelationGraph,
    RevealedEdge,
    Prototype,
    VerbatimTrace,
)
from abm.filling import fill_missing_slots
from abm.accounting import update_frequency
from abm.sme import apply_threshold, map_graphs, project


class RNG(Protocol):
    """`predict` に注入できる最小乱数インターフェース。"""

    def random(self) -> float: ...


FrozenAgentState: TypeAlias = AgentState


@dataclass(frozen=True, slots=True)
class PendingState:
    """予測確定後、フィードバック受領前の保留状態。

    oracle 由来のフィードバックはここには含めず、`update` の引数としてだけ受ける。
    """

    previous_state: FrozenAgentState
    output: AgentOutput
    agent_input: AgentInput | None = None
    rng_state: str | int | tuple[Any, ...] | None = None


def predict(
    agent_input: AgentInput,
    state: FrozenAgentState,
    config: AgentConfig,
    rng: RNG,
) -> tuple[AgentOutput, PendingState]:
    """公開入力と不変状態だけから P1〜P7 を実行する。"""

    if not state.prototype.traces:
        output = AgentOutput(prediction=Abstain(reason="no_prototype"), trace={})
        return output, PendingState(state, output, agent_input, _snapshot_rng_state(rng, state.rng_state))
    ranked = []
    for trace in state.prototype.traces:
        result = map_graphs(trace.scene, agent_input.target_graph_partial)
        ranked.append((result, trace))
    mapping, selected_trace = sorted(
        ranked,
        key=lambda item: (-item[0].alignment.total_score, -item[1].written_at, item[1].scene.graph_id),
    )[0]
    base = selected_trace.scene
    threshold = apply_threshold(mapping, config.threshold)
    trace: dict[str, Any] = {
        "alignment": mapping.alignment,
        "support_at_adoption": 0,
        "R_used": None,
        "m_live": 0,
        "filled_slots": (),
        "entity_map_covered": False,
        "selected_scene": base,
    }
    if not threshold.accepted:
        prediction = Abstain(reason="below_threshold")
    else:
        prediction = project(
            mapping.alignment,
            base,
            agent_input.target_graph_partial,
            prototype_prior_weight=config.prototype_prior_weight,
        )
        selected = _select_definition(state, mapping)
        if selected is not None:
            name, definition, support = selected
            trace.update(
                m_live=definition.m_live,
                support_at_adoption=support,
                definition_alignment=mapping.alignment,
            )
            if support >= min(2, definition.m_live):
                trace["R_identified"] = name
            if support >= _need(config.tau_acc, definition.m_live):
                trace["R_used"] = name
                prediction = project(
                    mapping.alignment,
                    base,
                    agent_input.target_graph_partial,
                    prototype_prior_weight=0.0,
                )
                filling = fill_missing_slots(
                    definition,
                    agent_input.target_graph_partial,
                    mapping.alignment.entity_mapping,
                    mapping.alignment.relation_mapping,
                    state.slot_history,
                    state.p_hat,
                )
                trace.update(
                    filled_slots=filling.relations,
                    filled_slot_indices=filling.slot_indices,
                    filling_fallback=filling.used_fallback,
                    entity_map_covered=all(
                        argument in mapping.alignment.entity_mapping
                        or argument in mapping.alignment.relation_mapping
                        for row in definition.constituents
                        for argument in row.relation.arguments
                    ),
                )
                if filling.ambiguous:
                    prediction = Abstain(reason="ambiguous_projection")
                elif isinstance(prediction, Abstain) and filling.relations:
                    prediction = EdgePrediction(filling.relations[0])
    output = AgentOutput(prediction=prediction, trace=trace)
    pending = PendingState(
        previous_state=state,
        output=output,
        agent_input=agent_input,
        rng_state=_snapshot_rng_state(rng, state.rng_state),
    )
    return output, pending


def _need(tau_acc: float, m_live: int) -> int:
    from math import ceil

    return ceil(tau_acc * m_live)


def _select_definition(state: AgentState, mapping: Any):
    ranked = []
    for name, definition in state.definitions.items():
        relation_mapping = mapping.alignment.relation_mapping
        support = sum(
            1 for constituent in definition.constituents
            if constituent.alive and constituent.relation.relation_id in relation_mapping
        )
        if support:
            ranked.append((-support, name, definition, support))
    if not ranked:
        return None
    _, name, definition, support = sorted(
        ranked, key=lambda item: (item[0], item[1])
    )[0]
    return name, definition, support


def _definition_graph(definition: Any) -> RelationGraph:
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


def update(pending: PendingState, feedback: Feedback) -> AgentState:
    """保留状態と予測後フィードバックだけから次の `AgentState` を返す。"""

    state = pending.previous_state
    written = pending.agent_input.target_graph_partial if pending.agent_input is not None else None
    history = (*state.public_history, pending.output)
    p_hat = update_frequency(state.p_hat, written.relations if written is not None else ())
    trial = max((trace.written_at for trace in state.prototype.traces), default=-1) + 1
    prototype = _write_graph(state.prototype, written, trial)
    next_state = replace(
        state,
        public_history=history,
        prototype=prototype,
        rng_state=pending.rng_state,
        p_hat=p_hat,
    )

    if isinstance(feedback, RevealedEdge):
        prototype = _write_relation(
            next_state.prototype,
            feedback.edge,
            trial,
        )
        return replace(
            next_state,
            public_history=(*next_state.public_history, feedback.edge),
            prototype=prototype,
            p_hat=update_frequency(next_state.p_hat, (feedback.edge,)),
        )
    if isinstance(feedback, CorrectnessBit) or feedback is None:
        return next_state
    raise TypeError("unknown feedback variant")


def redact(
    G_star: RelationGraph,
    held_out_edge: Relation,
    visibility_spec: Mapping[str, Any] | Iterable[str] | None,
) -> AgentInput:
    """完全 target graph から hold-out と不可視辺を除いた `AgentInput` を作る。

    `observable_mask` は公開済み relation_id の正の情報だけに限定し、完全グラフ上の
    bitmap や欠番 ID 列は返さない。
    """

    base_graph = _require_base_graph(visibility_spec)
    visible_relation_ids = _visible_relation_ids(G_star, held_out_edge, visibility_spec)
    visible_relations = tuple(
        relation for relation in G_star.relations if relation.relation_id in visible_relation_ids
    )
    visible_relations = _drop_relations_referencing_hidden(
        visible_relations,
        {held_out_edge.relation_id},
    )
    target_graph_partial = RelationGraph(
        graph_id=G_star.graph_id,
        entities=tuple(G_star.entities),
        relations=visible_relations,
    )
    return AgentInput(
        base_graph=base_graph,
        target_graph_partial=target_graph_partial,
        observable_mask=tuple(relation.relation_id for relation in visible_relations),
    )


def _visible_relation_ids(
    graph: RelationGraph,
    hidden_relation: Relation,
    visibility_spec: Mapping[str, Any] | Iterable[str] | None,
) -> set[str]:
    all_ids = {relation.relation_id for relation in graph.relations}
    if visibility_spec is None:
        visible_ids = set(all_ids)
    elif isinstance(visibility_spec, Mapping):
        raw_ids = visibility_spec.get("visible_relation_ids")
        if raw_ids is None:
            raw_ids = visibility_spec.get("observable_relation_ids")
        if raw_ids is None:
            raw_ids = all_ids
        visible_ids = {str(relation_id) for relation_id in raw_ids}
    else:
        visible_ids = {str(relation_id) for relation_id in visibility_spec}

    visible_ids.intersection_update(all_ids)
    visible_ids.discard(hidden_relation.relation_id)
    return visible_ids


def _drop_relations_referencing_hidden(
    relations: tuple[Relation, ...],
    hidden_ids: set[str],
) -> tuple[Relation, ...]:
    """不可視 relation_id を引数に持つ relation を推移的に可視集合から除く。"""

    hidden = set(hidden_ids)
    changed = True
    while changed:
        changed = False
        for relation in relations:
            if relation.relation_id in hidden:
                continue
            if any(argument in hidden for argument in relation.arguments):
                hidden.add(relation.relation_id)
                changed = True
    return tuple(relation for relation in relations if relation.relation_id not in hidden)


def _require_base_graph(
    visibility_spec: Mapping[str, Any] | Iterable[str] | None,
) -> RelationGraph:
    if not isinstance(visibility_spec, Mapping):
        raise TypeError("visibility_spec must be a mapping with base_graph")
    if "base_graph" not in visibility_spec:
        raise ValueError("visibility_spec must include base_graph")
    base_graph = visibility_spec["base_graph"]
    if not isinstance(base_graph, RelationGraph):
        raise TypeError("visibility_spec['base_graph'] must be a RelationGraph")
    return base_graph


def _append_relation(graph: RelationGraph, relation: Relation) -> RelationGraph:
    if any(existing.relation_id == relation.relation_id for existing in graph.relations):
        return graph
    return RelationGraph(
        graph_id=graph.graph_id,
        entities=tuple(graph.entities),
        relations=(*graph.relations, relation),
    )


def _write_graph(
    prototype: Prototype,
    observed: RelationGraph | None,
    trial: int,
) -> Prototype:
    if observed is None:
        return prototype
    return Prototype((*prototype.traces, VerbatimTrace(trial, observed)))


def _write_relation(
    prototype: Prototype,
    relation: Relation,
    trial: int,
) -> Prototype:
    traces = list(prototype.traces)
    if not traces or traces[-1].written_at != trial:
        traces.append(VerbatimTrace(trial, RelationGraph(f"scene-{trial}", relations=(relation,))))
    else:
        trace = traces[-1]
        traces[-1] = VerbatimTrace(trace.written_at, _append_relation(trace.scene, relation))
    return Prototype(tuple(traces))


def _snapshot_rng_state(
    rng: RNG,
    fallback: str | int | tuple[Any, ...] | None,
) -> str | int | tuple[Any, ...] | None:
    if isinstance(rng, Random):
        return rng.getstate()
    getstate = getattr(rng, "getstate", None)
    if callable(getstate):
        state = getstate()
        if isinstance(state, (str, int, tuple)) or state is None:
            return state
    return fallback
