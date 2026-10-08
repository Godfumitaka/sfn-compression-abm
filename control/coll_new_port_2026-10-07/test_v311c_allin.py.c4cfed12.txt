"""新しい計算への接続の検査。答えの良し悪しを規定しない。"""
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
import v311c_allin as P
from attnsme_features import Observations
from attnstage2_questions import Questions
from abm.domains import Entity, Relation, RelationGraph
from v311c_fingerprint import fingerprint


def graph(name="公開"):
    return RelationGraph("束", (Entity("物"),), (Relation("行", name, ("物",)),))


def test_report_observation_does_not_advance_real_question_or_clock():
    o = Observations(); q = Questions(); before = q.record()
    P.observe_report(o, graph()); P.observe_report(o, graph("別の公開"))
    assert o.last_trial == -1 and o.events == [] and q.record() == before
    assert o.names == {"公開", "別の公開"}
    assert o.arguments == {"行": ("物",)}
    assert sum(sum(v.values()) for v in o.table.values()) == 2


def test_nested_restore_keeps_pending_identity_and_all_learned_fields(monkeypatch):
    o = Observations(); P.observe_report(o, graph())
    q = Questions(); pending = q.present(True)
    individual = {"observations": o, "a": {"費用": .1}}
    a = SimpleNamespace(ST={"individuals": {"本人": individual}, "individual": individual})
    t = SimpleNamespace(ST={"questions": {"本人": q}, "question": pending})
    monkeypatch.setitem(sys.modules, "attnsme", a)
    monkeypatch.setitem(sys.modules, "attnstage2_runtime", t)
    monkeypatch.setitem(sys.modules, "smeevict", SimpleNamespace(MANAGER=None))
    before = fingerprint(P.isolation_record()); saved = P.snapshot_mutables()
    q.door += 10; q.door_names.add("仮の名"); q.pending = None
    o.names.add("仮の名"); o.parents["子"].append(("親", 0))
    individual["a"]["費用"] = 8
    a.ST["individual"] = {"別の実体": True}
    P.restore_mutables(saved)
    assert fingerprint(P.isolation_record()) == before
    assert q.pending is pending and t.ST["question"] is pending
    assert a.ST["individual"] is individual


def test_match_cache_keys_with_dataclass_and_set_are_fully_fingerprintable():
    @dataclass(frozen=True)
    class Setting:
        count: int
    value = {(Setting(1), "種"): {"集合": frozenset(("甲", "乙"))}}
    assert fingerprint(P.runtime_values(value)) == fingerprint(P.runtime_values(value))
    changed = {(Setting(2), "種"): {"集合": frozenset(("甲", "乙"))}}
    assert fingerprint(P.runtime_values(value)) != fingerprint(P.runtime_values(changed))


def test_unknown_additional_state_is_not_silently_omitted():
    import pytest
    with pytest.raises(TypeError): P.runtime_values(object())


def test_receive_freezes_background_restores_world_and_does_not_count_question(monkeypatch):
    o = Observations(); q = Questions(); question = q.present(True)
    a = SimpleNamespace(ST={"individual": {"observations": o, "a": {"位置": .2}}})
    t = SimpleNamespace(ST={"current_pre": ("世界",), "question": question, "questions": {"本人": q}})
    b = SimpleNamespace(CTX={"score_state": "世界の背景", "R_E_trial": 7})
    c = SimpleNamespace(CTX={"prediction_state": "世界", "last_partial": "世界の提示"})
    for name, module in (("attnsme",a),("attnstage2_runtime",t),("v310be",b),("cstar_runtime",c)):
        monkeypatch.setitem(sys.modules, name, module)
    P.CTX.clear(); P.CTX["world_observation"] = dict(scene=[], entities=set(), disclosed=None)
    state = SimpleNamespace(rng_state=(1, 2)); g = graph()
    with P.receive_context(state, g, 0, "設定"):
        assert b.CTX["score_state"] is state and c.CTX["collective_receive"]
        pre = t.ST["current_pre"]
        assert pre[0].target_graph_partial is g and pre[1] is state and pre[3] == state.rng_state
        assert pre[4] is not o and pre[5] == {"位置": .2}
        assert q.door == 1 and q.other == 0 and q.pending is question
    assert b.CTX == {"score_state": "世界の背景", "R_E_trial": 7}
    assert c.CTX == {"prediction_state": "世界", "last_partial": "世界の提示"}
    assert t.ST["current_pre"] == ("世界",) and t.ST["question"] is question
    assert o.last_trial == -1 and o.names == set()


