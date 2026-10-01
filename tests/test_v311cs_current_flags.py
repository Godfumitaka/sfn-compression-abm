"""現行の照合・欠けた位置・引数の控えを、受信の経路で確かめる小例。"""
from collections import Counter
from dataclasses import replace
from types import SimpleNamespace

import test_v311c as C
import test_v310h_hist_role as H
import abm.loop as loop
import fixorder2
import ustruct
import strictpc
import answergap
import v39
import v311c
from abm.domains import Abstain, Entity, Relation, RelationGraph, VerbatimTrace


def graph(name, entities, rows):
    return RelationGraph(name, tuple(Entity(e) for e in entities),
                         tuple(Relation(r, p, tuple(a)) for r, p, a in rows))


def setup(monkeypatch):
    C.setup()
    H.histrole.STATS.update(H.histrole._stats_zero())
    fixorder2.install()
    v39._install_candidates()
    ustruct.install_matching()
    strictpc.install()
    v311c.CFG['strict_pc'] = True
    v311c.STATS.update(recv_birth=0, recv_assim=0, recv_none=0, recv_memory_empty=0,
                      recv_score_changed=0, recv_merit_changed=0)
    def forbidden(*args, **kwargs):
        raise AssertionError('受信が予測又は通常の採点を呼んだ')
    monkeypatch.setattr(loop, 'predict', forbidden)
    monkeypatch.setattr(loop, '_update_accounting', forbidden)
    return SimpleNamespace(pricing_rule='legacy', refill_rule='legacy', local_lambda=1.0,
                           higher_order_predicates=frozenset({'cause', 'P'}))


def test_received_bundle_strict_parent_child_mapping(monkeypatch):
    cfg = setup(monkeypatch)
    base = graph('base', 'ab', [('c1', 'hold', ('a', 'b')), ('c2', 'wrap', ('a', 'b')),
                               ('P', 'P', ('c1', 'c2'))])
    target = graph('received', 'xy', [('d1', 'push', ('x', 'y')), ('d2', 'wrap', ('x', 'y')),
                                      ('Q', 'P', ('d1', 'd2'))])
    strictpc.record_kinds(base)
    seen = []
    def learner(state, base, target, alignment, trial, **kw):
        seen.append(dict(alignment.relation_mapping))
        return state, None
    monkeypatch.setattr(loop, 'm1', learner)
    out, rec = v311c.receive_one(C.state(traces=[VerbatimTrace(0, base)]),
                                {'graph': target, 'tag': 'nT'}, 5, cfg)
    assert seen == [{'c2': 'd2'}]
    assert rec['result'] == '不成立' and len(out.prototype.traces) == 2
    assert strictpc.KINDS['Q'] == ('関係', '関係')


def test_received_argument_kinds_survive_definition_graph(monkeypatch):
    cfg = setup(monkeypatch)
    first = graph('first_report', 'ab', [('r1', 'hold', ('a', 'b')), ('r2', 'brk', ('a', 'b')),
                                       ('c1', 'cause', ('r1', 'r2'))])
    second = graph('second_report', 'AB', [('s1', 'hold', ('A', 'B')), ('s2', 'brk', ('A', 'B')),
                                         ('t1', 'cause', ('s1', 's2'))])
    monkeypatch.setattr(loop, 'm1', H.NEW)
    st, empty = v311c.receive_one(C.state(), {'graph': first, 'tag': 'n1'}, 4, cfg)
    assert empty['memory_empty'] and strictpc.KINDS['c1'] == ('関係', '関係')
    out, rec = v311c.receive_one(st, {'graph': second, 'tag': 'n2'}, 5, cfg)
    assert rec['result'] == '誕生' and rec['base_is_report']
    d = out.definitions[rec['R']]
    assert {r.relation.relation_id for r in d.constituents} == {'c1', 'r1', 'r2'}
    # 受け取った行から作った部分定義：子の行が無い場合にも、関係の位置を物に替えない。
    partial = replace(d, constituents=tuple(r for r in d.constituents if r.relation.relation_id != 'r1'))
    g = v39.v39_graph(partial, out.slot_history)
    assert 'r1' not in {e.entity_id for e in g.entities}
    assert strictpc.RELPOS[id(g)] == frozenset({'r1'})
    assert strictpc.KINDS['r1'] == ('物', '物')
    v39.unregister(g)
    assert v311c.STATS['recv_score_changed'] == v311c.STATS['recv_merit_changed'] == 0


def test_received_definition_obeys_answer_gap_in_world(monkeypatch):
    cfg = setup(monkeypatch)
    strictpc.record_kinds(H.BASE)
    monkeypatch.setattr(loop, 'm1', H.NEW)
    out, rec = v311c.receive_one(C.state(traces=[VerbatimTrace(0, H.BASE)]),
                                {'graph': H.scene(), 'tag': 'nT'}, 5, cfg)
    assert rec['result'] == '誕生'
    d = out.definitions[rec['R']]
    brk = next(r for r in d.constituents if r.relation.relation_id == 'r2')
    d = replace(d, constituents=tuple(replace(r, alive=False) if r is brk else r for r in d.constituents))
    history = {**out.slot_history, (d.name, brk.slot_index): {'push': 10, 'brk': 1}}
    scene = H.scene(hide=('s1',))
    answergap.install()
    filling = v39.fill_v39(d, scene, {'a': 'A', 'b': 'B'}, {'c1': 't1', 'r1': 's1'},
                          history, out.p_hat, higher_order_predicates=cfg.higher_order_predicates, local_lambda=1.0)
    assert {r.predicate for r in filling.relations} == {'hold', 'push'}
    answer, path = v39.fill_decision(Abstain('no_projectable_relation'), filling, None)
    assert answer.edge.predicate == 'hold' and answer.edge.arguments == ('A', 'B')
    assert answergap.STATS['fill_dropped'] == 1 and answergap.STATS['spoke'] == 1


def test_probe_restores_current_records_and_counter_types():
    C.setup()
    strictpc.STATS.clear()
    strictpc.STATS.update(reasons=Counter({'original': 2}), use_calls=Counter(), use_dropped=Counter())
    strictpc.KINDS.clear()
    strictpc.KINDS['seen'] = ('関係', '物')
    strictpc.RELPOS.clear()
    strictpc.NONROW.clear()
    strictpc.SHADOW.clear()
    strictpc.MODE[:] = ['iii']
    answergap.STATS.clear()
    answergap.CTX.clear()
    refs = [strictpc.KINDS, strictpc.RELPOS, strictpc.NONROW, strictpc.SHADOW, answergap.STATS, answergap.CTX]
    before = [dict(r) for r in refs]
    mode_id = id(strictpc.MODE)
    def predict(ai, state, config, rng):
        for r in refs:
            r['temporary'] = 17
        strictpc.MODE[:] = ['off']
        strictpc.STATS['reasons']['temporary'] += 1
        return SimpleNamespace(prediction=Abstain('probe')), None
    v311c.CFG['inner_predict'] = predict
    assert v311c.probe(C.state(), [{'scene': H.scene()}], SimpleNamespace()) == [None]
    assert [dict(r) for r in refs] == before
    assert id(strictpc.MODE) == mode_id and strictpc.MODE == ['iii']
    assert isinstance(strictpc.STATS['reasons'], Counter)
    assert strictpc.STATS['reasons'] == Counter({'original': 2})
    strictpc.STATS['reasons']['new_after_probe'] += 1
    assert strictpc.STATS['reasons']['new_after_probe'] == 1
