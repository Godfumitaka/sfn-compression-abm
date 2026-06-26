"""SPEC §3.2b の権限分割ロール。

第3段では性能ではなく、予測前・予測後・分類後分析の入力境界を型と
シグネチャで固定する。エージェント側ロールは oracle 由来値を受け取らない。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from abm.domains import (
    Abstain,
    AgentInput,
    AgentOutput,
    AgentState,
    EdgePrediction,
    Relation,
    ScoringKey,
    TargetType,
)


@dataclass(frozen=True, slots=True)
class ModelScore:
    """予測前の内部モデル選択で使う oracle-free な採点結果。"""

    description_length: float
    L_H: float = 0.0
    L_DgH: float = 0.0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PriorStatistics:
    """事前固定 corpus または公開入力由来だけを想定する頻度統計。"""

    relation_counts: Mapping[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "relation_counts",
            MappingProxyType({str(key): int(value) for key, value in self.relation_counts.items()}),
        )


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    """予測後評価の最小結果。"""

    hit: int
    coverage: int
    predicted_edge: str | None = None


@dataclass(frozen=True, slots=True)
class MetricVector:
    """象限分類に渡す、ラベル非依存の指標ベクトル。"""

    transfer_gain: float = 0.0
    coordination_gain: float = 0.0
    coverage: float = 0.0


@dataclass(frozen=True, slots=True)
class PreregisteredCutpoints:
    """事前登録された分類閾値。"""

    transfer_min: float = 0.0
    coordination_min: float = 0.0
    coverage_min: float = 0.0


@dataclass(frozen=True, slots=True)
class QuadrantLabel:
    """分類結果。ラベル情報は含めない。"""

    name: str


@dataclass(frozen=True, slots=True)
class StratifiedRecord:
    """分類後に分析用ラベルを join したレコード。"""

    classification: QuadrantLabel
    target_type: TargetType
    seed_id: str


class ModelScorer:
    """予測前の内部MDL/モデル選択ロール。"""

    def __call__(self, agent_input: AgentInput, agent_state: AgentState) -> ModelScore:
        observed_edges = len(agent_input.base_graph.relations) + len(
            agent_input.target_graph_partial.relations
        )
        prototype_edges = 0 if agent_state.prototype is None else len(agent_state.prototype.relations)
        return ModelScore(
            description_length=float(observed_edges + prototype_edges),
            L_H=float(prototype_edges),
            L_DgH=float(observed_edges),
        )


class BaselinePredictor:
    """oracle-free な事前統計と公開入力だけを見るベースラインロール。"""

    def __call__(self, agent_input: AgentInput, prior_statistics: PriorStatistics) -> AgentOutput:
        candidates = _candidate_relations(agent_input)
        if not candidates:
            return AgentOutput(prediction=Abstain(reason="no_public_candidate"))
        best = max(
            candidates,
            key=lambda relation: (
                prior_statistics.relation_counts.get(relation.predicate, 0),
                relation.relation_id,
            ),
        )
        return AgentOutput(prediction=EdgePrediction(edge=best))


class OracleEvaluator:
    """予測後に `AgentOutput` と最小限の採点キーだけで評価するロール。"""

    def __call__(self, agent_output: AgentOutput, scoring_key: ScoringKey) -> EvaluationResult:
        prediction = agent_output.prediction
        if isinstance(prediction, EdgePrediction):
            predicted = prediction.edge.relation_id
            expected = scoring_key.held_out_edge.relation_id
            return EvaluationResult(hit=int(predicted == expected), coverage=1, predicted_edge=predicted)
        return EvaluationResult(hit=0, coverage=0, predicted_edge=None)


class QuadrantClassifier:
    """ラベル非依存の指標と事前cutpointだけで象限を分類するロール。"""

    def __call__(self, metric_vector: MetricVector, cutpoints: PreregisteredCutpoints) -> QuadrantLabel:
        transfer_ok = metric_vector.transfer_gain >= cutpoints.transfer_min
        coordination_ok = metric_vector.coordination_gain >= cutpoints.coordination_min
        coverage_ok = metric_vector.coverage >= cutpoints.coverage_min
        if transfer_ok and coordination_ok and coverage_ok:
            return QuadrantLabel(name="transfer_and_coordination")
        if transfer_ok and coverage_ok:
            return QuadrantLabel(name="transfer_only")
        if coordination_ok and coverage_ok:
            return QuadrantLabel(name="coordination_only")
        return QuadrantLabel(name="unresolved")


class Stratifier:
    """分類後に限って分析用ラベルを join するロール。"""

    def __call__(self, classification: QuadrantLabel, target_type: TargetType, seed_id: str) -> StratifiedRecord:
        return StratifiedRecord(classification=classification, target_type=target_type, seed_id=seed_id)


class Logger:
    """評価側の write-only sink。予測経路へ戻る状態を持たない。"""

    def __call__(self, record: Mapping[str, Any]) -> None:
        _ = record
        return None


def _candidate_relations(agent_input: AgentInput) -> tuple[Relation, ...]:
    return tuple(agent_input.target_graph_partial.relations)
