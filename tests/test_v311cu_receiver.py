"""受信の小例：U の親の対応から観察一回、初期評価だけを新世代へ入れる。"""
import io
from dataclasses import replace
from types import SimpleNamespace

import test_v311c as C
import test_v310h_hist_role as H
import test_v310u as U
import abm.abstraction as ab
import abm.loop as loop
import histrole
import relearninit
import tiestruct
import ustruct
import v39
import v310be
import v311c
from abm.domains import Abstain, VerbatimTrace


def test_received_u_observation_relearns_without_ordinary_score(monkeypatch):
    C.setup()
    v311c.CFG['relearn_init'] = True
    v311c.STATS.update(recv_birth=0, recv_assim=0, recv_none=0, recv_memory_empty=0,
                      recv_score_changed=0, recv_merit_changed=0)
    histrole.CFG['u_all_orders'] = True
    histrole.STATS.update(histrole._stats_zero())
    cfg = SimpleNamespace(pricing_rule='legacy', refill_rule='legacy', local_lambda=1.0,
                          higher_order_predicates=frozenset({'cause'}))
    v39.CTX['config'] = cfg
    v310be.CTX['R_B_trial'] = 0.0
    d = U.defn()
    base, target = U.scene(), replace(U.scene(), graph_id='received')
    st = C.state([d], {('R_u', 0): {'cause': 1}, ('R_u', 2): {'brk': 1}}, traces=[VerbatimTrace(0, base)])
    st = replace(st, v39_seats={('R_u', i): v39.SeatRec(7, 'U' if i == 1 else 'F', 0, 0, v39.ZERO4, v39.ZERO4)
                               for i in range(3)})
    monkeypatch.setattr(ab, '_definition_graph', lambda definition, mode='all': v39.v39_graph(definition, st.slot_history))
    monkeypatch.setattr(ab, '_extend_definition', lambda old, pairs, state, trial, **kw: old)
    # 小例では同化先を固定し、受信から履歴・照合・新世代の初期評価までの実関数を通す。
    def assimilation(state, base, target, alignment, trial, **kw):
        kw['name'] = 'R_u'
        out, reg = H.NEW(state, base, target, alignment, trial, **kw)
        return v39.reconcile(out, trial, 'm1'), reg
    def forbidden(*args, **kw):
        raise AssertionError('受信が予測又は通常採点を呼んだ')
    monkeypatch.setattr(loop, 'm1', assimilation)
    monkeypatch.setattr(loop, 'predict', forbidden)
    monkeypatch.setattr(loop, '_update_accounting', forbidden)
    monkeypatch.setattr(v39, 'reconcile', v39.reconcile)
    fo = io.StringIO()
    relearninit.install(fo)
    undo = ustruct.install_matching()
    try:
        out, rec = v311c.receive_one(st, {'graph': target, 'tag': 'received_tag'}, 9, cfg)
    finally:
        undo()
    seat = out.v39_seats[('R_u', 1)]
    assert rec['result'] == '同化' and out.slot_history[('R_u', 1)] == {'hold': 1}
    assert seat.gen == 8 and seat.state == 'H' and seat.post == v39.ZERO4 and seat.n_scored == 0
    assert seat.init[1] == v39.ZERO16 and seat.init[3] == (1.0,) * 16
    assert relearninit.CTX['scene'] is target and relearninit.STATS['relearn_init'] == 1
    assert v311c.STATS['recv_relearn'] == 1 and v311c.STATS['recv_score_changed'] == 0
    assert v310be.CTX['R_B_trial'] == 0.0 and 'relearn_init' in fo.getvalue()


def test_probe_restores_all_four_flag_records(monkeypatch):
    C.setup()
    st = C.state()
    records = [histrole.CFG, histrole.STATS, ustruct.UREG, ustruct.STATS,
               relearninit.CTX, relearninit.STATS, tiestruct.TCTX, tiestruct.STATS]
    before = [dict(r) for r in records]
    def predict(ai, state, config, rng):
        for r in records:
            r['temporary_probe_value'] = 17
        return SimpleNamespace(prediction=Abstain('probe')), None
    v311c.CFG['inner_predict'] = predict
    assert v311c.probe(st, [{'scene': H.scene()}], SimpleNamespace()) == [None]
    assert [dict(r) for r in records] == before
    assert st.definitions == {} and st.slot_history == {}
