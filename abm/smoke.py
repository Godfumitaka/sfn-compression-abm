"""BUILD ORDER 第11a段の最小 smoke harness。

isomorphic と anti_analogy だけを、2 seed × 2 operator の固定順で直接実行する。
Stage 10 の ecology schedule は使わず、単一 agent の wiring 穴を露出させる。
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable, Mapping

from abm.domains import Abstain, AgentOutput, ScoringKey
from abm.gains import (
    BaselineLift,
    BaselineTrialRecord,
    FLAT_MATCHER_BASELINE,
    FREQUENCY_BASELINE,
    TransferMetrics,
    TrialPredictionRecord,
    baseline_lift,
    baseline_record,
    flat_matcher_baseline,
    frequency_baseline,
    prediction_record,
    transfer_metrics,
)
from abm.mdl import MDLParams, description_length
from abm.perturbations import PerturbationOperator, PerturbationParams, anti_analogy, isomorphic
from abm.roles import OracleEvaluator
from abm.seeds import SeedGraphs, solar_system_atom, water_heat_flow
from abm.sme import SMEParams, apply_threshold, map_graphs, project


@dataclass(frozen=True, slots=True)
class SmokeTrialConfig:
    seed_name: str
    operator_name: str
    threshold: float = 0.0
    sme_params: SMEParams | None = None
    mdl_params: MDLParams | None = None
    perturbation_params: PerturbationParams = PerturbationParams(instance_id="stage_11a_smoke")
    trial_id: str | None = None


@dataclass(frozen=True, slots=True)
class SmokeTrialResult:
    trial_id: str
    seed_name: str
    operator_name: str
    prediction_kind: str
    prediction_category: object
    hit: int
    coverage: int
    description_length: float
    sme_total_score: float
    abstain_reason: str | None = None
    frequency_baseline_record: BaselineTrialRecord | None = None
    flat_matcher_baseline_record: BaselineTrialRecord | None = None


@dataclass(frozen=True, slots=True)
class SmokeSuiteResult:
    results: tuple[SmokeTrialResult, ...]
    transfer_metrics: TransferMetrics
    frequency_lift: BaselineLift | None = None
    flat_matcher_lift: BaselineLift | None = None


_SEEDS: Mapping[str, Callable[[], SeedGraphs]] = {
    "solar_system_atom": solar_system_atom,
    "water_heat_flow": water_heat_flow,
}
_OPERATORS: Mapping[str, PerturbationOperator] = {
    "isomorphic": isomorphic,
    "anti_analogy": anti_analogy,
}
_TRIAL_ORDER: tuple[tuple[str, str], ...] = (
    ("solar_system_atom", "isomorphic"),
    ("solar_system_atom", "anti_analogy"),
    ("water_heat_flow", "isomorphic"),
    ("water_heat_flow", "anti_analogy"),
)


def run_smoke_trial(config: SmokeTrialConfig) -> SmokeTrialResult:
    """1 seed × 1 operator を oracle-free な map→threshold→project→MDL で実行する。"""

    seed_constructor = _seed_constructor(config.seed_name)
    operator = _operator(config.operator_name)
    perturbation = operator(seed_constructor(), config.perturbation_params)
    agent_input = perturbation.agent_input
    scoring_key = ScoringKey(held_out_edge=perturbation.oracle_view.held_out_edge)

    mapping_result = map_graphs(agent_input.base_graph, agent_input.target_graph_partial, config.sme_params)
    decision = apply_threshold(mapping_result, config.threshold)
    if decision.accepted:
        prediction = project(mapping_result.alignment, agent_input.base_graph, agent_input.target_graph_partial)
    else:
        prediction = Abstain(reason="below_threshold")
    mdl_result = description_length(agent_input, mapping_result, config.mdl_params)

    record = prediction_record(prediction, evaluator=OracleEvaluator, scoring_key=scoring_key)
    frequency_prediction = frequency_baseline(agent_input)
    frequency_record = baseline_record(
        FREQUENCY_BASELINE,
        frequency_prediction,
        evaluator=OracleEvaluator,
        scoring_key=scoring_key,
    )
    flat_prediction = flat_matcher_baseline(agent_input)
    flat_record = baseline_record(
        FLAT_MATCHER_BASELINE,
        flat_prediction,
        evaluator=OracleEvaluator,
        scoring_key=scoring_key,
    )

    return SmokeTrialResult(
        trial_id=config.trial_id or _trial_id(config.seed_name, config.operator_name),
        seed_name=config.seed_name,
        operator_name=config.operator_name,
        prediction_kind=record.prediction_kind,
        prediction_category=record.prediction_category,
        hit=int(record.hit),
        coverage=record.coverage,
        description_length=mdl_result.description_length.total,
        sme_total_score=mapping_result.alignment.total_score,
        abstain_reason=record.abstain_reason,
        frequency_baseline_record=frequency_record,
        flat_matcher_baseline_record=flat_record,
    )


def run_minimal_smoke_suite(
    *,
    threshold: float = 0.0,
    sme_params: SMEParams | None = None,
    mdl_params: MDLParams | None = None,
    perturbation_params: PerturbationParams | None = None,
) -> SmokeSuiteResult:
    """Stage 11a の固定 2 seeds × 2 operators suite だけを実行する。"""

    params = perturbation_params or PerturbationParams(instance_id="stage_11a_smoke")
    results = tuple(
        run_smoke_trial(
            SmokeTrialConfig(
                seed_name=seed_name,
                operator_name=operator_name,
                threshold=threshold,
                sme_params=sme_params,
                mdl_params=mdl_params,
                perturbation_params=params,
                trial_id=_trial_id(seed_name, operator_name),
            )
        )
        for seed_name, operator_name in _TRIAL_ORDER
    )
    records = tuple(_trial_record(result) for result in results)
    frequency_records = tuple(result.frequency_baseline_record for result in results if result.frequency_baseline_record is not None)
    flat_records = tuple(result.flat_matcher_baseline_record for result in results if result.flat_matcher_baseline_record is not None)
    return SmokeSuiteResult(
        results=results,
        transfer_metrics=transfer_metrics(records),
        frequency_lift=baseline_lift(records, frequency_records, FREQUENCY_BASELINE) if len(frequency_records) == len(results) else None,
        flat_matcher_lift=baseline_lift(records, flat_records, FLAT_MATCHER_BASELINE) if len(flat_records) == len(results) else None,
    )


def summarize_smoke_suite(result: SmokeSuiteResult) -> Mapping[str, float | int | None]:
    """最小 smoke 結果の集計値だけを返す。"""

    return {
        "n_trials": result.transfer_metrics.n_trials,
        "transfer_accuracy": result.transfer_metrics.accuracy,
        "coverage": result.transfer_metrics.coverage,
        "selective_accuracy": result.transfer_metrics.selective_accuracy,
        "frequency_lift": None if result.frequency_lift is None else result.frequency_lift.lift,
        "flat_matcher_lift": None if result.flat_matcher_lift is None else result.flat_matcher_lift.lift,
    }


def _seed_constructor(seed_name: str) -> Callable[[], SeedGraphs]:
    try:
        return _SEEDS[seed_name]
    except KeyError as exc:
        raise ValueError(f"unsupported Stage 11a seed: {seed_name}") from exc


def _operator(operator_name: str) -> PerturbationOperator:
    try:
        return _OPERATORS[operator_name]
    except KeyError as exc:
        raise ValueError(f"unsupported Stage 11a operator: {operator_name}") from exc


def _trial_id(seed_name: str, operator_name: str) -> str:
    return f"stage_11a::{seed_name}::{operator_name}"


def _trial_record(result: SmokeTrialResult) -> TrialPredictionRecord:
    return TrialPredictionRecord(
        prediction_category=result.prediction_category,
        prediction_kind=result.prediction_kind,
        predicted_relation_content=None,
        abstain_reason=result.abstain_reason,
        hit=result.hit,
        coverage=result.coverage,
    )
