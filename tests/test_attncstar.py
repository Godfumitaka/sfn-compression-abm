"""指示8の主U維持・候補共通の基底・実C*の再照合の関門。"""
from dataclasses import replace
from types import SimpleNamespace as NS
from random import Random
from pathlib import Path
import math,sys,os,json
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'tools'),str(Path(__file__).resolve().parents[1])]
import pytest
from test_sme2017_connection import separate
from test_attnstage2_connection import build,retained_U_structure
from abm.definition import Constituent,FrequencyTable
from abm.domains import AgentInput,Entity,Relation,RelationGraph
import attncstar as N
import cstar_probability as CP
import cstar_runtime as C
import v39,v310be as B,smeshared as S,probeworld
import attnstage2 as T
from attnstage2_distribution import Readout
from cstar_matcher import CstarMatcher


@pytest.fixture
def cstar(separate,monkeypatch):
    monkeypatch.setattr(C,'CFG',dict(match_cstar=True,match_eps='shared',logp_eps=.01,h_dirichlet=1))
    monkeypatch.setattr(C,'CTX',{})
    monkeypatch.setattr(C,'STATS',{})
    monkeypatch.setattr(C,'ENGINE',CstarMatcher(S.ENGINE.settings,tie_seed=0,tie_uniform=True))
    monkeypatch.setattr(CP,'BACKGROUND_SOURCE',B.probabilities)
    monkeypatch.setattr(B,'probabilities',lambda d,r,st,sc,cfg:C.distributions(d,r,st,sc,cfg)['P'])
    monkeypatch.setattr(B,'EPSILON',.01)
    monkeypatch.setitem(v39.CFG,'h_dirichlet',1)
    monkeypatch.setattr(probeworld,'SNAP_MODULES',(*probeworld.SNAP_MODULES,'cstar_runtime'))
    for key,value in dict(call_seed=True,tie_uniform=True,run_seed=1,trial=2).items():
        monkeypatch.setitem(S.CTX,key,value)


def test_common_base_ignores_candidate_occurrence_and_keeps_native_U(cstar):
    row=Constituent(0,0,Relation('r','sig_n',('a',)),False)
    extra=Constituent(1,0,Relation('q','other',('a','b')),True)
    d0=NS(name='d0',constituents=(row,extra));d1=NS(name='d1',constituents=(row,))
    scene=RelationGraph('visible',(Entity('x'),),(Relation('v','sig_e',('x',)),))
    p=FrequencyTable({'sig_e':1,'sig_n':2,'other':4},7,.1,frozenset({'sig_e','sig_n','other'}))
    state=NS(p_hat=p,slot_history={})
    cfg=NS(higher_order_predicates=frozenset(),local_lambda=1.)
    ai=AgentInput(scene,scene)
    before=repr(state)
    b=N.common_bases(ai,state,cfg)['v']
    assert b=={'other':4/7,'sig_e':1/7,'sig_n':2/7}
    assert C.distributions(d0,row,state,scene,cfg)['P']['U']['sig_e']==1/3
    assert C.distributions(d1,row,state,scene,cfg)['P']['U']['sig_e']==1/7
    assert repr(state)==before


