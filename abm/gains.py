"""SPEC §7 の転移・ベースライン・協調指標。

このモジュールは Stage 8 の試行単位ユーティリティだけを提供する。
予測生成は公開 AgentInput または明示的に渡された事前固定統計だけを使い、
hit 判定は予測確定後に roles.OracleEvaluator へ委譲する。
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from abm.domains import Abstain, AgentInput, AgentOutput, EdgePrediction, Prediction, Relation, ScoringKey
from abm.roles import EvaluationResult, OracleEvaluator

PredictionCategory = tuple[str, tuple[str, ...]] | str
RelationContent = tuple[str, tuple[str, ...]]

ABSTAIN_CATEGORY = "ABSTAIN"
FREQUENCY_BASELINE = "frequency"
FLAT_MATCHER_BASELINE = "flat_matcher"


@dataclass(frozen=True, slots=True)
class TrialPredictionRecord:
    """一試行の予測カテゴリと、任意の事後評価結果。"""

    prediction_category: PredictionCategory
    prediction_kind: str
    predicted_relation_content: RelationContent | None
    abstain_reason: str | None
    hit: int | None
    coverage: int


@dataclass(frozen=True, slots=True)
class TransferMetrics:
    accuracy: float
    coverage: float
    selective_accuracy: float | None
    n_trials: int


@dataclass(frozen=True, slots=True)
class BaselineTrialRecord:
    baseline_name: str
    prediction_category: PredictionCategory
    predicted_relation_content: RelationContent | None
    abstain_reason: str | None
    hit: int | None
    coverage: int


@dataclass(frozen=True, slots=True)
class BaselineLift:
    baseline_name: str
    lift: float
    n_trials: int


@dataclass(frozen=True, slots=True)
class CoordinationGain:
    observed_agreement: float
    chance_agreement: float
    coordination_gain: float
    n_trials: int


@dataclass(frozen=True, slots=True)
class FrequencyStatistics:
    """頻度ベースラインに渡す事前固定 relation content 統計。"""

    relation_counts: Mapping[RelationContent, int]

    def __post_init__(self) -> None:
        normalized = {
            _relation_content_key(content): int(count)
            for content, count in self.relation_counts.items()
            if int(count) > 0
        }
        object.__setattr__(self, "relation_counts", dict(sorted(normalized.items())))


@dataclass(frozen=True, slots=True)
class FlatMatch:
    """flat matcher が作る局所的な同名述語対応。"""

    base_relation: Relation
    partial_relation: Relation


def prediction_category(prediction: Prediction) -> PredictionCategory:
    """出力カテゴリを relation content または単一 Abstain カテゴリへ正準化する。"""

    if isinstance(prediction, EdgePrediction):
        return _content(prediction.edge)
    if isinstance(prediction, Abstain):
        return ABSTAIN_CATEGORY
    raise TypeError("unknown prediction variant")


def prediction_record(
    prediction: Prediction,
    evaluator: object | None = None,
    scoring_key: ScoringKey | None = None,
) -> TrialPredictionRecord:
    """一試行の予測記録を作り、採点鍵がある場合だけ事後評価を委譲する。"""

    result = _evaluate_prediction(prediction, evaluator=evaluator, scoring_key=scoring_key)
    content = _prediction_content(prediction)
    return TrialPredictionRecord(
        prediction_category=prediction_category(prediction),
        prediction_kind=type(prediction).__name__,
        predicted_relation_content=content,
        abstain_reason=prediction.reason if isinstance(prediction, Abstain) else None,
        hit=None if result is None else result.hit,
        coverage=_coverage(prediction) if result is None else result.coverage,
    )


def transfer_metrics(records: Sequence[TrialPredictionRecord]) -> TransferMetrics:
    """transfer accuracy・coverage・selective accuracy を別々に集計する。"""

    evaluated = [record for record in records if record.hit is not None]
    if len(evaluated) != len(records):
        raise ValueError("transfer_metrics requires evaluated records")
    n_trials = len(records)
    if n_trials == 0:
        return TransferMetrics(accuracy=0.0, coverage=0.0, selective_accuracy=None, n_trials=0)
    hits = [int(record.hit) for record in evaluated]
    covered = [record for record in evaluated if record.coverage == 1]
    selective = None if not covered else sum(int(record.hit) for record in covered) / len(covered)
    return TransferMetrics(
        accuracy=sum(hits) / n_trials,
        coverage=sum(record.coverage for record in evaluated) / n_trials,
        selective_accuracy=selective,
        n_trials=n_trials,
    )


def frequency_statistics_from_agent_input(agent_input: AgentInput) -> FrequencyStatistics:
    """公開 AgentInput 内の relation content だけから頻度統計を作る。"""

    counts = Counter(_content(relation) for relation in _visible_relations(agent_input))
    return FrequencyStatistics(relation_counts=dict(counts))


def frequency_baseline(
    agent_input: AgentInput,
    statistics: FrequencyStatistics | Mapping[RelationContent, int] | None = None,
) -> Prediction:
    """事前固定統計または公開入力頻度から、安定した content 候補を一つ返す。"""

    stats = statistics if statistics is not None else frequency_statistics_from_agent_input(agent_input)
    counts = stats.relation_counts if isinstance(stats, FrequencyStatistics) else FrequencyStatistics(stats).relation_counts
    if not counts:
        return Abstain(reason="frequency_no_candidate")
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0][0], item[0][1]))
    if len(ordered) > 1 and ordered[0][1] == ordered[1][1]:
        return Abstain(reason="frequency_ambiguous_candidate")
    predicate, arguments = ordered[0][0]
    return EdgePrediction(edge=Relation(relation_id="frequency_baseline_prediction", predicate=predicate, arguments=arguments))


def flat_matcher_baseline(agent_input: AgentInput) -> Prediction:
    """同名述語の局所一致だけで base の未提示 content を partial 側へ投影する。"""

    matches = _flat_matches(agent_input)
    if not matches:
        return Abstain(reason="flat_matcher_no_local_match")
    entity_mapping = _flat_entity_mapping(matches)
    if entity_mapping is None:
        return Abstain(reason="flat_matcher_ambiguous_mapping")
    existing = {_content(relation) for relation in agent_input.target_graph_partial.relations}
    matched_base_ids = {match.base_relation.relation_id for match in matches}
    candidates: list[RelationContent] = []
    for relation in sorted(agent_input.base_graph.relations, key=_relation_order):
        if relation.relation_id in matched_base_ids:
            continue
        mapped_arguments = tuple(entity_mapping.get(argument) for argument in relation.arguments)
        if any(argument is None for argument in mapped_arguments):
            continue
        content = (relation.predicate, tuple(str(argument) for argument in mapped_arguments))
        if content not in existing:
            candidates.append(content)
    unique = sorted(set(candidates), key=lambda item: (item[0], item[1]))
    if len(unique) != 1:
        return Abstain(reason="flat_matcher_unstable_candidate")
    predicate, arguments = unique[0]
    return EdgePrediction(edge=Relation(relation_id="flat_matcher_baseline_prediction", predicate=predicate, arguments=arguments))


def baseline_record(
    baseline_name: str,
    prediction: Prediction,
    evaluator: object | None = None,
    scoring_key: ScoringKey | None = None,
) -> BaselineTrialRecord:
    """ベースラインの試行単位予測と、任意の事後評価結果を保存する。"""

    record = prediction_record(prediction, evaluator=evaluator, scoring_key=scoring_key)
    return BaselineTrialRecord(
        baseline_name=baseline_name,
        prediction_category=record.prediction_category,
        predicted_relation_content=record.predicted_relation_content,
        abstain_reason=record.abstain_reason,
        hit=record.hit,
        coverage=record.coverage,
    )


def baseline_lift(
    agent_records: Sequence[TrialPredictionRecord],
    baseline_records: Sequence[BaselineTrialRecord],
    baseline_name: str,
) -> BaselineLift:
    """agent_hit - baseline_hit の平均差として lift を計算する。"""

    if len(agent_records) != len(baseline_records):
        raise ValueError("agent and baseline records must be trial-aligned")
    selected = [record for record in baseline_records if record.baseline_name == baseline_name]
    if len(selected) != len(baseline_records):
        raise ValueError("baseline_records contain a different baseline name")
    if any(record.hit is None for record in agent_records) or any(record.hit is None for record in baseline_records):
        raise ValueError("baseline_lift requires evaluated records")
    n_trials = len(agent_records)
    if n_trials == 0:
        return BaselineLift(baseline_name=baseline_name, lift=0.0, n_trials=0)
    lift = sum(int(agent.hit) - int(base.hit) for agent, base in zip(agent_records, baseline_records, strict=True)) / n_trials
    return BaselineLift(baseline_name=baseline_name, lift=lift, n_trials=n_trials)


def coordination_gain(categories_a: Sequence[PredictionCategory], categories_b: Sequence[PredictionCategory]) -> CoordinationGain:
    """試行整列済み出力カテゴリ一致から observed - chance を計算する。"""

    if len(categories_a) != len(categories_b):
        raise ValueError("category sequences must have equal length")
    n_trials = len(categories_a)
    if n_trials == 0:
        return CoordinationGain(observed_agreement=0.0, chance_agreement=0.0, coordination_gain=0.0, n_trials=0)
    observed = sum(1 for left, right in zip(categories_a, categories_b, strict=True) if left == right) / n_trials
    counts_a = Counter(categories_a)
    counts_b = Counter(categories_b)
    universe = sorted(set(counts_a) | set(counts_b), key=_category_sort_key)
    chance = sum((counts_a[category] / n_trials) * (counts_b[category] / n_trials) for category in universe)
    return CoordinationGain(
        observed_agreement=observed,
        chance_agreement=chance,
        coordination_gain=observed - chance,
        n_trials=n_trials,
    )


def _evaluate_prediction(
    prediction: Prediction,
    evaluator: object | None,
    scoring_key: ScoringKey | None,
) -> EvaluationResult | None:
    if scoring_key is None:
        return None
    selected = OracleEvaluator if evaluator is None else evaluator
    return selected(AgentOutput(prediction=prediction), scoring_key)  # type: ignore[operator]


def _prediction_content(prediction: Prediction) -> RelationContent | None:
    if isinstance(prediction, EdgePrediction):
        return _content(prediction.edge)
    if isinstance(prediction, Abstain):
        return None
    raise TypeError("unknown prediction variant")


def _coverage(prediction: Prediction) -> int:
    return int(isinstance(prediction, EdgePrediction))


def _content(relation: Relation) -> RelationContent:
    return (relation.predicate, tuple(relation.arguments))


def _relation_content_key(content: RelationContent) -> RelationContent:
    predicate, arguments = content
    return (str(predicate), tuple(str(argument) for argument in arguments))


def _visible_relations(agent_input: AgentInput) -> tuple[Relation, ...]:
    return tuple(agent_input.base_graph.relations) + tuple(agent_input.target_graph_partial.relations)


def _flat_matches(agent_input: AgentInput) -> tuple[FlatMatch, ...]:
    candidates: list[FlatMatch] = []
    for base_relation in sorted(agent_input.base_graph.relations, key=_relation_order):
        for partial_relation in sorted(agent_input.target_graph_partial.relations, key=_relation_order):
            if base_relation.predicate == partial_relation.predicate and len(base_relation.arguments) == len(partial_relation.arguments):
                candidates.append(FlatMatch(base_relation=base_relation, partial_relation=partial_relation))
    return tuple(candidates)


def _flat_entity_mapping(matches: Iterable[FlatMatch]) -> dict[str, str] | None:
    mapping: dict[str, str] = {}
    reverse: dict[str, str] = {}
    for match in matches:
        for left, right in zip(match.base_relation.arguments, match.partial_relation.arguments, strict=True):
            if left in mapping and mapping[left] != right:
                return None
            if right in reverse and reverse[right] != left:
                return None
            mapping[left] = right
            reverse[right] = left
    return dict(sorted(mapping.items()))


def _relation_order(relation: Relation) -> tuple[str, str, tuple[str, ...]]:
    return (relation.predicate, relation.relation_id, tuple(relation.arguments))


def _category_sort_key(category: PredictionCategory) -> tuple[str, str, tuple[str, ...]]:
    if category == ABSTAIN_CATEGORY:
        return ("0", ABSTAIN_CATEGORY, ())
    predicate, arguments = category  # type: ignore[misc]
    return ("1", str(predicate), tuple(str(argument) for argument in arguments))
