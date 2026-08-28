from __future__ import annotations

from hashlib import sha256
import json
import re

from abm.domains import AgentConfig, AgentState, CorrectionMode
from abm.ledger import LEDGER_FIELDS, RUN_INPUT_FIELDS, RunHeader, _code_commit
from abm.loop import _apply, _json_bytes, run_longitudinal
from abm.seed import DEFAULT_SEED_PATH, load_seed
from abm.world import generate_world


class MemoryLedger:
    def __init__(self): self.records = []
    def append(self, record): self.records.append(record)


def _run(mode="delta", counterfactuals=True):
    ledger = MemoryLedger()
    run_longitudinal(generate_world(1, 60, ("agent",)), {"agent": AgentState()},
                     {"agent": AgentConfig(0.0, CorrectionMode.NONE, theta_prime=.1432)}, ledger,
                     snapshot_mode=mode, calculate_counterfactuals=counterfactuals)
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
