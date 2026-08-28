"""委任C: 構成素の行同一性を三つ組キーで保持する受け入れ試験。"""

from __future__ import annotations

from collections import defaultdict
import json

import pytest

from abm.domains import AgentConfig, AgentState, CorrectionMode
from abm.ledger import LEDGER_FIELDS
from abm.loop import run_longitudinal
from abm.world import generate_world


class MemoryLedger:
    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []

    def append(self, record: dict[str, object]) -> None:
        self.records.append(record)


def _run(trials: int, *, snapshot_mode: str = "delta", snapshot_every: int = 1):
    ledger = MemoryLedger()
    result = run_longitudinal(
        generate_world(1, trials, ("agent",)),
        {"agent": AgentState()},
        {
            "agent": AgentConfig(
                threshold=0.0,
                correction_mode=CorrectionMode.NONE,
                theta_prime=0.1432,
            )
        },
        ledger,
        snapshot_mode=snapshot_mode,
        snapshot_every=snapshot_every,
    )
    return result.states["agent"], ledger.records


@pytest.fixture(scope="module")
def state_100():
    return _run(100)[0]


@pytest.fixture(scope="module")
def state_400():
    return _run(400)[0]


def test_h1_all_three_maps_use_typed_triple_keys(state_100: AgentState) -> None:
    for mapping in (state_100.merit, state_100.embed, state_100.slot_history):
        assert mapping
        assert all(
            len(key) == 3
            and isinstance(key[0], str)
            and isinstance(key[1], int)
            and isinstance(key[2], int)
            for key in mapping
        )


def test_h2_duplicate_live_slots_have_independent_accumulators(state_400: AgentState) -> None:
    groups = defaultdict(list)
    for name, definition in state_400.definitions.items():
        for row in definition.constituents:
            if row.alive:
                groups[(name, row.slot_index)].append(row)
    duplicates = [(pair, rows) for pair, rows in groups.items() if len(rows) > 1]
    assert duplicates
    for (name, _), rows in duplicates:
        accumulators = [
            state_400.merit[(name, row.slot_index, row.registered_at)]
            for row in rows
        ]
        assert len({row.registered_at for row in rows}) == len(rows)
        assert len({id(accumulator) for accumulator in accumulators}) == len(accumulators)


def test_h3_tombstones_do_not_collide_with_reused_rows(state_400: AgentState) -> None:
    groups = defaultdict(list)
    for name, definition in state_400.definitions.items():
        for row in definition.constituents:
            groups[(name, row.slot_index)].append(row)
    reused = [
        (pair, rows)
        for pair, rows in groups.items()
        if len(rows) > 1 and any(not row.alive for row in rows)
    ]
    assert reused
    for (name, slot_index), rows in reused:
        keys = {(name, slot_index, row.registered_at) for row in rows}
        assert len(keys) == len(rows)
        assert keys <= set(state_400.merit)


def test_h4_h5_constituent_state_schema_and_ledger_width() -> None:
    _, records = _run(20)
    expected = {"R", "slot_index", "registered_at", "alive", "S_q", "ext_use_count", "embed"}
    rows = [row for record in records for row in record["constituent_states"]]
    assert rows
    assert all(set(row) == expected for row in rows)
    assert len(LEDGER_FIELDS) == 89


def test_h7_same_input_produces_identical_ledger() -> None:
    first = _run(40)[1]
    second = _run(40)[1]
    assert json.dumps(first, sort_keys=True, default=str) == json.dumps(second, sort_keys=True, default=str)


def test_h8_snapshot_settings_do_not_change_state_hashes() -> None:
    records = (
        _run(40, snapshot_every=1)[1],
        _run(40, snapshot_every=10)[1],
        _run(40, snapshot_mode="hash_only")[1],
    )
    hashes = [[record["agent_state_snapshot_hash"] for record in run] for run in records]
    assert hashes[0] == hashes[1] == hashes[2]
