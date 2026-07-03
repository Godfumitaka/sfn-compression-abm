"""BUILD ORDER 第11a段の最小 smoke harness。

isomorphic と anti_analogy だけを、2 seed × 2 operator の固定順で直接実行する。
Stage 10 の ecology schedule は使わず、単一 agent の wiring 穴を露出させる。
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable, Mapping
from typing import Literal

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
from abm.perturbations import PerturbationOperator, PerturbationParams, anti_analogy, isomorphic, role_divergence as _role_divergence
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
    prototype_prior_weight: float = 0.0


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


RoleDivergenceArm = Literal["prototype_absent", "prototype_present"]


@dataclass(frozen=True, slots=True)
class RoleDivergenceSmokeConfig:
    seed_name: str
    threshold: float = 0.0
    sme_params: SMEParams | None = None
    mdl_params: MDLParams | None = None
    perturbation_params: PerturbationParams = PerturbationParams(instance_id="stage_11b_role_divergence_smoke")
    trial_id_prefix: str | None = None
    prototype_prior_weight: float = 0.0


@dataclass(frozen=True, slots=True)
class RoleDivergenceArmResult:
    arm: RoleDivergenceArm
    seed_name: str
    preparation_trial: SmokeTrialResult | None
    role_divergence_trial: SmokeTrialResult
    prototype_present_at_presentation: bool
    prototype_inert: bool
    notes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RoleDivergenceArmDifference:
    hit_delta: int
    coverage_delta: int
    description_length_delta: float
    sme_total_score_delta: float


@dataclass(frozen=True, slots=True)
class RoleDivergenceSmokeResult:
    seed_name: str
    absent_arm: RoleDivergenceArmResult
    present_arm: RoleDivergenceArmResult
    arm_difference: RoleDivergenceArmDifference


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


def run_role_divergence_smoke_trial(
    config: RoleDivergenceSmokeConfig,
    *,
    trial_id: str | None = None,
    use_prototype: bool = False,
) -> SmokeTrialResult:
    """role_divergence 専用の単発 smoke trial を SME 経路だけで実行する。

    Stage 11a の `run_smoke_trial()` は意図的に role_divergence を受け付けないため、
    Stage 11b は専用入口を使う。AgentState.prototype は現在の SME 予測経路に
    接続されていないので、ここでも prototype を写像・MDL・threshold に注入しない。
    """

    return _run_trial(
        seed_name=config.seed_name,
        operator_name="role_divergence",
        operator=_role_divergence,
        threshold=config.threshold,
        sme_params=config.sme_params,
        mdl_params=config.mdl_params,
        perturbation_params=config.perturbation_params,
        trial_id=trial_id or _stage_11b_trial_id(config, "prototype_absent", "role_divergence"),
        prototype_prior_weight=config.prototype_prior_weight if use_prototype else 0.0,
        use_prototype=use_prototype,
    )


def run_role_divergence_two_arm_smoke(config: RoleDivergenceSmokeConfig) -> RoleDivergenceSmokeResult:
    """role_divergence の prototype_absent / prototype_present 二腕を固定順で実行する。

    実行順は absent role_divergence → present isomorphic preparation → present
    role_divergence。準備と role_divergence の間に他 operator や ecology schedule は挟まない。
    現在の予測配線は map_graphs→apply_threshold→project であり prototype を読まないため、
    present 腕は「準備が直前にあった」ことだけを記録し、効果は偽装しない。
    """

    prefix = config.trial_id_prefix or f"stage_11b::{config.seed_name}"
    absent_trial = run_role_divergence_smoke_trial(
        config, trial_id=f"{prefix}::prototype_absent::role_divergence"
    )
    preparation_trial = _run_trial(
        seed_name=config.seed_name,
        operator_name="isomorphic",
        operator=isomorphic,
        threshold=config.threshold,
        sme_params=config.sme_params,
        mdl_params=config.mdl_params,
        perturbation_params=config.perturbation_params,
        trial_id=f"{prefix}::prototype_present::isomorphic_preparation",
        prototype_prior_weight=config.prototype_prior_weight,
        use_prototype=True,
    )
    present_trial = run_role_divergence_smoke_trial(
        config,
        trial_id=f"{prefix}::prototype_present::role_divergence",
        use_prototype=True,
    )
    inert_note = (
        "prototype-to-prediction path remains inert unless prototype_prior_weight "
        "is configured positive"
    )
    absent_arm = RoleDivergenceArmResult(
        arm="prototype_absent",
        seed_name=config.seed_name,
        preparation_trial=None,
        role_divergence_trial=absent_trial,
        prototype_present_at_presentation=False,
        prototype_inert=True,
        notes=(inert_note,),
    )
    present_arm = RoleDivergenceArmResult(
        arm="prototype_present",
        seed_name=config.seed_name,
        preparation_trial=preparation_trial,
        role_divergence_trial=present_trial,
        prototype_present_at_presentation=True,
        prototype_inert=True,
        notes=(
            "isomorphic preparation immediately precedes role_divergence",
            inert_note,
        ),
    )
    return RoleDivergenceSmokeResult(
        seed_name=config.seed_name,
        absent_arm=absent_arm,
        present_arm=present_arm,
        arm_difference=_arm_difference(absent_trial, present_trial),
    )


def run_minimal_role_divergence_smoke_suite(
    *,
    threshold: float = 0.0,
    sme_params: SMEParams | None = None,
    mdl_params: MDLParams | None = None,
    perturbation_params: PerturbationParams | None = None,
    prototype_prior_weight: float = 0.0,
) -> tuple[RoleDivergenceSmokeResult, ...]:
    """既存 2 seed だけで Stage 11b 二腕 smoke を固定順に実行する。"""

    params = perturbation_params or PerturbationParams(instance_id="stage_11b_role_divergence_smoke")
    return tuple(
        run_role_divergence_two_arm_smoke(
            RoleDivergenceSmokeConfig(
                seed_name=seed_name,
                threshold=threshold,
                sme_params=sme_params,
                mdl_params=mdl_params,
                perturbation_params=params,
                prototype_prior_weight=prototype_prior_weight,
            )
        )
        for seed_name in _SEEDS
    )


def run_smoke_trial(config: SmokeTrialConfig) -> SmokeTrialResult:
    """1 seed × 1 operator を oracle-free な map→threshold→project→MDL で実行する。"""

    return _run_trial(
        seed_name=config.seed_name,
        operator_name=config.operator_name,
        operator=_operator(config.operator_name),
        threshold=config.threshold,
        sme_params=config.sme_params,
        mdl_params=config.mdl_params,
        perturbation_params=config.perturbation_params,
        trial_id=config.trial_id or _trial_id(config.seed_name, config.operator_name),
    )


def run_minimal_smoke_suite(
    *,
    threshold: float = 0.0,
    sme_params: SMEParams | None = None,
    mdl_params: MDLParams | None = None,
    perturbation_params: PerturbationParams | None = None,
    prototype_prior_weight: float = 0.0,
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
                prototype_prior_weight=prototype_prior_weight,
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


def _run_trial(
    *,
    seed_name: str,
    operator_name: str,
    operator: PerturbationOperator,
    threshold: float,
    sme_params: SMEParams | None,
    mdl_params: MDLParams | None,
    perturbation_params: PerturbationParams,
    trial_id: str,
    prototype_prior_weight: float = 0.0,
    use_prototype: bool = False,
) -> SmokeTrialResult:
    seed_constructor = _seed_constructor(seed_name)
    perturbation = operator(seed_constructor(), perturbation_params)
    agent_input = perturbation.agent_input
    scoring_key = ScoringKey(held_out_edge=perturbation.oracle_view.held_out_edge)

    prototype = seed_constructor().target_graph if use_prototype else None
    mapping_result = map_graphs(
        agent_input.base_graph,
        agent_input.target_graph_partial,
        sme_params,
        prototype=prototype,
        prototype_prior_weight=prototype_prior_weight,
    )
    decision = apply_threshold(mapping_result, threshold)
    if decision.accepted:
        prediction = project(
            mapping_result.alignment,
            agent_input.base_graph,
            agent_input.target_graph_partial,
            prototype_prior_weight=prototype_prior_weight,
        )
    else:
        prediction = Abstain(reason="below_threshold")
    mdl_result = description_length(agent_input, mapping_result, mdl_params)

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
        trial_id=trial_id,
        seed_name=seed_name,
        operator_name=operator_name,
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


def _stage_11b_trial_id(config: RoleDivergenceSmokeConfig, arm: RoleDivergenceArm, operator_name: str) -> str:
    prefix = config.trial_id_prefix or f"stage_11b::{config.seed_name}"
    return f"{prefix}::{arm}::{operator_name}"


def _arm_difference(absent: SmokeTrialResult, present: SmokeTrialResult) -> RoleDivergenceArmDifference:
    return RoleDivergenceArmDifference(
        hit_delta=present.hit - absent.hit,
        coverage_delta=present.coverage - absent.coverage,
        description_length_delta=present.description_length - absent.description_length,
        sme_total_score_delta=present.sme_total_score - absent.sme_total_score,
    )


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
