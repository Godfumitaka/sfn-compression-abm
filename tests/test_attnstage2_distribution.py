"""実際の答えの席を、名前と引数の正解を使わず公開の控えから読む。"""
from dataclasses import replace
from pathlib import Path
from random import Random
from types import SimpleNamespace
import sys
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'tools'),str(Path(__file__).resolve().parents[1])]
import pytest
from test_sme2017_connection import separate
from test_attnstage2_connection import build,retained_U_structure
from attnstage2_sme import Session
from attnstage2_distribution import Readout,global_background,mix_distributions
import attnstage2_readout as R
import v39
import v310be as B
from abm.domains import Abstain,Relation


def normal_scene():
    state,config,obs,ai=build()
    scene=replace(ai.target_graph_partial,relations=tuple(
        replace(r,predicate='sig_n' if r.relation_id=='s' else r.predicate)
        for r in ai.target_graph_partial.relations))
    return state,config,obs,replace(ai,target_graph_partial=scene)


def test_real_F_projection_reads_native_name_distribution_before_feedback():
    state,config,obs,ai=normal_scene()
    public_inputs=[]
    def background(ai_,state_,config_,door):
        public_inputs.append((ai_,door));return {'hold':.2}
    session=Session(ai,state,config,Random(1).getstate(),obs,{},mode='binary',position='k2',
                   door_task=True,readout_policy=Readout(background))
    chosen=session.choose(session.candidates,{})
    record=chosen.payload['readout']
    assert record['slot']==2 and record['state']=='F' and record['reason']=='native_answer_slot'
    assert record['P']==B.probabilities(state.definitions['R'],state.definitions['R'].constituents[2],
                                    state,ai.target_graph_partial,config)['F']
    assert public_inputs==[(ai,True)] and session.background=={'hold':.2}


def test_H_modal_tie_uses_unique_public_gap_distribution_not_correct_name():
    state,config,obs,ai=normal_scene()
    state,_=v39._convert(state,'FH','R',2,1)
    counts=dict(state.p_hat.counts);counts['hold_b']=counts['hold']
    history=dict(state.slot_history);history['R',2]={'hold':1,'hold_b':1}
    state=replace(state,slot_history=history,
                  p_hat=replace(state.p_hat,counts=counts,total=sum(counts.values()),alive_vocab=frozenset(counts)))
    obs.names.add('hold_b')
    session=Session(ai,state,config,Random(1).getstate(),obs,{},mode='binary',position='k2',
                   door_task=True,readout_policy=Readout(lambda *a:{'hold':.2,'hold_b':.2}))
    chosen=session.choose(session.candidates,{})
    assert chosen.answer is None
    record=chosen.payload['readout']
    assert record['slot']==2 and record['state']=='H' and record['eligible_slots']==[2]
    assert record['P']['hold']==record['P']['hold_b']>0
    scored=R.loss(session.candidates,{},('hold',('x',)),3,mode='top1',choose=session.choose,
                  background=session.background)
    assert scored.correct_mass==record['P']['hold'] and scored.source=='selected_slot'


def test_gate_closed_does_not_create_question_shape_or_slot_from_truth():
    state,config,obs,ai=build()
    session=Session(ai,state,config,Random(1).getstate(),obs,{},mode='binary',position='k2',
                   door_task=True,readout_policy=Readout(lambda *a:{'hold':.2}))
    chosen=session.choose(session.candidates,{})
    assert not chosen.payload['readout']['gate_passed']
    assert chosen.payload['readout']['P'] is None and chosen.payload['readout']['slot'] is None
    scored=R.loss(session.candidates,{},('hold',('x',)),3,mode='top1',choose=session.choose,
                  background=session.background)
    assert scored.correct_mass==.2 and scored.source=='background_gate_closed'


def test_missing_background_rule_has_no_default_guess():
    with pytest.raises(ValueError,match='共通b'):Readout(None)


def test_multiple_eligible_silent_slots_are_mixed_without_hidden_name():
    state,config,obs,ai=normal_scene();d=state.definitions['R']
    door,link=d.constituents[2],d.constituents[3]
    d=replace(d,constituents=d.constituents+(
       replace(door,slot_index=4,relation=replace(door.relation,relation_id='door2')),
       replace(link,slot_index=5,relation=replace(link.relation,relation_id='link2',arguments=('seal','door2')))))
    scene=replace(ai.target_graph_partial,relations=ai.target_graph_partial.relations+(
       Relation('l2','attach',('s','hole2')),))
    alignment=SimpleNamespace(relation_mapping={'link':'l','link2':'l2'})
    output=SimpleNamespace(prediction=Abstain(reason='ambiguous_projection'),trace={'R_used':'R'})
    pending=SimpleNamespace(filling_candidate_distribution=({'slot_index':2},{'slot_index':4}))
    record=Readout().prepare(d,alignment,state,scene,config,output,pending,.5)
    expected=mix_distributions([B.probabilities(d,r,state,scene,config)['F'] for r in (d.constituents[2],d.constituents[4])])
    assert record['P']==expected and record['slot']==(2,4)
    assert record['distribution_case']=='equal_slot_mixture'


def test_42five_background_uses_all_observed_counts_without_question_shape():
    state,config,obs,ai=normal_scene()
    expected={p:n/state.p_hat.total for p,n in state.p_hat.counts.items() if n>0}
    assert Readout().background(ai,state,config,True)==expected
    assert Readout().background(ai,state,config,False)==expected
    empty=replace(state,p_hat=SimpleNamespace(total=0,counts={}))
    assert global_background(None,empty,None,False)=={}


def test_equal_slot_mixture_normalizes_and_does_not_create_names():
    mixed=mix_distributions([{'hold':1.},{'hold_b':1.}])
    assert mixed=={'hold':.5,'hold_b':.5}
    assert mix_distributions([])=={}
