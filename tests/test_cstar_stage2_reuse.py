"""点の変更・構造の境界・反実仮想の状態不変を独立に検査する。"""
from dataclasses import replace
from pathlib import Path
from random import Random
from functools import partial
import sys
sys.path[:0] = [str(Path(__file__).resolve().parents[1]/'tools'), str(Path(__file__).resolve().parents[1])]
import pytest
from sme2017 import Graph, Node, Settings
from cstar_matcher import CstarMatcher, validate
from cstar_reuse import Store
from test_attncstar import cstar, retained_U_structure, build
from test_sme2017_connection import separate
import attncstar as N
import attnstage2 as T
from attnstage2_distribution import Readout
import cstar_runtime as C
import smeshared as S
import v39


def counters():
    return dict(match_calls=0, result_cache_hits=0, engine_calls=0, engine_seconds=0.,
                foundation_builds=0, foundation_hits=0)


@pytest.mark.parametrize('uniform', [False, True])
def test_full_result_and_rng_equal_after_probability_and_state_changes(uniform):
    rng = Random(11208)
    settings = Settings()
    for case in range(32):
        nodes = [Node('e0','entity'), Node('e1','entity')]
        for i in range(rng.randint(2,5)):
            # 共有した子と一対一の競合を含め、型・順つき引数を無作為に作る。
            kind = rng.choice(['relation','function','attribute'])
            args = tuple(rng.choice(nodes).key for _ in range(rng.randint(1,2)))
            nodes.append(Node(f'r{i}',kind,frozenset({f'p{i%2}'}),args,
                              ubiquitous=rng.choice([False,False,True])))
        right = Graph(tuple(Node(n.key,'unknown',args=None) if case%4==0 and n.key=='r0' else n
                            for n in nodes))
        off, on = (CstarMatcher(settings,tie_seed=case,tie_uniform=uniform) for _ in range(2))
        store, stats = Store(), counters()
        for step in range(5):
            left = Graph(tuple(replace(n,state=('F','H','U')[step%3],
                                names=n.names if step%3<2 else frozenset()) if n.kind!='entity' else n
                               for n in nodes))
            ps = {n.key:{'p0':p,'p1':1-p} for n in nodes if n.kind!='entity'
                  for p in [rng.choice([0.,1e-12,.1,.5,.9,1.]) ]}
            with on.stage2_scope(store, stats):
                actual = on.match(left,right,probabilities=ps,use_cache=False)
            expected = off.match(left,right,probabilities=ps,use_cache=False)
            assert actual == expected
            assert on.snapshot() == off.snapshot()
            assert validate(left,right,actual)
            assert not hasattr(on,'_stage2_scope')
        assert stats['foundation_builds']==1 and stats['foundation_hits']==4
        assert all(not hasattr(node,'names') for f in store.foundations.values()
                   for node in f.left.values())


def test_zero_probability_and_greedy_pruning_do_not_freeze_a_mapping():
    left = Graph((Node('e','entity'),Node('r','relation',frozenset({'p'}),('e',))))
    right = Graph((Node('a','entity'),Node('b','entity'),
                   Node('x','relation',frozenset({'p'}),('a',)),
                   Node('y','relation',frozenset({'q'}),('b',))))
    store, stats = Store(), counters()
    m = CstarMatcher(Settings(greedy_max=1),tie_uniform=True)
    mappings = []
    for p in [1.,.9,.1,0.,1.]:
        ps = {'r':{'p':p,'q':1-p}}
        with m.stage2_scope(store,stats):
            actual = m.match(left,right,probabilities=ps,use_cache=False,tie_seed=7)
        expected = CstarMatcher(m.settings,tie_uniform=True).match(
            left,right,probabilities=ps,use_cache=False,tie_seed=7)
        assert actual == expected
        mappings.append(actual.best.relation_mapping)
    assert mappings[0] == mappings[-1] and mappings[0] != mappings[2]


