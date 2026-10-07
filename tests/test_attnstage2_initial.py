"""予測前の固定状態からの出生初期値と、負の価値の変換を検査。"""
from dataclasses import replace
from pathlib import Path
from random import Random
from types import SimpleNamespace
import sys
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'tools'),str(Path(__file__).resolve().parents[1])]
import pytest
from abm.domains import AgentInput
import attnratio as A
import attnstage2 as T
import attnstage2_initial as I
from attnstage2_questions import Snapshot
from attnstage2_distribution import Readout
from test_attnstage2_birth import materials
from test_attnstage2_connection import build
from test_sme2017_connection import separate
import v39
import v310be as L


def context():
    first,second,d,before=materials()
    ai=AgentInput(first,second)
    questions=Snapshot(3,1,frozenset({'hold_b'}),frozenset(),True)
    pre=(ai,before,None,Random(1).getstate(),SimpleNamespace(events=[]),{'role':.5},True,(),None)
    return {'definition':d,'row':d.constituents[0],'first_material':first,
            'second_visible':second,'trial':2,'base_age':1,'pre':pre,'questions':questions}


def test_virtual_initial_session_fixed_pre_state_and_one_evaluation_for_all_seats():
    ctx=context();seen=[];pre=ctx['pre'];saved=repr(pre[1]);rng=pre[3]
    class FakeSession:
        def __init__(self,ai,state,config,rng_state,observations,attention,**kw):
            assert rng_state==rng and attention=={'role':.5}
            assert state.p_hat is pre[1].p_hat
            assert set(state.definitions)=={'new'}
            assert [r.relation.predicate for r in state.definitions['new'].constituents]==['hold','sig_n']
            seen.append((ai.target_graph_partial,kw['door_task']))
            observations.events.append('仮の記録')
            attention['role']=9
            self.attention={};self.background={}
            name='hold_b' if kw['door_task'] else 'sig_e'
            self.candidates=(A.Candidate('new',1,2,0,(),(name,('y',)),{}),)
        choose=staticmethod(A.select)
        def rematched(self,seat):return replace(self.candidates[0],answer=None)
    policy=I.VirtualInitial(loss_mode='alpha',mode='global',position='k2',epsilon=.01,session_class=FakeSession)
    rec=v39.SeatRec(0,'F',2,2,v39.ZERO4,v39.ZERO4)
    out=policy(rec,'birth',ctx)
    second=policy(replace(rec,state='H'),'birth',{**ctx,'row':ctx['definition'].constituents[1]})
    assert len(seen)==2 and out.init[1]!=v39.ZERO16 and second.init[2]!=v39.ZERO16
    assert repr(pre[1])==saved and pre[4].events==[] and pre[5]=={'role':.5}
    records=policy.drain_records()
    assert len(records)==1 and records[0]['background_and_attention']=='prediction_before'
    assert policy.drain_records()==[]
    policy.begin_trial()
    policy(rec,'birth',ctx)
    assert len(seen)==4


def test_reconcile_initial_is_native_zero_and_never_calls_birth_session():
    def forbidden(*a,**kw):raise AssertionError('覚え直しに誕生の二材料を使った')
    policy=I.VirtualInitial(loss_mode='top1',mode='global',position='k2',epsilon=.01,session_class=forbidden)
    rec=v39.SeatRec(1,'H',4,4,((9.,)*16,)*4,v39.ZERO4)
    out=policy(rec,'new_generation',{'trial':4,'key':('old',0),'why':'会計','pre':None})
    assert out.gen==1 and out.init==v39.ZERO4
    assert policy.drain_records()[0]['initial']=='native_reconcile_zero'


@pytest.mark.parametrize('loss_mode',['alpha','top1','mixture'])
def test_virtual_initial_native_session_and_input_state_unchanged(separate,loss_mode,monkeypatch):
    import smeshared as S
    import ustruct
    restore=ustruct.install_matching()
    try:
        state,config,observations,ai=build()
        first=ai.base_graph
        definition=replace(state.definitions['R'],name='new',registered_at=2)
        snapshot=Snapshot(1,1,frozenset({'hold'}),frozenset(),True)
        before=repr(state);events=repr(observations.__dict__);sme_rng=S.ENGINE.rng.getstate()
        monkeypatch.setattr(L,'EPSILON',.5)
        pre=(ai,state,config,Random(1).getstate(),observations,{},True,(),None)
        policy=I.VirtualInitial(loss_mode=loss_mode,mode='binary',position='k2',epsilon=.5,readout_policy=Readout())
        # 仮の問いの材料にある名前は全て実際に可視。正解はSessionへ渡さない。
        ctx={'definition':definition,'row':definition.constituents[0],'first_material':first,
             'second_visible':ai.target_graph_partial,'trial':2,'base_age':1,'pre':pre,'questions':snapshot}
        rec=v39.SeatRec(0,'F',2,2,v39.ZERO4,v39.ZERO4)
        value=policy(rec,'birth',ctx)
        assert all(__import__('math').isfinite(x) for col in value.init for x in col)
        assert repr(state)==before and repr(observations.__dict__)==events
        assert S.ENGINE.rng.getstate()==sme_rng and policy.records[0]['evaluated_questions']>0
    finally:restore()


def test_lambda_zero_runs_native_negative_delta_conversion(separate,monkeypatch):
    state,config,obs,ai=build()
    monkeypatch.setattr(L,'STATS',{'zero_release':0,'retire_candidate_evals':0})
    monkeypatch.setattr(L,'CTX',{})
    monkeypatch.setattr(v39,'_candidates',L.candidates)
    monkeypatch.setitem(v39.CFG,'price',0.)
    monkeypatch.setitem(v39.CFG,'budget',None)
    monkeypatch.setitem(v39.CTX,'struct_cache',{})
    monkeypatch.setitem(v39.CTX,'cost_mismatch',[])
    rec=state.v39_seats['R',1]
    scored,_=T.accumulate(state.v39_seats,[{'R':'R','slot':1,'state':'F','gen':rec.gen,'delta':-2.}],2)
    state=replace(state,v39_seats=scored)
    saved=repr(state)
    after,events,before_bits,after_bits,_,_=v39.run_conversions(state,2)
    conversion=next(e for e in events if e.get('slot_index')==1)
    assert conversion['V']<0 and conversion['v39']=='FH' and conversion['why']=='neg'
    assert v39.seat_state(after.definitions['R'],after.definitions['R'].constituents[1],after.slot_history)=='H'
    assert before_bits>after_bits and repr(state)==saved
