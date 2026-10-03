"""順を逆にした答えの正誤・保持費用・初期費用を独立の数で検査する。"""
from dataclasses import replace
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
import sys

sys.path[:0] = [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parents[1])]
import pytest
import argorder
import histrole
import relearninit
import v39
import v310be
from abm.accounting import score_prediction
from abm.definition import Constituent, FrozenPrice, FrequencyTable, NamedDefinition
from abm.domains import AgentOutput, EdgePrediction, Entity, Relation, RelationGraph
from abm.sme import Alignment


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    # 各小例は実験の状態の写しだけを使う。
    for module in (argorder, histrole, relearninit, v39, v310be):
        for attr in ("CTX", "CFG", "STATS"):
            if hasattr(module, attr):
                monkeypatch.setattr(module, attr, {})
    v310be.CFG["score_arg_order"] = True
    v310be.CTX.update(L_score={"fold": 7}, R_B_trial=0.0)
    v310be.STATS.update(score_role_scored=0, score_role_scored_pos_differs=0)
    v39.CFG.update(decay=(0.5,) * 16, init="two")
    v39.CTX.update(births_rec=[])
    relearninit.STATS.update(relearn_init=0, relearn_init_multi_obs=0, relearn_init_rU_gt_rH=0)


def definition(alive=True):
    row = Constituent(0, 1, Relation("slot", "fold" if alive else v39.ERASED, ("a", "b")), FrozenPrice(7, 0, 0, 1), alive)
    return NamedDefinition("R", (row,), 1, 1), row


def state_for(d):
    frequencies = FrequencyTable({"fold": 1, "other": 127}, 128, 0.1, frozenset({"fold", "other"}))
    return v39._state_class()(definitions={"R": d}, slot_history={("R", 0): {"fold": 1}}, p_hat=frequencies,
                             v39_seats={("R", 0): v39.SeatRec(1, "F" if d.constituents[0].alive else "H", 1, 1, v39.ZERO4, v39.ZERO4)})


@pytest.mark.parametrize("position,expected", [(("a", "b"), 0.0), (("b", "a"), 7.0)])
def test_oracle_and_role_score_agree_on_order(position, expected):
    received = Relation("observed", "fold", ("a", "b"))
    output = AgentOutput(prediction=EdgePrediction(Relation("answer", "fold", position)), trace={})
    assert bool(score_prediction(output, received, 10).hit) == (expected == 0.0)
    d, row = definition()
    state = state_for(d)
    ans = {"R": "R", "items": [{"slot": 0, "gen": 1, "st": "F", "pos": position, "cid": "observed", "higher": False,
                                "ans": {"F": "fold", "H": "fold", "U": "fold"}}]}
    seats, scored = v310be.score_answers_role(state.v39_seats, ans, received, 1)
    assert scored == [[0, "F", expected, expected, expected]]
    assert seats["R", 0].post == ((expected,) * 16, (expected,) * 16, (expected,) * 16, (1.0,) * 16)


def test_birth_uses_given_alignment_not_rematching(monkeypatch):
    d, row = definition()
    state = state_for(d)
    base = RelationGraph("base", (Entity("a"), Entity("b")), (row.relation,))
    target = RelationGraph("target", base.entities, (Relation("t", "fold", ("b", "a")),))
    argorder.CTX["birth_alignment"] = Alignment({"a": "a", "b": "b"}, {"slot": "t"}, 0, {}, 0, 0, 0)
    monkeypatch.setattr(v39, "h_answer", lambda *a: ("fold", "小例"))
    monkeypatch.setattr(v39, "u_answer", lambda *a: ("fold", "小例"))
    import abm.sme
    monkeypatch.setattr(abm.sme, "map_graphs", lambda *a, **k: pytest.fail("初期採点で照合を呼び直した"))
    rec = v310be.init_rec(d, row, state, base, target, 2, 1, SimpleNamespace(local_lambda=1, higher_order_predicates=frozenset()))
    assert rec.init == ((7.0,) * 16, (7.0,) * 16, (7.0,) * 16, (1.5,) * 16)
    assert v39.CTX["births_rec"][-1]["rF"] == 7.0