def test_shape_change_does_not_use_old_arguments_or_unknown_children():
    a = Graph((Node('e','entity'),Node('r','relation',frozenset({'p'}),('e',))))
    b = Graph((Node('e','entity'),Node('r','relation',frozenset({'p'}),('e','e'))))
    hidden = Graph((Node('e','entity'),Node('r','unknown',args=None)))
    store, stats = Store(), counters()
    m = CstarMatcher(tie_uniform=True)
    for left, right in [(a,a),(b,a),(a,hidden),(a,a)]:
        with m.stage2_scope(store,stats):
            actual = m.match(left,right,probabilities={'r':{'p':1.}},use_cache=False,tie_seed=8)
        expected = CstarMatcher(tie_uniform=True).match(
            left,right,probabilities={'r':{'p':1.}},use_cache=False,tie_seed=8)
        assert actual == expected
    assert stats['foundation_builds']==3 and stats['foundation_hits']==1


def test_actual_Cstar_seats_values_readouts_and_main_state_equal(cstar, retained_U_structure):
    state,cfg,obs,ai = build()
    state,_ = v39._convert(state,'FH','R',1,1)
    before = repr(state),repr(obs.__dict__),S.ENGINE.rng.getstate(),C.snapshot()
    records = []
    kwargs = dict(mode='global',position='k2',door_task=True,epsilon=.01,
                  readout_policy=Readout(),feature_policy=N.Features())
    off = N.Session(ai,state,cfg,Random(1).getstate(),obs,{},**kwargs)
    on = N.Session(ai,state,cfg,Random(1).getstate(),obs,{},reuse_structure=True,
                   rematch_record=records.append,**kwargs)
    assert off.candidates == on.candidates
    seats = [T.Seat(d.name,row.slot_index,v39.seat_state(d,row,state.slot_history),
                    state.v39_seats[d.name,row.slot_index].gen)
             for d in state.definitions.values() for row in d.constituents
             if v39.seat_state(d,row,state.slot_history)!='U']
    for seat in seats:
        assert off.rematched(seat) == on.rematched(seat)
    assert records and any(r['engine_calls'] for r in records)
    assert any(r['foundation_hits'] for r in records)
    assert (repr(state),repr(obs.__dict__),S.ENGINE.rng.getstate(),C.snapshot())==before
    assert not hasattr(C.ENGINE,'_stage2_scope')


def test_virtual_birth_columns_equal_and_diagnostic_origin_separate(cstar, retained_U_structure):
    from attnstage2_initial import VirtualInitial
    from attnstage2_questions import Snapshot
    state,cfg,obs,ai = build()
    definition = replace(state.definitions['R'],name='fresh',registered_at=2)
    pre = ai,state,cfg,Random(1).getstate(),obs,{},True,(),None
    context = dict(definition=definition,row=definition.constituents[0],first_material=ai.base_graph,
        second_visible=ai.target_graph_partial,trial=2,base_age=1,pre=pre,
        questions=Snapshot(1,1,frozenset({'hold'}),frozenset(),True))
    rec = v39.SeatRec(0,'F',2,2,v39.ZERO4,v39.ZERO4)
    before = repr(state),repr(obs.__dict__),S.ENGINE.rng.getstate(),C.snapshot()
    diagnostics,values,records = [],[],[]
    for reuse in [False,True]:
        policy = VirtualInitial(loss_mode='top1',mode='global',position='k2',epsilon=.01,
            readout_policy=Readout(),feature_policy=N.Features(),
            session_class=partial(N.Session,reuse_structure=reuse,rematch_origin='birth',
                                  rematch_record=diagnostics.append))
        values.append(policy(rec,'birth',context))
        records.append([{k:v for k,v in r.items() if k!='seconds'} for r in policy.records])
    assert values[0] == values[1] and records[0] == records[1]
    assert diagnostics and all(r['origin']=='birth' for r in diagnostics)
    assert {r['reuse'] for r in diagnostics} == {False,True}
    assert (repr(state),repr(obs.__dict__),S.ENGINE.rng.getstate(),C.snapshot())==before
