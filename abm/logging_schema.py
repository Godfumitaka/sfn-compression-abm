"""SPEC §10 のJSONLログ形状。

ログは評価側の記録であり、エージェント側DTOには混ぜない。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from abm.domains import CorrectionMode, SendingPolicy, TargetType


LOGGING_SCHEMA_FIELDS: tuple[str, ...] = (
    "run_id",
    "agent_id",
    "partner_id",
    "timestamp",
    "prediction_order",
    "seed_id",
    "target_type",
    "constitution",
    "threshold",
    "lambda",
    "correction_mode",
    "error_correlation",
    "sending_policy",
    "agent_state_snapshot_hash",
    "prototype_version",
    "prototype_present_at_presentation",
    "instance_id",
    "observable_mask_edges",
    "prediction_kind",
    "predicted_edge",
    "abstain_reason",
    "hit",
    "coverage",
    "frequency_baseline_prediction",
    "frequency_baseline_hit",
    "flat_matcher_baseline_prediction",
    "flat_matcher_baseline_hit",
    "accuracy",
    "L_H",
    "L_DgH",
    "description_length",
    "coordination_gain",
    "error_agreement",
    "alignment_candidates",
    "pruning_events",
    "activated_prototype",
    "total_score_breakdown",
    "error_direction_prototype_consistent",
)


@dataclass(frozen=True, slots=True)
class LogRecord:
    run_id: str
    agent_id: str
    partner_id: str | None
    timestamp: str
    prediction_order: int
    seed_id: str
    target_type: TargetType
    constitution: str
    threshold: float
    lambda_: float
    correction_mode: CorrectionMode
    error_correlation: float
    sending_policy: SendingPolicy
    agent_state_snapshot_hash: str
    prototype_version: str | None
    prototype_present_at_presentation: bool
    instance_id: str
    observable_mask_edges: tuple[str, ...]
    prediction_kind: str
    predicted_edge: str | None
    abstain_reason: str | None
    hit: int
    coverage: int
    frequency_baseline_prediction: str | None
    frequency_baseline_hit: int
    flat_matcher_baseline_prediction: str | None
    flat_matcher_baseline_hit: int
    accuracy: float
    L_H: float
    L_DgH: float
    description_length: float
    coordination_gain: float | None
    error_agreement: float | None
    alignment_candidates: tuple[dict[str, Any], ...] = ()
    pruning_events: tuple[dict[str, Any], ...] = ()
    activated_prototype: str | None = None
    total_score_breakdown: dict[str, Any] = field(default_factory=dict)
    error_direction_prototype_consistent: bool | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "observable_mask_edges", tuple(self.observable_mask_edges))
        object.__setattr__(self, "alignment_candidates", tuple(self.alignment_candidates))
        object.__setattr__(self, "pruning_events", tuple(self.pruning_events))
        object.__setattr__(self, "total_score_breakdown", dict(self.total_score_breakdown))

    def to_jsonl_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "agent_id": self.agent_id,
            "partner_id": self.partner_id,
            "timestamp": self.timestamp,
            "prediction_order": self.prediction_order,
            "seed_id": self.seed_id,
            "target_type": self.target_type.value,
            "constitution": self.constitution,
            "threshold": self.threshold,
            "lambda": self.lambda_,
            "correction_mode": self.correction_mode.value,
            "error_correlation": self.error_correlation,
            "sending_policy": self.sending_policy.value,
            "agent_state_snapshot_hash": self.agent_state_snapshot_hash,
            "prototype_version": self.prototype_version,
            "prototype_present_at_presentation": self.prototype_present_at_presentation,
            "instance_id": self.instance_id,
            "observable_mask_edges": list(self.observable_mask_edges),
            "prediction_kind": self.prediction_kind,
            "predicted_edge": self.predicted_edge,
            "abstain_reason": self.abstain_reason,
            "hit": self.hit,
            "coverage": self.coverage,
            "frequency_baseline_prediction": self.frequency_baseline_prediction,
            "frequency_baseline_hit": self.frequency_baseline_hit,
            "flat_matcher_baseline_prediction": self.flat_matcher_baseline_prediction,
            "flat_matcher_baseline_hit": self.flat_matcher_baseline_hit,
            "accuracy": self.accuracy,
            "L_H": self.L_H,
            "L_DgH": self.L_DgH,
            "description_length": self.description_length,
            "coordination_gain": self.coordination_gain,
            "error_agreement": self.error_agreement,
            "alignment_candidates": list(self.alignment_candidates),
            "pruning_events": list(self.pruning_events),
            "activated_prototype": self.activated_prototype,
            "total_score_breakdown": dict(self.total_score_breakdown),
            "error_direction_prototype_consistent": self.error_direction_prototype_consistent,
        }
