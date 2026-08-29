"""`registration_event.base_written_at` の記録に関する試験。

`base_written_at` は m1 の base に選ばれた枚（verbatim）の書込試行である。
段階2 の「そのパターン」を候補 a1（base に選ばれた枚）で読む場合に必要で、
台帳から復元できない量なので走行前に記録する（D23：後付け不可）。
"""

import math

import pytest

from abm.domains import AgentConfig, AgentState, CorrectionMode, RepairScope
from abm.ledger import LEDGER_FIELDS
from abm.loop import run_longitudinal
from abm.world import generate_world

THETA_PRIMES = (0.0410, 0.1432, 0.2637, 0.3842)
TRIAL_COUNT = 150
RUN_SEED = 1


class _Memory:
    def __init__(self) -> None:
        self.records: list[dict] = []

    def append(self, record: dict) -> None:
        self.records.append(record)


_CACHE: dict[float, list[dict]] = {}


def _registration_events(theta_prime: float) -> list[dict]:
    if theta_prime not in _CACHE:
        memory = _Memory()
        run_longitudinal(
            generate_world(RUN_SEED, TRIAL_COUNT, ("agent",)),
            {"agent": AgentState()},
            {"agent": AgentConfig(0.0, CorrectionMode.NONE, theta_prime=theta_prime,
                                  repair_scope=RepairScope.ALL)},
            memory,
            snapshot_mode="hash_only",
        )
        _CACHE[theta_prime] = [
            record["registration_event"]
            for record in memory.records
            if record.get("registration_event")
        ]
    return _CACHE[theta_prime]


@pytest.mark.parametrize("theta_prime", THETA_PRIMES)
def test_every_registration_event_carries_base_written_at(theta_prime: float) -> None:
    events = _registration_events(theta_prime)
    assert events, "登録イベントが一件も出ていない"
    assert all("base_written_at" in event for event in events)
    assert all(isinstance(event["base_written_at"], int) for event in events)


@pytest.mark.parametrize("theta_prime", THETA_PRIMES)
def test_base_is_strictly_older_than_the_event_trial(theta_prime: float) -> None:
    """base は必ず過去の枚である。現在試行の枚は predict の時点でまだ書かれていない。"""
    for event in _registration_events(theta_prime):
        assert event["trial"] - event["base_written_at"] >= 1


@pytest.mark.parametrize("theta_prime", THETA_PRIMES)
def test_base_lies_within_the_verbatim_lifetime(theta_prime: float) -> None:
    """上限は floor(1/θ′²) + 1。

    枚は経過 <= 1/θ′² のあいだ生存する。predict は apply_theta より前に走るので、
    base は削除の一巡ぶん古くなりうる。上限を floor(1/θ′²) にすると誤って落ちる。
    """
    bound = math.floor(theta_prime ** -2) + 1
    for event in _registration_events(theta_prime):
        assert event["trial"] - event["base_written_at"] <= bound


def test_base_written_at_is_nested_and_does_not_add_a_ledger_column() -> None:
    """最上位欄ではない。台帳の欄数は変わらない。"""
    assert "base_written_at" not in LEDGER_FIELDS
    assert "registration_event" in LEDGER_FIELDS
