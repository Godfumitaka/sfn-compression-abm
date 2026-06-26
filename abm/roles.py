"""SPEC §3.2b のロール境界。

このモジュールは BUILD ORDER 第3段として、予測前ロールと予測後ロールを
別関数に分ける。`ModelScorer` と `BaselinePredictor` は公開入力だけを受け、
`OracleEvaluator` は予測後の出力と最小採点鍵だけを受ける。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Protocol, TextIO

from abm.domains import (
    Abstain,
    AgentInput,
    AgentOutput,
    AgentState,
    EdgePrediction,
    Prediction,
    ScoringKey,
)


@dataclass(frozen=True, slots=True)
class ScoreResult:
    """内部MDL選択ロールが返す、公開観測だけに基づく符号長。"""

    L_H: float
    L_DgH: float
    description_length: float
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "details", dict(self.details))


@dataclass(frozen=True, slots=True)
class MetricVector:
    """象限分類に渡す事前登録済み測度ベクトル。"""

    transfer_gain: float
    coordination_gain: float
    description_length: float


@dataclass(frozen=True, slots=True)
class Cutpoints:
    """ラベル非依存の象限分類しきい値。"""

    transfer: float = 0.0
    coordination: float = 0.0
    description_length: float = 0.0


@dataclass(frozen=True, slots=True)
class ClassifiedPoint:
    """`QuadrantClassifier` の分類結果。"""

    transfer_high: bool
    coordination_high: bool
    description_length_high: bool
    label: str


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    """予測後評価器が返す最小結果。"""

    hit: int
    coverage: int
    predicted_edge: str | None
    abstain_reason: str | None


@dataclass(frozen=True, slots=True)
class StratifiedRecord:
    """分類後に分析用メタデータを join した記録。"""

    classified: ClassifiedPoint
    metadata: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", dict(self.metadata))


class WriteOnlySink(Protocol):
    """評価側 logger が使う最小 write-only sink。"""

    def write(self, data: str) -> object: ...


def ModelScorer(agent_input: AgentInput, agent_state: AgentState) -> ScoreResult:
    """予測前の内部MDL選択用スコアを公開観測だけから計算する。

    第3段では SME/MDL 本体をまだ接続しないため、固定 codebook の詳細は置かず、
    `AgentInput` に含まれる観測辺数と prototype 辺数から単純なプレースホルダ符号長を返す。
    """

    observed_edges = len(agent_input.target_graph_partial.relations)
    prototype_edges = 0 if agent_state.prototype is None else len(agent_state.prototype.relations)
    L_H = float(prototype_edges)
    L_DgH = float(observed_edges)
    return ScoreResult(
        L_H=L_H,
        L_DgH=L_DgH,
        description_length=L_H + L_DgH,
        details={"observed_edges": observed_edges, "prototype_edges": prototype_edges},
    )


def BaselinePredictor(
    agent_input: AgentInput,
    frozen_statistics: Mapping[str, int] | None = None,
) -> Prediction:
    """公開入力または事前固定統計だけに基づくベースライン予測。

    第3段では二ベースライン本体はまだ実装しないため、正解挙動を埋め込まず棄却を返す。
    """

    _ = (agent_input, frozen_statistics)
    return Abstain(reason="baseline_not_implemented")


def OracleEvaluator(agent_output: AgentOutput, scoring_key: ScoringKey) -> EvaluationResult:
    """予測確定後に、最小採点鍵だけで hit/coverage を評価する。"""

    prediction = agent_output.prediction
    if isinstance(prediction, EdgePrediction):
        predicted_id = prediction.edge.relation_id
        return EvaluationResult(
            hit=int(predicted_id == scoring_key.held_out_edge.relation_id),
            coverage=1,
            predicted_edge=predicted_id,
            abstain_reason=None,
        )
    if isinstance(prediction, Abstain):
        return EvaluationResult(
            hit=0,
            coverage=0,
            predicted_edge=None,
            abstain_reason=prediction.reason,
        )
    raise TypeError("unknown prediction variant")


def QuadrantClassifier(
    metric_vector: MetricVector,
    preregistered_cutpoints: Cutpoints,
) -> ClassifiedPoint:
    """ラベルや seed を使わず、事前登録 cutpoint だけで象限を分類する。"""

    transfer_high = metric_vector.transfer_gain >= preregistered_cutpoints.transfer
    coordination_high = metric_vector.coordination_gain >= preregistered_cutpoints.coordination
    description_length_high = (
        metric_vector.description_length >= preregistered_cutpoints.description_length
    )
    label = "T{0}_C{1}_D{2}".format(
        int(transfer_high),
        int(coordination_high),
        int(description_length_high),
    )
    return ClassifiedPoint(
        transfer_high=transfer_high,
        coordination_high=coordination_high,
        description_length_high=description_length_high,
        label=label,
    )


def Stratifier(
    classified_points: Iterable[ClassifiedPoint],
    metadata_rows: Iterable[Mapping[str, Any]],
) -> tuple[StratifiedRecord, ...]:
    """分類後に分析用メタデータを join する。"""

    return tuple(
        StratifiedRecord(classified=classified, metadata=metadata)
        for classified, metadata in zip(classified_points, metadata_rows, strict=False)
    )


def Logger(record: Mapping[str, Any], sink: WriteOnlySink | TextIO) -> None:
    """評価側の write-only sink へ1レコードを書き込む。"""

    sink.write(f"{dict(record)}\n")


model_scorer = ModelScorer
baseline_predictor = BaselinePredictor
oracle_evaluator = OracleEvaluator
quadrant_classifier = QuadrantClassifier
stratifier = Stratifier
logger = Logger
