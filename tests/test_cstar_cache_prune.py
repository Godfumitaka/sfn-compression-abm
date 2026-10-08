"""指示26。試行の種の分離、順序、旧キーの検出、反実仮想の復元を検査する。"""
from pathlib import Path
from random import Random
import json
import sys
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'tools'),str(Path(__file__).resolve().parents[1])]
import pytest
from cstar_cache_prune import PruneGuard
from cstar_matcher import CstarMatcher
from sme2017 import Graph,Node,Settings
import cstar_runtime as C
import smeshared as S
import attncstar as N
import attnstage2 as T
from attnstage2_distribution import Readout
from test_attncstar import cstar
from test_sme2017_connection import separate
from test_attnstage2_connection import build,retained_U_structure
import v39


def graphs():
    left=Graph((Node('a','entity'),Node('r','relation',frozenset({'p'}),('a',))))
    right=Graph((Node('b','entity'),Node('s','relation',frozenset({'p'}),('b',))))
    return left,right,{'r':{'p':1.}}


def test_prune_preserves_current_order_unseeded_self_and_rng():
    e=CstarMatcher(Settings(),tie_seed=3,tie_uniform=True); e.cache_prune_guard=g=PruneGuard()
    a,b,p=graphs();g.begin_trial(e,0)
    old=e.match(a,b,probabilities=p,tie_seed=4)
    e.match(a,b,probabilities=p,tie_seed=5)
    e.match(a,b,probabilities=p);e.self_score(a)
    unseeded={k:v for k,v in e.cache.items() if g.seed(k) is None}
    self_before=dict(e.self_cache);rng=e.rng.getstate()
    g.begin_trial(e,1)
    assert e.cache==unseeded and e.self_cache==self_before and e.rng.getstate()==rng
    assert g.removed=={'cache':2,'cache_rng':2}
    now=e.match(a,b,probabilities=p,tie_seed=6)
    assert now==old
    order=list(e.cache);g.begin_trial(e,1);assert list(e.cache)==order


def test_monitor_catches_old_seed_before_a_result_can_be_reused():
    e=CstarMatcher(Settings(),tie_seed=3);e.cache_prune_guard=g=PruneGuard()
    a,b,p=graphs();g.begin_trial(e,0);e.match(a,b,probabilities=p,tie_seed=4);g.begin_trial(e,1)
    key=e.match_key(a,b,4,probabilities=p)
    with pytest.raises(RuntimeError,match='過去'):
        g.request(key,1,'mapping')
    assert g.forbidden_reads==1
    with pytest.raises(RuntimeError,match='過去'):
        e.match(a,b,probabilities=p,tie_seed=4)
    assert g.forbidden_reads==2


def test_unknown_origin_and_wrong_trial_stop():
    e=CstarMatcher(Settings());g=PruneGuard();a,b,p=graphs()
    e.match(a,b,probabilities=p,tie_seed=4)
    with pytest.raises(RuntimeError,match='由来'):g.begin_trial(e,1)
    g.begin_trial(CstarMatcher(Settings()),0)
    with pytest.raises(RuntimeError,match='文脈'):g.request(('call-seed-v1',4),1,'mapping')


def test_audit_keeps_zero_and_actual_failure_counts(tmp_path):
    e=CstarMatcher(Settings());e.cache_prune_guard=g=PruneGuard(tmp_path/'audit.jsonl.gz')
    a,b,p=graphs();g.begin_trial(e,0);e.match(a,b,probabilities=p,tie_seed=4);g.begin_trial(e,1)
    summary=g.close(True)
    assert summary['forbidden_reads']==0 and summary['removed']['cache']==1
    assert json.loads((tmp_path/'audit.jsonl.gz.summary.json').read_text())==summary


@pytest.mark.parametrize('mode',['alpha','top1','mixture'])
def test_real_Cstar_all_seats_and_state_rng_unchanged(cstar,retained_U_structure,monkeypatch,mode):
    state,cfg,obs,ai=build();state,_=v39._convert(state,'FH','R',1,2)
    def measured():
        session=N.Session(ai,state,cfg,Random(1).getstate(),obs,{},mode='global',position='k2',door_task=True,
                          epsilon=.01,readout_policy=Readout(),feature_policy=N.Features())
        seats=[T.Seat(d.name,row.slot_index,v39.seat_state(d,row,state.slot_history),state.v39_seats[d.name,row.slot_index].gen)
               for d in state.definitions.values() for row in d.constituents]
        rows,work=T.compare_seats(session.candidates,{},seats,session.rematched,session.exact,
                                  correct=('hold',('x',)),ell=4.,mode=mode,choose=session.choose,
                                  background=session.background,method='rematched')
        return rows,{k:v for k,v in work.items() if k!='seconds'}
    before=repr(state),repr(obs.__dict__),S.ENGINE.rng.getstate(),C.ENGINE.rng.getstate()
    old=measured();guard=PruneGuard();monkeypatch.setattr(C.ENGINE,'cache_prune_guard',guard,raising=False)
    guard.begin_trial(C.ENGINE,S.CTX['trial'])
    snap=C.snapshot();new=measured()
    assert new==old and C.snapshot()==snap
    assert (repr(state),repr(obs.__dict__),S.ENGINE.rng.getstate(),C.ENGINE.rng.getstate())==before
    assert guard.forbidden_reads==0


def test_guard_trial_restored_inside_nested_snapshot(cstar,monkeypatch):
    guard=PruneGuard();monkeypatch.setattr(C.ENGINE,'cache_prune_guard',guard,raising=False)
    guard.begin_trial(C.ENGINE,0);saved=C.snapshot()
    guard.begin_trial(C.ENGINE,1);C.restore(saved)
    assert guard.trial==0 and len(C.snapshot())==4


@pytest.mark.parametrize('mode',['alpha','top1','mixture'])
def test_real_birth_FH_then_HU_values_unchanged(cstar,retained_U_structure,monkeypatch,mode):
    from dataclasses import replace
    from attnstage2_initial import VirtualInitial
    from attnstage2_questions import Snapshot
    state,cfg,obs,ai=build()
    d=replace(state.definitions['R'],name='fresh',registered_at=2)
    context=dict(definition=d,row=d.constituents[0],first_material=ai.base_graph,
                 second_visible=ai.target_graph_partial,trial=2,base_age=1,
                 pre=(ai,state,cfg,Random(1).getstate(),obs,{},True,(),None),
                 questions=Snapshot(1,1,frozenset({'hold'}),frozenset(),True))
    def measured():
        policy=VirtualInitial(loss_mode=mode,mode='global',position='k2',epsilon=.01,
                              readout_policy=Readout(),feature_policy=N.Features(),
                              measure_birth_hu=True,session_class=N.Session)
        return policy(v39.SeatRec(0,'F',2,2,v39.ZERO4,v39.ZERO4),'birth',context)
    old=measured()
    guard=PruneGuard();monkeypatch.setattr(C.ENGINE,'cache_prune_guard',guard,raising=False)
    guard.begin_trial(C.ENGINE,S.CTX['trial']);snap=C.snapshot()
    assert measured()==old and C.snapshot()==snap and guard.forbidden_reads==0
