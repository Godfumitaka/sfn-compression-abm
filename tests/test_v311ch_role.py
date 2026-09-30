"""載せ直しの小例。受信経路と E の仮適用に、同じ役割の履歴処理が入る。"""
from types import SimpleNamespace

import test_v310h_hist_role as H
import test_v311c as C
import abm.abstraction as ab
import abm.loop as loop
import v310be
import v311c
from abm.domains import VerbatimTrace
from abm.sme import map_graphs


def test_received_bundle_history_uses_parent_role(monkeypatch):
    C.setup()
    v311c.STATS.update(recv_birth=0, recv_assim=0, recv_none=0, recv_memory_empty=0,
                      recv_score_changed=0, recv_merit_changed=0)
    H.histrole.STATS.update(H.histrole._stats_zero())
    st = C.state(traces=[VerbatimTrace(0, H.BASE)])
    cfg = SimpleNamespace(pricing_rule="legacy", refill_rule="legacy", local_lambda=1.0)
    monkeypatch.setattr(loop, "m1", H.NEW)
    def forbidden(*args, **kw):
        raise AssertionError("受信で予測又は通常の採点が呼ばれた")
    monkeypatch.setattr(loop, "predict", forbidden)
    monkeypatch.setattr(loop, "_update_accounting", forbidden)
    target = H.scene()
    out, rec = v311c.receive_one(st, {"graph": target, "tag": "nT"}, 5, cfg)
    assert rec["result"] == "誕生"
    R = rec["R"]
    assert H.slots(out, R) == {"c1": {"cause": 1}, "r1": {"hold": 1}, "r2": {"brk": 1}}
    assert len(out.prototype.traces) == 2
    assert out.prototype.traces[-1].scene is target
    assert out.c_trace_tags == {"scene": "nT"}
    assert rec["base"] == "base" and not rec["base_is_report"]
    assert out.v39_seats == st.v39_seats


def test_hypothetical_candidate_uses_same_role_history(monkeypatch):
    C.setup()
    st = C.state()
    v310be.CFG.update(nohash=True)
    monkeypatch.setattr(ab, "m1", H.histrole.make(H.ORIG, real=False))
    target = H.scene()
    al = map_graphs(H.BASE, target).alignment
    out, R = v310be.hypo_m1(st, H.BASE, target, al, 5, None, H.KW)
    assert H.slots(out, R) == {"c1": {"cause": 1}, "r1": {"hold": 1}, "r2": {"brk": 1}}
    assert st.slot_history == {} and st.definitions == {}


def test_probe_preserves_state_and_role_counters(monkeypatch):
    C.setup()
    H.histrole.STATS.clear()
    H.histrole.STATS.update(H.histrole._stats_zero())
    st = C.state()
    before = dict(H.histrole.STATS)
    from abm.domains import Abstain
    def predict(ai, state, config, rng):
        assert state is st
        v310be.STATS["probe_temporary"] = 1
        return SimpleNamespace(prediction=Abstain("probe")), None
    v311c.CFG["inner_predict"] = predict
    out = v311c.probe(st, [{"scene": H.scene()}], SimpleNamespace())
    assert out == [None]
    assert H.histrole.STATS == before and "probe_temporary" not in v310be.STATS
    assert st.slot_history == {} and st.definitions == {}