def test_receive_context_restores_even_if_calculation_raises(monkeypatch):
    import pytest
    b = SimpleNamespace(CTX={"score_state": "元"})
    monkeypatch.setitem(sys.modules, "v310be", b)
    monkeypatch.setitem(sys.modules, "cstar_runtime", None)
    monkeypatch.setitem(sys.modules, "attnstage2_runtime", None)
    with pytest.raises(RuntimeError):
        with P.receive_context(SimpleNamespace(), graph(), 0, None): raise RuntimeError("停止")
    assert b.CTX == {"score_state": "元"}


def test_final_attention_probe_restores_nested_state_rng_and_real_journal(monkeypatch):
    import io
    import random
    import abm.loop as loop
    import v311c as C
    import v39
    import smeshared as S
    import smereplay as R
    from sme2017 import Matcher
    from abm.domains import Abstain
    o = Observations(); q = Questions(); pending = q.present(True)
    individual = {"observations": o, "a": {"位置": .2}}
    a = SimpleNamespace(ST={"individuals": {"本人": individual}, "individual": individual,
        "door_task": True, "checks": 1, "pending": {"実課題": True}})
    t = SimpleNamespace(ST={"questions": {"本人": q}, "question": pending, "current_pre": None})
    monkeypatch.setitem(sys.modules, "attnsme", a)
    monkeypatch.setitem(sys.modules, "attnstage2_runtime", t)
    monkeypatch.setitem(sys.modules, "cstar_runtime", None)
    monkeypatch.setitem(sys.modules, "smeevict", SimpleNamespace(MANAGER=None))
    monkeypatch.setattr(S, "ENGINE", Matcher(tie_seed=1, tie_uniform=True))
    for name in ("CTX", "STATS", "RESULTS", "GRAPHS", "CHOICES", "LOG"):
        monkeypatch.setattr(S, name, {})
    monkeypatch.setattr(S, "_text_gzip", lambda path: io.StringIO())
    journal = io.StringIO(); monkeypatch.setattr(R, "ST", {"f": journal, "predictions": 1})
    def prepared(ai, state, config, rng):
        assert a.ST["door_task"] is False
        a.ST["checks"] += 1; individual["a"]["位置"] = 7
        o.names.add("診断だけ"); S.ENGINE.rng.random(); S.CHOICES["診断"] = 1
        R.ST["f"].write("診断だけ")
        return SimpleNamespace(prediction=Abstain("試験")), None
    monkeypatch.setattr(C, "CFG", {"sme2017": True, "audit": True, "run": 1,
        "inner_predict": lambda *a: (_ for _ in ()).throw(RuntimeError("旧い予測へ戻った")),
        "prepared_predict": prepared})
    for name in ("choose_partner", "receive_one", "_snapshot_modules", "_restore_modules", "learning_fingerprint", "probe"):
        monkeypatch.setattr(C, name, getattr(C, name))
    monkeypatch.setattr(C, "_check_dictionary_guard", lambda *a: None)
    monkeypatch.setattr(loop, "_update_accounting", lambda *a: None)
    monkeypatch.setattr(loop, "_ledger_record", lambda *a: None)
    monkeypatch.setattr(loop, "predict", lambda *a: None)
    monkeypatch.setattr(v39, "_init_rec", lambda *a: None)
    P.install({"seed": 1}, Path("使わない書込先"))
    state = v39._state_class()(); rng = random.getstate()
    before = C.learning_fingerprint(state)
    assert C.probe(state, [{"scene": graph(), "held_out_is_door": False}], None) == [None]
    assert C.learning_fingerprint(state) == before and random.getstate() == rng
    assert journal.getvalue() == "" and R.ST["f"] is journal and R.ST["predictions"] == 1
    assert q.door == 1 and q.pending is pending and t.ST["question"] is pending
    P.close()