def test_Cstar_rematch_matches_exact_and_does_not_change_main_state(cstar,retained_U_structure):
    state,cfg,obs,ai=build()
    state,_=v39._convert(state,'FH','R',1,1)
    before=repr(state),repr(obs.__dict__),S.ENGINE.rng.getstate(),C.snapshot()
    session=N.Session(ai,state,cfg,Random(1).getstate(),obs,{},mode='global',position='k2',
                      door_task=True,epsilon=.01,readout_policy=Readout(),feature_policy=N.Features())
    assert session.candidates
    assert session.candidates[0].payload['ranked'][4].sme_audit['version']==C.VERSION
    records=[]
    for d in state.definitions.values():
        for row in d.constituents:
            st=v39.seat_state(d,row,state.slot_history)
            if st=='U':continue
            seat=T.Seat(d.name,row.slot_index,st,state.v39_seats[d.name,row.slot_index].gen)
            after=session.rematched(seat)
            exact=next((c for c in session.exact(seat) if c.name==d.name),None)
            assert (after is None)==(exact is None)
            if after is not None:
                assert after.q==exact.q and after.answer==exact.answer and after.mismatch==exact.mismatch
                assert after.payload['readout']==exact.payload['readout']
                assert after.payload['ranked'][1]==exact.payload['ranked'][1]
                assert after.payload['ranked'][4].relation_mapping==exact.payload['ranked'][4].relation_mapping
                records.append(dict(R=d.name,slot=row.slot_index,state=st,Q_before=float(session.candidates[0].q),
                    Q_thin=float(after.q),support=after.payload['ranked'][1],m_before=dict(session.candidates[0].mismatch),
                    m_thin=dict(after.mismatch),readout=after.payload['readout'],
                    mapping=dict(after.payload['ranked'][4].relation_mapping),exact_equal=True))
    assert (repr(state),repr(obs.__dict__),S.ENGINE.rng.getstate(),C.snapshot())==before
    target=os.environ.get('STAGE2_RECORD_DIR')
    if target:
        Path(target).mkdir(parents=True,exist_ok=True)
        (Path(target)/'cstar_seat_comparison.json').write_text(json.dumps(dict(
            rows=records,version=C.VERSION,state_history_observations_rng_unchanged=True),ensure_ascii=False,indent=2)+'\n')


def test_feature_base_frozen_for_thinned_state_and_U_ratio(cstar,retained_U_structure):
    state,cfg,obs,ai=build()
    session=N.Session(ai,state,cfg,Random(1).getstate(),obs,{},mode='global',position='k2',
                      door_task=True,epsilon=.01,readout_policy=Readout(),feature_policy=N.Features())
    policy=session.feature_policy
    changed=replace(state,p_hat=replace(state.p_hat,counts={'sig_n':1000},total=1000,
                                       alive_vocab=frozenset({'sig_n'})))
    assert policy.bases==N.common_bases(ai,state,cfg)
    assert policy.bases!=N.common_bases(ai,changed,cfg)
    for c in session.candidates:
        for detail in c.payload['details']:
            if 'c_P' in detail:
                assert detail['m']==pytest.approx((detail['c_P']-detail['c_b'])/(-math.log(.01)),abs=1e-15)


def test_attention_mixture_uses_gate_passed_set_only():
    from attnratio import Candidate
    def c(name,p,passed):
        return Candidate(name,.5,1,0,(('role',1.),),None,
                         {'readout':{'gate_passed':passed,'slot':0,'P':{'y':p}}})
    cs=(c('inside',.8,True),c('outside',.1,False))
    after,record=N.learn(cs,{'role':.5},disclosed=True,door_task=True,
                        feedback_reader=lambda:('y',4.),background={'y':.5},eta=.1)
    assert record['candidate_names']==['inside'] and record['gradient']['role']==pytest.approx(0.)
    assert after=={'role':.5} and record['L']==pytest.approx(-math.log(.8))


def test_virtual_birth_uses_real_Cstar_session_and_pre_information(cstar,retained_U_structure):
    from attnstage2_initial import VirtualInitial
    from attnstage2_questions import Snapshot
    state,cfg,obs,ai=build()
    definition=replace(state.definitions['R'],name='new',registered_at=2)
    before=repr(state),repr(obs.__dict__),S.ENGINE.rng.getstate(),C.snapshot()
    attention={'independent-key':.5}
    pre=(ai,state,cfg,Random(1).getstate(),obs,attention,True,(),None)
    policy=VirtualInitial(loss_mode='top1',mode='global',position='k2',epsilon=.01,
                          readout_policy=Readout(),feature_policy=N.Features(),session_class=N.Session)
    context=dict(definition=definition,row=definition.constituents[0],first_material=ai.base_graph,
                 second_visible=ai.target_graph_partial,trial=2,base_age=1,pre=pre,
                 questions=Snapshot(1,1,frozenset({'hold'}),frozenset(),True))
    rec=v39.SeatRec(0,'F',2,2,v39.ZERO4,v39.ZERO4)
    value=policy(rec,'birth',context)
    assert all(math.isfinite(v) for column in value.init for v in column)
    assert policy.records[0]['evaluated_questions']>0
    assert policy.records[0]['background_and_attention']=='prediction_before'
    assert (repr(state),repr(obs.__dict__),S.ENGINE.rng.getstate(),C.snapshot())==before
    assert attention=={'independent-key':.5}
