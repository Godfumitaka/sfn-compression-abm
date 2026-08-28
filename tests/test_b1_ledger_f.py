from __future__ import annotations

from hashlib import sha256
import json
import re
from time import perf_counter

import pytest

from abm.domains import AgentConfig, AgentState, CorrectionMode
from abm.ledger import LEDGER_FIELDS, RUN_INPUT_FIELDS, RunHeader, _code_commit
from abm.loop import _apply, _json_bytes, run_longitudinal
from abm.seed import DEFAULT_SEED_PATH, load_seed
from abm.world import generate_world


class MemoryLedger:
    def __init__(self): self.records = []
    def append(self, record): self.records.append(record)


def _run(mode="delta", counterfactuals=True, *, trials=60, snapshot_every=None):
    ledger = MemoryLedger()
    kwargs = {} if snapshot_every is None else {"snapshot_every": snapshot_every}
    run_longitudinal(generate_world(1, trials, ("agent",)), {"agent": AgentState()},
                     {"agent": AgentConfig(0.0, CorrectionMode.NONE, theta_prime=.1432)}, ledger,
                     snapshot_mode=mode, calculate_counterfactuals=counterfactuals, **kwargs)
    return ledger.records


def test_f1_f2_f3_header_and_reproducibility_inputs():
    seed = load_seed()
    header = RunHeader(.3,.2,.1,4.,"tower","removed","constant",.1,False,None,None,None,
                       1,60,("agent",),seed.file_sha256,"world",_code_commit(),.1432,.8,.5)
    assert len(header.to_dict()) == 21 and set(RUN_INPUT_FIELDS) <= set(header.to_dict())
    assert seed.file_sha256 == sha256(DEFAULT_SEED_PATH.read_bytes()).hexdigest() != seed.sha256
    assert _code_commit() == "unknown" or re.fullmatch(r"[0-9a-f]{40}", _code_commit())


def test_f4_f10_f11_f12_delta_round_trip_and_new_fields():
    state = None
    for record in _run():
        item = record["state_snapshot"]
        state = item["value"] if item["kind"] == "full" else _apply(state, item["changes"])
        assert sha256(_json_bytes(state)).hexdigest() == record["agent_state_snapshot_hash"]
        assert isinstance(record["tau_passed_defs"], list)
        selected = [x["R"] for x in record["tau_passed_defs"] if x["selected"]]
        if record["R_used"] is not None: assert selected == [record["R_used"]]
        assert len(record["counterfactual_predictions"]) == sum(not x["selected"] for x in record["tau_passed_defs"])


def test_f5_f6_f13_f14_f16_modes_purity_schema_and_determinism():
    delta, full, hash_only = _run(), _run("full"), _run("hash_only")
    hashes = lambda records: [r["agent_state_snapshot_hash"] for r in records]
    assert hashes(delta) == hashes(full) == hashes(hash_only) == hashes(_run(counterfactuals=False))
    assert all(r["state_snapshot"] is None for r in hash_only)
    assert len(LEDGER_FIELDS) == 89
    assert json.dumps(delta, sort_keys=True, default=str) == json.dumps(_run(), sort_keys=True, default=str)


def test_g1_snapshot_every_one_preserves_delta_jsonl():
    assert json.dumps(_run(), sort_keys=True, default=str) == json.dumps(
        _run(snapshot_every=1), sort_keys=True, default=str
    )


def test_g2_g3_g4_g5_sparse_delta_schedule_base_hash_and_round_trip():
    records = _run(snapshot_every=10)
    captured = [record for record in records if record["state_snapshot"]["kind"] != "skipped"]
    assert [record["prediction_order"] for record in captured] == [0, 10, 20, 30, 40, 50, 59]
    assert all(record["agent_state_snapshot_hash"] is not None for record in records)

    captured_hash = None
    state = None
    for record in records:
        item = record["state_snapshot"]
        if item["kind"] == "skipped":
            assert item == {"kind": "skipped", "base_hash": captured_hash}
            continue
        if item["kind"] == "delta":
            assert item["base_hash"] == captured_hash
        else:
            assert item["kind"] == "full"
        state = item["value"] if item["kind"] == "full" else _apply(state, item["changes"])
        captured_hash = record["agent_state_snapshot_hash"]
        assert sha256(_json_bytes(state)).hexdigest() == captured_hash


def test_g6_snapshot_every_does_not_change_state_hashes():
    hashes = [
        [record["agent_state_snapshot_hash"] for record in _run(trials=200, snapshot_every=every)]
        for every in (1, 5, 10)
    ]
    assert hashes[0] == hashes[1] == hashes[2]


@pytest.mark.parametrize("mode", ["full", "hash_only"])
def test_g7_non_delta_mode_rejects_snapshot_every(mode):
    with pytest.raises(ValueError):
        _run(mode, snapshot_every=10)


@pytest.mark.parametrize("snapshot_every", [0, -1])
def test_g8_non_positive_snapshot_every_is_rejected(snapshot_every):
    with pytest.raises(ValueError):
        _run(snapshot_every=snapshot_every)


def test_g9_g10_sparse_delta_is_faster_and_at_most_one_third_the_size():
    started = perf_counter()
    every_one = _run(trials=400, snapshot_every=1)
    every_one_seconds = perf_counter() - started
    started = perf_counter()
    every_ten = _run(trials=400, snapshot_every=10)
    every_ten_seconds = perf_counter() - started

    every_one_size = len(json.dumps(every_one, sort_keys=True, default=str).encode())
    every_ten_size = len(json.dumps(every_ten, sort_keys=True, default=str).encode())
    assert every_ten_seconds < every_one_seconds
    assert every_ten_size <= every_one_size / 3
