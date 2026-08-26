"""SPEC B0+B2 §B.9 の書き込み専用 JSONL 台帳。"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any, Mapping

from abm.logging_schema import LOGGING_SCHEMA_FIELDS


D23_FIELDS = (
    "coin_t", "f_realized", "f_fired", "feedback_content", "held_out_content",
    "expansion_and_filling_all", "constituent_reason_123", "type2_fired",
    "predictions_all_slots", "oracle_verdict", "registration_event", "deletion_event",
    "deletion_ell", "tie_event", "dangling_ref_onset", "dangling_ref_duration", "R_used",
    "def_R_diff", "agent_state_snapshot_hash", "state_snapshot", "transmission_event", "scene_G_star_ref",
)
MECHANISM_FIELDS = (
    "m_alloc", "m_live", "theta_prime", "tau", "constituent_states", "entity_map_covered",
    "slot_history_size", "filled_predicate", "slot_signature", "support_at_adoption",
    "charge_source", "verbatim_written", "reg_del_events", "exception_bits_charged",
    "M051_balance", "matcher", "abstain_reason", "n_tie_candidates", "candidate_distribution",
    "enumeration_version", "V_vocab", "merit_event_times", "outcome_category",
)
RESEARCH_FIELDS = ("p1", "p0", "Sel", "OA", "f_realized")
ARM_DESCRIPTOR_FIELDS = (
    "arm_alpha", "arm_beta", "arm_w", "arm_kappa", "arm_repair_scope",
    "arm_holdout_repr", "arm_f_profile",
    "arm_lambda_mix", "arm_abstain_charge", "arm_temperature", "arm_d_shared",
    "arm_adaptation_table",
)
NON_NULL_FIELDS = frozenset(
    ("exception_bits_charged", "constituent_reason_123", "oracle_verdict", "m_live", "support_at_adoption")
)


def _unique_fields(*groups: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(field for group in groups for field in group))


LEDGER_FIELDS = _unique_fields(
    LOGGING_SCHEMA_FIELDS, D23_FIELDS, MECHANISM_FIELDS, RESEARCH_FIELDS
)
if len(LOGGING_SCHEMA_FIELDS) != 38:
    raise RuntimeError(f"層A台帳欄は38本ではない: {len(LOGGING_SCHEMA_FIELDS)}")
if len(LEDGER_FIELDS) != 85:
    raise RuntimeError(
        "台帳欄は85本ではない: "
        f"A={len(LOGGING_SCHEMA_FIELDS)}, D23={len(D23_FIELDS)}, "
        f"mechanism={len(MECHANISM_FIELDS)}, "
        f"research={len(RESEARCH_FIELDS)}, unique={len(LEDGER_FIELDS)}"
    )
if len(ARM_DESCRIPTOR_FIELDS) != 12:
    raise RuntimeError(f"腕記述子は12本ではない: {len(ARM_DESCRIPTOR_FIELDS)}")


@dataclass(frozen=True, slots=True)
class RunHeader:
    arm_alpha: float
    arm_beta: float
    arm_w: float
    arm_kappa: float
    arm_repair_scope: str
    arm_holdout_repr: str
    arm_f_profile: str
    arm_lambda_mix: float
    arm_abstain_charge: bool
    arm_temperature: float | None
    arm_d_shared: float | None
    arm_adaptation_table: str | None

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in ARM_DESCRIPTOR_FIELDS}


class Ledger:
    """新規台帳を作り、runヘッダと試行行を同期追記する。"""

    def __init__(self, path: str | Path, header: RunHeader) -> None:
        self._path = Path(path)
        self._stream = self._path.open("x", encoding="utf-8")
        self._write_line({"record_type": "run_header", **header.to_dict()})

    def append(self, record: Mapping[str, Any]) -> None:
        keys = frozenset(record)
        expected = frozenset(LEDGER_FIELDS)
        if keys != expected:
            missing = sorted(expected - keys)
            extra = sorted(keys - expected)
            raise ValueError(f"台帳欄が不一致: missing={missing}, extra={extra}")
        null_fields = sorted(field for field in NON_NULL_FIELDS if record[field] is None)
        if null_fields:
            raise ValueError(f"毎試行 non-null 欄が null: {null_fields}")
        self._write_line({"record_type": "trial", **record})

    def close(self) -> None:
        if not self._stream.closed:
            self._stream.close()

    def __enter__(self) -> "Ledger":
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.close()

    def _write_line(self, value: Mapping[str, Any]) -> None:
        self._stream.write(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n")
        self._stream.flush()
        os.fsync(self._stream.fileno())


def empty_record(**values: Any) -> dict[str, Any]:
    """B1未実装欄を null で立て、与えられた同期値を入れる。"""

    unknown = sorted(set(values) - set(LEDGER_FIELDS))
    if unknown:
        raise ValueError(f"未知の台帳欄: {unknown}")
    return {field: values.get(field) for field in LEDGER_FIELDS}
