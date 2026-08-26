"""SPEC §3.2 の型境界。

このモジュールは第1段の構造契約だけを定義する。エージェント側DTOは
oracle 由来情報へ型レベルで到達できないよう、OracleView/Feedback と分離する。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

from abm.definition import (
    EmbedState,
    ExceptionAccumulator,
    FrequencyTable,
    MeritAccumulator,
    NamedDefinition,
)


class TargetType(str, Enum):
    ISOMORPHIC = "isomorphic"
    ANTI_ANALOGY = "anti_analogy"
    ROLE_REVERSAL = "role_reversal"
    ROLE_DIVERGENCE = "role_divergence"
    SURPLUS = "surplus"
    OPAQUE = "opaque"


class CorrectionMode(str, Enum):
    NONE = "none"
    CORRECTNESS_BIT = "correctness_bit"
    REVEALED_EDGE = "revealed_edge"


class SendingPolicy(str, Enum):
    RAW_INSTANCE_RANDOM = "raw_instance_random"


class PredictionKind(str, Enum):
    EDGE_PREDICTION = "EdgePrediction"
    ABSTAIN = "Abstain"


@dataclass(frozen=True, slots=True)
class Entity:
    entity_id: str
    label: str | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "attributes", _freeze_mapping(self.attributes))

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "label": self.label,
            "attributes": dict(self.attributes),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Entity":
        return cls(
            entity_id=str(data["entity_id"]),
            label=data.get("label"),
            attributes=dict(data.get("attributes", {})),
        )


@dataclass(frozen=True, slots=True)
class Relation:
    relation_id: str
    predicate: str
    arguments: tuple[str, ...]
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "arguments", tuple(self.arguments))
        object.__setattr__(self, "attributes", _freeze_mapping(self.attributes))

    def to_dict(self) -> dict[str, Any]:
        return {
            "relation_id": self.relation_id,
            "predicate": self.predicate,
            "arguments": list(self.arguments),
            "attributes": dict(self.attributes),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Relation":
        return cls(
            relation_id=str(data["relation_id"]),
            predicate=str(data["predicate"]),
            arguments=tuple(str(v) for v in data.get("arguments", ())),
            attributes=dict(data.get("attributes", {})),
        )


@dataclass(frozen=True, slots=True)
class RelationGraph:
    graph_id: str
    entities: tuple[Entity, ...] = ()
    relations: tuple[Relation, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "entities", tuple(self.entities))
        object.__setattr__(self, "relations", tuple(self.relations))

    def to_dict(self) -> dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "entities": [entity.to_dict() for entity in self.entities],
            "relations": [relation.to_dict() for relation in self.relations],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RelationGraph":
        return cls(
            graph_id=str(data["graph_id"]),
            entities=tuple(Entity.from_dict(v) for v in data.get("entities", ())),
            relations=tuple(Relation.from_dict(v) for v in data.get("relations", ())),
        )


@dataclass(frozen=True, slots=True)
class AgentInput:
    base_graph: RelationGraph
    target_graph_partial: RelationGraph
    observable_mask: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "observable_mask", tuple(self.observable_mask))

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_graph": self.base_graph.to_dict(),
            "target_graph_partial": self.target_graph_partial.to_dict(),
            "observable_mask": list(self.observable_mask),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AgentInput":
        return cls(
            base_graph=RelationGraph.from_dict(data["base_graph"]),
            target_graph_partial=RelationGraph.from_dict(data["target_graph_partial"]),
            observable_mask=tuple(str(v) for v in data.get("observable_mask", ())),
        )


@dataclass(frozen=True, slots=True)
class AgentConfig:
    threshold: float
    correction_mode: CorrectionMode
    lambda_: float = 1.0
    prototype_prior_weight: float = 0.0
    theta_prime: float = 0.0410
    tau_acc: float = 0.67
    alpha: float = 0.0
    beta: float = 0.0
    w: float = 0.0
    kappa: float = 1.0
    lambda_mix: float = 0.1
    abstain_charge: bool = False


@dataclass(frozen=True, slots=True)
class VerbatimTrace:
    """単回露出した一場面と、その書込時刻。"""

    written_at: int
    scene: RelationGraph

    def sigma(self, now: int) -> float:
        elapsed = now - self.written_at
        return float("inf") if elapsed <= 0 else elapsed ** -0.5


@dataclass(frozen=True, slots=True)
class Prototype:
    """合成せずに保持する逐語場面の列。"""

    traces: tuple[VerbatimTrace, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "traces", tuple(self.traces))

    def alive(self, now: int, theta_prime: float) -> tuple[VerbatimTrace, ...]:
        return tuple(trace for trace in self.traces if trace.sigma(now) >= theta_prime)


@dataclass(frozen=True, slots=True)
class AgentState:
    prototype: Prototype = Prototype()
    public_history: tuple[Any, ...] = ()
    rng_state: str | int | tuple[Any, ...] | None = None
    definitions: Mapping[str, NamedDefinition] = field(default_factory=dict)
    merit: Mapping[tuple[str, int], MeritAccumulator] = field(default_factory=dict)
    embed: Mapping[tuple[str, int], EmbedState] = field(default_factory=dict)
    exceptions: ExceptionAccumulator = ExceptionAccumulator(0.0, 0)
    p_hat: FrequencyTable = FrequencyTable.empty()
    slot_history: Mapping[tuple[str, int], frozenset[str]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "public_history", tuple(self.public_history))


@dataclass(frozen=True, slots=True)
class EdgePrediction:
    edge: Relation


@dataclass(frozen=True, slots=True)
class Abstain:
    reason: str | None = None


Prediction = EdgePrediction | Abstain


@dataclass(frozen=True, slots=True)
class AgentOutput:
    prediction: Prediction
    trace: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "trace", _freeze_mapping(self.trace))


@dataclass(frozen=True, slots=True)
class OracleView:
    G_star: RelationGraph
    held_out_edge: Relation
    target_type: TargetType
    seed_id: str


@dataclass(frozen=True, slots=True)
class ScoringKey:
    held_out_edge: Relation


@dataclass(frozen=True, slots=True)
class CorrectnessBit:
    is_correct: bool


@dataclass(frozen=True, slots=True)
class RevealedEdge:
    edge: Relation


Feedback = None | CorrectnessBit | RevealedEdge


def _freeze_mapping(data: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(dict(data))
