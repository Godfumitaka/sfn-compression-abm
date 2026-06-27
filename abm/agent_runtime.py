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
)


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
    rng_state: str | int | tuple[Any, ...] | None = None


def predict(
    agent_input: AgentInput,
    state: FrozenAgentState,
    config: AgentConfig,
    rng: RNG,
) -> tuple[AgentOutput, PendingState]:
    """公開入力だけから予測を確定し、フィードバック前の状態を返す。

    第2段では SME/MDL 未接続なので、正解挙動を stipulate せず一律に棄却する。
    `config` と `rng` は境界契約を固定するために受け取るが、oracle 情報は受け取らない。
    """

    _ = (agent_input, config, rng)
    output = AgentOutput(prediction=Abstain(reason="model_not_implemented"))
    pending = PendingState(
        previous_state=state,
        output=output,
        rng_state=_snapshot_rng_state(rng, state.rng_state),
    )
    return output, pending


def update(pending: PendingState, feedback: Feedback) -> AgentState:
    """保留状態と予測後フィードバックだけから次の `AgentState` を返す。"""

    state = pending.previous_state
    history = (*state.public_history, pending.output)
    next_state = replace(state, public_history=history, rng_state=pending.rng_state)

    if isinstance(feedback, RevealedEdge):
        return replace(next_state, prototype=_append_relation(next_state.prototype, feedback.edge))
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


def _append_relation(graph: RelationGraph | None, relation: Relation) -> RelationGraph:
    if graph is None:
        return RelationGraph(graph_id="prototype", relations=(relation,))
    if any(existing.relation_id == relation.relation_id for existing in graph.relations):
        return graph
    return RelationGraph(
        graph_id=graph.graph_id,
        entities=tuple(graph.entities),
        relations=(*graph.relations, relation),
    )


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
