"""出生の二段の差・同じ仮問いの重み・既定offと状態不変を検査する。"""
from dataclasses import replace
from functools import partial
from pathlib import Path
from random import Random
import math
import sys
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'tools'),str(Path(__file__).resolve().parents[1])]
import pytest
import attnratio as A
import attnstage2_birth as B
from attnstage2_questions import Snapshot
from attnstage2_initial import VirtualInitial
from attnstage2_distribution import Readout
from test_attnstage2_birth import materials
from test_attncstar import cstar,retained_U_structure,build
from test_sme2017_connection import separate
import attncstar as N
import cstar_runtime as C
import smeshared as S
import v39


@pytest.mark.parametrize('door_probs,other_probs',[
    ((.8,.4,.2),(.5,.5,.25)),
    ((.8,.4,.8),(.8,.4,.8)),
])
def test_two_step_hand_losses_same_questions_weights_and_negative_values(door_probs,other_probs):
    first,second,d,before=materials()
    snapshot=Snapshot(3,1,frozenset({'hold_b'}),frozenset(),True)
    calls=[]
    class Session:
        def __init__(self,state,scene,door):
            self.state,self.scene,self.door=state,scene,door
            self.attention={};self.background={}
            calls.append((repr(state),scene,door))
            self.candidates=(self.candidate(state),)
        def candidate(self,state):
            row=state.definitions['new'].constituents[0]
            st=v39.seat_state(state.definitions['new'],row,state.slot_history)
            p=(door_probs if self.door else other_probs)[('F','H','U').index(st)]
            name='hold_b' if self.door else 'sig_e'
            return A.Candidate('new',1,2,0,(),(name,('y',)),
                {'readout':{'gate_passed':True,'slot':0,'P':{name:p,'unused':1-p}}})
        choose=staticmethod(A.select)
        def thin(self,seat):
            return v39._convert(self.state,'FH' if seat.state=='F' else 'HU',
                                seat.definition,seat.slot,0)[0]
        def rematched(self,seat):return self.candidate(self.thin(seat))
    kwargs=dict(session_factory=Session,loss_mode='top1',length_of=lambda _:5.)
    saved=repr(before)
    off,record_off=B.birth_values(before,d,first,second,snapshot,2,**kwargs)
    off_explicit,record_explicit=B.birth_values(before,d,first,second,snapshot,2,
                                               measure_birth_hu=False,**kwargs)
    assert off==off_explicit
    assert {k:v for k,v in record_off.items() if k!='seconds'}=={
           k:v for k,v in record_explicit.items() if k!='seconds'}
    calls.clear()
    on,record=B.birth_values(before,d,first,second,snapshot,2,measure_birth_hu=True,**kwargs)
    fh=.75*math.log2(door_probs[0]/door_probs[1])+.25*math.log2(other_probs[0]/other_probs[1])
    hu=.75*math.log2(door_probs[1]/door_probs[2])+.25*math.log2(other_probs[1]/other_probs[2])
    assert record['delta_by_slot'][0]==pytest.approx(fh,abs=1e-12)
    assert record['hu_after_fh_delta_by_slot'][0]==pytest.approx(hu,abs=1e-12)
    RF,RH,RU,mass=v39.rec_means(on[0],2)
    assert RH-RF==pytest.approx(fh,abs=1e-12)
    assert RU-RH==pytest.approx(hu,abs=1e-12)
    assert RU-RF==pytest.approx(fh+hu,abs=1e-12) and mass==1.
    assert on[1]==off[1] and on[0].post==v39.ZERO4
    # 元の仮問いとHにした後の仮問いは、可視入力・種類が同じ。
    assert len(calls)==4
    assert calls[0][1:]==calls[1][1:] and calls[2][1:]==calls[3][1:]
    assert all([x['state'] for x in r['hu_after_fh_rows']]==['H'] for r in record['records'])
    assert repr(before)==saved and snapshot.door==3 and snapshot.other==1
    if door_probs[2]>.4:assert RU-RH<0


def test_real_Cstar_two_stage_birth_keeps_prediction_state_and_rng(cstar,retained_U_structure):
    state,cfg,obs,ai=build()
    d=replace(state.definitions['R'],name='fresh',registered_at=2)
    pre=ai,state,cfg,Random(1).getstate(),obs,{},True,(),None
    ctx=dict(definition=d,row=d.constituents[0],first_material=ai.base_graph,
        second_visible=ai.target_graph_partial,trial=2,base_age=1,pre=pre,
        questions=Snapshot(1,1,frozenset({'hold'}),frozenset(),True))
    saved=repr(state),repr(obs.__dict__),S.ENGINE.rng.getstate(),C.snapshot()
    values=[]
    for reuse in (False,True):
        policy=VirtualInitial(loss_mode='top1',mode='global',position='k2',epsilon=.01,
            readout_policy=Readout(),feature_policy=N.Features(),measure_birth_hu=True,
            session_class=partial(N.Session,reuse_structure=reuse))
        rec=v39.SeatRec(0,'F',2,2,v39.ZERO4,v39.ZERO4)
        values.append(policy(rec,'birth',ctx))
        assert any(r.get('hu_after_fh_rows') for r in policy.records[0]['records'])
        assert all(math.isfinite(x) for col in values[-1].init for x in col)
    assert values[0]==values[1]
    assert (repr(state),repr(obs.__dict__),S.ENGINE.rng.getstate(),C.snapshot())==saved
