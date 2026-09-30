"""記録用の計算が選択の対応・乱数・記録を変えないことを検査する。"""
import sys
from pathlib import Path
from random import Random
from types import SimpleNamespace as NS

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import answerlog
import v39
from abm.domains import Abstain, EdgePrediction, Relation
from abm.sme import Alignment


def _fixtures():
    row = NS(slot_index=0, alive=True, relation=Relation("r0", "p", ("e",)))
    d = NS(name="R", constituents=(row,))
    al = Alignment(entity_mapping={"e": "a"}, relation_mapping={}, candidate_projections=("r0",),
                   total_score=1.0, score_breakdown={}, systematicity_contribution=0.0,
                   matched_predicates_count=0, unmatched_count=1)
    state = NS(slot_history={}, p_hat=NS())
    config = NS(fill_selection="most_frequent", higher_order_predicates=frozenset(), local_lambda=1.0)
    return d, NS(), al, state, config, NS()


@pytest.mark.parametrize("raises", [False, True])
def test_candidate_restores_rng_stats_and_ctx(monkeypatch, raises):
    import abm.sme as sme
    args = _fixtures()
    rng = Random(7)
    before = rng.getstate()
    v39.STATS.clear()
    v39.STATS.update(saved=3)
    nested = {"saved": object()}
    v39.CTX.clear()
    v39.CTX.update(saved=nested)
    monkeypatch.setattr(sme, "project", lambda *a, **k: Abstain("no_projectable_relation"))
    monkeypatch.setattr(v39, "seat_state", lambda *a: "F")

    def fill(*a, **k):
        assert a[3] == args[2].relation_mapping
        assert a[2] == args[2].entity_mapping
        a[7].random()
        v39.STATS["extra"] = 1
        v39.CTX["extra"] = 2
        if raises:
            raise ValueError("記録用の例外")
        return NS(ambiguous=False, relations=(Relation("filling__R__0__1", "p", ("a",)),))

    monkeypatch.setattr(v39, "fill_v39", fill)
    if raises:
        with pytest.raises(ValueError):
            answerlog._candidate_answer(*args, rng)
    else:
        got = answerlog._candidate_answer(*args, rng)
        assert (got["pred"], got["arguments"], got["source"]) == ("p", ["a"], "F_fill")
    assert rng.getstate() == before
    assert v39.STATS == {"saved": 3}
    assert v39.CTX == {"saved": nested}
    assert v39.CTX["saved"] is nested


def test_projection_survives_ambiguous_filling(monkeypatch):
    import abm.sme as sme
    monkeypatch.setattr(sme, "project", lambda *a, **k: EdgePrediction(Relation("sme_projection__r0", "p", ("a",))))
    monkeypatch.setattr(v39, "fill_v39", lambda *a, **k: NS(ambiguous=True, relations=()))
    monkeypatch.setattr(v39, "seat_state", lambda *a: "F")
    assert answerlog._candidate_answer(*_fixtures(), Random(7))["source"] == "F_proj"


def test_scoring_keeps_gate_below_and_uses_arguments():
    cands = [
        {"selected": 1, "support_ratio": .8, "gate_pass": 1, "pred": "wrong", "arguments": ["a"]},
        {"selected": 0, "support_ratio": .5, "gate_pass": 0, "pred": "right", "arguments": ["a"]},
        {"selected": 0, "support_ratio": .8, "gate_pass": 1, "pred": "right", "arguments": ["b"]},
    ]
    got = answerlog._score_candidates(cands, Relation("held", "right", ("a",)))
    assert got["cand_other_correct"] == 1
    assert got["cand_other_correct_passed"] == 0
    assert got["cand_tie_disagree"] == 1
    assert got["cand_tie_disagree_pairs"] == 1
    assert all("hit" not in c for c in cands)