@pytest.mark.parametrize("why", ["会計", "m1"])
def test_relearn_initial_score_uses_observation_alignment(monkeypatch, why):
    d, row = definition(alive=False)
    state = state_for(d)
    observed = Relation("observed", "fold", ("a", "b"))
    v39.CTX["config"] = SimpleNamespace(local_lambda=1, higher_order_predicates=frozenset())
    v39.CTX["answers"] = {"R": "R", "items": [{"slot": 0, "pos": ("b", "a")}]}
    argorder.CTX["received"] = observed
    histrole.CTX["observations"] = {("R", 0): ((observed, ("b", "a")),)}
    relearninit.CTX["scene"] = RelationGraph("s", relations=(observed,))
    monkeypatch.setattr(v39, "h_answer", lambda *a: ("fold", "小例"))
    monkeypatch.setattr(v39, "u_answer", lambda *a: ("fold", "小例"))
    import abm.sme
    monkeypatch.setattr(abm.sme, "map_graphs", lambda *a, **k: pytest.fail("初期採点で照合を呼び直した"))
    result = relearninit._apply_init(state, 2, why, [{"R": "R", "slot": 0, "gen": 1}], StringIO())
    assert result.v39_seats["R", 0].init == ((0.0,) * 16, (7.0,) * 16, (7.0,) * 16, (1.0,) * 16)


def test_reverse_order_has_rewrite_cost(monkeypatch):
    d, row = definition()
    state = state_for(d)
    x = RelationGraph("x", (Entity("a"), Entity("b")), (Relation("t", "fold", ("b", "a")),))
    import abm.sme
    # 不整合な対応を与えても、E の費用が順の不一致を見逃さないか。
    alignment = Alignment({"a": "a", "b": "b"}, {"slot": "t"}, 0, {}, 0, 0, 0)
    monkeypatch.setattr(abm.sme, "map_graphs", lambda *a, **k: SimpleNamespace(alignment=alignment))
    _, on = v310be.rewrite(state, "R", x, {"fold": 7}, SimpleNamespace(), {"t"})
    v310be.CFG["score_arg_order"] = False
    _, off = v310be.rewrite(state, "R", x, {"fold": 7}, SimpleNamespace(), {"t"})
    assert on["書換数"] == 1 and off["書換数"] == 0
    assert on["書換"] - off["書換"] == 9.0


@pytest.mark.parametrize("initial,delta,expected_value", [("F", 3, 0.01), ("H", 7, 0.03 / 7)])
def test_be_forgetting_matches_hand_calculation(monkeypatch, initial, delta, expected_value):
    # 二席のうち片方だけを変換する。もう一席を残し、退役の費用を混ぜない。
    rows = tuple(Constituent(i, 0, Relation(str(i), p if i or initial == "F" else v39.ERASED,
                                           ("a", "b")), FrozenPrice(1, 0, 0, 0), bool(i or initial == "F"))
                 for i, p in enumerate(("p", "q")))
    d = NamedDefinition("R", rows, 2, 0)
    col = lambda x: (x,) * 16
    init = (col(0.0), col(0.03 if initial == "F" else 0.0), col(10.0 if initial == "F" else 0.03), col(1.0))
    seats = {("R", 0): v39.SeatRec(0, initial, 0, 0, init, v39.ZERO4),
             ("R", 1): v39.SeatRec(0, "F", 0, 0, (col(0.0), col(10.0), col(10.0), col(1.0)), v39.ZERO4)}
    state = v39._state_class()(definitions={"R": d}, slot_history={("R", 0): {"p": 1}, ("R", 1): {"q": 1}},
                             p_hat=FrequencyTable({"p": 1, "q": 1}, 2, 0.1, frozenset({"p", "q"})), v39_seats=seats)
    monkeypatch.setattr(v39, "_candidates", v310be.candidates)
    monkeypatch.setattr(v39, "_POW", {})
    v39.CFG.update(D=2, T=1740, dict_index={"p": 0, "q": 1}, mean_weights=None,
                   price=0.01873710622997919, budget=None, seed=1)
    v39.CTX["cost_mismatch"] = []
    v39.CTX["struct_cache"] = {}
    candidates = v310be.candidates(state, d, 0, {"p": 1, "q": 1}, 1)
    assert candidates[0][0] == pytest.approx(expected_value)
    assert candidates[0][4] == delta
    after, events, before_bits, after_bits, _, _ = v39.run_conversions(state, 0)
    assert len(events) == 1 and events[0]["v39"] == ("FH" if initial == "F" else "HU")
    assert before_bits - after_bits == delta
    assert after.v39_seats["R", 0].state == ("H" if initial == "F" else "U")
