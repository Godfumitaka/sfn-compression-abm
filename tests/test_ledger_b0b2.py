from __future__ import annotations

import json

import pytest

from abm.ledger import (
    ARM_DESCRIPTOR_FIELDS,
    D23_FIELDS,
    LEDGER_FIELDS,
    MECHANISM_FIELDS,
    RESEARCH_FIELDS,
    RUN_INPUT_FIELDS,
    Ledger,
    RunHeader,
    empty_record,
)
from abm.logging_schema import LOGGING_SCHEMA_FIELDS


def _header() -> RunHeader:
    return RunHeader(
        0.3, 0.2, 0.1, 4.0, "tower", "removed", "constant",
        0.1, False, None, None, None,
        1, 2, ("agent",), "seed", "world", "commit", 0.1, 0.8, 0.5,
    )


def _record(trial: int) -> dict:
    return empty_record(
        run_id="run",
        prediction_order=trial,
        exception_bits_charged=[],
        constituent_reason_123={},
        oracle_verdict="保留",
        m_live=4,
        support_at_adoption=0.0,
    )


def test_ledger_field_accounting_is_38_22_24_8_minus_three() -> None:
    assert len(LOGGING_SCHEMA_FIELDS) == 38
    assert len(D23_FIELDS) == 26
    assert len(MECHANISM_FIELDS) == 24
    assert len(RESEARCH_FIELDS) == 8
    assert len(LEDGER_FIELDS) == 93
    assert len(ARM_DESCRIPTOR_FIELDS) == 13
    assert LEDGER_FIELDS.count("agent_state_snapshot_hash") == 1
    assert LEDGER_FIELDS.count("abstain_reason") == 1


def test_ledger_writes_one_header_and_one_line_per_trial(tmp_path) -> None:
    path = tmp_path / "ledger.jsonl"
    with Ledger(path, _header()) as ledger:
        ledger.append(_record(0))
        ledger.append(_record(1))

    lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 3
    assert lines[0]["record_type"] == "run_header"
    assert set(lines[0]) == {"record_type", *ARM_DESCRIPTOR_FIELDS, *RUN_INPUT_FIELDS}
    assert [line["record_type"] for line in lines[1:]] == ["trial", "trial"]
    assert all(set(line) == {"record_type", *LEDGER_FIELDS} for line in lines[1:])


def test_ledger_rejects_missing_and_null_required_fields(tmp_path) -> None:
    path = tmp_path / "ledger.jsonl"
    with Ledger(path, _header()) as ledger:
        missing = _record(0)
        missing.pop("scene_G_star_ref")
        with pytest.raises(ValueError, match="missing"):
            ledger.append(missing)
        with pytest.raises(ValueError, match="non-null"):
            ledger.append(empty_record())


def test_ledger_is_new_file_append_only_and_has_no_read_api(tmp_path) -> None:
    path = tmp_path / "ledger.jsonl"
    with Ledger(path, _header()):
        pass

    with pytest.raises(FileExistsError):
        Ledger(path, _header())
    assert not hasattr(Ledger, "read")
